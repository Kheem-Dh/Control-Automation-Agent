"""Render docs/architecture.png (the LangGraph control-testing flow).

    python docs/make_architecture.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

INK = "#1f2933"
BLUE = "#2f6f9f"
GREEN = "#3f9142"
AMBER = "#c9820a"
GREY = "#6b7785"


def _box(ax, x, y, w, h, text, fc, ec=INK, tc="white", fs=10):
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.4, edgecolor=ec, facecolor=fc,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            color=tc, fontsize=fs, weight="bold")


def _arrow(ax, x1, y1, x2, y2, color=INK, label=None, lx=None, ly=None):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
        linewidth=1.4, color=color, shrinkA=2, shrinkB=2))
    if label:
        ax.text(lx if lx is not None else (x1 + x2) / 2,
                ly if ly is not None else (y1 + y2) / 2,
                label, ha="center", va="center", fontsize=8,
                color=color, style="italic",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))


def main() -> None:
    fig, ax = plt.subplots(figsize=(9, 8.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11)
    ax.axis("off")

    ax.text(5, 10.6, "Control Automation Agent — LangGraph flow",
            ha="center", fontsize=13, weight="bold", color=INK)

    # Inputs
    _box(ax, 0.4, 9.2, 4.0, 0.9,
         "Evidence exports (CSV/JSON)\naccess log · HR terms · tickets · roles",
         GREY, fs=8.5)
    _box(ax, 5.6, 9.2, 4.0, 0.9,
         "Control definitions (YAML)\nAC-1 · AC-2 · AC-3", GREY, fs=8.5)

    # Pipeline nodes
    _box(ax, 3.6, 8.0, 2.8, 0.8, "plan", BLUE)
    _box(ax, 3.6, 6.9, 2.8, 0.8, "load_evidence", BLUE)
    _box(ax, 3.2, 5.8, 3.6, 0.8, "test_control  (per record)", BLUE)
    _box(ax, 3.2, 4.7, 3.6, 0.8, "draft_findings  (+ confidence)", BLUE)
    _box(ax, 2.9, 3.6, 4.2, 0.8, "verifier / critic  (drop false positives)", GREEN)

    # Branch
    _box(ax, 0.6, 2.1, 3.4, 0.8, "conclude\n(confidence ≥ threshold)", GREEN, fs=8.5)
    _box(ax, 6.0, 2.1, 3.4, 0.8, "escalate\n(confidence < threshold)", AMBER, fs=8.5)

    # Output
    _box(ax, 2.4, 0.5, 5.2, 0.9,
         "Audit workpaper (JSON + Markdown)\npass/fail · exceptions · evidence · reasoning",
         INK, fs=8.5)

    # Arrows
    _arrow(ax, 2.4, 9.2, 4.6, 8.8)
    _arrow(ax, 7.6, 9.2, 5.4, 8.8)
    _arrow(ax, 5.0, 8.0, 5.0, 7.7)
    _arrow(ax, 5.0, 6.9, 5.0, 6.6)
    _arrow(ax, 5.0, 5.8, 5.0, 5.5)
    _arrow(ax, 5.0, 4.7, 5.0, 4.4)
    _arrow(ax, 4.3, 3.6, 2.3, 2.9, color=GREEN, label="≥ τ", lx=3.0, ly=3.35)
    _arrow(ax, 5.7, 3.6, 7.7, 2.9, color=AMBER, label="< τ", lx=7.0, ly=3.35)
    _arrow(ax, 2.3, 2.1, 4.2, 1.4, color=GREEN)
    _arrow(ax, 7.7, 2.1, 5.8, 1.4, color=AMBER, label="human review", lx=7.4, ly=1.75)

    out = Path(__file__).resolve().parent / "architecture.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
