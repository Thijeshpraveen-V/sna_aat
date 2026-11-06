"""Builds presentation/slides.pptx (and slides.pdf when PowerPoint or
LibreOffice is available) on top of the department's AAT slide template.

Every number on the slides is read from outputs/results.json; team/course
details come from team_info.txt.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
from lxml import etree  # noqa: E402
from pptx import Presentation  # noqa: E402
from pptx.dml.color import RGBColor  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Emu, Pt  # noqa: E402

from common import METHODS, OUTPUT_DIR, RESULTS_JSON, VIZ_DIR, load_json, load_team_info  # noqa: E402

TEMPLATE = ROOT / "LLM AAT_template.pptx"
OUT = ROOT / "presentation" / "slides.pptx"
R = load_json(RESULTS_JSON)
T = load_team_info()

RED = RGBColor(0xC0, 0x00, 0x00)
BLUE = RGBColor(0x00, 0x48, 0x7E)
BLACK = RGBColor(0x0B, 0x0B, 0x0B)
GREY = RGBColor(0x52, 0x51, 0x4E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ZEBRA = RGBColor(0xEE, 0xF3, 0xFA)
PRED_RED = RGBColor(0xE3, 0x49, 0x48)
FONT = "Times New Roman"
SW, SH = 9144000, 5143500          # template slide size (16:9)

MT, MH, MS = R["metrics_test"], R["metrics_hard_negatives"], R["multi_seed"]["summary"]
SF, SL, SP = R["stats_full"], R["stats_lcc"], R["split"]
BEST, BEST_NAME = R["best_method"]["key"], R["best_method"]["name"]
POOL, COM = R["candidate_pool_train"], R["communities"]
HITS = pd.DataFrame(R["hit_rate"])
TOP20 = pd.DataFrame(R["top20"])


def hit(m, k):
    return float(HITS[(HITS.method == m) & (HITS.k == k)].hit_rate.iloc[0])


def f3(x):
    return f"{float(x):.3f}"


def f4(x):
    return f"{float(x):.4f}"


def n(x):
    return f"{int(x):,}"


# ---------------------------------------------------------------- helpers
def set_runs(paragraph, *texts):
    """Replace the text of a template paragraph run by run (keeps formatting)."""
    runs = paragraph.runs
    for r, t in zip(runs, texts):
        r.text = t
    for r in runs[len(texts):]:
        r.text = ""


def remove_paragraph(paragraph):
    paragraph._p.getparent().remove(paragraph._p)


def style_run(run, size, bold=False, color=BLACK, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color


def set_bullet(paragraph, char="•", indent=Emu(228600), level_indent=0):
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(indent + level_indent))
    pPr.set("indent", str(-indent))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    bu = etree.SubElement(pPr, qn("a:buChar"))
    bu.set("char", char)


def add_title(slide, text):
    """Red, centred Times New Roman title at the top - same look as the template's 'Agenda'."""
    tb = slide.shapes.add_textbox(Emu(0), Emu(30000), Emu(SW), Emu(560000))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    style_run(p.add_run(), 30, color=RED)
    p.runs[0].text = text
    return tb


def add_text(slide, items, left, top, width, height, size=15, bullets=True, space=6, color=BLACK):
    """items: list of str or (bold_lead, rest) tuples or ('  sub', text) for level-2."""
    tb = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space)
        sub = isinstance(item, str) and item.startswith("  ")
        if isinstance(item, tuple):
            lead, rest = item
            style_run(p.add_run(), size, bold=True, color=color)
            p.runs[-1].text = lead
            style_run(p.add_run(), size, color=color)
            p.runs[-1].text = rest
        else:
            style_run(p.add_run(), size - (2 if sub else 0), color=GREY if sub else color)
            p.runs[-1].text = item.strip()
        if bullets:
            set_bullet(p, "–" if sub else "•",
                       level_indent=Emu(260000) if sub else 0)
    return tb


def add_picture(slide, path, left, top, max_w, max_h, center=True):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_w / w, max_h / h)
    pw, ph = int(w * scale), int(h * scale)
    x = left + (max_w - pw) // 2 if center else left
    y = top + (max_h - ph) // 2 if center else top
    return slide.shapes.add_picture(str(path), Emu(x), Emu(y), Emu(pw), Emu(ph))


