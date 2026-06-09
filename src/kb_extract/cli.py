"""kb 命令行入口（规格 sec.8.1）。

退出码:
  0  正常
  1  至少一份源文件失败 / partial
  2  命令行用法错误（Click 默认）
  3  hardness 违规（仅 verify 模式）
"""

from __future__ import annotations

import csv as _csv
import io as _io
import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from . import __version__
from .adapters.base import get_default_registry
from .layout import find_project_root
from .manifest import Manifest
from .orchestrator import run as orch_run
from .verify import verify_project


@click.group()
@click.version_option(__version__, prog_name="kb")
def main() -> None:
    """kb —— 确定性文档抽取工具。"""


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="即使源文件 hash 未变也重新抽取。")
@click.option("--dry-run", is_flag=True, help="仅扫描可抽取的源文件，不写入磁盘。")
@click.option("--json", "as_json", is_flag=True, help="在标准输出打印 JSON 报告。")
@click.option("--only", "only", multiple=True, help="只处理列出的扩展名（例如 --only .pdf）。")
@click.option("--adapter", default=None, help="（v1 暂未使用）强制指定适配器。")
def extract(
    path: Path,
    force: bool,
    dry_run: bool,
    as_json: bool,
    only: tuple[str, ...],
    adapter: str | None,
) -> None:
    """抽取 PATH 下的所有文档。"""
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
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出。")
@click.option("--fail-fast", is_flag=True, help="发现第一条违规后立刻停止。")
def verify(path: Path, as_json: bool, fail_fast: bool) -> None:
    """基于 manifest 重新校验磁盘产物。检测到违规时返回退出码 3。"""
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


@main.command()
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出适配器列表。")
def adapters(as_json: bool) -> None:
    """列出已注册的适配器。"""
    reg = get_default_registry()
    rows = [
        {"name": a.name, "version": a.version, "extensions": list(a.extensions)}
        for a in reg.all()
    ]
    if as_json:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    click.echo(f"{'NAME':<20} {'VERSION':<10} EXTENSIONS")
    for r in rows:
        click.echo(f"{r['name']:<20} {r['version']:<10} {','.join(r['extensions'])}")


@main.command(name="manifest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--status",
              type=click.Choice(["ok", "partial", "failed", "skipped"]),
              default=None,
              help="按状态过滤记录。")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]),
              default="table", help="输出格式（默认 table）。")
def manifest_cmd(path: Path, status: str | None, fmt: str) -> None:
    """展示项目的 manifest 记录。"""
    project_root = find_project_root(path)
    db = project_root / "kb" / "manifest.sqlite"
    if not db.exists():
        click.echo(f"no manifest at {db}", err=True)
        sys.exit(1)
    m = Manifest(db)
    try:
        rows = [r for r in m.iter() if status is None or r.status == status]
    finally:
        m.close()
    if fmt == "json":
        click.echo(json.dumps([asdict(r) for r in rows], indent=2, sort_keys=True))
    elif fmt == "csv":
        buf = _io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow(["source_path", "status", "adapter_name", "output_sha256"])
        for r in rows:
            writer.writerow([r.source_path, r.status, r.adapter_name or "", r.output_sha256 or ""])
        click.echo(buf.getvalue())
    else:
        click.echo(f"{'STATUS':<10} {'ADAPTER':<15} SOURCE")
        for r in rows:
            click.echo(f"{r.status:<10} {(r.adapter_name or '-'):<15} {r.source_path}")
