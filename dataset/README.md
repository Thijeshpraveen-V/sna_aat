# ca-GrQc co-authorship dataset package

## Source
SNAP - Stanford Network Analysis Project, *ca-GrQc: General Relativity and Quantum
Cosmology collaboration network* (arXiv GR-QC, papers Jan 1993 - Apr 2003).
URL: https://snap.stanford.edu/data/ca-GrQc.txt.gz
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
1. Read 28,980 data lines (5,242 distinct author IDs).
2. Removed 12 self-loop lines (an author paired with themself).
3. Put every pair in canonical order (min, max) and removed 14,484 duplicate
   lines (the reverse direction of each pair).
4. Result: 5,242 nodes and 14,484 undirected edges
   (1 author became isolated because their only line was a self-loop).
5. Kept the largest connected component (LCC) for the link-prediction experiments:
   4,158 nodes and 13,422 edges.

## Train/test split (seed = 42)
* A random spanning tree of the LCC (4,157 edges) is always kept in the
  training graph, so the training graph stays connected and no author is isolated
  (every bridge edge is in the spanning tree).
* 2,684 test edges (20 % of 13,422) were sampled
  uniformly from the remaining non-tree edges; the other 10,738 edges form the
  training graph. The training graph keeps all 4,158 LCC nodes and has
  1 connected component(s).

## Negative sampling
Negatives are author pairs that are **not** linked in the FULL graph (so a negative
can never be a hidden positive), sampled uniformly at random with seed 42,
1:1 with the positives: 10,738 train negatives and
2,684 test negatives, the two sets being disjoint.

## Leakage
Test edges are removed from the training graph before any score is computed, and
every heuristic is computed on the training graph only. For train positives
(which are edges of the training graph) the pair's own edge is hidden while
scoring it.