def add_caption(slide, text, left, top, width, size=10):
    tb = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(260000))
    tb.text_frame.word_wrap = True
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    style_run(p.add_run(), size, italic=True, color=GREY)
    p.runs[0].text = text


def add_table(slide, rows, left, top, width, col_w=None, size=11, row_h=260000, bold_first_col=False,
              highlight_row=None):
    nr, nc = len(rows), len(rows[0])
    shape = slide.shapes.add_table(nr, nc, Emu(left), Emu(top), Emu(width), Emu(row_h * nr))
    tbl = shape.table
    if col_w:
        total = sum(col_w)
        for j, w in enumerate(col_w):
            tbl.columns[j].width = Emu(int(width * w / total))
    for i, row in enumerate(rows):
        tbl.rows[i].height = Emu(row_h)
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Emu(50000)
            cell.margin_top = cell.margin_bottom = Emu(15000)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if i == 0:
                cell.fill.fore_color.rgb = BLUE
            elif highlight_row is not None and i == highlight_row:
                cell.fill.fore_color.rgb = RGBColor(0xFF, 0xF2, 0xCC)
            else:
                cell.fill.fore_color.rgb = ZEBRA if i % 2 == 0 else WHITE
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            style_run(p.add_run(), size, bold=(i == 0 or (bold_first_col and j == 0)),
                      color=WHITE if i == 0 else BLACK)
            p.runs[0].text = str(val)
    return shape


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def new_slide(prs, title):
    s = prs.slides.add_slide(prs.slide_layouts[6])   # template's BLANK layout
    add_title(s, title)
    return s


def move_slide_to_end(prs, slide):
    lst = prs.slides._sldIdLst
    for sld in list(lst):
        if prs.slides.part.related_part(sld.get(qn("r:id"))) is slide.part:
            lst.remove(sld)
            lst.append(sld)
            return


# ---------------------------------------------------------------- slides
def title_slide(prs):
    s = prs.slides[0]
    shapes = {sh.name: sh for sh in s.shapes}
    course = shapes["Google Shape;305;p29"].text_frame.paragraphs
    set_runs(course[0], f"Course : {T['subject_name']}")
    set_runs(course[1], f"Course Code: {T['subject_code']}")

    topic = shapes["Google Shape;308;p29"].text_frame.paragraphs
    set_runs(topic[0], T["topic"])
    topic[0].runs[0].font.size = Pt(19)

    by = shapes["Google Shape;307;p29"].text_frame.paragraphs
    set_runs(by[1], f"Student Name & USN : {T['team_member_1_name']} ({T['team_member_1_usn']})")
    set_runs(by[2], f"Student Name & USN : {T['team_member_2_name']} ({T['team_member_2_usn']})")
    set_runs(by[3], "Semester & Section: ", T.get("semester_section", ""))
    box = shapes["Google Shape;307;p29"]
    box.width = Emu(4300000)

    fac = shapes["Google Shape;306;p29"].text_frame.paragraphs
    set_runs(fac[1], T["faculty_incharge"])
    if T.get("faculty_designation"):
        set_runs(fac[2], T["faculty_designation"])
    else:
        remove_paragraph(fac[2])
    notes(s, f"Introduce the team and the topic: predicting future co-authorships in the arXiv GR-QC "
             f"collaboration network and turning the predictions into collaborator recommendations.")


def agenda_slide(prs):
    s = prs.slides[1]
    box = next(sh for sh in s.shapes if sh.name == "Rectangle 2")
    items = ["Problem Definition", "Dataset and Network Modeling", "Methodology: Link Prediction Heuristics",
             "Experimental Setup", "Results and Evaluation", "Top-K Comparison", "Recommendations",
             "Visualization", "Insights, Limitations and Future Work", "Conclusion"]
    for p, t in zip(box.text_frame.paragraphs, items):
        set_runs(p, t)
    box.width = Emu(6000000)
    notes(s, "Roadmap of the talk.")


