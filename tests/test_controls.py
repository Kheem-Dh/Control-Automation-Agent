"""Each control's logic: a known exception is caught, a clean record is not."""
from __future__ import annotations

from agent.tester import check_ac1, check_ac2, check_ac3
from agent.verifier import run_verifier
from ingest.load import load_control


def _by_id(results):
    return {r["record_id"]: r for r in results}


# --- AC-1 -----------------------------------------------------------------
def test_ac1_catches_never_revoked():
    ctl = load_control("AC-1")
    evidence = {
        "hr_terminations": [
            {"employee_id": "E1", "employee_name": "A", "department": "IT",
             "termination_date": "2026-01-10T09:00:00", "termination_type": "voluntary"},
            {"employee_id": "E2", "employee_name": "B", "department": "IT",
             "termination_date": "2026-01-10T09:00:00", "termination_type": "voluntary"},
        ],
        "access_log": [
            # E1: granted, never revoked -> EXCEPTION
            {"event_id": "V1", "employee_id": "E1", "employee_name": "A",
             "system": "ERP", "access_level": "standard", "action": "grant",
             "timestamp": "2025-06-01T09:00:00", "performed_by": "x"},
            # E2: granted then revoked within window -> CLEAN
            {"event_id": "V2", "employee_id": "E2", "employee_name": "B",
             "system": "ERP", "access_level": "standard", "action": "grant",
             "timestamp": "2025-06-01T09:00:00", "performed_by": "x"},
            {"event_id": "V3", "employee_id": "E2", "employee_name": "B",
             "system": "ERP", "access_level": "standard", "action": "revoke",
             "timestamp": "2026-01-10T15:00:00", "performed_by": "x"},
        ],
    }
    res = _by_id(check_ac1(ctl, evidence))
    assert res["E1"]["is_exception"] is True
    assert res["E1"]["rule"] == "never_revoked"
    assert res["E1"]["confidence"] >= 0.7
    assert res["E2"]["is_exception"] is False


def test_ac1_malformed_termination_escalates():
    ctl = load_control("AC-1")
    evidence = {
        "hr_terminations": [
            {"employee_id": "E9", "employee_name": "C", "department": "IT",
             "termination_date": "", "termination_type": "voluntary"},
        ],
        "access_log": [
            {"event_id": "V9", "employee_id": "E9", "employee_name": "C",
             "system": "ERP", "access_level": "standard", "action": "grant",
             "timestamp": "2025-06-01T09:00:00", "performed_by": "x"},
        ],
    }
    res = _by_id(check_ac1(ctl, evidence))
    assert res["E9"]["rule"] == "malformed_evidence"
    assert res["E9"]["confidence"] < 0.7  # -> escalation


# --- AC-2 -----------------------------------------------------------------
def test_ac2_catches_conflict_and_clears_clean():
    ctl = load_control("AC-2")
    evidence = {
        "role_assignments": [
            {"assignment_id": "R1", "employee_id": "U1", "employee_name": "A",
             "role": "create_vendor", "assigned_date": "2025-01-01", "assigned_by": "x"},
            {"assignment_id": "R2", "employee_id": "U1", "employee_name": "A",
             "role": "approve_payment", "assigned_date": "2025-01-01", "assigned_by": "x"},
            {"assignment_id": "R3", "employee_id": "U2", "employee_name": "B",
             "role": "read_only", "assigned_date": "2025-01-01", "assigned_by": "x"},
        ],
    }
    res = _by_id(check_ac2(ctl, evidence))
    assert res["U1"]["is_exception"] is True
    assert res["U1"]["rule"] == "conflict"
    assert res["U2"]["is_exception"] is False


def test_ac2_unknown_role_escalates():
    ctl = load_control("AC-2")
    evidence = {
        "role_assignments": [
            {"assignment_id": "R1", "employee_id": "U3", "employee_name": "A",
             "role": "read_only", "assigned_date": "2025-01-01", "assigned_by": "x"},
            {"assignment_id": "R2", "employee_id": "U3", "employee_name": "A",
             "role": "", "assigned_date": "2025-01-01", "assigned_by": "x"},
        ],
    }
    res = _by_id(check_ac2(ctl, evidence))
    assert res["U3"]["rule"] == "malformed_evidence"
    assert res["U3"]["confidence"] < 0.7


# --- AC-3 -----------------------------------------------------------------
def test_ac3_catches_missing_and_unauthorised():
    ctl = load_control("AC-3")
    evidence = {
        "access_log": [
            {"event_id": "G1", "employee_id": "P1", "employee_name": "A",
             "system": "ERP", "access_level": "privileged", "action": "grant",
             "timestamp": "2026-01-01", "performed_by": "x"},
            {"event_id": "G2", "employee_id": "P2", "employee_name": "B",
             "system": "ERP", "access_level": "privileged", "action": "grant",
             "timestamp": "2026-01-01", "performed_by": "x"},
            {"event_id": "G3", "employee_id": "P3", "employee_name": "C",
             "system": "ERP", "access_level": "privileged", "action": "grant",
             "timestamp": "2026-01-01", "performed_by": "x"},
        ],
        "approval_tickets": [
            # P2: approved by an unauthorised role -> EXCEPTION
            {"ticket_id": "T2", "employee_id": "P2", "system": "ERP",
             "access_level": "privileged", "approver": "joe",
             "approver_role": "Team_Lead", "status": "approved",
             "decision_date": "2025-12-30"},
            # P3: approved by an authorised role -> CLEAN
            {"ticket_id": "T3", "employee_id": "P3", "system": "ERP",
             "access_level": "privileged", "approver": "kim",
             "approver_role": "IT_Manager", "status": "approved",
             "decision_date": "2025-12-30"},
        ],
    }
    res = _by_id(check_ac3(ctl, evidence))
    assert res["G1"]["rule"] == "no_ticket" and res["G1"]["is_exception"]
    assert res["G2"]["rule"] == "unauthorised_approver" and res["G2"]["is_exception"]
    assert res["G3"]["is_exception"] is False


def test_verifier_drops_a_false_positive():
    """A fabricated AC-2 finding whose evidence doesn't support it is dropped."""
    ctl = load_control("AC-2")
    bogus = {
        "control_id": "AC-2", "record_id": "UX", "is_exception": True,
        "confidence": 0.98, "rule": "conflict",
        "reasoning": "claims a conflict that isn't there",
        "evidence": [
            {"assignment_id": "R1", "employee_id": "UX", "role": "read_only"},
            {"assignment_id": "R2", "employee_id": "UX", "role": "reporting"},
        ],
    }
    kept, dropped = run_verifier(ctl, [bogus])
    assert kept == []
    assert len(dropped) == 1
    assert dropped[0]["verifier"]["verdict"] == "rejected"
