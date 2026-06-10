"""Tests for the cached LLM provider (v0.6.0).

The cached provider reads a JSON file mapping ``prompt_sha256 -> response`` and
serves answers offline / deterministically. It's the bridge that lets users
generate prompts, send them through *any* LLM (manual paste into ChatGPT,
Claude, the GitHub Copilot CLI itself, batch APIs), and replay the answers
into the wiki build with full hardness guarantees.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from kb_extract.wiki.providers.base import Message


def _hash_messages(messages: list[Message]) -> str:
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_cached_client_returns_response_from_cache(tmp_path: Path) -> None:
    from kb_extract.wiki.providers.cached import CachedLlmClient

    messages: list[Message] = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello"},
    ]
    h = _hash_messages(messages)
    cache_path = tmp_path / "responses.json"
    cache_path.write_text(
        json.dumps({h: "Hi there.[^ev-1]"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    client = CachedLlmClient(responses_path=cache_path)
    assert client.chat(messages) == "Hi there.[^ev-1]"


def test_cached_client_raises_on_missing_response_with_hash_in_message(tmp_path: Path) -> None:
    from kb_extract.wiki.providers.cached import CachedLlmClient, CachedResponseMissing

    cache_path = tmp_path / "responses.json"
    cache_path.write_text("{}", encoding="utf-8")
    client = CachedLlmClient(responses_path=cache_path)

    messages: list[Message] = [{"role": "user", "content": "what?"}]
    with pytest.raises(CachedResponseMissing) as exc_info:
        client.chat(messages)
    # The hash must be in the error so users know which prompt to fill
    assert _hash_messages(messages) in str(exc_info.value)


def test_cached_client_records_missing_prompts_when_record_path_given(tmp_path: Path) -> None:
    """When record_missing_path is set, missing prompts are appended there instead of raising."""
    from kb_extract.wiki.providers.cached import CachedLlmClient

    cache_path = tmp_path / "responses.json"
    cache_path.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing-prompts.json"

    client = CachedLlmClient(
        responses_path=cache_path,
        record_missing_path=missing,
        placeholder="<<MISSING_RESPONSE>>",
    )

    msg1: list[Message] = [{"role": "user", "content": "topic A"}]
    msg2: list[Message] = [{"role": "user", "content": "topic B"}]

    r1 = client.chat(msg1)
    r2 = client.chat(msg2)

    # Both should return the placeholder (so wiki build can proceed; user will
    # see the placeholder in the rendered files and know what to fill).
    assert r1 == "<<MISSING_RESPONSE>>"
    assert r2 == "<<MISSING_RESPONSE>>"

    # missing-prompts.json should contain both messages keyed by hash
    recorded = json.loads(missing.read_text(encoding="utf-8"))
    assert _hash_messages(msg1) in recorded
    assert _hash_messages(msg2) in recorded
    assert recorded[_hash_messages(msg1)]["messages"] == msg1


def test_cached_client_handles_unicode_in_messages_deterministically(tmp_path: Path) -> None:
    """Chinese / emoji content must hash the same way for same input (UTF-8 + sort_keys)."""
    from kb_extract.wiki.providers.cached import CachedLlmClient

    messages: list[Message] = [
        {"role": "system", "content": "你是技术写手"},
        {"role": "user", "content": "请总结：电池规格"},
    ]
    h = _hash_messages(messages)
    cache = tmp_path / "r.json"
    cache.write_text(json.dumps({h: "电池规格符合 IEC 62133。[^ev-1]"}, ensure_ascii=False),
                     encoding="utf-8")
    client = CachedLlmClient(responses_path=cache)
    out = client.chat(messages)
    assert "电池规格" in out


def test_cached_client_name(tmp_path: Path) -> None:
    from kb_extract.wiki.providers.cached import CachedLlmClient

    cache = tmp_path / "r.json"
    cache.write_text("{}", encoding="utf-8")
    c = CachedLlmClient(responses_path=cache)
    assert c.name == "cached"


def test_cached_provider_registered_in_factory(tmp_path: Path) -> None:
    """``get_provider('cached', responses_path=...)`` should work."""
    from kb_extract.wiki.providers.mock import get_provider

    cache = tmp_path / "r.json"
    cache.write_text("{}", encoding="utf-8")
    c = get_provider("cached", responses_path=cache)
    assert c.name == "cached"


def test_cached_client_missing_responses_file_treated_as_empty(tmp_path: Path) -> None:
    """If responses_path doesn't exist yet, treat as empty cache."""
    from kb_extract.wiki.providers.cached import CachedLlmClient, CachedResponseMissing

    cache = tmp_path / "nope.json"  # not created
    c = CachedLlmClient(responses_path=cache)
    with pytest.raises(CachedResponseMissing):
        c.chat([{"role": "user", "content": "x"}])
