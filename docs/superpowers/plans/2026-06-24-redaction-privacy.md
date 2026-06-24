# SP-1 Deterministic Redaction / Privacy Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, deterministic redaction layer that strips part-number text (e.g. `M132xxxx` / `H123xxxx`) and drops logo images from extraction output before it is written to disk, driven by a `redaction.toml` policy.

**Architecture:** A pure `redaction.py` module (no LLM, no network) loads a TOML policy, applies regex text substitutions and sha256/glob logo dropping to an `ExtractionResult`, and returns a redacted result plus counts. The orchestrator applies it just before `_write_result_to_disk`, deletes dropped asset files, and writes a counts-only `redaction.json` audit sidecar. When no policy is present, behavior is byte-identical to today (no regression).

**Tech Stack:** Python 3.11+ (stdlib `tomllib`, `re`, `fnmatch`, `hashlib`, `dataclasses`), Click CLI, pytest (socket disabled by default).

**Spec:** `docs/superpowers/specs/2026-06-24-redaction-privacy-design.md`

---

## File Structure

- Create: `src/kb_extract/redaction.py` — policy model, `load_policy`, `apply_to_result` (the whole feature's logic).
- Modify: `src/kb_extract/errors.py` — add `RedactionPolicyError`.
- Modify: `src/kb_extract/serialization.py` — add `serialize_redaction_json`.
- Modify: `src/kb_extract/orchestrator.py` — load policy, apply before write, delete dropped assets, write sidecar, count in `RunReport`.
- Modify: `src/kb_extract/cli.py` — `--redaction-policy` / `--no-redaction` flags + report fields.
- Create: `tests/test_redaction.py` — unit + integration tests.
- Modify: `README.md`, `CHANGELOG.md`, `pyproject.toml` — docs + version bump to 0.11.0.

Run the full suite with `uv run pytest` and lint with `uv run ruff check .` (per AGENTS.md).

---

## Task 1: Policy model + loader (`redaction.py`, `errors.py`)

**Files:**
- Create: `src/kb_extract/redaction.py`
- Modify: `src/kb_extract/errors.py`
- Test: `tests/test_redaction.py`

- [ ] **Step 1: Add the error type**

In `src/kb_extract/errors.py`, append:

```python
class RedactionPolicyError(Exception):
    """The redaction.toml policy file is missing (when explicitly given),
    malformed, or contains an invalid regex. Surfaced to the user."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_redaction.py`:

```python
from pathlib import Path

import pytest

from kb_extract.errors import RedactionPolicyError
from kb_extract.redaction import RedactionPolicy, TextRule, load_policy


def _write_policy(root: Path, body: str) -> Path:
    p = root / "redaction.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_policy_absent_default_returns_none(tmp_path):
    assert load_policy(tmp_path, None) is None


def test_load_policy_explicit_missing_raises(tmp_path):
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, tmp_path / "nope.toml")


def test_load_policy_parses_fields(tmp_path):
    _write_policy(
        tmp_path,
        '[redaction]\n'
        'enabled = true\n'
        '[[redaction.text]]\n'
        "pattern = '(?i)\\\\b[MH]\\\\d{6,8}\\\\b'\n"
        'replacement = "[PN-REDACTED]"\n'
        '[redaction.logos]\n'
        'sha256 = ["abc"]\n'
        'filename_globs = ["*logo*"]\n'
        'alt_globs = ["*logo*"]\n',
    )
    policy = load_policy(tmp_path, None)
    assert isinstance(policy, RedactionPolicy)
    assert policy.enabled is True
    assert policy.text_rules == (TextRule(pattern=r'(?i)\b[MH]\d{6,8}\b', replacement="[PN-REDACTED]"),)
    assert policy.logo_sha256 == ("abc",)
    assert policy.logo_filename_globs == ("*logo*",)
    assert policy.logo_alt_globs == ("*logo*",)
    assert len(policy.policy_sha256) == 64


def test_load_policy_invalid_regex_raises(tmp_path):
    _write_policy(
        tmp_path,
        '[redaction]\nenabled = true\n[[redaction.text]]\n'
        'pattern = "("\nreplacement = "x"\n',
    )
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, None)


def test_load_policy_invalid_toml_raises(tmp_path):
    _write_policy(tmp_path, "this is = = not toml")
    with pytest.raises(RedactionPolicyError):
        load_policy(tmp_path, None)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_redaction.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kb_extract.redaction'`.

- [ ] **Step 4: Write minimal implementation**

Create `src/kb_extract/redaction.py`:

```python
"""Deterministic redaction layer (SP-1). Pure: no LLM, no network.

Loads a redaction.toml policy and applies it to an ExtractionResult before
it is written to disk. See spec 2026-06-24-redaction-privacy-design.md.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from .contracts import AssetRef, ExtractionResult
from .errors import RedactionPolicyError


@dataclass(frozen=True, slots=True)
class TextRule:
    pattern: str
    replacement: str


@dataclass(frozen=True, slots=True)
class RedactionPolicy:
    enabled: bool
    text_rules: tuple[TextRule, ...]
    logo_sha256: tuple[str, ...]
    logo_filename_globs: tuple[str, ...]
    logo_alt_globs: tuple[str, ...]
    policy_sha256: str


@dataclass(frozen=True, slots=True)
class RedactionStats:
    pn_redacted: int
    logos_dropped: int


def load_policy(project_root: Path, override: Path | None) -> RedactionPolicy | None:
    """Load redaction.toml. Returns None when no policy applies.

    - override given but missing / malformed TOML / bad regex -> RedactionPolicyError
    - no override and no project_root/redaction.toml -> None (redaction off)
    """
    if override is not None:
        path = Path(override)
        if not path.is_file():
            raise RedactionPolicyError(f"redaction policy not found: {path}")
    else:
        path = project_root / "redaction.toml"
        if not path.is_file():
            return None

    raw = path.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise RedactionPolicyError(f"invalid redaction TOML {path}: {e}") from e

    red = data.get("redaction", {})
    text_rules: list[TextRule] = []
    for i, item in enumerate(red.get("text", [])):
        pattern = item.get("pattern", "")
        replacement = item.get("replacement", "[REDACTED]")
        try:
            re.compile(pattern)
        except re.error as e:
            raise RedactionPolicyError(
                f"invalid regex in redaction.text[{i}] pattern={pattern!r}: {e}"
            ) from e
        text_rules.append(TextRule(pattern=pattern, replacement=replacement))

    logos = red.get("logos", {})
    return RedactionPolicy(
        enabled=bool(red.get("enabled", False)),
        text_rules=tuple(text_rules),
        logo_sha256=tuple(logos.get("sha256", [])),
        logo_filename_globs=tuple(logos.get("filename_globs", [])),
        logo_alt_globs=tuple(logos.get("alt_globs", [])),
        policy_sha256=hashlib.sha256(raw).hexdigest(),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_redaction.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add src/kb_extract/redaction.py src/kb_extract/errors.py tests/test_redaction.py
git commit -m "feat(redaction): policy model and TOML loader (SP-1 1/6)"
```

---

## Task 2: Text redaction in `apply_to_result`

**Files:**
- Modify: `src/kb_extract/redaction.py`
- Test: `tests/test_redaction.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_redaction.py`:

```python
from kb_extract.contracts import ExtractionMeta, ExtractionResult, SectionNode
from kb_extract.redaction import RedactionStats, apply_to_result


def _meta() -> ExtractionMeta:
    return ExtractionMeta(
        source_path="x.pdf", source_sha256="a" * 64, source_bytes=1,
        source_mtime_iso="t", adapter_name="p", adapter_version="v",
        tool_versions={}, extracted_at_iso="t", outline_source="bookmark",
        status="ok",
    )


def _result(markdown: str, assets=()) -> ExtractionResult:
    root = SectionNode(
        node_id="0000", title="Root", level=0, page_start=1, page_end=1,
        anchor="", language="und",
        children=(SectionNode(
            node_id="0001", title="Leaf", level=1, page_start=1, page_end=1,
            anchor="sec-0001", language="und",
        ),),
    )
    return ExtractionResult(markdown=markdown, index=root, tables=(), assets=assets, meta=_meta())


def _policy(text_rules=(), logo_sha256=(), filename_globs=(), alt_globs=()):
    from kb_extract.redaction import RedactionPolicy
    return RedactionPolicy(
        enabled=True, text_rules=tuple(text_rules), logo_sha256=tuple(logo_sha256),
        logo_filename_globs=tuple(filename_globs), logo_alt_globs=tuple(alt_globs),
        policy_sha256="d" * 64,
    )


def test_apply_redacts_part_numbers_and_counts():
    md = (
        '<a id="sec-0001"></a>\n'
        '# Leaf\n\n'
        'Part M1320001 and H1234567 are confidential. M9999999 too.\n'
    )
    rule = TextRule(pattern=r'(?i)\b[MH]\d{6,8}\b', replacement="[PN-REDACTED]")
    new_result, stats, dropped = apply_to_result(_result(md), _policy(text_rules=(rule,)))
    assert "M1320001" not in new_result.markdown
    assert "H1234567" not in new_result.markdown
    assert new_result.markdown.count("[PN-REDACTED]") == 3
    assert stats == RedactionStats(pn_redacted=3, logos_dropped=0)
    assert dropped == ()


def test_apply_preserves_anchor_line():
    md = '<a id="sec-0001"></a>\n# Leaf\n\nM1320001\n'
    rule = TextRule(pattern=r'(?i)\b[MH]\d{6,8}\b', replacement="[PN-REDACTED]")
    new_result, _, _ = apply_to_result(_result(md), _policy(text_rules=(rule,)))
    assert '<a id="sec-0001"></a>' in new_result.markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redaction.py -k apply -v`
Expected: FAIL with `ImportError: cannot import name 'apply_to_result'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/kb_extract/redaction.py`:

```python
def apply_to_result(
    result: ExtractionResult, policy: RedactionPolicy
) -> tuple[ExtractionResult, RedactionStats, tuple[str, ...]]:
    """Apply text + logo redaction. Returns (redacted_result, stats, dropped_rel_paths).

    Anchors (`<a id="...">`) are never touched: logo handling only removes
    image lines, and the default part-number patterns cannot match anchor ids.
    """
    md = result.markdown
    pn_count = 0
    for rule in policy.text_rules:
        md, n = re.subn(rule.pattern, rule.replacement, md)
        pn_count += n

    stats = RedactionStats(pn_redacted=pn_count, logos_dropped=0)
    new_result = replace(result, markdown=md)
    return new_result, stats, ()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_redaction.py -k apply -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/redaction.py tests/test_redaction.py
git commit -m "feat(redaction): part-number text redaction (SP-1 2/6)"
```

---

## Task 3: Logo dropping in `apply_to_result`

**Files:**
- Modify: `src/kb_extract/redaction.py`
- Test: `tests/test_redaction.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_redaction.py`:

```python
from kb_extract.contracts import AssetRef


def _logo_md() -> str:
    return (
        '<a id="sec-0001"></a>\n'
        '# Leaf\n\n'
        '![company logo](assets/logo_1.png)\n\n'
        '![figure](assets/fig_2.png)\n'
    )


def test_apply_drops_logo_by_sha256():
    assets = (
        AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256="L" * 64, alt="company logo"),
        AssetRef(kind="image", rel_path="assets/fig_2.png", page=1, sha256="F" * 64, alt="figure"),
    )
    new_result, stats, dropped = apply_to_result(
        _result(_logo_md(), assets), _policy(logo_sha256=("L" * 64,))
    )
    assert dropped == ("assets/logo_1.png",)
    assert "assets/logo_1.png" not in new_result.markdown
    assert "assets/fig_2.png" in new_result.markdown
    assert tuple(a.rel_path for a in new_result.assets) == ("assets/fig_2.png",)
    assert stats.logos_dropped == 1


def test_apply_drops_logo_by_filename_glob():
    assets = (AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256="L" * 64, alt=""),)
    _, stats, dropped = apply_to_result(_result(_logo_md(), assets), _policy(filename_globs=("*logo*",)))
    assert dropped == ("assets/logo_1.png",)
    assert stats.logos_dropped == 1


def test_apply_drops_logo_by_alt_glob():
    assets = (AssetRef(kind="image", rel_path="assets/x.png", page=1, sha256="L" * 64, alt="company logo"),)
    md = '<a id="sec-0001"></a>\n# Leaf\n\n![company logo](assets/x.png)\n'
    _, stats, dropped = apply_to_result(_result(md, assets), _policy(alt_globs=("*logo*",)))
    assert dropped == ("assets/x.png",)
    assert stats.logos_dropped == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redaction.py -k logo -v`
Expected: FAIL (dropped is `()`, assets unchanged).

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/redaction.py`, add the helper above `apply_to_result`:

```python
def _is_logo(asset: AssetRef, policy: RedactionPolicy) -> bool:
    if asset.sha256 in policy.logo_sha256:
        return True
    fname = asset.rel_path.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatch(fname, g) for g in policy.logo_filename_globs):
        return True
    if any(fnmatch.fnmatch(asset.alt, g) for g in policy.logo_alt_globs):
        return True
    return False
