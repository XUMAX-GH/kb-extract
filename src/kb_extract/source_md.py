"""kb source layer (SP-2): markitdown -> image-free, redacted source.md.

markitdown is imported ONLY in this module (never under adapters/), so the
adapter-only LLM-import scan is unaffected. Conversion of local files needs
no network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version as _pkg_version
from pathlib import Path

from .discovery import discover_sources
from .layout import find_project_root, kb_dir, target_dir
from .redaction import RedactionPolicy, load_policy, redact_text
from .serialization import serialize_markdown, serialize_source_meta_json
from .source_manifest import SourceManifest

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def strip_images(markdown: str) -> tuple[str, int]:
    """Remove all markdown and HTML image references; return (text, count)."""
    text, n1 = _MD_IMAGE_RE.subn("", markdown)
    text, n2 = _HTML_IMG_RE.subn("", text)
    return text, n1 + n2


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


def _markitdown_version() -> str:
    try:
        return _pkg_version("markitdown")
    except Exception:  # package may not be installed in test environments
        return "unknown"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


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
                    src.stat().st_mtime, tz=UTC
                ).isoformat(),
                markitdown_version=md_version,
                source_md_sha256=_sha256_bytes(data),
                images_stripped=stats.images_stripped,
                pn_redacted=stats.pn_redacted,
                policy_sha256=policy_sha,
                generated_at_iso=datetime.now(tz=UTC).isoformat(),
            )
            (out_dir / "source.meta.json").write_bytes(sidecar.encode("utf-8"))
            if manifest is not None:
                manifest.upsert_ok(
                    src,
                    source_sha256=src_sha,
                    source_bytes=len(raw_bytes),
                    source_mtime_iso=datetime.fromtimestamp(
                        src.stat().st_mtime, tz=UTC
                    ).isoformat(),
                    markitdown_version=md_version,
                    source_md_sha256=_sha256_bytes(data),
                    images_stripped=stats.images_stripped,
                    pn_redacted=stats.pn_redacted,
                    policy_sha256=policy_sha,
                    generated_at_iso=datetime.now(tz=UTC).isoformat(),
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
