# Control Automation Agent

An **agentic AI system that autonomously tests IT General Controls (ITGCs)** over
the *full population* of access-management evidence — not a periodic sample — and
produces an **audit-ready workpaper**: pass/fail per item, isolated exceptions,
the evidence trail behind each exception, and a confidence score that routes
borderline cases to a human reviewer.

Built to demonstrate agentic workflow engineering, eval-driven development, and
responsible-AI guardrails applied to a real second-line-of-defence problem.

> ⚠️ **Synthetic data only.** Every dataset in this repo is generated with Faker.
> Nothing here is, resembles, or is derived from any real organisation's access
> logs, HR records, or systems.

---

## 1. The problem this solves

Control owners test IT General Controls by hand, quarterly, on a *sample* of
records. Sampling misses exceptions that fall outside the sampled rows, and the
lag between test cycles means a control can silently fail for weeks.

This agent moves control testing from **periodic and sample-based** to
**continuous and exception-based**. It ingests raw evidence, tests each record
against a control statement, and surfaces only the exceptions — with a full,
explainable trail for each one — so a human reviews *decisions*, not spreadsheets.

---

## 2. Controls tested

Three concrete, recognisable ITGC access controls:

| ID | Control statement | Exception = |
|----|-------------------|-------------|
| **AC-1** | Terminated employees have all system access revoked within the policy window (24h). | Active access after termination + window. |
| **AC-2** | No user holds a segregation-of-duties (SoD) conflict. | User holds two roles from a conflicting pair (e.g. *create vendor* + *approve payment*). |
| **AC-3** | Every privileged-access grant has a matching, approved request. | Privileged grant with no approval record, or approval by an unauthorised approver. |

Scope is deliberately narrow. Three controls tested *properly* — with a real
evaluation harness — beats fifteen half-built ones.

---

## 3. Why this design maps to the role

| Job requirement | Where it lives in this repo |
|-----------------|------------------------------|
| Agentic workflows automating control testing | `agent/` — LangGraph plan → test → verify → escalate |
| Evidence collection & exception handling | `ingest/` structured extraction; exceptions isolated in `report/` |
| Eval-driven development (custom evals, benchmarking, stress testing) | `evals/` — labelled ground truth, precision/recall, stress set |
| Continuous, exception-based monitoring | Full-population run; only exceptions escalate |
| Responsible AI (guardrails, human oversight, explainability) | Confidence gating + human-review queue + per-decision reasoning log |
| AI governance (NIST AI RMF) | `docs/NIST_MAPPING.md` |

---

## 4. Tech stack

- **Orchestration:** LangGraph (plan → test → verify → escalate)
- **Multi-agent roles:** Tester agent + Verifier/Critic agent
- **API:** FastAPI (`/test-controls` endpoint) + a small Streamlit demo UI
- **Evidence extraction:** pandas over structured CSV/JSON evidence exports
- **Synthetic data:** Faker (deterministic seed for reproducibility)
- **Eval harness:** custom — precision, recall, false-positive rate on exception detection
- **LLM:** GPT-4o / Claude Sonnet (configurable via env var)
- **Language:** Python 3.11+

---

## 5. Architecture

```
Evidence exports (CSV/JSON)          Control definitions (YAML)
   access log · HR term list ·            AC-1 · AC-2 · AC-3
   approval tickets · role map                  │
        │                                        │
        └──────────────┬─────────────────────────┘
                       ▼
              FastAPI /test-controls
                       │
                       ▼
   LangGraph:
     plan ──► load_evidence ──► test_control (per record, per control)
                                      │
                                      ▼
                               draft_findings  ── confidence score
                                      │
                                      ▼
                            verifier / critic agent
                          (checks reasoning vs. evidence,
                           drops false positives)
                                      │
                        ┌─────────────┴─────────────┐
                        ▼                           ▼
                confidence ≥ threshold        confidence < threshold
                        │                           │
                        ▼                           ▼
                 auto-conclude              human-review queue
                        │                           │
                        └─────────────┬─────────────┘
                                      ▼
                     Audit workpaper (structured JSON + Markdown)
                     pass/fail · exceptions · evidence trail · reasoning
```

---

## 6. Quick start

```bash
git clone https://github.com/<you>/control-automation-agent.git
cd control-automation-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your LLM API key

# 1. generate synthetic evidence (200 records, known ground truth)
python -m ingest.generate --seed 42 --n 200

# 2. run the agent over the full population
python -m agent.run --controls AC-1,AC-2,AC-3

# 3. see the workpaper
open report/workpaper.md

# 4. run the eval harness (precision / recall / FPR)
python -m evals.run
```

Or run the API + demo UI:

```bash
uvicorn api.main:app --reload      # POST /test-controls
streamlit run demo/app.py          # local demo at localhost:8501
```

---

## 7. Repository structure