```

Then replace the body of `apply_to_result` with:

```python
def apply_to_result(
    result: ExtractionResult, policy: RedactionPolicy
) -> tuple[ExtractionResult, RedactionStats, tuple[str, ...]]:
    """Apply text + logo redaction. Returns (redacted_result, stats, dropped_rel_paths).

    Anchors (`<a id="...">`) are never touched: logo handling only removes
    image lines, and the default part-number patterns cannot match anchor ids.
    """
    dropped = tuple(sorted(a.rel_path for a in result.assets if _is_logo(a, policy)))
    dropped_set = set(dropped)
    kept_assets = tuple(a for a in result.assets if a.rel_path not in dropped_set)

    md = result.markdown
    if dropped:
        kept_lines = [
            line for line in md.split("\n")
            if not any(f"]({p})" in line for p in dropped)
        ]
        md = "\n".join(kept_lines)

    pn_count = 0
    for rule in policy.text_rules:
        md, n = re.subn(rule.pattern, rule.replacement, md)
        pn_count += n

    new_result = replace(result, markdown=md, assets=kept_assets)
    stats = RedactionStats(pn_redacted=pn_count, logos_dropped=len(dropped))
    return new_result, stats, dropped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_redaction.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/redaction.py tests/test_redaction.py
git commit -m "feat(redaction): drop logo assets by sha256/filename/alt (SP-1 3/6)"
```

---

## Task 4: `serialize_redaction_json`

**Files:**
- Modify: `src/kb_extract/serialization.py`
- Test: `tests/test_redaction.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_redaction.py`:

```python
from kb_extract.serialization import serialize_redaction_json


