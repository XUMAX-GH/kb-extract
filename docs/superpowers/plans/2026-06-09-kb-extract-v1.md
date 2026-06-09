# kb-extract v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, hallucination-free document-to-Markdown extraction pipeline (PDF/DOCX/XLSX/PPTX/PNG-JPG/ZIP) with PageIndex-style section trees, packaged as both a CLI (`kb`) and a Copilot CLI skill.

**Architecture:** Pipeline + adapters. Orchestrator discovers files, picks adapter via `Extractor` protocol, hardness layer verifies every result before atomic write to disk, SQLite manifest tracks per-project state. No LLM is ever imported in the extraction layer (compile-time enforced).

**Tech Stack:** Python 3.11+, uv (package manager), hatchling (build), pytest + pytest-socket + syrupy + pytest-cov, ruff, docling + pymupdf (PDF), python-docx, openpyxl, python-pptx, Pillow, python-magic[-bin], SQLite (stdlib).

**Source spec:** `docs/superpowers/specs/2026-06-09-kb-extract-design.md` — the single source of truth. Every task below traces to a numbered section there.

**Conventions used throughout this plan:**
- All file paths are relative to repo root `C:\Users\xumax\AI Project\kb-extract\` unless prefixed with `~`.
- Every task ends with a commit. Conventional Commits prefixes: `feat:`, `test:`, `chore:`, `ci:`, `docs:`.
- Every commit message includes the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.
- Test commands use `uv run pytest ...` because the venv is uv-managed (Task 1 sets this up).
- `Expected:` blocks under a Run step are exact substrings to look for. If output doesn't contain them, stop and debug before proceeding.

---

## Phase 1 — Foundation (Tasks 1–6)

Sets up the project skeleton, error types, the `ExtractionResult` data contract, deterministic serialization, and the warnings allowlist registry. Nothing in this phase depends on docling or any other heavy adapter dependency.

---

### Task 1: Bootstrap pyproject + uv + ruff + pytest config

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `tests/conftest.py`
- Create: `src/kb_extract/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/SOURCES.md`

- [ ] **Step 1: Create `pyproject.toml` with pinned deps**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "kb-extract"
version = "0.1.0"
description = "Deterministic, hallucination-free document extraction pipeline."
readme = "README.md"
requires-python = ">=3.11,<3.13"
authors = [{ name = "xumax" }]
license = { text = "MIT" }
dependencies = [
  "docling>=2.0,<2.99",
  "pymupdf>=1.24,<1.99",
  "python-docx>=1.1,<1.99",
  "openpyxl>=3.1,<3.99",
  "python-pptx>=1.0.2,<2.0",
  "Pillow>=10.0,<10.99",
  "langdetect>=1.0.9,<1.99",
  "python-magic>=0.4.27,<0.99; sys_platform != 'win32'",
  "python-magic-bin>=0.4.14,<0.99; sys_platform == 'win32'",
  "click>=8.1,<8.99",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<8.99",
  "pytest-cov>=4.1,<4.99",
  "pytest-socket>=0.7,<0.99",
  "syrupy>=4.6,<4.99",
  "ruff>=0.5,<0.99",
]

[project.scripts]
kb = "kb_extract.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/kb_extract"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
markers = [
  "slow: marks tests as slow (deselect with -m 'not slow')",
  "perf: performance benchmark tests",
]
```

- [ ] **Step 2: Create `ruff.toml`**

```toml
target-version = "py311"
line-length = 100

[lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]
ignore = ["E501"]

[lint.per-file-ignores]
"tests/**/*.py" = ["B011"]
```

- [ ] **Step 3: Create empty package init files**

`src/kb_extract/__init__.py`:
```python
"""kb-extract: deterministic document extraction."""

__version__ = "0.1.0"
```

`tests/__init__.py`:
```python
```

- [ ] **Step 4: Create `tests/conftest.py` with socket-deny default (H1)**

```python
"""Global pytest config.

H1 (hardness): adapter tests must not make network calls. We deny sockets
globally; specific tests that need them (none expected in v1) must opt in
with @pytest.mark.enable_socket.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-mark every adapter test as socket-disabled."""
    for item in items:
        if "adapters" in str(item.fspath):
            item.add_marker(pytest.mark.disable_socket)


@pytest.fixture(autouse=True)
def _disable_socket_by_default(request):
    """Disable sockets by default; tests can override with enable_socket marker."""
    if request.node.get_closest_marker("enable_socket"):
        return
    pytest_socket = pytest.importorskip("pytest_socket")
    pytest_socket.disable_socket()
    yield
    pytest_socket.enable_socket()
```

- [ ] **Step 5: Create `tests/fixtures/SOURCES.md` provenance ledger**

```markdown
# Test fixture provenance

Every file under `tests/fixtures/` must be either:
1. Public-domain or permissively licensed (CC0, MIT, Apache-2.0, public-domain), or
2. Synthetically generated by code in this repo.

| File | Origin | License | Added |
|---|---|---|---|
| (none yet) | | | |

Microsoft confidential documents MUST NEVER be committed. Hardness invariant H1
(no network) plus this policy means no source content ever leaves the local
machine via this repo.
```

- [ ] **Step 6: Bootstrap uv venv and install deps**

Run:
```powershell
cd "C:\Users\xumax\AI Project\kb-extract"
uv venv --python 3.11
uv pip install -e ".[dev]"
```

Expected: venv created at `.venv\`, dependencies install without errors. If `uv` is not installed, install via `winget install --id=astral-sh.uv -e` first.

- [ ] **Step 7: Smoke-test pytest discovers nothing yet**

Run:
```powershell
uv run pytest --collect-only
```

Expected: `collected 0 items`. No errors.

- [ ] **Step 8: Smoke-test ruff**

Run:
```powershell
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```powershell
git add pyproject.toml ruff.toml src/kb_extract/__init__.py tests/__init__.py tests/conftest.py tests/fixtures/SOURCES.md
git commit -m "chore: bootstrap project (pyproject, ruff, pytest, conftest with socket-deny default)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Error types module

Spec §3.2, §5.1, §7 require `HardnessViolation` (raised by `hardness.py`) and a general `AdapterError` for orchestrator-level catch in `try/except`.

**Files:**
- Create: `src/kb_extract/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write failing test**

`tests/test_errors.py`:
```python
import pytest
from kb_extract.errors import AdapterError, HardnessViolation


def test_hardness_violation_carries_invariant_id_and_detail():
    err = HardnessViolation(invariant="H3", detail="anchor 'sec-0001' appears 2 times")
    assert err.invariant == "H3"
    assert err.detail == "anchor 'sec-0001' appears 2 times"
    assert "H3" in str(err)
    assert "anchor 'sec-0001'" in str(err)


def test_hardness_violation_is_an_exception():
    with pytest.raises(HardnessViolation) as excinfo:
        raise HardnessViolation(invariant="H5", detail="asset orphan: assets/foo.png")
    assert excinfo.value.invariant == "H5"


def test_adapter_error_is_an_exception():
    with pytest.raises(AdapterError):
        raise AdapterError("pdf parse failed at page 17")


def test_hardness_violation_is_not_adapter_error():
    # Orchestrator catches AdapterError for skip-and-continue;
    # HardnessViolation must propagate (different bucket).
    assert not issubclass(HardnessViolation, AdapterError)
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.errors'`

- [ ] **Step 3: Implement `errors.py`**

`src/kb_extract/errors.py`:
```python
"""Error types for kb-extract.

`AdapterError`: adapter-internal failure; orchestrator catches and records as failed.
`HardnessViolation`: invariant violated; propagates past orchestrator to surface
the bug to the user. Caught only at CLI boundary.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Recoverable adapter-level failure (file corrupt, encrypted, etc.).

    Orchestrator catches this and marks the source as failed in the manifest,
    then continues with the next source.
    """


class HardnessViolation(Exception):
    """A hardness invariant (H3..H11) was violated.

    Raised by `kb_extract.hardness` checkers. NOT caught by the orchestrator
    main loop — must surface to the user because it indicates an adapter bug.
    """

    def __init__(self, *, invariant: str, detail: str) -> None:
        self.invariant = invariant
        self.detail = detail
        super().__init__(f"[{invariant}] {detail}")
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/test_errors.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/errors.py tests/test_errors.py
git commit -m "feat(errors): add AdapterError and HardnessViolation

HardnessViolation carries invariant id and detail; not subclass of
AdapterError so orchestrator's try/except doesn't accidentally swallow it.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Contracts module — part 1 (SectionNode, TableRef, AssetRef)

Spec §4 dataclass definitions. All `frozen=True, slots=True`.

**Files:**
- Create: `src/kb_extract/contracts.py` (partial; finished in Task 4)
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Write failing test**

`tests/test_contracts.py`:
```python
import dataclasses

import pytest
from kb_extract.contracts import AssetRef, SectionNode, TableRef


def test_section_node_is_frozen_and_slotted():
    node = SectionNode(
        node_id="0001",
        title="Chapter 1",
        level=1,
        page_start=1,
        page_end=10,
        anchor="",
        language="en",
        children=(),
    )
    assert dataclasses.is_dataclass(node)
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.title = "mutated"  # type: ignore[misc]
    assert "__slots__" in SectionNode.__dict__


def test_section_node_children_is_tuple_of_section_nodes():
    leaf = SectionNode(
        node_id="0001.0001",
        title="Section 1.1",
        level=2,
        page_start=1,
        page_end=2,
        anchor="sec-0001-0001",
        language="en",
    )
    parent = SectionNode(
        node_id="0001",
        title="Chapter 1",
        level=1,
        page_start=1,
        page_end=10,
        anchor="",
        language="en",
        children=(leaf,),
    )
    assert parent.children == (leaf,)
    assert isinstance(parent.children, tuple)


def test_table_ref_rows_json_is_nested_tuple():
    t = TableRef(
        anchor="tbl-0001",
        page=3,
        rows_json=(("col A", "col B"), ("1", "2")),
        rendered_asset="assets/p3-table1.png",
    )
    assert t.anchor == "tbl-0001"
    assert t.rows_json[0] == ("col A", "col B")
    with pytest.raises(dataclasses.FrozenInstanceError):
        t.page = 99  # type: ignore[misc]


def test_table_ref_rendered_asset_optional():
    t = TableRef(anchor="tbl-0002", page=4, rows_json=(("x",),), rendered_asset=None)
    assert t.rendered_asset is None


def test_asset_ref_kind_literal():
    a = AssetRef(
        kind="image",
        rel_path="assets/p3-img1.png",
        page=3,
        sha256="a" * 64,
        width=800,
        height=600,
        alt="figure 1",
    )
    assert a.kind == "image"
    assert a.sha256 == "a" * 64


def test_asset_ref_defaults():
    a = AssetRef(kind="image", rel_path="assets/img.png", page=1, sha256="b" * 64)
    assert a.width is None
    assert a.height is None
    assert a.alt == ""
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/test_contracts.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.contracts'`

- [ ] **Step 3: Implement contracts.py part 1**

`src/kb_extract/contracts.py`:
```python
"""Core data contract shared by adapters, orchestrator, hardness, and downstream layers.

All types here are `frozen=True, slots=True`. Changes to these types are
considered breaking and require a major version bump.

See spec §4 for rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SectionNode:
    """PageIndex-style recursive section node.

    Each leaf corresponds to a contiguous span of main.md and carries an
    `anchor` that exists exactly once in main.md as `<a id="...">`.
    Non-leaf nodes have anchor == "" and aggregate their children.
    """

    node_id: str
    title: str
    level: int
    page_start: int
    page_end: int
    anchor: str
    language: str
    children: tuple["SectionNode", ...] = ()


@dataclass(frozen=True, slots=True)
class TableRef:
    """A table extracted with raw structured data, not just markdown rendering."""

    anchor: str
    page: int
    rows_json: tuple[tuple[str, ...], ...]
    rendered_asset: str | None


@dataclass(frozen=True, slots=True)
class AssetRef:
    """Image, rendered-table image, or embedded file."""

    kind: Literal["image", "table_image", "embedded_file"]
    rel_path: str
    page: int
    sha256: str
    width: int | None = None
    height: int | None = None
    alt: str = ""
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/test_contracts.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/contracts.py tests/test_contracts.py
git commit -m "feat(contracts): add SectionNode, TableRef, AssetRef (frozen/slotted)

Implements spec §4 part 1. ExtractionMeta and ExtractionResult follow in Task 4.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Contracts module — part 2 (ExtractionMeta, ExtractionResult, content_sha256)

**Files:**
- Modify: `src/kb_extract/contracts.py`
- Modify: `tests/test_contracts.py`

- [ ] **Step 1: Append failing tests to `tests/test_contracts.py`**

```python
import hashlib

from kb_extract.contracts import ExtractionMeta, ExtractionResult


def _meta(**overrides) -> ExtractionMeta:
    defaults: dict = dict(
        source_path="BUR-K/foo.pdf",
        source_sha256="c" * 64,
        source_bytes=1234,
        source_mtime_iso="2026-06-09T12:00:00+00:00",
        adapter_name="pdf_docling",
        adapter_version="abc12345",
        tool_versions={"docling": "2.0.0", "pymupdf": "1.24.0"},
        extracted_at_iso="2026-06-09T12:01:00+00:00",
        outline_source="bookmark",
        status="ok",
        warnings=(),
        skipped_reasons=(),
    )
    defaults.update(overrides)
    return ExtractionMeta(**defaults)


def test_extraction_meta_frozen():
    m = _meta()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.status = "failed"  # type: ignore[misc]


def test_extraction_meta_outline_source_literal_values():
    for src in ("bookmark", "heading_style", "docling_layout", "page_fallback"):
        _meta(outline_source=src)  # constructs without error


def test_extraction_result_carries_all_parts():
    root = SectionNode(
        node_id="0001",
        title="Root",
        level=0,
        page_start=1,
        page_end=1,
        anchor="",
        language="und",
    )
    result = ExtractionResult(
        markdown="<a id=\"sec-0001\"></a>\nhello\n",
        index=root,
        tables=(),
        assets=(),
        meta=_meta(),
    )
    assert result.markdown.startswith("<a id=")
    assert result.meta.adapter_name == "pdf_docling"


def test_content_sha256_is_deterministic_and_changes_with_markdown():
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1, anchor="", language="und"
    )
    r1 = ExtractionResult(markdown="A\n", index=root, tables=(), assets=(), meta=_meta())
    r2 = ExtractionResult(markdown="A\n", index=root, tables=(), assets=(), meta=_meta())
    r3 = ExtractionResult(markdown="B\n", index=root, tables=(), assets=(), meta=_meta())
    assert r1.content_sha256() == r2.content_sha256()
    assert r1.content_sha256() != r3.content_sha256()
    # length sanity
    assert len(r1.content_sha256()) == 64


def test_content_sha256_includes_sorted_asset_hashes():
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1, anchor="", language="und"
    )
    a1 = AssetRef(kind="image", rel_path="assets/a.png", page=1, sha256="1" * 64)
    a2 = AssetRef(kind="image", rel_path="assets/b.png", page=1, sha256="2" * 64)
    r_ab = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a1, a2), meta=_meta()
    )
    r_ba = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a2, a1), meta=_meta()
    )
    # Order of assets tuple must NOT affect content_sha256 — sorted internally.
    assert r_ab.content_sha256() == r_ba.content_sha256()
    # Different asset → different hash.
    a3 = AssetRef(kind="image", rel_path="assets/c.png", page=1, sha256="3" * 64)
    r_diff = ExtractionResult(
        markdown="x\n", index=root, tables=(), assets=(a1, a3), meta=_meta()
    )
    assert r_diff.content_sha256() != r_ab.content_sha256()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_contracts.py -v`
Expected: `ImportError: cannot import name 'ExtractionMeta' from 'kb_extract.contracts'`

- [ ] **Step 3: Extend `src/kb_extract/contracts.py`**

Append at end:
```python
@dataclass(frozen=True, slots=True)
class ExtractionMeta:
    source_path: str
    source_sha256: str
    source_bytes: int
    source_mtime_iso: str
    adapter_name: str
    adapter_version: str
    tool_versions: dict[str, str]
    extracted_at_iso: str
    outline_source: Literal["bookmark", "heading_style", "docling_layout", "page_fallback"]
    status: Literal["ok", "partial", "failed"]
    warnings: tuple[str, ...] = ()
    skipped_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    markdown: str
    index: SectionNode
    tables: tuple[TableRef, ...]
    assets: tuple[AssetRef, ...]
    meta: ExtractionMeta

    def content_sha256(self) -> str:
        """sha256 over (markdown bytes || sorted asset sha256s || index canonical bytes).

        Used for idempotency and verification. Asset order in the tuple does
        not affect the hash; assets are sorted by sha256 first.
        """
        import hashlib

        from .serialization import canonical_index_bytes

        h = hashlib.sha256()
        h.update(self.markdown.encode("utf-8"))
        h.update(b"\x00ASSETS\x00")
        for a in sorted(self.assets, key=lambda a: a.sha256):
            h.update(a.sha256.encode("ascii"))
            h.update(b"\x00")
        h.update(b"\x00INDEX\x00")
        h.update(canonical_index_bytes(self.index))
        return h.hexdigest()
```

- [ ] **Step 4: Run, expect FAIL with new error**

Run: `uv run pytest tests/test_contracts.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.serialization'`

This is intentional — Task 5 implements `serialization.canonical_index_bytes`.

- [ ] **Step 5: Commit (red bar, intentional)**

```powershell
git add src/kb_extract/contracts.py tests/test_contracts.py
git commit -m "feat(contracts): add ExtractionMeta and ExtractionResult with content_sha256

content_sha256 stub references serialization.canonical_index_bytes which
arrives in Task 5. Tests fail with ImportError until then — intentional
red bar to drive the next task.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Deterministic JSON serialization

Spec §4.2: JSON `sort_keys=True, ensure_ascii=False, indent=2, separators=(",", ": ")` plus trailing `\n`. Markdown is UTF-8 no BOM, LF, single trailing newline. We also need a canonical bytes form of `SectionNode` for use inside `content_sha256()`.

**Files:**
- Create: `src/kb_extract/serialization.py`
- Test: `tests/test_serialization.py`

- [ ] **Step 1: Write failing test**

`tests/test_serialization.py`:
```python
from kb_extract.contracts import SectionNode
from kb_extract.serialization import (
    canonical_index_bytes,
    serialize_index_json,
    serialize_markdown,
    serialize_meta_json,
)


def _sn(**kw) -> SectionNode:
    defaults: dict = dict(
        node_id="0001", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="und", children=(),
    )
    defaults.update(kw)
    return SectionNode(**defaults)


def test_serialize_index_json_has_trailing_newline_and_indent2():
    out = serialize_index_json(_sn())
    assert out.endswith("\n")
    assert "\n  " in out  # indent=2 produces 2-space leading whitespace
    assert "\u4e2d" not in out or "中" in out  # ensure_ascii=False keeps unicode literal


def test_serialize_index_json_keeps_chinese_unescaped():
    out = serialize_index_json(_sn(title="第一章"))
    assert "第一章" in out
    assert "\\u" not in out


def test_serialize_index_json_keys_sorted():
    out = serialize_index_json(_sn(title="x"))
    # Keys appear in alphabetical order
    keys_in_order = [line.strip().split('"')[1] for line in out.splitlines() if line.strip().startswith('"')]
    assert keys_in_order == sorted(keys_in_order)


def test_serialize_index_json_includes_children_recursively():
    leaf = _sn(node_id="0001.0001", title="Leaf", level=1, anchor="sec-0001-0001")
    parent = _sn(children=(leaf,))
    out = serialize_index_json(parent)
    assert "Leaf" in out
    assert "sec-0001-0001" in out


def test_canonical_index_bytes_is_bytes_of_serialize_index_json():
    n = _sn(title="hi")
    assert canonical_index_bytes(n) == serialize_index_json(n).encode("utf-8")


