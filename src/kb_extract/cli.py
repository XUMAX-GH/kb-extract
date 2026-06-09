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
from pathlib import Path

import click

from . import __version__
from .orchestrator import run as orch_run
from .verify import verify_project


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
