"""Shared fixtures. Tests run in deterministic rule-only mode (no API key)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("LLM_PROVIDER", "rule")

from ingest.generate import generate  # noqa: E402


@pytest.fixture(scope="session")
def dataset():
    """A small deterministic dataset generated in memory (no disk I/O)."""
    return generate(seed=7, n=120)


@pytest.fixture(scope="session")
def evidence(dataset):
    return {name: df.to_dict(orient="records") for name, df in dataset["tables"].items()}


@pytest.fixture(scope="session")
def ground_truth(dataset):
    return dataset["ground_truth"]
