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
