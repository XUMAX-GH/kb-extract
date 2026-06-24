"""Main extraction pipeline. Spec §5."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .adapters.base import Registry, get_default_registry
from .contracts import ExtractionResult
from .discovery import discover_sources
from .errors import HardnessViolation
from .hardness import assert_invariants
from .layout import find_project_root, kb_dir, target_dir
from .manifest import Manifest
from .redaction import apply_to_result, load_policy
from .serialization import (
    serialize_index_json,
    serialize_markdown,
    serialize_meta_json,
    serialize_redaction_json,
)


@dataclass(slots=True)
class RunReport:
    ok_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    unchanged_count: int = 0
    dry_run_count: int = 0
    pn_redacted: int = 0
    logos_dropped: int = 0
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


def _redaction_cache_current(out_dir: Path, policy) -> bool:
    sidecar = out_dir / "redaction.json"
    if policy is not None and policy.enabled:
        if not sidecar.is_file():
            return False
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return payload.get("policy_sha256") == policy.policy_sha256
    return not sidecar.exists()


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
    """Top-level extraction over a project root or file. See spec §5.1.

    ``output_dir`` (v0.5.0): when provided, kb/ is created at
    ``output_dir/kb/`` instead of ``project_root/kb/``. The per-source path
    structure under ``kb/`` is still computed from the source's relative
    location within ``project_root``.
    """
    if registry is None:
        registry = get_default_registry()

    if _nest_depth > 5:
        return RunReport()  # zip too nested; adapter handles warning

    project_root = find_project_root(path)
    policy = None if no_redaction else load_policy(project_root, redaction_policy)
    child_redaction_policy = redaction_policy
    if policy is not None and child_redaction_policy is None:
        child_redaction_policy = project_root / "redaction.toml"
    child_no_redaction = no_redaction or policy is None or not policy.enabled

    # Wire ZipAdapter with registry handle if zip extension not yet registered.
    from .adapters.zip import ZipAdapter
    if ".zip" not in {ext for a in registry.all() for ext in a.extensions}:
        registry.register(ZipAdapter(
            child_registry=registry,
            nest_depth=_nest_depth,
            redaction_policy=child_redaction_policy,
            no_redaction=child_no_redaction,
        ))
    for adapter in registry.all():
        if isinstance(adapter, ZipAdapter):
            adapter.configure_redaction(
                redaction_policy=child_redaction_policy,
                no_redaction=child_no_redaction,
            )
    sources = discover_sources(path)
    if only_exts:
        sources = [s for s in sources if s.suffix.lower() in {e.lower() for e in only_exts}]

    manifest_path = kb_dir(project_root, output_dir) / "manifest.sqlite"
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
            out_dir = target_dir(project_root, src, output_dir)
            if (
                prev
                and prev.source_sha256 == src_hash
                and prev.status == "ok"
                and not force
                and _redaction_cache_current(out_dir, policy)
            ):
                report.unchanged_count += 1
                continue

            out_dir_tmp = out_dir.with_suffix(out_dir.suffix + ".tmp")
            if out_dir_tmp.exists():
                shutil.rmtree(out_dir_tmp)
            out_dir_tmp.mkdir(parents=True, exist_ok=True)
            (out_dir_tmp / "assets").mkdir(exist_ok=True)

            try:
                result = adapter.extract(src, out_dir_tmp)
                consume_child_report = getattr(adapter, "consume_child_report", None)
                if callable(consume_child_report):
                    child_report = consume_child_report()
                    if child_report is not None:
                        report.pn_redacted += child_report.pn_redacted
                        report.logos_dropped += child_report.logos_dropped
            except HardnessViolation:
                shutil.rmtree(out_dir_tmp, ignore_errors=True)
                raise
            except Exception as e:  # orchestrator is the catch-all per spec §5.1
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
    finally:
        if manifest is not None:
            manifest.close()
    return report
