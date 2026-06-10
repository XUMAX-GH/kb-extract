"""kb verify implementation. Spec §7 (last paragraph), §8.1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .layout import kb_dir
from .manifest import Manifest


@dataclass(slots=True)
class VerifyReport:
    ok: bool = True
    violations: list[str] = field(default_factory=list)
    files_checked: int = 0


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _doc_dirs(project_root: Path, output_dir: Path | None = None) -> list[Path]:
    kb = kb_dir(project_root, output_dir)
    if not kb.exists():
        return []
    # Only verify direct children: kb/<doc>/main.md. Deeper paths come from
    # the ZIP adapter's internal `_unpacked/kb/...` recursion, which is
    # tracked by the per-zip nested manifest (not the project-level one).
    out: list[Path] = []
    for p in sorted(kb.rglob("main.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(kb).parts
        if len(rel) != 2:
            continue
        out.append(p)
    return out


def verify_project(
    project_root: Path,
    *,
    fail_fast: bool = False,
    output_dir: Path | None = None,
) -> VerifyReport:
    """Re-run filesystem-level checks against artifacts on disk.

    Catches unauthorized edits to main.md (by re-hashing and comparing with
    manifest), plus structural integrity (assets present, hashes match).

    ``output_dir`` (v0.5.0): when provided, read manifest + artifacts from
    ``output_dir/kb/`` instead of ``project_root/kb/``.
    """
    report = VerifyReport()
    manifest_path = kb_dir(project_root, output_dir) / "manifest.sqlite"
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

    for main_md in _doc_dirs(project_root, output_dir):
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
        # We stored a composite output_sha; the markdown-only sha is a different value.
        # For v1 simplicity: also recompute composite from on-disk artifacts.
        composite = _recompute_composite_sha(doc_dir)
        if row.output_sha256 and composite != row.output_sha256:
            kb_root = kb_dir(project_root, output_dir)
            try:
                rel_label = doc_dir.relative_to(kb_root).as_posix()
            except ValueError:
                rel_label = doc_dir.name
            report.ok = False
            report.violations.append(
                f"{rel_label}/main.md: "
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