def problem_slide(prs):
    s = new_slide(prs, "Problem Definition")
    add_text(s, [
        ("Domain: ", "academic collaboration - who writes papers with whom."),
        ("Link prediction: ", "given today's co-authorship network, which unconnected pairs of authors "
                              "are most likely to collaborate in the future?"),
        ("Why it matters: ", "collaborator recommendation (Google Scholar, ResearchGate), team formation, "
                             "reviewer suggestion, forecasting the growth of a field."),
        ("Formal task: ", "hide part of the edges, score every non-adjacent pair s(u, v) using only the "
                          "visible graph, and rank the hidden edges at the top."),
    ], 380000, 720000, 5000000, 4100000, size=16.5, space=10)
    add_table(s, [["Network element", "Mapping"],
                  ["Node", "Author (researcher)"],
                  ["Edge", "Co-authored >= 1 paper"],
                  ["Type", "Undirected, unweighted"],
                  ["Self-loops", "Removed"],
                  ["Experiments on", "Largest connected component"]],
              5600000, 1000000, 3250000, col_w=[1.1, 1.4], size=12, row_h=330000, bold_first_col=True)
    notes(s, "A paper with k authors becomes a k-clique, so the network is highly clustered. Link prediction "
             "turns the question 'who should collaborate?' into a ranking problem.")


def dataset_slide(prs):
    s = new_slide(prs, "Dataset and Network")
    rows = [["Statistic", "Full graph", "LCC"],
            ["Nodes (authors)", n(SF["nodes"]), n(SL["nodes"])],
            ["Edges (co-authorships)", n(SF["edges"]), n(SL["edges"])],
            ["Density", f"{SF['density']:.5f}", f"{SL['density']:.5f}"],
            ["Average degree", f"{SF['avg_degree']:.2f}", f"{SL['avg_degree']:.2f}"],
            ["Avg. clustering coefficient", f3(SF["avg_clustering"]), f3(SL["avg_clustering"])],
            ["Transitivity", f3(SF["transitivity"]), f3(SL["transitivity"])],
            ["Connected components", n(SF["connected_components"]), "1"],
            ["Diameter / avg. path length", "-", f"{SL['diameter']} / {SL['avg_shortest_path']:.2f}"]]
    add_table(s, rows, 250000, 720000, 4300000, col_w=[2.2, 1, 1], size=11.5, row_h=300000)
    add_picture(s, VIZ_DIR / "fig_degree_distribution.png", 4700000, 700000, 4300000, 2300000)
    add_text(s, [
        f"SNAP ca-GrQc (arXiv General Relativity, 1993-2003); {R['cleaning']['self_loop_lines_removed']} "
        f"self-loops and {n(R['cleaning']['duplicate_lines_removed'])} duplicate lines removed.",
        f"Sparse but highly clustered and small-world; heavy-tailed degrees "
        f"(median {SF['median_degree']:.0f}, max {SF['max_degree']}).",
        f"Louvain: {COM['count']} communities, modularity {COM['modularity']:.3f}.",
    ], 4750000, 3100000, 4200000, 1800000, size=12.5, space=4)
    notes(s, f"The LCC keeps {SL['nodes'] / SF['nodes']:.1%} of the authors. High clustering is exactly what "
             f"neighbourhood-based link predictors exploit.")


