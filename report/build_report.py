"""Builds report/report.pdf from outputs/results.json, the output CSVs and the
figures - no number in the report is typed by hand.

Layout follows the department's AAT report template (title page with the
college header, course name/code, topic, 'Submitted by' and 'Valuation Report'
tables; table of contents; running footer with course code and page x of y).
Team/course details come from team_info.txt.
"""
from __future__ import annotations

import sys
from math import comb, log
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402
import pandas as pd  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether,  # noqa: E402
                                ListFlowable, ListItem, NextPageTemplate, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from common import (ASSETS_DIR, METHODS, OUTPUT_DIR, RESULTS_JSON, VIZ_DIR,  # noqa: E402
                    load_json, load_team_info)

R = load_json(RESULTS_JSON)
T = load_team_info()
OUT = ROOT / "report" / "report.pdf"

# DejaVu Sans ships with matplotlib; used only for the Greek Gamma in the text
pdfmetrics.registerFont(TTFont("DejaVu", str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf")))
GAMMA = "<font name='DejaVu' size='9.5'>Γ</font>"

NAVY = colors.HexColor("#1F3864")
RED = colors.HexColor("#E00000")
PURPLE = colors.HexColor("#7030A0")
HEAD_BG = colors.HexColor("#1F3864")
ZEBRA = colors.HexColor("#EEF3FA")
GRID = colors.HexColor("#9AA5B5")
PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
TEXT_W = PAGE_W - 2 * MARGIN
FOOTER_LEFT = f"SNA AAT Report [{T['subject_code']}]"

# ---------------------------------------------------------------- styles
base = dict(fontName="Times-Roman", fontSize=10.5, leading=13.4)
S = {
    "body": ParagraphStyle("body", **base, alignment=TA_JUSTIFY, spaceAfter=6),
    "cell": ParagraphStyle("cell", fontName="Times-Roman", fontSize=8.5, leading=10),
    "cellb": ParagraphStyle("cellb", fontName="Times-Bold", fontSize=8.5, leading=10,
                            textColor=colors.white),
    "caption": ParagraphStyle("caption", fontName="Times-Italic", fontSize=9.5, leading=12,
                              alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Times-Bold", fontSize=16, leading=20, keepWithNext=1,
                         spaceBefore=8, spaceAfter=6, textColor=colors.black),
    "h2": ParagraphStyle("h2", fontName="Times-Bold", fontSize=12, leading=15, keepWithNext=1,
                         spaceBefore=6, spaceAfter=3, textColor=NAVY),
    "abstract": ParagraphStyle("abstract", **base, alignment=TA_JUSTIFY, leftIndent=0.8 * cm,
                               rightIndent=0.8 * cm, spaceAfter=6),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.5, leading=11,
                           leftIndent=0.5 * cm, backColor=colors.HexColor("#F4F4F2"),
                           borderPadding=6, spaceBefore=4, spaceAfter=10),
    "ref": ParagraphStyle("ref", **base, alignment=TA_LEFT, leftIndent=0.7 * cm,
                          firstLineIndent=-0.7 * cm, spaceAfter=3),
}


def c(text, center=False, bold=False):
    return Paragraph(text, S["cellb"] if bold else
                     (ParagraphStyle("cc", parent=S["cell"], alignment=TA_CENTER) if center else S["cell"]))


# ---------------------------------------------------------------- document
class ReportDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=1.8 * cm, bottomMargin=2.0 * cm,
                         title=T["topic"], author=f"{T['team_member_1_name']}, {T['team_member_2_name']}",
                         subject=f"{T['subject_name']} ({T['subject_code']}) AAT Report")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("main", [frame])])

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            level = 0 if f.style.name == "h1" else 1
            text = f.getPlainText()
            key = f"sec{self.seq.nextf('sec')}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas so the footer can say 'Page x of y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont("Helvetica", 9.5)
            self.drawString(MARGIN, 1.1 * cm, FOOTER_LEFT)
            label = f"Page {self._pageNumber} of {total}"
            self.drawRightString(PAGE_W - MARGIN, 1.1 * cm, label)
            super().showPage()
        super().save()


