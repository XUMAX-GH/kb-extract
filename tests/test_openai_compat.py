from kb_extract.wiki.providers.openai_compat import OpenAICompatLlmClient


def _fake(resp):
    def t(url, headers, body, timeout):
        assert url.endswith("/chat/completions")
        t.last = {"url": url, "auth": headers["Authorization"]}
        return {"choices": [{"message": {"content": resp}}]}
    return t


def test_custom_uses_cli_over_env(monkeypatch):
    monkeypatch.setenv("KB_LLM_BASE_URL", "https://env")
    monkeypatch.setenv("KB_LLM_MODEL", "envm")
    tr = _fake("hi")
    c = OpenAICompatLlmClient(base_url="https://cli", model="gpt-5",
                              api_key="k", transport=tr)
    assert c.chat([{"role": "user", "content": "x"}]) == "hi"
    assert tr.last["url"].startswith("https://cli")
    assert "k" in tr.last["auth"]


def test_custom_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("KB_LLM_BASE_URL", "https://env")
    monkeypatch.setenv("KB_LLM_API_KEY", "envkey")
    monkeypatch.delenv("KB_LLM_MODEL", raising=False)
    c = OpenAICompatLlmClient(transport=_fake("ok"))
    assert c.chat([{"role": "user", "content": "x"}]) == "ok"


def test_custom_requires_endpoint(monkeypatch):
    monkeypatch.delenv("KB_LLM_BASE_URL", raising=False)
    try:
        OpenAICompatLlmClient(api_key="k", transport=_fake("x"))
        assert False
    except Exception as e:
        assert "endpoint" in str(e)
