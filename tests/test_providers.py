"""Provider layer (v0.8): model-agnostic resolution + robust extraction.

No network: HTTP is monkeypatched. These pin the de-Gemma contract — no model
family hardwired, explicit-model requirements, and None-safe content extraction
(reasoning models can return content=null when thinking eats the token budget).
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from smelt_rs.core.failures import ProviderError  # noqa: E402
from smelt_rs.providers import providers as prov  # noqa: E402


def test_resolve_model_chain(monkeypatch):
    monkeypatch.delenv("SMELT_MODEL", raising=False)
    monkeypatch.delenv("SMELT_NVIDIA_MODEL", raising=False)
    assert prov.resolve_model("nvidia", "explicit") == "explicit"
    assert prov.resolve_model("nvidia", None) == prov.NVIDIA_DEFAULT_MODEL
    monkeypatch.setenv("SMELT_NVIDIA_MODEL", "env-model")
    assert prov.resolve_model("nvidia", None) == "env-model"
    monkeypatch.setenv("SMELT_MODEL", "global-model")
    assert prov.resolve_model("nvidia", None) == "global-model"
    assert prov.resolve_model("nvidia", "explicit") == "explicit"
    # no default for gemini/do/openai — explicit model required
    monkeypatch.delenv("SMELT_MODEL", raising=False)
    monkeypatch.delenv("SMELT_GEMINI_MODEL", raising=False)
    assert prov.resolve_model("gemini", None) is None
    assert prov.resolve_model("local", None) == "local-model"


def test_resolve_default_provider(monkeypatch):
    monkeypatch.setenv("SMELT_PROVIDER", "local")
    assert prov.resolve_default_provider() == "local"
    monkeypatch.delenv("SMELT_PROVIDER", raising=False)
    monkeypatch.setattr(prov, "resolve_secret", lambda *n: "key" if n == ("NVIDIA_API_KEY",) else None)
    assert prov.resolve_default_provider() == "nvidia"
    monkeypatch.setattr(prov, "resolve_secret", lambda *n: None)
    assert prov.resolve_default_provider() == "local"


def test_model_required_providers(monkeypatch):
    monkeypatch.delenv("SMELT_MODEL", raising=False)
    for p in ("gemini", "do", "openai"):
        monkeypatch.delenv(f"SMELT_{p.upper()}_MODEL", raising=False)
        with pytest.raises(ProviderError, match="needs a model"):
            prov.make_provider(p, None, None, None)


def test_no_gemma_defaults_anywhere():
    """The de-Gemma contract: no model family hardwired into any default."""
    assert "gemma" not in prov.NVIDIA_DEFAULT_MODEL.lower()
    assert "gemma" not in (prov.resolve_model("local", None) or "").lower()
    for p in ("gemini", "do", "openai", "openrouter"):
        assert prov.resolve_model(p, None) is None


def test_none_content_is_typed_provider_error(monkeypatch):
    """content=null (reasoning exhausted the budget) must be a ProviderError,
    never an AttributeError crash."""
    p = prov.OpenAICompatProvider(base_url="http://x/v1", model="m", name="t")
    monkeypatch.setattr(prov, "_post_with_retries",
                        lambda *a, **k: {"choices": [{"message": {"content": None},
                                                      "finish_reason": "length"}]})
    with pytest.raises(ProviderError, match="empty completion"):
        p.generate("prompt")


def test_content_extraction_strips_fences(monkeypatch):
    p = prov.OpenAICompatProvider(base_url="http://x/v1", model="m", name="t")
    rust = "use pyo3::prelude::*;\nfn f() {}"
    monkeypatch.setattr(prov, "_post_with_retries",
                        lambda *a, **k: {"choices": [{"message": {"content": "```rust\n" + rust + "\n```"}}]})
    assert p.generate("prompt") == [rust]


def test_max_tokens_env_override(monkeypatch):
    captured = {}

    def fake_post(url, body, headers, timeout, **kw):
        captured.update(body)
        return {"choices": [{"message": {"content": "use pyo3::prelude::*;"}}]}

    p = prov.OpenAICompatProvider(base_url="http://x/v1", model="m", name="t")
    monkeypatch.setattr(prov, "_post_with_retries", fake_post)
    monkeypatch.delenv("SMELT_MAX_TOKENS", raising=False)
    p.generate("prompt")
    assert captured["max_tokens"] == 8192
    monkeypatch.setenv("SMELT_MAX_TOKENS", "4096")
    p.generate("prompt")
    assert captured["max_tokens"] == 4096
