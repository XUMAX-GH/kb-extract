# kb source (markitdown source.md) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `kb source` command that converts each original input file to a readable, image-free, redacted, byte-reproducible `source.md` via the embedded markitdown library, with its own idempotency manifest, without touching the deterministic `kb extract` core.

**Architecture:** A new core module `source_md.py` is the only place that imports markitdown; it exposes pure helpers (`strip_images`) plus a single-file converter and a batch `run_source` orchestrator. A separate `source_manifest.py` (SQLite at `kb/source.manifest.sqlite`) provides idempotency. A thin `kb source` CLI command delegates to `run_source`. Redaction text rules are reused from the existing `redaction` module.

**Tech Stack:** Python 3.11, Click, markitdown, SQLite (stdlib), uv, pytest, ruff.

**PREREQUISITE:** This plan builds on SP-1 (redaction layer, PR #1). It reuses `kb_extract.redaction` (`RedactionPolicy`, `load_policy`, text rules). Implement only after SP-1 is merged to `main`, and branch off the updated `main` (where `pyproject.toml` version is `0.11.0`). All commands below assume `uv run`.

---

## File Structure

- Create `src/kb_extract/source_md.py` — markitdown seam, `strip_images`, `SourceStats`, `convert_one`, `SourceReport`, `run_source`.
- Create `src/kb_extract/source_manifest.py` — `SourceManifest` SQLite wrapper for `kb/source.manifest.sqlite`.
- Modify `src/kb_extract/redaction.py` — add public `redact_text(text, policy)` helper.
- Modify `src/kb_extract/serialization.py` — add `serialize_source_meta_json(...)`.
- Modify `src/kb_extract/cli.py` — add `kb source` command.
- Create `tests/test_source_md.py` — unit + integration tests.
- Modify `pyproject.toml` (dependency + version), `README.md`, `CHANGELOG.md`.

---

## Task 1: Add markitdown dependency and the image-stripping helper

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Create: `src/kb_extract/source_md.py`
- Test: `tests/test_source_md.py`

- [ ] **Step 1: Add the dependency**

Run: `uv add markitdown`
Expected: `pyproject.toml` `dependencies` gains a `markitdown>=...` entry and `uv.lock` updates. Then confirm an HTML conversion works offline:

Run:
```
uv run python -c "from markitdown import MarkItDown; print(MarkItDown(enable_plugins=False).convert_local('README.md').text_content[:40])"
```
Expected: prints the first chars of README with no network error. If `convert_local` is unavailable in the installed version, use `.convert('README.md')` instead and adjust the seam in Step 3 accordingly. If HTML conversion later fails for missing extras, run `uv add 'markitdown[all]'`.

- [ ] **Step 2: Write the failing test for `strip_images`**

Create `tests/test_source_md.py`:

```python
from kb_extract.source_md import strip_images


def test_strip_images_removes_markdown_images_and_counts():
    md = (
        "# Title\n\n"
        "Intro text.\n\n"
        "![company logo](assets/logo.png)\n\n"
        "Body with inline ![x](data:image/png;base64,AAAA) image.\n\n"
        '<img src="banner.png" alt="b"/>\n'
    )
    out, count = strip_images(md)
    assert "logo.png" not in out
    assert "base64" not in out
    assert "<img" not in out
    assert "# Title" in out
    assert "Intro text." in out
    assert count == 3
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_source_md.py -k strip_images -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` (`strip_images` not defined).

- [ ] **Step 4: Create `source_md.py` with the seam and `strip_images`**

Create `src/kb_extract/source_md.py`:

```python
"""kb source layer (SP-2): markitdown -> image-free, redacted source.md.

markitdown is imported ONLY in this module (never under adapters/), so the
adapter-only LLM-import scan is unaffected. Conversion of local files needs
no network.
"""

from __future__ import annotations

import re

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def strip_images(markdown: str) -> tuple[str, int]:
    """Remove all markdown and HTML image references; return (text, count)."""
    text, n1 = _MD_IMAGE_RE.subn("", markdown)
    text, n2 = _HTML_IMG_RE.subn("", text)
    return text, n1 + n2
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_source_md.py -k strip_images -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/kb_extract/source_md.py tests/test_source_md.py
git commit -m "feat(source): add markitdown dep and image-stripping helper (SP-2 1/6)"
```

---

## Task 2: Reusable text redaction helper + single-file converter

**Files:**
- Modify: `src/kb_extract/redaction.py` (add `redact_text`)
- Modify: `src/kb_extract/source_md.py` (add `SourceStats`, `_markitdown_convert`, `convert_one`)
- Test: `tests/test_source_md.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_source_md.py`:

```python
from kb_extract.redaction import RedactionPolicy, TextRule
from kb_extract import source_md


def _policy():
    return RedactionPolicy(
        enabled=True,
        text_rules=(TextRule(pattern=r"(?i)\b[MH]\d{6,8}\b", replacement="[PN-REDACTED]"),),
        logo_sha256=(), logo_filename_globs=(), logo_alt_globs=(),
        policy_sha256="d" * 64,
    )


def test_convert_one_strips_images_and_redacts(monkeypatch, tmp_path):
    raw = (
        "# Doc M1320001\n\n"
        "Part M1320001 is secret.\n\n"
        "![logo](assets/logo.png)\n"
    )
    monkeypatch.setattr(source_md, "_markitdown_convert", lambda src: raw)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    text, stats = source_md.convert_one(src, _policy())
    assert "M1320001" not in text
    assert "[PN-REDACTED]" in text
    assert "logo.png" not in text
    assert text.endswith("\n") and "\r" not in text  # normalized
    assert stats.images_stripped == 1
    assert stats.pn_redacted == 2


def test_convert_one_without_policy_keeps_text_strips_images(monkeypatch, tmp_path):
    raw = "# Doc\n\nPart M1320001 stays.\n\n![logo](assets/logo.png)\n"
    monkeypatch.setattr(source_md, "_markitdown_convert", lambda src: raw)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    text, stats = source_md.convert_one(src, None)
    assert "M1320001" in text  # no policy -> text unchanged
    assert "logo.png" not in text  # images always stripped
    assert stats.pn_redacted == 0
    assert stats.images_stripped == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_md.py -k convert_one -v`
Expected: FAIL (`convert_one`/`_markitdown_convert`/`redact_text` not defined).

- [ ] **Step 3: Add `redact_text` to `redaction.py`**

In `src/kb_extract/redaction.py`, add after `_apply_text_rules` (which already exists):

```python
def redact_text(text: str, policy: RedactionPolicy) -> tuple[str, int]:
    """Apply a policy's text rules to a plain string. Returns (text, count)."""
    return _apply_text_rules(text, policy.text_rules)
```

- [ ] **Step 4: Add converter to `source_md.py`**

In `src/kb_extract/source_md.py`, add imports and code:

```python
from dataclasses import dataclass
from pathlib import Path

from .redaction import RedactionPolicy, redact_text
from .serialization import serialize_markdown


@dataclass(frozen=True, slots=True)
class SourceStats:
    images_stripped: int
    pn_redacted: int


def _markitdown_convert(src: Path) -> str:
    """Seam around markitdown; monkeypatched in tests. Local-only, no network."""
    from markitdown import MarkItDown

    return MarkItDown(enable_plugins=False).convert_local(str(src)).text_content


def convert_one(
    src: Path, policy: RedactionPolicy | None
) -> tuple[str, SourceStats]:
    """Convert one local file to a normalized, image-free, redacted source.md."""
    raw = _markitdown_convert(src)
    text, images = strip_images(raw)
    pn = 0
    if policy is not None and policy.enabled:
        text, pn = redact_text(text, policy)
    text = serialize_markdown(text)
    return text, SourceStats(images_stripped=images, pn_redacted=pn)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_source_md.py -k "convert_one or strip_images" -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/kb_extract/redaction.py src/kb_extract/source_md.py tests/test_source_md.py
git commit -m "feat(source): single-file markitdown converter with redaction (SP-2 2/6)"
```

---

## Task 3: source.meta.json serializer

**Files:**
- Modify: `src/kb_extract/serialization.py`
- Test: `tests/test_source_md.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_source_md.py`:

```python
import json
from kb_extract.serialization import serialize_source_meta_json


def test_serialize_source_meta_json_sorted_counts_only():
    out = serialize_source_meta_json(
        source_path="sub/doc.docx",
        source_sha256="a" * 64,
        source_bytes=10,
        source_mtime_iso="t",
        markitdown_version="0.0.1",
        source_md_sha256="b" * 64,
        images_stripped=2,
        pn_redacted=3,
        policy_sha256="c" * 64,
        generated_at_iso="t2",
    )
    assert out.endswith("\n")
    d = json.loads(out)
    assert d["images_stripped"] == 2
    assert d["pn_redacted"] == 3
    assert d["policy_sha256"] == "c" * 64
    assert d["source_md_sha256"] == "b" * 64
    assert set(d.keys()) == {
        "generated_at_iso", "images_stripped", "markitdown_version",
        "pn_redacted", "policy_sha256", "source_bytes", "source_md_sha256",
        "source_mtime_iso", "source_path", "source_sha256",
    }
    # keys sorted
    assert out.index("generated_at_iso") < out.index("source_sha256")


def test_serialize_source_meta_json_null_policy():
    out = serialize_source_meta_json(
        source_path="d.docx", source_sha256="a" * 64, source_bytes=1,
        source_mtime_iso="t", markitdown_version="0.0.1",
        source_md_sha256="b" * 64, images_stripped=0, pn_redacted=0,
        policy_sha256=None, generated_at_iso="t2",
    )
    assert json.loads(out)["policy_sha256"] is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_md.py -k serialize_source_meta -v`
Expected: FAIL (`serialize_source_meta_json` not defined).

- [ ] **Step 3: Implement the serializer**

In `src/kb_extract/serialization.py`, add (reuse the existing module-level `_json_dumps`):

```python
def serialize_source_meta_json(
    *,
    source_path: str,
    source_sha256: str,
    source_bytes: int,
    source_mtime_iso: str,
    markitdown_version: str,
    source_md_sha256: str,
    images_stripped: int,
    pn_redacted: int,
    policy_sha256: str | None,
    generated_at_iso: str,
) -> str:
    """Canonical source.md sidecar. Only counts/hashes, never redacted values."""
    return _json_dumps(
        {
            "generated_at_iso": generated_at_iso,
            "images_stripped": images_stripped,
            "markitdown_version": markitdown_version,
            "pn_redacted": pn_redacted,
            "policy_sha256": policy_sha256,
            "source_bytes": source_bytes,
            "source_md_sha256": source_md_sha256,
            "source_mtime_iso": source_mtime_iso,
            "source_path": source_path,
            "source_sha256": source_sha256,
        }
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_md.py -k serialize_source_meta -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/serialization.py tests/test_source_md.py
git commit -m "feat(source): source.meta.json serializer (SP-2 3/6)"
```

---

## Task 4: source.manifest.sqlite wrapper

**Files:**
- Create: `src/kb_extract/source_manifest.py`
- Test: `tests/test_source_md.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_source_md.py`:

```python
from kb_extract.source_manifest import SourceManifest, SourceRow


def test_source_manifest_upsert_get_and_idempotency(tmp_path):
    db = tmp_path / "kb" / "source.manifest.sqlite"
    m = SourceManifest(db)
    src = tmp_path / "doc.docx"
    src.write_bytes(b"x")
    m.upsert_ok(
        src,
        source_sha256="a" * 64, source_bytes=1, source_mtime_iso="t",
        markitdown_version="0.0.1", source_md_sha256="b" * 64,
        images_stripped=1, pn_redacted=2, policy_sha256="c" * 64,
        generated_at_iso="t2",
    )
    row = m.get(src)
    assert isinstance(row, SourceRow)
    assert row.status == "ok"
    assert row.source_sha256 == "a" * 64
    assert row.policy_sha256 == "c" * 64
    assert row.markitdown_version == "0.0.1"
    m.close()


def test_source_manifest_mark_failed(tmp_path):
    db = tmp_path / "kb" / "source.manifest.sqlite"
    m = SourceManifest(db)
    src = tmp_path / "bad.docx"
    src.write_bytes(b"x")
    m.mark_failed(src, "boom")
    row = m.get(src)
    assert row.status == "failed"
    assert row.error_repr == "boom"
    m.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_md.py -k source_manifest -v`
Expected: FAIL (`SourceManifest` not defined).

- [ ] **Step 3: Implement `source_manifest.py`**

Create `src/kb_extract/source_manifest.py`:

```python
"""Per-project SQLite manifest for the kb source layer (SP-2).

Physically separate from extract's manifest.sqlite; this file lives at
kb/source.manifest.sqlite and is never touched by `kb extract`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Status = Literal["ok", "failed", "skipped"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    key                TEXT PRIMARY KEY,
    source_path        TEXT,
    source_sha256      TEXT,
    source_bytes       INTEGER,
    source_mtime_iso   TEXT,
    markitdown_version TEXT,
    source_md_sha256   TEXT,
    images_stripped    INTEGER,
    pn_redacted        INTEGER,
    policy_sha256      TEXT,
    status             TEXT NOT NULL,
    error_repr         TEXT,
    generated_at_iso   TEXT
);
"""


@dataclass(frozen=True, slots=True)
class SourceRow:
    source_path: str
    source_sha256: str | None
    source_bytes: int | None
    source_mtime_iso: str | None
    markitdown_version: str | None
    source_md_sha256: str | None
    images_stripped: int | None
    pn_redacted: int | None
    policy_sha256: str | None
    status: Status
    error_repr: str | None
    generated_at_iso: str | None


class SourceManifest:
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

    def upsert_ok(
        self,
        src: Path,
        *,
        source_sha256: str,
        source_bytes: int,
        source_mtime_iso: str,
        markitdown_version: str,
        source_md_sha256: str,
        images_stripped: int,
        pn_redacted: int,
        policy_sha256: str | None,
        generated_at_iso: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(
                    key, source_path, source_sha256, source_bytes,
                    source_mtime_iso, markitdown_version, source_md_sha256,
                    images_stripped, pn_redacted, policy_sha256, status,
                    error_repr, generated_at_iso
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    source_path=excluded.source_path,
                    source_sha256=excluded.source_sha256,
                    source_bytes=excluded.source_bytes,
                    source_mtime_iso=excluded.source_mtime_iso,
                    markitdown_version=excluded.markitdown_version,
                    source_md_sha256=excluded.source_md_sha256,
                    images_stripped=excluded.images_stripped,
                    pn_redacted=excluded.pn_redacted,
                    policy_sha256=excluded.policy_sha256,
                    status='ok',
                    error_repr=NULL,
                    generated_at_iso=excluded.generated_at_iso
                """,
                (
                    self._key(src), src.resolve().as_posix(), source_sha256,
                    source_bytes, source_mtime_iso, markitdown_version,
                    source_md_sha256, images_stripped, pn_redacted,
                    policy_sha256, "ok", None, generated_at_iso,
                ),
            )

    def mark_failed(self, src: Path, error_repr: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(key, source_path, status, error_repr)
                VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    status='failed', error_repr=excluded.error_repr
                """,
                (self._key(src), src.resolve().as_posix(), "failed", error_repr),
            )

    def mark_skipped(self, src: Path, reason: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(key, source_path, status, error_repr)
                VALUES (?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    status='skipped', error_repr=excluded.error_repr
                """,
                (self._key(src), src.resolve().as_posix(), "skipped", reason),
            )

    def get(self, src: Path) -> SourceRow | None:
        cur = self.conn.execute(
            "SELECT * FROM sources WHERE key = ?", (self._key(src),)
        )
        row = cur.fetchone()
        if row is None:
            return None
        d = {cur.description[i][0]: row[i] for i in range(len(cur.description))}
        return SourceRow(
            source_path=d["source_path"],
            source_sha256=d.get("source_sha256"),
            source_bytes=d.get("source_bytes"),
            source_mtime_iso=d.get("source_mtime_iso"),
            markitdown_version=d.get("markitdown_version"),
            source_md_sha256=d.get("source_md_sha256"),
            images_stripped=d.get("images_stripped"),
            pn_redacted=d.get("pn_redacted"),
            policy_sha256=d.get("policy_sha256"),
            status=d["status"],
            error_repr=d.get("error_repr"),
            generated_at_iso=d.get("generated_at_iso"),
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_md.py -k source_manifest -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/source_manifest.py tests/test_source_md.py
git commit -m "feat(source): source.manifest.sqlite wrapper (SP-2 4/6)"
```

---

## Task 5: Batch orchestrator `run_source`

**Files:**
- Modify: `src/kb_extract/source_md.py` (add `SourceReport`, `run_source`)
- Test: `tests/test_source_md.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_source_md.py`:

```python
from kb_extract import source_md as _sm


def _fake_convert_factory(text_by_name):
    def _convert(src):
        return text_by_name[src.name]
    return _convert


def test_run_source_writes_source_md_and_sidecar(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    (project / "redaction.toml").write_text(
        "[redaction]\nenabled = true\n[[redaction.text]]\n"
        "pattern = '(?i)\\b[MH]\\d{6,8}\\b'\nreplacement = \"[PN-REDACTED]\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A M1320001\n\n![l](x.png)\nBody.\n"}),
    )
    report = _sm.run_source(project)
    out = project / "kb" / "a"
    sm_text = (out / "source.md").read_text(encoding="utf-8")
    assert "M1320001" not in sm_text
    assert "x.png" not in sm_text
    assert (out / "source.meta.json").exists()
    assert report.ok_count == 1
    assert report.pn_redacted == 1
    assert report.images_stripped == 1


def test_run_source_is_idempotent_second_run_unchanged(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A\n\nBody.\n"}),
    )
    _sm.run_source(project)
    report2 = _sm.run_source(project)
    assert report2.unchanged_count == 1
    assert report2.ok_count == 0


def test_run_source_reprocesses_with_force(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert",
        _fake_convert_factory({"a.docx": "# A\n\nBody.\n"}),
    )
    _sm.run_source(project)
    report2 = _sm.run_source(project, force=True)
    assert report2.ok_count == 1
    assert report2.unchanged_count == 0


def test_run_source_one_bad_file_does_not_abort(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    (project / "b.docx").write_bytes(b"bbb")

    def _convert(src):
        if src.name == "b.docx":
            raise RuntimeError("cannot convert")
        return "# A\n\nBody.\n"

    monkeypatch.setattr(_sm, "_markitdown_convert", _convert)
    report = _sm.run_source(project)
    assert report.ok_count == 1
    assert report.failed_count == 1
    assert (project / "kb" / "a" / "source.md").exists()


def test_run_source_deterministic_bytes_two_projects(monkeypatch, tmp_path):
    raw = "# A M1320001\r\n\r\n![l](x.png)\r\nBody.\r\n"  # CRLF to prove normalization
    monkeypatch.setattr(
        _sm, "_markitdown_convert", lambda src: raw,
    )

    def build(name):
        p = tmp_path / name
        p.mkdir()
        (p / "a.docx").write_bytes(b"aaa")
        return p

    p1, p2 = build("P1"), build("P2")
    _sm.run_source(p1)
    _sm.run_source(p2)
    b1 = (p1 / "kb" / "a" / "source.md").read_bytes()
    b2 = (p2 / "kb" / "a" / "source.md").read_bytes()
    assert b1 == b2
    assert b"\r" not in b1


def test_run_source_dry_run_writes_nothing(monkeypatch, tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(
        _sm, "_markitdown_convert", lambda src: "# A\n\nBody.\n",
    )
    report = _sm.run_source(project, dry_run=True)
    assert not (project / "kb" / "a" / "source.md").exists()
    assert report.dry_run_count == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_md.py -k run_source -v`
Expected: FAIL (`run_source`/`SourceReport` not defined).

- [ ] **Step 3: Implement `run_source` in `source_md.py`**

Add to `src/kb_extract/source_md.py` (extend the existing imports as shown):

```python
import hashlib
from datetime import datetime, timezone
from importlib.metadata import version as _pkg_version

from .discovery import discover_sources
from .layout import find_project_root, kb_dir, target_dir
from .redaction import load_policy
from .serialization import serialize_source_meta_json
from .source_manifest import SourceManifest


def _markitdown_version() -> str:
    try:
        return _pkg_version("markitdown")
    except Exception:
        return "unknown"


@dataclass(frozen=True, slots=True)
class SourceReport:
    ok_count: int
    failed_count: int
    skipped_count: int
    unchanged_count: int
    dry_run_count: int
    pn_redacted: int
    images_stripped: int
    overall_status: str


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_source(
    path: Path,
    *,
    output_dir: Path | None = None,
    redaction_policy: Path | None = None,
    no_redaction: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> SourceReport:
    """Generate source.md for every discovered file under `path`."""
    project_root = find_project_root(path)
    policy = None if no_redaction else load_policy(project_root, redaction_policy)
    policy_sha = policy.policy_sha256 if (policy and policy.enabled) else None
    md_version = _markitdown_version()

    ok = failed = skipped = unchanged = dry = 0
    pn_total = img_total = 0

    manifest = None
    if not dry_run:
        manifest = SourceManifest(kb_dir(project_root, output_dir) / "source.manifest.sqlite")
    try:
        for src in discover_sources(path):
            raw_bytes = src.read_bytes()
            src_sha = _sha256_bytes(raw_bytes)
            out_dir = target_dir(project_root, src, output_dir)
            source_md_path = out_dir / "source.md"

            if not dry_run and not force and source_md_path.exists() and manifest is not None:
                prev = manifest.get(src)
                if (
                    prev is not None
                    and prev.status == "ok"
                    and prev.source_sha256 == src_sha
                    and prev.markitdown_version == md_version
                    and prev.policy_sha256 == policy_sha
                ):
                    unchanged += 1
                    continue

            try:
                text, stats = convert_one(src, policy)
            except Exception as e:  # one bad file must not abort the batch
                failed += 1
                if manifest is not None:
                    manifest.mark_failed(src, repr(e))
                continue

            pn_total += stats.pn_redacted
            img_total += stats.images_stripped

            if dry_run:
                dry += 1
                continue

            out_dir.mkdir(parents=True, exist_ok=True)
            data = text.encode("utf-8")
            source_md_path.write_bytes(data)
            sidecar = serialize_source_meta_json(
                source_path=src.resolve().as_posix(),
                source_sha256=src_sha,
                source_bytes=len(raw_bytes),
                source_mtime_iso=datetime.fromtimestamp(
                    src.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                markitdown_version=md_version,
                source_md_sha256=_sha256_bytes(data),
                images_stripped=stats.images_stripped,
                pn_redacted=stats.pn_redacted,
                policy_sha256=policy_sha,
                generated_at_iso=datetime.now(tz=timezone.utc).isoformat(),
            )
            (out_dir / "source.meta.json").write_bytes(sidecar.encode("utf-8"))
            if manifest is not None:
                manifest.upsert_ok(
                    src,
                    source_sha256=src_sha,
                    source_bytes=len(raw_bytes),
                    source_mtime_iso=datetime.fromtimestamp(
                        src.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    markitdown_version=md_version,
                    source_md_sha256=_sha256_bytes(data),
                    images_stripped=stats.images_stripped,
                    pn_redacted=stats.pn_redacted,
                    policy_sha256=policy_sha,
                    generated_at_iso=datetime.now(tz=timezone.utc).isoformat(),
                )
            ok += 1
    finally:
        if manifest is not None:
            manifest.close()

    overall = "ok" if failed == 0 else "partial"
    return SourceReport(
        ok_count=ok, failed_count=failed, skipped_count=skipped,
        unchanged_count=unchanged, dry_run_count=dry, pn_redacted=pn_total,
        images_stripped=img_total, overall_status=overall,
    )
```

Note: the `redaction.toml` policy file itself is discovered as a source by `discover_sources`. markitdown will convert it as plain text; that is acceptable (it produces `kb/redaction/source.md`). If you prefer to skip it, that is out of scope for SP-2 — do not add filtering here.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_md.py -k run_source -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the full source test file + ruff**

Run: `uv run pytest tests/test_source_md.py -v`
Expected: PASS (all tasks 1-5 tests).
Run: `uv run ruff check src/kb_extract/source_md.py src/kb_extract/source_manifest.py`
Expected: `All checks passed!` (fix any lint inline, e.g. unused imports).

- [ ] **Step 6: Commit**

```bash
git add src/kb_extract/source_md.py tests/test_source_md.py
git commit -m "feat(source): run_source batch orchestrator with idempotency (SP-2 5/6)"
```

---

## Task 6: CLI command, import-isolation guard, docs, version bump

**Files:**
- Modify: `src/kb_extract/cli.py`
- Test: `tests/test_source_md.py` (guard test), `tests/test_cli.py` (smoke)
- Modify: `README.md`, `CHANGELOG.md`, `pyproject.toml`

- [ ] **Step 1: Write the failing guard + CLI smoke tests**

Append to `tests/test_source_md.py`:

```python
import ast
from pathlib import Path as _P


def test_markitdown_imported_only_in_source_md():
    src_root = _P("src/kb_extract")
    offenders = []
    for py in src_root.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "markitdown" in text and py.name != "source_md.py":
            offenders.append(py.as_posix())
    assert offenders == [], f"markitdown imported outside source_md.py: {offenders}"


def test_source_md_imports_no_llm_sdk():
    import kb_extract.source_md as mod
    tree = ast.parse(_P(mod.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    forbidden = {"openai", "anthropic", "litellm", "langchain", "transformers"}
    assert not (names & forbidden)
```

Append to `tests/test_cli.py` (use the existing `CliRunner` import pattern already in that file):

```python
def test_cli_source_smoke(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from kb_extract.cli import main
    from kb_extract import source_md as _sm

    project = tmp_path / "P"
    project.mkdir()
    (project / "a.docx").write_bytes(b"aaa")
    monkeypatch.setattr(_sm, "_markitdown_convert", lambda src: "# A\n\nBody.\n")
    result = CliRunner().invoke(main, ["source", str(project)])
    assert result.exit_code == 0
    assert "ok=1" in result.output
    assert (project / "kb" / "a" / "source.md").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_md.py -k "guard or no_llm or imported_only" tests/test_cli.py -k source_smoke -v`
Expected: the CLI smoke test FAILS (`No such command 'source'`). The two guard tests should already PASS (they reflect Task 1-5 code). If a guard test fails, STOP and fix the offending import.

- [ ] **Step 3: Add the `kb source` command to `cli.py`**

In `src/kb_extract/cli.py`, add an import near the top with the other `from .` imports:

```python
from .source_md import run_source
```

Then add this command after the `extract` command definition:

```python
@main.command(name="source")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="即使源文件 hash 未变也重新生成 source.md。")
@click.option("--dry-run", is_flag=True, help="仅转换不写盘。")
@click.option("--json", "as_json", is_flag=True, help="在标准输出打印 JSON 报告。")
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path), default=None,
    help="将 kb/ 写入此目录（而不是源所在目录）。",
)
@click.option(
    "--redaction-policy", "redaction_policy",
    type=click.Path(path_type=Path), default=None,
    help="脱敏策略文件路径（默认自动发现项目根的 redaction.toml）。",
)
@click.option("--no-redaction", is_flag=True, help="即使发现 redaction.toml 也强制关闭脱敏。")
def source(
    path: Path,
    force: bool,
    dry_run: bool,
    as_json: bool,
    output_dir: Path | None,
    redaction_policy: Path | None,
    no_redaction: bool,
) -> None:
    """用 markitdown 为 PATH 下的文档生成可读的 source.md 源文件。"""
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()
    report = run_source(
        path,
        output_dir=output_dir,
        redaction_policy=redaction_policy,
        no_redaction=no_redaction,
        force=force,
        dry_run=dry_run,
    )
    if as_json:
        d = {
            "ok_count": report.ok_count,
            "failed_count": report.failed_count,
            "skipped_count": report.skipped_count,
            "unchanged_count": report.unchanged_count,
            "dry_run_count": report.dry_run_count,
            "pn_redacted": report.pn_redacted,
            "images_stripped": report.images_stripped,
            "overall_status": report.overall_status,
            "output_dir": str(output_dir) if output_dir else None,
        }
        click.echo(json.dumps(d, indent=2, sort_keys=True))
    else:
        click.echo(
            f"ok={report.ok_count} failed={report.failed_count} "
            f"skipped={report.skipped_count} unchanged={report.unchanged_count} "
            f"dry_run={report.dry_run_count} "
            f"redacted_pn={report.pn_redacted} images_stripped={report.images_stripped}"
        )
    exit_code = 1 if report.failed_count else 0
    _record_history(
        path, "source",
        {"force": force, "dry_run": dry_run,
         "output_dir": str(output_dir) if output_dir else None,
         "no_redaction": no_redaction},
        exit_code,
        f"ok={report.ok_count} failed={report.failed_count}",
    )
    sys.exit(exit_code)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_md.py tests/test_cli.py -k "source or guard or no_llm" -v`
Expected: PASS.

- [ ] **Step 5: Bump version and update docs**

In `pyproject.toml`, change `version = "0.11.0"` to `version = "0.12.0"`. In `src/kb_extract/__init__.py`, update `__version__` to `"0.12.0"` (match how SP-1 updated it).

In `README.md`, update the version badge `version-0.11.0` to `version-0.12.0`, and add a section after the redaction section:

```markdown
## source.md 源文件层（kb source）

`kb source` 用嵌入的 markitdown 把原始文件转换为一份完整、易读的
`source.md`（写在 `kb/<doc>/source.md`），作为人类阅读与后续归纳的源文件。
它与确定性的 `kb extract` 完全独立，不修改抽取产物：

```bash
kb source .                 # 为当前目录下所有文档生成 source.md
kb source . --no-redaction  # 不脱敏
kb source . --json          # 结构化报告
```

特性：

- **始终无图**：所有图片引用都会被移除，杜绝 logo 泄漏，保证可读纯文本。
- **料号脱敏**：若存在 `redaction.toml`，正文中的料号会按规则脱敏
  （复用 `kb extract` 的同一策略）。
- **确定性 + 幂等**：输出经归一化（LF / 无 BOM），对同一输入与同一
  markitdown 版本 byte-identical；`kb/source.manifest.sqlite` 记录哈希，
  未变更的文件再次运行记为 `unchanged`。
- 每份文档附带 `source.meta.json` 侧车（只含哈希与计数，不含被脱敏原值）。
```

In `CHANGELOG.md`, add at the top below the header line:

```markdown
## [0.12.0] - 2026-06-24

### Added
- `kb source` command (SP-2): converts each input file to a readable,
  image-free, redacted `source.md` via the embedded markitdown library.
  Output is normalized and byte-reproducible for a fixed markitdown version;
  idempotency is tracked in a separate `kb/source.manifest.sqlite` with a
  per-document counts-only `source.meta.json` sidecar. The deterministic
  `kb extract` core and `kb verify` are untouched. markitdown is imported only
  in `source_md.py`, preserving the adapter LLM-import invariant.
```

- [ ] **Step 6: Full verification**

Run: `uv run pytest`
Expected: ALL tests pass.
Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/kb_extract/cli.py src/kb_extract/__init__.py tests/test_source_md.py tests/test_cli.py README.md CHANGELOG.md pyproject.toml
git commit -m "feat(source): kb source CLI, guards, docs, v0.12.0 bump (SP-2 6/6)"
```

---

## Final Verification (after Task 6)

- [ ] Run `uv run pytest` -> all green.
- [ ] Run `uv run ruff check .` -> clean.
- [ ] Run `uv run kb source --help` (or `uv run python -m kb_extract.cli source --help`) -> shows the new flags.
- [ ] Dispatch a comprehensive code review of the whole SP-2 diff (base = SP-2 branch point, head = final commit), focusing on: markitdown isolated to `source_md.py`; offline/no-socket in tests; byte-reproducible normalization; idempotency-key correctness; sidecar counts-only (no leaked values); `kb extract`/`kb verify` untouched.
- [ ] Invoke `superpowers:finishing-a-development-branch` to open a PR (per AGENTS.md "走 PR").
