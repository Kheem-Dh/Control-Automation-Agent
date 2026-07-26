"""Structured evidence loaders.

Reads the CSV evidence exports and the control YAML definitions into plain
Python structures the agent can reason over. All CSV fields are read as strings
so the tester can detect malformed/blank values itself (rather than pandas
silently coercing them).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

EVIDENCE_FILES = {
    "access_log": "access_log.csv",
    "hr_terminations": "hr_terminations.csv",
    "approval_tickets": "approval_tickets.csv",
    "role_assignments": "role_assignments.csv",
}

CONTROL_FILES = {
    "AC-1": "AC-1_termination.yaml",
    "AC-2": "AC-2_sod.yaml",
    "AC-3": "AC-3_privileged_access.yaml",
}


def load_evidence(data_dir: str | Path = "data") -> dict[str, list[dict]]:
    """Load every evidence file into a dict of row-lists (records)."""
    data_dir = Path(data_dir)
    evidence: dict[str, list[dict]] = {}
    for name, fname in EVIDENCE_FILES.items():
        path = data_dir / fname
        if path.exists():
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
            evidence[name] = df.to_dict(orient="records")
        else:
            evidence[name] = []
    return evidence


def load_control(control_id: str, controls_dir: str | Path = "controls") -> dict:
    """Load a single control definition by id (e.g. ``AC-1``)."""
    if control_id not in CONTROL_FILES:
        raise KeyError(f"Unknown control id: {control_id!r}")
    path = Path(controls_dir) / CONTROL_FILES[control_id]
    with path.open() as fh:
        return yaml.safe_load(fh)


def load_controls(
    control_ids: list[str], controls_dir: str | Path = "controls"
) -> dict[str, dict]:
    """Load several control definitions keyed by id."""
    return {cid: load_control(cid, controls_dir) for cid in control_ids}


def load_ground_truth(data_dir: str | Path = "data") -> dict:
    """Load ground-truth labels if present (used by the eval harness)."""
    import json

    path = Path(data_dir) / "ground_truth.json"
    if not path.exists():
        return {}
    with path.open() as fh:
        return json.load(fh)