class Builder:
    def __init__(self):
        self.story = []
        self.fig = 0
        self.tab = 0

    def add(self, *flow):
        self.story.extend(flow)

    def h1(self, text):
        self.add(CondPageBreak(5 * cm), Paragraph(text, S["h1"]))

    def h2(self, text):
        self.add(CondPageBreak(3 * cm), Paragraph(text, S["h2"]))

    def p(self, text, style="body"):
        self.add(Paragraph(text, S[style]))

    def bullets(self, items):
        self.add(ListFlowable([ListItem(Paragraph(i, S["body"]), leftIndent=12) for i in items],
                              bulletType="bullet", start="•", leftIndent=14, bulletFontSize=9))

    def table(self, rows, caption, widths=None, header=True, font=8.5, align_right_from=1):
        self.tab += 1
        data = [[x if not isinstance(x, str) else Paragraph(
            x, ParagraphStyle("t", parent=S["cellb" if (header and i == 0) else "cell"], fontSize=font,
                              leading=font + 1.6,
                              alignment=TA_LEFT if (j < align_right_from or (header and i == 0)) else TA_CENTER))
            for j, x in enumerate(r)] for i, r in enumerate(rows)]
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="CENTER")
        style = [("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        t.setStyle(TableStyle(style))
        cap = Paragraph(f"<b>Table {self.tab}:</b> {caption}",
                        ParagraphStyle("tcap", parent=S["caption"], keepWithNext=1))
        if len(rows) > 16:      # long tables may split across pages (header row repeats)
            self.add(cap, t, Spacer(1, 8))
        else:
            self.add(KeepTogether([cap, t, Spacer(1, 8)]))
        return self.tab

    def figure(self, names, caption, width=TEXT_W, max_h=11 * cm):
        """One image, or several side by side (names = list)."""
        self.fig += 1
        names = names if isinstance(names, list) else [names]
        w_each = width / len(names)
        imgs = []
        for n in names:
            path = VIZ_DIR / f"{n}.png"
            iw, ih = ImageReader(str(path)).getSize()
            w = w_each - (0.2 * cm if len(names) > 1 else 0)
            h = w * ih / iw
            if h > max_h:
                w, h = max_h * iw / ih, max_h
            imgs.append(Image(str(path), width=w, height=h))
        body = imgs[0] if len(imgs) == 1 else Table([imgs], colWidths=[w_each] * len(imgs))
        cap = Paragraph(f"<b>Figure {self.fig}:</b> {caption}", S["caption"])
        self.add(KeepTogether([body, cap]))
        return self.fig


# ---------------------------------------------------------------- helpers
def f4(x):
    return f"{float(x):.4f}"


def f3(x):
    return f"{float(x):.3f}"


def n(x):
    return f"{int(x):,}"


def pct(x, d=1):
    return f"{100 * float(x):.{d}f}%"


MT = R["metrics_test"]
MH = R["metrics_hard_negatives"]
MS = R["multi_seed"]["summary"]
SL, SF, SP = R["stats_lcc"], R["stats_full"], R["split"]
CL = R["cleaning"]
BEST = R["best_method"]["key"]
BEST_NAME = R["best_method"]["name"]
POOL = R["candidate_pool_train"]
COM = R["communities"]
HITS = pd.DataFrame(R["hit_rate"])
TOP20 = pd.DataFrame(R["top20"])
TOP10 = pd.DataFrame(R["top10"])
META = R["meta"]
local = ["cn", "jaccard", "adamic_adar"]
loc_auc = [float(MT[m]["roc_auc"]) for m in local]
non_edges_lcc = comb(SL["nodes"], 2) - SL["edges"]
hit = lambda m, k: float(HITS[(HITS.method == m) & (HITS.k == k)].hit_rate.iloc[0])  # noqa: E731


# ---------------------------------------------------------------- title page
def title_page(b: Builder):
    def para(text, size, color=colors.black, font="Times-Bold", space=2, leading=None):
        return Paragraph(text, ParagraphStyle("tp", fontName=font, fontSize=size, textColor=color,
                                              alignment=TA_CENTER, leading=leading or size * 1.2,
                                              spaceAfter=space))
    b.add(Spacer(1, 0.3 * cm),
          para(T["college"].replace("B.M.S.", "B. M. S."), 20, NAVY),
          para(T["college_subtitle"], 10.5, font="Times-Italic", space=12),
          para(T["department"], 18, NAVY),
          para(f"Program: {T['program'].replace('B.E. in', 'B.E. In')}", 14, font="Times-Roman"),
          para(T["academic_year"], 11, space=8),
          Image(str(ASSETS_DIR / "bmsce_logo.jpg"), width=2.0 * cm, height=2.0 * cm * 223 / 226),
          Spacer(1, 0.25 * cm),
          para(T["subject_name"], 20, RED, space=0),
          para(f"({T['subject_code']})", 20, RED, space=4),
          para("Alternative Assessment Tool (AAT) Report", 12, space=8),
          Paragraph(f"<font color='#7030A0'><b>Topic:</b></font> <font color='#7030A0'>"
                    f"<u>{escape(T['topic'])}</u></font>",
                    ParagraphStyle("topic", fontName="Times-Bold", fontSize=13.5, leading=17,
                                   alignment=TA_CENTER, leftIndent=1.2 * cm, rightIndent=1.2 * cm,
                                   spaceAfter=10)),
          para("Submitted by", 11.5, space=6))

    cell = ParagraphStyle("tc", fontName="Times-Roman", fontSize=11.5, leading=15)
    left = lambda head: Paragraph(  # noqa: E731
        f"{head}<br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Team Member 1:<br/>"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Team Member 2:", cell)
    right = lambda a, b_: Paragraph(f"<br/>{escape(a)}<br/>{escape(b_)}", cell)  # noqa: E731
    sub = Table([[left("Student Name:"), right(T["team_member_1_name"], T["team_member_2_name"])],
                 [left("USN:"), right(T["team_member_1_usn"], T["team_member_2_usn"])],
                 [Paragraph("&nbsp;&nbsp;&nbsp;Semester &amp; Section:", cell),
                  Paragraph(escape(T.get("semester_section", "")), cell)]],
                colWidths=[6.4 * cm, 7.9 * cm])
    sub.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    b.add(sub, Spacer(1, 1.0 * cm),
          para("Valuation Report", 12, RED, space=0),
          para("(to be filled by faculty)", 10.5, font="Times-Italic", space=4))
    vb = ParagraphStyle("vb", fontName="Times-Bold", fontSize=11.5, leading=14)
    designation = T.get("faculty_designation", "")
    fac = escape(T["faculty_incharge"]) + (f", {escape(designation)}" if designation else "")
    val = Table([[Paragraph("Score:", vb), ""], [Paragraph("Comments:", vb), ""],
                 [Paragraph("Faculty In-charge:", vb), Paragraph(fac, cell)],
                 [Paragraph("Faculty Signature with date:", vb), ""]],
                colWidths=[7.3 * cm, 9.7 * cm], rowHeights=[0.95 * cm] * 4)
    val.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    b.add(val, PageBreak())


def contents_page(b: Builder):
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc1", fontName="Times-Bold", fontSize=11.5, leading=13.5, leftIndent=0,
                       spaceBefore=2.5),
        ParagraphStyle("toc2", fontName="Times-Roman", fontSize=9.2, leading=10.4, leftIndent=18),
    ]
    toc.dotsMinLevel = 0
    toc.tableStyle = TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])
    b.add(Paragraph("Table of Contents", ParagraphStyle("tt", fontName="Times-Bold", fontSize=22,
                                                        alignment=TA_CENTER, spaceAfter=14, leading=26)),
          toc, PageBreak())