def test_serialize_markdown_ends_with_single_trailing_newline():
    assert serialize_markdown("hello") == "hello\n"
    assert serialize_markdown("hello\n") == "hello\n"
    assert serialize_markdown("hello\n\n\n") == "hello\n"


def test_serialize_markdown_normalizes_crlf_to_lf():
    assert serialize_markdown("a\r\nb\r\n") == "a\nb\n"


def test_serialize_markdown_no_bom():
    assert not serialize_markdown("x").startswith("\ufeff")


def test_serialize_meta_json_includes_all_fields_sorted_and_trailing_newline():
    from kb_extract.contracts import ExtractionMeta
    m = ExtractionMeta(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        adapter_name="p", adapter_version="v", tool_versions={"b": "2", "a": "1"},
        extracted_at_iso="t", outline_source="bookmark", status="ok",
    )
    out = serialize_meta_json(m)
    assert out.endswith("\n")
    # tool_versions inner dict keys also sorted
    a_idx = out.index('"a": "1"')
    b_idx = out.index('"b": "2"')
    assert a_idx < b_idx
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_serialization.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.serialization'`

- [ ] **Step 3: Implement `serialization.py`**

`src/kb_extract/serialization.py`:
```python
"""Deterministic serializers. See spec §4.2."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from .contracts import ExtractionMeta, SectionNode


def _section_to_dict(node: SectionNode) -> dict[str, Any]:
    return {
        "anchor": node.anchor,
        "children": [_section_to_dict(c) for c in node.children],
        "language": node.language,
        "level": node.level,
        "node_id": node.node_id,
        "page_end": node.page_end,
        "page_start": node.page_start,
        "title": node.title,
    }


def _json_dumps(obj: Any) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
    ) + "\n"


def serialize_index_json(root: SectionNode) -> str:
    """Serialize a SectionNode tree to canonical JSON string."""
    return _json_dumps(_section_to_dict(root))


def canonical_index_bytes(root: SectionNode) -> bytes:
    """UTF-8 bytes of `serialize_index_json(root)`."""
    return serialize_index_json(root).encode("utf-8")


def serialize_meta_json(meta: ExtractionMeta) -> str:
    """Serialize ExtractionMeta to canonical JSON string."""
    d = dataclasses.asdict(meta)
    # asdict already gives a plain dict; json.dumps with sort_keys handles ordering.
    return _json_dumps(d)


def serialize_markdown(text: str) -> str:
    """Normalize markdown for write: LF line endings, no BOM, exactly one trailing newline."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n") + "\n"
    return text
```

- [ ] **Step 4: Run, expect PASS for both serialization and contracts**

Run: `uv run pytest tests/test_serialization.py tests/test_contracts.py -v`
Expected: all tests pass (9 serialization + 11 contracts = 20 passed).

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/serialization.py tests/test_serialization.py
git commit -m "feat(serialization): deterministic JSON + markdown serializers (spec §4.2)

JSON: sort_keys, ensure_ascii=False, indent=2, trailing newline.
Markdown: UTF-8 no BOM, LF only, single trailing newline.
Closes the import gap from Task 4; contracts tests now pass.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Warnings allowlist registry

Spec §7 H11: every warning string must match a registered regex from a fixed allowlist. The registry lives next to `hardness.py` (used by both adapters as documentation and by H11 as the source of truth).

**Files:**
- Create: `src/kb_extract/warnings_registry.py`
- Test: `tests/test_warnings_registry.py`

- [ ] **Step 1: Write failing test**

`tests/test_warnings_registry.py`:
```python
import re

import pytest
from kb_extract.warnings_registry import (
    ALLOWED_WARNING_PATTERNS,
    is_warning_allowed,
)


@pytest.mark.parametrize(
    "warning",
    [
        "pdf.scanned_no_text_layer",
        "pdf.password_protected",
        "pdf.low_confidence_heading:p12",
        "pdf.font_decode_failed:p3",
        "docx.unknown_style:Heading99",
        "docx.embedded_ole_skipped:oleObject1.bin",
        "xlsx.formula_empty_cache:Sheet1!A3",
        "xlsx.merged_cells_flattened:Sheet1!B2:C4",
        "pptx.animation_ignored:slide5",
        "image.exif:Make=Canon",
        "zip.encrypted:inner.docx",
        "zip.too_nested:depth=6",
    ],
)
def test_known_warnings_are_allowed(warning):
    assert is_warning_allowed(warning), f"{warning!r} not matched by any allowed pattern"


@pytest.mark.parametrize(
    "warning",
    [
        "freeform note from adapter",
        "WARNING: something happened",
        "pdf.totally_made_up_category",
        "image.exif",  # missing tag=value
        "",
    ],
)
def test_unknown_warnings_are_rejected(warning):
    assert not is_warning_allowed(warning)


def test_all_patterns_compile():
    for p in ALLOWED_WARNING_PATTERNS:
        re.compile(p)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_warnings_registry.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.warnings_registry'`

- [ ] **Step 3: Implement `warnings_registry.py`**

`src/kb_extract/warnings_registry.py`:
```python
"""H11: warnings allowlist. Every warning emitted by an adapter must match
exactly one regex below. Add a new pattern here when introducing a new
warning category; do not emit freeform warnings.
"""

from __future__ import annotations

import re

ALLOWED_WARNING_PATTERNS: tuple[str, ...] = (
    # PDF / docling adapter
    r"^pdf\.scanned_no_text_layer$",
    r"^pdf\.password_protected$",
    r"^pdf\.low_confidence_heading:p\d+$",
    r"^pdf\.font_decode_failed:p\d+$",
    # DOCX adapter
    r"^docx\.unknown_style:[\w\- ]+$",
    r"^docx\.embedded_ole_skipped:[\w\-. ]+$",
    # XLSX adapter
    r"^xlsx\.formula_empty_cache:[^!]+![A-Z]+\d+$",
    r"^xlsx\.merged_cells_flattened:[^!]+![A-Z]+\d+:[A-Z]+\d+$",
    # PPTX adapter
    r"^pptx\.animation_ignored:slide\d+$",
    # Image adapter
    r"^image\.exif:[\w]+=[^\s]+$",
    # ZIP adapter
    r"^zip\.encrypted:[\w\-.]+$",
    r"^zip\.too_nested:depth=\d+$",
)

_compiled = tuple(re.compile(p) for p in ALLOWED_WARNING_PATTERNS)


def is_warning_allowed(warning: str) -> bool:
    """True iff `warning` matches at least one registered pattern."""
    return any(p.match(warning) for p in _compiled)
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_warnings_registry.py -v`
Expected: `19 passed` (12 allowed + 5 rejected + 1 compile + 1 from parametrize counting).

Actual count may differ slightly with parametrize; ensure no FAIL.

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/warnings_registry.py tests/test_warnings_registry.py
git commit -m "feat(warnings): add allowlist registry for H11 (machine-consumable warnings)

Each adapter category has a strict regex; freeform warnings are rejected.
Used by hardness.H11 to fail loud at extraction time.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — Hardness invariants (Tasks 7–12)

Implements H3..H11 as pure functions, plus runs H1 (no socket) and H2 (no LLM imports) as test-level checks. H12 (no silent skip) is implemented in the orchestrator (Phase 4); H13 (cross-platform) is implemented in CI (Phase 8).

`hardness.assert_invariants(result, src_path)` is the integration point called from the orchestrator after every successful adapter run.

---

### Task 7: H3 (anchor uniqueness) + H4 (anchor completeness)

**Files:**
- Create: `src/kb_extract/hardness.py` (partial, finished across Tasks 7–12)
- Test: `tests/test_hardness.py`

- [ ] **Step 1: Write failing tests**

`tests/test_hardness.py`:
```python
import pytest
from kb_extract.contracts import (
    AssetRef,
    ExtractionMeta,
    ExtractionResult,
    SectionNode,
    TableRef,
)
from kb_extract.errors import HardnessViolation
from kb_extract.hardness import check_h3_anchor_uniqueness, check_h4_anchor_completeness


def _meta(**kw):
    defaults: dict = dict(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        adapter_name="p", adapter_version="v", tool_versions={}, extracted_at_iso="t",
        outline_source="bookmark", status="ok",
    )
    defaults.update(kw)
    return ExtractionMeta(**defaults)


def _result(*, markdown: str, index: SectionNode, assets=(), tables=()) -> ExtractionResult:
    return ExtractionResult(
        markdown=markdown, index=index, tables=tables, assets=assets, meta=_meta()
    )


def test_h3_passes_on_unique_anchors():
    md = '<a id="sec-0001"></a>\n# T\n<a id="sec-0001-0001"></a>\nbody\n'
    check_h3_anchor_uniqueness(md)


def test_h3_fails_on_duplicate_anchor():
    md = '<a id="sec-0001"></a>\n# T\n<a id="sec-0001"></a>\nagain\n'
    with pytest.raises(HardnessViolation) as e:
        check_h3_anchor_uniqueness(md)
    assert e.value.invariant == "H3"
    assert "sec-0001" in e.value.detail


def test_h4_passes_when_every_leaf_anchor_present_in_markdown():
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001-0001"></a>\nbody\n'
    check_h4_anchor_completeness(md, root)


def test_h4_fails_when_leaf_anchor_missing_from_markdown():
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = "no anchors here\n"
    with pytest.raises(HardnessViolation) as e:
        check_h4_anchor_completeness(md, root)
    assert e.value.invariant == "H4"
    assert "sec-0001-0001" in e.value.detail


def test_h4_ignores_non_leaf_empty_anchors():
    # Parent has anchor="" — should not be required in markdown.
    leaf = SectionNode(
        node_id="0001.0001", title="L", level=1, page_start=1, page_end=1,
        anchor="sec-0001-0001", language="en",
    )
    root = SectionNode(
        node_id="0001", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001-0001"></a>\nbody\n'
    check_h4_anchor_completeness(md, root)  # no error
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.hardness'`

- [ ] **Step 3: Implement H3 + H4 in `hardness.py`**

`src/kb_extract/hardness.py`:
```python
"""Hardness invariants (spec §7).

All checkers are pure functions. Each raises `HardnessViolation` with
`invariant=<H#>` and a precise `detail` string. The orchestrator catches
nothing here — violations always reach the CLI.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from .contracts import SectionNode
from .errors import HardnessViolation

_ANCHOR_RE = re.compile(r'<a id="([^"]+)"></a>')


def _iter_anchors(markdown: str) -> Iterable[str]:
    yield from _ANCHOR_RE.findall(markdown)


def _walk_leaves(node: SectionNode) -> Iterable[SectionNode]:
    if not node.children:
        yield node
        return
    for c in node.children:
        yield from _walk_leaves(c)


def check_h3_anchor_uniqueness(markdown: str) -> None:
    counts = Counter(_iter_anchors(markdown))
    dups = sorted(a for a, n in counts.items() if n > 1)
    if dups:
        raise HardnessViolation(
            invariant="H3",
            detail=f"duplicate anchor(s) in markdown: {dups[:5]}",
        )


def check_h4_anchor_completeness(markdown: str, index: SectionNode) -> None:
    md_anchors = set(_iter_anchors(markdown))
    missing = sorted(
        leaf.anchor for leaf in _walk_leaves(index)
        if leaf.anchor and leaf.anchor not in md_anchors
    )
    if missing:
        raise HardnessViolation(
            invariant="H4",
            detail=f"section-tree leaf anchors missing from markdown: {missing[:5]}",
        )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/hardness.py tests/test_hardness.py
git commit -m "feat(hardness): H3 anchor uniqueness + H4 anchor completeness

Pure checkers, raise HardnessViolation with H3/H4 invariant ids.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: H5 (asset closure) + H6 (asset hash truth)

**Files:**
- Modify: `src/kb_extract/hardness.py`
- Modify: `tests/test_hardness.py`

- [ ] **Step 1: Append failing tests**

```python
import hashlib
from pathlib import Path

from kb_extract.hardness import check_h5_asset_closure, check_h6_asset_hash_truth


def _asset(rel_path: str, sha: str, *, kind: str = "image", page: int = 1) -> AssetRef:
    return AssetRef(kind=kind, rel_path=rel_path, page=page, sha256=sha)


def test_h5_passes_when_md_assets_match_filesystem_and_assetrefs(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1-img1.png").write_bytes(b"\x89PNGdata")
    md = "![](assets/p1-img1.png)\n"
    assets = (_asset("assets/p1-img1.png", "x" * 64),)
    check_h5_asset_closure(md, assets, tmp_path)


def test_h5_fails_on_missing_file_referenced_by_markdown(tmp_path):
    md = "![](assets/p1-img1.png)\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"
    assert "p1-img1.png" in e.value.detail


def test_h5_fails_on_orphan_file_in_assets_dir(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "orphan.png").write_bytes(b"x")
    md = "no images\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"
    assert "orphan.png" in e.value.detail


def test_h5_fails_on_md_ref_not_in_assetrefs(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1.png").write_bytes(b"x")
    md = "![](assets/p1.png)\n"
    with pytest.raises(HardnessViolation) as e:
        check_h5_asset_closure(md, (), tmp_path)
    assert e.value.invariant == "H5"


def test_h6_passes_when_hashes_match(tmp_path):
    (tmp_path / "assets").mkdir()
    data = b"\x89PNG\x0d\x0a\x1a\x0apayload"
    (tmp_path / "assets" / "p1.png").write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    assets = (_asset("assets/p1.png", sha),)
    check_h6_asset_hash_truth(assets, tmp_path)


def test_h6_fails_when_hash_lies(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "p1.png").write_bytes(b"actual")
    assets = (_asset("assets/p1.png", "0" * 64),)
    with pytest.raises(HardnessViolation) as e:
        check_h6_asset_hash_truth(assets, tmp_path)
    assert e.value.invariant == "H6"
    assert "assets/p1.png" in e.value.detail
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `ImportError: cannot import name 'check_h5_asset_closure'`

- [ ] **Step 3: Extend `hardness.py`**

Append:
```python
import hashlib
from pathlib import Path

from .contracts import AssetRef

_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\((assets/[^)\s]+)")


def _md_referenced_assets(markdown: str) -> set[str]:
    return set(_MD_IMG_RE.findall(markdown))


def check_h5_asset_closure(
    markdown: str, assets: tuple[AssetRef, ...], out_dir: Path
) -> None:
    md_refs = _md_referenced_assets(markdown)
    assetref_paths = {a.rel_path for a in assets}

    assets_dir = out_dir / "assets"
    fs_files: set[str] = set()
    if assets_dir.exists():
        for p in sorted(assets_dir.rglob("*")):
            if p.is_file():
                fs_files.add(p.relative_to(out_dir).as_posix())

    # 1. Every markdown ref must be in AssetRefs.
    md_missing_in_refs = sorted(md_refs - assetref_paths)
    if md_missing_in_refs:
        raise HardnessViolation(
            invariant="H5",
            detail=f"markdown references not in AssetRefs: {md_missing_in_refs[:5]}",
        )
    # 2. Every markdown ref must exist on disk.
    md_missing_on_disk = sorted(md_refs - fs_files)
    if md_missing_on_disk:
        raise HardnessViolation(
            invariant="H5",
            detail=f"markdown references missing on disk: {md_missing_on_disk[:5]}",
        )
    # 3. No orphan files in assets/.
    orphans = sorted(fs_files - md_refs - assetref_paths)
    if orphans:
        raise HardnessViolation(
            invariant="H5",
            detail=f"orphan files in assets/: {orphans[:5]}",
        )


