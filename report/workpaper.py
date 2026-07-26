"""Audit workpaper renderer.

Turns the agent's final state into an audit-ready workpaper in two forms:

  * structured JSON  (``report/workpaper.json``) - machine-ingestible
  * readable Markdown (``report/workpaper.md``)   - what a reviewer reads

Idempotent: the output is a pure function of the agent state, so re-running with
the same evidence + controls + threshold reproduces byte-identical files (no
wall-clock timestamps are embedded).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _evidence_ids(evidence: list[dict]) -> list[str]:
    """Compact list of the id-ish fields from cited evidence rows."""
    ids = []
    for row in evidence:
        for key in ("event_id", "assignment_id", "ticket_id", "employee_id"):
            if key in row and row[key]:
                ids.append(f"{key}={row[key]}")
                break
    return ids


def _finding_view(f: dict) -> dict:
    return {
        "record_id": f["record_id"],
        "rule": f["rule"],
        "confidence": f["confidence"],
        "reasoning": f["reasoning"],
        "verifier": f.get("verifier", {}),
        "evidence_cited": _evidence_ids(f["evidence"]),
        "evidence": f["evidence"],
    }


def build_workpaper(state: dict[str, Any]) -> dict:
    """Assemble the structured workpaper dict from the agent's final state."""
    controls = state.get("controls", {})
    passes = state.get("passes", {})
    verified = state.get("verified", {})
    exceptions = state.get("exceptions", {})
    escalated = state.get("escalated", {})
    dropped = state.get("dropped", {})
    test_results = state.get("test_results", {})

    wp_controls: dict[str, Any] = {}
    totals = {"tested": 0, "passed": 0, "exceptions": 0, "escalated": 0,
              "false_positives_dropped": 0}

    for cid in state.get("plan", list(controls.keys())):
        ctl = controls.get(cid, {})
        tested = len(test_results.get(cid, []))
        exc = exceptions.get(cid, [])
        esc = escalated.get(cid, [])
        drp = dropped.get(cid, [])
        passed = passes.get(cid, 0)

        wp_controls[cid] = {
            "id": cid,
            "name": ctl.get("name", cid),
            "statement": ctl.get("statement", ""),
            "tested": tested,
            "passed": passed,
            "exceptions_count": len(exc),
            "escalated_count": len(esc),
            "false_positives_dropped_count": len(drp),
            "exceptions": [_finding_view(f) for f in exc],
            "escalated": [_finding_view(f) for f in esc],
            "dropped_false_positives": [_finding_view(f) for f in drp],
        }
        totals["tested"] += tested
        totals["passed"] += passed
        totals["exceptions"] += len(exc)
        totals["escalated"] += len(esc)
        totals["false_positives_dropped"] += len(drp)

    return {
        "run": {
            "controls": state.get("plan", list(controls.keys())),
            "threshold": state.get("threshold"),
            "provider": state.get("provider") or "rule",
            "data_dir": state.get("data_dir"),
        },
        "summary": totals,
        "controls": wp_controls,
    }


def to_markdown(wp: dict) -> str:
    """Render the workpaper as readable Markdown."""
    run = wp["run"]
    s = wp["summary"]
    lines: list[str] = []
    lines.append("# Control Testing Workpaper")
    lines.append("")
    lines.append(
        f"**Controls:** {', '.join(run['controls'])}  ·  "
        f"**Confidence threshold:** {run['threshold']}  ·  "
        f"**Engine:** {run['provider']}"
    )
    lines.append("")
    lines.append("> Synthetic data only. Not a certified audit tool.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Records tested | {s['tested']} |")
    lines.append(f"| Passed | {s['passed']} |")
    lines.append(f"| Exceptions (auto-concluded) | {s['exceptions']} |")
    lines.append(f"| Escalated to human review | {s['escalated']} |")
    lines.append(f"| False positives dropped by verifier | {s['false_positives_dropped']} |")
    lines.append("")

    for cid, c in wp["controls"].items():
        lines.append(f"## {cid} — {c['name']}")
        lines.append("")
        lines.append(f"> {c['statement']}")
        lines.append("")
        lines.append(
            f"- Tested: **{c['tested']}**  ·  Passed: **{c['passed']}**  ·  "
            f"Exceptions: **{c['exceptions_count']}**  ·  "
            f"Escalated: **{c['escalated_count']}**  ·  "
            f"FP dropped: **{c['false_positives_dropped_count']}**"
        )
        lines.append("")

        lines.append("### Exceptions")
        lines.append("")
        if c["exceptions"]:
            for f in c["exceptions"]:
                lines.append(
                    f"- **{f['record_id']}** — `{f['rule']}` "
                    f"(confidence {f['confidence']})"
                )
                lines.append(f"  - Reasoning: {f['reasoning']}")
                lines.append(f"  - Evidence: {', '.join(f['evidence_cited'])}")
                v = f.get("verifier", {})
                if v:
                    lines.append(
                        f"  - Verifier: {v.get('verdict')} — {v.get('note')}"
                    )
        else:
            lines.append("_None._")
        lines.append("")

        lines.append("### Escalated to human review")
        lines.append("")
        if c["escalated"]:
            for f in c["escalated"]:
                lines.append(
                    f"- **{f['record_id']}** — `{f['rule']}` "
                    f"(confidence {f['confidence']}) — {f['reasoning']}"
                )
        else:
            lines.append("_None._")
        lines.append("")

        if c["dropped_false_positives"]:
            lines.append("### False positives dropped by verifier")
            lines.append("")
            for f in c["dropped_false_positives"]:
                v = f.get("verifier", {})
                lines.append(
                    f"- **{f['record_id']}** — {v.get('note', 'rejected')}"
                )
            lines.append("")

    return "\n".join(lines) + "\n"


def save(wp: dict, out_dir: str | Path = "report") -> tuple[Path, Path]:
    """Write both JSON and Markdown; return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "workpaper.json"
    md_path = out_dir / "workpaper.md"
    with json_path.open("w") as fh:
        json.dump(wp, fh, indent=2)
    md_path.write_text(to_markdown(wp))
    return json_path, md_path
