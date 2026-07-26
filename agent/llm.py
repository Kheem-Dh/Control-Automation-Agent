"""Swappable LLM layer.

Three modes, selected by the ``LLM_PROVIDER`` env var (default ``rule``):

  * ``rule``      - deterministic, no API key, no network. Used in CI, in tests,
                    and by anyone cloning the repo without a key. The tester and
                    verifier fall back to their built-in rule engines.
  * ``openai``    - OpenAI GPT-4o (reads ``OPENAI_API_KEY``).
  * ``anthropic`` - Anthropic Claude Sonnet (reads ``ANTHROPIC_API_KEY``).

The provider object exposes a single ``complete(system, user) -> str`` method.
``RuleLLM.mode == "rule"`` signals callers to use their deterministic logic
instead of prompting a model, so the exact same code path runs with or without
a key — only the reasoning text differs.
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader (no python-dotenv dependency required)."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


class RuleLLM:
    """No-op provider. Callers detect ``mode == 'rule'`` and use rule logic."""

    mode = "rule"
    model = "rule-engine"

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        raise RuntimeError("RuleLLM has no model; use the rule engine instead.")


class OpenAILLM:
    mode = "llm"

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        from openai import OpenAI  # imported lazily so rule mode needs no dep

        self.model = model
        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def complete(self, system: str, user: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


class AnthropicLLM:
    mode = "llm"

    def __init__(
        self, model: str = "claude-sonnet-4-5", api_key: str | None = None
    ):
        import anthropic  # imported lazily so rule mode needs no dep

        self.model = model
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )

    def complete(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )


def get_llm(provider: str | None = None):
    """Return an LLM provider.

    Falls back to ``RuleLLM`` whenever the requested provider is unavailable or
    its API key is missing, so the pipeline is always runnable.
    """
    _load_dotenv()
    provider = (provider or os.environ.get("LLM_PROVIDER", "rule")).lower()

    try:
        if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
            return OpenAILLM(model=os.environ.get("LLM_MODEL", "gpt-4o"))
        if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            return AnthropicLLM(
                model=os.environ.get("LLM_MODEL", "claude-sonnet-4-5")
            )
    except Exception:
        # Any import/auth failure degrades gracefully to deterministic mode.
        return RuleLLM()

    return RuleLLM()
