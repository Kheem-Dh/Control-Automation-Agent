"""FastAPI service exposing the control-testing agent.

    POST /test-controls   -> run the agent, return the workpaper JSON

Evidence may be supplied inline in the request body; if omitted, the bundled
synthetic dataset in ``data/`` is used. Run with:

    uvicorn api.main:app --reload
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent.graph import DEFAULT_THRESHOLD, run_graph
from report.workpaper import build_workpaper

app = FastAPI(
    title="Control Automation Agent",
    description="Autonomous ITGC control testing over full-population evidence "
    "(synthetic data only).",
    version="1.0.0",
)


class TestControlsRequest(BaseModel):
    control_ids: list[str] = Field(
        default_factory=lambda: ["AC-1", "AC-2", "AC-3"],
        description="Control ids to test.",
    )
    threshold: float = Field(
        default=DEFAULT_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Confidence below which findings are escalated to a human.",
    )
    provider: Optional[str] = Field(
        default=None, description="LLM provider: rule | openai | anthropic."
    )
    evidence: Optional[dict[str, list[dict]]] = Field(
        default=None,
        description="Inline evidence tables. If omitted, the bundled dataset "
        "in data/ is used.",
    )
    data_dir: str = Field(default="data")
    controls_dir: str = Field(default="controls")


@app.get("/")
def root() -> dict:
    return {
        "service": "control-automation-agent",
        "endpoints": ["/test-controls (POST)", "/health"],
        "note": "Synthetic data only. Not a certified audit tool.",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/test-controls")
def test_controls(req: TestControlsRequest) -> dict:
    """Run the agent over the evidence and return the audit workpaper JSON."""
    try:
        state = run_graph(
            req.control_ids,
            data_dir=req.data_dir,
            controls_dir=req.controls_dir,
            threshold=req.threshold,
            provider=req.provider,
            evidence=req.evidence,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown control: {exc}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return build_workpaper(state)