def method_slide(prs):
    s = new_slide(prs, "Methodology")
    steps = ["Load & clean\nedge list", "Largest\nconnected comp.", "80/20 edge split\n(spanning tree kept)",
             "Negative sampling\n1:1, full-graph\nnon-edges", "Score pairs on\nG_train only\n(CN, JC, AA, PA)",
             "Evaluate &\nrecommend"]
    w, h, gap, top = 1330000, 1000000, 165000, 900000
    left0 = (SW - (len(steps) * w + (len(steps) - 1) * gap)) // 2
    for i, txt in enumerate(steps):
        x = left0 + i * (w + gap)
        box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(x), Emu(top), Emu(w), Emu(h))
        box.fill.solid()
        box.fill.fore_color.rgb = BLUE if i != 4 else RED
        box.line.fill.background()
        tf = box.text_frame
        tf.word_wrap = True
        for k, line in enumerate(txt.split("\n")):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            style_run(p.add_run(), 11.5, bold=True, color=WHITE)
            p.runs[0].text = line
        if i < len(steps) - 1:
            arr = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Emu(x + w + 15000), Emu(top + h // 2 - 70000),
                                     Emu(gap - 30000), Emu(140000))
            arr.fill.solid()
            arr.fill.fore_color.rgb = GREY
            arr.line.fill.background()
    add_text(s, [
        ("Four heuristics written from scratch ", "with Python neighbour sets (src/scores.py) and "
         f"cross-checked against NetworkX on {n(R['cross_check_pairs'])} pairs: max difference "
         f"{max(R['cross_check_max_abs_diff'].values()):g}."),
        ("Leakage-free: ", "test edges are removed before any score is computed; train positives are scored "
                           "with their own edge hidden."),
        ("Evaluation: ", "ROC-AUC, Average Precision, Precision@K, P/R/F1 at a train-chosen threshold, "
                         "5-seed stability, hard negatives, hit rate."),
        ("Recommendation: ", "rank all distance-2 non-adjacent pairs; explain each by its shared co-authors."),
    ], 450000, 2150000, 8250000, 2800000, size=16, space=9)
    notes(s, "The spanning tree contains every bridge, so removing only non-tree edges keeps the training "
             "graph connected and no author is isolated.")


def formula_slide(prs):
    s = new_slide(prs, "Heuristic Formulas")
    fdir = OUTPUT_DIR / "formulas"
    cards = [("cn", "Common Neighbours", "Number of shared co-authors (triadic closure)."),
             ("jaccard", "Jaccard Coefficient", "Shared co-authors as a fraction of all co-authors."),
             ("adamic_adar", "Adamic-Adar", "Shared co-authors weighted by 1/log(degree): rare "
                                            "collaborators count more than hubs."),
             ("pref_attach", "Preferential Attachment", "Product of degrees: 'rich get richer', favours hubs.")]
    cw, ch = 4200000, 2000000
    for i, (m, name, text) in enumerate(cards):
        x = 300000 + (i % 2) * (cw + 240000)
        y = 680000 + (i // 2) * (ch + 120000)
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Emu(x), Emu(y), Emu(cw), Emu(ch))
        card.adjustments[0] = 0.06
        card.fill.solid()
        card.fill.fore_color.rgb = ZEBRA
        card.line.color.rgb = BLUE
        card.line.width = Pt(1)
        head = add_text(s, [name], x + 100000, y + 50000, cw - 200000, 350000, size=16, bullets=False,
                        color=BLUE)
        head.text_frame.paragraphs[0].runs[0].font.bold = True
        add_picture(s, fdir / f"formula_{m}.png", x + 150000, y + 450000, cw - 300000, 850000)
        add_text(s, [text], x + 100000, y + 1350000, cw - 200000, 600000, size=12.5, bullets=False,
                 color=GREY)
    notes(s, "Gamma(x) = set of co-authors of x, k(x) = degree. A shared co-author with 3 collaborators "
             "contributes 1/ln 3 to Adamic-Adar, one with 60 collaborators only 1/ln 60.")


def setup_slide(prs):
    s = new_slide(prs, "Experimental Setup")
    add_text(s, [
        ("Split (seed 42): ", f"{n(SP['n_train_pos'])} train edges / {n(SP['n_test_pos'])} test edges "
                              f"(20 % of {n(SP['lcc_edges'])}); a random spanning tree of "
                              f"{n(SP['forest_edges'])} edges always stays in train - the training graph keeps "
                              f"all {n(SP['train_graph_nodes'])} nodes and stays connected."),
        ("Negative sampling: ", f"pairs that are NOT edges of the full graph, 1:1 - {n(SP['n_train_neg'])} "
                                f"train and {n(SP['n_test_neg'])} test negatives (disjoint)."),
        ("Leakage avoided: ", "every score is computed on the training graph only."),
        ("Threshold: ", "the value that maximises F1 on the TRAINING pairs, then applied unchanged to the "
                        "test pairs."),
        ("Metrics: ", "ROC-AUC, Average Precision, Precision@K (K = 10, 20, 50, 100), Precision/Recall/F1."),
        ("Robustness: ", f"5 random splits (seeds {', '.join(map(str, R['multi_seed']['seeds']))}); hard "
                         f"negatives = {n(R['n_hard_negatives'])} non-links at distance 2."),
    ], 380000, 720000, 8400000, 4300000, size=17, space=12)
    notes(s, "Without negative sampling there would be nothing to rank the positives against; sampling from "
             "non-edges of the FULL graph guarantees that a hidden test edge is never labelled negative.")


