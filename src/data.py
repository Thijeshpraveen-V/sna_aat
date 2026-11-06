"""Phase 1 & 2: loading, cleaning, network statistics, edge split and
negative sampling for the SNAP ca-GrQc co-authorship network."""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from common import DATASET_DIR, RAW_FILE, RAW_URL, SEED


# ---------------------------------------------------------------------------
# Loading and cleaning
# ---------------------------------------------------------------------------
def download_raw(path: Path = RAW_FILE, url: str = RAW_URL) -> Path:
    """Download the gzipped SNAP edge list if it is not already present."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, path)
    return path


def load_raw_edges(path: Path = RAW_FILE) -> pd.DataFrame:
    """Read the raw tab-separated edge list (lines starting with '#' are comments)."""
    return pd.read_csv(path, sep="\t", comment="#", header=None,
                       names=["source", "target"], dtype=np.int64)


def clean_edges(raw: pd.DataFrame) -> tuple[nx.Graph, pd.DataFrame, dict]:
    """Build an undirected, unweighted simple graph and log every cleaning step.

    1. Self-loops (u == u) are dropped - an author cannot co-author with themself.
    2. Each pair (u, v) is put in canonical order (min, max) so that the two
       directions stored by SNAP collapse into one undirected edge.
    3. Duplicate undirected pairs are dropped.
    Every node ID that appears in the file is kept as a node, even if it only
    appeared in a self-loop (it then becomes an isolated author).
    """
    log = {"raw_lines": len(raw)}
    all_nodes = np.union1d(raw["source"].unique(), raw["target"].unique())
    log["raw_unique_nodes"] = len(all_nodes)

    self_loop = raw["source"] == raw["target"]
    log["self_loop_lines_removed"] = int(self_loop.sum())
    df = raw.loc[~self_loop].copy()

    df["u"] = df[["source", "target"]].min(axis=1)
    df["v"] = df[["source", "target"]].max(axis=1)
    before = len(df)
    df = df.drop_duplicates(["u", "v"])[["u", "v"]].sort_values(["u", "v"])
    log["duplicate_lines_removed"] = before - len(df)

    G = nx.Graph()
    G.add_nodes_from(sorted(all_nodes.tolist()))
    G.add_edges_from(df.itertuples(index=False, name=None))
    log["clean_nodes"] = G.number_of_nodes()
    log["clean_edges"] = G.number_of_edges()
    log["isolated_nodes_after_cleaning"] = nx.number_of_isolates(G)
    return G, df.reset_index(drop=True), log


def largest_cc(G: nx.Graph) -> nx.Graph:
    return G.subgraph(max(nx.connected_components(G), key=len)).copy()


# ---------------------------------------------------------------------------
# Phase 1: statistics and centrality
# ---------------------------------------------------------------------------
def basic_stats(G: nx.Graph, path_stats: bool = False) -> dict:
    """Standard descriptive statistics. Path statistics (diameter, average
    shortest path length) are only defined on a connected graph, so they are
    computed exactly when ``path_stats=True`` (we do this on the LCC)."""
    n, m = G.number_of_nodes(), G.number_of_edges()
    degrees = np.array([d for _, d in G.degree()])
    comps = list(nx.connected_components(G))
    stats = {
        "nodes": n,
        "edges": m,
        "density": nx.density(G),
        "avg_degree": 2 * m / n,
        "max_degree": int(degrees.max()),
        "median_degree": float(np.median(degrees)),
        "avg_clustering": nx.average_clustering(G),
        "transitivity": nx.transitivity(G),
        "connected_components": len(comps),
        "lcc_nodes": max(len(c) for c in comps),
        "isolated_nodes": nx.number_of_isolates(G),
        "degree_assortativity": nx.degree_assortativity_coefficient(G),
    }
    if path_stats:
        stats["diameter"] = nx.diameter(G)
        stats["avg_shortest_path"] = nx.average_shortest_path_length(G)
    return stats


def degree_distribution(G: nx.Graph) -> pd.DataFrame:
    counts = pd.Series(dict(G.degree())).value_counts().sort_index()
    return pd.DataFrame({"degree": counts.index, "count": counts.values,
                         "fraction": counts.values / G.number_of_nodes()})


def centrality_table(G: nx.Graph, betweenness_k: int | None = None) -> pd.DataFrame:
    """Degree, betweenness and PageRank for every node.

    Betweenness is exact when ``betweenness_k`` is None, otherwise it is
    approximated from ``k`` sampled source nodes (seeded)."""
    deg = dict(G.degree())
    btw = nx.betweenness_centrality(G, k=betweenness_k, seed=SEED, normalized=True)
    pr = nx.pagerank(G, alpha=0.85)
    df = pd.DataFrame({"node": list(G.nodes())})
    df["degree"] = df["node"].map(deg)
    df["degree_centrality"] = df["degree"] / (G.number_of_nodes() - 1)
    df["betweenness"] = df["node"].map(btw)
    df["pagerank"] = df["node"].map(pr)
    return df


def top_k_by(df: pd.DataFrame, column: str, k: int = 10) -> pd.DataFrame:
    return (df.sort_values([column, "node"], ascending=[False, True])
              .head(k).reset_index(drop=True))


# ---------------------------------------------------------------------------
# Phase 2: edge split and negative sampling
# ---------------------------------------------------------------------------
def canonical(u, v) -> tuple:
    return (u, v) if u <= v else (v, u)


def split_edges(G: nx.Graph, test_frac: float = 0.2, seed: int = SEED):
    """80/20 edge split that never disconnects the training graph.

    A *random spanning forest* is built first (minimum spanning forest over
    random edge weights). Its edges - which include every bridge - always stay
    in the training graph, so the training graph has exactly the same connected
    components as the full graph and no node becomes isolated. The test edges
    are then sampled uniformly (seeded) from the remaining, non-forest edges.

    Returns (G_train, train_pos, test_pos) where the edge lists are sorted
    lists of canonical (u, v) tuples.
    """
    rng = np.random.default_rng(seed)
    edges = sorted(canonical(u, v) for u, v in G.edges())
    H = nx.Graph()
    H.add_nodes_from(G.nodes())
    H.add_weighted_edges_from((u, v, w) for (u, v), w in zip(edges, rng.random(len(edges))))
    forest = {canonical(u, v) for u, v in nx.minimum_spanning_edges(H, data=False)}
    removable = [e for e in edges if e not in forest]

    n_test = int(round(test_frac * len(edges)))
    if n_test > len(removable):
        raise ValueError("Not enough non-forest edges for the requested test size")
    idx = rng.choice(len(removable), size=n_test, replace=False)
    test_pos = sorted(removable[i] for i in idx)
    test_set = set(test_pos)
    train_pos = [e for e in edges if e not in test_set]

    G_train = nx.Graph()
    G_train.add_nodes_from(G.nodes())   # keep ALL nodes
    G_train.add_edges_from(train_pos)
    return G_train, train_pos, test_pos


def sample_negatives(G_full: nx.Graph, n: int, rng: np.random.Generator,
                     exclude: set | None = None) -> list[tuple]:
    """Uniformly sample ``n`` distinct node pairs that are NOT edges of the
    FULL graph (so a 'negative' can never be a hidden test positive).
    ``exclude`` holds pairs already used, e.g. the train negatives when the
    test negatives are drawn, keeping both sets disjoint."""
    nodes = np.array(sorted(G_full.nodes()))
    chosen, taken = [], set(exclude or ())
    while len(chosen) < n:
        u, v = rng.choice(nodes, size=2, replace=True)
        if u == v:
            continue
        pair = canonical(int(u), int(v))
        if pair in taken or G_full.has_edge(*pair):
            continue
        taken.add(pair)
        chosen.append(pair)
    return chosen


def sample_hard_negatives(G_full: nx.Graph, G_train: nx.Graph, n: int,
                          rng: np.random.Generator, exclude: set | None = None) -> list[tuple]:
    """'Hard' negatives: non-edges of the full graph that are at distance
    exactly 2 in the training graph (they share at least one collaborator).
    Used only for an extra robustness check."""
    taken = set(exclude or ())
    cands = set()
    for w in G_train.nodes():
        nb = sorted(G_train[w])
        for i in range(len(nb)):
            for j in range(i + 1, len(nb)):
                cands.add((nb[i], nb[j]))
    cands = sorted(p for p in cands if not G_full.has_edge(*p) and p not in taken)
    idx = rng.choice(len(cands), size=min(n, len(cands)), replace=False)
    return [cands[i] for i in sorted(idx)]


def build_pair_sets(G: nx.Graph, seed: int = SEED, test_frac: float = 0.2):
    """Run the full Phase 2 pipeline for one seed.

    Returns a dict with the train graph and two labelled DataFrames:
      train_pairs = train positives (edges of G_train) + 1:1 random negatives
      test_pairs  = held-out test positives           + 1:1 random negatives
    Train and test negatives are disjoint and never edges of the full graph.
    """
    rng = np.random.default_rng(seed)
    G_train, train_pos, test_pos = split_edges(G, test_frac, seed)
    train_neg = sample_negatives(G, len(train_pos), rng)
    test_neg = sample_negatives(G, len(test_pos), rng, exclude=set(train_neg))

    def frame(pos, neg):
        df = pd.DataFrame(pos + neg, columns=["u", "v"])
        df["label"] = [1] * len(pos) + [0] * len(neg)
        return df

    return {
        "G_train": G_train,
        "train_pos": train_pos, "test_pos": test_pos,
        "train_neg": train_neg, "test_neg": test_neg,
        "train_pairs": frame(train_pos, train_neg),
        "test_pairs": frame(test_pos, test_neg),
        "rng": rng,
    }


# ---------------------------------------------------------------------------
# Dataset package
# ---------------------------------------------------------------------------
def save_dataset_package(clean_df: pd.DataFrame, split: dict, nodes_df: pd.DataFrame,
                         out_dir: Path = DATASET_DIR) -> dict:
    """Write the processed dataset files and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw": out_dir / "raw" / "ca-GrQc.txt.gz",
        "raw_txt": out_dir / "raw" / "ca-GrQc.txt",
        "clean": out_dir / "ca-GrQc_clean_edges.csv",
        "train": out_dir / "train_edges.csv",
        "test": out_dir / "test_edges.csv",
        "train_graph": out_dir / "train_graph_edges.csv",
        "nodes": out_dir / "nodes.csv",
    }
    if not paths["raw_txt"].exists():   # uncompressed copy of the raw file
        import gzip
        with gzip.open(paths["raw"], "rb") as src, open(paths["raw_txt"], "wb") as dst:
            shutil.copyfileobj(src, dst)
    clean_df.to_csv(paths["clean"], index=False)
    split["train_pairs"].to_csv(paths["train"], index=False)
    split["test_pairs"].to_csv(paths["test"], index=False)
    pd.DataFrame(split["train_pos"], columns=["u", "v"]).to_csv(paths["train_graph"], index=False)
    nodes_df.to_csv(paths["nodes"], index=False)
    return {k: str(p.relative_to(out_dir.parent)).replace("\\", "/") for k, p in paths.items()}


