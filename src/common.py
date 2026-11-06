"""Shared constants, project paths and small I/O helpers.

All paths are resolved relative to the project root (the folder that contains
``src/``), so nothing in the project depends on an absolute path.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SEED = 42  # single global seed used everywhere for reproducibility

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "dataset"
RAW_DIR = DATASET_DIR / "raw"
OUTPUT_DIR = ROOT / "outputs"
VIZ_DIR = ROOT / "visualizations"
CYTO_DIR = VIZ_DIR / "cytoscape"
REPORT_DIR = ROOT / "report"
PRESENTATION_DIR = ROOT / "presentation"
ASSETS_DIR = ROOT / "assets"

RAW_URL = "https://snap.stanford.edu/data/ca-GrQc.txt.gz"
RAW_FILE = RAW_DIR / "ca-GrQc.txt.gz"
RESULTS_JSON = OUTPUT_DIR / "results.json"

# Short keys used in code -> display names used in tables and plots
METHODS = {
    "cn": "Common Neighbours",
    "jaccard": "Jaccard",
    "adamic_adar": "Adamic-Adar",
    "pref_attach": "Preferential Attachment",
}


def ensure_dirs() -> None:
    for d in (DATASET_DIR, RAW_DIR, OUTPUT_DIR, VIZ_DIR, CYTO_DIR,
              REPORT_DIR, PRESENTATION_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _to_builtin(obj):
    """Convert numpy scalars/arrays so they can be written as JSON."""
    if isinstance(obj, dict):
        return {str(k): _to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_builtin(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_builtin(obj), indent=2), encoding="utf-8")


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def update_results(section: str, payload) -> None:
    """Merge one section into outputs/results.json (creating it if needed)."""
    results = load_json(RESULTS_JSON) if RESULTS_JSON.exists() else {}
    results[section] = _to_builtin(payload)
    save_json(results, RESULTS_JSON)


def load_team_info(path: Path | None = None) -> dict:
    """Parse ``team_info.txt`` (key = value lines, '#' comments)."""
    path = path or ROOT / "team_info.txt"
    info = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        info[key.strip()] = value.strip()
    return info
