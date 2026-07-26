"""Stress test: malformed / ambiguous records.

The generator plants deliberately broken records per control (missing
termination timestamps, contradictory approvals, blank roles). A responsible
agent should *escalate* these to human review rather than guess a pass/fail.

This harness runs the agent, isolates the ground-truth ambiguous records, and
reports the escalation rate on that stress set. High escalation is the desired
behaviour.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.graph import DEFAULT_THRESHOLD, run_graph
from ingest.load import load_ground_truth

CONTROLS = ["AC-1", "AC-2", "AC-3"]


def run_stress(
    data_dir: str = "data",
    controls_dir: str = "controls",
    threshold: float = DEFAULT_THRESHOLD,
    provider: str | None = None,
) -> dict[str, Any]:
    gt = load_ground_truth(data_dir)
    if not gt:
        raise FileNotFoundError(
            f"No ground_truth.json in {data_dir}/. Run: python -m ingest.generate"
        )
    state = run_graph(
        CONTROLS,
        data_dir=data_dir,
        controls_dir=controls_dir,
        threshold=threshold,
        provider=provider,
    )

    rows = []
    total_amb = total_esc = 0
    for cid in CONTROLS:
        ambiguous = set(gt[cid]["ambiguous"])
        escalated_ids = {f["record_id"] for f in state["escalated"][cid]}
        # An ambiguous record is "handled well" if it was escalated (not
        # auto-concluded) and not silently passed.
        concluded_ids = {f["record_id"] for f in state["exceptions"][cid]}
        escalated_amb = ambiguous & escalated_ids
        concluded_amb = ambiguous & concluded_ids
        rows.append(
            {
                "control": cid,
                "ambiguous": len(ambiguous),
                "escalated": len(escalated_amb),
                "auto_concluded": len(concluded_amb),
                "escalation_rate": (len(escalated_amb) / len(ambiguous))
                if ambiguous
                else 0.0,
            }
        )
        total_amb += len(ambiguous)
        total_esc += len(escalated_amb)

    return {
        "rows": rows,
        "overall_escalation_rate": total_esc / total_amb if total_amb else 0.0,
        "total_ambiguous": total_amb,
        "total_escalated": total_esc,
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Stress Test — Malformed / Ambiguous Records",
        "",
        "The agent should **escalate** ambiguous records to human review, not "
        "guess. Higher escalation rate is better.",
        "",
        "| Control | Ambiguous records | Escalated | Auto-concluded | Escalation rate |",
        "|---------|-------------------|-----------|----------------|-----------------|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {r['control']} | {r['ambiguous']} | {r['escalated']} "
            f"| {r['auto_concluded']} | {r['escalation_rate']:.0%} |"
        )
    lines += [
        "",
        f"**Overall escalation rate:** {report['overall_escalation_rate']:.0%} "
        f"({report['total_escalated']}/{report['total_ambiguous']}).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the stress test.")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--controls-dir", type=str, default="controls")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--out", type=str, default="evals/stress_results.md")
    args = parser.parse_args()

    report = run_stress(
        data_dir=args.data_dir,
        controls_dir=args.controls_dir,
        threshold=args.threshold,
        provider=args.provider,
    )
    md = to_markdown(report)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md)

    print(
        f"Stress escalation rate: {report['overall_escalation_rate']:.0%} "
        f"({report['total_escalated']}/{report['total_ambiguous']})"
    )
    for r in report["rows"]:
        print(
            f"  {r['control']}: {r['escalated']}/{r['ambiguous']} escalated, "
            f"{r['auto_concluded']} auto-concluded"
        )
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
