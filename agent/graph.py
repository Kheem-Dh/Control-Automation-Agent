"""LangGraph control-testing flow.

    plan -> load_evidence -> test_control -> draft_findings -> verifier
         -> (escalate | conclude)

Each node operates on a shared state dict. The routing after the verifier splits
verified findings into two queues by confidence:

  * confidence >= threshold  -> auto-concluded exception
  * confidence <  threshold  -> human-review queue (escalated, never concluded)

If LangGraph is not installed the module falls back to an equivalent sequential
executor, so the pipeline is always runnable (e.g. in a minimal CI image).
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from agent.llm import get_llm
from agent.tester import run_tester
from agent.verifier import run_verifier
from ingest.load import load_controls, load_evidence

DEFAULT_THRESHOLD = 0.7


class ControlState(TypedDict, total=False):
    control_ids: list[str]
    data_dir: str
    controls_dir: str
    threshold: float
    provider: Optional[str]
    plan: list[str]
    controls: dict[str, dict]
    evidence: dict[str, list[dict]]
    test_results: dict[str, list[dict]]
    drafts: dict[str, list[dict]]
    verified: dict[str, list[dict]]
    dropped: dict[str, list[dict]]
    exceptions: dict[str, list[dict]]
    escalated: dict[str, list[dict]]
    passes: dict[str, int]


# --- nodes -----------------------------------------------------------------
def node_plan(state: ControlState) -> ControlState:
    state["plan"] = list(state["control_ids"])
    state.setdefault("threshold", DEFAULT_THRESHOLD)
    return state


def node_load_evidence(state: ControlState) -> ControlState:
    state["controls"] = load_controls(
        state["plan"], state.get("controls_dir", "controls")
    )
    # Evidence may be injected directly (e.g. by the API); only load from disk
    # when it wasn't supplied.
    if not state.get("evidence"):
        state["evidence"] = load_evidence(state.get("data_dir", "data"))
    return state


def node_test_control(state: ControlState) -> ControlState:
    llm = get_llm(state.get("provider"))
    results: dict[str, list[dict]] = {}
    for cid in state["plan"]:
        results[cid] = run_tester(state["controls"][cid], state["evidence"], llm=llm)
    state["test_results"] = results
    return state


def node_draft_findings(state: ControlState) -> ControlState:
    drafts, passes = {}, {}
    for cid, results in state["test_results"].items():
        drafts[cid] = [r for r in results if r["is_exception"]]
        passes[cid] = sum(1 for r in results if not r["is_exception"])
    state["drafts"] = drafts
    state["passes"] = passes
    return state


def node_verifier(state: ControlState) -> ControlState:
    verified, dropped = {}, {}
    for cid, findings in state["drafts"].items():
        kept, drop = run_verifier(state["controls"][cid], findings)
        verified[cid] = kept
        dropped[cid] = drop
    state["verified"] = verified
    state["dropped"] = dropped
    return state


def _needs_escalation(state: ControlState) -> str:
    threshold = state.get("threshold", DEFAULT_THRESHOLD)
    for findings in state["verified"].values():
        if any(f["confidence"] < threshold for f in findings):
            return "escalate"
    return "conclude"


def node_escalate(state: ControlState) -> ControlState:
    """Populate the human-review queue (findings below the threshold)."""
    threshold = state.get("threshold", DEFAULT_THRESHOLD)
    escalated = {}
    for cid, findings in state["verified"].items():
        escalated[cid] = [f for f in findings if f["confidence"] < threshold]
    state["escalated"] = escalated
    return state


def node_conclude(state: ControlState) -> ControlState:
    """Auto-conclude findings at/above the threshold; keep any escalations."""
    threshold = state.get("threshold", DEFAULT_THRESHOLD)
    state.setdefault("escalated", {cid: [] for cid in state["plan"]})
    exceptions = {}
    for cid, findings in state["verified"].items():
        exceptions[cid] = [f for f in findings if f["confidence"] >= threshold]
        state["escalated"].setdefault(cid, [])
    state["exceptions"] = exceptions
    return state


# --- graph construction ----------------------------------------------------
def build_graph():
    """Build the LangGraph ``StateGraph`` (or a sequential fallback)."""
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception:  # pragma: no cover - fallback path
        return _SequentialGraph()

    g = StateGraph(ControlState)
    g.add_node("plan", node_plan)
    g.add_node("load_evidence", node_load_evidence)
    g.add_node("test_control", node_test_control)
    g.add_node("draft_findings", node_draft_findings)
    g.add_node("verifier", node_verifier)
    g.add_node("escalate", node_escalate)
    g.add_node("conclude", node_conclude)

    g.add_edge(START, "plan")
    g.add_edge("plan", "load_evidence")
    g.add_edge("load_evidence", "test_control")
    g.add_edge("test_control", "draft_findings")
    g.add_edge("draft_findings", "verifier")
    g.add_conditional_edges(
        "verifier", _needs_escalation, {"escalate": "escalate", "conclude": "conclude"}
    )
    g.add_edge("escalate", "conclude")
    g.add_edge("conclude", END)
    return g.compile()


class _SequentialGraph:
    """Fallback executor mirroring the LangGraph flow, no dependency needed."""

    def invoke(self, state: ControlState) -> ControlState:
        state = node_plan(state)
        state = node_load_evidence(state)
        state = node_test_control(state)
        state = node_draft_findings(state)
        state = node_verifier(state)
        if _needs_escalation(state) == "escalate":
            state = node_escalate(state)
        state = node_conclude(state)
        return state


def run_graph(
    control_ids: list[str],
    data_dir: str = "data",
    controls_dir: str = "controls",
    threshold: float = DEFAULT_THRESHOLD,
    provider: Optional[str] = None,
    evidence: Optional[dict[str, list[dict]]] = None,
) -> dict[str, Any]:
    """Run the flow end-to-end and return the final state.

    Pass ``evidence`` to test an in-memory population (used by the API);
    otherwise evidence is loaded from ``data_dir``.
    """
    graph = build_graph()
    init: ControlState = {
        "control_ids": control_ids,
        "data_dir": data_dir,
        "controls_dir": controls_dir,
        "threshold": threshold,
        "provider": provider,
    }
    if evidence is not None:
        init["evidence"] = evidence
    return dict(graph.invoke(init))
