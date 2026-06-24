# SP-3 实施计划：`kb wiki requirements`（领域路由 + 证据溯源的需求抽取）

关联 spec：`docs/superpowers/specs/2026-06-24-enrichment-kb-design.md`
分支：`feat/enrichment-kb`（基于 `origin/main`）
方法：TDD，每个 task 一次提交（测试先行）。全部建在 **wiki 层**内部，复用
`wiki/providers/*`、`wiki/sections.py`、anchor 引用机制，不新建 `enrichment/` 包。

## 背景与不变量（所有 task 必须遵守）

- **H2**：`tests/test_no_llm_imports.py` 只扫描 `src/kb_extract/adapters/**`。所有
  新代码放在 `src/kb_extract/wiki/requirements/` 和 `wiki/providers/` 下，不要让
  adapters 引用它们。
- **联网禁用**：测试默认 `--disable-socket`。GitHub Models provider 必须通过
  **可注入 transport** 测试，绝不真实联网，绝不打 `@pytest.mark.enable_socket`。
- **字节可复现（H13）**：所有写盘内容用 LF / 无 BOM / 单一末尾换行；JSON 用
  `ensure_ascii=False`、固定字段/元素顺序。需排序处一律 `sorted(...)`，禁止依赖
  dict/set 迭代顺序。
- **证据溯源**：每条抽取结果的 `EvidenceRef` 必须是 kb `main.md` 里真实存在的
  `<a id="sec-NNNN"></a>` anchor；由代码确定性回填，不信任 LLM 自填。
- **确定性 LLM**：默认 provider 为 `mock`；可复现产物用 `cached`（按 prompt_hash）。
  `github-models` 仅用于真实生成，temperature=0。
- 提交信息用英文，含 `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`。
- 每个 task 结束运行 `uv run pytest` 与 `uv run ruff check .`，必须全绿。

## 目录结构（最终形态）

```
src/kb_extract/wiki/
  providers/
    github_models.py          # Task 3：GitHubModelsLlmClient
  requirements/
    __init__.py
    assets/
      base_extraction.md      # = CTx prompts/base_system_rules.md（逐字）
      p1_rules.md             # = CTx prompts/P1_variant_rules.md（逐字）
      user_template.md        # = CTx prompts/P1_user_template.md（逐字）
      output_schema.json      # = CTx base-extraction/references/output_schema.json
      domain_rules.json       # = CTx section-router/.../domain_mapping.md 中的 JSON
      domains/<domain>.md     # = CTx domain_skills/<domain>/SKILL.md（逐字，每个域一个）
    router.py                 # Task 1：确定性领域路由
    prompts.py                # Task 2：组装 list[Message]
    models.py                 # Task 4：TestItem + 解析/校正
    extractor.py              # Task 4：编排（route -> read -> chat -> parse -> stamp）
    render.py                 # Task 5：requirements.json + requirements.md
tests/
  test_requirements_router.py     # Task 1
  test_requirements_prompts.py    # Task 2
  test_github_models_provider.py  # Task 3
  test_requirements_extractor.py  # Task 4
  test_requirements_render.py     # Task 5
  test_requirements_cli.py        # Task 6
```

---

## Task 1：领域路由（router.py + 资产）

**目标**：把 CTx 的 `domain_mapping.md` 关键词表移植为确定性路由：给定 section 标题
（含可选小节号），返回 `(domain, method)`。命中 `section_patterns` 优先；否则按关键词
命中数最多者；并列或 0 命中 -> 回退 `base-extraction`。

**新建 `src/kb_extract/wiki/requirements/__init__.py`**：空文件（仅包标识，docstring 一行）。

