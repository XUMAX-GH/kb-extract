"""Deterministic redaction layer (SP-1). Pure: no LLM, no network.

Loads a redaction.toml policy and applies it to an ExtractionResult before
it is written to disk. See spec 2026-06-24-redaction-privacy-design.md.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from .contracts import ExtractionResult
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