def results_slide(prs):
    s = new_slide(prs, "Results")
    rows = [["Method", "ROC-AUC", "AP", "Threshold", "Precision", "Recall", "F1", "P@100"]]
    for m in METHODS:
        r = MT[m]
        rows.append([METHODS[m], f4(r["roc_auc"]), f4(r["average_precision"]), f"{float(r['threshold']):.4g}",
                     f3(r["precision"]), f3(r["recall"]), f3(r["f1"]), f3(r["p@100"])])
    best_row = list(METHODS).index(BEST) + 1
    add_table(s, rows, 300000, 700000, 8550000, col_w=[2.4, 1, 1, 1, 1, 1, 1, 1], size=12.5, row_h=330000,
              highlight_row=best_row)
    loc = [float(MT[m]["roc_auc"]) for m in ("cn", "jaccard", "adamic_adar")]
    add_text(s, [
        f"Local indices (CN, Jaccard, AA) nearly tied: ROC-AUC {min(loc):.4f}-{max(loc):.4f}; "
        f"Preferential Attachment far behind ({f4(MT['pref_attach']['roc_auc'])}).",
        f"{R['test_zero_cn_fraction']['positives']:.1%} of test positives but "
        f"{R['test_zero_cn_fraction']['negatives']:.1%} of random negatives share no co-author - "
        f"'at least one shared co-author' already separates most pairs.",
        f"Best overall: {BEST_NAME} - mean ROC-AUC {f4(MS[BEST]['roc_auc_mean'])} +/- "
        f"{f4(MS[BEST]['roc_auc_std'])} over 5 splits.",
    ], 380000, 2500000, 8400000, 2400000, size=14.5)
    notes(s, "The thresholds of CN, Jaccard and AA all amount to 'at least one common neighbour', which is why "
             "their precision, recall and F1 are identical.")


def roc_slide(prs):
    s = new_slide(prs, "ROC and Precision-Recall Curves")
    add_picture(s, VIZ_DIR / "fig_roc_curves.png", 200000, 650000, 4300000, 3850000)
    add_picture(s, VIZ_DIR / "fig_pr_curves.png", 4640000, 650000, 4300000, 3850000)
    add_caption(s, "CN, Jaccard and Adamic-Adar overlap; Preferential Attachment ranks pairs far less sharply.",
                200000, 4600000, 8740000, size=12)
    notes(s, "ROC-AUC = probability that a random positive is scored above a random negative. AP summarises "
             "precision across all recall levels.")


def topk_slide(prs):
    s = new_slide(prs, "Top-K Comparison")
    add_picture(s, VIZ_DIR / "fig_precision_at_k.png", 150000, 620000, 5000000, 1900000)
    add_picture(s, VIZ_DIR / "fig_hit_rate.png", 5250000, 620000, 3750000, 2150000)
    rows = [["Hard negatives", "ROC-AUC", "AP", "P@10"]]
    for m in METHODS:
        rows.append([METHODS[m], f3(MH[m]["roc_auc"]), f3(MH[m]["average_precision"]), f3(MH[m]["p@10"])])
    add_table(s, rows, 250000, 2850000, 4600000, col_w=[2.3, 1, 1, 1], size=11.5, row_h=290000,
              highlight_row=list(METHODS).index(BEST) + 1)
    add_text(s, [
        "With random negatives P@K = 1.0 for all methods (saturated).",
        f"Hard negatives (share >= 1 co-author) separate them: {BEST_NAME} best.",
        f"Hit rate: {hit(BEST, 100):.0%} of {BEST_NAME}'s Top-100 (over {n(POOL['n_candidates'])} candidates) "
        f"are real held-out links vs {POOL['random_baseline_hit_rate']:.1%} at random.",
    ], 5050000, 2900000, 3950000, 2100000, size=12.5, space=5)
    notes(s, "Precision@K measures what a user of the recommender actually sees: the top of the list.")


