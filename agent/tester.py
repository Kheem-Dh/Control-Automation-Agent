"""Tester agent.

Evaluates every record in a control's population against the control statement
and returns a per-record result carrying:

  * ``is_exception`` - whether the record looks like a control failure
  * ``confidence``   - 0..1, how sure the tester is
  * ``reasoning``    - a human-readable string citing the evidence rows used
  * ``evidence``     - the exact evidence rows the decision relied on
  * ``rule``         - which rule fired (for traceability / the workpaper)

The decision logic is deterministic (the "rule engine"). When a real LLM
provider is configured, the same decision stands but the reasoning string is
re-expressed by the model — the control conclusion never depends on a
non-deterministic call, which is what keeps the eval reproducible.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from agent.llm import RuleLLM, get_llm


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-ish timestamp; return None if blank/malformed."""
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _result(control_id, record_id, is_exc, confidence, rule, reasoning, evidence):
    return {
        "control_id": control_id,
        "record_id": record_id,
        "is_exception": is_exc,
        "confidence": round(float(confidence), 3),
        "rule": rule,
        "reasoning": reasoning,
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# AC-1 - timely termination of access
# ---------------------------------------------------------------------------
def check_ac1(control: dict, evidence: dict) -> list[dict]:
    window = timedelta(hours=control.get("revocation_window_hours", 24))
    conf = control.get("confidence", {})
    access_by_emp: dict[str, list[dict]] = {}
    for row in evidence.get("access_log", []):
        access_by_emp.setdefault(row["employee_id"], []).append(row)

    results = []
    for term in evidence.get("hr_terminations", []):
        emp_id = term["employee_id"]
        term_dt = _parse_ts(term.get("termination_date"))
        grants = [r for r in access_by_emp.get(emp_id, []) if r["action"] == "grant"]
        revokes = [r for r in access_by_emp.get(emp_id, []) if r["action"] == "revoke"]

        # Malformed: no usable termination date -> cannot decide -> escalate.
        if term_dt is None:
            results.append(
                _result(
                    "AC-1", emp_id, True, conf.get("malformed_evidence", 0.40),
                    "malformed_evidence",
                    f"Termination date for {emp_id} is missing or unparseable "
                    f"('{term.get('termination_date')}'); cannot verify the "
                    "revocation window. Routing to human review.",
                    [term] + grants + revokes,
                )
            )
            continue

        deadline = term_dt + window
        violating_grant = None
        violating_revoke = None
        rule = None
        for g in grants:
            # A grant is a violation unless a same-system revoke lands in time.
            matched = [r for r in revokes if r["system"] == g["system"]]
            if not matched:
                violating_grant, rule = g, "never_revoked"
                break
            # Malformed revoke timestamp -> escalate.
            if all(_parse_ts(r.get("timestamp")) is None for r in matched):
                violating_grant, violating_revoke = g, matched[0]
                rule = "malformed_evidence"
                break
            latest = max(_parse_ts(r["timestamp"]) for r in matched
                         if _parse_ts(r["timestamp"]))
            if latest > deadline:
                violating_grant = g
                violating_revoke = next(
                    r for r in matched if _parse_ts(r["timestamp"]) == latest
                )
                rule = "revoked_late"
                break

        if violating_grant is None:
            results.append(
                _result(
                    "AC-1", emp_id, False, 0.95, "clean",
                    f"All access for {emp_id} was revoked within "
                    f"{control.get('revocation_window_hours', 24)}h of "
                    f"termination ({term_dt.date()}).",
                    [term] + grants + revokes,
                )
            )
            continue

        cited = [term, violating_grant] + ([violating_revoke] if violating_revoke else [])
        if rule == "never_revoked":
            reasoning = (
                f"{emp_id} was terminated on {term_dt.date()} but grant "
                f"{violating_grant['event_id']} on {violating_grant['system']} "
                "has no revocation record — access is still active."
            )
            c = conf.get("never_revoked", 0.90)
        elif rule == "revoked_late":
            rev_dt = _parse_ts(violating_revoke["timestamp"])
            reasoning = (
                f"{emp_id} was terminated on {term_dt.date()}; access on "
                f"{violating_grant['system']} was not revoked until {rev_dt} "
                f"— {(rev_dt - term_dt)} after termination, beyond the "
                f"{control.get('revocation_window_hours', 24)}h window."
            )
            c = conf.get("revoked_late", 0.97)
        else:  # malformed revoke
            reasoning = (
                f"Revocation record for {emp_id} on {violating_grant['system']} "
                "has a missing/unparseable timestamp; cannot confirm timing. "
                "Routing to human review."
            )
            c = conf.get("malformed_evidence", 0.40)

        results.append(
            _result("AC-1", emp_id, True, c, rule, reasoning, cited)
        )
    return results


# ---------------------------------------------------------------------------
# AC-2 - segregation of duties
# ---------------------------------------------------------------------------
def check_ac2(control: dict, evidence: dict) -> list[dict]:
    conf = control.get("confidence", {})
    pairs = [tuple(p) for p in control.get("conflicting_role_pairs", [])]
    known = set(control.get("known_roles", []))

    roles_by_emp: dict[str, list[dict]] = {}
    for row in evidence.get("role_assignments", []):
        roles_by_emp.setdefault(row["employee_id"], []).append(row)

    results = []
    for emp_id, rows in sorted(roles_by_emp.items()):
        roles = [r["role"].strip() for r in rows]
        role_set = set(roles)

        # Malformed: a blank or unknown role -> cannot fully assess -> escalate.
        unknown = [r for r in roles if r == "" or (known and r not in known)]
        conflict = next(
            ((a, b) for a, b in pairs if a in role_set and b in role_set), None
        )

        if conflict:
            cited = [r for r in rows if r["role"].strip() in conflict]
            results.append(
                _result(
                    "AC-2", emp_id, True, conf.get("conflict", 0.98), "conflict",
                    f"{emp_id} holds both '{conflict[0]}' and '{conflict[1]}', a "
                    "segregation-of-duties conflict "
                    f"(assignments {', '.join(r['assignment_id'] for r in cited)}).",
                    cited,
                )
            )
        elif unknown:
            results.append(
                _result(
                    "AC-2", emp_id, True, conf.get("malformed_evidence", 0.45),
                    "malformed_evidence",
                    f"{emp_id} has a blank/unrecognised role "
                    f"({unknown!r}); cannot confirm SoD status. Routing to "
                    "human review.",
                    rows,
                )
            )
        else:
            results.append(
                _result(
                    "AC-2", emp_id, False, 0.95, "clean",
                    f"{emp_id}'s roles ({', '.join(sorted(role_set))}) contain "
                    "no conflicting pair.",
                    rows,
                )
            )
    return results


# ---------------------------------------------------------------------------
# AC-3 - privileged access authorisation
# ---------------------------------------------------------------------------
def check_ac3(control: dict, evidence: dict) -> list[dict]:
    conf = control.get("confidence", {})
    authorised = set(control.get("authorised_approver_roles", []))
    approved_status = control.get("approved_status", "approved")

    tickets_by_emp: dict[str, list[dict]] = {}
    for t in evidence.get("approval_tickets", []):
        tickets_by_emp.setdefault(t["employee_id"], []).append(t)

    results = []
    priv_grants = [
        r
        for r in evidence.get("access_log", [])
        if r.get("access_level") == "privileged" and r.get("action") == "grant"
    ]
    for grant in priv_grants:
        evt = grant["event_id"]
        emp_id = grant["employee_id"]
        candidates = [
            t
            for t in tickets_by_emp.get(emp_id, [])
            if t.get("system") == grant.get("system")
            and t.get("access_level") == "privileged"
        ]
        approved = [t for t in candidates if t.get("status") == approved_status]

        if not candidates:
            results.append(
                _result(
                    "AC-3", evt, True, conf.get("no_ticket", 0.95), "no_ticket",
                    f"Privileged grant {evt} ({grant['system']}) for {emp_id} has "
                    "no matching approval ticket.",
                    [grant],
                )
            )
            continue

        # Contradictory/malformed: approved status but blank approver -> escalate.
        malformed = [
            t
            for t in approved
            if not t.get("approver", "").strip()
            or not t.get("approver_role", "").strip()
        ]
        if malformed:
            results.append(
                _result(
                    "AC-3", evt, True, conf.get("malformed_evidence", 0.42),
                    "malformed_evidence",
                    f"Ticket {malformed[0]['ticket_id']} for grant {evt} is marked "
                    f"'{approved_status}' but its approver/approver_role is blank; "
                    "contradictory evidence. Routing to human review.",
                    [grant, malformed[0]],
                )
            )
            continue

        authorised_ok = [t for t in approved if t.get("approver_role") in authorised]
        if authorised_ok:
            t = authorised_ok[0]
            results.append(
                _result(
                    "AC-3", evt, False, 0.95, "clean",
                    f"Privileged grant {evt} is covered by approved ticket "
                    f"{t['ticket_id']} from authorised approver role "
                    f"'{t['approver_role']}'.",
                    [grant, t],
                )
            )
        else:
            t = approved[0] if approved else candidates[0]
            results.append(
                _result(
                    "AC-3", evt, True, conf.get("unauthorised_approver", 0.90),
                    "unauthorised_approver",
                    f"Privileged grant {evt} for {emp_id} is only approved by "
                    f"'{t.get('approver_role') or 'unknown'}' "
                    f"(ticket {t['ticket_id']}), not an authorised approver role "
                    f"({', '.join(sorted(authorised))}).",
                    [grant, t],
                )
            )
    return results


_DISPATCH = {"AC-1": check_ac1, "AC-2": check_ac2, "AC-3": check_ac3}


def _enrich_reasoning(llm, control: dict, result: dict) -> None:
    """In LLM mode, re-express the reasoning via the model (decision unchanged)."""
    if isinstance(llm, RuleLLM):
        return
    try:
        system = (
            "You are an IT controls tester. Given a control statement, a record, "
            "the cited evidence, and a preliminary verdict, write one concise, "
            "factual sentence explaining the verdict, citing evidence ids. Do not "
            "change the verdict."
        )
        user = (
            f"Control: {control.get('statement')}\n"
            f"Verdict: {'EXCEPTION' if result['is_exception'] else 'PASS'} "
            f"(rule={result['rule']}, confidence={result['confidence']})\n"
            f"Evidence: {result['evidence']}\n"
            f"Preliminary reasoning: {result['reasoning']}"
        )
        text = llm.complete(system, user).strip()
        if text:
            result["reasoning"] = text
    except Exception:
        pass  # keep the deterministic reasoning on any failure


def run_tester(control: dict, evidence: dict, llm=None) -> list[dict]:
    """Run the tester for a single control over its population."""
    control_id = control["id"]
    if control_id not in _DISPATCH:
        raise KeyError(f"No tester implemented for control {control_id}")
    llm = llm or get_llm()
    results = _DISPATCH[control_id](control, evidence)
    for r in results:
        _enrich_reasoning(llm, control, r)
    return results
