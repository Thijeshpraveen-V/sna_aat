"""Writes VIVA_NOTES.md (concise answers to likely viva questions).
The 'key numbers' are filled in from outputs/results.json."""
from __future__ import annotations

import sys
from math import comb, log
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common import METHODS, RESULTS_JSON, load_json  # noqa: E402

R = load_json(RESULTS_JSON)
MT, MH, MS = R["metrics_test"], R["metrics_hard_negatives"], R["multi_seed"]["summary"]
SF, SL, SP = R["stats_full"], R["stats_lcc"], R["split"]
BEST, BEST_NAME = R["best_method"]["key"], R["best_method"]["name"]
POOL = R["candidate_pool_train"]
hit100 = {h["method"]: h["hit_rate"] for h in R["hit_rate"] if h["k"] == 100}
ratio = (comb(SL["nodes"], 2) - SL["edges"]) / SL["edges"]

rows = "\n".join(
    f"| {METHODS[m]} | {float(MT[m]['roc_auc']):.4f} | {float(MS[m]['roc_auc_mean']):.4f} ± "
    f"{float(MS[m]['roc_auc_std']):.4f} | {float(MT[m]['average_precision']):.4f} | "
    f"{float(MH[m]['roc_auc']):.3f} | {hit100[m]:.2f} |" for m in METHODS)

