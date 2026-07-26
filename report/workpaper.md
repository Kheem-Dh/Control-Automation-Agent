# Control Testing Workpaper

**Controls:** AC-1, AC-2, AC-3  ·  **Confidence threshold:** 0.7  ·  **Engine:** rule

> Synthetic data only. Not a certified audit tool.

## Summary

| Metric | Count |
|--------|-------|
| Records tested | 245 |
| Passed | 222 |
| Exceptions (auto-concluded) | 17 |
| Escalated to human review | 6 |
| False positives dropped by verifier | 0 |

## AC-1 — Timely termination of access

> Terminated employees have all system access revoked within the policy window (24 hours) of their termination date.

- Tested: **25**  ·  Passed: **17**  ·  Exceptions: **6**  ·  Escalated: **2**  ·  FP dropped: **0**

### Exceptions

- **EMP0066** — `revoked_late` (confidence 0.97)
  - Reasoning: EMP0066 was terminated on 2025-12-23; access on HR_Portal was not revoked until 2025-12-29 05:00:00 — 5 days, 20:00:00 after termination, beyond the 24h window.
  - Evidence: employee_id=EMP0066, event_id=EVT00357, event_id=EVT00358
  - Verifier: confirmed — Revoke 2025-12-29 05:00:00 is beyond the window (deadline 2025-12-24 09:00:00).
- **EMP0052** — `never_revoked` (confidence 0.9)
  - Reasoning: EMP0052 was terminated on 2025-11-06 but grant EVT00359 on ERP has no revocation record — access is still active.
  - Evidence: employee_id=EMP0052, event_id=EVT00359
  - Verifier: confirmed — No revoke for grant EVT00359 — access still active.
- **EMP0171** — `never_revoked` (confidence 0.9)
  - Reasoning: EMP0171 was terminated on 2025-10-04 but grant EVT00360 on ERP has no revocation record — access is still active.
  - Evidence: employee_id=EMP0171, event_id=EVT00360
  - Verifier: confirmed — No revoke for grant EVT00360 — access still active.
- **EMP0183** — `never_revoked` (confidence 0.9)
  - Reasoning: EMP0183 was terminated on 2025-12-24 but grant EVT00361 on HR_Portal has no revocation record — access is still active.
  - Evidence: employee_id=EMP0183, event_id=EVT00361
  - Verifier: confirmed — No revoke for grant EVT00361 — access still active.
- **EMP0080** — `revoked_late` (confidence 0.97)
  - Reasoning: EMP0080 was terminated on 2025-11-30; access on VPN was not revoked until 2025-12-10 01:00:00 — 9 days, 16:00:00 after termination, beyond the 24h window.
  - Evidence: employee_id=EMP0080, event_id=EVT00362, event_id=EVT00363
  - Verifier: confirmed — Revoke 2025-12-10 01:00:00 is beyond the window (deadline 2025-12-01 09:00:00).
- **EMP0061** — `revoked_late` (confidence 0.97)
  - Reasoning: EMP0061 was terminated on 2025-12-10; access on VPN was not revoked until 2026-01-07 19:00:00 — 28 days, 10:00:00 after termination, beyond the 24h window.
  - Evidence: employee_id=EMP0061, event_id=EVT00364, event_id=EVT00365
  - Verifier: confirmed — Revoke 2026-01-07 19:00:00 is beyond the window (deadline 2025-12-11 09:00:00).

### Escalated to human review

- **EMP0067** — `malformed_evidence` (confidence 0.4) — Termination date for EMP0067 is missing or unparseable (''); cannot verify the revocation window. Routing to human review.
- **EMP0101** — `malformed_evidence` (confidence 0.4) — Termination date for EMP0101 is missing or unparseable (''); cannot verify the revocation window. Routing to human review.

## AC-2 — Segregation of duties

> No user simultaneously holds two roles that form a segregation-of-duties (SoD) conflict.

- Tested: **200**  ·  Passed: **193**  ·  Exceptions: **5**  ·  Escalated: **2**  ·  FP dropped: **0**

### Exceptions

- **EMP0046** — `conflict` (confidence 0.98)
  - Reasoning: EMP0046 holds both 'create_user' and 'approve_access', a segregation-of-duties conflict (assignments ASG00067, ASG00068).
  - Evidence: assignment_id=ASG00067, assignment_id=ASG00068
  - Verifier: confirmed — Cited assignments hold conflicting pair ('create_user', 'approve_access').
