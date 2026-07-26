"""Verifier / critic agent.

Independently re-derives each drafted exception *from the cited evidence alone*
and decides whether the tester's reasoning actually holds. Findings that don't
re-derive are dropped as false positives — this is the false-positive filter the
README calls out.

Design note: the verifier does NOT trust the tester's ``is_exception`` flag or
its reasoning text. It re-checks the underlying facts in the cited rows. If a
tester ever hallucinated an exception whose evidence doesn't support it, the
verifier rejects it here.
"""
from __future__ import annotations

from datetime import timedelta

from agent.tester import _parse_ts


def _verdict(finding: dict, status: str, note: str) -> dict:
    out = dict(finding)
    out["verifier"] = {"verdict": status, "note": note}
    return out


def _verify_ac1(finding: dict, control: dict) -> dict:
    rule = finding["rule"]
    if rule == "malformed_evidence":
        return _verdict(finding, "uncertain", "Malformed evidence confirmed; escalate.")

    window = timedelta(hours=control.get("revocation_window_hours", 24))
    ev = finding["evidence"]
    term = next((r for r in ev if "termination_date" in r), None)
    grants = [r for r in ev if r.get("action") == "grant"]
    revokes = [r for r in ev if r.get("action") == "revoke"]
    if term is None or not grants:
        return _verdict(finding, "rejected", "Cited evidence lacks a termination or grant row.")
    term_dt = _parse_ts(term.get("termination_date"))
    if term_dt is None:
        return _verdict(finding, "uncertain", "Termination date unparseable; escalate.")

    deadline = term_dt + window
    for g in grants:
        matched = [r for r in revokes if r.get("system") == g.get("system")]
        if not matched:
            return _verdict(finding, "confirmed",
                            f"No revoke for grant {g['event_id']} — access still active.")
        latest = max((_parse_ts(r.get("timestamp")) for r in matched
                      if _parse_ts(r.get("timestamp"))), default=None)
        if latest is not None and latest > deadline:
            return _verdict(finding, "confirmed",
                            f"Revoke {latest} is beyond the window (deadline {deadline}).")
    return _verdict(finding, "rejected", "Cited revokes are all within the window.")


def _verify_ac2(finding: dict, control: dict) -> dict:
    if finding["rule"] == "malformed_evidence":
        return _verdict(finding, "uncertain", "Blank/unknown role confirmed; escalate.")
    pairs = [tuple(p) for p in control.get("conflicting_role_pairs", [])]
    roles = {r.get("role", "").strip() for r in finding["evidence"]}
    hit = next(((a, b) for a, b in pairs if a in roles and b in roles), None)
    if hit:
        return _verdict(finding, "confirmed",
                        f"Cited assignments hold conflicting pair {hit}.")
    return _verdict(finding, "rejected",
                    "Cited assignments do not form a conflicting pair.")


def _verify_ac3(finding: dict, control: dict) -> dict:
    rule = finding["rule"]
    if rule == "malformed_evidence":
        return _verdict(finding, "uncertain", "Contradictory ticket confirmed; escalate.")
    authorised = set(control.get("authorised_approver_roles", []))
    approved_status = control.get("approved_status", "approved")
    ev = finding["evidence"]
    tickets = [r for r in ev if "ticket_id" in r]
    if rule == "no_ticket":
        if not tickets:
            return _verdict(finding, "confirmed", "No ticket present in cited evidence.")
        return _verdict(finding, "rejected", "A ticket exists; not a no-ticket case.")
    if rule == "unauthorised_approver":
        approved = [t for t in tickets if t.get("status") == approved_status]
        if approved and all(t.get("approver_role") not in authorised for t in approved):
            return _verdict(finding, "confirmed",
                            "Approving role is not in the authorised set.")
        return _verdict(finding, "rejected",
                        "An authorised approver actually covers this grant.")
    return _verdict(finding, "rejected", f"Unrecognised AC-3 rule {rule!r}.")


_DISPATCH = {"AC-1": _verify_ac1, "AC-2": _verify_ac2, "AC-3": _verify_ac3}


def run_verifier(control: dict, findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Re-check drafted exceptions.

    Returns ``(kept, dropped)`` where ``dropped`` are false positives the
    verifier rejected. ``kept`` findings carry a ``verifier`` block.
    """
    verify = _DISPATCH[control["id"]]
    kept, dropped = [], []
    for f in findings:
        if not f.get("is_exception"):
            continue  # clean records are not "findings"
        checked = verify(f, control)
        if checked["verifier"]["verdict"] == "rejected":
            dropped.append(checked)
        else:
            kept.append(checked)
    return kept, dropped