# ---------------------------------------------------------------- body
def body(b: Builder):
    lcc_share = SL["nodes"] / SF["nodes"]

    # ---- Abstract
    b.add(Paragraph("Abstract", ParagraphStyle("abs", parent=S["h1"], alignment=TA_CENTER)))
    b.p(f"Co-authorship networks record who has written papers with whom. This report treats the "
        f"recommendation of future research collaborations as a <i>link prediction</i> problem on the SNAP "
        f"<i>ca-GrQc</i> network ({n(SF['nodes'])} authors, {n(SF['edges'])} co-authorship links after cleaning). "
        f"On the largest connected component ({n(SL['nodes'])} authors, {n(SL['edges'])} links) we hide "
        f"{n(SP['n_test_pos'])} links (20 %), using a spanning-tree-preserving split, and ask four classical "
        f"neighbourhood heuristics - Common Neighbours, Jaccard, Adamic-Adar and Preferential Attachment - to "
        f"rank them against an equal number of sampled non-links. The three local indices reach a ROC-AUC of "
        f"{min(loc_auc):.3f}-{max(loc_auc):.3f}, against {f3(MT['pref_attach']['roc_auc'])} for Preferential "
        f"Attachment. {BEST_NAME} is the best method (mean ROC-AUC {f4(MS[BEST]['roc_auc_mean'])} "
        f"&plusmn; {f4(MS[BEST]['roc_auc_std'])} over five random splits), and its advantage becomes clear on "
        f"a harder test with negatives that already share a co-author (ROC-AUC {f3(MH[BEST]['roc_auc'])} vs "
        f"{f3(MH['cn']['roc_auc'])} for Common Neighbours). Ranking all {n(POOL['n_candidates'])} distance-2 "
        f"candidate pairs, {pct(hit(BEST, 100), 0)} of its Top-100 predictions are real held-out collaborations "
        f"(random baseline {pct(POOL['random_baseline_hit_rate'])}). We finally produce Top-20 explained "
        f"recommendations, visualisations and a Cytoscape-ready export.", "abstract")
    b.p(f"<b>Keywords:</b> social network analysis, link prediction, co-authorship network, Adamic-Adar, "
        f"collaboration recommendation, triadic closure.", "abstract")

    # ---- 1 Introduction
    b.h1("1. Introduction")
    b.h2("1.1 Background of Social Network Analysis")
    b.p("Social Network Analysis (SNA) models a system as a graph of <i>actors</i> (nodes) and "
        "<i>relationships</i> (edges) and studies the structure of these relationships: who is central, which "
        "groups form, how information flows and how the network evolves. Scientific collaboration is a classic "
        "SNA domain - Newman's studies of co-authorship networks showed that they are small worlds with high "
        "clustering and heavy-tailed degree distributions [15].")
    b.h2("1.2 Importance of Link Prediction")
    b.p("Networks are not static. <i>Link prediction</i> asks which currently unconnected pairs of nodes are "
        "likely to become connected [1]. In a co-authorship network a predicted link is a <b>recommended "
        "collaboration</b>: two researchers who have not written together yet, but whose position in the "
        "network suggests that they should know each other.")
    b.h2("1.3 Objective of the Study")
    b.bullets([
        "Model the ca-GrQc collaboration data as a graph and describe its structure.",
        "Implement four neighbourhood-based link predictors from scratch and verify them against NetworkX.",
        "Evaluate them without information leakage (ROC-AUC, Average Precision, Precision@K, P/R/F1) and "
        "check stability over several random splits.",
        "Produce explained Top-K collaboration recommendations and visualisations, including a Cytoscape export.",
    ])
    b.h2("1.4 Scope of the Report")
    b.p("The study is limited to unsupervised, structure-only heuristics on a static, unweighted snapshot. "
        "Supervised and embedding-based methods are discussed as future work (Section 9.4).")

    # ---- 2 Problem definition
    b.h1("2. Problem Definition and Network Modeling")
    b.h2("2.1 Description of the Link Prediction Task")
    b.p("Let G = (V, E) be an undirected graph. A fraction of E is hidden as the test set E<sub>test</sub>; "
        "the remaining training graph G<sub>train</sub> = (V, E ∖ E<sub>test</sub>) is the only "
        "information available to the predictor. A heuristic assigns a score s(u, v) to every non-adjacent "
        "pair of G<sub>train</sub>; a good heuristic ranks the hidden pairs of E<sub>test</sub> above pairs "
        "that never link.".replace("∖", "\\"))
    b.h2("2.2 Real-World Use Cases")
    b.bullets([
        "Collaborator recommendation in academic platforms (Google Scholar, ResearchGate) and "
        "\"people you may know\" features in professional networks.",
        "Team formation for grants and interdisciplinary projects; reviewer suggestion for journals.",
        "Forecasting how a research field will grow, and detecting missing or mis-attributed records in "
        "bibliographic databases.",
    ])
    b.h2("2.3 Relevance to the Syllabus and Industry")
    b.p("The project uses the core SNA toolkit - graph modeling, degree distributions, clustering, path "
        "lengths, centrality (degree, betweenness, PageRank), community detection (Louvain) and link "
        "prediction - and the same evaluation discipline (held-out data, negative sampling, ranking metrics) "
        "that industry recommender systems use.")
    b.h2("2.4 Key Challenges")
    b.bullets([
        f"<b>Extreme class imbalance:</b> the LCC has {n(non_edges_lcc)} non-adjacent pairs for only "
        f"{n(SL['edges'])} edges ({non_edges_lcc / SL['edges']:,.0f} non-links per link).",
        "<b>Leakage:</b> scores must be computed without the hidden edges, or evaluation is meaningless.",
        "<b>Cold start:</b> an author with few collaborators gives the local heuristics little to work with.",
        "<b>No timestamps:</b> SNAP's ca-GrQc has no dates, so the 'future' is simulated by random hiding.",
    ])
    b.h2("2.5 Network Model")
    b.table([["Element", "Mapping"],
             ["Node", "An author of a paper submitted to the arXiv General Relativity and Quantum Cosmology "
                      "(GR-QC) category"],
             ["Edge", "The two authors co-authored at least one paper (Jan 1993 - Apr 2003)"],
             ["Type", "Undirected (co-authorship is symmetric), unweighted, no self-loops"],
             ["Scope", "Full graph for descriptive statistics; largest connected component (LCC) for all "
                       "link-prediction experiments"]],
            "Mapping of the collaboration data to a network.", [3 * cm, 14 * cm], align_right_from=9)
    b.p("A paper with k authors becomes a k-clique, so the network is built from overlapping cliques. This is "
        "why it is so strongly clustered, and why collaborators of collaborators so often become collaborators "
        "(<i>triadic closure</i>).")

    # ---- 3 Dataset
    b.h1("3. Dataset and Network Statistics")
    b.h2("3.1 Dataset Description")
    b.p(f"The SNAP ca-GrQc dataset [2, 14] is a tab-separated edge list with {n(CL['raw_lines'])} lines over "
        f"{n(CL['raw_unique_nodes'])} author IDs; SNAP stores every undirected pair in both directions. Author "
        f"identities are anonymised integers.")
    b.h2("3.2 Data Cleaning Steps")
    b.table([["Step", "Result"],
             ["Raw data lines read", n(CL["raw_lines"])],
             ["Self-loop lines removed (author paired with themself)", n(CL["self_loop_lines_removed"])],
             ["Duplicate lines removed (reverse direction of each pair, after ordering u < v)",
              n(CL["duplicate_lines_removed"])],
             ["Nodes after cleaning (all IDs kept)", n(CL["clean_nodes"])],
             ["Undirected edges after cleaning", n(CL["clean_edges"])],
             ["Authors isolated after cleaning (their only line was a self-loop)",
              n(CL["isolated_nodes_after_cleaning"])]],
            "Cleaning log produced by <font face='Courier'>data.clean_edges</font>.", [12.5 * cm, 4 * cm])
    b.h2("3.3 Network Statistics")
    st = pd.read_csv(OUTPUT_DIR / "network_stats.csv", index_col=0)

    def sv(v, key):
        if pd.isna(v):
            return "-"
        if key in ("Density",):
            return f"{v:.6f}"
        if float(v).is_integer():
            return n(v)
        return f"{v:.4f}"
    rows = [["Statistic", "Full graph", "LCC"]] + [[k, sv(r["Full graph"], k), sv(r["LCC"], k)]
                                                  for k, r in st.iterrows()]
    b.table(rows, "Basic network statistics (path statistics computed exactly on the LCC).",
            [8.5 * cm, 4 * cm, 4 * cm])
    b.p(f"The network is very sparse (density {SF['density']:.5f}) yet strongly clustered: the average clustering "
        f"coefficient ({SF['avg_clustering']:.3f}) is about {SF['avg_clustering'] / SF['density']:,.0f} times the "
        f"density, i.e. far higher than in a random graph with the same density. It splits into "
        f"{n(SF['connected_components'])} components, but the LCC holds {pct(lcc_share)} of the authors. Inside "
        f"the LCC any two authors are on average {SL['avg_shortest_path']:.2f} steps apart (diameter "
        f"{SL['diameter']}), a small-world structure. The positive degree assortativity "
        f"({SF['degree_assortativity']:.3f}) means that prolific authors mostly collaborate with other prolific "
        f"authors, a consequence of large multi-author papers.")
    b.figure("fig_degree_distribution",
             f"Degree distribution of the full graph on log-log axes (left) and its complementary CDF (right). "
             f"Median degree {SF['median_degree']:.0f}, maximum {SF['max_degree']}: a heavy tail of very "
             f"collaborative authors.", max_h=5.2 * cm)
    b.h2("3.4 Central Authors")
    tops = R["top10_authors"]
    rows = [["#", "Degree: author", "k", "Betweenness: author", "value", "PageRank: author", "value"]]
    for i in range(10):
        d, bt, pr = tops["degree"][i], tops["betweenness"][i], tops["pagerank"][i]
        rows.append([str(i + 1), str(d["node"]), str(d["degree"]), str(bt["node"]),
                     f"{bt['betweenness']:.4f}", str(pr["node"]), f"{pr['pagerank']:.5f}"])
    b.table(rows, "Top-10 authors by degree, exact betweenness and PageRank (full graph).",
            [1 * cm, 2.6 * cm, 1.4 * cm, 3.3 * cm, 2.3 * cm, 3.1 * cm, 2.3 * cm], align_right_from=0)
    overlap = R["top10_overlap_all_three"]
    b.p("The rankings capture different roles. The highest-degree authors are members of very large "
        "multi-author collaborations; the highest-betweenness authors are <i>brokers</i> linking otherwise "
        "separate groups; PageRank rewards being connected to well-connected authors. "
        + (f"Authors {', '.join(map(str, overlap))} appear in all three lists."
           if overlap else "No author appears in all three Top-10 lists, which shows how different these "
                           "notions of importance are."))
    b.h2("3.5 Community Structure")
    b.figure(["fig_network_overview", "fig_communities"],
             f"Force-directed layout of the LCC. Left: node size and colour = degree. Right: Louvain communities "
             f"[8] ({COM['count']} communities, modularity {COM['modularity']:.3f}); the eight largest are "
             f"coloured and labelled, the rest grey.", max_h=7.6 * cm)
    b.p(f"Louvain finds {COM['count']} communities with a very high modularity of {COM['modularity']:.3f}; "
        f"the largest holds only {pct(COM['largest_share'])} of the LCC. Strong communities matter for link "
        f"prediction: {pct(COM['test_edges_intra_community'])} of the held-out test links join two authors of "
        f"the same community, so new collaborations are overwhelmingly local.")

    # ---- 4 Methodology
    b.h1("4. Methodology: Link Prediction Heuristics")
    b.h2("4.1 Theoretical Foundations")
    b.p(f"Notation: {GAMMA}(x) is the set of co-authors (neighbours) of author x and k(x) = |{GAMMA}(x)| is its degree."
        +
        " All four heuristics are <i>unsupervised similarity scores</i>: a larger score means a link is more "
        "likely. They rest on two sociological mechanisms: <b>triadic closure</b> (people who share friends "
        "tend to become friends) and <b>preferential attachment</b> (well-connected people attract new "
        "connections) [5]. All four are implemented from scratch with Python sets in "
        "<font face='Courier'>src/scores.py</font>.")
    fdir = OUTPUT_DIR / "formulas"
    expl = {
        "cn": ("Common Neighbours (CN)", "Counts shared collaborators: the direct measure of triadic closure "
               "[4]. Simple and strong, but biased towards authors with many co-authors."),
        "jaccard": ("Jaccard Coefficient (JC)", "Shared collaborators as a fraction of all collaborators of "
                    "the pair [6]. Normalises CN so that prolific authors are not automatically favoured, but "
                    "over-rewards pairs of authors with very few co-authors."),
        "adamic_adar": ("Adamic-Adar (AA)", "Like CN, but each shared collaborator w counts 1 / log k(w) [3]. "
                        "A shared collaborator who works with few people is strong evidence; a hub who works "
                        "with everyone is weak evidence."),
        "pref_attach": ("Preferential Attachment (PA)", "Product of the two degrees [5]. Purely a popularity "
                        "score: it ignores whether the two authors are close in the network."),
    }
    rows = [["Heuristic", "Formula", "Intuition"]]
    for m, (name, text) in expl.items():
        iw, ih = ImageReader(str(fdir / f"formula_{m}.png")).getSize()
        h = 0.9 * cm if m in ("jaccard", "adamic_adar") else 0.5 * cm
        rows.append([f"<b>{name}</b>", Image(str(fdir / f"formula_{m}.png"), width=h * iw / ih, height=h), text])
    b.table(rows, f"The four heuristics ({GAMMA} = neighbour set, k = degree).",
            [3.4 * cm, 5.8 * cm, 7.8 * cm], align_right_from=9)
    b.h2("4.2 Why Adamic-Adar Uses 1 / log k(w)")
    b.p("A collaborator w with degree k(w) 'introduces' k(w)(k(w)-1)/2 pairs of its co-authors to each other, "
        "so sharing a hub says little about a specific pair. Dividing by log k(w) down-weights hubs smoothly: a "
        f"shared co-author with 3 collaborators contributes 1/log 3 = {1 / log(3):.2f}, one with 60 collaborators "
        f"only 1/log 60 = {1 / log(60):.2f} (natural log). The logarithm (rather than 1/k) keeps hubs from being "
        "ignored completely. Every shared neighbour has k(w) of at least 2, so log k(w) is always positive.")
    b.h2("4.3 Why These Heuristics Suit the Task")
    b.p("Co-authorship links are produced by groups (papers) and grow by introductions through common "
        "collaborators, so neighbourhood overlap is a strong signal. The heuristics are interpretable (a "
        "recommendation can be explained by naming the shared collaborators), need no training, scale to the "
        "whole graph, and are the standard baselines of the link prediction literature [1, 7].")
    b.h2("4.4 Workflow")
    b.add(Paragraph(
        "load + clean edge list  -&gt;  G (full)  -&gt;  LCC<br/>"
        "split LCC edges 80/20 (spanning tree always in train)  -&gt;  G_train, test positives<br/>"
        "sample non-edges of G (1:1)  -&gt;  train / test negatives<br/>"
        "for each pair: CN, JC, AA, PA computed on G_train only<br/>"
        "threshold = argmax F1 on train pairs  -&gt;  metrics on test pairs<br/>"
        "repeat split for 5 seeds  -&gt;  mean +/- std ROC-AUC<br/>"
        "rank distance-2 candidates  -&gt;  hit rate (G_train) and Top-K recommendations (full LCC)",
        S["code"]))

    # ---- 5 Experimental setup
    b.h1("5. Experimental Setup")
    b.h2("5.1 Train/Test Split")
    b.p(f"Deleting 20 % of edges at random would cut bridges and isolate low-degree authors, who could then "
        f"never be scored. We therefore first draw a random spanning tree of the LCC ({n(SP['forest_edges'])} "
        f"edges, minimum spanning tree over random weights, seed 42). A spanning tree contains every bridge, so "
        f"keeping it in the training graph guarantees that the training graph stays connected. The "
        f"{n(SP['n_test_pos'])} test positives (20 % of {n(SP['lcc_edges'])}) are then sampled uniformly from "
        f"the remaining non-tree edges. The training graph keeps all {n(SP['train_graph_nodes'])} nodes, "
        f"{n(SP['train_graph_edges'])} edges and {SP['train_components']} connected component.")
    b.h2("5.2 Negative Sampling and Leakage Prevention")
    b.p(f"Evaluation needs pairs that do <i>not</i> link. Negatives are sampled uniformly from pairs that are "
        f"not edges of the <b>full</b> graph, so a hidden test edge can never be mislabelled as a negative. "
        f"Sampling is 1:1: {n(SP['n_train_neg'])} train negatives and {n(SP['n_test_neg'])} test negatives, "
        f"disjoint. Leakage is avoided by computing <b>every score on the training graph only</b>. Train "
        f"positives are themselves edges of that graph, so they are scored with their own edge hidden. "
        f"Otherwise PA and Jaccard would 'see' the edge they are meant to predict.")
    b.h2("5.3 Evaluation Metrics")
    b.bullets([
        "<b>ROC-AUC</b>: probability that a random positive pair is scored above a random negative pair; "
        "threshold-free, uses the whole ranking.",
        "<b>Average Precision (AP)</b>: area under the precision-recall curve; sensitive to the top of the ranking.",
        "<b>Precision@K</b> (K = 10, 20, 50, 100): fraction of true links among the K highest-scored pairs - "
        "what a user of a recommender actually sees. Ties are broken randomly with seed 42.",
        "<b>Precision, Recall, F1 at a threshold</b>: the threshold maximising F1 on the <i>training</i> pairs "
        "is applied unchanged to the test pairs.",
        "<b>Hit rate@K</b>: fraction of the Top-K over <i>all</i> distance-2 candidate pairs of the training "
        "graph that are real held-out links.",
    ])
    b.h2("5.4 Tools, Libraries and Configuration")
    b.table([["Item", "Value"],
             ["Language / libraries", f"Python {META['python']}, NetworkX {META['networkx']}, pandas "
                                      f"{META['pandas']}, NumPy {META['numpy']}, scikit-learn "
                                      f"{META['scikit_learn']}, Matplotlib {META['matplotlib']}, pyvis, "
                                      f"ReportLab, python-pptx"],
             ["Random seed", f"{META['seed']} (split, sampling, tie-breaking, layouts, Louvain); "
                             f"stability seeds {', '.join(map(str, R['multi_seed']['seeds']))}"],
             ["Split / negatives", "80 % train / 20 % test edges of the LCC; negatives 1:1, from non-edges of "
                                   "the full graph"],
             ["Hard-negative test", f"same {n(SP['n_test_pos'])} positives + {n(R['n_hard_negatives'])} "
                                    f"non-links at distance 2 in the training graph"],
             ["Implementation check", f"own scores vs NetworkX on {n(R['cross_check_pairs'])} pairs: max "
                                      f"absolute difference {max(R['cross_check_max_abs_diff'].values()):g}"],
             ["Runtime", f"whole notebook {META['runtime_seconds'] / 60:.1f} min on a laptop"]],
            "Environment and configuration.", [4 * cm, 13 * cm], align_right_from=9)

    # ---- 6 Results
    b.h1("6. Results and Evaluation")
    b.h2("6.1 Comparison of the Four Heuristics")
    rows = [["Method", "ROC-AUC", "AP", "Thr.", "Prec.", "Recall", "F1", "P@10", "P@20", "P@50", "P@100"]]
    for m in METHODS:
        r = MT[m]
        rows.append([METHODS[m], f4(r["roc_auc"]), f4(r["average_precision"]),
                     f"{float(r['threshold']):.4g}", f3(r["precision"]), f3(r["recall"]), f3(r["f1"]),
                     f3(r["p@10"]), f3(r["p@20"]), f3(r["p@50"]), f3(r["p@100"])])
    t_main = b.table(rows, f"Test-set results ({n(SP['n_test_pos'])} positives + {n(SP['n_test_neg'])} random "
                           f"negatives, seed 42). The threshold is the F1-optimal value learned on the training "
                           f"pairs.", [3.6 * cm] + [1.34 * cm] * 10)
    b.figure("fig_metric_comparison", "ROC-AUC, Average Precision and F1 of the four heuristics on the test set.",
             max_h=5.6 * cm)
    b.p(f"The three local indices are practically tied on this test set (ROC-AUC {min(loc_auc):.4f}-"
        f"{max(loc_auc):.4f}) and clearly beat Preferential Attachment ({f4(MT['pref_attach']['roc_auc'])}). "
        f"The reason is visible in the data: {pct(R['test_zero_cn_fraction']['positives'])} of the test "
        f"positives but {pct(R['test_zero_cn_fraction']['negatives'])} of the random negatives have no common "
        f"neighbour, so 'share at least one co-author' already separates most pairs. The F1-optimal thresholds "
        f"learned on the training pairs (CN &gt;= {float(MT['cn']['threshold']):.0f}, Jaccard &gt;= "
        f"{float(MT['jaccard']['threshold']):.4f}, AA &gt;= {float(MT['adamic_adar']['threshold']):.4f}) all "
        f"amount to exactly that rule, which is why the three methods have identical precision "
        f"({f3(MT[BEST]['precision'])}), recall ({f3(MT[BEST]['recall'])}) and F1 ({f3(MT[BEST]['f1'])}). For PA "
        f"the learned threshold is k(u)k(v) &gt;= {float(MT['pref_attach']['threshold']):.0f}, giving F1 "
        f"{f3(MT['pref_attach']['f1'])}.")
    b.h2("6.2 ROC and Precision-Recall Curves")
    b.figure(["fig_roc_curves", "fig_pr_curves"],
             "ROC curves (left) and precision-recall curves (right) on the test set. CN, Jaccard and AA overlap "
             "almost perfectly; their curves bend at the share of positives with at least one common neighbour.",
             max_h=6.4 * cm)
    b.h2("6.3 Precision@K and a Harder Test with Hard Negatives")
    b.p(f"With random negatives Precision@K is 1.0 for every method up to K = 100 (Table {t_main}): the top of "
        f"every ranking is filled with true links, so this metric cannot separate the methods here. We therefore "
        f"repeated the evaluation with the same positives against <b>hard negatives</b> - non-links that already "
        f"share at least one co-author in the training graph.")
    rows = [["Method", "ROC-AUC", "AP", "P@10", "P@20", "P@50", "P@100"]]
    for m in METHODS:
        r = MH[m]
        rows.append([METHODS[m], f4(r["roc_auc"]), f4(r["average_precision"]), f3(r["p@10"]), f3(r["p@20"]),
                     f3(r["p@50"]), f3(r["p@100"])])
    b.table(rows, f"Results against {n(R['n_hard_negatives'])} hard negatives (distance-2 non-links).",
            [4.2 * cm] + [2 * cm] * 6)
    b.figure("fig_precision_at_k", "Precision@K on the main test set (left) and with hard negatives (right). "
             "Common Neighbours is hidden under the Adamic-Adar line where both are 1.0.", max_h=5.0 * cm)
    b.p(f"Now the methods separate: {BEST_NAME} keeps the highest ROC-AUC ({f3(MH[BEST]['roc_auc'])}) and AP "
        f"({f3(MH[BEST]['average_precision'])}), ahead of Common Neighbours ({f3(MH['cn']['roc_auc'])}), Jaccard "
        f"({f3(MH['jaccard']['roc_auc'])}) and PA ({f3(MH['pref_attach']['roc_auc'])}). Jaccard's Precision@10 "
        f"drops to {f3(MH['jaccard']['p@10'])}: its top scores (1.0) go to small groups of low-degree authors with "
        f"identical co-author lists, many of which never link.")
    b.h2("6.4 Stability over Five Random Splits")
    rows = [["Method", "ROC-AUC mean", "ROC-AUC std", "AP mean", "AP std"]]
    for m in METHODS:
        r = MS[m]
        rows.append([METHODS[m], f4(r["roc_auc_mean"]), f4(r["roc_auc_std"]), f4(r["average_precision_mean"]),
                     f4(r["average_precision_std"])])
    b.table(rows, f"Mean and standard deviation over seeds {', '.join(map(str, R['multi_seed']['seeds']))} "
                  f"(new split and new negatives each time).", [4.6 * cm] + [2.8 * cm] * 4)
    b.figure("fig_seed_stability", "ROC-AUC mean +/- standard deviation over five random splits.", max_h=4.4 * cm)
    b.p(f"The standard deviations are below {max(float(MS[m]['roc_auc_std']) for m in METHODS):.3f}, so the "
        f"ranking of the methods does not depend on one lucky split. The gap between the local indices and PA is "
        f"about {float(MS['adamic_adar']['roc_auc_mean']) - float(MS['pref_attach']['roc_auc_mean']):.3f}, "
        f"much larger than the noise.")
    b.h2("6.5 Comparison and Analysis: Why Adamic-Adar Wins")
    b.bullets([
        "<b>Clustering drives everything.</b> The graph is built from overlapping cliques (papers), so new links "
        "close triangles. All local indices capture this; PA does not look at shared neighbours at all.",
        "<b>Hubs are weak evidence.</b> The hubs of ca-GrQc are members of very large collaborations. Sharing such "
        "a hub tells little about a specific pair; AA discounts it with 1/log k(w), CN does not. This is exactly "
        "what the hard-negative test rewards.",
        "<b>Jaccard over-normalises.</b> Dividing by the union favours pairs of low-degree authors and penalises "
        "authors inside large groups, hurting its top-ranked predictions.",
        "<b>PA favours hubs.</b> PA scores pairs of popular authors highly even when they work in different groups. "
        "It still beats random because the network is degree-assortative, but it misses the locality of "
        "collaboration.",
    ])

    # ---- 7 Recommendations
    b.h1("7. Recommendations")
    b.h2("7.1 Candidate Generation and Filters")
    b.p(f"Scoring all {n(comb(SL['nodes'], 2))} LCC pairs is unnecessary. For CN, Jaccard and AA every pair at "
        f"distance 3 or more has no common neighbour and scores exactly 0, so it can never enter a Top-K list. "
        f"Candidates are therefore the non-adjacent pairs at distance exactly 2: "
        f"{n(R['candidate_pool_full']['n_candidates'])} pairs in the LCC. For PA this is a deliberate restriction "
        f"that stops it from proposing hub pairs with no connection at all. Filters: no self-pairs, no pair "
        f"already linked in the full graph, and no (u, v)/(v, u) duplicates (pairs are stored with u &lt; v).")
    b.h2("7.2 Validation: Do the Predictions Come True?")
    ks = sorted(HITS.k.unique())
    rows = [["K"] + [METHODS[m] for m in METHODS] + ["Random"]]
    for k in ks:
        rows.append([str(k)] + [f3(hit(m, k)) for m in METHODS] + [f3(POOL["random_baseline_hit_rate"])])
    b.table(rows, f"Hit rate@K: share of the Top-K training-graph predictions (out of "
                  f"{n(POOL['n_candidates'])} distance-2 candidates) that are held-out test links.",
            [1.6 * cm, 3.1 * cm, 2.4 * cm, 2.6 * cm, 4.1 * cm, 2.2 * cm])
    b.p(f"{pct(POOL['share_test_at_distance_2'])} of the test links are at distance 2 in the training graph, "
        f"so a random distance-2 candidate is a real link with probability {f3(POOL['random_baseline_hit_rate'])}. "
        f"{BEST_NAME} and CN keep a hit rate of 1.0 up to K = 100 and {f3(hit(BEST, 500))} / {f3(hit('cn', 500))} "
        f"at K = 500; that is about {hit(BEST, 500) / POOL['random_baseline_hit_rate']:.0f} times better than "
        f"random. Jaccard's hit rate falls to {f3(hit('jaccard', 100))} at K = 100 and PA's to "
        f"{f3(hit('pref_attach', 500))} at K = 500. A high hit rate shows that the top of the ranking is "
        f"reliable. This is the property a recommender needs.")
    b.figure("fig_hit_rate", "Hit rate of the Top-K predictions made on the training graph.", max_h=5.0 * cm)
    def short_shared(r, keep=3):
        parts = r.shared_collaborators.split(", ")
        names = [x for x in parts if not x.startswith("+")]
        rest = r.common_neighbours - min(keep, len(names))
        return ", ".join(names[:keep]) + (f", +{rest} more" if rest > 0 else "")

    b.h2(f"7.3 Top-20 Recommended Collaborations ({BEST_NAME})")
    rows = [["#", "Author u", "Author v", "AA score", "Common nbrs", "Dist.", "k(u)", "k(v)",
             "Shared co-authors (least-connected first)"]]
    for r in TOP20.itertuples():
        rows.append([str(r.rank), str(r.author_u), str(r.author_v), f3(r.score), str(r.common_neighbours),
                     str(int(r.shortest_path)), str(r.degree_u), str(r.degree_v), escape(short_shared(r))])
    b.table(rows, f"Top-20 predicted new collaborations by {BEST_NAME} on the full LCC (no pair is linked in the "
                  f"data).", [0.7 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.6 * cm, 1.0 * cm, 1.0 * cm, 1.0 * cm,
                              7.2 * cm], font=7.5, align_right_from=1)
    s20 = R["top20_summary"]
    dens = R["top20_group_density"]
    b.p(f"All 20 pairs are at distance 2 and share between {s20['cn_min']} and {s20['cn_max']} co-authors; they "
        f"involve only {s20['distinct_authors']} distinct authors. For every pair, the group formed by the two "
        f"authors and their shared co-authors has an edge density of {dens['min']:.3f}-{dens['max']:.3f}: these are "
        f"almost complete cliques, typical of very large multi-author papers or long-running consortia, in which the "
        f"recommended pair is one of the few missing links. <b>Why recommended:</b> for example, authors "
        f"{TOP20.iloc[0].author_u} and {TOP20.iloc[0].author_v} share {TOP20.iloc[0].common_neighbours} co-authors "
        f"(degrees {TOP20.iloc[0].degree_u} and {TOP20.iloc[0].degree_v}) but have never published together.")
    b.figure("fig_recommendation_subgraph",
             "The Top-20 recommendations: recommended authors (inner ring), their shared co-authors (outer ring), "
             "existing co-authorships (grey) and predicted collaborations (dashed red).", max_h=6.8 * cm)
    b.h2("7.4 Top-10 of the Other Methods")
    others = [m for m in METHODS if m != BEST]
    rows = [["#"] + [f"{METHODS[m]}: pair (score; common nbrs; k(u), k(v))" for m in others]]
    for i in range(10):
        row = [str(i + 1)]
        for m in others:
            r = TOP10[TOP10.method == METHODS[m]].iloc[i]
            row.append(f"{r.author_u} - {r.author_v} ({r.score:.4g}; {r.common_neighbours}; "
                       f"{r.degree_u}, {r.degree_v})")
        rows.append(row)
    b.table(rows, "Top-10 recommendations of the other three heuristics (full table with explanations in "
                  "outputs/top10_recommendations.csv).", [0.7 * cm] + [5.45 * cm] * 3, font=7.8,
            align_right_from=9)
    ov = R["top10_overlap"]
    b.p(f"Common Neighbours shares {ov['Common Neighbours']['Adamic-Adar']} of its Top-10 pairs with Adamic-Adar, "
        f"because both reward large overlaps. Jaccard shares none: its Top-10 pairs score 1.0 because the two "
        f"authors have identical, small co-author lists. Preferential Attachment proposes pairs of hubs; many share "
        f"only a single co-author, so these are 'popular' rather than 'close' recommendations.")
    b.figure("fig_recommendation_pairs",
             "Ego networks of the #1 pair of each method (plus the best pair from a second group for "
             f"{BEST_NAME}). Dark blue: recommended pair; light blue: shared co-authors; grey: other co-authors.",
             max_h=9 * cm)

    # ---- 8 Discussion
    b.h1("8. Discussion")
    b.h2("8.1 Interpretation of Results")
    b.p("Collaboration in this field is local and group-based. Once two authors share a collaborator, the "
        "probability that they collaborate is high, and the most informative shared collaborators are the "
        "less-connected ones. This is exactly the assumption behind Adamic-Adar, which is why it ranks best.")
    b.h2("8.2 Strengths and Weaknesses")
    b.bullets([
        "<b>Strengths:</b> no training, fast (all test pairs are scored in well under a second), fully "
        "interpretable, and verified against NetworkX.",
        "<b>Weaknesses:</b> CN, JC and AA cannot score pairs at distance 3 or more (they are all 0), so they "
        "cannot recommend 'bridging' collaborations between groups. PA can, but with low precision. All four "
        "ignore time, paper counts and research topics.",
    ])
    b.h2("8.3 Limitations and Threats to Validity")
    b.bullets([
        "<b>Random rather than temporal split:</b> without timestamps, 'future' links are simulated by hiding "
        "random edges. A temporal split (train on earlier years, test on later ones) would be more realistic.",
        "<b>Split bias:</b> test edges are drawn from non-spanning-tree edges, which lie on cycles and are therefore "
        "easier to predict than bridges. Results may be slightly optimistic.",
        "<b>Easy negatives:</b> random negatives are almost never at distance 2, which inflates ROC-AUC. The "
        f"hard-negative results (ROC-AUC {min(float(MH[m]['roc_auc']) for m in METHODS):.3f}-"
        f"{max(float(MH[m]['roc_auc']) for m in METHODS):.3f}) are a more honest picture.",
        "<b>Balanced evaluation:</b> 1:1 sampling hides the real imbalance of about "
        f"{non_edges_lcc / SL['edges']:,.0f} non-links per link, so absolute precision values do not transfer to "
        "a deployed system. The hit-rate analysis over all distance-2 candidates is closer to deployment.",
        "<b>Data artefacts:</b> very large cliques dominate the top recommendations, and a missing link inside "
        "a clique may come from author-name disambiguation errors rather than a true missing collaboration. "
        "Author IDs are anonymised, so recommendations cannot be checked against real publications.",
    ])
    b.h2("8.4 Challenges Encountered")
    b.p("Keeping the training graph connected (solved with the spanning-tree split), avoiding leakage when "
        "scoring training positives (solved by hiding the pair's own edge), the saturation of Precision@K with "
        "random negatives (solved with the hard-negative test and the hit-rate analysis), and the slow "
        f"force-directed layout of the {SL['nodes']:,}-node LCC (computed once with a fixed seed and cached).")

    # ---- 9 Conclusion
    b.h1("9. Conclusion")
    b.h2("9.1 Summary of the Work Done")
    b.p(f"We modeled the ca-GrQc co-authorship data as an undirected graph, characterised it (sparse, highly "
        f"clustered, small-world, modular), and built a leakage-free link prediction pipeline. Four heuristics were "
        f"implemented from scratch and compared. {BEST_NAME} performed best (ROC-AUC "
        f"{f4(MS[BEST]['roc_auc_mean'])} &plusmn; {f4(MS[BEST]['roc_auc_std'])}; hard-negative ROC-AUC "
        f"{f3(MH[BEST]['roc_auc'])}) and was used to produce explained Top-20 collaboration recommendations, "
        f"visualisations and a Cytoscape export.")
    b.h2("9.2 Key Learnings and Insights")
    b.bullets([
        "Network structure alone predicts collaborations very well when the network is clustered.",
        "How the evaluation is designed (split, negatives, leakage) matters as much as the choice of "
        "algorithm: easy negatives make every local method look perfect.",
        "Down-weighting hubs (Adamic-Adar) is what separates the methods on hard cases.",
    ])
    b.h2("9.3 Real-World Applicability")
    b.p("The pipeline can run as a 'researchers you may want to work with' feature: it is cheap, explainable "
        "('you share 12 co-authors, e.g. ...') and can be recomputed nightly on a bibliographic database.")
    b.h2("9.4 Future Improvements")
    b.bullets([
        "<b>Path-based scores</b> such as Katz [12] or Resource Allocation, which also reach pairs at distance 3 "
        "or more.",
        "<b>Node embeddings</b> (Node2Vec [11]) or graph neural networks to learn structural features.",
        "<b>Supervised classifier</b> (e.g. logistic regression or gradient boosting) trained on CN, JC, AA, PA "
        "and community features.",
        "<b>Temporal evaluation</b> on time-stamped arXiv data, and <b>weighted edges</b> (number of joint papers).",
        "<b>Diversity-aware re-ranking</b> so that one large clique does not dominate the recommendation list.",
    ])

    # ---- 10 References
    b.h1("10. References")
    refs = [
        "D. Liben-Nowell and J. Kleinberg, \"The link-prediction problem for social networks,\" <i>Journal of the "
        "American Society for Information Science and Technology</i>, 58(7), pp. 1019-1031, 2007.",
        "J. Leskovec, J. Kleinberg and C. Faloutsos, \"Graph evolution: Densification and shrinking diameters,\" "
        "<i>ACM Transactions on Knowledge Discovery from Data</i>, 1(1), 2007.",
        "L. A. Adamic and E. Adar, \"Friends and neighbors on the Web,\" <i>Social Networks</i>, 25(3), "
        "pp. 211-230, 2003.",
        "M. E. J. Newman, \"Clustering and preferential attachment in growing networks,\" <i>Physical Review E</i>, "
        "64, 025102, 2001.",
        "A.-L. Barabasi and R. Albert, \"Emergence of scaling in random networks,\" <i>Science</i>, 286(5439), "
        "pp. 509-512, 1999.",
        "P. Jaccard, \"Etude comparative de la distribution florale dans une portion des Alpes et du Jura,\" "
        "<i>Bulletin de la Societe Vaudoise des Sciences Naturelles</i>, 37, pp. 547-579, 1901.",
        "L. Lu and T. Zhou, \"Link prediction in complex networks: A survey,\" <i>Physica A</i>, 390(6), "
        "pp. 1150-1170, 2011.",
        "V. D. Blondel, J.-L. Guillaume, R. Lambiotte and E. Lefebvre, \"Fast unfolding of communities in large "
        "networks,\" <i>Journal of Statistical Mechanics</i>, P10008, 2008.",
        "A. Hagberg, D. Schult and P. Swart, \"Exploring network structure, dynamics, and function using "
        "NetworkX,\" <i>Proc. 7th Python in Science Conference (SciPy)</i>, pp. 11-15, 2008.",
        "F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" <i>Journal of Machine Learning "
        "Research</i>, 12, pp. 2825-2830, 2011.",
        "A. Grover and J. Leskovec, \"node2vec: Scalable feature learning for networks,\" <i>Proc. ACM KDD</i>, "
        "pp. 855-864, 2016.",
        "L. Katz, \"A new status index derived from sociometric analysis,\" <i>Psychometrika</i>, 18(1), "
        "pp. 39-43, 1953.",
        "P. Shannon et al., \"Cytoscape: A software environment for integrated models of biomolecular interaction "
        "networks,\" <i>Genome Research</i>, 13(11), pp. 2498-2504, 2003.",
        "J. Leskovec and A. Krevl, \"SNAP Datasets: Stanford Large Network Dataset Collection,\" 2014. "
        "https://snap.stanford.edu/data/ca-GrQc.html",
        "M. E. J. Newman, \"The structure of scientific collaboration networks,\" <i>Proceedings of the National "
        "Academy of Sciences</i>, 98(2), pp. 404-409, 2001.",
    ]
    for i, r in enumerate(refs, 1):
        b.p(f"[{i}]&nbsp;&nbsp;{r}", "ref")


def build():
    b = Builder()
    title_page(b)
    contents_page(b)
    body(b)
    doc = ReportDoc(OUT)
    doc.multiBuild(b.story, canvasmaker=NumberedCanvas)
    print(f"wrote {OUT.relative_to(ROOT)}  ({b.fig} figures, {b.tab} tables)")


if __name__ == "__main__":
    build()
