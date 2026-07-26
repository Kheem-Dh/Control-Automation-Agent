"""Eval harness: score agent findings against ground truth.

Reports, per control, precision / recall / false-positive rate on exception
detection, and how many records were escalated to human review. Writes
``evals/results.md`` with a table matching README section 8.

Definitions (per control):
  * population   = all records the agent tested, EXCLUDING the deliberately
                   ambiguous stress records (those belong to ``stress.py``).
  * predicted +  = records auto-concluded as exceptions (>= threshold).
  * actual +     = ground-truth exceptions.
  * TP/FP/FN     = usual confusion-matrix counts on predicted vs actual.
  * precision    = TP / (TP + FP)
  * recall       = TP / (TP + FN)
  * FPR          = FP / (FP + TN),  TN = clean records correctly not flagged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.graph import DEFAULT_THRESHOLD, run_graph
from ingest.load import load_ground_truth

CONTROLS = ["AC-1", "AC-2", "AC-3"]


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def score_control(cid: str, state: dict, gt: dict) -> dict[str, Any]:
    gt_c = gt[cid]
    actual = set(gt_c["exceptions"])
    ambiguous = set(gt_c["ambiguous"])

    tested_ids = {r["record_id"] for r in state["test_results"][cid]}
    # Exclude ambiguous stress records from the precision/recall population.
    population = tested_ids - ambiguous
    predicted = {f["record_id"] for f in state["exceptions"][cid]} - ambiguous
    escalated = {f["record_id"] for f in state["escalated"][cid]}

    tp = len(predicted & actual)
    fp = len(predicted - actual)
    fn = len(actual - predicted)
    tn = len(population) - tp - fp - fn

    return {
        "control": cid,
        "population": len(population),
        "actual_exceptions": len(actual),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": _safe_div(tp, tp + fp),
        "recall": _safe_div(tp, tp + fn),
        "fpr": _safe_div(fp, fp + tn),
        "escalated": len(escalated),
    }


def run_eval(
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
    rows = [score_control(cid, state, gt) for cid in CONTROLS]
    return {"threshold": threshold, "rows": rows}


def to_markdown(report: dict) -> str:
    labels = {
        "AC-1": "AC-1 (termination)",
        "AC-2": "AC-2 (SoD)",
        "AC-3": "AC-3 (privileged)",
    }
    lines = [
        "# Eval Results",
        "",
        "Exception detection measured against labelled synthetic ground truth "
        f"(confidence threshold {report['threshold']}).",
        "",
        "| Control | Precision | Recall | False-positive rate | Escalated to human |",
        "|---------|-----------|--------|---------------------|--------------------|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {labels.get(r['control'], r['control'])} "
            f"| {r['precision']:.2f} "
            f"| {r['recall']:.2f} "
            f"| {r['fpr']:.2f} "
            f"| {r['escalated']} |"
        )
    lines += [
        "",
        "**Confusion matrix (per control).**",
        "",
        "| Control | Population | TP | FP | FN | TN |",
        "|---------|-----------|----|----|----|----|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {r['control']} | {r['population']} | {r['tp']} | {r['fp']} "
            f"| {r['fn']} | {r['tn']} |"
        )
    lines += [
        "",
        "**Why both precision and recall matter.** A false negative is a missed "
        "control failure; a false positive is wasted auditor time. Accuracy alone "
        "would hide that trade-off.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the eval harness.")
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--controls-dir", type=str, default="controls")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--out", type=str, default="evals/results.md")
    args = parser.parse_args()

    report = run_eval(
        data_dir=args.data_dir,
        controls_dir=args.controls_dir,
        threshold=args.threshold,
        provider=args.provider,
    )
    md = to_markdown(report)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md)

    print("Eval results (precision / recall / FPR):")
    for r in report["rows"]:
        print(
            f"  {r['control']}: P={r['precision']:.2f} R={r['recall']:.2f} "
            f"FPR={r['fpr']:.2f} escalated={r['escalated']}"
        )
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