def recs_slide(prs):
    s = new_slide(prs, f"Recommendations ({BEST_NAME})")
    rows = [["#", "Author u", "Author v", "AA score", "Shared co-authors", "k(u)", "k(v)"]]
    for r in TOP20.head(10).itertuples():
        rows.append([r.rank, r.author_u, r.author_v, f3(r.score), r.common_neighbours, r.degree_u, r.degree_v])
    add_table(s, rows, 200000, 650000, 4900000, col_w=[0.5, 1, 1, 1.1, 1.5, 0.7, 0.7], size=11,
              row_h=300000)
    s20, dens = R["top20_summary"], R["top20_group_density"]
    add_text(s, [
        f"Candidates: {n(R['candidate_pool_full']['n_candidates'])} non-adjacent pairs at distance 2 "
        f"(every pair further away scores 0 for CN/JC/AA).",
        "Filtered: no self-pairs, no existing links, no (v, u) duplicates.",
        f"Top-20 pairs share {s20['cn_min']}-{s20['cn_max']} co-authors; their groups have edge density "
        f"{dens['min']:.3f}-{dens['max']:.3f} - missing links inside near-cliques (large multi-author papers).",
        f"Why #1? Authors {TOP20.iloc[0].author_u} and {TOP20.iloc[0].author_v} share "
        f"{TOP20.iloc[0].common_neighbours} co-authors but have never published together.",
    ], 5250000, 650000, 3750000, 4300000, size=13, space=6)
    notes(s, "Full Top-20 with shared collaborators is in outputs/top20_recommendations.csv; Top-10 of every "
             "method in outputs/top10_recommendations.csv.")


def viz_slide(prs):
    s = new_slide(prs, "Visualization")
    add_picture(s, VIZ_DIR / "fig_communities.png", 150000, 620000, 3300000, 3900000)
    add_picture(s, VIZ_DIR / "fig_recommendation_pairs.png", 3550000, 620000, 5450000, 3900000)
    add_caption(s, f"Left: Louvain communities of the LCC. Right: ego networks of each method's #1 pair - "
                   f"dashed red = predicted link, light blue = shared co-authors.", 150000, 4600000, 8850000,
                size=11.5)
    notes(s, "Interactive version: visualizations/recommendation_subgraph_interactive.html. Cytoscape files: "
             "visualizations/cytoscape (GraphML + CSV).")


def insights_slide(prs):
    s = new_slide(prs, "Insights")
    add_text(s, [
        ("Clustering drives prediction: ", f"{COM['test_edges_intra_community']:.0%} of held-out links fall "
                                           f"inside one Louvain community - new collaborations are local."),
        ("Adamic-Adar wins ", f"because it discounts shared hubs (hard-negative ROC-AUC {f3(MH[BEST]['roc_auc'])} "
                              f"vs {f3(MH['cn']['roc_auc'])} for CN)."),
        ("Jaccard over-normalises: ", "its top scores go to tiny groups with identical co-author lists "
                                      f"(hard-negative P@10 = {f3(MH['jaccard']['p@10'])})."),
        ("PA favours hubs: ", "it recommends popular authors from different groups, not close ones "
                              f"(ROC-AUC {f3(MT['pref_attach']['roc_auc'])})."),
        ("Stable: ", f"ROC-AUC std over 5 splits <= {max(float(MS[m]['roc_auc_std']) for m in METHODS):.4f} "
                     f"for every method."),
    ], 380000, 760000, 8400000, 4300000, size=18.5, space=14)
    notes(s, "The evaluation design (split, negatives, leakage) matters as much as the algorithm: with easy "
             "negatives every local method looks perfect.")


