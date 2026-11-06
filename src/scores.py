"""Phase 3: the four neighbourhood-based link-prediction heuristics, written
from scratch with Python sets, plus a cross-check against NetworkX.

Notation: Gamma(x) is the set of neighbours (co-authors) of author x and
k(x) = |Gamma(x)| is the degree of x.

    Common Neighbours        CN(u,v) = |Gamma(u) & Gamma(v)|
    Jaccard Coefficient      JC(u,v) = |Gamma(u) & Gamma(v)| / |Gamma(u) | Gamma(v)|
    Adamic-Adar              AA(u,v) = sum_{w in Gamma(u) & Gamma(v)} 1 / log k(w)
    Preferential Attachment  PA(u,v) = k(u) * k(v)
"""
from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pandas as pd

from common import METHODS


def neighbour_sets(G: nx.Graph) -> dict:
    """Pre-compute Gamma(x) for every node once (fast repeated lookups)."""
    return {n: set(G[n]) for n in G.nodes()}


def common_neighbours(Nu: set, Nv: set) -> int:
    return len(Nu & Nv)


def jaccard(Nu: set, Nv: set) -> float:
    union = Nu | Nv
    return len(Nu & Nv) / len(union) if union else 0.0


def adamic_adar(Nu: set, Nv: set, nbrs: dict) -> float:
    # A common neighbour w is linked to both u and v, so k(w) >= 2 and
    # log k(w) > 0: the division is always safe.
    return sum(1.0 / math.log(len(nbrs[w])) for w in Nu & Nv)


def preferential_attachment(Nu: set, Nv: set) -> int:
    return len(Nu) * len(Nv)


def score_pairs(G: nx.Graph, pairs, nbrs: dict | None = None,
                hide_pair_edge: bool = False) -> pd.DataFrame:
    """Score every (u, v) pair with all four heuristics on graph ``G``.

    ``hide_pair_edge=True`` is used for TRAIN positives, which are edges of the
    graph they are scored on: u and v are removed from each other's
    neighbourhood so the pair is scored as if that one edge were unknown. This
    stops PA/Jaccard from 'seeing' the very edge they should predict.
    (CN and AA are unaffected, because the edge u-v never creates a common
    neighbour.)
    """
    nbrs = nbrs or neighbour_sets(G)
    rows = []
    for u, v in pairs:
        Nu, Nv = nbrs[u], nbrs[v]
        if hide_pair_edge and v in Nu:
            Nu, Nv = Nu - {v}, Nv - {u}
        rows.append((u, v,
                     common_neighbours(Nu, Nv),
                     jaccard(Nu, Nv),
                     adamic_adar(Nu, Nv, nbrs),
                     preferential_attachment(Nu, Nv)))
    return pd.DataFrame(rows, columns=["u", "v", *METHODS])


def score_labelled(G: nx.Graph, pairs_df: pd.DataFrame, nbrs: dict | None = None) -> pd.DataFrame:
    """Score a labelled pair table (u, v, label). Rows that are edges of G
    (train positives) are scored with their own edge hidden."""
    nbrs = nbrs or neighbour_sets(G)
    pairs = list(pairs_df[["u", "v"]].itertuples(index=False, name=None))
    # hide_pair_edge only changes anything for pairs that are edges of G
    scored = score_pairs(G, pairs, nbrs, hide_pair_edge=True)
    scored.index = pairs_df.index
    return pd.concat([pairs_df[["u", "v", "label"]], scored[list(METHODS)]], axis=1)


def networkx_scores(G: nx.Graph, pairs) -> pd.DataFrame:
    """The same four scores from NetworkX's built-in functions."""
    pairs = list(pairs)
    df = pd.DataFrame(pairs, columns=["u", "v"])
    df["cn"] = [len(list(nx.common_neighbors(G, u, v))) for u, v in pairs]
    df["jaccard"] = [p for _, _, p in nx.jaccard_coefficient(G, pairs)]
    df["adamic_adar"] = [p for _, _, p in nx.adamic_adar_index(G, pairs)]
    df["pref_attach"] = [p for _, _, p in nx.preferential_attachment(G, pairs)]
    return df


def cross_check(G: nx.Graph, pairs) -> dict:
    """Max absolute difference between our scores and NetworkX's (should be ~0).
    Only valid for non-edges of G (NetworkX does not hide the pair's edge)."""
    pairs = list(pairs)
    ours = score_pairs(G, pairs)
    ref = networkx_scores(G, pairs)
    return {m: float(np.max(np.abs(ours[m].to_numpy(float) - ref[m].to_numpy(float))))
            for m in METHODS}