- **EMP0074** — `conflict` (confidence 0.98)
  - Reasoning: EMP0074 holds both 'create_user' and 'approve_access', a segregation-of-duties conflict (assignments ASG00110, ASG00111).
  - Evidence: assignment_id=ASG00110, assignment_id=ASG00111
  - Verifier: confirmed — Cited assignments hold conflicting pair ('create_user', 'approve_access').
- **EMP0079** — `conflict` (confidence 0.98)
  - Reasoning: EMP0079 holds both 'create_vendor' and 'approve_payment', a segregation-of-duties conflict (assignments ASG00118, ASG00119).
  - Evidence: assignment_id=ASG00118, assignment_id=ASG00119
  - Verifier: confirmed — Cited assignments hold conflicting pair ('create_vendor', 'approve_payment').
- **EMP0086** — `conflict` (confidence 0.98)
  - Reasoning: EMP0086 holds both 'create_user' and 'approve_access', a segregation-of-duties conflict (assignments ASG00130, ASG00131).
  - Evidence: assignment_id=ASG00130, assignment_id=ASG00131
  - Verifier: confirmed — Cited assignments hold conflicting pair ('create_user', 'approve_access').
- **EMP0138** — `conflict` (confidence 0.98)
  - Reasoning: EMP0138 holds both 'create_vendor' and 'approve_payment', a segregation-of-duties conflict (assignments ASG00208, ASG00209).
  - Evidence: assignment_id=ASG00208, assignment_id=ASG00209
  - Verifier: confirmed — Cited assignments hold conflicting pair ('create_vendor', 'approve_payment').

### Escalated to human review

- **EMP0032** — `malformed_evidence` (confidence 0.45) — EMP0032 has a blank/unrecognised role (['']); cannot confirm SoD status. Routing to human review.
- **EMP0102** — `malformed_evidence` (confidence 0.45) — EMP0102 has a blank/unrecognised role (['']); cannot confirm SoD status. Routing to human review.

## AC-3 — Privileged access authorisation

> Every privileged-access grant has a matching request that was approved by an authorised approver.

- Tested: **20**  ·  Passed: **12**  ·  Exceptions: **6**  ·  Escalated: **2**  ·  FP dropped: **0**

### Exceptions

- **EVT00404** — `no_ticket` (confidence 0.95)
  - Reasoning: Privileged grant EVT00404 (Billing) for EMP0020 has no matching approval ticket.
  - Evidence: event_id=EVT00404
  - Verifier: confirmed — No ticket present in cited evidence.
- **EVT00405** — `no_ticket` (confidence 0.95)
  - Reasoning: Privileged grant EVT00405 (VPN) for EMP0128 has no matching approval ticket.
  - Evidence: event_id=EVT00405
  - Verifier: confirmed — No ticket present in cited evidence.
- **EVT00406** — `no_ticket` (confidence 0.95)
  - Reasoning: Privileged grant EVT00406 (ERP) for EMP0133 has no matching approval ticket.
  - Evidence: event_id=EVT00406
  - Verifier: confirmed — No ticket present in cited evidence.
- **EVT00407** — `no_ticket` (confidence 0.95)
  - Reasoning: Privileged grant EVT00407 (Billing) for EMP0199 has no matching approval ticket.
  - Evidence: event_id=EVT00407
  - Verifier: confirmed — No ticket present in cited evidence.
- **EVT00408** — `unauthorised_approver` (confidence 0.9)
  - Reasoning: Privileged grant EVT00408 for EMP0148 is only approved by 'Contractor' (ticket TKT00012), not an authorised approver role (IT_Manager, Security_Officer).
  - Evidence: event_id=EVT00408, ticket_id=TKT00012
  - Verifier: confirmed — Approving role is not in the authorised set.
- **EVT00409** — `no_ticket` (confidence 0.95)
  - Reasoning: Privileged grant EVT00409 (HR_Portal) for EMP0099 has no matching approval ticket.
  - Evidence: event_id=EVT00409
  - Verifier: confirmed — No ticket present in cited evidence.

### Escalated to human review

- **EVT00410** — `malformed_evidence` (confidence 0.42) — Ticket TKT00013 for grant EVT00410 is marked 'approved' but its approver/approver_role is blank; contradictory evidence. Routing to human review.
- **EVT00411** — `malformed_evidence` (confidence 0.42) — Ticket TKT00014 for grant EVT00411 is marked 'approved' but its approver/approver_role is blank; contradictory evidence. Routing to human review.

