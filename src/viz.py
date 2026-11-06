"""Phase 4-6 plotting, interactive HTML and Cytoscape export.

Every static figure is written to /visualizations as both .png and .svg.
Colour roles (validated categorical palette, fixed order, never cycled):
one fixed hue per heuristic, grey for existing edges, dashed red for
predicted links.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

from common import CYTO_DIR, METHODS, OUTPUT_DIR, SEED, VIZ_DIR  # noqa: E402

# --- palette ---------------------------------------------------------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#6250d6", "#e34948"]
METHOD_COLOR = dict(zip(METHODS, SERIES))
METHOD_STYLE = {"cn": "-", "jaccard": "--", "adamic_adar": "-", "pref_attach": ":"}
METHOD_MARKER = {"cn": "o", "jaccard": "s", "adamic_adar": "D", "pref_attach": "^"}
TEXT, TEXT_2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
GRID, EDGE_GREY, OTHER_GREY = "#e4e3df", "#b9b8b2", "#c9c8c2"
PREDICTED_RED = "#e34948"
BLUE_SEQ = LinearSegmentedColormap.from_list(
    "blue_seq", ["#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])


def set_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.edgecolor": MUTED, "axes.labelcolor": TEXT_2, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2, "legend.frameon": False,
        "lines.linewidth": 2, "svg.fonttype": "none",
    })


def save_fig(fig, name: str, out_dir: Path = VIZ_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for ext in ("png", "svg"):
        p = out_dir / f"{name}.{ext}"
        fig.savefig(p, facecolor="white")
        paths[ext] = p
    plt.close(fig)
    return paths


# --- Phase 1: degree distribution -------------------------------------------
def plot_degree_distribution(G: nx.Graph, title_suffix: str = ""):
    deg = np.array([d for _, d in G.degree() if d > 0])
    values, counts = np.unique(deg, return_counts=True)
    pk = counts / counts.sum()
    ccdf = np.array([(deg >= k).mean() for k in values])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].scatter(values, pk, s=22, color=SERIES[0], edgecolor="white", linewidth=0.6)
    axes[0].set(xscale="log", yscale="log", xlabel="Degree k (number of co-authors)",
                ylabel="P(k)", title=f"Degree distribution{title_suffix}")
    axes[1].plot(values, ccdf, color=SERIES[0], marker="o", markersize=4)
    axes[1].set(xscale="log", yscale="log", xlabel="Degree k",
                ylabel="P(K >= k)", title="Complementary CDF (log-log)")
    fig.tight_layout()
    return fig


# --- Phase 4: evaluation plots ----------------------------------------------
def _method_lines(ax, xy: dict, metric_label: dict):
    for m in METHODS:
        x, y = xy[m]
        ax.plot(x, y, METHOD_STYLE[m], color=METHOD_COLOR[m],
                label=f"{METHODS[m]} ({metric_label[m]})")


def plot_roc(curves: dict, metrics: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 5.2))
    _method_lines(ax, {m: (c["fpr"], c["tpr"]) for m, c in curves.items()},
                  {m: f"AUC = {metrics.loc[m, 'roc_auc']:.3f}" for m in METHODS})
    ax.plot([0, 1], [0, 1], color=MUTED, linewidth=1, linestyle="--", label="Random (AUC = 0.5)")
    ax.set(xlabel="False positive rate", ylabel="True positive rate",
           title="ROC curves on the test set", xlim=(0, 1), ylim=(0, 1.01))
    ax.legend(loc="lower right")
    return fig


def plot_pr(curves: dict, metrics: pd.DataFrame, base_rate: float = 0.5):
    fig, ax = plt.subplots(figsize=(6, 5.2))
    _method_lines(ax, {m: (c["recall"], c["precision"]) for m, c in curves.items()},
                  {m: f"AP = {metrics.loc[m, 'average_precision']:.3f}" for m in METHODS})
    ax.axhline(base_rate, color=MUTED, linewidth=1, linestyle="--",
               label=f"Random (AP = {base_rate:.2f})")
    ax.set(xlabel="Recall", ylabel="Precision", title="Precision-Recall curves on the test set",
           xlim=(0, 1), ylim=(0.4, 1.01))
    ax.legend(loc="lower left")
    return fig


def plot_metric_bars(metrics: pd.DataFrame, cols=("roc_auc", "average_precision", "f1"),
                     labels=("ROC-AUC", "Average Precision", "F1 @ threshold")):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    x = np.arange(len(cols))
    width = 0.19
    for i, m in enumerate(METHODS):
        vals = metrics.loc[m, list(cols)].astype(float).to_numpy()
        bars = ax.bar(x + (i - 1.5) * width, vals, width * 0.92, color=METHOD_COLOR[m],
                      label=METHODS[m])
        ax.bar_label(bars, fmt="%.3f", fontsize=7.5, color=TEXT_2, padding=2)
    ax.set_xticks(x, labels)
    ax.set(ylim=(0.5, 1.03), ylabel="Score", title="Heuristic comparison on the test set")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    ax.grid(axis="x", visible=False)
    return fig


def plot_precision_at_k(panels: dict):
    """panels: {panel title: DataFrame(index=method, columns=K values)}"""
    fig, axes = plt.subplots(1, len(panels), figsize=(5 * len(panels), 4), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (title, df) in zip(axes, panels.items()):
        ks = [int(k) for k in df.columns]
        for m in METHODS:
            ax.plot(range(len(ks)), df.loc[m].to_numpy(float), METHOD_STYLE[m],
                    marker=METHOD_MARKER[m], markersize=7, color=METHOD_COLOR[m],
                    label=METHODS[m])
        ax.set_xticks(range(len(ks)), [str(k) for k in ks])
        ax.set(xlabel="K", title=title, ylim=(-0.03, 1.05))
    axes[0].set_ylabel("Precision@K")
    axes[-1].legend(loc="lower left")
    fig.tight_layout()
    return fig


def plot_seed_stability(summary: pd.DataFrame, n_seeds: int):
    fig, ax = plt.subplots(figsize=(7, 3.6))
    order = list(METHODS)[::-1]
    for i, m in enumerate(order):
        mean, std = summary.loc[m, "roc_auc_mean"], summary.loc[m, "roc_auc_std"]
        ax.errorbar(mean, i, xerr=std, fmt=METHOD_MARKER[m], color=METHOD_COLOR[m],
                    markersize=9, capsize=5, elinewidth=2)
        ax.annotate(f"{mean:.4f} ± {std:.4f}", (mean, i), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=8.5, color=TEXT_2)
    ax.set_yticks(range(len(order)), [METHODS[m] for m in order])
    ax.margins(x=0.08)
    ax.set(xlabel="ROC-AUC (mean ± std)", ylim=(-0.6, len(order) - 0.3),
           title=f"Stability of ROC-AUC over {n_seeds} random splits")
    ax.grid(axis="y", visible=False)
    return fig


def plot_hit_rate(hits: pd.DataFrame, baseline: float):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ks = sorted(hits["k"].unique())
    for m in METHODS:
        d = hits[hits.method == m].set_index("k").loc[ks]
        ax.plot(range(len(ks)), d["hit_rate"], METHOD_STYLE[m], marker=METHOD_MARKER[m],
                markersize=7, color=METHOD_COLOR[m], label=METHODS[m])
    ax.axhline(baseline, color=MUTED, linewidth=1, linestyle="--",
               label=f"Random candidate ({baseline:.3f})")
    ax.set_xticks(range(len(ks)), [str(k) for k in ks])
    ax.set(xlabel="K (top-ranked distance-2 candidate pairs)", ylabel="Hit rate",
           title="Top-K predictions that are real held-out collaborations", ylim=(-0.03, 1.05))
    ax.legend(loc="lower left", fontsize=8.5)
    return fig


# --- Phase 6: network pictures ----------------------------------------------
def lcc_layout(L: nx.Graph, cache: Path = OUTPUT_DIR / "lcc_layout.csv") -> dict:
    """Force-directed (energy-based spring) layout of the LCC, seeded and
    cached because it takes ~45 s."""
    if cache.exists():
        df = pd.read_csv(cache)
        if set(df.node) == set(L.nodes()):
            return {int(r.node): (r.x, r.y) for r in df.itertuples()}
    pos = nx.spring_layout(L, seed=SEED, method="energy")
    pd.DataFrame([(n, x, y) for n, (x, y) in pos.items()],
                 columns=["node", "x", "y"]).to_csv(cache, index=False)
    return pos


def _draw_edges(ax, G, pos, color=EDGE_GREY, alpha=0.25, width=0.3):
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=color, alpha=alpha, width=width)


def plot_network_overview(L: nx.Graph, pos: dict):
    deg = dict(L.degree())
    nodes = sorted(L.nodes(), key=deg.get)          # hubs drawn last (on top)
    fig, ax = plt.subplots(figsize=(10, 9))
    _draw_edges(ax, L, pos)
    sc = ax.scatter([pos[n][0] for n in nodes], [pos[n][1] for n in nodes],
                    s=[4 + 1.6 * deg[n] for n in nodes], c=[deg[n] for n in nodes],
                    cmap=BLUE_SEQ, norm=LogNorm(1, max(deg.values())),
                    edgecolors="white", linewidths=0.25, zorder=3)
    cb = fig.colorbar(sc, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label("Degree (log scale)", color=TEXT_2)
    ax.set_title(f"ca-GrQc largest connected component: {L.number_of_nodes():,} authors, "
                 f"{L.number_of_edges():,} co-authorships\n(node size and colour = degree)")
    ax.axis("off")
    return fig


def plot_communities(L: nx.Graph, pos: dict, communities: list[set], n_colour: int = 8):
    """Colour the n_colour largest Louvain communities (fixed palette order),
    fold the rest into grey 'Other', and label each coloured community at its
    centroid so identity never relies on colour alone."""
    comms = sorted(communities, key=len, reverse=True)
    colour = {n: OTHER_GREY for n in L}
    for i, c in enumerate(comms[:n_colour]):
        for n in c:
            colour[n] = SERIES[i]
    deg = dict(L.degree())
    fig, ax = plt.subplots(figsize=(10, 9))
    _draw_edges(ax, L, pos, alpha=0.18)
    nodes = sorted(L.nodes(), key=lambda n: colour[n] != OTHER_GREY)
    ax.scatter([pos[n][0] for n in nodes], [pos[n][1] for n in nodes],
               s=[4 + 1.2 * deg[n] for n in nodes], c=[colour[n] for n in nodes],
               edgecolors="white", linewidths=0.25, zorder=3)
    handles = []
    for i, c in enumerate(comms[:n_colour]):
        xy = np.array([pos[n] for n in c]).mean(axis=0)
        ax.annotate(f"C{i + 1}", xy, fontsize=11, fontweight="bold", color=TEXT, ha="center",
                    va="center", zorder=5,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=SERIES[i], lw=1.5))
        handles.append(plt.Line2D([], [], marker="o", linestyle="", color=SERIES[i],
                                  markersize=8, label=f"C{i + 1}: {len(c)} authors"))
    rest = sum(len(c) for c in comms[n_colour:])
    handles.append(plt.Line2D([], [], marker="o", linestyle="", color=OTHER_GREY, markersize=8,
                              label=f"Other {len(comms) - n_colour} communities: {rest} authors"))
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, frameon=True, framealpha=0.9)
    ax.set_title(f"Louvain communities ({len(comms)} communities, "
                 f"modularity = {nx.community.modularity(L, communities):.3f})")
    ax.axis("off")
    return fig


def recommendation_subgraph(G: nx.Graph, recs: pd.DataFrame) -> nx.Graph:
    """Recommended endpoints + all their shared collaborators, with existing
    co-author edges (kind='existing') and predicted links (kind='predicted')."""
    nodes = set()
    for u, v in zip(recs.author_u, recs.author_v):
        nodes |= {u, v} | (set(G[u]) & set(G[v]))
    H = nx.Graph(G.subgraph(nodes))
    nx.set_edge_attributes(H, "existing", "kind")
    for r in recs.itertuples():
        H.add_edge(r.author_u, r.author_v, kind="predicted", score=float(r.score), rank=int(r.rank))
    return H


def plot_recommendation_subgraph(H: nx.Graph, title: str):
    """Each connected group is drawn on its own: recommended authors on an inner
    ring (so the dashed red predicted links between them are readable), their
    shared collaborators on an outer ring, existing edges faint grey."""
    endpoints = {n for u, v, d in H.edges(data=True) if d["kind"] == "predicted" for n in (u, v)}
    groups = sorted(nx.connected_components(H), key=len, reverse=True)
    fig, axes = plt.subplots(1, len(groups), figsize=(6.2 * len(groups), 6.8), squeeze=False)
    for ax, comp in zip(axes[0], groups):
        S = H.subgraph(comp)
        inner = sorted(n for n in comp if n in endpoints)
        outer = sorted(n for n in comp if n not in endpoints)
        pos = nx.shell_layout(S, nlist=[inner, outer] if outer else [inner])
        pos.update({n: 0.58 * np.asarray(pos[n]) for n in inner})
        existing = [(u, v) for u, v, d in S.edges(data=True) if d["kind"] == "existing"]
        predicted = [(u, v) for u, v, d in S.edges(data=True) if d["kind"] == "predicted"]
        nx.draw_networkx_edges(S, pos, edgelist=existing, ax=ax, edge_color=EDGE_GREY,
                               width=0.35, alpha=0.35)
        nx.draw_networkx_edges(S, pos, edgelist=predicted, ax=ax, edge_color=PREDICTED_RED,
                               width=2.4, style="dashed")
        nx.draw_networkx_nodes(S, pos, nodelist=outer, ax=ax, node_size=45, node_color="#9ec5f4",
                               edgecolors="white", linewidths=0.5)
        nx.draw_networkx_nodes(S, pos, nodelist=inner, ax=ax, node_size=260, node_color=SERIES[0],
                               edgecolors="white", linewidths=1.5)
        nx.draw_networkx_labels(S, pos, labels={n: str(n) for n in inner}, ax=ax, font_size=8.5,
                                font_color=TEXT, verticalalignment="bottom",
                                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                                          alpha=0.85))
        ax.set_title(f"{len(inner)} recommended authors, {len(predicted)} predicted links, "
                     f"{len(outer)} shared co-authors", fontsize=10)
        ax.set_xlim(-1.15, 1.15)
        ax.set_ylim(-1.15, 1.15)
        ax.axis("off")
    fig.legend(handles=[
        plt.Line2D([], [], color=EDGE_GREY, linewidth=1.5, label="Existing co-authorship"),
        plt.Line2D([], [], color=PREDICTED_RED, linewidth=2.2, linestyle="--",
                   label="Predicted new collaboration"),
        plt.Line2D([], [], marker="o", linestyle="", color=SERIES[0], markersize=10,
                   label="Recommended author"),
        plt.Line2D([], [], marker="o", linestyle="", color="#9ec5f4", markersize=7,
                   label="Shared collaborator")], loc="lower center", ncol=4)
    fig.suptitle(title, fontweight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    return fig


def plot_recommendation_pairs(G: nx.Graph, recs: pd.DataFrame, cols: int = 2):
    """Small multiples: ego network of each recommended pair - u and v (dark
    blue), shared collaborators (light blue), their other co-authors (grey);
    the predicted link is dashed red. ``recs`` needs a ``method`` column."""
    rows = int(np.ceil(len(recs) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 5.4 * rows), squeeze=False)
    for ax, r in zip(np.ravel(axes), recs.itertuples()):
        u, v = r.author_u, r.author_v
        shared = set(G[u]) & set(G[v])
        others = (set(G[u]) | set(G[v])) - shared - {u, v}
        H = G.subgraph({u, v} | shared | others)
        pos = nx.spring_layout(H, seed=SEED, iterations=300)
        nx.draw_networkx_edges(H, pos, ax=ax, edge_color=EDGE_GREY, width=0.4, alpha=0.5)
        nx.draw_networkx_edges(nx.Graph([(u, v)]), pos, ax=ax, edge_color=PREDICTED_RED,
                               width=2.8, style="dashed")
        nx.draw_networkx_nodes(H, pos, nodelist=sorted(others), ax=ax, node_size=18,
                               node_color=OTHER_GREY, edgecolors="white", linewidths=0.3)
        nx.draw_networkx_nodes(H, pos, nodelist=sorted(shared), ax=ax, node_size=40,
                               node_color="#9ec5f4", edgecolors="white", linewidths=0.4)
        nx.draw_networkx_nodes(H, pos, nodelist=[u, v], ax=ax, node_size=200,
                               node_color=SERIES[0], edgecolors="white", linewidths=1.2)
        nx.draw_networkx_labels(H, pos, labels={u: str(u), v: str(v)}, ax=ax, font_size=9,
                                verticalalignment="bottom",
                                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                                          alpha=0.85))
        ax.set_title(f"{r.method} #{r.rank}: {u} - {v}\nscore = {r.score:.3f} | "
                     f"{r.common_neighbours} shared co-authors | degrees {r.degree_u} & {r.degree_v}",
                     fontsize=10)
        ax.axis("off")
    for ax in np.ravel(axes)[len(recs):]:
        ax.axis("off")
    fig.legend(handles=[
        plt.Line2D([], [], color=PREDICTED_RED, linewidth=2.2, linestyle="--",
                   label="Predicted link"),
        plt.Line2D([], [], marker="o", linestyle="", color=SERIES[0], markersize=10,
                   label="Recommended pair"),
        plt.Line2D([], [], marker="o", linestyle="", color="#9ec5f4", markersize=7,
                   label="Shared co-author"),
        plt.Line2D([], [], marker="o", linestyle="", color=OTHER_GREY, markersize=6,
                   label="Other co-author of u or v")], loc="lower center", ncol=4)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def interactive_recommendations(H: nx.Graph, path: Path, title: str) -> Path:
    """pyvis HTML of the recommendation subgraph (JS inlined so it works offline)."""
    from pyvis.network import Network
    endpoints = {n for u, v, d in H.edges(data=True) if d["kind"] == "predicted" for n in (u, v)}
    net = Network(height="760px", width="100%", bgcolor="#ffffff", font_color=TEXT,
                  cdn_resources="in_line", heading=title)
    deg = dict(H.degree())
    for n in H.nodes():
        is_rec = n in endpoints
        net.add_node(int(n), label=str(n), size=18 if is_rec else 8,
                     color=SERIES[0] if is_rec else "#9ec5f4",
                     title=(f"Author {n}<br>degree in this subgraph: {deg[n]}"
                            + ("<br><b>recommended author</b>" if is_rec else "")))
    for u, v, d in H.edges(data=True):
        if d["kind"] == "predicted":
            net.add_edge(int(u), int(v), color=PREDICTED_RED, width=3, dashes=True,
                         title=f"PREDICTED link #{d['rank']}<br>score = {d['score']:.3f}")
        else:
            net.add_edge(int(u), int(v), color=EDGE_GREY, width=0.8, title="existing co-authorship")
    net.barnes_hut(gravity=-9000, spring_length=120)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(net.generate_html(notebook=False), encoding="utf-8")
    return path


# --- Cytoscape export --------------------------------------------------------
def export_cytoscape(L: nx.Graph, node_table: pd.DataFrame, predicted: pd.DataFrame,
                     out_dir: Path = CYTO_DIR) -> dict:
    """GraphML + plain CSV tables that Cytoscape Desktop imports directly.

    node_table columns: node, degree, community, pagerank, betweenness
    predicted columns:  author_u, author_v, score, method, rank
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    attrs = node_table.set_index("node")
    rec_nodes = set(predicted.author_u) | set(predicted.author_v)

    G = nx.Graph()
    for n in L.nodes():
        a = attrs.loc[n]
        G.add_node(int(n), label=str(n), degree=int(a.degree), community=int(a.community),
                   pagerank=float(a.pagerank), betweenness=float(a.betweenness),
                   recommended=bool(n in rec_nodes))
    G.add_edges_from(((int(u), int(v)) for u, v in L.edges()), interaction="coauthor",
                     predicted=False, score=0.0)
    paths = {"graphml": out_dir / "ca-GrQc_lcc.graphml"}
    nx.write_graphml(G, paths["graphml"])

    Gp = G.copy()
    for r in predicted.itertuples():
        Gp.add_edge(int(r.author_u), int(r.author_v), interaction="predicted",
                    predicted=True, score=float(r.score))
    paths["graphml_pred"] = out_dir / "ca-GrQc_lcc_with_predictions.graphml"
    nx.write_graphml(Gp, paths["graphml_pred"])

    paths["nodes"] = out_dir / "cytoscape_nodes.csv"
    nodes_out = node_table[node_table.node.isin(set(L.nodes()))].copy()
    nodes_out["recommended"] = nodes_out.node.isin(rec_nodes)
    nodes_out.to_csv(paths["nodes"], index=False)

    paths["edges"] = out_dir / "cytoscape_edges.csv"
    edges = pd.DataFrame(sorted((min(u, v), max(u, v)) for u, v in L.edges()),
                         columns=["source", "target"])
    edges["interaction"] = "coauthor"
    edges.to_csv(paths["edges"], index=False)

    paths["predicted"] = out_dir / "predicted_links.csv"
    pd.DataFrame({"source": predicted.author_u, "target": predicted.author_v,
                  "interaction": "predicted", "score": predicted.score,
                  "method": predicted.method, "rank": predicted["rank"]}
                 ).to_csv(paths["predicted"], index=False)
    return paths


# --- formula images for the report and slides --------------------------------
FORMULAS = {
    "cn": r"$CN(u,v)=|\Gamma(u)\cap\Gamma(v)|$",
    "jaccard": r"$JC(u,v)=\dfrac{|\Gamma(u)\cap\Gamma(v)|}{|\Gamma(u)\cup\Gamma(v)|}$",
    "adamic_adar": r"$AA(u,v)=\sum_{w\,\in\,\Gamma(u)\cap\Gamma(v)}\dfrac{1}{\log\,k(w)}$",
    "pref_attach": r"$PA(u,v)=k(u)\cdot k(v)$",
}


def render_formulas(out_dir: Path, fontsize: int = 20) -> dict:
    """Render each heuristic formula with matplotlib mathtext to a PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for m, tex in FORMULAS.items():
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, tex, fontsize=fontsize, color=TEXT)
        p = out_dir / f"formula_{m}.png"
        fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.04, transparent=True)
        plt.close(fig)
        paths[m] = p
    return paths