def test_serialize_redaction_json_counts_only_sorted_keys():
    out = serialize_redaction_json(pn_redacted=12, logos_dropped=3, policy_sha256="e" * 64)
    assert out.endswith("\n")
    assert '"logos_dropped": 3' in out
    assert '"pn_redacted": 12' in out
    assert '"policy_sha256": "' + "e" * 64 + '"' in out
    # keys sorted: logos_dropped < pn_redacted < policy_sha256
    assert out.index("logos_dropped") < out.index("pn_redacted") < out.index("policy_sha256")
    # only the three known keys exist (no leaked source values)
    import json as _json
    assert set(_json.loads(out).keys()) == {"logos_dropped", "pn_redacted", "policy_sha256"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redaction.py -k serialize_redaction -v`
Expected: FAIL with `ImportError: cannot import name 'serialize_redaction_json'`.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/serialization.py`, append:

```python
def serialize_redaction_json(
    *, pn_redacted: int, logos_dropped: int, policy_sha256: str
) -> str:
    """Counts-only audit sidecar. Never contains redacted source values."""
    return _json_dumps(
        {
            "logos_dropped": logos_dropped,
            "pn_redacted": pn_redacted,
            "policy_sha256": policy_sha256,
        }
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_redaction.py -k serialize_redaction -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/serialization.py tests/test_redaction.py
git commit -m "feat(redaction): counts-only redaction.json serializer (SP-1 4/6)"
```

---

## Task 5: Orchestrator integration

**Files:**
- Modify: `src/kb_extract/orchestrator.py`
- Test: `tests/test_redaction.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_redaction.py`. First ensure these imports are present at the **top** of the file (add any that are missing):

```python
import hashlib
import json

from kb_extract.adapters.base import Registry
from kb_extract.contracts import AssetRef, ExtractionResult, SectionNode
from kb_extract.orchestrator import run
```

Then add a tiny in-test adapter that emits a part number and a logo asset:

```python
class _RedactTestAdapter:
    name = "_redact"
    version = "0.1"
    extensions = (".rdt",)

    def extract(self, src, out_dir_tmp):
        assets_dir = out_dir_tmp / "assets"
        assets_dir.mkdir(exist_ok=True)
        (assets_dir / "logo_1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        sha = hashlib.sha256((assets_dir / "logo_1.png").read_bytes()).hexdigest()
        md = (
            '<!-- generated -->\n\n'
            '<a id="sec-0001"></a>\n'
            '# Doc\n\n'
            'Part M1320001 is secret.\n\n'
            '![company logo](assets/logo_1.png)\n'
        )
        root = SectionNode(
            node_id="0000", title="Root", level=0, page_start=1, page_end=1,
            anchor="", language="und",
            children=(SectionNode(
                node_id="0001", title="Doc", level=1, page_start=1, page_end=1,
                anchor="sec-0001", language="und",
            ),),
        )
        assets = (AssetRef(kind="image", rel_path="assets/logo_1.png", page=1, sha256=sha, alt="company logo"),)
        return ExtractionResult(markdown=md, index=root, tables=(), assets=assets, meta=_meta())


def _project_with_policy(tmp_path, policy_body):
    project = tmp_path / "P"
    project.mkdir()
    (project / "doc.rdt").write_bytes(b"x")
    (project / "redaction.toml").write_text(policy_body, encoding="utf-8")
    return project


POLICY = (
    '[redaction]\nenabled = true\n'
    '[[redaction.text]]\n'
    "pattern = '(?i)\\\\b[MH]\\\\d{6,8}\\\\b'\n"
    'replacement = "[PN-REDACTED]"\n'
    '[redaction.logos]\nfilename_globs = ["*logo*"]\n'
)


def test_run_applies_redaction_and_writes_sidecar(tmp_path):
    project = _project_with_policy(tmp_path, POLICY)
    reg = Registry()
    reg.register(_RedactTestAdapter())
    report = run(project, registry=reg)
    assert report.ok_count == 1
    out = project / "kb" / "doc"
    main_md = (out / "main.md").read_text(encoding="utf-8")
    assert "M1320001" not in main_md
    assert "[PN-REDACTED]" in main_md
    assert "assets/logo_1.png" not in main_md
    assert '<a id="sec-0001"></a>' in main_md
    assert not (out / "assets" / "logo_1.png").exists()
    sidecar = json.loads((out / "redaction.json").read_text(encoding="utf-8"))
    assert sidecar["pn_redacted"] == 1
    assert sidecar["logos_dropped"] == 1
    assert len(sidecar["policy_sha256"]) == 64
    assert report.pn_redacted == 1
    assert report.logos_dropped == 1


def test_run_without_policy_writes_no_sidecar(tmp_path):
    project = tmp_path / "P"
    project.mkdir()
    (project / "doc.rdt").write_bytes(b"x")
    reg = Registry()
    reg.register(_RedactTestAdapter())
    run(project, registry=reg)
    out = project / "kb" / "doc"
    assert "M1320001" in (out / "main.md").read_text(encoding="utf-8")
    assert not (out / "redaction.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_redaction.py -k run_ -v`
Expected: FAIL — `report.pn_redacted` does not exist / redaction not applied / sidecar missing.

- [ ] **Step 3: Write minimal implementation**

In `src/kb_extract/orchestrator.py`:

a) Add counters to `RunReport` (after `dry_run_count`):

