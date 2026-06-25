"""GitHub Models LLM provider (OpenAI-compatible chat completions).

Network access is wrapped in an injectable ``transport`` callable so tests
never touch the socket. The default transport uses urllib (stdlib only) --
no third-party LLM SDK is imported, keeping the H2 invariant intact.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any

from .base import Message

DEFAULT_BASE_URL = "https://models.github.ai/inference"
DEFAULT_MODEL = "openai/gpt-4o-mini"

Transport = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


class GitHubModelsError(RuntimeError):
    """Base error for the GitHub Models provider."""


class GitHubModelsAuthError(GitHubModelsError):
    """Raised when no token is available."""


def _urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> dict[str, Any]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class GitHubModelsLlmClient:
    name = "github-models"

    def __init__(
        self,
        *,
        model: str | None = None,
        token: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
        timeout: float = 60.0,
        transport: Transport | None = None,
    ) -> None:
        self._token = (
            token
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GITHUB_MODELS_TOKEN")
        )
        if not self._token:
            raise GitHubModelsAuthError(
                "github-models provider requires a token; set GITHUB_TOKEN "
                "or pass token=..."
            )
        self._model = model or os.environ.get("KB_GITHUB_MODEL", DEFAULT_MODEL)
        self._base_url = (
            base_url or os.environ.get("KB_GITHUB_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self._temperature = temperature
        self._timeout = timeout
        self._transport = transport or _urllib_transport

    def chat(self, messages: list[Message]) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        resp = self._transport(url, headers, body, self._timeout)
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise GitHubModelsError(f"unexpected response shape: {resp!r}") from e
