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
from .layout import find_project_root, kb_dir
from .manifest import Manifest
from .orchestrator import run as orch_run
from .verify import verify_project


def _record_history(
    project_root: Path,
    command: str,
    args: dict,
    exit_code: int,
    summary: str,
) -> None:
    """Best-effort memory write; never raises into user-facing code."""
    try:
        from .memory import MemoryStore
        with MemoryStore() as m:
            m.record(
                project_root=str(Path(project_root).resolve()),
                command=command,
                args=args,
                exit_code=exit_code,
                summary=summary,
            )
    except Exception:
        # memory is non-essential; never break a kb command for a memory bug
        pass


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
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="将 kb/ 写入此目录（而不是源所在目录）。目录不存在会自动创建。",
)
def extract(
    path: Path,
    force: bool,
    dry_run: bool,
    as_json: bool,
    only: tuple[str, ...],
    adapter: str | None,
    output_dir: Path | None,
) -> None:
    """抽取 PATH 下的所有文档。"""
    only_exts = tuple(only) if only else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()
    report = orch_run(
        path,
        force=force,
        dry_run=dry_run,
        only_exts=only_exts,
        output_dir=output_dir,
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
            "output_dir": str(output_dir) if output_dir else None,
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
    exit_code = 1 if report.failed_count or report.violations else 0
    _record_history(
        path, "extract",
        {"force": force, "dry_run": dry_run, "only": list(only),
         "output_dir": str(output_dir) if output_dir else None},
        exit_code,
        f"ok={report.ok_count} failed={report.failed_count}",
    )
    sys.exit(exit_code)


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出。")
@click.option("--fail-fast", is_flag=True, help="发现第一条违规后立刻停止。")
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/（与 extract 用相同参数）。",
)
def verify(
    path: Path, as_json: bool, fail_fast: bool, output_dir: Path | None
) -> None:
    """基于 manifest 重新校验磁盘产物。检测到违规时返回退出码 3。"""
    if output_dir is not None:
        output_dir = output_dir.resolve()
    report = verify_project(path, fail_fast=fail_fast, output_dir=output_dir)
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
    exit_code = 0 if report.ok else 3
    _record_history(
        path, "verify",
        {"fail_fast": fail_fast,
         "output_dir": str(output_dir) if output_dir else None},
        exit_code,
        f"files_checked={report.files_checked} violations={len(report.violations)}",
    )
    sys.exit(exit_code)


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


@main.group(name="wiki")
def wiki_group() -> None:
    """LLM-Wiki 子命令（v0.3+）。基于 kb/ 抽取产物生成带 evidence pin 的 wiki。"""


