"""sp3 测试：MockLlmClient 的确定性。"""

from __future__ import annotations

import pytest

from kb_extract.wiki.providers.mock import MockLlmClient, get_provider

pytestmark = pytest.mark.disable_socket


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def test_mock_provider_is_deterministic_for_same_seed_and_input() -> None:
    msgs = [_msg("system", "sys"), _msg("user", "Topic: X\n[1] A\n[2] B")]
    a = MockLlmClient(seed=42).chat(msgs)
    b = MockLlmClient(seed=42).chat(msgs)
    assert a == b


def test_mock_provider_changes_with_seed() -> None:
    msgs = [_msg("user", "Topic: X\n[1] A\n[2] B")]
    a = MockLlmClient(seed=0).chat(msgs)
    b = MockLlmClient(seed=1).chat(msgs)
    assert a != b


def test_mock_provider_changes_with_input() -> None:
    a = MockLlmClient(seed=0).chat([_msg("user", "Topic: X\n[1] A")])
    b = MockLlmClient(seed=0).chat([_msg("user", "Topic: Y\n[1] A")])
    assert a != b


def test_mock_provider_emits_evidence_pins() -> None:
    out = MockLlmClient(seed=0).chat([_msg("user", "Topic: T\n[1] alpha\n[2] beta\n[3] gamma")])
    assert "[^ev-" in out


def test_get_provider_defaults_to_mock_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KB_EXTRACT_LLM_PROVIDER", raising=False)
    p = get_provider()
    assert p.name == "mock"


def test_get_provider_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="未知"):
        get_provider("does-not-exist")


def test_get_provider_real_providers_are_stubbed() -> None:
    with pytest.raises(NotImplementedError):
        get_provider("openai")
