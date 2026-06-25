# SP-2 设计：`kb source` - 基于 markitdown 的 source.md 源文件层

状态：已批准（设计）
日期：2026-06-24
关联：本项目升级三部曲之第二步（SP-1 脱敏层已完成，见
`2026-06-24-redaction-privacy-design.md`；SP-3 领域归纳知识库另立）。

## 1. 背景与目标

`kb extract` 产出确定性、可复现、带段落锚点的 `main.md`，作为**可溯源的证据来源**。
本层（SP-2）在其旁边再生成一份**完整、易读**的 `source.md`：用嵌入的 markitdown
库把原始文件标准化转换为 Markdown，供人阅读与 SP-3 归纳引用。

核心承诺保持不变：

- **零幻觉、确定性**：markitdown 对本地文件的转换是纯解析（不启用 LLM 图像描述），
  对同一输入 + 同一 markitdown 版本，输出 byte-identical。
- **离线**：只处理本地文件（`convert_local`），不联网，测试无需 `enable_socket`。
- **不触碰 extract 核心**：`kb source` 是独立的、可选的命令，不修改抽取管线，
  零回归风险。

## 2. 不可触碰的承重墙（与 AGENTS.md 一致）

1. markitdown **只在** `src/kb_extract/source_md.py` 内 import；
   `adapters/` 任何文件都不 import 它，`tests/test_no_llm_imports.py`
   的 AST 扫描（仅扫 adapters/）不受影响。
2. 测试默认禁用 socket。SP-2 测试只跑本地 fixture，**不**打 `enable_socket`。
3. `source.md` 写盘前必须经过 `serialization.serialize_markdown(...)` 归一化
   （strip BOM / CRLF->LF / 统一末尾换行）。
4. 输出跨平台 byte-identical：固定 markitdown 版本；不依赖 set/dict 迭代顺序。
5. 不修改 `kb extract` 的 `manifest.sqlite`、不修改 `kb verify`。

## 3. 架构与模块边界

- 新增核心模块 `src/kb_extract/source_md.py`：唯一 import markitdown 的地方。
  负责单文件转换 -> 去图 -> 脱敏 -> 归一化，返回 `(source_md_text, SourceStats)`。
- 新增 `src/kb_extract/source_manifest.py`：独立 SQLite 清单
  `kb/source.manifest.sqlite`，模式参照现有 `manifest.py`，但与之物理隔离。
- 新增 `kb source` CLI 命令（`cli.py`），选项形状对齐 `kb extract`。
- 复用：`discovery.discover_sources`、`layout.target_dir` / `kb_dir` /
  `find_project_root`、`serialization.serialize_markdown`、`redaction`
  （文本规则与策略加载）。

## 4. 数据流（逐文件）

1. `discover_sources(path)` 得到排序后的源文件列表。
2. 对每个 `src`：`out_dir = target_dir(root, src)`（即 `kb/<rel-stem>/`）。
3. **幂等检查**：查 `source.manifest.sqlite`，若 `source_sha256` +
   `markitdown_version` + `policy_sha256` 三者均未变且 `source.md` 已存在，
   记 `unchanged` 跳过（`--force` 可强制重跑）。
4. `MarkItDown().convert_local(src).text_content` 得到原始 markdown。
5. **去图**：删除所有 Markdown 图片行（`![...](...)`），无条件执行。
6. **脱敏**：若策略生效，对文本套用 `redaction` 的文本规则
   （料号等）；统计 `pn_redacted`。
7. `serialize_markdown` 归一化。
8. 写 `kb/<rel-stem>/source.md` 与 `source.meta.json` 侧车；upsert 清单。

策略解析与 `kb extract` 一致：自动发现项目根 `redaction.toml`，
`--redaction-policy <path>` 覆盖，`--no-redaction` 强制关闭。

## 5. `source.md` 内容规则