@wiki_group.command(name="build")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--provider",
    default="mock",
    show_default=True,
    help="LLM provider 名称：mock | cached（openai/anthropic/ollama 为占位）。",
)
@click.option("--seed", type=int, default=0, show_default=True, help="provider 的随机种子（H15）。")
@click.option("--dry-run", is_flag=True, help="只 discover topics + 生成内容，不写盘。")
@click.option("--json", "as_json", is_flag=True, help="JSON 输出。")
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/，把 wiki/ 写入这里。",
)
@click.option(
    "--responses-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="cached provider 的响应文件路径（JSON: {prompt_hash: response}）。",
)
@click.option(
    "--record-missing",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="cached provider: 把缺失的 prompt 追加写到此 JSON 文件（不抛错）。",
)
@click.option(
    "--min-evidence",
    type=int,
    default=1,
    show_default=True,
    help="只保留 evidence 数 ≥ 该值的 topic（v0.6.0）。",
)
@click.option(
    "--skip-numeric-titles",
    is_flag=True,
    help="丢弃标题仅为数字/点号/短横线的 topic（v0.6.0）。",
)
@click.option(
    "--taxonomy",
    "taxonomy_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="taxonomy.json 路径（v0.7.0）。指定时按 category 子目录组织 wiki/。",
)
def wiki_build(
    path: Path,
    provider: str,
    seed: int,
    dry_run: bool,
    as_json: bool,
    output_dir: Path | None,
    responses_file: Path | None,
    record_missing: Path | None,
    min_evidence: int,
    skip_numeric_titles: bool,
    taxonomy_path: Path | None,
) -> None:
    """基于 PATH/kb/ 重新构建 wiki/。"""
    from .wiki import build_wiki

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir = output_dir.resolve()

    provider_arg: object = provider
    if provider == "cached":
        if responses_file is None:
            raise click.UsageError("--provider cached 需要 --responses-file 指向响应 JSON。")
        from .wiki.providers.cached import CachedLlmClient

        provider_arg = CachedLlmClient(
            responses_path=responses_file,
            record_missing_path=record_missing,
        )

    taxonomy_cfg = None
    if taxonomy_path is not None:
        if not taxonomy_path.is_file():
            raise click.UsageError(f"--taxonomy 文件不存在: {taxonomy_path}")
        from .wiki.taxonomy import load_taxonomy

        taxonomy_cfg = load_taxonomy(taxonomy_path)

    result = build_wiki(
        path,
        provider=provider_arg,
        seed=seed,
        dry_run=dry_run,
        output_dir=output_dir,
        min_evidence=min_evidence,
        skip_numeric_titles=skip_numeric_titles,
        taxonomy=taxonomy_cfg,
    )
    if as_json:
        click.echo(json.dumps({
            "project_root": str(result.project_root),
            "provider": result.provider_name,
            "seed": result.seed,
            "topic_count": len(result.topics),
            "total_pins": sum(e.pin_count for e in result.entries),
            "unresolved_total": result.unresolved_total,
            "ok": result.ok,
            "dry_run": dry_run,
            "output_dir": str(output_dir) if output_dir else None,
        }, indent=2, sort_keys=True))
    else:
        click.echo(
            f"wiki build: topics={len(result.topics)} "
            f"pins={sum(e.pin_count for e in result.entries)} "
            f"unresolved={result.unresolved_total} "
            f"provider={result.provider_name} seed={result.seed}"
            + (" (dry-run)" if dry_run else "")
        )
    exit_code = 0 if result.ok else 1
    _record_history(
        path, "wiki build",
        {"provider": provider, "seed": seed, "dry_run": dry_run,
         "output_dir": str(output_dir) if output_dir else None,
         "min_evidence": min_evidence,
         "skip_numeric_titles": skip_numeric_titles},
        exit_code,
        f"topics={len(result.topics)} unresolved={result.unresolved_total}",
    )
    sys.exit(exit_code)


@wiki_group.command(name="dump-prompts")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/。",
)
@click.option(
    "--out",
    "out_file",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="prompts JSON 输出路径。",
)
@click.option(
    "--min-evidence",
    type=int,
    default=1,
    show_default=True,
    help="只 dump evidence 数 ≥ 该值的 topic。",
)
@click.option(
    "--skip-numeric-titles",
    is_flag=True,
    help="丢弃标题仅为数字的 topic。",
)
def wiki_dump_prompts(
    path: Path,
    output_dir: Path | None,
    out_file: Path,
    min_evidence: int,
    skip_numeric_titles: bool,
) -> None:
    """把当前 topic 列表对应的 LLM prompts 写到 JSON，方便外部 LLM 离线生成响应。

    输出形如::

      {
        "<prompt_sha256>": {
          "topic_slug": "...",
          "messages": [{"role":"system","content":"..."}, ...]
        },
        ...
      }

    用法：
      1. kb wiki dump-prompts <project> -o <out> --out prompts.json
      2. 用任意 LLM 生成 responses.json：{prompt_sha256: response_string}
      3. kb wiki build <project> -o <out> --provider cached --responses-file responses.json
    """
    from .layout import kb_dir as _kb_dir
    from .wiki.providers.cached import prompt_hash
    from .wiki.topics import discover_topics
    from .wiki.writer import _build_prompt

    if output_dir is not None:
        output_dir = output_dir.resolve()

    topics = discover_topics(
        path,
        output_dir=output_dir,
        min_evidence=min_evidence,
        skip_numeric_titles=skip_numeric_titles,
    )
    kb_root = _kb_dir(path, output_dir)

    prompts: dict[str, dict[str, object]] = {}
    for t in topics:
        messages = _build_prompt(t, kb_root=kb_root)
        h = prompt_hash(messages)
        prompts[h] = {
            "topic_slug": t.slug,
            "topic_title": t.title,
            "evidence_count": len(t.evidence),
            "messages": messages,
        }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    click.echo(
        f"wiki dump-prompts: {len(prompts)} prompts → {out_file}"
        f" (min_evidence={min_evidence}, skip_numeric_titles={skip_numeric_titles})"
    )


