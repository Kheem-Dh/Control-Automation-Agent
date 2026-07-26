# NIST AI RMF Mapping

This document maps the design choices in this project to the
[NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
(AI RMF 1.0), focusing on the **Measure** and **Manage** functions — the two
most relevant to an operational, second-line control-testing agent. A few
**Govern** and **Map** touchpoints are noted for completeness.

> This is a demonstration project on entirely synthetic data. The mapping shows
> *how* the system is engineered to support responsible-AI outcomes; it is not a
> claim of certification or conformity assessment.

---

## Why these functions

The agent makes consequential-looking decisions (is a control passing or
failing?) over a full population. The two risks that matter most are:

1. **Missing a real control failure** (false negative) — a measurement problem.
2. **Flooding a human with false alarms** (false positive) — a measurement *and*
   an oversight problem.

The Measure function is where we quantify those; the Manage function is where we
put controls (human review, escalation, reproducibility) around them.

---

## MEASURE

*"Appropriate methods and metrics are identified and applied."*

| Sub-category (theme) | Design choice in this repo | Where |
|----------------------|----------------------------|-------|
| **Measure 1.1** — metrics for trustworthiness are selected and justified | Per-control **precision, recall, and false-positive rate** on exception detection — not accuracy alone — because in a controls setting false negatives (missed failures) and false positives (wasted auditor time) carry very different costs. | `evals/run.py`, README §8 |
| **Measure 2.3** — system performance is evaluated against ground truth | A **labelled ground-truth file** (`ground_truth.json`) with a known, planted number of exceptions per control lets us compute those metrics deterministically. | `ingest/generate.py`, `evals/run.py` |
| **Measure 2.5** — the system is evaluated under conditions similar to deployment / for robustness | A dedicated **stress test** injects malformed and ambiguous records (missing timestamps, contradictory approvals, blank roles) and measures the **escalation rate** — the correct behaviour is to escalate, not guess. | `evals/stress.py` |
| **Measure 2.7** — false-positive / false-negative behaviour is characterised | The **verifier/critic agent** independently re-derives each finding from the cited evidence and drops those that don't hold; the count of dropped false positives is reported in the workpaper. | `agent/verifier.py`, `report/workpaper.py` |
| **Measure 2.9** — model explainability is evaluated | Every decision carries a **reasoning string and the exact evidence rows cited**, so a reviewer can check the "why" of each finding, not just the verdict. | `agent/tester.py`, `report/workpaper.py` |
| **Measure 4.2** — measurement is repeatable | Deterministic seed + deterministic rule engine ⇒ **byte-identical** evidence, findings, and metrics across runs. | `ingest/generate.py`, `agent/graph.py` |

---

## MANAGE

*"Risks are prioritised and acted upon based on a projected impact."*

| Sub-category (theme) | Design choice in this repo | Where |
|----------------------|----------------------------|-------|
| **Manage 1.3** — responses to risks are planned (human oversight retained) | Any finding below the configurable **confidence threshold (default 0.7)** is routed to a **human-review queue** and never auto-concluded. The human reviews *decisions*, not spreadsheets. | `agent/graph.py` (`node_escalate` / `node_conclude`) |
| **Manage 2.2** — mechanisms to sustain the value of the system | **Exception-based, full-population** testing replaces periodic sampling, so a control that silently fails is surfaced on the next run rather than the next quarter. | `agent/graph.py`, README §1 |
| **Manage 2.3** — mechanisms to supersede / deactivate an unsafe decision | The verifier can **override the tester** and drop a finding; low-confidence findings are withheld from auto-conclusion entirely. No single agent's output is final. | `agent/verifier.py` |
| **Manage 2.4** — decisions are documented and auditable | The **workpaper** (JSON + Markdown) records, per control, pass/fail counts, each exception, its evidence trail and reasoning, and what was escalated. It is reproducible from seed + evidence + control definitions. | `report/workpaper.py` |
| **Manage 4.1** — post-deployment monitoring | The eval + stress harnesses are re-runnable on every new evidence drop (and in CI), giving continuous monitoring of the agent's own error rates over time. | `evals/`, `.github/workflows/ci.yml` |

---

## GOVERN & MAP (touchpoints)

- **Govern 1.2 / 4.1 (accountability, transparency):** control definitions live
  in human-readable YAML (`controls/*.yaml`), separate from code, so a control
  owner can read and change the rule without touching the agent.
- **Govern 6.1 (data provenance):** all data is **synthetic, generated locally,
  and never leaves the machine**; the repo states this prominently and plants no
  real data.
- **Map 1.1 (context):** the intended use is narrow and explicit — three ITGC
  access controls, second-line testing, advisory output only (no assurance
  opinion). See the disclaimer in README §12.

---

## Residual risks & honest limitations

- The rule engine encodes a *specific* interpretation of each control; a
  different organisation's policy may differ. The YAML is the place to adjust it.
- LLM-generated reasoning (when a provider is configured) is used only to
  *re-express* a decision the deterministic engine already made — it never
  changes the pass/fail verdict — precisely to avoid non-reproducible or
  hallucinated conclusions.
- Ground truth here is *planted*; on real evidence, ground truth is exactly what
  a human reviewer establishes, which is why the human-review queue is the
  system's backstop rather than an afterthought.