**新建 `src/kb_extract/wiki/requirements/assets/domain_rules.json`**：把
`C:\Users\xumax\AI Project\CTx_Converter\generation\domain_skills\section-router\references\domain_mapping.md`
中 ```json 代码块（从 `{` 到 `}`）**逐字复制**为本文件内容（19 个域：product-overview、
mechanical、electrical、display、ports-connectivity、power-battery、user-experience、
keyboard-input、cosmetics-quality、compliance-safety、repair-serviceability、
dfx-manufacturing、packaging-logistics、wireless-rf、audio-camera-sensors、software、
thermal）。每个域含 `keywords`（list[str]）与 `section_patterns`（list[str] 正则）。

**新建 `src/kb_extract/wiki/requirements/router.py`**：

```python
"""Deterministic section-to-domain router (ports CTx section-router rules).

No LLM. Same input -> same output. Section heading text is matched
case-insensitively against keyword lists; a leading section number
(e.g. "3.2.1") is matched against per-domain section_patterns.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

FALLBACK_DOMAIN = "base-extraction"

_RULES_PATH = Path(__file__).with_name("assets") / "domain_rules.json"
# Leading section number like "3", "3.2", "3.2.1" optionally followed by text.
_SECTION_NO_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\b")


@dataclass(frozen=True, slots=True)
class RouteResult:
    domain: str
    method: str  # "section_pattern" | "keyword" | "fallback"


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, dict[str, list[str]]]:
    raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    # Normalise: keep insertion order deterministic via sorted domain names.
    return {k: raw[k] for k in sorted(raw)}


def _section_number(title: str) -> str:
    m = _SECTION_NO_RE.match(title)
    return m.group(1) if m else ""


def route_heading(title: str) -> RouteResult:
    """Route a single section heading to a domain.

    Priority:
      1. section_patterns match (deterministic by sorted domain name)
      2. highest keyword hit count
      3. fallback to base-extraction
    """
    rules = _load_rules()
    sec_no = _section_number(title)
    lower = title.lower()

    if sec_no:
        for domain in sorted(rules):
            for pat in rules[domain].get("section_patterns", []):
                if re.search(pat, sec_no):
                    return RouteResult(domain=domain, method="section_pattern")

    best_domain = ""
    best_hits = 0
    for domain in sorted(rules):
        hits = sum(1 for kw in rules[domain].get("keywords", []) if kw.lower() in lower)
        if hits > best_hits:
            best_hits = hits
            best_domain = domain

    if best_hits > 0:
        return RouteResult(domain=best_domain, method="keyword")
    return RouteResult(domain=FALLBACK_DOMAIN, method="fallback")
```

**新建 `tests/test_requirements_router.py`**：

```python
from kb_extract.wiki.requirements.router import FALLBACK_DOMAIN, route_heading


def test_keyword_routes_mechanical():
    r = route_heading("Retractable Hinge Stiffness and Deflection")
    assert r.domain == "mechanical"
    assert r.method == "keyword"


def test_section_pattern_takes_priority():
    # "8." -> dfx-manufacturing via section_patterns even with generic words
    r = route_heading("8. Design for Excellence")
    assert r.domain == "dfx-manufacturing"
    assert r.method == "section_pattern"


def test_no_match_falls_back():
    r = route_heading("Acknowledgements and Greetings")
    assert r.domain == FALLBACK_DOMAIN
    assert r.method == "fallback"


def test_keyboard_input_keywords():
    r = route_heading("Touchpad force to fire and snap ratio")
    assert r.domain == "keyboard-input"


def test_deterministic_repeat():
    a = route_heading("Power Management and Battery Life")
    b = route_heading("Power Management and Battery Life")
    assert a == b
    assert a.domain == "power-battery"
```

**验收**：5 个测试通过；ruff 干净。
**提交**：`feat(wiki): add deterministic requirements domain router`

---

## Task 2：Prompt 组装（prompts.py + 资产）

**目标**：把 CTx 的系统/变体/用户模板移植为资产，提供 `compose_messages(...)` 生成
`list[Message]`（system = base + 域 SKILL + P1；user = 模板填入单 section 的证据 JSON）。

**逐字复制以下资产文件**（源 -> 目标）：
- `CTx.../prompts/base_system_rules.md` -> `assets/base_extraction.md`
- `CTx.../prompts/P1_variant_rules.md` -> `assets/p1_rules.md`
- `CTx.../prompts/P1_user_template.md` -> `assets/user_template.md`
- `CTx.../domain_skills/base-extraction/references/output_schema.json` -> `assets/output_schema.json`
- 对每个被路由用到的域（Task 1 的 19 个域 **加** `base-extraction`），把
  `CTx.../domain_skills/<domain>/SKILL.md` 复制为 `assets/domains/<domain>.md`。
  （即至少 20 个域文件；以路由表 domain 名为准，外加 `base-extraction.md`。）

> 注：`user_template.md` 含占位符 `{evidence_content}`。我们把单个 section 包装成
> 一个 JSON block 列表 `[{"id": <anchor>, ...}]` 填入，使 LLM 用 anchor 作为 EvidenceRef。

**新建 `src/kb_extract/wiki/requirements/prompts.py`**：

```python
"""Compose chat messages for requirement extraction from bundled assets."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..providers.base import Message
from .router import FALLBACK_DOMAIN

