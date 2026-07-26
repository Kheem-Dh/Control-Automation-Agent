"""Deterministic synthetic-evidence generator.

Produces four evidence files and a ground-truth label file. Everything is
generated with Faker under a fixed seed so the same ``--seed`` always yields
the same population, the same planted exceptions, and the same ground truth.

Nothing here is, resembles, or is derived from any real organisation's data.

Evidence produced (written to ``data/``):
  * access_log.csv        - grant/revoke events per employee & system
  * hr_terminations.csv   - HR termination records
  * approval_tickets.csv  - access-request approval tickets
  * role_assignments.csv  - role grants (used for SoD testing)

Ground truth (``data/ground_truth.json``) records, per control, which records
are TRUE exceptions and which are deliberately ambiguous/malformed (for the
stress test). The eval harness scores agent findings against this file.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

# Systems and roles the population is drawn from.
SYSTEMS = ["ERP", "Billing", "HR_Portal", "DataWarehouse", "VPN"]
KNOWN_ROLES = [
    "create_vendor",
    "approve_payment",
    "create_user",
    "approve_access",
    "submit_journal",
    "approve_journal",
    "read_only",
    "reporting",
]
CONFLICT_PAIRS = [
    ("create_vendor", "approve_payment"),
    ("create_user", "approve_access"),
    ("submit_journal", "approve_journal"),
]
AUTHORISED_APPROVER_ROLES = ["IT_Manager", "Security_Officer"]
UNAUTHORISED_APPROVER_ROLES = ["Team_Lead", "Analyst", "Contractor"]

REVOCATION_WINDOW_HOURS = 24
# A fixed "as of" reference date keeps every timestamp deterministic.
REFERENCE_DATE = datetime(2026, 1, 1, 9, 0, 0)


@dataclass
class GroundTruth:
    """Accumulates the labels the eval harness scores against."""

    ac1_exceptions: list[str] = field(default_factory=list)
    ac1_ambiguous: list[str] = field(default_factory=list)
    ac2_exceptions: list[str] = field(default_factory=list)
    ac2_ambiguous: list[str] = field(default_factory=list)
    ac3_exceptions: list[str] = field(default_factory=list)
    ac3_ambiguous: list[str] = field(default_factory=list)

    def to_dict(self, seed: int, n: int) -> dict:
        return {
            "seed": seed,
            "n": n,
            "generated_at": REFERENCE_DATE.isoformat(),
            "AC-1": {
                "population": "hr_terminations",
                "key": "employee_id",
                "exceptions": sorted(self.ac1_exceptions),
                "ambiguous": sorted(self.ac1_ambiguous),
            },
            "AC-2": {
                "population": "role_assignments",
                "key": "employee_id",
                "exceptions": sorted(self.ac2_exceptions),
                "ambiguous": sorted(self.ac2_ambiguous),
            },
            "AC-3": {
                "population": "access_log",
                "key": "event_id",
                "exceptions": sorted(self.ac3_exceptions),
                "ambiguous": sorted(self.ac3_ambiguous),
            },
        }


def _emp_id(i: int) -> str:
    return f"EMP{i:04d}"


def _iso(dt: datetime | None) -> str:
    return "" if dt is None else dt.isoformat()


def generate(seed: int = 42, n: int = 200) -> dict:
    """Generate the full evidence set + ground truth in memory.

    Returns a dict of ``{"tables": {name: DataFrame}, "ground_truth": dict}``.
    """
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    gt = GroundTruth()

    employees = []
    for i in range(n):
        employees.append(
            {
                "employee_id": _emp_id(i),
                "employee_name": fake.name(),
                "department": rng.choice(
                    ["Finance", "IT", "Sales", "HR", "Operations", "Legal"]
                ),
                "hire_date": (REFERENCE_DATE - timedelta(days=rng.randint(200, 2000))),
            }
        )

    # -- how many exceptions to plant per control (scaled to n) ---------------
    n_terminated = max(8, n // 8)          # ~25 terminated employees at n=200
    n_ac1_exc = max(3, n_terminated // 4)  # planted AC-1 exceptions
    n_ac1_amb = 2                          # ambiguous terminations (stress)
    n_ac2_exc = max(3, n // 40)            # planted SoD conflicts
    n_ac2_amb = 2                          # ambiguous role assignments (stress)
    n_ac3_exc = max(3, n // 30)            # planted privileged-access exceptions
    n_ac3_amb = 2                          # ambiguous approval evidence (stress)

    # ========================================================================
    # HR terminations + AC-1 (termination access revocation)
    # ========================================================================
    terminated = rng.sample(employees, n_terminated)
    terminated_ids = set(e["employee_id"] for e in terminated)
    non_terminated = [e for e in employees if e["employee_id"] not in terminated_ids]
    ac1_exc_set = set(e["employee_id"] for e in terminated[:n_ac1_exc])
    ac1_amb_set = set(
        e["employee_id"] for e in terminated[n_ac1_exc : n_ac1_exc + n_ac1_amb]
    )

    hr_rows = []
    access_rows = []
    event_counter = 0

    def _next_event() -> str:
        nonlocal event_counter
        eid = f"EVT{event_counter:05d}"
        event_counter += 1
        return eid

    # Baseline standard access for ACTIVE (non-terminated) employees only.
    # Terminated employees get their access solely from the AC-1 section below,
    # so their revocation state is fully controlled and matches ground truth.
    for emp in non_terminated:
        for _ in range(rng.randint(1, 3)):
            grant_dt = emp["hire_date"] + timedelta(days=rng.randint(0, 60))
            access_rows.append(
                {
                    "event_id": _next_event(),
                    "employee_id": emp["employee_id"],
                    "employee_name": emp["employee_name"],
                    "system": rng.choice(SYSTEMS),
                    "access_level": "standard",
                    "action": "grant",
                    "timestamp": _iso(grant_dt),
                    "performed_by": fake.user_name(),
                }
            )

    for emp in terminated:
        emp_id = emp["employee_id"]
        term_dt = REFERENCE_DATE - timedelta(days=rng.randint(1, 120))
        is_exc = emp_id in ac1_exc_set
        is_amb = emp_id in ac1_amb_set

        hr_rows.append(
            {
                "employee_id": emp_id,
                "employee_name": emp["employee_name"],
                "department": emp["department"],
                # Ambiguous records get a blank/malformed termination date.
                "termination_date": "" if is_amb else _iso(term_dt),
                "termination_type": rng.choice(
                    ["voluntary", "involuntary", "retirement"]
                ),
            }
        )

        # This employee's access grant that must be revoked on termination.
        grant_dt = term_dt - timedelta(days=rng.randint(30, 400))
        grant_evt = _next_event()
        access_rows.append(
            {
                "event_id": grant_evt,
                "employee_id": emp_id,
                "employee_name": emp["employee_name"],
                "system": rng.choice(SYSTEMS),
                "access_level": "standard",
                "action": "grant",
                "timestamp": _iso(grant_dt),
                "performed_by": fake.user_name(),
            }
        )

        if is_exc:
            # EXCEPTION: either never revoked, or revoked well after window.
            if rng.random() < 0.5:
                pass  # never revoked -> no revoke row at all
            else:
                late = term_dt + timedelta(hours=rng.randint(48, 720))
                access_rows.append(
                    {
                        "event_id": _next_event(),
                        "employee_id": emp_id,
                        "employee_name": emp["employee_name"],
                        "system": access_rows[-1]["system"],
                        "access_level": "standard",
                        "action": "revoke",
                        "timestamp": _iso(late),
                        "performed_by": fake.user_name(),
                    }
                )
        elif is_amb:
            # AMBIGUOUS: a revoke row exists but with a blank timestamp, and the
            # termination_date is blank -> cannot decide -> should escalate.
            access_rows.append(
                {
                    "event_id": _next_event(),
                    "employee_id": emp_id,
                    "employee_name": emp["employee_name"],
                    "system": access_rows[-1]["system"],
                    "access_level": "standard",
                    "action": "revoke",
                    "timestamp": "",
                    "performed_by": fake.user_name(),
                }
            )
        else:
            # CLEAN: revoked within the policy window.
            on_time = term_dt + timedelta(hours=rng.randint(1, REVOCATION_WINDOW_HOURS))
            access_rows.append(
                {
                    "event_id": _next_event(),
                    "employee_id": emp_id,
                    "employee_name": emp["employee_name"],
                    "system": access_rows[-1]["system"],
                    "access_level": "standard",
                    "action": "revoke",
                    "timestamp": _iso(on_time),
                    "performed_by": fake.user_name(),
                }
            )

    gt.ac1_exceptions = sorted(ac1_exc_set)
    gt.ac1_ambiguous = sorted(ac1_amb_set)

    # ========================================================================
    # Role assignments + AC-2 (segregation of duties)
    # ========================================================================
    role_rows = []
    assignment_counter = 0

    def _next_assignment() -> str:
        nonlocal assignment_counter
        aid = f"ASG{assignment_counter:05d}"
        assignment_counter += 1
        return aid

    # Candidates for planted conflicts / ambiguity: active employees only, so
    # AC-2 exceptions never overlap the terminated AC-1 population.
    conflict_emps = rng.sample(non_terminated, n_ac2_exc)
    conflict_ids = set(e["employee_id"] for e in conflict_emps)
    remaining = [e for e in non_terminated if e["employee_id"] not in conflict_ids]
    amb_role_emps = rng.sample(remaining, n_ac2_amb)
    amb_role_ids = set(e["employee_id"] for e in amb_role_emps)

    for emp in employees:
        emp_id = emp["employee_id"]
        if emp_id in conflict_ids:
            # EXCEPTION: assign both roles of a conflicting pair.
            pair = rng.choice(CONFLICT_PAIRS)
            roles = list(pair)
        elif emp_id in amb_role_ids:
            # AMBIGUOUS: one recognised role + one blank/unknown role.
            roles = [rng.choice(["read_only", "reporting"]), ""]
        else:
            # CLEAN: 1-2 non-conflicting roles.
            safe = ["read_only", "reporting", "create_vendor", "create_user"]
            roles = rng.sample(safe, rng.randint(1, 2))
            # Guard: never accidentally form a conflicting pair.
            roles = [roles[0]] if _has_conflict(roles) else roles

        for role in roles:
            role_rows.append(
                {
                    "assignment_id": _next_assignment(),
                    "employee_id": emp_id,
                    "employee_name": emp["employee_name"],
                    "role": role,
                    "assigned_date": _iso(
                        REFERENCE_DATE - timedelta(days=rng.randint(10, 900))
                    ),
                    "assigned_by": fake.user_name(),
                }
            )

    gt.ac2_exceptions = sorted(conflict_ids)
    gt.ac2_ambiguous = sorted(amb_role_ids)

    # ========================================================================
    # Privileged grants + approval tickets + AC-3 (privileged access)
    # ========================================================================
    ticket_rows = []
    ticket_counter = 0

    def _next_ticket() -> str:
        nonlocal ticket_counter
        tid = f"TKT{ticket_counter:05d}"
        ticket_counter += 1
        return tid

    # Pick ACTIVE employees who receive privileged grants (a terminated
    # employee's privileged grant would otherwise also read as an AC-1 issue).
    n_priv = max(n_ac3_exc + n_ac3_amb + 8, n // 10)
    priv_emps = rng.sample(non_terminated, min(n_priv, len(non_terminated)))
    priv_events = []  # (event_id, employee)
    for emp in priv_emps:
        grant_dt = REFERENCE_DATE - timedelta(days=rng.randint(1, 300))
        evt = _next_event()
        access_rows.append(
            {
                "event_id": evt,
                "employee_id": emp["employee_id"],
                "employee_name": emp["employee_name"],
                "system": rng.choice(SYSTEMS),
                "access_level": "privileged",
                "action": "grant",
                "timestamp": _iso(grant_dt),
                "performed_by": fake.user_name(),
            }
        )
        priv_events.append((evt, emp, grant_dt))

    # Decide which privileged grants are exceptions / ambiguous.
    exc_events = priv_events[:n_ac3_exc]
    amb_events = priv_events[n_ac3_exc : n_ac3_exc + n_ac3_amb]
    clean_events = priv_events[n_ac3_exc + n_ac3_amb :]

    ac3_exc_ids, ac3_amb_ids = [], []

    for evt, emp, grant_dt in clean_events:
        # CLEAN: matching approved ticket from an authorised approver.
        ticket_rows.append(
            {
                "ticket_id": _next_ticket(),
                "employee_id": emp["employee_id"],
                "system": _system_of(access_rows, evt),
                "access_level": "privileged",
                "approver": fake.user_name(),
                "approver_role": rng.choice(AUTHORISED_APPROVER_ROLES),
                "status": "approved",
                "decision_date": _iso(grant_dt - timedelta(days=rng.randint(0, 5))),
            }
        )

    for evt, emp, grant_dt in exc_events:
        ac3_exc_ids.append(evt)
        if rng.random() < 0.5:
            # EXCEPTION type A: no ticket at all -> emit nothing.
            continue
        # EXCEPTION type B: ticket approved by an unauthorised role.
        ticket_rows.append(
            {
                "ticket_id": _next_ticket(),
                "employee_id": emp["employee_id"],
                "system": _system_of(access_rows, evt),
                "access_level": "privileged",
                "approver": fake.user_name(),
                "approver_role": rng.choice(UNAUTHORISED_APPROVER_ROLES),
                "status": "approved",
                "decision_date": _iso(grant_dt - timedelta(days=rng.randint(0, 5))),
            }
        )

    for evt, emp, grant_dt in amb_events:
        ac3_amb_ids.append(evt)
        # AMBIGUOUS: contradictory ticket - marked approved but approver blank.
        ticket_rows.append(
            {
                "ticket_id": _next_ticket(),
                "employee_id": emp["employee_id"],
                "system": _system_of(access_rows, evt),
                "access_level": "privileged",
                "approver": "",
                "approver_role": "",
                "status": "approved",
                "decision_date": _iso(grant_dt - timedelta(days=rng.randint(0, 5))),
            }
        )

    gt.ac3_exceptions = sorted(ac3_exc_ids)
    gt.ac3_ambiguous = sorted(ac3_amb_ids)

    tables = {
        "access_log": pd.DataFrame(access_rows),
        "hr_terminations": pd.DataFrame(hr_rows),
        "approval_tickets": pd.DataFrame(ticket_rows),
        "role_assignments": pd.DataFrame(role_rows),
    }
    return {"tables": tables, "ground_truth": gt.to_dict(seed, n)}


def _has_conflict(roles: list[str]) -> bool:
    rset = set(roles)
    return any(a in rset and b in rset for a, b in CONFLICT_PAIRS)


def _system_of(access_rows: list[dict], event_id: str) -> str:
    for r in access_rows:
        if r["event_id"] == event_id:
            return r["system"]
    return ""


def write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in result["tables"].items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    with (out_dir / "ground_truth.json").open("w") as fh:
        json.dump(result["ground_truth"], fh, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ITGC evidence.")
    parser.add_argument("--seed", type=int, default=42, help="deterministic seed")
    parser.add_argument("--n", type=int, default=200, help="number of employees")
    parser.add_argument(
        "--out",
        type=str,
        default="data",
        help="output directory for evidence + ground truth",
    )
    args = parser.parse_args()

    result = generate(seed=args.seed, n=args.n)
    out_dir = Path(args.out)
    write_outputs(result, out_dir)

    gt = result["ground_truth"]
    print(f"Generated {args.n} employees (seed={args.seed}) -> {out_dir}/")
    for cid in ("AC-1", "AC-2", "AC-3"):
        print(
            f"  {cid}: {len(gt[cid]['exceptions'])} exceptions, "
            f"{len(gt[cid]['ambiguous'])} ambiguous (stress)"
        )


if __name__ == "__main__":
    main()
