# Cytoscape Desktop guide

The files in this folder are written by the notebook (Phase 6) and open directly in
[Cytoscape Desktop](https://cytoscape.org) (3.9 or later).

| File | What it is |
|---|---|
| `ca-GrQc_lcc.graphml` | Largest connected component with node attributes `degree`, `community`, `pagerank`, `betweenness`, `recommended`; every edge has `interaction = coauthor` |
| `ca-GrQc_lcc_with_predictions.graphml` | Same network plus the recommended links as extra edges with `interaction = predicted`, `predicted = true` and `score` |
| `cytoscape_nodes.csv` | Node table (`node, degree, pagerank, betweenness, community, recommended`) |
| `cytoscape_edges.csv` | Edge list (`source, target, interaction`) |
| `predicted_links.csv` | Recommended links (`source, target, interaction, score, method, rank`) - Top-20 of the best method + Top-10 of the others |

## Option A - GraphML (quickest)
1. **File → Import → Network from File…** and choose `ca-GrQc_lcc_with_predictions.graphml`.
2. All node and edge attributes come in automatically (check the *Node Table* / *Edge Table* tabs).

## Option B - CSV tables
1. **File → Import → Network from File…** → `cytoscape_edges.csv`.
   Set `source` = *Source Node*, `target` = *Target Node*, `interaction` = *Interaction Type*.
2. **File → Import → Table from File…** → `cytoscape_nodes.csv`, *Import Data as: Node Table Columns*,
   key column `node` (matches the network's *shared name*).
3. Optional: import `predicted_links.csv` as a second network the same way and merge with
   **Tools → Merge → Networks → Union**, so the predicted links appear on top of the real ones.

## Layout
* Whole network: **Layout → Prefuse Force Directed Layout** (or *yFiles Organic* if installed).
  The LCC has ~4,000 nodes, so give it a few seconds.
* Recommendation view: select the recommended authors (*Select → Nodes → By column value* → `recommended = true`),
  then **Select → Nodes → First Neighbors of Selected Nodes**, then
  **File → New Network → From Selected Nodes, All Edges**, and apply a force-directed layout to the new network.

## Styling (Style tab)
| Visual property | Mapping |
|---|---|
| Node Size | *Continuous* mapping on `degree` (e.g. 10 → 60) |
| Node Fill Color | *Discrete* mapping on `community` (use *Mapping Value Generators → Rainbow*), **or** *Continuous* on `pagerank` (light → dark blue) |
| Node Label | `name` (author ID); for the overview, show labels only for `recommended = true` via a *Discrete* mapping on Label Font Size (0 / 12) |
| Edge Stroke Color | *Discrete* on `interaction`: `coauthor` → light grey (#B9B8B2), `predicted` → red (#E34948) |
| Edge Line Type | *Discrete* on `interaction`: `coauthor` → Solid, `predicted` → **Dash** |
| Edge Width | *Discrete* on `interaction`: `coauthor` → 1, `predicted` → 4 |
| Edge Transparency | `coauthor` → 80, `predicted` → 255 |

## Screenshots for the report / slides
**File → Export → Network to Image…** → PNG at 300 DPI (or SVG/PDF for vector output).
Suggested screenshots: (1) the full LCC coloured by community, (2) the recommendation sub-network with
dashed red predicted links.

## Optional analyses inside Cytoscape
* **Tools → Analyze Network** (treat as undirected) recomputes degree, clustering, betweenness - a good
  cross-check of the numbers in the report.
* The *clusterMaker2* app (Apps → App Manager) can run community detection (e.g. GLay) for comparison
  with the Louvain `community` column.