```python
    pn_redacted: int = 0
    logos_dropped: int = 0
```

b) Add imports near the other local imports at top of file:

```python
from .redaction import apply_to_result, load_policy
from .serialization import serialize_redaction_json
```

(`serialize_redaction_json` is added to the existing `from .serialization import (...)` block instead, to keep one import.)

c) Extend the `run` signature (add two keyword-only params before `_nest_depth`):

```python
def run(
    path: Path,
    *,
    registry: Registry | None = None,
    force: bool = False,
    dry_run: bool = False,
    only_exts: tuple[str, ...] | None = None,
    output_dir: Path | None = None,
    redaction_policy: Path | None = None,
    no_redaction: bool = False,
    _nest_depth: int = 0,
) -> RunReport:
```

d) After `project_root = find_project_root(path)` (line ~94), load the policy once:

```python
    policy = None if no_redaction else load_policy(project_root, redaction_policy)
```

e) Replace the write block (currently lines ~156-161):

```python
            if policy is not None and policy.enabled:
                result, rstats, dropped = apply_to_result(result, policy)
                for rel in dropped:
                    (out_dir_tmp / rel).unlink(missing_ok=True)
            else:
                rstats = None

            output_sha = _write_result_to_disk(result, out_dir_tmp)
            if rstats is not None:
                (out_dir_tmp / "redaction.json").write_bytes(
                    serialize_redaction_json(
                        pn_redacted=rstats.pn_redacted,
                        logos_dropped=rstats.logos_dropped,
                        policy_sha256=policy.policy_sha256,
                    ).encode("utf-8")
                )
                report.pn_redacted += rstats.pn_redacted
                report.logos_dropped += rstats.logos_dropped
            if out_dir.exists():
                shutil.rmtree(out_dir)
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            out_dir_tmp.rename(out_dir)
            manifest.upsert(src, result.meta, output_sha256=output_sha)
            report.ok_count += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_redaction.py tests/test_orchestrator.py -v`
