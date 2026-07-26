"""The generator's ground truth must match the planted exceptions exactly."""
from __future__ import annotations

from ingest.generate import CONFLICT_PAIRS, generate


def test_deterministic_seed():
    a = generate(seed=1, n=100)
    b = generate(seed=1, n=100)
    for name in a["tables"]:
        assert a["tables"][name].equals(b["tables"][name])
    assert a["ground_truth"] == b["ground_truth"]


def test_ac1_ground_truth_matches_evidence(dataset, evidence, ground_truth):
    """Every labelled AC-1 exception really lacks a timely revocation."""
    from agent.tester import _parse_ts
    from datetime import timedelta

    hr = {r["employee_id"]: r for r in evidence["hr_terminations"]}
    access = {}
    for r in evidence["access_log"]:
        access.setdefault(r["employee_id"], []).append(r)

    for emp_id in ground_truth["AC-1"]["exceptions"]:
        term = hr[emp_id]
        term_dt = _parse_ts(term["termination_date"])
        assert term_dt is not None
        grants = [r for r in access[emp_id] if r["action"] == "grant"]
        revokes = [r for r in access[emp_id] if r["action"] == "revoke"]
        # At least one grant has no timely revoke.
        deadline = term_dt + timedelta(hours=24)
        offending = False
        for g in grants:
            matched = [r for r in revokes if r["system"] == g["system"]]
            if not matched:
                offending = True
            else:
                latest = max((_parse_ts(r["timestamp"]) for r in matched
                              if _parse_ts(r["timestamp"])), default=None)
                if latest is None or latest > deadline:
                    offending = True
        assert offending, f"{emp_id} labelled exception but access was timely"


def test_ac2_ground_truth_has_conflict(evidence, ground_truth):
    roles = {}
    for r in evidence["role_assignments"]:
        roles.setdefault(r["employee_id"], set()).add(r["role"])
    for emp_id in ground_truth["AC-2"]["exceptions"]:
        held = roles[emp_id]
        assert any(a in held and b in held for a, b in CONFLICT_PAIRS)


def test_ac3_ground_truth_lacks_valid_approval(evidence, ground_truth):
    grants = {r["event_id"]: r for r in evidence["access_log"]
              if r["access_level"] == "privileged" and r["action"] == "grant"}
    tickets = {}
    for t in evidence["approval_tickets"]:
        tickets.setdefault((t["employee_id"], t["system"]), []).append(t)
    authorised = {"IT_Manager", "Security_Officer"}
    for evt in ground_truth["AC-3"]["exceptions"]:
        g = grants[evt]
        cand = tickets.get((g["employee_id"], g["system"]), [])
        valid = [t for t in cand if t["status"] == "approved"
                 and t["approver_role"] in authorised]
        assert not valid, f"{evt} labelled exception but has a valid approval"


def test_counts_are_planted(ground_truth):
    for cid in ("AC-1", "AC-2", "AC-3"):
        assert len(ground_truth[cid]["exceptions"]) >= 3
        assert len(ground_truth[cid]["ambiguous"]) == 2
