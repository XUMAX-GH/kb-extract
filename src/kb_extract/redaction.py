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

from .contracts import AssetRef, ExtractionMeta, ExtractionResult, SectionNode
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


def _is_logo(asset: AssetRef, policy: RedactionPolicy) -> bool:
    if asset.sha256 in policy.logo_sha256:
        return True
    fname = asset.rel_path.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatch(fname, g) for g in policy.logo_filename_globs):
        return True
    return any(fnmatch.fnmatch(asset.alt, g) for g in policy.logo_alt_globs)


def _apply_text_rules(text: str, rules: tuple[TextRule, ...]) -> tuple[str, int]:
    count = 0
    for rule in rules:
        text, n = re.subn(rule.pattern, rule.replacement, text)
        count += n
    return text, count


def _redact_section(node: SectionNode, rules: tuple[TextRule, ...]) -> tuple[SectionNode, int]:
    """Redact node titles recursively. Anchors and ids are never touched."""
    new_title, count = _apply_text_rules(node.title, rules)
    new_children: list[SectionNode] = []
    for child in node.children:
        redacted, n = _redact_section(child, rules)
        new_children.append(redacted)
        count += n
    return replace(node, title=new_title, children=tuple(new_children)), count


def _redact_meta(meta: ExtractionMeta, rules: tuple[TextRule, ...]) -> tuple[ExtractionMeta, int]:
    """Redact free-text meta fields that may carry part numbers."""
    source_path, count = _apply_text_rules(meta.source_path, rules)
    warnings: list[str] = []
    for w in meta.warnings:
        rw, n = _apply_text_rules(w, rules)
        warnings.append(rw)
        count += n
    skipped: list[str] = []
    for s in meta.skipped_reasons:
        rs, n = _apply_text_rules(s, rules)
        skipped.append(rs)
        count += n
    return (
        replace(
            meta,
            source_path=source_path,
            warnings=tuple(warnings),
            skipped_reasons=tuple(skipped),
        ),
        count,
    )


def apply_to_result(
    result: ExtractionResult, policy: RedactionPolicy
) -> tuple[ExtractionResult, RedactionStats, tuple[str, ...]]:
    """Apply text + logo redaction. Returns (redacted_result, stats, dropped_rel_paths).

    Text rules are applied to the markdown body, the index section titles, and
    free-text meta fields (source_path, warnings, skipped_reasons). Anchors
    (`<a id="...">`) and section node ids are never touched: logo handling only
    removes image lines, and title/meta redaction rewrites only text fields.
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

    md, pn_count = _apply_text_rules(md, policy.text_rules)
    new_index, index_count = _redact_section(result.index, policy.text_rules)
    new_meta, meta_count = _redact_meta(result.meta, policy.text_rules)
    pn_count += index_count + meta_count

    new_result = replace(
        result, markdown=md, index=new_index, assets=kept_assets, meta=new_meta
    )
    stats = RedactionStats(pn_redacted=pn_count, logos_dropped=len(dropped))
    return new_result, stats, dropped