Expected: PASS (new redaction tests + existing orchestrator tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/kb_extract/orchestrator.py tests/test_redaction.py
git commit -m "feat(redaction): apply in orchestrator and write audit sidecar (SP-1 5/6)"
```

---

## Task 6: CLI flags + guard tests + docs

**Files:**
- Modify: `src/kb_extract/cli.py`
- Modify: `tests/test_no_llm_imports.py` (extend H1/H2 guard to redaction.py)
- Test: `tests/test_redaction.py`
- Modify: `README.md`, `CHANGELOG.md`, `pyproject.toml`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_redaction.py` a determinism test and a no-LLM-import guard:

```python
import ast


def test_redaction_is_deterministic_across_two_runs(tmp_path):
    reg1, reg2 = Registry(), Registry()
    reg1.register(_RedactTestAdapter())
    reg2.register(_RedactTestAdapter())

    def build(root):
        root.mkdir(parents=True)
        (root / "doc.rdt").write_bytes(b"x")
        (root / "redaction.toml").write_text(POLICY, encoding="utf-8")
        return root

    r1 = build(tmp_path / "a")
    r2 = build(tmp_path / "b")
    run(r1, registry=reg1)
    run(r2, registry=reg2)
    md1 = (r1 / "kb" / "doc" / "main.md").read_bytes()
    md2 = (r2 / "kb" / "doc" / "main.md").read_bytes()
    assert md1 == md2
    side1 = (r1 / "kb" / "doc" / "redaction.json").read_bytes()
    side2 = (r2 / "kb" / "doc" / "redaction.json").read_bytes()
    assert side1 == side2
    assert b"\r" not in md1  # LF only


def test_redaction_module_imports_no_llm_sdk():
    import kb_extract.redaction as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
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

- [ ] **Step 2: Run tests to verify they fail or pass**

Run: `uv run pytest tests/test_redaction.py -k "deterministic or no_llm" -v`
Expected: PASS (these exercise already-built behavior; if they fail, fix the implementation, not the test).

- [ ] **Step 3: Add CLI flags**

In `src/kb_extract/cli.py`, in the `extract` command decorator block (after the `--output-dir` option, before `def extract(`), add:

```python
@click.option(
    "--redaction-policy", "redaction_policy",
    type=click.Path(path_type=Path), default=None,
    help="脱敏策略文件路径（默认自动发现项目根的 redaction.toml）。",
)
@click.option("--no-redaction", is_flag=True, help="即使发现 redaction.toml 也强制关闭脱敏。")
```

Extend the `extract` function signature and the `orch_run(...)` call:

```python
def extract(
    path: Path,
    force: bool,
    dry_run: bool,
    as_json: bool,
    only: tuple[str, ...],
    adapter: str | None,
    output_dir: Path | None,
    redaction_policy: Path | None,
    no_redaction: bool,
) -> None:
```

```python
    report = orch_run(
        path,
        force=force,
        dry_run=dry_run,
        only_exts=only_exts,
        output_dir=output_dir,
        redaction_policy=redaction_policy,
        no_redaction=no_redaction,
    )
```

In the `as_json` dict add:

```python
            "pn_redacted": report.pn_redacted,
            "logos_dropped": report.logos_dropped,
```

In the human-readable branch, append to the summary `click.echo`:

```python
        click.echo(
            f"ok={report.ok_count} failed={report.failed_count} "
            f"skipped={report.skipped_count} unchanged={report.unchanged_count} "
            f"dry_run={report.dry_run_count} "
            f"redacted_pn={report.pn_redacted} redacted_logos={report.logos_dropped}"
        )
```

- [ ] **Step 4: Update the H1/H2 guard (optional but recommended)**

`tests/test_no_llm_imports.py` only scans `adapters/`. The redaction guard added in Step 1 already covers `redaction.py`, so no change is required here. Leave this file untouched.

- [ ] **Step 5: Update docs and version**

In `pyproject.toml`, bump `version = "0.10.0"` to `version = "0.11.0"`.

In `README.md`, update the version badge `version-0.10.0` to `version-0.11.0`, and add a short section after the install section:

```markdown
## 脱敏 / 隐私

工程文档常含机密料号与公司 logo。在项目根放一份 `redaction.toml` 即可在
**抽取产物落盘前**确定性脱敏（不破坏段落锚点，仍逐 byte 可复现）：

```toml
[redaction]
enabled = true

[[redaction.text]]
pattern = '(?i)\b[MH]\d{6,8}\b'   # M132xxxx / H123xxxx 料号
replacement = "[PN-REDACTED]"

[redaction.logos]
sha256 = []                       # 资产 sha256 精确匹配
filename_globs = ["*logo*"]
alt_globs = ["*logo*"]
```

运行 `kb extract .`（或 `--redaction-policy <path>`；`--no-redaction` 可强制关闭）。
每份文档会额外写出 `redaction.json` 审计侧车（只含计数，不含被脱敏原值）。
```

In `CHANGELOG.md`, add at the top below the header:

```markdown
## [0.11.0] - 2026-06-24

### Added
- Deterministic redaction layer (SP-1): opt-in `redaction.toml` policy redacts
  part-number text (e.g. M132xxxx / H123xxxx) and drops logo images before the
  extraction output is written. Anchors are preserved and output stays
  byte-reproducible. Adds `kb extract --redaction-policy / --no-redaction` and a
  counts-only `redaction.json` audit sidecar.
```

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest`
Expected: all tests pass (existing + new redaction tests).

Run: `uv run ruff check .`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add src/kb_extract/cli.py tests/test_redaction.py README.md CHANGELOG.md pyproject.toml
git commit -m "feat(redaction): CLI flags, docs, and v0.11.0 bump (SP-1 6/6)"
```

---

## Notes for the implementer

- **Do not** add `redaction.py` to `adapters/`. It is a core-level sibling module; keeping it out of `adapters/` is what lets it stay LLM-free without tripping `test_no_llm_imports`.
- **Determinism:** iterate assets via the sorted `dropped` tuple; never rely on `set` ordering for output. The `dropped_set` is used only for membership tests, never for emitting output.
- **Anchor safety:** the default part-number regex cannot match `sec-0001` anchor ids. If a future policy adds a reckless pattern, that is the policy author's responsibility; the tests lock in anchor preservation for the default pattern.
- **TOML string escaping:** in tests the regex backslashes are doubled inside the Python string literal that writes the TOML file. Verify the on-disk TOML reads `pattern = '(?i)\b[MH]\d{6,8}\b'`.
```
