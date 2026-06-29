"""Custom OpenAI-compatible LLM provider.

Targets any OpenAI-compatible endpoint. Endpoint, key and model resolve from
explicit args first, then KB_LLM_* env vars; default model is ``gpt-5``.
Reuses the urllib transport + retry from the GitHub Models client, so no
third-party LLM SDK is imported (H2 invariant intact).
"""

from __future__ import annotations

import os

from .github_models import GitHubModelsAuthError, GitHubModelsLlmClient

DEFAULT_MODEL = "gpt-5"


class OpenAICompatLlmClient(GitHubModelsLlmClient):
    name = "custom"

    def __init__(self, *, base_url=None, model=None, api_key=None, **kw):
        resolved_url = base_url or os.environ.get("KB_LLM_BASE_URL")
        if not resolved_url:
            raise GitHubModelsAuthError(
                "custom provider requires an endpoint; pass --base-url or set "
                "KB_LLM_BASE_URL"
            )
        super().__init__(
            base_url=resolved_url,
            model=model or os.environ.get("KB_LLM_MODEL", DEFAULT_MODEL),
            token=api_key or os.environ.get("KB_LLM_API_KEY"),
            **kw,
        )
        if not self._token:
            raise GitHubModelsAuthError(
                "custom provider requires an API key; pass --api-key or set "
                "KB_LLM_API_KEY"
            )
