"""Main extraction pipeline. Spec §5."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .adapters.base import Registry, get_default_registry
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
    _nest_depth: int = 0,
) -> RunReport:
    """Top-level extraction over a project root or file. See spec §5.1."""
    if registry is None:
        registry = get_default_registry()

    if _nest_depth > 5:
        return RunReport()  # zip too nested; adapter handles warning

    # Wire ZipAdapter with registry handle if zip extension not yet registered.
    if ".zip" not in {ext for a in registry.all() for ext in a.extensions}:
        from .adapters.zip import ZipAdapter
        registry.register(ZipAdapter(child_registry=registry, nest_depth=_nest_depth))

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