text = f"""# Viva notes - Link Prediction in the ca-GrQc Co-authorship Network

## Key numbers (from `outputs/results.json`)
* Full graph: **{SF['nodes']:,} authors, {SF['edges']:,} edges**, {SF['connected_components']} components,
  avg clustering **{SF['avg_clustering']:.3f}**, density {SF['density']:.5f}.
* LCC: **{SL['nodes']:,} nodes, {SL['edges']:,} edges**, diameter {SL['diameter']},
  avg shortest path {SL['avg_shortest_path']:.2f}.
* Split: {SP['n_train_pos']:,} train / {SP['n_test_pos']:,} test edges; {SP['n_test_neg']:,} test negatives (1:1).
* Best method: **{BEST_NAME}**.

| Method | ROC-AUC (seed 42) | ROC-AUC (5 seeds) | AP | ROC-AUC hard neg. | Hit rate@100 |
|---|---|---|---|---|---|
{rows}

---

## Why this dataset?
* Real, public, well-known benchmark (SNAP, Leskovec et al. 2007), so results are comparable with the literature.
* Clear social meaning: node = author, edge = co-authored a paper; link prediction = collaborator recommendation.
* Right size: big enough to be realistic ({SF['nodes']:,} nodes) and small enough for exact statistics
  (exact betweenness, exact diameter) on a laptop.
* Interesting structure: heavy-tailed degrees, very high clustering, many communities.

## What does each heuristic measure?
* **Common Neighbours** - number of shared co-authors, |Γ(u) ∩ Γ(v)|. Direct measure of triadic closure.
* **Jaccard** - shared co-authors divided by all co-authors of the pair, |Γ(u) ∩ Γ(v)| / |Γ(u) ∪ Γ(v)|.
  It is a similarity in [0, 1] that removes the bias toward prolific authors.
* **Adamic-Adar** - Σ over shared co-authors w of 1 / log k(w): common neighbours weighted by how *rare* they are.
* **Preferential Attachment** - k(u)·k(v): popularity; "the rich get richer".

## Why does Adamic-Adar weight by 1 / log(degree)?
* A hub with k co-authors connects about k²/2 pairs, so sharing a hub says almost nothing about one specific pair.
  Sharing a co-author who works with only 3 people is strong evidence that u and v are in the same small team.
* 1/log k down-weights hubs *smoothly*: degree 3 → {1 / log(3):.2f}, degree 60 → {1 / log(60):.2f}. With 1/k
  (Resource Allocation) hubs are punished more strongly.
* A common neighbour always has degree ≥ 2, so log k > 0 and there is no division by zero.
* Origin: Adamic & Adar (2003), who used it to predict friendships between personal home pages.

## Why does the PA score favour hubs?
* PA = k(u)·k(v) depends only on degrees. Two hubs get a huge score even if they are in different parts of the
  network with no shared collaborator. A pair of newcomers always scores low.
* It models growth (Barabási-Albert): new links attach preferentially to high-degree nodes. In ca-GrQc hubs are
  members of large multi-author papers, so PA proposes "popular" rather than "close" pairs.
  ROC-AUC {float(MT['pref_attach']['roc_auc']):.3f}: better than random (the network is degree-assortative,
  assortativity {SF['degree_assortativity']:.2f}), but clearly worse than the local indices.

## Why do ROC-AUC and Precision@K both matter?
* **ROC-AUC** looks at the *whole* ranking. It is the probability that a random true link is scored above a random
  non-link. It is threshold-free and insensitive to class balance, but it does not tell you whether the *top* of
  the list is good.
* **Precision@K** looks only at the *top K*, which is what a recommender actually shows a user. A method can have a
  high AUC and still put wrong pairs at the very top (Jaccard: hard-negative P@10 = {float(MH['jaccard']['p@10']):.2f}).
* Here P@K saturated at 1.0 with random negatives, so we added hard negatives and a hit-rate over all
  {POOL['n_candidates']:,} distance-2 candidates to compare the methods at the top of the ranking.

## How was leakage avoided?
1. The test edges are removed **before** any score is computed. All four scores use the **training graph only**.
2. Negatives are sampled from non-edges of the **full** graph, so a hidden test edge can never be labelled negative.
3. The decision threshold is chosen on the **training** pairs, never on the test pairs.
4. Train positives are edges of the training graph, so each is scored with its own edge hidden.
   Otherwise PA (degree +1) and Jaccard (u, v in each other's neighbourhood) would "see" the answer.

## Why was negative sampling needed?
* A ranking metric needs both classes. All non-edges are far too many
  (~{ratio:,.0f} per edge in the LCC) to score and evaluate exhaustively, so we sample them 1:1.
  This gives a balanced, cheap and standard evaluation.
* We also used **hard negatives** (distance-2 non-links): uniform negatives are almost always far apart and easy to
  reject ({R['test_zero_cn_fraction']['negatives']:.1%} of them have no common neighbour), which inflates AUC.

## How was the train graph kept connected?
* We drew a random spanning tree of the LCC (minimum spanning tree over random weights, seed 42). A spanning tree
  contains every bridge. Test edges are sampled only from the non-tree edges, so the training graph keeps all
  {SP['train_graph_nodes']:,} nodes and stays connected ({SP['train_components']} component).

## Limitations
* Random split instead of a temporal one (the SNAP file has no dates).
* The spanning-tree split takes test edges only from cycles, which are easier, so results may be slightly optimistic.
* 1:1 balanced evaluation hides the real imbalance; random negatives are easy.
* CN, Jaccard and AA give 0 to every pair at distance ≥ 3, so they cannot recommend "bridging" collaborations.
* The top recommendations are dominated by a few near-cliques (large multi-author papers). IDs are anonymised,
  so they cannot be checked against real publications.
* Unweighted edges: one joint paper counts the same as twenty.

## How could the work be improved?
* **Katz index**: Σ_l β^l (number of paths of length l). It uses longer paths, so it can score pairs at
  distance ≥ 3. **Resource Allocation** is a stronger version of AA (1/k instead of 1/log k).
* **Node2Vec / DeepWalk embeddings**: learn node vectors from random walks and score pairs by similarity of
  their vectors (Hadamard product + classifier).
* **Supervised classifier**: use CN, JC, AA, PA, degrees and same-community as features and train logistic regression or
  gradient boosting on the training pairs. It learns how to combine the heuristics.
* **Graph neural networks** (GraphSAGE, SEAL), temporal evaluation, weighted edges, and diversity-aware re-ranking
  so that one clique does not fill the Top-K.

## Quick definitions
* **Clustering coefficient**: fraction of a node's neighbour pairs that are themselves linked.
* **Transitivity**: 3 × triangles / connected triples (global clustering).
* **Betweenness**: fraction of shortest paths that pass through a node (brokers).
* **PageRank**: importance from being linked to important nodes (random surfer, damping 0.85).
* **Modularity**: how much denser the communities are than expected at random. Louvain maximises it greedily.
* **Triadic closure**: if A-B and B-C are linked, A-C is likely to become linked.
"""

(ROOT / "VIVA_NOTES.md").write_text(text, encoding="utf-8")
print("wrote VIVA_NOTES.md")
