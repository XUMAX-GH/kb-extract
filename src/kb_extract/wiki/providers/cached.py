"""Cached LLM provider.

Maps a canonical SHA-256 of the prompt to a pre-recorded response. The cache
file is plain JSON, easy to author manually or to generate by piping prompts
into any external LLM (Claude CLI, OpenAI batch, manual paste, etc).

Two modes:
1. **strict** (default): missing prompts raise ``CachedResponseMissing`` with
   the prompt hash, so users know exactly which entry to fill.
2. **record**: when ``record_missing_path`` is set, missing prompts are
   appended to that file and a placeholder string is returned. This lets a
   wiki build complete on the first pass (with placeholders in the output)
   while emitting a clean to-do list of prompts that still need answers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .base import Message


class CachedResponseMissing(KeyError):
    """Raised when a prompt has no cached response and no record path is set."""


def _canonical_bytes(messages: list[Message]) -> bytes:
    return json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")


def prompt_hash(messages: list[Message]) -> str:
    """Stable SHA-256 of a chat-completion-style message list.

    Uses ``ensure_ascii=False`` so CJK content survives, and ``sort_keys=True``
    for determinism across Python dict-iteration orders.
    """
    return hashlib.sha256(_canonical_bytes(messages)).hexdigest()


class CachedLlmClient:
    """LLM client that reads responses from a JSON file keyed by prompt hash."""

    name = "cached"

    def __init__(
        self,
        *,
        responses_path: Path,
        record_missing_path: Path | None = None,
        placeholder: str = "<<MISSING_RESPONSE>>",
    ) -> None:
        self._responses_path = Path(responses_path)
        self._record_missing_path = Path(record_missing_path) if record_missing_path else None
        self._placeholder = placeholder
        self._cache: dict[str, str] = self._load_cache()

    def _load_cache(self) -> dict[str, str]:
        if not self._responses_path.is_file():
            return {}
        try:
            raw = json.loads(self._responses_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"cached provider: {self._responses_path} is not valid JSON ({e})"
            ) from e
        if not isinstance(raw, dict):
            raise ValueError(
                f"cached provider: {self._responses_path} must be a JSON object "
                "of the form {{prompt_hash: response_string}}"
            )
        return {str(k): str(v) for k, v in raw.items()}

    def chat(self, messages: list[Message]) -> str:
        h = prompt_hash(messages)
        if h in self._cache:
            return self._cache[h]
        if self._record_missing_path is None:
            raise CachedResponseMissing(
                f"no cached response for prompt hash {h}; add it to "
                f"{self._responses_path}"
            )
        # Record mode: append to record file and return placeholder
        self._record_missing(h, messages)
        return self._placeholder

    def _record_missing(self, h: str, messages: list[Message]) -> None:
        path = self._record_missing_path
        assert path is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, dict[str, object]] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = {str(k): v for k, v in loaded.items()}
            except json.JSONDecodeError:
                pass
        if h not in existing:
            existing[h] = {"messages": messages}
            self._atomic_write_json(path, existing)

    @staticmethod
    def _atomic_write_json(path: Path, obj: dict[str, object]) -> None:
        data = (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        with NamedTemporaryFile(
            mode="wb", dir=path.parent, delete=False, prefix=".tmp-", suffix=".part"
        ) as tmp:
            tmp.write(data)
            tmp_name = tmp.name
        os.replace(tmp_name, path)