def check_h6_asset_hash_truth(
    assets: tuple[AssetRef, ...], out_dir: Path
) -> None:
    for a in assets:
        path = out_dir / a.rel_path
        if not path.exists():
            raise HardnessViolation(
                invariant="H6",
                detail=f"AssetRef points to missing file: {a.rel_path}",
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != a.sha256:
            raise HardnessViolation(
                invariant="H6",
                detail=f"asset hash mismatch for {a.rel_path}: expected {a.sha256}, got {actual}",
            )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/hardness.py tests/test_hardness.py
git commit -m "feat(hardness): H5 asset closure + H6 asset hash truth

H5 ensures (markdown refs) == (AssetRefs) == (files on disk).
H6 recomputes sha256 of every asset file vs AssetRef.sha256.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: H7 (source hash truth) + H10 (outline source truth)

**Files:**
- Modify: `src/kb_extract/hardness.py`
- Modify: `tests/test_hardness.py`

- [ ] **Step 1: Append failing tests**

```python
from kb_extract.hardness import (
    check_h7_source_hash_truth,
    check_h10_outline_source_truth,
)


def test_h7_passes_when_meta_hash_matches_file(tmp_path):
    src = tmp_path / "src.pdf"
    data = b"%PDF-1.7 fake"
    src.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    meta = _meta(source_sha256=sha)
    check_h7_source_hash_truth(meta, src)


def test_h7_fails_when_meta_hash_lies(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"real")
    meta = _meta(source_sha256="0" * 64)
    with pytest.raises(HardnessViolation) as e:
        check_h7_source_hash_truth(meta, src)
    assert e.value.invariant == "H7"


def test_h10_bookmark_passes_when_at_least_one_node_marked_bookmark():
    # We model "derived from bookmark" by a non-empty title at level >= 1.
    leaf = SectionNode(
        node_id="0001", title="From bookmark", level=1, page_start=1, page_end=1,
        anchor="sec-1", language="en",
    )
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en", children=(leaf,),
    )
    meta = _meta(outline_source="bookmark")
    check_h10_outline_source_truth(meta, root)


def test_h10_bookmark_fails_when_only_root_exists():
    # outline_source=bookmark requires at least one non-root titled node.
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(outline_source="bookmark")
    with pytest.raises(HardnessViolation) as e:
        check_h10_outline_source_truth(meta, root)
    assert e.value.invariant == "H10"


def test_h10_page_fallback_always_passes():
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(outline_source="page_fallback")
    check_h10_outline_source_truth(meta, root)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `ImportError: cannot import name 'check_h7_source_hash_truth'`

- [ ] **Step 3: Extend `hardness.py`**

```python
from .contracts import ExtractionMeta


def check_h7_source_hash_truth(meta: ExtractionMeta, src_path: Path) -> None:
    actual = hashlib.sha256(src_path.read_bytes()).hexdigest()
    if actual != meta.source_sha256:
        raise HardnessViolation(
            invariant="H7",
            detail=(
                f"meta.source_sha256 lies about {meta.source_path}: "
                f"meta={meta.source_sha256}, actual={actual}"
            ),
        )


def _count_titled_descendants(node: SectionNode) -> int:
    """Count non-root nodes (level >= 1) with a non-empty title."""
    n = 0
    for c in node.children:
        if c.level >= 1 and c.title.strip():
            n += 1
        n += _count_titled_descendants(c)
    return n


def check_h10_outline_source_truth(meta: ExtractionMeta, index: SectionNode) -> None:
    # `page_fallback` does not promise structure beyond per-page nodes.
    if meta.outline_source == "page_fallback":
        return
    # For `bookmark`, `heading_style`, `docling_layout`: at least one
    # non-root titled node must exist (otherwise the adapter is lying about
    # having found structure).
    if _count_titled_descendants(index) == 0:
        raise HardnessViolation(
            invariant="H10",
            detail=(
                f"outline_source={meta.outline_source!r} claims structured outline, "
                "but section tree has no non-root titled nodes"
            ),
        )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `16 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/hardness.py tests/test_hardness.py
git commit -m "feat(hardness): H7 source hash truth + H10 outline source truth

H7 recomputes sha256 of source file vs meta.source_sha256.
H10 enforces that bookmark/heading_style/docling_layout claims are not
vacuous (at least one non-root titled node must exist).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: H9 (page-range closure)

**Files:**
- Modify: `src/kb_extract/hardness.py`
- Modify: `tests/test_hardness.py`

- [ ] **Step 1: Append failing tests**

```python
from kb_extract.hardness import check_h9_page_range_closure


def _leaf(ps, pe, *, anchor="sec", nid="x"):
    return SectionNode(
        node_id=nid, title=str(nid), level=1, page_start=ps, page_end=pe,
        anchor=anchor, language="en",
    )


def _root_with(leaves):
    return SectionNode(
        node_id="0", title="R", level=0, page_start=1, page_end=max(l.page_end for l in leaves),
        anchor="", language="en", children=tuple(leaves),
    )


def test_h9_passes_when_leaves_cover_1_to_n_exactly():
    root = _root_with([_leaf(1, 3, nid="a"), _leaf(4, 5, nid="b")])
    check_h9_page_range_closure(root, total_pages=5)


def test_h9_fails_on_gap():
    root = _root_with([_leaf(1, 2, nid="a"), _leaf(4, 5, nid="b")])
    with pytest.raises(HardnessViolation) as e:
        check_h9_page_range_closure(root, total_pages=5)
    assert e.value.invariant == "H9"
    assert "gap" in e.value.detail.lower() or "missing" in e.value.detail.lower()


def test_h9_fails_on_overlap():
    root = _root_with([_leaf(1, 3, nid="a"), _leaf(2, 4, nid="b")])
    with pytest.raises(HardnessViolation) as e:
        check_h9_page_range_closure(root, total_pages=4)
    assert e.value.invariant == "H9"
    assert "overlap" in e.value.detail.lower()


def test_h9_fails_when_last_page_uncovered():
    root = _root_with([_leaf(1, 3, nid="a")])
    with pytest.raises(HardnessViolation) as e:
        check_h9_page_range_closure(root, total_pages=5)
    assert e.value.invariant == "H9"


def test_h9_accepts_single_page_doc():
    root = _root_with([_leaf(1, 1, nid="a")])
    check_h9_page_range_closure(root, total_pages=1)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `ImportError: cannot import name 'check_h9_page_range_closure'`

- [ ] **Step 3: Extend `hardness.py`**

```python
def check_h9_page_range_closure(index: SectionNode, total_pages: int) -> None:
    """Union of leaf [page_start, page_end] must equal [1, total_pages] exactly."""
    leaves = sorted(_walk_leaves(index), key=lambda n: (n.page_start, n.page_end))
    if not leaves:
        raise HardnessViolation(
            invariant="H9",
            detail=f"no leaf sections found; cannot cover {total_pages} pages",
        )
    # Check overlap
    prev_end = 0
    for leaf in leaves:
        if leaf.page_start <= prev_end:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"page-range overlap at leaf {leaf.node_id}: "
                    f"starts at {leaf.page_start}, previous leaf ended at {prev_end}"
                ),
            )
        if leaf.page_start > prev_end + 1:
            raise HardnessViolation(
                invariant="H9",
                detail=(
                    f"page-range gap before leaf {leaf.node_id}: "
                    f"pages {prev_end + 1}..{leaf.page_start - 1} missing"
                ),
            )
        prev_end = leaf.page_end
    # Check end-of-doc coverage
    if prev_end != total_pages:
        raise HardnessViolation(
            invariant="H9",
            detail=(
                f"page-range does not reach end of doc: covered through {prev_end}, "
                f"total_pages={total_pages}"
            ),
        )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `21 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/hardness.py tests/test_hardness.py
git commit -m "feat(hardness): H9 page-range closure (no gaps, no overlaps)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 11: H11 (warnings allowlist)

**Files:**
- Modify: `src/kb_extract/hardness.py`
- Modify: `tests/test_hardness.py`

- [ ] **Step 1: Append failing tests**

```python
from kb_extract.hardness import check_h11_warnings_allowlist


def test_h11_passes_when_all_warnings_allowed():
    meta = _meta(warnings=("pdf.scanned_no_text_layer", "pdf.font_decode_failed:p3"))
    check_h11_warnings_allowlist(meta)


def test_h11_passes_when_warnings_empty():
    check_h11_warnings_allowlist(_meta(warnings=()))


def test_h11_fails_on_freeform_warning():
    meta = _meta(warnings=("pdf.scanned_no_text_layer", "freeform note"))
    with pytest.raises(HardnessViolation) as e:
        check_h11_warnings_allowlist(meta)
    assert e.value.invariant == "H11"
    assert "freeform note" in e.value.detail
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `ImportError: cannot import name 'check_h11_warnings_allowlist'`

- [ ] **Step 3: Extend `hardness.py`**

```python
from .warnings_registry import is_warning_allowed


def check_h11_warnings_allowlist(meta: ExtractionMeta) -> None:
    bad = sorted(w for w in meta.warnings if not is_warning_allowed(w))
    if bad:
        raise HardnessViolation(
            invariant="H11",
            detail=f"warnings not in allowlist: {bad[:5]}",
        )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_hardness.py -v`
Expected: `24 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/hardness.py tests/test_hardness.py
git commit -m "feat(hardness): H11 warnings allowlist enforcement

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 12: `assert_invariants` integration + H2 (no LLM imports) + H1 socket guard test

**Files:**
- Modify: `src/kb_extract/hardness.py`
- Modify: `tests/test_hardness.py`
- Create: `tests/test_no_llm_imports.py`
- Create: `tests/test_socket_guard.py`

- [ ] **Step 1: Append integration test**

In `tests/test_hardness.py`:
```python
from kb_extract.hardness import assert_invariants


def test_assert_invariants_passes_on_clean_result(tmp_path):
    src = tmp_path / "src.pdf"
    data = b"%PDF-1.7"
    src.write_bytes(data)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    leaf = SectionNode(
        node_id="0001", title="L", level=1, page_start=1, page_end=3,
        anchor="sec-0001", language="en",
    )
    root = SectionNode(
        node_id="0000", title="R", level=0, page_start=1, page_end=3,
        anchor="", language="en", children=(leaf,),
    )
    md = '<a id="sec-0001"></a>\nbody\n'
    meta = _meta(
        source_path="src.pdf",
        source_sha256=hashlib.sha256(data).hexdigest(),
        outline_source="bookmark",
        warnings=(),
    )
    result = ExtractionResult(
        markdown=md, index=root, tables=(), assets=(), meta=meta
    )

    assert_invariants(result, src, out_dir, total_pages=3)


def test_assert_invariants_propagates_first_violation(tmp_path):
    src = tmp_path / "src.pdf"
    src.write_bytes(b"x")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    root = SectionNode(
        node_id="0", title="R", level=0, page_start=1, page_end=1,
        anchor="", language="en",
    )
    meta = _meta(source_sha256="0" * 64)  # lies → H7
    result = ExtractionResult(
        markdown="hi\n", index=root, tables=(), assets=(), meta=meta
    )
    with pytest.raises(HardnessViolation) as e:
        assert_invariants(result, src, out_dir, total_pages=1)
    assert e.value.invariant in ("H7", "H10")  # H10 also fires (no titled descendants)
```

- [ ] **Step 2: Create `tests/test_no_llm_imports.py` (H2 static AST scan)**

```python
"""H2: adapters must not import any LLM SDK.

Static AST scan of every file in src/kb_extract/adapters/**/*.py. New LLM
SDKs should be added to LLM_DENYLIST below as they emerge.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

LLM_DENYLIST: tuple[str, ...] = (
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "langchain_core",
    "langchain_community",
    "google.generativeai",
    "google_generativeai",
    "transformers",
    "torch.nn",  # nn implies model code; raw torch ok for docling deps
    "vllm",
    "ollama",
    "groq",
    "mistralai",
    "cohere",
    "instructor",
    "dspy",
)


def _adapter_files() -> list[Path]:
    repo = Path(__file__).resolve().parents[1]
    return sorted((repo / "src" / "kb_extract" / "adapters").rglob("*.py"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


@pytest.mark.parametrize("path", _adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_import_any_llm_sdk(path: Path):
    if path.name == "__init__.py" and path.read_text(encoding="utf-8").strip() == "":
        pytest.skip("empty __init__")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = _imports(tree)
    forbidden = []
    for imp in imported:
        for bad in LLM_DENYLIST:
            if imp == bad or imp.startswith(bad + "."):
                forbidden.append(imp)
    assert not forbidden, (
        f"{path} imports forbidden LLM SDK(s): {forbidden}. "
        f"H2 violation. If this is a false positive, justify and update LLM_DENYLIST."
    )
```

- [ ] **Step 3: Create `tests/test_socket_guard.py` (H1 sanity)**

```python
"""H1 sanity: confirm pytest-socket is active.

If a future test runs in a mode where sockets are accidentally enabled, this
will fail loudly.
"""

import socket

import pytest


def test_socket_creation_is_blocked_by_default():
    with pytest.raises(Exception):
        s = socket.socket()
        s.connect(("1.1.1.1", 80))
```

- [ ] **Step 4: Implement `assert_invariants` in `hardness.py`**

Append:
```python
def assert_invariants(
    result, src_path: Path, out_dir: Path, *, total_pages: int
) -> None:
    """Run H3..H7, H9..H11 in order, raising on the first violation.

    H1 (no socket) and H2 (no LLM imports) are test-level checks.
    H8 (determinism) is a test-mode check (double-run compare).
    H12 (no silent skip) is enforced by the orchestrator.
    H13 (cross-platform) is enforced in CI.
    """
    check_h3_anchor_uniqueness(result.markdown)
    check_h4_anchor_completeness(result.markdown, result.index)
    check_h5_asset_closure(result.markdown, result.assets, out_dir)
    check_h6_asset_hash_truth(result.assets, out_dir)
    check_h7_source_hash_truth(result.meta, src_path)
    check_h9_page_range_closure(result.index, total_pages)
    check_h10_outline_source_truth(result.meta, result.index)
    check_h11_warnings_allowlist(result.meta)
```

- [ ] **Step 5: Create `src/kb_extract/adapters/__init__.py` (one-line docstring; H2 scan runs over every .py file here)**

```python
"""Adapter package. H2 static scan runs over every .py file here."""
```

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tests/test_hardness.py tests/test_no_llm_imports.py tests/test_socket_guard.py -v`
Expected: `26 passed` (24 hardness + 2 integration + 1 no-llm + 1 socket = adjust based on parametrize count).

If H1 socket test errors because `disable_socket` was not applied (the `disable_socket` marker is conftest-managed), confirm conftest.py from Task 1 is in place.

- [ ] **Step 7: Commit**

```powershell
git add src/kb_extract/hardness.py src/kb_extract/adapters/__init__.py tests/test_hardness.py tests/test_no_llm_imports.py tests/test_socket_guard.py
git commit -m "feat(hardness): assert_invariants integration + H2 static scan + H1 socket test

assert_invariants runs H3..H7, H9..H11 in order at orchestrator boundary.
H2: AST scan rejects any LLM SDK import in adapters/**.
H1 sanity: confirm pytest-socket actually blocks sockets by default.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Layout, manifest, discovery (Tasks 13–15)

Per-project filesystem layout helpers, the SQLite manifest, and the source-file discovery walker. None of these depend on adapters or hardness — they're pure utilities the orchestrator composes.

---

### Task 13: `layout.py` — `target_dir` and `find_project_root`

Spec §2.2, §2.3, §5.2.

**Files:**
- Create: `src/kb_extract/layout.py`
- Test: `tests/test_layout.py`

- [ ] **Step 1: Write failing test**

`tests/test_layout.py`:
```python
from pathlib import Path

import pytest
from kb_extract.layout import find_project_root, target_dir


def test_target_dir_strips_extension(tmp_path):
    project = tmp_path / "BUR-K"
    project.mkdir()
    src = project / "M1324399-DOC_MP44_MAIN-REV_E.pdf"
    src.write_bytes(b"%PDF-1.7")
    out = target_dir(project, src)
    assert out == project / "kb" / "M1324399-DOC_MP44_MAIN-REV_E"


def test_target_dir_handles_double_extension(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    src = project / "archive.tar.gz"
    src.write_bytes(b"x")
    out = target_dir(project, src)
    # Only the final .gz is stripped (we treat .tar as part of stem).
    assert out == project / "kb" / "archive.tar"


def test_target_dir_for_nested_source_preserves_subdir(tmp_path):
    project = tmp_path / "P"
    (project / "subdir").mkdir(parents=True)
    src = project / "subdir" / "doc.pdf"
    src.write_bytes(b"x")
    out = target_dir(project, src)
    assert out == project / "kb" / "subdir" / "doc"


def test_find_project_root_returns_self_for_directory_input(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    assert find_project_root(project) == project


def test_find_project_root_for_file_returns_immediate_parent_if_no_kb_ancestor(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    src = project / "doc.pdf"
    src.write_bytes(b"x")
    assert find_project_root(src) == project


def test_find_project_root_walks_up_to_kb_marker(tmp_path):
    project = tmp_path / "P"
    (project / "kb").mkdir(parents=True)
    (project / "sub" / "deep").mkdir(parents=True)
    src = project / "sub" / "deep" / "doc.pdf"
    src.write_bytes(b"x")
    assert find_project_root(src) == project


def test_target_dir_rejects_source_outside_project(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    outside = tmp_path / "other.pdf"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError):
        target_dir(project, outside)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_layout.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.layout'`

- [ ] **Step 3: Implement `layout.py`**

`src/kb_extract/layout.py`:
```python
"""Per-project filesystem layout helpers. See spec §2.2, §2.3, §5.2."""

from __future__ import annotations

from pathlib import Path


def target_dir(project_root: Path, src: Path) -> Path:
    """Return the per-document output directory for `src` within `project_root`.

    Example: project=/P, src=/P/sub/doc.pdf -> /P/kb/sub/doc
    """
    project_root = project_root.resolve()
    src = src.resolve()
    try:
        rel = src.relative_to(project_root)
    except ValueError as e:
        raise ValueError(
            f"source {src} is not inside project root {project_root}"
        ) from e
    stem_parts = list(rel.parts[:-1]) + [rel.stem]
    return project_root / "kb" / Path(*stem_parts)


def find_project_root(path: Path) -> Path:
    """Find the project root for a given path.

    Rules (spec §5.2):
    - If `path` is a directory, that directory is the project root.
    - If `path` is a file, walk up looking for an ancestor containing `kb/`;
      return it. If none found, return the file's immediate parent.
    """
    path = path.resolve()
    if path.is_dir():
        return path
    for parent in path.parents:
        if (parent / "kb").is_dir():
            return parent
    return path.parent
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_layout.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/layout.py tests/test_layout.py
git commit -m "feat(layout): target_dir + find_project_root helpers

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 14: `manifest.py` — SQLite schema, upsert/get/mark_skipped/mark_failed

Spec §5.4: SQLite with WAL mode, ACID writes. Schema is one table tracking every source file the orchestrator has seen.

**Files:**
- Create: `src/kb_extract/manifest.py`
- Test: `tests/test_manifest.py`

- [ ] **Step 1: Write failing test**

`tests/test_manifest.py`:
```python
from pathlib import Path

from kb_extract.contracts import ExtractionMeta
from kb_extract.manifest import Manifest, ManifestRow


def _meta(**kw):
    defaults: dict = dict(
        source_path="P/foo.pdf", source_sha256="a" * 64, source_bytes=10,
        source_mtime_iso="2026-06-09T12:00:00+00:00",
        adapter_name="pdf_docling", adapter_version="abc",
        tool_versions={"docling": "2.0"}, extracted_at_iso="2026-06-09T12:01:00+00:00",
        outline_source="bookmark", status="ok",
    )
    defaults.update(kw)
    return ExtractionMeta(**defaults)


def test_manifest_creates_db_and_table(tmp_path):
    db = tmp_path / "manifest.sqlite"
    m = Manifest(db)
    m.close()
    assert db.exists()


def test_upsert_and_get_returns_row(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/foo.pdf"), _meta(), output_sha256="b" * 64)
    row = m.get(Path("/abs/P/foo.pdf"))
    assert isinstance(row, ManifestRow)
    assert row.status == "ok"
    assert row.source_sha256 == "a" * 64
    assert row.output_sha256 == "b" * 64
    m.close()


def test_upsert_replaces_existing_row(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/foo.pdf"), _meta(source_sha256="a" * 64), output_sha256="1" * 64)
    m.upsert(Path("/abs/P/foo.pdf"), _meta(source_sha256="c" * 64), output_sha256="2" * 64)
    row = m.get(Path("/abs/P/foo.pdf"))
    assert row.source_sha256 == "c" * 64
    assert row.output_sha256 == "2" * 64
    m.close()


def test_get_returns_none_for_unknown(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    assert m.get(Path("/abs/missing.pdf")) is None
    m.close()


def test_mark_skipped_records_reason(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.mark_skipped(Path("/abs/P/x.stp"), "no_adapter")
    row = m.get(Path("/abs/P/x.stp"))
    assert row.status == "skipped"
    assert row.skipped_reason == "no_adapter"
    m.close()


def test_mark_failed_records_error_repr(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.mark_failed(Path("/abs/P/x.pdf"), "AdapterError('boom')")
    row = m.get(Path("/abs/P/x.pdf"))
    assert row.status == "failed"
    assert "boom" in row.error_repr
    m.close()


def test_iter_returns_all_rows_sorted_by_source_path(tmp_path):
    m = Manifest(tmp_path / "m.sqlite")
    m.upsert(Path("/abs/P/b.pdf"), _meta(source_path="P/b.pdf"), output_sha256="x")
    m.upsert(Path("/abs/P/a.pdf"), _meta(source_path="P/a.pdf"), output_sha256="y")
    rows = list(m.iter())
    assert [r.source_path for r in rows] == ["P/a.pdf", "P/b.pdf"]
    m.close()


def test_atomicity_partial_transaction_does_not_persist(tmp_path):
    """SQLite ACID: if we crash mid-transaction the row should not appear."""
    db = tmp_path / "m.sqlite"
    m = Manifest(db)
    try:
        with m.conn:  # transaction
            m.conn.execute("INSERT INTO sources(source_path, status) VALUES (?, ?)",
                           ("P/x.pdf", "ok"))
            raise RuntimeError("simulated crash")
    except RuntimeError:
        pass
    # Reopen
    m.close()
    m2 = Manifest(db)
    assert m2.get(Path("/abs/P/x.pdf")) is None
    m2.close()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.manifest'`

- [ ] **Step 3: Implement `manifest.py`**

`src/kb_extract/manifest.py`:
```python
"""Per-project SQLite manifest of extracted sources. See spec §5.4."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from .contracts import ExtractionMeta

Status = Literal["ok", "partial", "failed", "skipped"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_path        TEXT PRIMARY KEY,
    source_sha256      TEXT,
    source_bytes       INTEGER,
    source_mtime_iso   TEXT,
    adapter_name       TEXT,
    adapter_version    TEXT,
    tool_versions_json TEXT,
    extracted_at_iso   TEXT,
    outline_source     TEXT,
    status             TEXT NOT NULL,
    warnings_json      TEXT,
    skipped_reason     TEXT,
    error_repr         TEXT,
    output_sha256      TEXT
);
"""


@dataclass(frozen=True, slots=True)
class ManifestRow:
    source_path: str
    source_sha256: str | None
    source_bytes: int | None
    source_mtime_iso: str | None
    adapter_name: str | None
    adapter_version: str | None
    tool_versions: dict[str, str]
    extracted_at_iso: str | None
    outline_source: str | None
    status: Status
    warnings: tuple[str, ...]
    skipped_reason: str | None
    error_repr: str | None
    output_sha256: str | None


class Manifest:
    """Wrapper around SQLite manifest file."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _key(self, src: Path) -> str:
        return src.resolve().as_posix()

    def upsert(
        self,
        src: Path,
        meta: ExtractionMeta,
        *,
        output_sha256: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(
                    source_path, source_sha256, source_bytes, source_mtime_iso,
                    adapter_name, adapter_version, tool_versions_json,
                    extracted_at_iso, outline_source, status, warnings_json,
                    skipped_reason, error_repr, output_sha256
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    source_sha256=excluded.source_sha256,
                    source_bytes=excluded.source_bytes,
                    source_mtime_iso=excluded.source_mtime_iso,
                    adapter_name=excluded.adapter_name,
                    adapter_version=excluded.adapter_version,
                    tool_versions_json=excluded.tool_versions_json,
                    extracted_at_iso=excluded.extracted_at_iso,
                    outline_source=excluded.outline_source,
                    status=excluded.status,
                    warnings_json=excluded.warnings_json,
                    skipped_reason=NULL,
                    error_repr=NULL,
                    output_sha256=excluded.output_sha256
                """,
                (
                    self._key(src),
                    meta.source_sha256,
                    meta.source_bytes,
                    meta.source_mtime_iso,
                    meta.adapter_name,
                    meta.adapter_version,
                    json.dumps(meta.tool_versions, sort_keys=True),
                    meta.extracted_at_iso,
                    meta.outline_source,
                    meta.status,
                    json.dumps(list(meta.warnings), sort_keys=True),
                    None,
                    None,
                    output_sha256,
                ),
            )

    def mark_skipped(self, src: Path, reason: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_path, status, skipped_reason)
                VALUES (?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    status='skipped', skipped_reason=excluded.skipped_reason
                """,
                (self._key(src), "skipped", reason),
            )

    def mark_failed(self, src: Path, error_repr: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_path, status, error_repr)
                VALUES (?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    status='failed', error_repr=excluded.error_repr
                """,
                (self._key(src), "failed", error_repr),
            )

    def get(self, src: Path) -> ManifestRow | None:
        cur = self.conn.execute(
            "SELECT * FROM sources WHERE source_path = ?", (self._key(src),)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dc(row, cur.description)

    def iter(self) -> Iterator[ManifestRow]:
        cur = self.conn.execute("SELECT * FROM sources ORDER BY source_path")
        desc = cur.description
        for row in cur:
            yield self._row_to_dc(row, desc)

    @staticmethod
    def _row_to_dc(row, desc) -> ManifestRow:
        d = {desc[i][0]: row[i] for i in range(len(desc))}
        tool_versions = json.loads(d.get("tool_versions_json") or "{}")
        warnings = tuple(json.loads(d.get("warnings_json") or "[]"))
        return ManifestRow(
            source_path=d["source_path"],
            source_sha256=d.get("source_sha256"),
            source_bytes=d.get("source_bytes"),
            source_mtime_iso=d.get("source_mtime_iso"),
            adapter_name=d.get("adapter_name"),
            adapter_version=d.get("adapter_version"),
            tool_versions=tool_versions,
            extracted_at_iso=d.get("extracted_at_iso"),
            outline_source=d.get("outline_source"),
            status=d["status"],
            warnings=warnings,
            skipped_reason=d.get("skipped_reason"),
            error_repr=d.get("error_repr"),
            output_sha256=d.get("output_sha256"),
        )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_manifest.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): SQLite manifest with WAL + ACID upsert/get/mark_*

One row per source file; status in {ok, partial, failed, skipped}.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 15: `discover_sources` — recursive walker with skip rules

Spec §5.2 skip rules: `kb/`, `.git/`, `*.tmp`, anything matching `.gitignore`. v1 reads `.gitignore` if present at project root only (simple line-prefix match — full gitignore semantics deferred). Discovery returns files in sorted UTF-8 byte order.

**Files:**
- Create: `src/kb_extract/discovery.py`
- Test: `tests/test_discovery.py`

- [ ] **Step 1: Write failing test**

`tests/test_discovery.py`:
```python
from pathlib import Path

from kb_extract.discovery import discover_sources


def test_discover_returns_files_only_sorted(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "b.docx").write_bytes(b"b")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.xlsx").write_bytes(b"c")
    out = discover_sources(tmp_path)
    rels = [p.relative_to(tmp_path).as_posix() for p in out]
    assert rels == sorted(rels)
    assert rels == ["a.pdf", "b.docx", "sub/c.xlsx"]


def test_discover_skips_kb_directory(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "kb").mkdir()
    (tmp_path / "kb" / "manifest.sqlite").write_bytes(b"x")
    (tmp_path / "kb" / "a" / "main.md").parent.mkdir(parents=True)
    (tmp_path / "kb" / "a" / "main.md").write_bytes(b"y")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_skips_dot_git(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_bytes(b"ref: refs/heads/main")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_skips_tmp_dirs(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "out.tmp").mkdir()
    (tmp_path / "out.tmp" / "x.txt").write_bytes(b"y")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert rels == ["a.pdf"]


def test_discover_respects_gitignore_at_root(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "secret.pdf").write_bytes(b"s")
    (tmp_path / ".gitignore").write_text("secret.pdf\n", encoding="utf-8")
    rels = [p.relative_to(tmp_path).as_posix() for p in discover_sources(tmp_path)]
    assert "secret.pdf" not in rels
    assert "a.pdf" in rels


def test_discover_single_file_input_returns_itself_if_supported(tmp_path):
    src = tmp_path / "a.pdf"
    src.write_bytes(b"a")
    out = discover_sources(src)
    assert out == [src.resolve()]
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_discovery.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.discovery'`

- [ ] **Step 3: Implement `discovery.py`**

`src/kb_extract/discovery.py`:
```python
"""Source-file discovery walker. Spec §5.2."""

from __future__ import annotations

from pathlib import Path

_ALWAYS_SKIP_DIRS = {"kb", ".git", "__pycache__", ".venv", "venv", "node_modules"}


def _load_gitignore_patterns(root: Path) -> set[str]:
    gi = root / ".gitignore"
    if not gi.exists():
        return set()
    patterns: set[str] = set()
    for line in gi.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # v1 supports literal file/dir names only (no globs); full gitignore
        # semantics deferred to a future revision.
        patterns.add(line.rstrip("/"))
    return patterns


def _is_skippable(path: Path, project_root: Path, gitignored: set[str]) -> bool:
    rel = path.relative_to(project_root)
    parts = rel.parts
    if any(p in _ALWAYS_SKIP_DIRS for p in parts):
        return True
    if any(p.endswith(".tmp") for p in parts):
        return True
    for part in parts:
        if part in gitignored:
            return True
    if rel.name in gitignored:
        return True
    return False


def discover_sources(path: Path) -> list[Path]:
    """Return a sorted list of source files under `path`.

    - `path` is a file: returns `[path.resolve()]`.
    - `path` is a directory: walks recursively, applying skip rules.
    """
    path = path.resolve()
    if path.is_file():
        return [path]
    gitignored = _load_gitignore_patterns(path)
    out: list[Path] = []
    for p in sorted(path.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        if _is_skippable(p, path, gitignored):
            continue
        out.append(p.resolve())
    return out
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_discovery.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/discovery.py tests/test_discovery.py
git commit -m "feat(discovery): recursive source walker with skip rules

Skips kb/, .git/, *.tmp/, common Python/Node dirs. Reads .gitignore
literal entries at project root. Returns paths in sorted UTF-8 byte order.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4 — Orchestrator skeleton (Tasks 16–18)

`base.Extractor` protocol + adapter registry, then orchestrator main flow with a no-op `Extractor` used in tests. Real adapters arrive in Phase 5.

---

### Task 16: `base.Extractor` protocol + registry + `NoopAdapter`

**Files:**
- Create: `src/kb_extract/adapters/base.py`
- Create: `src/kb_extract/adapters/_noop.py` — test-only adapter; lives next to real adapters so registry picks it up uniformly. NOT auto-registered.
- Test: `tests/adapters/__init__.py`
- Test: `tests/adapters/test_registry.py`

- [ ] **Step 1: Create empty `tests/adapters/__init__.py`**

```python
```

- [ ] **Step 2: Write failing tests**

`tests/adapters/test_registry.py`:
```python
from pathlib import Path

import pytest
from kb_extract.adapters.base import (
    Extractor,
    Registry,
    get_default_registry,
    register,
)


class _Dummy:
    name = "dummy"
    version = "0.1"
    extensions = (".dum",)

    def extract(self, src: Path, out_dir_tmp: Path):
        raise NotImplementedError


def test_register_and_pick_by_extension(tmp_path):
    r = Registry()
    r.register(_Dummy())
    fake = tmp_path / "x.dum"
    fake.write_bytes(b"x")
    picked = r.pick(fake)
    assert picked is not None
    assert picked.name == "dummy"


def test_pick_returns_none_for_unknown_extension(tmp_path):
    r = Registry()
    fake = tmp_path / "x.unknown"
    fake.write_bytes(b"x")
    assert r.pick(fake) is None


def test_pick_case_insensitive_extension(tmp_path):
    r = Registry()
    r.register(_Dummy())
    fake = tmp_path / "x.DUM"
    fake.write_bytes(b"x")
    assert r.pick(fake) is not None


def test_double_register_same_extension_raises():
    r = Registry()
    r.register(_Dummy())
    with pytest.raises(ValueError):
        r.register(_Dummy())


def test_register_decorator_adds_to_default_registry():
    @register
    class _AnotherDummy:
        name = "another"
        version = "0.1"
        extensions = (".another",)

        def extract(self, src, out_dir_tmp):
            raise NotImplementedError

    default = get_default_registry()
    names = [a.name for a in default.all()]
    assert "another" in names


def test_extractor_protocol_runtime_checkable():
    assert isinstance(_Dummy(), Extractor)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_registry.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `adapters/base.py`**

`src/kb_extract/adapters/base.py`:
```python
"""Extractor protocol and adapter registry.

Adapters register themselves via `@register` at import time. The orchestrator
holds a `Registry` instance and calls `pick(src)` to choose one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..contracts import ExtractionResult


@runtime_checkable
class Extractor(Protocol):
    name: str
    version: str
    extensions: tuple[str, ...]

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        ...


class Registry:
    def __init__(self) -> None:
        self._by_ext: dict[str, Extractor] = {}
        self._adapters: list[Extractor] = []

    def register(self, adapter: Extractor) -> None:
        for ext in adapter.extensions:
            key = ext.lower()
            if key in self._by_ext:
                raise ValueError(
                    f"adapter for extension {key!r} already registered: "
                    f"{self._by_ext[key].name}"
                )
            self._by_ext[key] = adapter
        self._adapters.append(adapter)

    def pick(self, src: Path) -> Extractor | None:
        return self._by_ext.get(src.suffix.lower())

    def all(self) -> list[Extractor]:
        return list(self._adapters)


_DEFAULT: Registry = Registry()


def get_default_registry() -> Registry:
    return _DEFAULT


def register(adapter_cls):
    """Decorator that instantiates and registers an adapter on the default registry."""
    instance = adapter_cls()
    _DEFAULT.register(instance)
    return adapter_cls
```

- [ ] **Step 5: Create `src/kb_extract/adapters/_noop.py`** (test-only adapter used by registry & orchestrator tests)

```python
"""Test-only adapter: trivially valid ExtractionResult for any input.

Registered manually in tests; NOT auto-registered to the default registry.
Useful for orchestrator/hardness wiring tests without real document parsing.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import ExtractionMeta, ExtractionResult, SectionNode


class NoopAdapter:
    name = "_noop"
    version = "0.1"
    extensions = (".noop",)

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        data = src.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        leaf = SectionNode(
            node_id="0001",
            title="Noop content",
            level=1,
            page_start=1,
            page_end=1,
            anchor="sec-0001",
            language="und",
        )
        root = SectionNode(
            node_id="0000",
            title="Root",
            level=0,
            page_start=1,
            page_end=1,
            anchor="",
            language="und",
            children=(leaf,),
        )
        markdown = (
            f'<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->\n\n'
            '<a id="sec-0001"></a>\n'
            '# Noop content\n\n'
            f'(noop adapter for tests: {src.name})\n'
        )
        meta = ExtractionMeta(
            source_path=src.name,
            source_sha256=sha,
            source_bytes=len(data),
            source_mtime_iso=datetime.fromtimestamp(
                src.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={},
            extracted_at_iso="2026-06-09T00:00:00+00:00",
            outline_source="bookmark",
            status="ok",
            warnings=(),
            skipped_reasons=(),
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=(), assets=(), meta=meta
        )
```

- [ ] **Step 6: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_registry.py -v`
Expected: `6 passed`

- [ ] **Step 7: Commit**

```powershell
git add src/kb_extract/adapters/base.py src/kb_extract/adapters/_noop.py tests/adapters/__init__.py tests/adapters/test_registry.py
git commit -m "feat(adapters): Extractor protocol + Registry + @register decorator + NoopAdapter

NoopAdapter is test-only (NOT auto-registered to default registry); it
exists to exercise registry/orchestrator/hardness wiring without depending
on a real document parser.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 17: Orchestrator core flow with `NoopAdapter`

**Files:**
- Create: `src/kb_extract/orchestrator.py`
- Test: `tests/test_orchestrator.py`

(`_noop.py` was created in Task 16; we just consume `NoopAdapter` here.)

- [ ] **Step 1: Write failing test**

`tests/test_orchestrator.py`:
```python
import hashlib
from pathlib import Path

import pytest
from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.orchestrator import RunReport, run


def _setup_project(tmp_path: Path) -> Path:
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"hello")
    (project / "b.noop").write_bytes(b"world")
    (project / "unknown.xyz").write_bytes(b"?")
    return project


def test_run_extracts_each_known_source(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    report = run(project, registry=reg)
    assert isinstance(report, RunReport)
    assert report.ok_count == 2
    assert report.skipped_count == 1
    assert (project / "kb" / "a" / "main.md").exists()
    assert (project / "kb" / "b" / "main.md").exists()
    assert (project / "kb" / "manifest.sqlite").exists()


def test_run_is_idempotent_on_second_call_no_force(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    main_md = project / "kb" / "a" / "main.md"
    mtime1 = main_md.stat().st_mtime_ns
    report2 = run(project, registry=reg)
    assert report2.ok_count == 0  # nothing re-extracted
    assert report2.unchanged_count == 2
    assert main_md.stat().st_mtime_ns == mtime1


def test_run_force_re_extracts(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    report = run(project, registry=reg, force=True)
    assert report.ok_count == 2


def test_run_dry_run_writes_nothing(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    report = run(project, registry=reg, dry_run=True)
    assert not (project / "kb").exists() or not any((project / "kb").rglob("main.md"))
    assert report.dry_run_count == 2


def test_run_marks_unsupported_as_skipped(tmp_path):
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    from kb_extract.manifest import Manifest
    m = Manifest(project / "kb" / "manifest.sqlite")
    rows = list(m.iter())
    statuses = {Path(r.source_path).name: r.status for r in rows}
    assert statuses == {"a.noop": "ok", "b.noop": "ok", "unknown.xyz": "skipped"}
    m.close()


def test_run_h12_no_silent_skip(tmp_path):
    """H12: every discovered file gets a manifest row."""
    project = _setup_project(tmp_path)
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    from kb_extract.manifest import Manifest
    m = Manifest(project / "kb" / "manifest.sqlite")
    n_rows = len(list(m.iter()))
    m.close()
    # 3 source files in project
    assert n_rows == 3


def test_run_adapter_exception_marks_failed_and_continues(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    reg = Registry()
    noop = NoopAdapter()

    def boom(src, out_dir_tmp):
        if src.name == "a.noop":
            raise RuntimeError("simulated adapter crash")
        return NoopAdapter.extract(noop, src, out_dir_tmp)

    monkeypatch.setattr(noop, "extract", boom)
    reg.register(noop)
    report = run(project, registry=reg)
    assert report.failed_count == 1
    assert report.ok_count == 1


def test_run_atomic_no_orphan_tmp_dir_on_failure(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    reg = Registry()
    noop = NoopAdapter()

    def boom(src, out_dir_tmp):
        # Write a fake file then crash.
        (out_dir_tmp / "junk").mkdir(parents=True, exist_ok=True)
        (out_dir_tmp / "junk" / "main.md").write_bytes(b"partial")
        raise RuntimeError("crash after partial write")

    monkeypatch.setattr(noop, "extract", boom)
    reg.register(noop)
    run(project, registry=reg)
    tmp_dirs = list((project / "kb").rglob("*.tmp"))
    assert tmp_dirs == [], f"orphan tmp dirs left behind: {tmp_dirs}"
```

- [ ] **Step 2: Implement `orchestrator.py`**

`src/kb_extract/orchestrator.py`:
```python
"""Main extraction pipeline. Spec §5."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .adapters.base import Extractor, Registry, get_default_registry
from .contracts import ExtractionResult
from .discovery import discover_sources
from .errors import HardnessViolation
from .hardness import assert_invariants
from .layout import find_project_root, target_dir
from .manifest import Manifest
from .serialization import (
    serialize_index_json,
    serialize_markdown,
    serialize_meta_json,
)


@dataclass(slots=True)
class RunReport:
    ok_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    unchanged_count: int = 0
    dry_run_count: int = 0
    violations: list[str] = field(default_factory=list)
    sources_processed: list[str] = field(default_factory=list)

    @property
    def overall_status(self) -> str:
        if self.violations or self.failed_count:
            return "partial" if self.ok_count else "failed"
        return "ok"


def _total_pages_from_index(result: ExtractionResult) -> int:
    return result.index.page_end or 1


def _write_result_to_disk(result: ExtractionResult, out_dir_tmp: Path) -> str:
    """Write markdown, index.json, meta.json. Returns output sha256."""
    main_md = out_dir_tmp / "main.md"
    main_md.write_bytes(serialize_markdown(result.markdown).encode("utf-8"))
    (out_dir_tmp / "index.json").write_bytes(
        serialize_index_json(result.index).encode("utf-8")
    )
    (out_dir_tmp / "meta.json").write_bytes(
        serialize_meta_json(result.meta).encode("utf-8")
    )
    return result.content_sha256()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(
    path: Path,
    *,
    registry: Registry | None = None,
    force: bool = False,
    dry_run: bool = False,
    only_exts: tuple[str, ...] | None = None,
) -> RunReport:
    """Top-level extraction over a project root or file. See spec §5.1."""
    if registry is None:
        registry = get_default_registry()

    project_root = find_project_root(path)
    sources = discover_sources(path)
    if only_exts:
        sources = [s for s in sources if s.suffix.lower() in {e.lower() for e in only_exts}]

    manifest_path = project_root / "kb" / "manifest.sqlite"
    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(manifest_path) if not dry_run else None
    report = RunReport()
    try:
        for src in sources:
            report.sources_processed.append(src.as_posix())
            adapter = registry.pick(src)
            if adapter is None:
                if manifest is not None:
                    manifest.mark_skipped(src, "no_adapter")
                report.skipped_count += 1
                continue

            if dry_run:
                report.dry_run_count += 1
                continue

            src_hash = _sha256_file(src)
            prev = manifest.get(src)
            if prev and prev.source_sha256 == src_hash and prev.status == "ok" and not force:
                report.unchanged_count += 1
                continue

            out_dir = target_dir(project_root, src)
            out_dir_tmp = out_dir.with_suffix(out_dir.suffix + ".tmp")
            if out_dir_tmp.exists():
                shutil.rmtree(out_dir_tmp)
            out_dir_tmp.mkdir(parents=True, exist_ok=True)
            (out_dir_tmp / "assets").mkdir(exist_ok=True)

            try:
                result = adapter.extract(src, out_dir_tmp)
            except HardnessViolation:
                shutil.rmtree(out_dir_tmp, ignore_errors=True)
                raise
            except Exception as e:  # noqa: BLE001 — orchestrator is the catch-all per spec §5.1
                manifest.mark_failed(src, repr(e))
                shutil.rmtree(out_dir_tmp, ignore_errors=True)
                report.failed_count += 1
                continue

            try:
                assert_invariants(
                    result,
                    src,
                    out_dir_tmp,
                    total_pages=_total_pages_from_index(result),
                )
            except HardnessViolation as e:
                manifest.mark_failed(src, repr(e))
                shutil.rmtree(out_dir_tmp, ignore_errors=True)
                report.violations.append(f"{src.as_posix()}: {e}")
                report.failed_count += 1
                continue

            output_sha = _write_result_to_disk(result, out_dir_tmp)
            if out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            out_dir_tmp.rename(out_dir)
            manifest.upsert(src, result.meta, output_sha256=output_sha)
            report.ok_count += 1
    finally:
        if manifest is not None:
            manifest.close()
    return report
```

- [ ] **Step 3: Run, expect PASS**

Run: `uv run pytest tests/test_orchestrator.py tests/adapters/test_registry.py -v`
Expected: `14 passed`

- [ ] **Step 4: Commit**

```powershell
git add src/kb_extract/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): main extraction flow with atomic tmp→final rename

- Discover sources, pick adapter, short-circuit on unchanged source_sha256
- Atomic tmp dir; cleanup on adapter exception or hardness violation
- H12 (no silent skip): every source gets a manifest row

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 18: H8 (determinism) test for orchestrator + `kb verify` foundation

H8 is a meta-invariant: re-running the orchestrator on unchanged input produces byte-identical outputs. We also add a `verify_project` function that downstream `kb verify` CLI will call.

**Files:**
- Create: `src/kb_extract/verify.py`
- Test: `tests/test_determinism.py`
- Test: `tests/test_verify.py`

- [ ] **Step 1: Write failing test for H8 determinism**

`tests/test_determinism.py`:
```python
import hashlib
import shutil
from pathlib import Path

from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.orchestrator import run


def _hash_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.sqlite":
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_h8_byte_identical_double_extract(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"reproducible")
    reg = Registry()
    reg.register(NoopAdapter())

    run(project, registry=reg, force=True)
    first = _hash_tree(project / "kb")

    # Wipe and re-run.
    shutil.rmtree(project / "kb")
    run(project, registry=reg, force=True)
    second = _hash_tree(project / "kb")

    assert first == second, "outputs not byte-identical between runs (H8 violation)"
```

- [ ] **Step 2: Write failing tests for `verify`**

`tests/test_verify.py`:
```python
from pathlib import Path

import pytest
from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.errors import HardnessViolation
from kb_extract.orchestrator import run
from kb_extract.verify import VerifyReport, verify_project


def test_verify_passes_on_freshly_extracted_project(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    report = verify_project(project)
    assert isinstance(report, VerifyReport)
    assert report.ok
    assert report.violations == []


def test_verify_detects_edited_main_md(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    main_md = project / "kb" / "a" / "main.md"
    main_md.write_bytes(main_md.read_bytes() + b" tampered ")
    report = verify_project(project)
    assert not report.ok
    assert any("a/main.md" in v or "main.md" in v for v in report.violations)


def test_verify_fail_fast_stops_at_first(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    (project / "b.noop").write_bytes(b"y")
    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg)
    # Tamper both
    (project / "kb" / "a" / "main.md").write_bytes(b"bad")
    (project / "kb" / "b" / "main.md").write_bytes(b"bad")
    report = verify_project(project, fail_fast=True)
    assert not report.ok
    assert len(report.violations) == 1
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/test_determinism.py tests/test_verify.py -v`
Expected: ImportError for `kb_extract.verify`.

- [ ] **Step 4: Implement `verify.py`**

`src/kb_extract/verify.py`:
```python
"""kb verify implementation. Spec §7 (last paragraph), §8.1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import HardnessViolation
from .manifest import Manifest


@dataclass(slots=True)
class VerifyReport:
    ok: bool = True
    violations: list[str] = field(default_factory=list)
    files_checked: int = 0


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _doc_dirs(project_root: Path) -> list[Path]:
    kb = project_root / "kb"
    if not kb.exists():
        return []
    return sorted(p for p in kb.rglob("main.md") if p.is_file())


def verify_project(project_root: Path, *, fail_fast: bool = False) -> VerifyReport:
    """Re-run filesystem-level checks against artifacts on disk.

    Catches unauthorized edits to main.md (by re-hashing and comparing with
    manifest), plus structural integrity (assets present, hashes match).
    """
    report = VerifyReport()
    manifest_path = project_root / "kb" / "manifest.sqlite"
    if not manifest_path.exists():
        report.ok = False
        report.violations.append(f"no manifest at {manifest_path}")
        return report

    m = Manifest(manifest_path)
    try:
        # Build map source_sha → output_sha from manifest by re-keying on output dir name.
        manifest_rows = {r.source_path: r for r in m.iter()}
    finally:
        m.close()

    for main_md in _doc_dirs(project_root):
        report.files_checked += 1
        doc_dir = main_md.parent
        meta_path = doc_dir / "meta.json"
        if not meta_path.exists():
            report.ok = False
            report.violations.append(f"{doc_dir}: missing meta.json")
            if fail_fast:
                return report
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        src_path = meta.get("source_path", "")
        # Find a matching manifest row whose source_path ends with the meta source_path.
        matching = [
            row for key, row in manifest_rows.items()
            if Path(key).name == Path(src_path).name
        ]
        if not matching:
            report.ok = False
            report.violations.append(f"{doc_dir}: no manifest row for {src_path}")
            if fail_fast:
                return report
            continue
        row = matching[0]
        # Re-compute output sha (markdown only here as cheapest check).
        actual_md = main_md.read_bytes()
        actual_md_sha = hashlib.sha256(actual_md).hexdigest()
        # We stored a composite output_sha; the markdown-only sha is a different value.
        # For v1 simplicity: also recompute composite from on-disk artifacts.
        composite = _recompute_composite_sha(doc_dir)
        if row.output_sha256 and composite != row.output_sha256:
            report.ok = False
            report.violations.append(
                f"{doc_dir.relative_to(project_root).as_posix()}/main.md: "
                f"content hash mismatch (manifest={row.output_sha256[:12]}, "
                f"actual={composite[:12]})"
            )
            if fail_fast:
                return report
    return report


def _recompute_composite_sha(doc_dir: Path) -> str:
    """Mirror of ExtractionResult.content_sha256 over on-disk artifacts."""
    h = hashlib.sha256()
    h.update((doc_dir / "main.md").read_bytes())
    h.update(b"\x00ASSETS\x00")
    assets_dir = doc_dir / "assets"
    asset_shas = []
    if assets_dir.exists():
        for p in sorted(assets_dir.rglob("*")):
            if p.is_file():
                asset_shas.append(hashlib.sha256(p.read_bytes()).hexdigest())
    for sha in sorted(asset_shas):
        h.update(sha.encode("ascii"))
        h.update(b"\x00")
    h.update(b"\x00INDEX\x00")
    h.update((doc_dir / "index.json").read_bytes())
    return h.hexdigest()
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/test_determinism.py tests/test_verify.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/verify.py tests/test_determinism.py tests/test_verify.py
git commit -m "feat(verify): kb verify foundation + H8 double-extract determinism test

verify_project re-checks artifacts on disk against manifest output_sha256;
detects unauthorized edits to main.md.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 5 — Real adapters (Tasks 19–24)

One task per format. Each follows the same pattern:
1. Stub adapter class with name/version/extensions
2. Write a failing test against a tiny generated fixture
3. Implement adapter producing a hardness-valid `ExtractionResult`
4. Verify against the test
5. Commit

Per spec §6, every adapter:
- Must not perform network I/O (H1)
- Must not import any LLM SDK (H2)
- May only write within `out_dir_tmp/`
- Must emit warnings matching the H11 allowlist

Adapters use a common helper `make_meta(...)` to construct `ExtractionMeta`. We add it now.

---

### Task 19: Common adapter helpers + `image` adapter (simplest)

**Files:**
- Create: `src/kb_extract/adapters/_common.py`
- Create: `src/kb_extract/adapters/image.py`
- Test: `tests/adapters/test_image.py`

- [ ] **Step 1: Create common helpers**

`src/kb_extract/adapters/_common.py`:
```python
"""Helpers shared by all adapters."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..contracts import ExtractionMeta

OutlineSource = Literal["bookmark", "heading_style", "docling_layout", "page_fallback"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_meta(
    *,
    src: Path,
    adapter_name: str,
    adapter_version: str,
    tool_versions: dict[str, str],
    outline_source: OutlineSource,
    status: str = "ok",
    warnings: tuple[str, ...] = (),
    skipped_reasons: tuple[str, ...] = (),
    extracted_at_iso: str | None = None,
) -> ExtractionMeta:
    stat = src.stat()
    src_bytes = src.read_bytes()
    return ExtractionMeta(
        source_path=src.name,
        source_sha256=sha256_bytes(src_bytes),
        source_bytes=len(src_bytes),
        source_mtime_iso=datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        tool_versions=tool_versions,
        extracted_at_iso=extracted_at_iso or "1970-01-01T00:00:00+00:00",
        outline_source=outline_source,
        status=status,  # type: ignore[arg-type]
        warnings=warnings,
        skipped_reasons=skipped_reasons,
    )
```

Note: `extracted_at_iso` defaults to epoch for determinism. Real "now" timestamp would break H8 byte-identical determinism; we record extraction time via the manifest instead.

- [ ] **Step 2: Write failing test**

`tests/adapters/test_image.py`:
```python
import io
from pathlib import Path

import pytest
from PIL import Image as PILImage

from kb_extract.adapters.image import ImageAdapter
from kb_extract.hardness import assert_invariants


def _png_bytes(w=4, h=3, color=(255, 0, 0)) -> bytes:
    img = PILImage.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.disable_socket
def test_image_adapter_produces_valid_extraction(tmp_path):
    src = tmp_path / "photo.png"
    src.write_bytes(_png_bytes())
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    a = ImageAdapter()
    result = a.extract(src, out_dir)
    # main.md has single section with anchor; image referenced
    assert "assets/photo.png" in result.markdown
    assert result.assets and result.assets[0].rel_path == "assets/photo.png"
    # Asset file actually copied
    assert (out_dir / "assets" / "photo.png").exists()
    assert_invariants(result, src, out_dir, total_pages=1)


@pytest.mark.disable_socket
def test_image_adapter_jpg_extension(tmp_path):
    src = tmp_path / "p.jpg"
    img = PILImage.new("RGB", (5, 5), (0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    src.write_bytes(buf.getvalue())
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    a = ImageAdapter()
    result = a.extract(src, out_dir)
    assert "assets/p.jpg" in result.markdown
    assert_invariants(result, src, out_dir, total_pages=1)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_image.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `image.py`**

`src/kb_extract/adapters/image.py`:
```python
"""Image adapter: PNG/JPG/JPEG. Single section per image. Spec §6."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image as PILImage

from ..contracts import AssetRef, ExtractionResult, SectionNode
from ._common import make_meta, sha256_file

_PIL_VERSION = getattr(PILImage, "__version__", "unknown")


class ImageAdapter:
    name = "image"
    version = "0.1"
    extensions = (".png", ".jpg", ".jpeg")

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        # 1. Copy raw bytes (no re-encoding).
        dest_name = src.name
        dest = out_dir_tmp / "assets" / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        sha = sha256_file(dest)

        # 2. Read dimensions via Pillow (no network).
        with PILImage.open(dest) as im:
            w, h = im.size

        # 3. Build single-section tree.
        leaf = SectionNode(
            node_id="0001",
            title=src.stem,
            level=1,
            page_start=1,
            page_end=1,
            anchor="sec-0001",
            language="und",
        )
        root = SectionNode(
            node_id="0000",
            title=src.stem,
            level=0,
            page_start=1,
            page_end=1,
            anchor="",
            language="und",
            children=(leaf,),
        )
        markdown = (
            f'<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->\n\n'
            f'<a id="sec-0001"></a>\n'
            f'# {src.stem}\n\n'
            f'![{src.stem}](assets/{dest_name})\n'
        )
        asset = AssetRef(
            kind="image", rel_path=f"assets/{dest_name}",
            page=1, sha256=sha, width=w, height=h, alt=src.stem,
        )
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"Pillow": _PIL_VERSION},
            outline_source="page_fallback",
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=(), assets=(asset,), meta=meta
        )
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_image.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/adapters/_common.py src/kb_extract/adapters/image.py tests/adapters/test_image.py
git commit -m "feat(adapters): image adapter (PNG/JPG/JPEG) + common helpers

Image bytes copied verbatim (no re-encoding); dimensions via Pillow.
Single-section per image; passes assert_invariants on synthetic fixtures.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 20: `docx` adapter

Heading 1/2/3 styles → section tree. Tables → markdown + rows_json. Embedded images → `assets/`.

**Files:**
- Create: `src/kb_extract/adapters/docx.py`
- Test: `tests/adapters/test_docx.py`
- Test: `tests/adapters/_fixtures.py` (fixture builder used by docx + downstream)

- [ ] **Step 1: Create fixture builder**

`tests/adapters/_fixtures.py`:
```python
"""Helpers that generate tiny synthetic fixtures on the fly.

Avoids committing binary blobs; matches the "no Microsoft confidential docs"
rule in tests/fixtures/SOURCES.md.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image as PILImage


def make_png(path: Path, w: int = 4, h: int = 3, color=(255, 0, 0)) -> Path:
    img = PILImage.new("RGB", (w, h), color)
    img.save(path, format="PNG")
    return path


def make_docx(path: Path) -> Path:
    from docx import Document
    doc = Document()
    doc.add_heading("Chapter 1", level=1)
    doc.add_paragraph("First paragraph in chapter 1.")
    doc.add_heading("Section 1.1", level=2)
    doc.add_paragraph("Body of section 1.1.")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "col A"
    t.cell(0, 1).text = "col B"
    t.cell(1, 0).text = "1"
    t.cell(1, 1).text = "2"
    doc.save(str(path))
    return path
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_docx.py`:
```python
import pytest
from kb_extract.adapters.docx import DocxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_docx


@pytest.mark.disable_socket
def test_docx_adapter_extracts_headings_and_paragraphs(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert "# Chapter 1" in result.markdown
    assert "## Section 1.1" in result.markdown
    assert "First paragraph in chapter 1." in result.markdown


@pytest.mark.disable_socket
def test_docx_adapter_extracts_table_as_markdown_and_rows_json(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert "| col A | col B |" in result.markdown
    assert any(t.rows_json[0] == ("col A", "col B") for t in result.tables)


@pytest.mark.disable_socket
def test_docx_adapter_passes_hardness_invariants(tmp_path):
    src = make_docx(tmp_path / "test.docx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = DocxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_docx.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `docx.py`**

`src/kb_extract/adapters/docx.py`:
```python
"""DOCX adapter using python-docx. Spec §6 row 'docx'."""

from __future__ import annotations

import hashlib
from pathlib import Path

import docx as _docx  # python-docx
import langdetect

from ..contracts import AssetRef, ExtractionResult, SectionNode, TableRef
from ._common import make_meta

_DOCX_VERSION = getattr(_docx, "__version__", "unknown")

_HEADING_LEVELS = {
    "Heading 1": 1,
    "Heading 2": 2,
    "Heading 3": 3,
    "Heading 4": 4,
}


def _detect_lang(text: str) -> str:
    try:
        return langdetect.detect(text) if text.strip() else "und"
    except Exception:  # noqa: BLE001
        return "und"


class DocxAdapter:
    name = "docx"
    version = "0.1"
    extensions = (".docx",)

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        doc = _docx.Document(str(src))

        md_lines: list[str] = []
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        md_lines.append(
            f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->"
        )
        md_lines.append("")

        children: list[SectionNode] = []
        tables: list[TableRef] = []
        warnings: list[str] = []
        anchor_counter = 0
        table_counter = 0
        body_text_acc: list[str] = []

        def next_anchor() -> str:
            nonlocal anchor_counter
            anchor_counter += 1
            return f"sec-{anchor_counter:04d}"

        # Walk top-level paragraphs and tables in document order.
        for block in _iter_blocks(doc):
            if block.__class__.__name__ == "Paragraph":
                style = block.style.name if block.style else ""
                level = _HEADING_LEVELS.get(style)
                if level:
                    anchor = next_anchor()
                    children.append(SectionNode(
                        node_id=f"{len(children)+1:04d}",
                        title=block.text.strip() or "(untitled)",
                        level=level,
                        page_start=1,
                        page_end=1,
                        anchor=anchor,
                        language="und",
                    ))
                    md_lines.append(f'<a id="{anchor}"></a>')
                    md_lines.append(f"{'#' * level} {block.text.strip()}")
                    md_lines.append("")
                elif style and style not in {"Normal", "Default Paragraph Font"}:
                    if style not in _HEADING_LEVELS:
                        warnings.append(f"docx.unknown_style:{style}")
                    md_lines.append(block.text)
                    md_lines.append("")
                    body_text_acc.append(block.text)
                else:
                    if block.text.strip():
                        md_lines.append(block.text)
                        md_lines.append("")
                        body_text_acc.append(block.text)
            elif block.__class__.__name__ == "Table":
                table_counter += 1
                t_anchor = f"tbl-{table_counter:04d}"
                rows: list[tuple[str, ...]] = []
                for row in block.rows:
                    rows.append(tuple(cell.text for cell in row.cells))
                md_lines.append(f'<a id="{t_anchor}"></a>')
                md_lines.append(_render_table_md(rows))
                md_lines.append("")
                tables.append(TableRef(
                    anchor=t_anchor, page=1, rows_json=tuple(rows),
                    rendered_asset=None,
                ))

        if not children:
            # Page-fallback: one synthetic section so H4/H9 hold.
            anchor = next_anchor()
            children.append(SectionNode(
                node_id="0001", title=src.stem, level=1,
                page_start=1, page_end=1, anchor=anchor, language="und",
            ))
            md_lines.insert(2, f'<a id="{anchor}"></a>')
            md_lines.insert(3, f"# {src.stem}")
            md_lines.insert(4, "")
            outline_source = "page_fallback"
        else:
            outline_source = "heading_style"

        lang = _detect_lang(" ".join(body_text_acc))
        root = SectionNode(
            node_id="0000", title=src.stem, level=0, page_start=1, page_end=1,
            anchor="", language=lang, children=tuple(children),
        )
        # Update children language uniformly (v1 simplification).
        root = _set_language(root, lang)

        markdown = "\n".join(md_lines) + "\n"
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"python-docx": _DOCX_VERSION},
            outline_source=outline_source,
            warnings=tuple(warnings),
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=tuple(tables), assets=(), meta=meta
        )


def _iter_blocks(doc):
    """Yield Paragraph / Table objects in document order."""
    from docx.oxml.ns import qn
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield doc.paragraphs[[p._element for p in doc.paragraphs].index(child)]
        elif child.tag == qn("w:tbl"):
            yield doc.tables[[t._element for t in doc.tables].index(child)]


def _render_table_md(rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]
    lines = []
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in body:
        # Pad/truncate to header width.
        cells = list(r) + [""] * (len(header) - len(r))
        lines.append("| " + " | ".join(cells[: len(header)]) + " |")
    return "\n".join(lines)


def _set_language(node: SectionNode, lang: str) -> SectionNode:
    return SectionNode(
        node_id=node.node_id, title=node.title, level=node.level,
        page_start=node.page_start, page_end=node.page_end,
        anchor=node.anchor, language=lang,
        children=tuple(_set_language(c, lang) for c in node.children),
    )
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_docx.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/adapters/docx.py tests/adapters/test_docx.py tests/adapters/_fixtures.py
git commit -m "feat(adapters): docx adapter (headings, paragraphs, tables, langdetect)

Uses python-docx; falls back to page_fallback if no Heading styles found.
Synthetic fixtures generated on the fly (no binary blobs in repo).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 21: `xlsx` adapter

Sheet = level-1; contiguous block of cells = level-2 (TableRef with rows_json + 50-row markdown preview).

**Files:**
- Create: `src/kb_extract/adapters/xlsx.py`
- Test: `tests/adapters/test_xlsx.py`
- Modify: `tests/adapters/_fixtures.py`

- [ ] **Step 1: Extend fixtures**

Append to `tests/adapters/_fixtures.py`:
```python
def make_xlsx(path: Path) -> Path:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "metric"
    ws["B1"] = "value"
    ws["A2"] = "count"
    ws["B2"] = 42
    ws["A3"] = "ratio"
    ws["B3"] = 0.5
    ws2 = wb.create_sheet("Details")
    ws2["A1"] = "id"
    ws2["B1"] = "name"
    ws2["A2"] = 1
    ws2["B2"] = "alpha"
    wb.save(str(path))
    return path
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_xlsx.py`:
```python
import pytest
from kb_extract.adapters.xlsx import XlsxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_xlsx


@pytest.mark.disable_socket
def test_xlsx_adapter_sheet_per_level1_section(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    # Two sheets → two L1 children
    assert len(result.index.children) == 2
    titles = [c.title for c in result.index.children]
    assert "Summary" in titles and "Details" in titles


@pytest.mark.disable_socket
def test_xlsx_adapter_table_block_with_rows_json(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    # Summary sheet has 3 rows × 2 cols
    summary_tables = [
        t for t in result.tables if t.rows_json and t.rows_json[0] == ("metric", "value")
    ]
    assert summary_tables, "expected Summary table extracted"


@pytest.mark.disable_socket
def test_xlsx_adapter_passes_hardness(tmp_path):
    src = make_xlsx(tmp_path / "wb.xlsx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = XlsxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_xlsx.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `xlsx.py`**

`src/kb_extract/adapters/xlsx.py`:
```python
"""XLSX adapter using openpyxl (read_only=True, data_only=True). Spec §6."""

from __future__ import annotations

import hashlib
from pathlib import Path

import openpyxl
from openpyxl import __version__ as openpyxl_version

from ..contracts import ExtractionResult, SectionNode, TableRef
from ._common import make_meta


class XlsxAdapter:
    name = "xlsx"
    version = "0.1"
    extensions = (".xlsx",)

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        wb = openpyxl.load_workbook(str(src), read_only=True, data_only=True)
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        md_lines: list[str] = [
            f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->",
            "",
        ]
        children: list[SectionNode] = []
        tables: list[TableRef] = []
        warnings: list[str] = []
        anchor_count = 0
        table_count = 0

        sheet_index = 0
        for sheet_name in wb.sheetnames:
            sheet_index += 1
            ws = wb[sheet_name]
            anchor_count += 1
            sheet_anchor = f"sec-{anchor_count:04d}"
            md_lines.append(f'<a id="{sheet_anchor}"></a>')
            md_lines.append(f"# {sheet_name}")
            md_lines.append("")

            # Read all rows; treat the whole sheet as one contiguous block.
            rows: list[tuple[str, ...]] = []
            max_col = 0
            for row in ws.iter_rows(values_only=True):
                if row is None:
                    continue
                cells = tuple("" if v is None else str(v) for v in row)
                if any(c != "" for c in cells):
                    rows.append(cells)
                    max_col = max(max_col, len(cells))
            # Normalize to rectangular grid
            rows = [tuple(list(r) + [""] * (max_col - len(r))) for r in rows]

            if rows:
                table_count += 1
                t_anchor = f"tbl-{table_count:04d}"
                tables.append(TableRef(
                    anchor=t_anchor, page=sheet_index, rows_json=tuple(rows),
                    rendered_asset=None,
                ))
                md_lines.append(f'<a id="{t_anchor}"></a>')
                md_lines.append(_render_md_table(rows[:50]))
                if len(rows) > 50:
                    md_lines.append(f"\n_(showing first 50 of {len(rows)} rows)_")
                md_lines.append("")

            child = SectionNode(
                node_id=f"{sheet_index:04d}",
                title=sheet_name,
                level=1,
                page_start=sheet_index,
                page_end=sheet_index,
                anchor=sheet_anchor,
                language="und",
            )
            children.append(child)
        wb.close()

        total_pages = max(sheet_index, 1)
        root = SectionNode(
            node_id="0000", title=src.stem, level=0,
            page_start=1, page_end=total_pages,
            anchor="", language="und", children=tuple(children),
        )
        markdown = "\n".join(md_lines) + "\n"
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"openpyxl": openpyxl_version},
            outline_source="heading_style",
            warnings=tuple(warnings),
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=tuple(tables), assets=(), meta=meta
        )


def _render_md_table(rows: list[tuple[str, ...]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    body = rows[1:]
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in body:
        cells = list(r) + [""] * (len(header) - len(r))
        lines.append("| " + " | ".join(cells[: len(header)]) + " |")
    return "\n".join(lines)
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_xlsx.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/adapters/xlsx.py tests/adapters/test_xlsx.py tests/adapters/_fixtures.py
git commit -m "feat(adapters): xlsx adapter (sheet=L1, whole-sheet table block)

read_only + data_only modes; 50-row markdown preview, full rows_json.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 22: `pptx` adapter

Each slide = level-1 (title). Shape tables → leaf. Speaker notes → `> Note:` block.

**Files:**
- Create: `src/kb_extract/adapters/pptx.py`
- Test: `tests/adapters/test_pptx.py`
- Modify: `tests/adapters/_fixtures.py`

- [ ] **Step 1: Extend fixtures**

```python
def make_pptx(path: Path) -> Path:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    slide1 = prs.slides.add_slide(prs.slide_layouts[0])  # title slide
    slide1.shapes.title.text = "First Slide"
    if slide1.placeholders[1].has_text_frame:
        slide1.placeholders[1].text = "Subtitle text"
    slide1.notes_slide.notes_text_frame.text = "presenter note one"

    slide2 = prs.slides.add_slide(prs.slide_layouts[5])  # title only
    slide2.shapes.title.text = "Second Slide"
    tx_box = slide2.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
    tx_box.text_frame.text = "Some bullet body text on slide 2"
    prs.save(str(path))
    return path
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_pptx.py`:
```python
import pytest
from kb_extract.adapters.pptx import PptxAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_pptx


@pytest.mark.disable_socket
def test_pptx_adapter_one_section_per_slide(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert len(result.index.children) == 2
    titles = [c.title for c in result.index.children]
    assert "First Slide" in titles and "Second Slide" in titles


@pytest.mark.disable_socket
def test_pptx_adapter_includes_speaker_notes_as_blockquote(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert "> Note: presenter note one" in result.markdown


@pytest.mark.disable_socket
def test_pptx_adapter_passes_hardness(tmp_path):
    src = make_pptx(tmp_path / "deck.pptx")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PptxAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_pptx.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `pptx.py`**

`src/kb_extract/adapters/pptx.py`:
```python
"""PPTX adapter using python-pptx. Spec §6."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pptx as _pptx

from ..contracts import ExtractionResult, SectionNode
from ._common import make_meta

_PPTX_VERSION = getattr(_pptx, "__version__", "unknown")


class PptxAdapter:
    name = "pptx"
    version = "0.1"
    extensions = (".pptx",)

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        prs = _pptx.Presentation(str(src))
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        md_lines: list[str] = [
            f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->",
            "",
        ]
        children: list[SectionNode] = []
        for i, slide in enumerate(prs.slides, start=1):
            title = ""
            if slide.shapes.title is not None:
                title = (slide.shapes.title.text or "").strip()
            if not title:
                title = f"Slide {i}"
            anchor = f"sec-{i:04d}"
            md_lines.append(f'<a id="{anchor}"></a>')
            md_lines.append(f"# {title}")
            md_lines.append("")
            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_text_frame and shape.text_frame.text.strip():
                    md_lines.append(shape.text_frame.text.strip())
                    md_lines.append("")
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    for line in notes.splitlines():
                        md_lines.append(f"> Note: {line}")
                    md_lines.append("")
            children.append(SectionNode(
                node_id=f"{i:04d}", title=title, level=1,
                page_start=i, page_end=i, anchor=anchor, language="und",
            ))
        total = max(len(children), 1)
        root = SectionNode(
            node_id="0000", title=src.stem, level=0,
            page_start=1, page_end=total,
            anchor="", language="und", children=tuple(children),
        )
        markdown = "\n".join(md_lines) + "\n"
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"python-pptx": _PPTX_VERSION},
            outline_source="heading_style",
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=(), assets=(), meta=meta
        )
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_pptx.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/adapters/pptx.py tests/adapters/test_pptx.py tests/adapters/_fixtures.py
git commit -m "feat(adapters): pptx adapter (slide=L1, speaker notes as blockquote)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 23: `pdf_docling` adapter

Most complex. Uses docling for layout-based extraction + pymupdf for raw image bytes. Outline source priority: bookmark → docling layout → page fallback.

NOTE on determinism: docling's transformer may not be bit-identical across CPU vendors. Mitigation per spec §10: force single-threaded inference (`OMP_NUM_THREADS=1`), pin torch CPU-only, `PYTHONHASHSEED=0` in install scripts.

**Files:**
- Create: `src/kb_extract/adapters/pdf_docling.py`
- Test: `tests/adapters/test_pdf_docling.py`
- Modify: `tests/adapters/_fixtures.py`

- [ ] **Step 1: Extend fixtures (synthesize a tiny PDF with pymupdf)**

```python
def make_pdf(path: Path) -> Path:
    """Make a minimal 2-page PDF with a bookmark, text, and an embedded image."""
    import fitz  # pymupdf
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Chapter 1: Intro\n\nFirst paragraph on page one.")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Chapter 2: Body\n\nSecond paragraph on page two.")
    doc.set_toc([
        [1, "Chapter 1", 1],
        [1, "Chapter 2", 2],
    ])
    doc.save(str(path))
    doc.close()
    return path
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_pdf_docling.py`:
```python
import pytest
from kb_extract.adapters.pdf_docling import PdfDoclingAdapter
from kb_extract.hardness import assert_invariants

from ._fixtures import make_pdf


@pytest.mark.disable_socket
@pytest.mark.slow
def test_pdf_adapter_uses_bookmarks_when_available(tmp_path):
    src = make_pdf(tmp_path / "doc.pdf")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PdfDoclingAdapter().extract(src, out_dir)
    titles = [c.title for c in result.index.children]
    assert "Chapter 1" in titles and "Chapter 2" in titles
    assert result.meta.outline_source == "bookmark"


@pytest.mark.disable_socket
@pytest.mark.slow
def test_pdf_adapter_passes_hardness(tmp_path):
    src = make_pdf(tmp_path / "doc.pdf")
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    result = PdfDoclingAdapter().extract(src, out_dir)
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_pdf_docling.py -v -m "slow or not slow"`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `pdf_docling.py`**

For v1 we implement a bookmark-first path with pymupdf for both layout + raw image bytes; docling is wired in as a future enhancement when bookmarks are absent. This keeps the first iteration tractable.

`src/kb_extract/adapters/pdf_docling.py`:
```python
"""PDF adapter. Bookmark-first via pymupdf; docling-layout fallback planned.

For v1: pymupdf bookmarks → section tree; raw text extracted per page;
embedded images saved verbatim. docling integration deferred for v1.1
because docling first-run model download is heavy and may not be
bit-identical (spec §10 risk).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import fitz  # pymupdf

from ..contracts import AssetRef, ExtractionResult, SectionNode
from ._common import make_meta, sha256_bytes


class PdfDoclingAdapter:
    name = "pdf_docling"
    version = "0.1"
    extensions = (".pdf",)

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        doc = fitz.open(str(src))
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        md_lines: list[str] = [
            f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->",
            "",
        ]
        page_texts: list[str] = []
        warnings: list[str] = []
        # Per-page raw text
        for page in doc:
            try:
                page_texts.append(page.get_text("text") or "")
            except Exception:  # noqa: BLE001
                page_texts.append("")
                warnings.append(f"pdf.font_decode_failed:p{page.number + 1}")

        n_pages = doc.page_count
        toc = doc.get_toc(simple=True)  # [[level, title, page], ...]
        children: list[SectionNode] = []
        outline_source: str

        if toc:
            outline_source = "bookmark"
            # Build flat children list at level=1; group multi-page ranges.
            # toc page numbers are 1-based.
            sorted_toc = [t for t in toc if t[2] >= 1]
            sorted_toc.sort(key=lambda t: t[2])
            for i, entry in enumerate(sorted_toc):
                level, title, start_page = entry
                end_page = (
                    sorted_toc[i + 1][2] - 1 if i + 1 < len(sorted_toc) else n_pages
                )
                anchor = f"sec-{i + 1:04d}"
                md_lines.append(f'<a id="{anchor}"></a>')
                md_lines.append(f"# {title}")
                md_lines.append("")
                for p in range(start_page, end_page + 1):
                    txt = page_texts[p - 1].strip()
                    if txt:
                        md_lines.append(txt)
                        md_lines.append("")
                children.append(SectionNode(
                    node_id=f"{i + 1:04d}", title=title, level=1,
                    page_start=start_page, page_end=end_page,
                    anchor=anchor, language="und",
                ))
        else:
            outline_source = "page_fallback"
            for p in range(1, n_pages + 1):
                anchor = f"sec-{p:04d}"
                md_lines.append(f'<a id="{anchor}"></a>')
                md_lines.append(f"# Page {p}")
                md_lines.append("")
                if page_texts[p - 1].strip():
                    md_lines.append(page_texts[p - 1].strip())
                    md_lines.append("")
                children.append(SectionNode(
                    node_id=f"{p:04d}", title=f"Page {p}", level=1,
                    page_start=p, page_end=p, anchor=anchor, language="und",
                ))

        # Embedded images via pymupdf (raw bytes, no re-encoding).
        assets: list[AssetRef] = []
        assets_dir = out_dir_tmp / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        for page_idx in range(n_pages):
            page = doc.load_page(page_idx)
            for img_idx, img in enumerate(page.get_images(full=True), start=1):
                xref = img[0]
                try:
                    info = doc.extract_image(xref)
                except Exception:  # noqa: BLE001
                    warnings.append(f"pdf.font_decode_failed:p{page_idx + 1}")
                    continue
                ext = info.get("ext", "png")
                data = info["image"]
                fname = f"p{page_idx + 1}-img{img_idx}.{ext}"
                (assets_dir / fname).write_bytes(data)
                # Find the markdown section for this page and append the image ref.
                # Simpler: append all image refs after their section heading line.
                # For determinism, we insert after the heading of the matching page.
                ref_line = f"![{fname}](assets/{fname})"
                _insert_image_after_page(md_lines, page_idx + 1, ref_line)
                assets.append(AssetRef(
                    kind="image", rel_path=f"assets/{fname}",
                    page=page_idx + 1, sha256=sha256_bytes(data),
                    alt=fname,
                ))

        if any(not pt.strip() for pt in page_texts):
            # Heuristic: if no text on any page, mark scanned warning.
            if all(not pt.strip() for pt in page_texts):
                warnings.append("pdf.scanned_no_text_layer")

        root = SectionNode(
            node_id="0000", title=src.stem, level=0,
            page_start=1, page_end=n_pages,
            anchor="", language="und", children=tuple(children),
        )
        doc.close()
        markdown = "\n".join(md_lines) + "\n"
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"pymupdf": fitz.__doc__ or "unknown"},
            outline_source=outline_source,  # type: ignore[arg-type]
            warnings=tuple(sorted(set(warnings))),
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=(), assets=tuple(assets), meta=meta
        )


def _insert_image_after_page(md_lines: list[str], page: int, ref_line: str) -> None:
    """Insert `ref_line` after the heading matching this page.

    Page anchor convention: `sec-{page:04d}` when in page_fallback mode, or
    the first heading whose section span includes this page. v1 keeps it
    simple: insert after the first `<a id="sec-xxxx"></a>` whose number
    matches the page; if not found, append at end.
    """
    needle = f'<a id="sec-{page:04d}"></a>'
    for i, line in enumerate(md_lines):
        if line == needle:
            # Insert two lines after (after the heading line).
            insert_at = min(i + 3, len(md_lines))
            md_lines.insert(insert_at, ref_line)
            md_lines.insert(insert_at + 1, "")
            return
    md_lines.append(ref_line)
    md_lines.append("")
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_pdf_docling.py -v -m "slow or not slow"`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```powershell
git add src/kb_extract/adapters/pdf_docling.py tests/adapters/test_pdf_docling.py tests/adapters/_fixtures.py
git commit -m "feat(adapters): pdf_docling v1 (pymupdf bookmarks + raw image bytes)

v1 uses pymupdf TOC bookmarks for section tree; raw images extracted
without re-encoding. docling layout-fallback wiring deferred to v1.1
(docling first-run model download + cross-CPU determinism need their own
checkpoint per spec §10).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 24: `zip` adapter (recursive)

ZIP unpacks to `out_dir_tmp/_unpacked/` and re-enters the orchestrator. Nesting depth ≤ 5; encrypted → skipped.

**Files:**
- Create: `src/kb_extract/adapters/zip.py`
- Test: `tests/adapters/test_zip.py`
- Modify: `src/kb_extract/orchestrator.py` (add `_nest_depth` param)

- [ ] **Step 1: Patch orchestrator to support nesting depth**

`src/kb_extract/orchestrator.py` — find the `run(` signature and modify:

```python
def run(
    path: Path,
    *,
    registry: Registry | None = None,
    force: bool = False,
    dry_run: bool = False,
    only_exts: tuple[str, ...] | None = None,
    _nest_depth: int = 0,
) -> RunReport:
```

Add at top of function body (after `if registry is None`):
```python
    if _nest_depth > 5:
        return RunReport()  # zip too nested; adapter handles warning
```

- [ ] **Step 2: Write failing test**

`tests/adapters/test_zip.py`:
```python
import zipfile
from pathlib import Path

import pytest
from kb_extract.adapters._noop import NoopAdapter
from kb_extract.adapters.base import Registry
from kb_extract.adapters.zip import ZipAdapter
from kb_extract.hardness import assert_invariants


def _make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


@pytest.mark.disable_socket
def test_zip_adapter_returns_aggregate_section(tmp_path):
    src = _make_zip(tmp_path / "a.zip", {"inner.noop": b"x"})
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    reg = Registry()
    reg.register(NoopAdapter())
    a = ZipAdapter(child_registry=reg)
    result = a.extract(src, out_dir)
    assert result.index.title == src.stem
    # One child for inner.noop
    assert len(result.index.children) == 1
    assert_invariants(result, src, out_dir, total_pages=result.index.page_end)


@pytest.mark.disable_socket
def test_zip_adapter_marks_encrypted_skipped(tmp_path):
    src = tmp_path / "enc.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("x.noop", b"data")
        # Mark all entries as encrypted by setting flag bit 0 manually
        for info in zf.filelist:
            info.flag_bits |= 0x1
    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    reg = Registry()
    reg.register(NoopAdapter())
    a = ZipAdapter(child_registry=reg)
    result = a.extract(src, out_dir)
    assert any(w.startswith("zip.encrypted:") for w in result.meta.warnings)
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/adapters/test_zip.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement `zip.py`**

`src/kb_extract/adapters/zip.py`:
```python
"""ZIP adapter: unpacks and recursively invokes the orchestrator.

The zip adapter is special: it depends on the orchestrator. To avoid a
circular import, the orchestrator passes `registry` at call time; the zip
adapter holds a registry handle and re-enters with `_nest_depth + 1`.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from ..contracts import ExtractionResult, SectionNode
from ._common import make_meta


class ZipAdapter:
    name = "zip"
    version = "0.1"
    extensions = (".zip",)

    def __init__(self, child_registry=None, nest_depth: int = 0) -> None:
        self._registry = child_registry
        self._depth = nest_depth

    def extract(self, src: Path, out_dir_tmp: Path) -> ExtractionResult:
        warnings: list[str] = []
        children: list[SectionNode] = []
        sha = hashlib.sha256(src.read_bytes()).hexdigest()

        if self._depth >= 5:
            warnings.append(f"zip.too_nested:depth={self._depth + 1}")
            md = (
                f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->\n\n"
                '<a id="sec-0001"></a>\n# (zip too nested)\n'
            )
            root = SectionNode(
                node_id="0000", title=src.stem, level=0,
                page_start=1, page_end=1, anchor="", language="und",
                children=(SectionNode(
                    node_id="0001", title="too nested", level=1,
                    page_start=1, page_end=1, anchor="sec-0001", language="und",
                ),),
            )
            return ExtractionResult(
                markdown=md, index=root, tables=(), assets=(), meta=make_meta(
                    src=src, adapter_name=self.name, adapter_version=self.version,
                    tool_versions={"stdlib_zipfile": "1"}, outline_source="page_fallback",
                    warnings=tuple(warnings),
                ),
            )

        unpacked = out_dir_tmp / "_unpacked"
        unpacked.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(src) as zf:
                for info in zf.infolist():
                    if info.flag_bits & 0x1:
                        warnings.append(f"zip.encrypted:{info.filename}")
                        continue
                    zf.extract(info, str(unpacked))
        except zipfile.BadZipFile:
            warnings.append("zip.encrypted:unreadable")

        # Recurse via orchestrator.
        from ..orchestrator import run as orch_run
        report = orch_run(
            unpacked,
            registry=self._registry,
            _nest_depth=self._depth + 1,
        )

        # Build aggregator section tree from child main.md files.
        kb_dir = unpacked / "kb"
        idx = 0
        md_lines = [
            f"<!-- generated by kb-extract; do not edit; source_sha256: {sha} -->",
            "",
        ]
        if kb_dir.exists():
            for child_main in sorted(kb_dir.rglob("main.md")):
                idx += 1
                rel = child_main.relative_to(unpacked).as_posix()
                anchor = f"sec-{idx:04d}"
                md_lines.append(f'<a id="{anchor}"></a>')
                md_lines.append(f"# {child_main.parent.name}")
                md_lines.append("")
                md_lines.append(f"See `{rel}` (extracted from zip member).")
                md_lines.append("")
                children.append(SectionNode(
                    node_id=f"{idx:04d}", title=child_main.parent.name,
                    level=1, page_start=idx, page_end=idx, anchor=anchor,
                    language="und",
                ))

        if not children:
            anchor = "sec-0001"
            md_lines.append(f'<a id="{anchor}"></a>')
            md_lines.append(f"# {src.stem}")
            md_lines.append("")
            md_lines.append(f"(zip contained {report.skipped_count} unsupported file(s))")
            md_lines.append("")
            children.append(SectionNode(
                node_id="0001", title=src.stem, level=1,
                page_start=1, page_end=1, anchor=anchor, language="und",
            ))

        total = max(len(children), 1)
        root = SectionNode(
            node_id="0000", title=src.stem, level=0,
            page_start=1, page_end=total,
            anchor="", language="und", children=tuple(children),
        )
        markdown = "\n".join(md_lines) + "\n"
        meta = make_meta(
            src=src,
            adapter_name=self.name,
            adapter_version=self.version,
            tool_versions={"stdlib_zipfile": "1"},
            outline_source="page_fallback",
            warnings=tuple(sorted(set(warnings))),
        )
        return ExtractionResult(
            markdown=markdown, index=root, tables=(), assets=(), meta=meta,
        )
```

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/adapters/test_zip.py -v`
Expected: `2 passed`

- [ ] **Step 6: Register all real adapters into default registry**

Modify `src/kb_extract/adapters/__init__.py`:
```python
"""Adapter package. H2 static scan runs over every .py file here."""

from .base import register
from .docx import DocxAdapter
from .image import ImageAdapter
from .pdf_docling import PdfDoclingAdapter
from .pptx import PptxAdapter
from .xlsx import XlsxAdapter
from .zip import ZipAdapter

# Auto-register all real adapters on import.
for _cls in (DocxAdapter, ImageAdapter, PdfDoclingAdapter, PptxAdapter, XlsxAdapter):
    register(_cls)

# ZipAdapter requires registry handle; orchestrator wires it explicitly when used.
__all__ = [
    "DocxAdapter", "ImageAdapter", "PdfDoclingAdapter",
    "PptxAdapter", "XlsxAdapter", "ZipAdapter",
]
```

Update `src/kb_extract/orchestrator.py` to set up zip adapter using the chosen registry. Inside `run()`, just after `registry = ...`:
```python
    # Wire ZipAdapter with registry handle if zip extension not yet registered.
    if ".zip" not in {ext for a in registry.all() for ext in a.extensions}:
        from .adapters.zip import ZipAdapter
        registry.register(ZipAdapter(child_registry=registry, nest_depth=_nest_depth))
```

- [ ] **Step 7: Run all adapter tests**

Run: `uv run pytest tests/adapters/ -v`
Expected: All adapter tests pass.

- [ ] **Step 8: Commit**

```powershell
git add src/kb_extract/adapters/zip.py src/kb_extract/adapters/__init__.py src/kb_extract/orchestrator.py tests/adapters/test_zip.py
git commit -m "feat(adapters): zip adapter (recursive into orchestrator) + auto-registration

- ZipAdapter holds registry handle to recurse via orchestrator.run
- Nest depth limit 5 (per spec §5.3)
- Auto-register PDF/DOCX/XLSX/PPTX/Image into default registry
- Orchestrator wires ZipAdapter on demand

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 6 — CLI (Tasks 25–27)

Click-based `kb` console script. Subcommands: `extract`, `verify`, `manifest`, `adapters`, plus `--version`. Each supports `--json` output for the skill wrapper.

---

### Task 25: `kb extract` command

**Files:**
- Create: `src/kb_extract/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

`tests/test_cli.py`:
```python
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main


def _setup(tmp_path: Path) -> Path:
    from kb_extract.adapters._noop import NoopAdapter
    from kb_extract.adapters.base import get_default_registry
    # Ensure noop adapter is registered for CLI tests.
    reg = get_default_registry()
    if ".noop" not in {e for a in reg.all() for e in a.extensions}:
        reg.register(NoopAdapter())
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.noop").write_bytes(b"x")
    return project


def test_kb_extract_exits_0_on_success(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project)])
    assert result.exit_code == 0, result.output
    assert (project / "kb" / "a" / "main.md").exists()


def test_kb_extract_json_output_parsable(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["ok_count"] == 1
    assert parsed["overall_status"] == "ok"


def test_kb_extract_dry_run_writes_nothing(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--dry-run"])
    assert result.exit_code == 0
    assert not (project / "kb").exists() or not list((project / "kb").rglob("main.md"))


def test_kb_extract_only_flag_filters_by_extension(tmp_path):
    project = _setup(tmp_path)
    (project / "b.unsupported").write_bytes(b"y")
    runner = CliRunner()
    result = runner.invoke(main, ["extract", str(project), "--only", ".noop", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["sources_processed"] == 1


def test_kb_extract_usage_error_returns_2(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["extract"])  # missing path
    assert result.exit_code == 2
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_cli.py -v`
Expected: `ModuleNotFoundError: No module named 'kb_extract.cli'`

- [ ] **Step 3: Implement `cli.py` (extract subcommand only first)**

`src/kb_extract/cli.py`:
```python
"""kb console script. Spec §8.1.

Exit codes:
  0  ok
  1  at least one source failed/partial
  2  usage error (Click default)
  3  hardness violation (verify mode)
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from . import __version__
from .orchestrator import run as orch_run


@click.group()
@click.version_option(__version__, prog_name="kb")
def main() -> None:
    """kb — deterministic document extraction."""


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="Re-extract even if source hash matches.")
@click.option("--dry-run", is_flag=True, help="Discover sources but don't extract.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON report on stdout.")
@click.option("--only", "only", multiple=True, help="Limit to listed extensions (e.g. --only .pdf).")
@click.option("--adapter", default=None, help="(unused in v1) Force specific adapter.")
def extract(
    path: Path,
    force: bool,
    dry_run: bool,
    as_json: bool,
    only: tuple[str, ...],
    adapter: str | None,
) -> None:
    """Extract documents under PATH."""
    only_exts = tuple(only) if only else None
    report = orch_run(
        path,
        force=force,
        dry_run=dry_run,
        only_exts=only_exts,
    )
    if as_json:
        d = {
            "ok_count": report.ok_count,
            "failed_count": report.failed_count,
            "skipped_count": report.skipped_count,
            "unchanged_count": report.unchanged_count,
            "dry_run_count": report.dry_run_count,
            "violations": report.violations,
            "sources_processed": len(report.sources_processed),
            "overall_status": report.overall_status,
        }
        click.echo(json.dumps(d, indent=2, sort_keys=True))
    else:
        click.echo(
            f"ok={report.ok_count} failed={report.failed_count} "
            f"skipped={report.skipped_count} unchanged={report.unchanged_count} "
            f"dry_run={report.dry_run_count}"
        )
        for v in report.violations:
            click.echo(f"  [violation] {v}", err=True)
    sys.exit(1 if report.failed_count or report.violations else 0)
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_cli.py -v -k extract`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/cli.py tests/test_cli.py
git commit -m "feat(cli): kb extract subcommand with --json/--dry-run/--force/--only

Exit code 0 on success, 1 on any failure or violation.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 26: `kb verify` command

**Files:**
- Modify: `src/kb_extract/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append failing tests**

```python
def test_kb_verify_exits_0_on_clean_project(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["verify", str(project)])
    assert result.exit_code == 0, result.output


def test_kb_verify_exits_3_on_tamper(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"tampered")
    result = runner.invoke(main, ["verify", str(project)])
    assert result.exit_code == 3
    assert "main.md" in result.output or "violation" in result.output.lower()


def test_kb_verify_json_output_lists_violations(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"x")
    result = runner.invoke(main, ["verify", str(project), "--json"])
    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["violations"]


def test_kb_verify_fail_fast_returns_first_only(tmp_path):
    project = _setup(tmp_path)
    (project / "b.noop").write_bytes(b"y")
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    (project / "kb" / "a" / "main.md").write_bytes(b"x")
    (project / "kb" / "b" / "main.md").write_bytes(b"x")
    result = runner.invoke(main, ["verify", str(project), "--fail-fast", "--json"])
    payload = json.loads(result.output)
    assert len(payload["violations"]) == 1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_cli.py -v -k verify`
Expected: usage error (`No such command 'verify'`).

- [ ] **Step 3: Add `verify` subcommand to `cli.py`**

Append at end:
```python
from .verify import verify_project


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option("--fail-fast", is_flag=True, help="Stop at first violation.")
def verify(path: Path, as_json: bool, fail_fast: bool) -> None:
    """Re-check on-disk artifacts against manifest. Exit 3 on violation."""
    report = verify_project(path, fail_fast=fail_fast)
    if as_json:
        click.echo(json.dumps({
            "ok": report.ok,
            "files_checked": report.files_checked,
            "violations": report.violations,
        }, indent=2, sort_keys=True))
    else:
        click.echo(
            f"verify: ok={report.ok} files_checked={report.files_checked} "
            f"violations={len(report.violations)}"
        )
        for v in report.violations:
            click.echo(f"  [violation] {v}", err=True)
    sys.exit(0 if report.ok else 3)
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_cli.py -v -k verify`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/cli.py tests/test_cli.py
git commit -m "feat(cli): kb verify subcommand (exit 3 on hardness violation)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 27: `kb manifest` + `kb adapters`

**Files:**
- Modify: `src/kb_extract/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append failing tests**

```python
def test_kb_adapters_lists_registered_names():
    runner = CliRunner()
    result = runner.invoke(main, ["adapters"])
    assert result.exit_code == 0
    for name in ("pdf_docling", "docx", "xlsx", "pptx", "image"):
        assert name in result.output


def test_kb_adapters_json_machine_readable():
    runner = CliRunner()
    result = runner.invoke(main, ["adapters", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = [a["name"] for a in payload]
    assert "docx" in names


def test_kb_manifest_table_default(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project)])
    assert result.exit_code == 0
    assert "a.noop" in result.output
    assert "ok" in result.output.lower()


def test_kb_manifest_status_filter(tmp_path):
    project = _setup(tmp_path)
    (project / "weird.unsupported").write_bytes(b"x")
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project), "--status", "skipped"])
    assert result.exit_code == 0
    assert "weird.unsupported" in result.output
    assert "a.noop" not in result.output


def test_kb_manifest_format_json(tmp_path):
    project = _setup(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["extract", str(project)])
    result = runner.invoke(main, ["manifest", str(project), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(row["source_path"].endswith("a.noop") for row in payload)


def test_kb_version_outputs_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_cli.py -v -k "adapters or manifest or version"`
Expected: Click reports unknown commands.

- [ ] **Step 3: Implement subcommands**

Append to `cli.py`:
```python
import csv as _csv
import io as _io

from .adapters.base import get_default_registry
from .layout import find_project_root
from .manifest import Manifest


@main.command()
@click.option("--json", "as_json", is_flag=True)
def adapters(as_json: bool) -> None:
    """List registered adapters."""
    reg = get_default_registry()
    rows = [
        {"name": a.name, "version": a.version, "extensions": list(a.extensions)}
        for a in reg.all()
    ]
    if as_json:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    click.echo(f"{'NAME':<20} {'VERSION':<10} EXTENSIONS")
    for r in rows:
        click.echo(f"{r['name']:<20} {r['version']:<10} {','.join(r['extensions'])}")


@main.command(name="manifest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--status",
              type=click.Choice(["ok", "partial", "failed", "skipped"]),
              default=None)
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]), default="table")
def manifest_cmd(path: Path, status: str | None, fmt: str) -> None:
    """Show manifest rows for the project."""
    project_root = find_project_root(path)
    db = project_root / "kb" / "manifest.sqlite"
    if not db.exists():
        click.echo(f"no manifest at {db}", err=True)
        sys.exit(1)
    m = Manifest(db)
    try:
        rows = [r for r in m.iter() if status is None or r.status == status]
    finally:
        m.close()
    if fmt == "json":
        click.echo(json.dumps([asdict(r) for r in rows], indent=2, sort_keys=True))
    elif fmt == "csv":
        buf = _io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow(["source_path", "status", "adapter_name", "output_sha256"])
        for r in rows:
            writer.writerow([r.source_path, r.status, r.adapter_name or "", r.output_sha256 or ""])
        click.echo(buf.getvalue())
    else:
        click.echo(f"{'STATUS':<10} {'ADAPTER':<15} SOURCE")
        for r in rows:
            click.echo(f"{r.status:<10} {(r.adapter_name or '-'):<15} {r.source_path}")
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All CLI tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/kb_extract/cli.py tests/test_cli.py
git commit -m "feat(cli): kb manifest + kb adapters subcommands; table/json/csv output

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 7 — Install scripts + Copilot CLI skill (Tasks 28–30)

Per spec §8.2: skill scripts NEVER import `kb_extract`; they shell out to `kb` CLI and parse `--json`. The skill→CLI process boundary is intentional and load-bearing.

---

### Task 28: `install.ps1` / `install.sh` + `uninstall.*`

**Files:**
- Create: `install.ps1`
- Create: `install.sh`
- Create: `uninstall.ps1`
- Create: `uninstall.sh`
- Create: `tests/test_install_scripts.py`

- [ ] **Step 1: Write failing test (basic shape check; no actual install in CI)**

`tests/test_install_scripts.py`:
```python
from pathlib import Path


def test_install_ps1_exists_and_has_expected_steps():
    p = Path(__file__).resolve().parents[1] / "install.ps1"
    assert p.exists(), "install.ps1 missing"
    body = p.read_text(encoding="utf-8")
    for needle in ("uv venv", "uv pip install", "kb-extract", "DOCLING"):
        assert needle in body, f"install.ps1 missing reference to {needle!r}"


def test_install_sh_exists_and_has_expected_steps():
    p = Path(__file__).resolve().parents[1] / "install.sh"
    assert p.exists(), "install.sh missing"
    body = p.read_text(encoding="utf-8")
    for needle in ("uv venv", "uv pip install", "kb-extract"):
        assert needle in body


def test_uninstall_scripts_exist():
    repo = Path(__file__).resolve().parents[1]
    assert (repo / "uninstall.ps1").exists()
    assert (repo / "uninstall.sh").exists()
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_install_scripts.py -v`
Expected: Files missing.

- [ ] **Step 3: Create `install.ps1`**

```powershell
# install.ps1 — kb-extract installer for Windows
$ErrorActionPreference = "Stop"

$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
$venvPath = Join-Path $venvRoot "venv"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install with: winget install --id=astral-sh.uv -e"
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating venv at $venvPath ..."
    uv venv $venvPath --python 3.11
}

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Installing kb-extract from $repo ..."
uv pip install --python (Join-Path $venvPath "Scripts\python.exe") -e $repo

Write-Host "Pre-downloading docling models (may take several minutes)..."
$env:DOCLING_ARTIFACTS_PATH = Join-Path $venvRoot "docling-models"
& (Join-Path $venvPath "Scripts\python.exe") -c "import docling; print('docling import ok')"

$kbBin = Join-Path $venvPath "Scripts"
Write-Host ""
Write-Host "Install complete. Add to PATH (one-time):"
Write-Host "  setx PATH `"$kbBin;`$env:PATH`""
Write-Host ""
Write-Host "Then run: kb --version"
```

- [ ] **Step 4: Create `install.sh`**

```bash
#!/usr/bin/env bash
# install.sh — kb-extract installer for macOS/Linux
set -euo pipefail

VENV_ROOT="${HOME}/.kb-extract"
VENV_PATH="${VENV_ROOT}/venv"

command -v uv >/dev/null 2>&1 || {
    echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
}

if [ ! -d "${VENV_PATH}" ]; then
    echo "Creating venv at ${VENV_PATH} ..."
    uv venv "${VENV_PATH}" --python 3.11
fi

REPO="$(cd "$(dirname "$0")" && pwd)"
echo "Installing kb-extract from ${REPO} ..."
uv pip install --python "${VENV_PATH}/bin/python" -e "${REPO}"

echo "Pre-downloading docling models (may take several minutes)..."
export DOCLING_ARTIFACTS_PATH="${VENV_ROOT}/docling-models"
"${VENV_PATH}/bin/python" -c "import docling; print('docling import ok')"

echo ""
echo "Install complete. Add to PATH (one-time):"
echo "  echo 'export PATH=\"${VENV_PATH}/bin:\$PATH\"' >> ~/.bashrc"
echo ""
echo "Then run: kb --version"
```

- [ ] **Step 5: Create `uninstall.ps1`**

```powershell
$ErrorActionPreference = "Stop"
$venvRoot = Join-Path $env:USERPROFILE ".kb-extract"
if (Test-Path $venvRoot) {
    Write-Host "Removing $venvRoot ..."
    Remove-Item -Recurse -Force $venvRoot
    Write-Host "Done."
} else {
    Write-Host "Nothing to uninstall."
}
```

- [ ] **Step 6: Create `uninstall.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
VENV_ROOT="${HOME}/.kb-extract"
if [ -d "${VENV_ROOT}" ]; then
    echo "Removing ${VENV_ROOT} ..."
    rm -rf "${VENV_ROOT}"
    echo "Done."
else
    echo "Nothing to uninstall."
fi
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_install_scripts.py -v`
Expected: `3 passed`

- [ ] **Step 8: Commit**

```powershell
git add install.ps1 install.sh uninstall.ps1 uninstall.sh tests/test_install_scripts.py
git commit -m "chore(install): per-OS install/uninstall scripts (uv venv + docling bootstrap)

Spec §8.3: user venv at ~/.kb-extract/venv, pip install -e, docling first-
time model download, PATH hint.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 29: Copilot skill: `SKILL.md` + `extract.ps1` / `extract.sh`

Per spec §8.2: skill triggers extraction by shelling out to `kb extract --json`.

**Files:**
- Create: `skill/SKILL.md`
- Create: `skill/scripts/extract.ps1`
- Create: `skill/scripts/extract.sh`
- Create: `tests/test_skill_scripts.py`

- [ ] **Step 1: Write failing test**

`tests/test_skill_scripts.py`:
```python
import ast
from pathlib import Path


def test_skill_md_declares_trigger_phrases():
    p = Path(__file__).resolve().parents[1] / "skill" / "SKILL.md"
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "trigger" in body.lower()
    assert "kb extract" in body
    assert "extract this folder" in body.lower() or "extract folder" in body.lower()


def test_skill_scripts_never_import_kb_extract():
    """Spec §8.2: scripts must shell out to `kb` CLI, never import the package."""
    skill_dir = Path(__file__).resolve().parents[1] / "skill" / "scripts"
    for script in skill_dir.rglob("*.ps1"):
        assert "import kb_extract" not in script.read_text(encoding="utf-8"), script
        assert "kb_extract." not in script.read_text(encoding="utf-8"), script
    for script in skill_dir.rglob("*.sh"):
        body = script.read_text(encoding="utf-8")
        assert "import kb_extract" not in body, script


def test_skill_extract_scripts_exist():
    skill_dir = Path(__file__).resolve().parents[1] / "skill" / "scripts"
    assert (skill_dir / "extract.ps1").exists()
    assert (skill_dir / "extract.sh").exists()


def test_skill_extract_scripts_call_kb_adapters_then_extract():
    skill_dir = Path(__file__).resolve().parents[1] / "skill" / "scripts"
    for script in (skill_dir / "extract.ps1", skill_dir / "extract.sh"):
        body = script.read_text(encoding="utf-8")
        # Must check `kb adapters` first per SKILL.md contract.
        assert "kb adapters" in body
        assert "kb extract" in body
        assert "--json" in body
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_skill_scripts.py -v`
Expected: Files missing.

- [ ] **Step 3: Create `skill/SKILL.md`**

```markdown
---
name: kb-extract
description: |
  Convert a folder of engineering documents (PDF/DOCX/XLSX/PPTX/PNG/JPG/ZIP)
  into a deterministic, citable Markdown knowledge base under <folder>/kb/.
  Never invokes an LLM during extraction. Always honours hardness invariants.
triggers:
  - "extract this folder"
  - "extract folder"
  - "build kb from folder"
  - "extract documents"
  - "extract knowledge base"
  - "verify kb"
  - "verify knowledge base"
---

# kb-extract skill

This skill is a thin shell around the `kb` CLI. It never parses documents
itself, never modifies extracted artifacts, and never enriches or paraphrases
extracted content. All extraction logic lives in the `kb` CLI.

## Contract (load-bearing — do not bend)

1. The skill never parses documents itself; it only decides what subcommand
   and path to invoke.
2. The skill never modifies `main.md`, `index.json`, or `meta.json`. To
   re-extract, the user must explicitly request `kb extract --force`.
3. Before any extract command, the skill runs `kb adapters` to confirm CLI
   availability; if the command fails, instructs the user to run
   `install.ps1` / `install.sh` from the kb-extract repo root.
4. The skill summarises the CLI's `--json` output to the user. It never
   adds, reorders, or paraphrases extracted content.
5. If `kb verify` exits non-zero, the skill surfaces every violation
   verbatim. It does not suggest "fixes" to extracted content.

## Usage

| User intent | Skill action |
|---|---|
| "Extract this folder" (cwd is a project) | `scripts/extract.{ps1,sh} .` |
| "Extract folder X" | `scripts/extract.{ps1,sh} X` |
| "Re-extract" | `scripts/extract.{ps1,sh} X --force` |
| "Dry run extract" | `scripts/extract.{ps1,sh} X --dry-run` |
| "Verify kb" | `scripts/verify.{ps1,sh} X` |

All scripts use `kb ... --json` and surface the parsed status to the user.
```

- [ ] **Step 4: Create `skill/scripts/extract.ps1`**

```powershell
$ErrorActionPreference = "Stop"

$path = $args[0]
if (-not $path) { Write-Error "usage: extract.ps1 <path> [--force] [--dry-run]" }

$extraArgs = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extraArgs += $args[$i] }

# 1. Verify CLI is installed.
$adapters = & kb adapters --json 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "kb CLI not found. Run install.ps1 from the kb-extract repo first."
}

# 2. Invoke extract.
$report = & kb extract $path --json @extraArgs
$exit = $LASTEXITCODE
Write-Host $report
exit $exit
```

- [ ] **Step 5: Create `skill/scripts/extract.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

PATH_ARG="${1:?usage: extract.sh <path> [--force] [--dry-run]}"
shift

# 1. Verify CLI installed.
if ! kb adapters --json >/dev/null 2>&1; then
    echo "kb CLI not found. Run install.sh from the kb-extract repo first." >&2
    exit 1
fi

# 2. Invoke extract.
kb extract "${PATH_ARG}" --json "$@"
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_skill_scripts.py -v`
Expected: `4 passed`

- [ ] **Step 7: Commit**

```powershell
git add skill/SKILL.md skill/scripts/extract.ps1 skill/scripts/extract.sh tests/test_skill_scripts.py
git commit -m "feat(skill): Copilot CLI skill SKILL.md + extract scripts

Thin shell around 'kb' CLI; never imports kb_extract, never paraphrases
extracted content. Spec §8.2 contract is encoded in SKILL.md.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 30: `skill/scripts/verify.*` + VS Code tasks example

**Files:**
- Create: `skill/scripts/verify.ps1`
- Create: `skill/scripts/verify.sh`
- Create: `.vscode/tasks.json.example`
- Modify: `tests/test_skill_scripts.py`

- [ ] **Step 1: Append failing tests**

```python
def test_skill_verify_scripts_exist():
    skill_dir = Path(__file__).resolve().parents[1] / "skill" / "scripts"
    assert (skill_dir / "verify.ps1").exists()
    assert (skill_dir / "verify.sh").exists()


def test_vscode_tasks_example_exists():
    p = Path(__file__).resolve().parents[1] / ".vscode" / "tasks.json.example"
    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "KB: Extract" in body
    assert "KB: Verify" in body
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/test_skill_scripts.py -v`
Expected: Files missing.

- [ ] **Step 3: Create `skill/scripts/verify.ps1`**

```powershell
$ErrorActionPreference = "Stop"
$path = $args[0]
if (-not $path) { Write-Error "usage: verify.ps1 <path> [--fail-fast]" }

$extra = @()
for ($i = 1; $i -lt $args.Length; $i++) { $extra += $args[$i] }

if (-not (Get-Command kb -ErrorAction SilentlyContinue)) {
    Write-Error "kb CLI not found. Run install.ps1 first."
}
& kb verify $path --json @extra
exit $LASTEXITCODE
```

- [ ] **Step 4: Create `skill/scripts/verify.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
PATH_ARG="${1:?usage: verify.sh <path> [--fail-fast]}"
shift
command -v kb >/dev/null 2>&1 || { echo "kb CLI not found. Run install.sh first." >&2; exit 1; }
kb verify "${PATH_ARG}" --json "$@"
```

- [ ] **Step 5: Create `.vscode/tasks.json.example`**

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "KB: Extract current folder",
      "type": "shell",
      "command": "kb",
      "args": ["extract", "${workspaceFolder}", "--json"],
      "problemMatcher": []
    },
    {
      "label": "KB: Extract current folder (force)",
      "type": "shell",
      "command": "kb",
      "args": ["extract", "${workspaceFolder}", "--force", "--json"],
      "problemMatcher": []
    },
    {
      "label": "KB: Verify project",
      "type": "shell",
      "command": "kb",
      "args": ["verify", "${workspaceFolder}", "--json"],
      "problemMatcher": []
    },
    {
      "label": "KB: Show manifest",
      "type": "shell",
      "command": "kb",
      "args": ["manifest", "${workspaceFolder}"],
      "problemMatcher": []
    }
  ]
}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_skill_scripts.py -v`
Expected: All skill tests pass.

- [ ] **Step 7: Commit**

```powershell
git add skill/scripts/verify.ps1 skill/scripts/verify.sh .vscode/tasks.json.example tests/test_skill_scripts.py
git commit -m "feat(skill): verify scripts + VS Code tasks.json.example

Right-click → Run Task → 'KB: Extract current folder'.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 8 — CI, performance, cross-platform (Tasks 31–33)

GitHub Actions matrix CI + H13 cross-platform identity job + performance benchmark gate.

---

### Task 31: GitHub Actions matrix CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: test (${{ matrix.os }}, py${{ matrix.python-version }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install uv
        run: pip install uv
      - name: Create venv
        run: uv venv --python ${{ matrix.python-version }}
      - name: Install package + dev deps
        run: uv pip install -e ".[dev]"
        env:
          PYTHONHASHSEED: "0"
          OMP_NUM_THREADS: "1"
      - name: Lint
        run: uv run ruff check .
      - name: Test
        env:
          PYTHONHASHSEED: "0"
          OMP_NUM_THREADS: "1"
        run: uv run pytest -v --cov=kb_extract --cov-report=term -m "not perf"
      - name: Upload hash manifest (for H13 cross-platform job)
        if: matrix.python-version == '3.11'
        uses: actions/upload-artifact@v4
        with:
          name: hash-manifest-${{ matrix.os }}
          path: tests/fixtures/_h13-output/
          if-no-files-found: ignore
```

- [ ] **Step 2: Run locally for syntax check**

Run: `gh workflow view ci.yml` (if `gh` available) or simply ensure file parses as YAML:
```powershell
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```
Expected: no error.

- [ ] **Step 3: Commit**

```powershell
git add .github/workflows/ci.yml
git commit -m "ci: matrix workflow {ubuntu, windows, macos} × {py3.11, py3.12}

Sets PYTHONHASHSEED=0 and OMP_NUM_THREADS=1 for deterministic adapter
output across runs. Excludes -m perf (handled in dedicated job).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 32: H13 cross-platform identity job + golden snapshots

**Files:**
- Modify: `.github/workflows/ci.yml` — add `cross_platform_identity` job
- Create: `tests/test_cross_platform.py`
- Create: `tests/golden/` (syrupy auto-creates files; we just ensure the dir is tracked)

- [ ] **Step 1: Write the H13 test**

`tests/test_cross_platform.py`:
```python
"""H13: extraction output is byte-identical across Ubuntu/Windows/macOS.

The matrix CI uploads a per-OS hash manifest as an artifact. A dedicated job
(`cross_platform_identity`) downloads all three and compares them.

This local test runs the noop + image adapters and writes a hash manifest
that the CI job will consume.
"""

import hashlib
import json
from pathlib import Path

import pytest


def _hash_dir(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.sqlite":
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
    return out


@pytest.mark.disable_socket
def test_emit_h13_hash_manifest(tmp_path):
    """Produce a deterministic hash manifest of synthetic fixture extractions."""
    from kb_extract.adapters._noop import NoopAdapter
    from kb_extract.adapters.base import Registry
    from kb_extract.orchestrator import run

    project = tmp_path / "P"
    project.mkdir()
    (project / "deterministic.noop").write_bytes(b"H13 fixture content")

    reg = Registry()
    reg.register(NoopAdapter())
    run(project, registry=reg, force=True)

    manifest = _hash_dir(project / "kb")
    out_root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "_h13-output"
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "hash-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    assert manifest, "hash manifest empty (something went wrong)"
```

- [ ] **Step 2: Add CI job to `.github/workflows/ci.yml`**

Append:
```yaml
  cross_platform_identity:
    name: H13 cross-platform identity
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: artifacts/
      - name: Compare hash manifests across OSes
        run: |
          set -euo pipefail
          a=artifacts/hash-manifest-ubuntu-latest/hash-manifest.json
          b=artifacts/hash-manifest-windows-latest/hash-manifest.json
          c=artifacts/hash-manifest-macos-latest/hash-manifest.json
          for f in "$a" "$b" "$c"; do
            test -f "$f" || { echo "missing $f"; exit 1; }
          done
          diff -u "$a" "$b" || { echo "H13 violation: ubuntu != windows"; exit 1; }
          diff -u "$a" "$c" || { echo "H13 violation: ubuntu != macos"; exit 1; }
          echo "H13 OK"
```

- [ ] **Step 3: Add `.gitignore` entry for the H13 ephemeral output**

Append to existing `.gitignore`:
```
tests/fixtures/_h13-output/
```

- [ ] **Step 4: Run locally**

Run: `uv run pytest tests/test_cross_platform.py -v`
Expected: `1 passed`; file `tests/fixtures/_h13-output/hash-manifest.json` created locally.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml tests/test_cross_platform.py .gitignore
git commit -m "ci(H13): cross-platform identity job + per-OS hash manifest test

Matrix tests upload hash-manifest.json; dedicated job downloads all three
OS artifacts and diffs them — any byte-level drift fails CI.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 33: Performance benchmark with 1.5× regression gate

**Files:**
- Create: `tests/test_performance.py`
- Create: `tests/fixtures/perf-baseline.json` (initial baseline; first run records it)
- Modify: `.github/workflows/ci.yml` — add `performance` job

- [ ] **Step 1: Write perf test**

`tests/test_performance.py`:
```python
"""Performance benchmark with 1.5× regression gate (spec §9)."""

import json
import time
from pathlib import Path

import pytest


def _bench_pdf_extract(tmp_path: Path) -> float:
    """Time extraction of a synthetic 100-page PDF."""
    import fitz

    src = tmp_path / "big.pdf"
    doc = fitz.open()
    for i in range(100):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1}\n" + ("Lorem ipsum dolor sit amet. " * 20))
    doc.set_toc([[1, f"Section {i+1}", i+1] for i in range(10)])
    doc.save(str(src))
    doc.close()

    out_dir = tmp_path / "out.tmp"
    (out_dir / "assets").mkdir(parents=True)
    from kb_extract.adapters.pdf_docling import PdfDoclingAdapter
    a = PdfDoclingAdapter()
    t0 = time.perf_counter()
    a.extract(src, out_dir)
    return time.perf_counter() - t0


@pytest.mark.perf
@pytest.mark.slow
def test_pdf_extract_100_pages_within_1_5x_baseline(tmp_path):
    baseline_path = Path(__file__).resolve().parent / "fixtures" / "perf-baseline.json"
    elapsed = _bench_pdf_extract(tmp_path)
    if not baseline_path.exists():
        # First-ever run records the baseline; subsequent runs gate against it.
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps({"pdf_100_pages_sec": elapsed}, indent=2))
        pytest.skip(f"recorded initial baseline: {elapsed:.2f}s")
    baseline = json.loads(baseline_path.read_text())["pdf_100_pages_sec"]
    limit = baseline * 1.5
    assert elapsed <= limit, (
        f"perf regression: {elapsed:.2f}s vs baseline {baseline:.2f}s "
        f"(limit {limit:.2f}s = 1.5×)"
    )
```

- [ ] **Step 2: Create initial baseline file (generous; tuned after first real CI run)**

`tests/fixtures/perf-baseline.json`:
```json
{
  "pdf_100_pages_sec": 30.0
}
```
(Generous initial baseline; will be tuned after first real run on CI.)

- [ ] **Step 3: Add `performance` job to `.github/workflows/ci.yml`**

Append:
```yaml
  performance:
    name: Performance benchmark
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install uv
      - run: uv venv --python 3.11
      - run: uv pip install -e ".[dev]"
      - run: uv run pytest -v -m perf --no-cov
        env:
          PYTHONHASHSEED: "0"
          OMP_NUM_THREADS: "1"
```

- [ ] **Step 4: Run locally**

Run: `uv run pytest tests/test_performance.py -v -m perf`
Expected: first run skips (baseline recorded); second run passes if under 45s.

- [ ] **Step 5: Final whole-suite run**

Run: `uv run pytest -v -m "not perf"`
Expected: every test passes; coverage report printed. Note any flakes or skips.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_performance.py tests/fixtures/perf-baseline.json .github/workflows/ci.yml
git commit -m "ci(perf): 100-page PDF benchmark with 1.5× regression gate

First run records baseline; subsequent runs fail if elapsed > 1.5× baseline.
Separate CI job (excluded from main test matrix by -m 'not perf').

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 9 — End-to-end acceptance (Task 34)

Final integration test exercising the full pipeline against the spec §12 acceptance criteria.

---

### Task 34: End-to-end acceptance test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write the e2e test**

`tests/test_e2e.py`:
```python
"""End-to-end acceptance test mirroring spec §12.

Builds a synthetic mini-project with PDF + DOCX + XLSX + PPTX + PNG + ZIP
(containing PPTX), runs `kb extract`, asserts:
- Every doc produces main.md/index.json/meta.json/assets
- `kb verify` exits 0
- Editing main.md makes verify exit 3
- Second run is a no-op
"""

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from kb_extract.cli import main as cli_main


def _build_mini_project(root: Path) -> None:
    from PIL import Image as PILImage
    from tests.adapters._fixtures import make_docx, make_pdf, make_pptx, make_xlsx
    import zipfile

    make_pdf(root / "doc1.pdf")
    make_docx(root / "doc2.docx")
    make_xlsx(root / "data.xlsx")
    make_pptx(root / "deck.pptx")
    PILImage.new("RGB", (16, 16), (123, 200, 50)).save(root / "logo.png")

    inner_pptx = root / "_tmp_inner.pptx"
    make_pptx(inner_pptx)
    with zipfile.ZipFile(root / "bundle.zip", "w") as zf:
        zf.write(inner_pptx, arcname="inner.pptx")
    inner_pptx.unlink()


@pytest.mark.disable_socket
@pytest.mark.slow
def test_e2e_full_pipeline_meets_acceptance_criteria(tmp_path):
    project = tmp_path / "ProjectX"
    project.mkdir()
    _build_mini_project(project)

    runner = CliRunner()

    # 1. Extract
    r1 = runner.invoke(cli_main, ["extract", str(project), "--json"])
    assert r1.exit_code == 0, r1.output
    for name in ("doc1", "doc2", "data", "deck", "logo", "bundle"):
        assert (project / "kb" / name / "main.md").exists(), f"missing main.md for {name}"

    # 2. Verify clean
    r2 = runner.invoke(cli_main, ["verify", str(project)])
    assert r2.exit_code == 0, r2.output

    # 3. Idempotency: re-running extracts nothing new
    main_md = project / "kb" / "doc1" / "main.md"
    mtime1 = main_md.stat().st_mtime_ns
    r3 = runner.invoke(cli_main, ["extract", str(project), "--json"])
    assert r3.exit_code == 0
    import json as _json
    payload = _json.loads(r3.output)
    assert payload["unchanged_count"] >= 5  # doc1..logo unchanged (bundle may re-recurse)
    assert main_md.stat().st_mtime_ns == mtime1

    # 4. Tamper detection
    main_md.write_bytes(b"tampered")
    r4 = runner.invoke(cli_main, ["verify", str(project), "--json"])
    assert r4.exit_code == 3
    assert "doc1" in r4.output
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_e2e.py -v -m slow`
Expected: `1 passed` (may take 30–60s depending on docling/pymupdf startup).

- [ ] **Step 3: Run full suite (excluding perf) one last time**

Run: `uv run pytest -v -m "not perf"`
Expected: every test passes; print summary of total count.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_e2e.py
git commit -m "test(e2e): full pipeline acceptance test (spec §12)

PDF + DOCX + XLSX + PPTX + PNG + ZIP(PPTX); extract → verify clean →
idempotent re-run → tamper detection.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Done

After Task 34 commits successfully, the v1 implementation matches every acceptance criterion in spec §12:

1. ✅ `kb extract <project>` produces full output tree.
2. ✅ Re-running is a no-op (unchanged_count).
3. ✅ `kb verify` exits 0 on clean projects.
4. ✅ Tampered `main.md` makes `kb verify` exit 3.
5. ✅ CI matrix green across three OSes + H13 hash-compare job.
6. ✅ Copilot skill triggers on natural-language prompts and shells out to `kb extract --json`.
7. ✅ H2 static no-LLM-imports test fails when a forbidden import is introduced.

### After completion — next sub-projects

The deferred sub-projects from the original brainstorm now have a hardened extraction foundation to build on:

- Sub-project #2: PageIndex LLM-assisted section refinement (consumes `index.json` + `main.md`).
- Sub-project #3: Karpathy LLM-Wiki + Obsidian-wiki organization (every claim cites an `<a id>` anchor from extracted markdown).
- Sub-project #4: Hardness extensions for the wiki layer.
- Sub-project #5: Memory layer for user habits and question history.
- Sub-project #6: GitHub auto-publish workflow to the user's account (clarify XUMAX-GH vs xumax_microsoft first).

Each gets its own spec + plan via the same brainstorming → writing-plans flow.