_ASSETS = Path(__file__).with_name("assets")
_SEP = "\n\n---\n\n"


@lru_cache(maxsize=None)
def _read_asset(rel: str) -> str:
    return (_ASSETS / rel).read_text(encoding="utf-8")


def _domain_skill(domain: str) -> str:
    path = _ASSETS / "domains" / f"{domain}.md"
    if not path.is_file():
        path = _ASSETS / "domains" / f"{FALLBACK_DOMAIN}.md"
    return path.read_text(encoding="utf-8")


def build_system_prompt(domain: str) -> str:
    return _SEP.join(
        [
            _read_asset("base_extraction.md").rstrip(),
            _domain_skill(domain).rstrip(),
            _read_asset("p1_rules.md").rstrip(),
        ]
    )


def _evidence_block(*, anchor: str, section_title: str, section_body: str) -> str:
    payload = [
        {
            "id": anchor,
            "type": "text",
            "section": section_title,
            "content": section_body,
        }
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_user_prompt(*, anchor: str, section_title: str, section_body: str) -> str:
    template = _read_asset("user_template.md")
    evidence = _evidence_block(
        anchor=anchor, section_title=section_title, section_body=section_body
    )
    return template.replace("{evidence_content}", evidence)


def compose_messages(
    *, domain: str, anchor: str, section_title: str, section_body: str
) -> list[Message]:
    return [
        {"role": "system", "content": build_system_prompt(domain)},
        {
            "role": "user",
            "content": build_user_prompt(
                anchor=anchor,
                section_title=section_title,
                section_body=section_body,
            ),
        ],
    ]
```

**新建 `tests/test_requirements_prompts.py`**：

```python
import json

from kb_extract.wiki.requirements.prompts import (
    build_system_prompt,
    compose_messages,
)


def test_system_prompt_includes_all_three_layers():
    sp = build_system_prompt("mechanical")
    assert "GROUNDED MODE" in sp  # from base_extraction.md
    assert "---" in sp            # separator between layers
    # P1 variant marker
    assert "Baseline" in sp or "P1" in sp


def test_unknown_domain_uses_fallback_skill():
    # Should not raise even if domain file is missing.
    sp = build_system_prompt("no-such-domain")
    assert sp.strip()


def test_compose_messages_embeds_anchor_as_evidence_id():
    msgs = compose_messages(
        domain="mechanical",
        anchor="sec-0007",
        section_title="3.2.1 Hinge Stiffness",
        section_body="Stiffness must be >= 5 N/mm.",
    )
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "sec-0007" in msgs[1]["content"]
    assert "Stiffness must be" in msgs[1]["content"]
    # evidence content must be valid JSON list embedded in the user prompt
    body = msgs[1]["content"]
    start = body.index("[")
    end = body.rindex("]") + 1
    blocks = json.loads(body[start:end])
    assert blocks[0]["id"] == "sec-0007"


def test_deterministic():
    a = compose_messages(domain="electrical", anchor="sec-0001",
                         section_title="Voltage", section_body="3.3V")
    b = compose_messages(domain="electrical", anchor="sec-0001",
                         section_title="Voltage", section_body="3.3V")
    assert a == b
```

**验收**：测试通过；ruff 干净。
**提交**：`feat(wiki): bundle extraction prompts and compose messages`

---

## Task 3：GitHub Models provider（github_models.py）

**目标**：实现 `LlmClient.chat` 的 OpenAI 兼容 GitHub Models 客户端，token 走环境变量，
**transport 可注入**以便离线测试，temperature=0。

**新建 `src/kb_extract/wiki/providers/github_models.py`**：

```python
"""GitHub Models LLM provider (OpenAI-compatible chat completions).

Network access is wrapped in an injectable ``transport`` callable so tests
never touch the socket. The default transport uses urllib (stdlib only) —
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
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
```

**新建 `tests/test_github_models_provider.py`**（注入 transport，零联网）：

```python
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
```

**验收**：测试通过且无 socket 报错；ruff 干净。
**提交**：`feat(wiki): add GitHub Models LLM provider with injectable transport`

---

## Task 4：抽取编排（models.py + extractor.py）

**目标**：遍历 `kb/<doc>/`，对每个 leaf section 路由 -> 读正文 -> 组 prompt ->
`llm.chat` -> 解析 JSON 列表 -> 校正成 `TestItem` 并**回填 EvidenceRef=anchor**。
单 section 失败不影响整体（容错计数）。支持 `dry_run`（只组 prompt 不解析）。

**新建 `src/kb_extract/wiki/requirements/models.py`**：

```python
"""TestItem model + tolerant LLM-JSON parsing/coercion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

DEFAULT_HOW = "Not explicitly defined"
DEFAULT_SAMPLE = "Not specified"
DEFAULT_DOC = "Not explicitly stated"

# Canonical output field order (matches CTx output_schema.json).
_FIELD_ORDER = (
    "Category",
    "Function",
    "What",
    "How",
    "Sample Size",
    "SourceDocument",
    "SourceSection",
    "EvidenceRef",
)


@dataclass(frozen=True, slots=True)
class TestItem:
    category: str
    function: str
    what: str
    how: str
    sample_size: str
    source_document: str
    source_section: str
    evidence_ref: str

    def to_dict(self) -> dict[str, str]:
        return {
            "Category": self.category,
            "Function": self.function,
            "What": self.what,
            "How": self.how,
            "Sample Size": self.sample_size,
            "SourceDocument": self.source_document,
            "SourceSection": self.source_section,
            "EvidenceRef": self.evidence_ref,
        }

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.evidence_ref, self.category, self.function, self.what)


