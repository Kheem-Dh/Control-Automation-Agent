"""CLI entrypoint: run the agent over the full evidence population.

    python -m agent.run --controls AC-1,AC-2,AC-3
"""
from __future__ import annotations

import argparse

from agent.graph import DEFAULT_THRESHOLD, run_graph
from report.workpaper import build_workpaper, save


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the control-testing agent.")
    parser.add_argument(
        "--controls",
        type=str,
        default="AC-1,AC-2,AC-3",
        help="comma-separated control ids to test",
    )
    parser.add_argument("--data-dir", type=str, default="data")
    parser.add_argument("--controls-dir", type=str, default="controls")
    parser.add_argument("--out", type=str, default="report")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="confidence threshold below which findings are escalated",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="LLM provider: rule (default) | openai | anthropic",
    )
    args = parser.parse_args()

    control_ids = [c.strip() for c in args.controls.split(",") if c.strip()]
    state = run_graph(
        control_ids,
        data_dir=args.data_dir,
        controls_dir=args.controls_dir,
        threshold=args.threshold,
        provider=args.provider,
    )
    wp = build_workpaper(state)
    json_path, md_path = save(wp, args.out)

    s = wp["summary"]
    print(f"Ran controls {control_ids} (engine={wp['run']['provider']})")
    print(
        f"  tested={s['tested']} passed={s['passed']} "
        f"exceptions={s['exceptions']} escalated={s['escalated']} "
        f"fp_dropped={s['false_positives_dropped']}"
    )
    print(f"  workpaper -> {md_path}  &  {json_path}")


if __name__ == "__main__":
    main()