@wiki_group.command(name="verify")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="JSON 输出。")
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 wiki/ 与 kb/。",
)
def wiki_verify(path: Path, as_json: bool, output_dir: Path | None) -> None:
    """校验 wiki/ 下所有 evidence pin 都能解析到真实 kb anchor (H14)。"""
    from .wiki.orchestrator import verify_wiki

    if output_dir is not None:
        output_dir = output_dir.resolve()
    violations = verify_wiki(path, output_dir=output_dir)
    if as_json:
        click.echo(json.dumps({
            "ok": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
        }, indent=2, sort_keys=True))
    else:
        if violations:
            click.echo(f"wiki verify: {len(violations)} 条违规")
            for v in violations:
                click.echo(f"  [violation] {v}", err=True)
        else:
            click.echo("wiki verify: ok")
    exit_code = 3 if violations else 0
    _record_history(
        path, "wiki verify",
        {"output_dir": str(output_dir) if output_dir else None},
        exit_code,
        f"violations={len(violations)}",
    )
    sys.exit(exit_code)


@wiki_group.group(name="taxonomy")
def wiki_taxonomy_group() -> None:
    """Taxonomy 配置管理子命令（v0.7.0）。"""


@wiki_taxonomy_group.command(name="generate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/，taxonomy.json 默认写入这里的 wiki/。",
)
@click.option(
    "--prd-doc",
    "prd_doc_id",
    default=None,
    help="PRD 文档 ID（kb/ 下的目录名）。不指定时自动检测含 'PRD' 的文档。",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="taxonomy.json 输出路径（默认: <project>/wiki/taxonomy.json）。",
)
@click.option("--json", "as_json", is_flag=True, help="JSON 输出。")
def wiki_taxonomy_generate(
    path: Path,
    output_dir: Path | None,
    prd_doc_id: str | None,
    out_path: Path | None,
    as_json: bool,
) -> None:
    """从 PRD 文档结构自动生成 taxonomy.json (v0.7.0)。"""
    from .layout import kb_dir as _kb_dir
    from .layout import wiki_dir as _wiki_dir
    from .wiki.taxonomy import generate_taxonomy, save_taxonomy

    if output_dir is not None:
        output_dir = output_dir.resolve()

    kb_root = _kb_dir(path, output_dir)
    if not kb_root.is_dir():
        raise click.UsageError(f"kb/ 目录不存在: {kb_root}")

    cfg = generate_taxonomy(kb_root, prd_doc_id=prd_doc_id)

    if out_path is None:
        wiki_root = _wiki_dir(path, output_dir)
        wiki_root.mkdir(parents=True, exist_ok=True)
        out_path = wiki_root / "taxonomy.json"

    save_taxonomy(cfg, out_path)

    if as_json:
        click.echo(json.dumps({
            "ok": True,
            "out": str(out_path),
            "source_prd": cfg.source_prd,
            "category_count": len(cfg.categories),
            "categories": [c.slug for c in cfg.categories],
        }, indent=2, sort_keys=True))
    else:
        click.echo(
            f"wiki taxonomy generate: categories={len(cfg.categories)} "
            f"source_prd={cfg.source_prd} -> {out_path}"
        )
    _record_history(
        path, "wiki taxonomy generate",
        {"prd_doc_id": prd_doc_id,
         "out": str(out_path),
         "output_dir": str(output_dir) if output_dir else None},
        0,
        f"categories={len(cfg.categories)}",
    )