def parse_items(raw: str) -> list[dict]:
    """Parse an LLM response into a list of dict items.

    Tolerant: strips ```json fences and surrounding prose. Raises
    ValueError if the payload is not a JSON list of objects.
    """
    text = raw.strip()
    text = _FENCE_RE.sub("", text).strip()
    # Fall back to extracting the outermost [...] if extra prose remains.
    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < 0 or end < start:
            raise ValueError("LLM response contains no JSON list")
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("LLM response is not a JSON list")
    return [obj for obj in data if isinstance(obj, dict)]


def coerce_item(
    obj: dict, *, anchor: str, section_title: str
) -> TestItem:
    """Build a TestItem, forcing EvidenceRef/SourceSection from real context."""

    def s(key: str, default: str = "") -> str:
        val = obj.get(key, default)
        return str(val).strip() if val is not None else default

    return TestItem(
        category=s("Category") or "Uncategorized",
        function=s("Function"),
        what=s("What"),
        how=s("How") or DEFAULT_HOW,
        sample_size=s("Sample Size") or DEFAULT_SAMPLE,
        source_document=s("SourceDocument") or DEFAULT_DOC,
        source_section=section_title or s("SourceSection"),
        evidence_ref=anchor,  # ALWAYS the real anchor; never trust LLM
    )
