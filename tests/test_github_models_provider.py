import pytest

from kb_extract.wiki.providers.github_models import (
    GitHubModelsAuthError,
    GitHubModelsError,
    GitHubModelsLlmClient,
)


def _fake_transport(captured):
    def transport(url, headers, body, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return {"choices": [{"message": {"content": "[]"}}]}
    return transport


def test_chat_uses_injected_transport_no_network():
    captured = {}
    client = GitHubModelsLlmClient(token="t", transport=_fake_transport(captured))
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "[]"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer t"


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    with pytest.raises(GitHubModelsAuthError):
        GitHubModelsLlmClient()


def test_bad_response_shape_raises():
    def transport(url, headers, body, timeout):
        return {"unexpected": True}
    client = GitHubModelsLlmClient(token="t", transport=transport)
    with pytest.raises(GitHubModelsError):
        client.chat([{"role": "user", "content": "hi"}])


def test_token_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-tok")
    captured = {}
    client = GitHubModelsLlmClient(transport=_fake_transport(captured))
    client.chat([{"role": "user", "content": "x"}])
    assert captured["headers"]["Authorization"] == "Bearer env-tok"
