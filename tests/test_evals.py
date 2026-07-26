"""Eval-harness metrics compute correctly on a tiny fixture, and end-to-end."""
from __future__ import annotations

from evals.run import score_control
from evals.stress import run_stress
from evals.run import run_eval


def test_score_control_math():
    """Hand-built state/ground-truth with a known confusion matrix."""
    state = {
        "test_results": {
            "AC-2": [{"record_id": f"U{i}"} for i in range(5)]  # U0..U4 tested
        },
        "exceptions": {
            "AC-2": [{"record_id": "U0"}, {"record_id": "U1"}, {"record_id": "U3"}]
        },
        "escalated": {"AC-2": []},
    }
    # Actual exceptions: U0, U1, U2. Predicted: U0, U1, U3.
    gt = {"AC-2": {"exceptions": ["U0", "U1", "U2"], "ambiguous": []}}
    r = score_control("AC-2", state, gt)
    assert r["tp"] == 2      # U0, U1
    assert r["fp"] == 1      # U3
    assert r["fn"] == 1      # U2
    assert r["tn"] == 1      # U4
    assert abs(r["precision"] - 2 / 3) < 1e-9
    assert abs(r["recall"] - 2 / 3) < 1e-9
    assert abs(r["fpr"] - 1 / 2) < 1e-9  # fp/(fp+tn) = 1/2


def test_ambiguous_excluded_from_population():
    state = {
        "test_results": {"AC-2": [{"record_id": "U0"}, {"record_id": "AMB"}]},
        "exceptions": {"AC-2": [{"record_id": "U0"}]},
        "escalated": {"AC-2": [{"record_id": "AMB"}]},
    }
    gt = {"AC-2": {"exceptions": ["U0"], "ambiguous": ["AMB"]}}
    r = score_control("AC-2", state, gt)
    assert r["population"] == 1  # AMB excluded
    assert r["precision"] == 1.0 and r["recall"] == 1.0


def test_end_to_end_perfect_on_rule_mode(tmp_path):
    """The rule engine should recover all planted exceptions on the fixture."""
    from ingest.generate import generate, write_outputs

    write_outputs(generate(seed=7, n=120), tmp_path)
    report = run_eval(data_dir=str(tmp_path))
    for row in report["rows"]:
        assert row["recall"] == 1.0, row
        assert row["precision"] == 1.0, row
        assert row["fpr"] == 0.0, row


def test_stress_escalates(tmp_path):
    from ingest.generate import generate, write_outputs

    write_outputs(generate(seed=7, n=120), tmp_path)
    report = run_stress(data_dir=str(tmp_path))
    # Every ambiguous record should be escalated, none auto-concluded.
    assert report["overall_escalation_rate"] == 1.0
    for row in report["rows"]:
        assert row["auto_concluded"] == 0