```

**新建 `src/kb_extract/wiki/requirements/extractor.py`**：

```python
"""Orchestrate requirement extraction over a kb/ tree (wiki layer)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ...layout import kb_dir as _kb_dir
from ..providers.base import LlmClient
from ..sections import read_section_body
from ..topics import EvidenceRef, _walk_index
from .models import TestItem, coerce_item, parse_items
from .prompts import compose_messages
from .router import route_heading


@dataclass(slots=True)
class RequirementsResult:
    items_by_doc: dict[str, list[TestItem]] = field(default_factory=dict)
    ok_sections: int = 0
    failed_sections: int = 0

    @property
    def docs(self) -> int:
        return len(self.items_by_doc)

    @property
    def total_items(self) -> int:
        return sum(len(v) for v in self.items_by_doc.values())


def _doc_evidence(kb_root: Path, doc_id: str) -> list[EvidenceRef]:
    index_file = kb_root / doc_id / "index.json"
    if not index_file.is_file():
        return []
    try:
        root = json.loads(index_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    collected: list[tuple[EvidenceRef, frozenset[str]]] = []
    _walk_index(root, doc_id, collected)
    return [ev for ev, _tokens in collected]


def extract_requirements(
    project_root: Path,
    llm: LlmClient,
    *,
    output_dir: Path | None = None,
    max_chars: int = 1500,
    dry_run: bool = False,
) -> RequirementsResult:
    """Route + prompt + extract requirements for every section under kb/.

    Per-section failures are isolated: a parse/LLM error increments
    ``failed_sections`` and processing continues. With ``dry_run=True`` the
    LLM is still called (to surface provider/cache issues) but the response
    is not parsed into items.
    """
    kb_root = _kb_dir(project_root, output_dir)
    result = RequirementsResult()
    if not kb_root.is_dir():
        return result

    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        items: list[TestItem] = []
        for ev in _doc_evidence(kb_root, doc_id):
            title = ev.section_title
            anchor = ev.anchor
            body = read_section_body(kb_root, doc_id, anchor, max_chars=max_chars)
            if not body:
                continue
            domain = route_heading(title).domain
            messages = compose_messages(
                domain=domain,
                anchor=anchor,
                section_title=title,
                section_body=body,
            )
            try:
                raw = llm.chat(messages)
                if dry_run:
                    result.ok_sections += 1
                    continue
                for obj in parse_items(raw):
                    items.append(coerce_item(obj, anchor=anchor, section_title=title))
                result.ok_sections += 1
            except Exception:  # noqa: BLE001 -- per-section fault tolerance
                result.failed_sections += 1
                continue
        if items:
            items.sort(key=lambda it: it.sort_key())
            result.items_by_doc[doc_id] = items
    return result
```

> 注：`_walk_index`/`EvidenceRef` 复用自 `..topics`；`read_section_body` 复用自
> `..sections`。`_kb_dir` 即 `kb_extract.layout.kb_dir`（注意 extractor 比 topics 深一层，
> 相对 import 为 `...layout`）。

**新建 `tests/test_requirements_extractor.py`**（用 MockLlmClient 与临时 kb/）：

```python
import json
from pathlib import Path

from kb_extract.wiki.requirements.extractor import extract_requirements
from kb_extract.wiki.requirements.models import parse_items, coerce_item


class _StubLlm:
    name = "stub"

    def __init__(self, response):
        self._response = response

    def chat(self, messages):
        return self._response


def _make_kb(tmp_path: Path) -> Path:
    doc = tmp_path / "kb" / "DOC1"
    doc.mkdir(parents=True)
    (doc / "main.md").write_text(
        '<a id="sec-0001"></a>\n# 3.2 Hinge Stiffness\n\n'
        "Stiffness must be >= 5 N/mm.\n",
        encoding="utf-8",
    )
    index = {
        "title": "root",
        "anchor": "",
        "children": [
            {"title": "3.2 Hinge Stiffness", "anchor": "sec-0001", "children": []}
        ],
    }
    (doc / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def test_parse_items_strips_fences():
    items = parse_items('```json\n[{"What": "x"}]\n```')
    assert items == [{"What": "x"}]


def test_coerce_forces_anchor():
    it = coerce_item({"What": "x", "EvidenceRef": "WRONG"},
                     anchor="sec-0009", section_title="T")
    assert it.evidence_ref == "sec-0009"
    assert it.source_section == "T"
    assert it.how == "Not explicitly defined"


def test_extract_happy_path(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm('[{"Category": "Mechanical", "What": "Stiffness >= 5 N/mm"}]')
    res = extract_requirements(root, llm)
    assert res.docs == 1
    items = res.items_by_doc["DOC1"]
    assert len(items) == 1
    assert items[0].evidence_ref == "sec-0001"
    assert res.failed_sections == 0


def test_extract_isolates_bad_json(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm("not json at all")
    res = extract_requirements(root, llm)
    assert res.failed_sections == 1
    assert res.total_items == 0


def test_dry_run_skips_parse(tmp_path):
    root = _make_kb(tmp_path)
    llm = _StubLlm("garbage")
    res = extract_requirements(root, llm, dry_run=True)
    assert res.ok_sections == 1
    assert res.total_items == 0
```

**验收**：测试通过；ruff 干净。
**提交**：`feat(wiki): add requirements extractor with anchor-stamped evidence`

---

## Task 5：渲染（render.py）

**目标**：把 `list[TestItem]` 渲染成 **字节可复现**的 `requirements.json` 与按 Category
分组、含 `main.md#anchor` 链接的 `requirements.md`，并写入 `kb/<doc>/`。

**新建 `src/kb_extract/wiki/requirements/render.py`**：

```python
"""Render extracted requirements to canonical JSON + grouped Markdown."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ...serialization import serialize_markdown
from .models import TestItem