@main.command(name="remember")
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--list", "list_all", is_flag=True, help="列出所有已记录的偏好。")
@click.option("--json", "as_json", is_flag=True, help="JSON 输出。")
def remember_cmd(key: str | None, value: str | None, list_all: bool, as_json: bool) -> None:
    """记录或查询用户偏好。kb remember KEY VALUE 写入；kb remember --list 全部列出。"""
    from .memory import MemoryStore

    with MemoryStore() as m:
        if list_all or (key is None and value is None):
            prefs = m.list_prefs()
            if as_json:
                click.echo(json.dumps(prefs, indent=2, sort_keys=True, ensure_ascii=False))
            else:
                if not prefs:
                    click.echo("(no preferences set)")
                else:
                    for k, v in prefs.items():
                        click.echo(f"{k} = {v}")
            return
        if key is None or value is None:
            click.echo("usage: kb remember <key> <value>  OR  kb remember --list", err=True)
            sys.exit(2)
        m.set_pref(key, value)
        if as_json:
            click.echo(json.dumps({"ok": True, "key": key, "value": value}))
        else:
            click.echo(f"ok: {key} = {value}")


@main.command(name="forget")
@click.argument("key")
def forget_cmd(key: str) -> None:
    """删除某条偏好。"""
    from .memory import MemoryStore

    with MemoryStore() as m:
        deleted = m.forget_pref(key)
    if deleted:
        click.echo(f"forgot: {key}")
    else:
        click.echo(f"(no such key: {key})", err=True)
        sys.exit(1)


@main.command(name="recall")
@click.option("--project", "project", default=None, help="按项目根路径过滤。")
@click.option("--command", "command", default=None,
              help="按命令名过滤，如 'extract' / 'wiki build'。")
@click.option("--limit", default=20, show_default=True, help="最多返回多少条。")
@click.option("--json", "as_json", is_flag=True, help="JSON 输出。")
def recall_cmd(project: str | None, command: str | None, limit: int, as_json: bool) -> None:
    """回顾以往的 kb 命令运行历史。"""
    from .memory import MemoryStore
    from .memory.store import history_to_dicts

    with MemoryStore() as m:
        records = m.recall(project_root=project, command=command, limit=limit)

    if as_json:
        click.echo(json.dumps(list(history_to_dicts(records)),
                              indent=2, sort_keys=True, ensure_ascii=False))
    else:
        if not records:
            click.echo("(no history)")
        else:
            for r in records:
                click.echo(
                    f"{r.ts}  exit={r.exit_code:>2}  {r.command:<12}  "
                    f"{Path(r.project_root).name:<25} {r.summary}"
                )


@main.command(name="manifest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--status",
              type=click.Choice(["ok", "partial", "failed", "skipped"]),
              default=None,
              help="按状态过滤记录。")
@click.option("--format", "fmt", type=click.Choice(["table", "json", "csv"]),
              default="table", help="输出格式（默认 table）。")
@click.option(
    "--output-dir", "-o", "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="从此目录读取 kb/manifest.sqlite。",
)
def manifest_cmd(
    path: Path, status: str | None, fmt: str, output_dir: Path | None
) -> None:
    """展示项目的 manifest 记录。"""
    project_root = find_project_root(path)
    if output_dir is not None:
        output_dir = output_dir.resolve()
    db = kb_dir(project_root, output_dir) / "manifest.sqlite"
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