def limits_slide(prs):
    s = new_slide(prs, "Limitations and Future Work")
    left = add_text(s, ["Limitations",
                 "  Random, not temporal split (no timestamps in SNAP data)",
                 "  Spanning-tree split favours easier (cycle) test edges",
                 "  Random negatives are easy; 1:1 hides the real imbalance",
                 "  Local indices cannot reach pairs at distance >= 3",
                 "  Large cliques dominate the Top-K; IDs are anonymised"],
             300000, 760000, 4200000, 4100000, size=19, space=11)
    right = add_text(s, ["Future work",
                 "  Katz index / Resource Allocation (longer paths)",
                 "  Node2Vec embeddings or graph neural networks",
                 "  Supervised classifier on CN, JC, AA, PA + community features",
                 "  Temporal evaluation; weighted edges (number of papers)",
                 "  Diversity-aware re-ranking of recommendations"],
             4700000, 760000, 4200000, 4100000, size=19, space=11)
    for tb in (left, right):
        p0 = tb.text_frame.paragraphs[0]
        for el in p0._p.get_or_add_pPr().findall(qn("a:buChar")):
            p0._p.get_or_add_pPr().remove(el)
        p0._p.get_or_add_pPr().set("marL", "0")
        p0._p.get_or_add_pPr().set("indent", "0")
        p0.runs[0].font.bold = True
        p0.runs[0].font.color.rgb = BLUE
    notes(s, "A supervised model can learn how to combine the four scores instead of choosing one.")


def conclusion_slide(prs):
    s = new_slide(prs, "Conclusion")
    add_text(s, [
        f"Modeled ca-GrQc as an author graph ({n(SL['nodes'])} authors, {n(SL['edges'])} links in the LCC): "
        f"sparse, highly clustered, small-world, modular.",
        "Built a leakage-free link prediction pipeline with a connectivity-preserving split.",
        f"{BEST_NAME} is the best predictor: ROC-AUC {f4(MS[BEST]['roc_auc_mean'])} +/- "
        f"{f4(MS[BEST]['roc_auc_std'])}, hard-negative ROC-AUC {f3(MH[BEST]['roc_auc'])}, "
        f"{hit(BEST, 100):.0%} hit rate in its Top-100.",
        "Delivered explained Top-20 recommendations, visualizations, a Cytoscape export, a dataset "
        "package and a reproducible notebook.",
    ], 380000, 800000, 8400000, 4100000, size=19.5, space=18)
    notes(s, "Network structure alone predicts collaborations well when the network is clustered.")


def thanks_slide(prs):
    s = prs.slides[2]
    tb = next(sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip())
    p = tb.text_frame.add_paragraph()
    p.alignment = PP_ALIGN.CENTER
    style_run(p.add_run(), 28, color=RED)
    p.runs[0].text = "Questions?"
    move_slide_to_end(prs, s)
    notes(s, "Q&A - see VIVA_NOTES.md for prepared answers.")


def export_pdf(pptx: Path) -> Path | None:
    """Export to PDF with PowerPoint (Windows) or LibreOffice, if available."""
    pdf = pptx.with_suffix(".pdf")
    if sys.platform == "win32":
        ps = (f"$a = New-Object -ComObject PowerPoint.Application; "
              f"$p = $a.Presentations.Open('{pptx}', $true, $false, $false); "
              f"$p.SaveAs('{pdf}', 32); $p.Close(); $a.Quit()")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode == 0 and pdf.exists():
            return pdf
    office = shutil.which("soffice") or shutil.which("libreoffice")
    if office:
        subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)],
                       capture_output=True)
        if pdf.exists():
            return pdf
    return None


def build():
    prs = Presentation(str(TEMPLATE))
    title_slide(prs)
    agenda_slide(prs)
    for make in (problem_slide, dataset_slide, method_slide, formula_slide, setup_slide, results_slide,
                 roc_slide, topk_slide, recs_slide, viz_slide, insights_slide, limits_slide, conclusion_slide):
        make(prs)
    thanks_slide(prs)
    prs.save(str(OUT))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(prs.slides)} slides)")
    pdf = export_pdf(OUT)
    print(f"wrote {pdf.relative_to(ROOT)}" if pdf else "PDF export skipped (no PowerPoint/LibreOffice found)")


if __name__ == "__main__":
    build()