def render_json(items: list[TestItem]) -> str:
    payload = [it.to_dict() for it in items]
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_markdown(doc_id: str, items: list[TestItem]) -> str:
    lines: list[str] = [f"# Requirements: {doc_id}", ""]
    if not items:
        lines.append("_No requirements extracted._")
        return serialize_markdown("\n".join(lines))

    by_cat: dict[str, list[TestItem]] = defaultdict(list)
    for it in items:
        by_cat[it.category].append(it)

    for cat in sorted(by_cat):
        lines.append(f"## {cat}")
        lines.append("")
        for it in by_cat[cat]:
            link = f"[{it.evidence_ref}](main.md#{it.evidence_ref})"
            lines.append(f"- **{it.function or 'Requirement'}** ({link})")
            lines.append(f"  - What: {it.what}")
            lines.append(f"  - How: {it.how}")
            lines.append(f"  - Sample Size: {it.sample_size}")
            lines.append(f"  - Source: {it.source_document} / {it.source_section}")
            lines.append("")
    return serialize_markdown("\n".join(lines))


def write_requirements(doc_dir: Path, doc_id: str, items: list[TestItem]) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "requirements.json").write_text(render_json(items), encoding="utf-8")
    (doc_dir / "requirements.md").write_text(
        render_markdown(doc_id, items), encoding="utf-8"
    )
```

> 确认 `serialize_markdown` 的签名：若它接受单一字符串参数并做 LF/BOM/末尾换行归一，
> 直接如上使用；若签名不同，实现者按 `src/kb_extract/serialization.py` 实际签名调整，
> 但**必须**经过它归一化（H13）。

**新建 `tests/test_requirements_render.py`**：

```python
from pathlib import Path

from kb_extract.wiki.requirements.models import TestItem
from kb_extract.wiki.requirements.render import (
    render_json,
    render_markdown,
    write_requirements,
)


def _item(**kw):
    base = dict(
        category="Mechanical", function="Force", what="Stiffness >= 5",
        how="Not explicitly defined", sample_size="Not specified",
        source_document="PRD", source_section="3.2", evidence_ref="sec-0001",
    )
    base.update(kw)
    return TestItem(**base)


def test_json_is_canonical_and_lf():
    out = render_json([_item()])
    assert out.endswith("}\n]\n") or out.endswith("\n")
    assert "\r" not in out
    assert '"EvidenceRef": "sec-0001"' in out


def test_markdown_has_anchor_link():
    md = render_markdown("DOC1", [_item()])
    assert "main.md#sec-0001" in md
    assert "\r" not in md


def test_byte_reproducible(tmp_path: Path):
    items = [_item(evidence_ref="sec-0002"), _item(evidence_ref="sec-0001")]
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    # render is order-sensitive: caller sorts; here verify same input same bytes
    items_sorted = sorted(items, key=lambda it: it.sort_key())
    write_requirements(d1, "DOC1", items_sorted)
    write_requirements(d2, "DOC1", items_sorted)
    assert (d1 / "requirements.json").read_bytes() == (d2 / "requirements.json").read_bytes()
    assert (d1 / "requirements.md").read_bytes() == (d2 / "requirements.md").read_bytes()


def test_empty_items_render():
    md = render_markdown("DOC1", [])
    assert "No requirements" in md
```

**验收**：测试通过；ruff 干净。
**提交**：`feat(wiki): render requirements to canonical json and grouped markdown`

---

## Task 6：CLI `kb wiki requirements` + 隔离守卫

**目标**：在已有 `wiki_group` 下新增 `requirements` 子命令，镜像 `wiki build` 的
provider 选项（mock|cached|github-models）；写出每个 doc 的产物；记录 history；
机器可解析摘要用英文。新增一条隔离守卫测试。

**在 `src/kb_extract/cli.py` 的 `wiki_group` 内新增命令**（参考 `wiki_build` 的 options
风格；放在 `wiki_verify` 之后即可）：

```python
@wiki_group.command(name="requirements")
@click.argument("path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--provider", type=click.Choice(["mock", "cached", "github-models"]),
              default="mock", show_default=True,
              help="LLM provider. mock=offline, cached=reproducible, github-models=real.")
@click.option("--responses-file", type=click.Path(path_type=Path), default=None,
              help="cached provider 的响应 JSON。")