def write_dataset_readme(log: dict, split_info: dict, path: Path = DATASET_DIR / "README.md") -> Path:
    """Generate dataset/README.md from the actual cleaning/split numbers."""
    text = f"""# ca-GrQc co-authorship dataset package

## Source
SNAP - Stanford Network Analysis Project, *ca-GrQc: General Relativity and Quantum
Cosmology collaboration network* (arXiv GR-QC, papers Jan 1993 - Apr 2003).
URL: {RAW_URL}
Reference: J. Leskovec, J. Kleinberg, C. Faloutsos. *Graph Evolution: Densification
and Shrinking Diameters.* ACM TKDD, 1(1), 2007.

Network model: node = author, edge = the two authors co-authored at least one
paper. Undirected, unweighted, no self-loops.

## Files
| File | Content |
|---|---|
| `raw/ca-GrQc.txt.gz`, `raw/ca-GrQc.txt` | Original SNAP file (tab-separated `FromNodeId ToNodeId`, '#' comment header; every undirected pair is stored in both directions) |
| `ca-GrQc_clean_edges.csv` | Cleaned undirected edge list of the full graph, columns `u,v` with `u < v` |
| `train_graph_edges.csv` | Edges of the training graph (80 % of the LCC edges) - all link scores are computed on this graph only |
| `train_edges.csv` | Training pairs `u,v,label`: train positives (label 1) + 1:1 sampled non-edges (label 0). Used only to choose the decision threshold |
| `test_edges.csv` | Test pairs `u,v,label`: held-out 20 % positives (label 1) + 1:1 sampled non-edges (label 0) |
| `nodes.csv` | One row per author: degree (full graph), in_lcc, degree in the train graph, betweenness, PageRank |
| `dataset.zip` | Everything above in one archive |

## Preprocessing steps
1. Read {log['raw_lines']:,} data lines ({log['raw_unique_nodes']:,} distinct author IDs).
2. Removed {log['self_loop_lines_removed']} self-loop lines (an author paired with themself).
3. Put every pair in canonical order (min, max) and removed {log['duplicate_lines_removed']:,} duplicate
   lines (the reverse direction of each pair).
4. Result: {log['clean_nodes']:,} nodes and {log['clean_edges']:,} undirected edges
   ({log['isolated_nodes_after_cleaning']} author became isolated because their only line was a self-loop).
5. Kept the largest connected component (LCC) for the link-prediction experiments:
   {split_info['lcc_nodes']:,} nodes and {split_info['lcc_edges']:,} edges.

## Train/test split (seed = {split_info['seed']})
* A random spanning tree of the LCC ({split_info['forest_edges']:,} edges) is always kept in the
  training graph, so the training graph stays connected and no author is isolated
  (every bridge edge is in the spanning tree).
* {split_info['n_test_pos']:,} test edges (20 % of {split_info['lcc_edges']:,}) were sampled
  uniformly from the remaining non-tree edges; the other {split_info['n_train_pos']:,} edges form the
  training graph. The training graph keeps all {split_info['lcc_nodes']:,} LCC nodes and has
  {split_info['train_components']} connected component(s).

## Negative sampling
Negatives are author pairs that are **not** linked in the FULL graph (so a negative
can never be a hidden positive), sampled uniformly at random with seed {split_info['seed']},
1:1 with the positives: {split_info['n_train_neg']:,} train negatives and
{split_info['n_test_neg']:,} test negatives, the two sets being disjoint.

## Leakage
Test edges are removed from the training graph before any score is computed, and
every heuristic is computed on the training graph only. For train positives
(which are edges of the training graph) the pair's own edge is hidden while
scoring it.
"""
    path.write_text(text, encoding="utf-8")
    return path