```
control-automation-agent/
├── README.md
├── requirements.txt
├── .env.example
├── controls/                 # control definitions (YAML) + SoD conflict pairs
│   ├── AC-1_termination.yaml
│   ├── AC-2_sod.yaml
│   └── AC-3_privileged_access.yaml
├── ingest/
│   ├── generate.py           # Faker synthetic-evidence generator (+ ground truth)
│   └── load.py               # structured evidence loaders
├── agent/
│   ├── graph.py              # LangGraph: plan → test → verify → escalate
│   ├── tester.py             # Tester agent
│   ├── verifier.py           # Verifier / critic agent
│   └── run.py                # CLI entrypoint
├── report/
│   ├── workpaper.py          # renders audit-ready JSON + Markdown
│   └── workpaper.md          # (generated)
├── evals/
│   ├── run.py                # precision / recall / FPR vs. ground truth
│   ├── stress.py             # malformed / ambiguous record injection
│   └── results.md            # (generated) eval report
├── api/
│   └── main.py               # FastAPI /test-controls
├── demo/
│   └── app.py                # Streamlit demo UI
└── docs/
    ├── NIST_MAPPING.md       # design choices → NIST AI RMF functions
    └── architecture.png
```

---

## 8. Results

*This is the most important section of the repo. Fill it in from your own run
of `evals/run.py`.* A reviewer spends ninety seconds here — make them land on
this table.

Exception detection, measured against 200 labelled synthetic employees
(seed 42, deterministic rule engine, confidence threshold 0.7):

| Control | Precision | Recall | False-positive rate | Escalated to human |
|---------|-----------|--------|---------------------|--------------------|
| AC-1 (termination) | 1.00 | 1.00 | 0.00 | 2 |
| AC-2 (SoD) | 1.00 | 1.00 | 0.00 | 2 |
| AC-3 (privileged) | 1.00 | 1.00 | 0.00 | 2 |

Confusion matrix behind the table (ambiguous stress records excluded from the
population — they are scored separately):

| Control | Population | TP | FP | FN | TN |
|---------|-----------|----|----|----|----|
| AC-1 | 23 | 6 | 0 | 0 | 17 |
| AC-2 | 198 | 5 | 0 | 0 | 193 |
| AC-3 | 18 | 6 | 0 | 0 | 12 |

> These are the **rule-only** results: the deterministic engine recovers every
> planted exception with no false positives, and the verifier confirms each one
> against its cited evidence. The point of the harness is that these numbers are
> *measured and reproducible* — swap in an LLM provider or perturb the data and
> the same `evals/run.py` re-scores it. Full output: [`evals/results.md`](evals/results.md).

**Why both precision and recall matter here.** In a controls setting a *false
negative* is a missed control failure (a real exception the agent cleared) and a
*false positive* is wasted auditor time. Reporting only accuracy would hide the
trade-off that actually matters to a second-line function.

**Stress test.** `evals/stress.py` injects malformed and ambiguous records
(missing timestamps, contradictory approvals, blank roles). The agent is
expected to *escalate* these rather than guess. On the bundled data the
escalation rate is **100% (6/6)** — every ambiguous record is routed to human
review and none is auto-concluded.

---

## 9. Responsible AI & governance

- **Human-in-the-loop:** any finding below the confidence threshold is routed to
  a review queue, never auto-concluded.
- **Explainability:** every decision logs the control tested, the records
  compared, the reasoning, and the specific evidence rows cited.
- **Audit trail:** the workpaper is reproducible from the seed + evidence +
  control definitions; re-running is idempotent.
- **NIST AI RMF:** `docs/NIST_MAPPING.md` maps each design choice to the
  **Measure** and **Manage** functions (bias/false-positive measurement,
  human oversight, monitoring).
- **Data:** synthetic only, generated locally, never leaves the machine.

---

## 10. Live demo

A hosted demo runs on synthetic data only:

**🔗 Live demo:** _add your URL here after deploying (see DEPLOY.md)_

Deployment options, easiest first:
- **Streamlit Community Cloud** — free, public URL, deploys straight from the
  GitHub repo. Point it at `demo/app.py`.
- **Hugging Face Spaces** — free, public URL, good for ML demos.
- **Render / Railway** — if you want the FastAPI service itself public.

---

## 11. Roadmap

- Add change-management and IT-operations controls beyond access.
- Export the workpaper in a GRC-platform-ingestible schema (AuditBoard-style).
- Continuous mode: watch an evidence folder and test on every new drop.
- Learn reviewer overrides to tune the confidence threshold over time.

---

## 12. Disclaimer

This is a demonstration project built on **entirely synthetic data**. It is not
a certified audit tool, has not been validated against any real control
environment, and produces no assurance opinion. It exists to demonstrate agentic
AI, evaluation, and responsible-AI engineering applied to a controls problem.