@click.option("--model", default=None, help="github-models 模型名（如 openai/gpt-4o-mini）。")
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), default=None,
              help="从此目录读取 kb/，产物写回此目录的 kb/<doc>/。")
@click.option("--max-chars", type=int, default=1500, show_default=True,
              help="喂给 LLM 的单 section 正文上限。")
@click.option("--dry-run", is_flag=True, help="只跑 prompt，不写盘。")
@click.option("--json", "as_json", is_flag=True, help="以 JSON 打印摘要。")
def wiki_requirements(path, provider, responses_file, model, output_dir,
                      max_chars, dry_run, as_json):
    """从 PATH/kb/ 抽取工程需求，写出 requirements.json / requirements.md。"""
    from .layout import kb_dir as _kb_dir
    from .wiki.requirements.extractor import extract_requirements
    from .wiki.requirements.render import write_requirements

    if provider == "mock":
        from .wiki.providers.mock import MockLlmClient
        llm = MockLlmClient()
    elif provider == "cached":
        if responses_file is None:
            raise click.UsageError("--provider cached 需要 --responses-file")
        from .wiki.providers.cached import CachedLlmClient
        llm = CachedLlmClient(responses_path=responses_file)
    else:  # github-models
        from .wiki.providers.github_models import (
            GitHubModelsAuthError,
            GitHubModelsLlmClient,
        )
        try:
            llm = GitHubModelsLlmClient(model=model)
        except GitHubModelsAuthError as e:
            raise click.ClickException(str(e)) from e

    result = extract_requirements(
        path, llm, output_dir=output_dir, max_chars=max_chars, dry_run=dry_run
    )

    if not dry_run:
        kb_root = _kb_dir(path, output_dir)
        for doc_id, items in result.items_by_doc.items():
            write_requirements(kb_root / doc_id, doc_id, items)

    summary = {
        "docs": result.docs,
        "items": result.total_items,
        "ok_sections": result.ok_sections,
        "failed_sections": result.failed_sections,
    }
    if as_json:
        click.echo(json.dumps(summary, ensure_ascii=False))
    else:
        click.echo(
            f"wiki requirements: docs={summary['docs']} items={summary['items']} "
            f"ok={summary['ok_sections']} failed={summary['failed_sections']}"
        )
    _record_history(path, "wiki requirements", {
        "provider": provider, "dry_run": dry_run, **summary,
    }, 0, f"items={summary['items']}")
```

> 确认 `cli.py` 顶部已 `import json` 与 `from pathlib import Path`、`_record_history`
> 签名（见现有 `wiki_build` 调用）。若 `MockLlmClient()` 构造参数不同，按
> `wiki/providers/mock.py` 实际签名调整（mock 应能对任意 prompt 返回 `[]` 或可解析
> 的占位 JSON，使命令在离线下成功跑完）。

**关于 MockLlmClient**：现有 `MockLlmClient.chat` 返回的是 wiki 风格散文（带 `[^ev-N]`
pin），**不是** JSON 列表。因此在本命令下 mock 是「离线冒烟」provider：每个非空 section
会被 `parse_items` 判为解析失败，`failed_sections` 计数上升、`items=0`，命令仍 **exit 0**。
这是预期行为——mock 只用于离线跑通管线；要可复现产物用 `cached`，要真实抽取用
`github-models`。CLI 冒烟测试只断言 `exit_code == 0` 与摘要前缀，不要求 `items>0`。

**新增隔离守卫**——在 `tests/test_no_llm_imports.py` 追加一个测试，断言真实 HTTP 调用
（字面量 `chat/completions`）只出现在 `wiki/providers/github_models.py`：

```python
def test_chat_completions_only_in_github_models():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "kb_extract"
    offenders = []
    for p in src.rglob("*.py"):
        if p.name == "github_models.py":
            continue
        if "chat/completions" in p.read_text(encoding="utf-8"):
            offenders.append(str(p.relative_to(src)))
    assert not offenders, f"raw chat/completions outside github_models.py: {offenders}"
```

**新建 `tests/test_requirements_cli.py`**（CliRunner，离线）：

```python
import json
from pathlib import Path

from click.testing import CliRunner

from kb_extract.cli import main


