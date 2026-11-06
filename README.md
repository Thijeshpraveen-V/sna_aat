# Link Prediction in a Co-authorship Network

SNA AAT project: recommending future research collaborations in the SNAP ca-GrQc network.

## Run everything
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python build_all.py              # notebook -> report -> slides -> viva notes (~5 min)
.venv\Scripts\python build_all.py --docs-only  # only rebuild report/slides/notes from saved results
```
Team and course details used by the report and the slides are in `team_info.txt`.

## Layout
| Path | Content |
|---|---|
| `notebook/link_prediction_ca_grqc.ipynb` | The whole analysis (Phases 1-6), executed, outputs saved |
| `src/` | `data.py` (load, clean, stats, split, sampling), `scores.py` (CN, Jaccard, AA, PA), `evaluate.py`, `recommend.py`, `viz.py`, `common.py` |
| `dataset/` | Raw and cleaned edge lists, train/test pairs, `nodes.csv`, `README.md`, `dataset.zip` |
| `outputs/` | `results.json` (single source of every reported number), metric tables, `top10_recommendations.csv`, `top20_recommendations.csv` |
| `visualizations/` | PNG + SVG figures, interactive HTML, `cytoscape/` (GraphML, CSVs, `CYTOSCAPE_GUIDE.md`) |
| `report/report.pdf` | Formatted report (built by `report/build_report.py`) |
| `presentation/slides.pptx`, `slides.pdf` | Slide deck on the department template (built by `presentation/build_slides.py`) |
| `VIVA_NOTES.md` | Answers to likely viva questions |
