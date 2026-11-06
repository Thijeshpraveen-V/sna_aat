"""One-command build of every deliverable.

    python build_all.py              # execute notebook, then report, slides
    python build_all.py --docs-only  # rebuild report + slides from saved results

1. Executes notebook/link_prediction_ca_grqc.ipynb in place (outputs saved in it);
   the notebook writes outputs/results.json, the figures and the dataset package.
2. Builds report/report.pdf from the saved results.
3. Builds presentation/slides.pptx (+ slides.pdf when PowerPoint is available).
4. Writes VIVA_NOTES.md.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTEBOOK = ROOT / "notebook" / "link_prediction_ca_grqc.ipynb"


def run_notebook() -> None:
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    nb = nbformat.read(NOTEBOOK, as_version=4)
    ExecutePreprocessor(timeout=1800, kernel_name="python3").preprocess(
        nb, {"metadata": {"path": str(NOTEBOOK.parent)}})
    nbformat.write(nb, NOTEBOOK)


def run_script(path: Path) -> None:
    subprocess.run([sys.executable, str(path)], check=True, cwd=ROOT)


if __name__ == "__main__":
    t0 = time.time()
    if "--docs-only" not in sys.argv:
        print("Executing notebook ...", flush=True)
        run_notebook()
    print("Building report ...", flush=True)
    run_script(ROOT / "report" / "build_report.py")
    print("Building slides ...", flush=True)
    run_script(ROOT / "presentation" / "build_slides.py")
    print("Writing viva notes ...", flush=True)
    run_script(ROOT / "report" / "build_viva_notes.py")
    print(f"Done in {time.time() - t0:.0f} s")