def _make_project(tmp_path: Path) -> Path:
    doc = tmp_path / "kb" / "DOC1"
    doc.mkdir(parents=True)
    (doc / "main.md").write_text(
        '<a id="sec-0001"></a>\n# 3.2 Hinge\n\nStiffness >= 5 N/mm.\n',
        encoding="utf-8",
    )
    (doc / "index.json").write_text(
        json.dumps({"title": "r", "anchor": "", "children": [
            {"title": "3.2 Hinge", "anchor": "sec-0001", "children": []}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_requirements_mock_runs(tmp_path):
    proj = _make_project(tmp_path)
    res = CliRunner().invoke(main, ["wiki", "requirements", str(proj)])
    assert res.exit_code == 0, res.output
    assert "wiki requirements:" in res.output


def test_requirements_cached_uses_responses(tmp_path):
    proj = _make_project(tmp_path)
    # Build the exact prompt_hash the extractor will produce, then answer it.
    from kb_extract.wiki.requirements.prompts import compose_messages
    from kb_extract.wiki.providers.cached import prompt_hash
    from kb_extract.wiki.sections import read_section_body
    from kb_extract.wiki.requirements.router import route_heading

    body = read_section_body(proj / "kb", "DOC1", "sec-0001")
    domain = route_heading("3.2 Hinge").domain
    msgs = compose_messages(domain=domain, anchor="sec-0001",
                            section_title="3.2 Hinge", section_body=body)
    responses = {prompt_hash(msgs): '[{"Category":"Mechanical","What":"Stiffness >= 5"}]'}
    rf = tmp_path / "responses.json"
    rf.write_text(json.dumps(responses), encoding="utf-8")

    res = CliRunner().invoke(main, [
        "wiki", "requirements", str(proj),
        "--provider", "cached", "--responses-file", str(rf), "--json",
    ])
    assert res.exit_code == 0, res.output
    summary = json.loads(res.output.strip().splitlines()[-1])
    assert summary["items"] == 1
    out = json.loads((proj / "kb" / "DOC1" / "requirements.json").read_text())
    assert out[0]["EvidenceRef"] == "sec-0001"


def test_github_models_without_token_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_MODELS_TOKEN", raising=False)
    proj = _make_project(tmp_path)
    res = CliRunner().invoke(main, [
        "wiki", "requirements", str(proj), "--provider", "github-models",
    ])
    assert res.exit_code != 0
```

**验收**：全部测试通过；ruff 干净。
**提交**：`feat(cli): add kb wiki requirements command`

---

## Task 7：文档 + 版本

**目标**：用户可见文档（简体中文）说明新命令与数据外发风险；更新 CHANGELOG；版本
升到 `0.13.0`（pyproject + `__init__.py` + `uv.lock`）。

- **README**：新增「`kb wiki requirements`：领域路由 + 证据溯源的需求抽取」一节（简体
  中文），覆盖：用途、三种 provider（mock 离线冒烟默认、不产出 items / cached 可复现 /
  github-models 真实）、`GITHUB_TOKEN` 环境变量、产物位置 `kb/<doc>/requirements.{json,md}`、EvidenceRef 即
  `main.md#sec-NNNN` anchor、以及**数据外发提示**（github-models 会把 section 正文发送到
  GitHub Models API，机密文档请先评估）。
- **CHANGELOG.md**：新增 `## [0.13.0]` 段，列出本次新增（wiki requirements 命令、
  GitHub Models provider、领域路由与 prompt 资产移植）。注明若 SP-2 的 `0.12.0` 尚未合并，
  本条目在合并顺序上位于其后。
- **版本号**：`pyproject.toml` 与 `src/kb_extract/__init__.py` 改为 `0.13.0`；运行
  `uv lock` 更新 `uv.lock` 内的包版本。

**验收**：`uv run pytest` 全绿、`uv run ruff check .` 干净；README/CHANGELOG/版本一致。
**提交**：`docs: document kb wiki requirements and bump version to 0.13.0`

---

## 执行顺序与复审

按 Task 1 -> 7 顺序，单 implementer 串行。每个 task 完成后：
1. **spec 合规复审**（对照本计划与 spec，不多不少）。
2. **代码质量复审**。
两轮通过才进下一个 task。全部完成后做一次整体 final review，再走
`finishing-a-development-branch`（推分支、开 PR）。

模型建议：Task 1/2/3/5/7 为机械实现，用快模型；Task 4/6 涉及编排与 CLI 集成，用标准
模型。