- **始终无图**：所有图片行无条件删除。markitdown 的图片处理不可靠，且
  `source.md` 的定位是"可读文本源"；确定性图片分类已由 extract 的 assets 承担。
  这样既杜绝 logo 泄漏，也让输出稳定可复现。
- **保留其余结构**：标题、表格、列表、正文按 markitdown 原样保留。
- **料号脱敏**：策略生效时对正文套用文本规则。

> 注意：默认规则 `\b[MH]\d{6,8}\b` 用 `\b` 词边界匹配，下划线属于"单词字符"，
> 因此 `M1320001_keyset.pdf` 这类紧跟下划线的料号不会被默认规则命中。需覆盖
> 此类场景请在 `redaction.toml` 自定义不依赖 `\b` 的规则。

## 6. `source.meta.json` 侧车（canonical JSON，sort_keys）

字段（仅计数与哈希，绝不含被脱敏原值）：

- `source_path`、`source_sha256`（原始输入）、`source_bytes`、`source_mtime_iso`
- `markitdown_version`
- `source_md_sha256`（归一化后 source.md 的哈希）
- `images_stripped`（整数计数）
- `pn_redacted`（整数计数）
- `policy_sha256`（字符串或 null）
- `generated_at_iso`

## 7. `source.manifest.sqlite` 模式

参照 `manifest.py`，单表 `sources`，主键为 `src.resolve().as_posix()`：

`key, source_path, source_sha256, source_bytes, source_mtime_iso,
markitdown_version, source_md_sha256, images_stripped, pn_redacted,
policy_sha256, status('ok'|'failed'|'skipped'), error_repr, generated_at_iso`。

幂等键 = `(source_sha256, markitdown_version, policy_sha256)`。

## 8. 错误处理与 CLI

- 不支持/转换失败的文件记 `failed` / `skipped` 并在报告中体现；
  单个坏文件**绝不**中断整批（对齐 extract）。
- 命令：
  `kb source [PATH] [--output-dir DIR] [--redaction-policy FILE]
  [--no-redaction] [--force] [--dry-run] [--json]`。
- 人类可读汇总（机器可解析部分保持英文）：
  `ok=N failed=N skipped=N unchanged=N redacted_pn=N images_stripped=N`。
- `--json` 输出结构化报告（含每文件状态与计数）。

## 9. 测试（TDD）

单元测试（`tests/test_source_md.py`）：

- 去图：含 `![alt](path)` 与 data-uri 图片的 markdown -> 全部删除，正文保留。
- 文本脱敏：料号被替换并计数；无策略时不改文本。
- 归一化：CRLF/BOM/多余末尾换行被规整为 LF + 单末尾换行。
- 侧车：字段完整、键有序、仅计数（无原值泄漏）。
- 幂等键逻辑：三元组任一变化 -> 需重跑；全等 -> unchanged。
- 隔离守卫：AST 扫描 `source_md.py` 不 import 任何 LLM SDK（openai 等）；
  并断言 markitdown 仅在该模块出现。

集成测试：

- `kb source` 跑 fixture 树（如一个 `.html` 或 `.docx` 小样本）：
  断言 `source.md` 内容、无图片、脱敏生效、侧车哈希正确。
- 第二次运行记 `unchanged`；两次独立运行 source.md byte-identical。
- 一个坏文件不影响其余文件成功。

## 10. 范围边界（YAGNI）

不在 SP-2：

- 任何 LLM/归纳/领域分类（属 SP-3）。
- 修改 `kb verify` 或 extract 的 `manifest.sqlite`。
- source.md 中的锚点/章节结构（它是可读文本源，不是证据锚点载体）。
- URL/远程输入（仅本地文件）。

## 11. 版本

实现完成后 `pyproject.toml` 次版本号 +1（预期 0.11.0 -> 0.12.0），
README（简体中文）补充 `kb source` 用法，CHANGELOG 记 `[0.12.0]`。
新增依赖 `markitdown`（按需选 format extras），在实现时用 `uv add` 固定版本。
