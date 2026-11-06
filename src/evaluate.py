"""Phase 4: evaluation metrics, threshold selection and multi-seed stability."""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, f1_score, precision_recall_curve,
                             precision_score, recall_score, roc_auc_score, roc_curve)

from common import METHODS, SEED
from data import build_pair_sets
from scores import neighbour_sets, score_labelled

K_VALUES = (10, 20, 50, 100)


def rank_order(scores: np.ndarray, seed: int = SEED) -> np.ndarray:
    """Indices sorted by score (descending). Ties - very common for the
    integer-valued CN - are broken randomly with a fixed seed so that
    Precision@K is not biased by the order in which pairs were listed."""
    tie_break = np.random.default_rng(seed).random(len(scores))
    return np.lexsort((tie_break, -np.asarray(scores, dtype=float)))


def precision_at_k(y: np.ndarray, scores: np.ndarray, ks=K_VALUES) -> dict:
    order = rank_order(scores)
    y_sorted = np.asarray(y)[order]
    return {k: float(y_sorted[:k].mean()) for k in ks}


def best_f1_threshold(y: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    """Threshold t (predict 'link' when score >= t) that maximises F1 on the
    given (training) pairs. Returns (t, F1 at t)."""
    prec, rec, thr = precision_recall_curve(y, scores)
    # precision/recall have one more entry than thresholds; drop the last point
    f1 = np.where(prec[:-1] + rec[:-1] > 0,
                  2 * prec[:-1] * rec[:-1] / np.maximum(prec[:-1] + rec[:-1], 1e-12), 0)
    i = int(np.argmax(f1))
    return float(thr[i]), float(f1[i])


def evaluate_method(train_scored: pd.DataFrame, test_scored: pd.DataFrame, m: str) -> dict:
    y_tr, s_tr = train_scored["label"].to_numpy(), train_scored[m].to_numpy(float)
    y_te, s_te = test_scored["label"].to_numpy(), test_scored[m].to_numpy(float)
    thr, train_f1 = best_f1_threshold(y_tr, s_tr)
    pred = (s_te >= thr).astype(int)
    res = {
        "roc_auc": roc_auc_score(y_te, s_te),
        "average_precision": average_precision_score(y_te, s_te),
        "threshold": thr,
        "train_f1_at_threshold": train_f1,
        "precision": precision_score(y_te, pred, zero_division=0),
        "recall": recall_score(y_te, pred, zero_division=0),
        "f1": f1_score(y_te, pred, zero_division=0),
    }
    res.update({f"p@{k}": v for k, v in precision_at_k(y_te, s_te).items()})
    return res


def evaluate_all(train_scored: pd.DataFrame, test_scored: pd.DataFrame) -> pd.DataFrame:
    """One row per heuristic with every metric."""
    rows = {m: evaluate_method(train_scored, test_scored, m) for m in METHODS}
    df = pd.DataFrame(rows).T
    df.insert(0, "method", [METHODS[m] for m in df.index])
    return df


def curves(test_scored: pd.DataFrame) -> dict:
    """ROC and precision-recall curve points for every heuristic."""
    y = test_scored["label"].to_numpy()
    out = {}
    for m in METHODS:
        s = test_scored[m].to_numpy(float)
        fpr, tpr, _ = roc_curve(y, s)
        prec, rec, _ = precision_recall_curve(y, s)
        out[m] = {"fpr": fpr, "tpr": tpr, "precision": prec, "recall": rec}
    return out


def multi_seed_auc(G: nx.Graph, seeds=(42, 43, 44, 45, 46)) -> pd.DataFrame:
    """Repeat split -> negative sampling -> scoring -> ROC-AUC/AP for several
    seeds to show that the results do not depend on one lucky split."""
    rows = []
    for seed in seeds:
        sp = build_pair_sets(G, seed=seed)
        nbrs = neighbour_sets(sp["G_train"])
        test_scored = score_labelled(sp["G_train"], sp["test_pairs"], nbrs)
        y = test_scored["label"].to_numpy()
        for m in METHODS:
            s = test_scored[m].to_numpy(float)
            rows.append({"seed": seed, "method": m,
                         "roc_auc": roc_auc_score(y, s),
                         "average_precision": average_precision_score(y, s)})
    return pd.DataFrame(rows)


def summarise_seeds(df: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("method")[["roc_auc", "average_precision"]].agg(["mean", "std"])
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg = agg.reindex(list(METHODS))
    agg.insert(0, "name", [METHODS[m] for m in agg.index])
    return agg
