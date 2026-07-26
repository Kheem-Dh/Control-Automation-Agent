"""Streamlit demo UI.

Upload evidence (or use the bundled synthetic dataset), pick controls, run the
agent, and view the workpaper + isolated exceptions in the browser.

    streamlit run demo/app.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running via `streamlit run demo/app.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph import DEFAULT_THRESHOLD, run_graph  # noqa: E402
from ingest.load import EVIDENCE_FILES, load_evidence  # noqa: E402
from report.workpaper import build_workpaper, to_markdown  # noqa: E402

st.set_page_config(page_title="Control Automation Agent", page_icon="🛡️", layout="wide")

st.title("🛡️ Control Automation Agent")
st.caption(
    "Autonomous ITGC control testing over the full population of access "
    "evidence. **Synthetic data only — not a certified audit tool.**"
)

with st.sidebar:
    st.header("Configuration")
    controls = st.multiselect(
        "Controls to test",
        options=["AC-1", "AC-2", "AC-3"],
        default=["AC-1", "AC-2", "AC-3"],
    )
    threshold = st.slider(
        "Confidence threshold (below → human review)",
        min_value=0.0,
        max_value=1.0,
        value=DEFAULT_THRESHOLD,
        step=0.05,
    )
    provider = st.selectbox(
        "LLM engine", options=["rule", "openai", "anthropic"], index=0
    )
    st.markdown("---")
    source = st.radio(
        "Evidence source", options=["Bundled synthetic data", "Upload CSVs"], index=0
    )


def _load_uploaded() -> dict[str, list[dict]] | None:
    st.write("Upload one CSV per evidence type (missing ones are treated as empty):")
    evidence: dict[str, list[dict]] = {name: [] for name in EVIDENCE_FILES}
    got_any = False
    for name in EVIDENCE_FILES:
        up = st.file_uploader(f"{name}.csv", type="csv", key=name)
        if up is not None:
            df = pd.read_csv(io.BytesIO(up.read()), dtype=str, keep_default_na=False)
            evidence[name] = df.to_dict(orient="records")
            got_any = True
    return evidence if got_any else None


evidence = None
if source == "Upload CSVs":
    evidence = _load_uploaded()
else:
    data_dir = Path("data")
    if (data_dir / "access_log.csv").exists():
        evidence = load_evidence(data_dir)
        with st.expander("Preview bundled evidence"):
            for name in EVIDENCE_FILES:
                rows = evidence.get(name, [])
                st.write(f"**{name}** — {len(rows)} rows")
                if rows:
                    st.dataframe(pd.DataFrame(rows).head(10), use_container_width=True)
    else:
        st.warning(
            "No bundled data found. Run `python -m ingest.generate --seed 42 --n 200`."
        )

run = st.button("▶️ Run control testing", type="primary", disabled=not controls)

if run:
    if evidence is None and source == "Upload CSVs":
        st.error("Upload at least one evidence CSV first.")
        st.stop()
    with st.spinner("Running agent: plan → load → test → verify → escalate…"):
        state = run_graph(
            controls,
            threshold=threshold,
            provider=None if provider == "rule" else provider,
            evidence=evidence,
        )
        wp = build_workpaper(state)

    s = wp["summary"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tested", s["tested"])
    c2.metric("Passed", s["passed"])
    c3.metric("Exceptions", s["exceptions"])
    c4.metric("Escalated", s["escalated"])
    c5.metric("FP dropped", s["false_positives_dropped"])

    for cid, c in wp["controls"].items():
        st.subheader(f"{cid} — {c['name']}")
        st.caption(c["statement"])
        if c["exceptions"]:
            st.markdown("**Exceptions (auto-concluded)**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "record": f["record_id"],
                            "rule": f["rule"],
                            "confidence": f["confidence"],
                            "reasoning": f["reasoning"],
                            "evidence": ", ".join(f["evidence_cited"]),
                        }
                        for f in c["exceptions"]
                    ]
                ),
                use_container_width=True,
            )
        else:
            st.write("No exceptions.")
        if c["escalated"]:
            st.markdown("**⚠️ Escalated to human review**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "record": f["record_id"],
                            "rule": f["rule"],
                            "confidence": f["confidence"],
                            "reasoning": f["reasoning"],
                        }
                        for f in c["escalated"]
                    ]
                ),
                use_container_width=True,
            )

    with st.expander("Full Markdown workpaper"):
        st.markdown(to_markdown(wp))
    st.download_button(
        "⬇️ Download workpaper (Markdown)",
        data=to_markdown(wp),
        file_name="workpaper.md",
        mime="text/markdown",
    )
    st.download_button(
        "⬇️ Download workpaper (JSON)",
        data=json.dumps(wp, indent=2),
        file_name="workpaper.json",
        mime="application/json",
    )
