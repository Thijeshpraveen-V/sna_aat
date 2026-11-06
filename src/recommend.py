"""Phase 5: candidate generation, Top-K recommendations, explanations and
the hit-rate check against the held-out test edges."""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from common import METHODS
from scores import neighbour_sets, score_pairs


def distance2_candidates(G: nx.Graph, nbrs: dict | None = None) -> list[tuple]:
    """All non-adjacent pairs (u < v) at shortest-path distance exactly 2,
    i.e. pairs with at least one common neighbour.

    Why only distance 2? For CN, Jaccard and Adamic-Adar every pair at distance
    >= 3 scores exactly 0 (no shared neighbour), so it can never enter a Top-K
    list - restricting to distance 2 loses nothing for these three and shrinks
    the ~13.7 million possible pairs to a few tens of thousands."""
    nbrs = nbrs or neighbour_sets(G)
    cands = set()
    for w in G.nodes():
        nb = sorted(nbrs[w])
        for i, a in enumerate(nb):
            for b in nb[i + 1:]:
                if b not in nbrs[a]:
                    cands.add((a, b))
    return sorted(cands)


def rank_candidates(G: nx.Graph, cands: list[tuple], method: str,
                    nbrs: dict | None = None) -> pd.DataFrame:
    """Score every candidate and sort best-first. Deterministic tie-breaking:
    more common neighbours, then higher Adamic-Adar, then node IDs."""
    df = score_pairs(G, cands, nbrs)
    return (df.sort_values([method, "cn", "adamic_adar", "u", "v"],
                           ascending=[False, False, False, True, True])
              .reset_index(drop=True))


def explain_pair(G: nx.Graph, u: int, v: int, nbrs: dict, max_show: int = 5) -> dict:
    """Why was (u, v) recommended? List the shared collaborators, least-connected
    first (these are the most informative ones, exactly what Adamic-Adar rewards)."""
    shared = sorted(nbrs[u] & nbrs[v], key=lambda w: (len(nbrs[w]), w))
    shown = ", ".join(f"{w} (deg {len(nbrs[w])})" for w in shared[:max_show])
    if len(shared) > max_show:
        shown += f", +{len(shared) - max_show} more"
    dist = nx.shortest_path_length(G, u, v) if nx.has_path(G, u, v) else np.inf
    return {
        "shared_collaborators": shown,
        "shortest_path": dist,
        "explanation": (f"{u} and {v} have never co-authored but share {len(shared)} "
                        f"co-author(s); both sit {dist} hops apart, inside the same "
                        f"collaboration circle."),
    }


def recommend(G: nx.Graph, method: str, k: int, cands: list[tuple] | None = None,
              nbrs: dict | None = None, exclude: nx.Graph | None = None) -> pd.DataFrame:
    """Top-k predicted new links for ``method`` on graph G.

    Filters: no self-pairs and no (v, u) duplicates (candidates are canonical
    u < v pairs), no pairs already linked in G or in ``exclude`` (the full graph).
    """
    nbrs = nbrs or neighbour_sets(G)
    cands = cands if cands is not None else distance2_candidates(G, nbrs)
    ranked = rank_candidates(G, cands, method, nbrs)
    if exclude is not None:
        ranked = ranked[[not exclude.has_edge(u, v) for u, v in zip(ranked.u, ranked.v)]]
    top = ranked.head(k).reset_index(drop=True)
    rows = []
    for i, r in top.iterrows():
        u, v = int(r.u), int(r.v)
        info = explain_pair(G, u, v, nbrs)
        rows.append({
            "rank": i + 1, "method": METHODS[method], "author_u": u, "author_v": v,
            "score": r[method], "common_neighbours": int(r.cn),
            "shortest_path": info["shortest_path"],
            "degree_u": len(nbrs[u]), "degree_v": len(nbrs[v]),
            "shared_collaborators": info["shared_collaborators"],
            "explanation": info["explanation"],
        })
    return pd.DataFrame(rows)


def hit_rate(G_train: nx.Graph, test_pos: list[tuple], ks=(10, 20, 50, 100, 500, 1000),
             nbrs: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Rank all distance-2 candidates of the TRAIN graph and check what fraction
    of each method's Top-K are real held-out test edges (precision@K over the
    realistic candidate pool). Also returns a random-ranking baseline."""
    nbrs = nbrs or neighbour_sets(G_train)
    cands = distance2_candidates(G_train, nbrs)
    test_set = set(test_pos)
    scored = score_pairs(G_train, cands, nbrs)
    scored["is_test"] = [(u, v) in test_set for u, v in zip(scored.u, scored.v)]
    rows = []
    for m in METHODS:
        ranked = scored.sort_values([m, "cn", "adamic_adar", "u", "v"],
                                    ascending=[False, False, False, True, True])
        hits = ranked["is_test"].to_numpy()
        for k in ks:
            rows.append({"method": m, "k": k, "hits": int(hits[:k].sum()),
                         "hit_rate": float(hits[:k].mean())})
    n_test_in_cands = int(scored["is_test"].sum())
    pool = {
        "n_candidates": len(cands),
        "n_test_positives": len(test_pos),
        "n_test_in_candidates": n_test_in_cands,
        "share_test_at_distance_2": n_test_in_cands / len(test_pos),
        "random_baseline_hit_rate": n_test_in_cands / len(cands),
    }
    return pd.DataFrame(rows), pool
