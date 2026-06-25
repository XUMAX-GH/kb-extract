import pytest

from kb_extract.wiki.providers.github_models import (
    GitHubModelsAuthError,
    GitHubModelsError,
    GitHubModelsLlmClient,
)


def _http_error(code: int, retry_after: str | None = None):
    import email.message
    import io
    import urllib.error

    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        "https://x/chat/completions", code, "err", hdrs, io.BytesIO(b"")
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


def test_retries_on_429_then_succeeds():
    calls = {"n": 0}
    slept: list[float] = []

    def transport(url, headers, body, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429)
        return {"choices": [{"message": {"content": "[]"}}]}

    client = GitHubModelsLlmClient(
        token="t", transport=transport, max_retries=3, sleep=slept.append,
    )
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "[]"
    assert calls["n"] == 2
    assert len(slept) == 1  # backed off exactly once


def test_honors_retry_after_header():
    calls = {"n": 0}
    slept: list[float] = []

    def transport(url, headers, body, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429, retry_after="7")
        return {"choices": [{"message": {"content": "[]"}}]}

    client = GitHubModelsLlmClient(
        token="t", transport=transport, max_retries=3, sleep=slept.append,
    )
    client.chat([{"role": "user", "content": "hi"}])
    assert slept == [7.0]


def test_gives_up_after_max_retries():
    slept: list[float] = []

    def transport(url, headers, body, timeout):
        raise _http_error(503)

    client = GitHubModelsLlmClient(
        token="t", transport=transport, max_retries=2, sleep=slept.append,
    )
    with pytest.raises(GitHubModelsError):
        client.chat([{"role": "user", "content": "hi"}])
    assert len(slept) == 2  # retried twice, then gave up


def test_non_retryable_status_raises_immediately():
    slept: list[float] = []

    def transport(url, headers, body, timeout):
        raise _http_error(400)

    client = GitHubModelsLlmClient(
        token="t", transport=transport, max_retries=3, sleep=slept.append,
    )
    with pytest.raises(GitHubModelsError):
        client.chat([{"role": "user", "content": "hi"}])
    assert slept == []  # 400 is not retryable
