# 更新日志

所有重要的版本变更都会记录在本文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

## [0.4.0] — 2026-06-09

合并 sp4（hardness 扩展）+ sp5（memory layer）到同一发行版。

### 新增 — sp4 hardness extensions

- **H17 `citation-graph-integrity`**：wiki 中每个 `[^ev-N]` 指向的 anchor 不仅
  要存在于对应 `kb/<doc>/main.md`，还必须**唯一**出现。`kb wiki verify` 现在
  会同时检查存在性和唯一性。
- **H18 `multi-source-provenance`**：当一个 topic 的 evidence 跨多份源文档时，
  `wiki/index.json` 的 `topics[].evidence_origins` 字段必须列出全部 source sha256
  （从 `kb/manifest.sqlite` 读取）。`kb wiki verify` 会比对实际 origins 与声明 origins。
- **H19 `wiki-mock-byte-stability`**（CI 强制）：v0.3 的 H15 只保证同进程同
  seed 输出 byte 一致；H19 进一步要求跨 OS 也一致（CI 增加跨平台 hash 比对 job）。
- **H2 边界扩展**：adapters 不仅不能 import LLM SDK，也不能 import `kb_extract.wiki`
  或 `kb_extract.memory`（防止反向依赖）。

### 新增 — sp5 memory layer

- **`src/kb_extract/memory/`** 模块：sqlite 持久层（WAL + BEGIN IMMEDIATE，
  支持多进程并发，对应新 hardness 约束 **H20**）。
- **新 CLI 子命令**：
  - `kb remember <key> <value>` / `kb remember --list` —— 用户偏好读写
  - `kb forget <key>` —— 删偏好
  - `kb recall [--project X] [--command Y] [--limit N]` —— 回顾命令历史
- **自动 history hook**：`kb extract` / `kb verify` / `kb wiki build` /
  `kb wiki verify` 每次运行结束自动记录一条 history（含 exit_code、参数、摘要）。
  写入失败时静默（决不破坏主命令）。
- **路径解析**：默认 `~/.kb-extract/memory.db`；可用 `KB_EXTRACT_HOME` 环境变量覆盖。

### 测试

- 新增 5 个测试文件，25 个测试：`test_h17_citation_uniqueness.py`、
  `test_h18_multi_source.py`、`test_memory_store.py`、`test_memory_cli.py`、
  `test_memory_hooks.py`
- 总用例数：210 → 235 (+25)

### 兼容性

- `wiki/index.json` schema 新增 `evidence_origins` 字段（每个 topic 一份）。
  老 v0.3 的 index.json 缺少该字段，重新跑一次 `kb wiki build` 即可补上。
- v0.4 的 memory.db 不存在时自动创建；卸载 kb 不会自动清除 memory.db
  （保留用户数据；如需彻底删除请手动 `rm ~/.kb-extract/memory.db`）。

## [0.3.0] — 2026-06-09

LLM-Wiki 层 (Karpathy LLM-Wiki 风格)：在 v0.2 抽取产物之上，构建带强制
evidence pin 的二级 wiki 文档。这是包内**唯一**允许调 LLM 的层；
adapters 仍然受 H2 不变量约束。

### 新增

- **新 CLI 子命令组** `kb wiki`：
  - `kb wiki build <project>`：基于 `<project>/kb/` 重建 `<project>/wiki/`
  - `kb wiki verify <project>`：校验所有 evidence pin 都能解析到真实 anchor
- **可插拔的 LLM provider 协议** (`src/kb_extract/wiki/providers/`)：
  - `MockLlmClient`：完全确定性的零网络 provider，CI 默认
  - `openai` / `anthropic` / `ollama` 留了占位接口（NotImplementedError，
    在 v0.4 接真实 SDK）
  - 通过 `--provider` 或 `KB_EXTRACT_LLM_PROVIDER` 环境变量切换
- **纯算法 topic 聚类** (`wiki/topics.py`)：从 `kb/<doc>/index.json` 收集叶子
  section title，按词集合 Jaccard 距离 (≤ 0.85) 做 single-linkage 聚类，
  跨文档自动合并相似主题。无 LLM。
- **Evidence pin 与脚注解析** (`wiki/writer.py`)：LLM 生成的每个 `[^ev-N]`
  自动追加 `[^ev-N]: [Section Title (p.X)](../kb/<doc>/main.md#<anchor>)` 脚注定义。
  越界编号会被显式标记为 `UNRESOLVED`。
- **3 条新增 hardness 不变量**：
  - **H14** `evidence-pin-resolves`: 每个 `[^ev-N]` 都指向真实存在的 kb anchor
  - **H15** `wiki-determinism-under-seed`: 固定 provider + seed 时 wiki/ 全部
    输出 byte 一致
  - **H16** `no-extract-side-effect`: `kb wiki build` 不修改 `kb/` 下任何文件
- **adapters 层导入边界自动检查**：测试 `test_adapter_does_not_import_from_wiki_layer`
  保证 adapters 永远不会反向依赖 wiki 层（H2 扩展）。

### 测试

- 新增 4 个测试文件，22 个测试：`test_wiki_mock_provider.py`、
  `test_wiki_topics.py`、`test_wiki_writer.py`、`test_wiki_e2e.py`
- adapters H2 测试自动从 11 个增长到 22 个（每个 adapter ×2 条不变量）
- 总用例数：177 → 199 (+22 sp3)

### 兼容性

- v0.3 的 `kb extract` 行为与 v0.2 完全一致
- 旧版本（v0.1 / v0.2）的 `kb/` 产物可以直接 `kb wiki build`，无需重抽
- `meta.json` schema 未改

## [0.2.0] — 2026-06-09

PageIndex 风格的章节树精炼。所有已抽取的 `kb/` 内容哈希都会变化，
首次重新提取会触发全量更新（这是预期行为，见下方"破坏性变更"）。

### 新增

- **真·递归章节树**：之前所有适配器都把章节压成两层（root + level=1 叶子），
  现在 PDF / PPTX 在条件具备时会构建多层嵌套：
  - `PDF` 用 PyMuPDF 的 TOC `level` 字段，原样保留章 / 节 / 小节嵌套
  - `PPTX` 检测 PowerPoint 原生"节"（Sections），形成 root → section → slide 两层
- **PDF 字号启发式 heading 推断**（`pdf_heading_infer.py`）：当 PDF 没有 TOC 时，
  按字号 / 字重纯数值聚类推断 heading 层级。完全确定性，无 LLM、无随机性。
  量化到 0.5pt 规避浮点抖动，保证 H8 / H13 不变量。
  - 标记为 `outline_source="heading_inferred"`，与 bookmark 来源区分
  - 通过 `outline_confidence` 字段（`high`/`medium`/`low`）暴露质量等级
- **XLSX 确定性排序**：sheet 按命名前缀数字自然排序（`01_Intro` 在 `10_Appendix` 前），
  无前缀数字的 sheet 按字典序追加在后面
- **`ExtractionMeta.outline_confidence` 新字段**：三档（`high` / `medium` / `low`），
  下游消费者（LLM-Wiki 层、人工 review 流程）可据此分流处理

### 扩展

- `outline_source` 枚举新增 `heading_inferred` / `pptx_section` 两个值
- `PdfDoclingAdapter.version` → `0.2`；`PptxAdapter.version` → `0.2`

### 破坏性变更（仅影响缓存）

- 由于 index 树结构变化，`ExtractionResult.content_sha256()` 哈希结果会变；
  现有 `kb/<doc>/manifest.sqlite` 中的旧条目会被视为"已变更"，首次运行
  `kb extract` 会全量重新提取所有源文档。这是有意为之 — 老的扁平 index
  本身就是 PageIndex 设计的债务清理对象。
- `meta.json` schema 增加 `outline_confidence`；老的 `meta.json` 仍可读
  （dataclass 提供 `"high"` 默认值），但不建议混用。

### 测试

- 新增 5 个测试文件 / 共 15 个测试：`test_xlsx_sort.py`、`test_pptx_sections.py`、
  `test_pdf_tree.py`、`test_pdf_heading_inference.py`、`test_outline_confidence.py`
- 总用例数：160 → 177（+15 sp2 + 2 baseline migrations）

## [0.1.0] — 2026-06-09

首个公开版本。完成了完整的 34 个 TDD 任务，共 160 个测试用例全部通过、
ruff 静态检查 0 警告。

### 新增

- **`kb` 命令行工具**，4 个子命令：`extract` / `verify` / `manifest` / `adapters`,
  以及全局 `--version`。
- **6 个文档适配器**：
  - `pdf_docling`（基于 PyMuPDF，处理 `.pdf`）
  - `docx`（python-docx，保留章节层级）
  - `xlsx`（openpyxl，逐 sheet → 表格化 Markdown）
  - `pptx`（python-pptx，每页一节）
  - `image`（Pillow，PNG / JPG，仅元数据 + 资产搬运）
  - `zip`（递归调用 orchestrator，深度上限 5 层）
- **13 条 hardness 不变量** 全部机器可验证（H1 socket 封禁、H2 无 LLM 导入、
  H3-H4 段落锚点唯一引用、H5-H7 SHA-256 / 原子写入、H8 跨次运行逐 byte 一致、
  H9 dry-run 不动磁盘、H10 异常不损坏既有产物、H11-H12 manifest 完整性、
  H13 跨平台输出一致性）。
- **Copilot CLI 技能** `skills/kb-extract/`，提供 `extract` / `verify`
  两个 shell 入口，从不绕过 CLI 直接 import 包。
- **VS Code 任务模板** `.vscode/tasks.json.example`。
- **跨平台 CI**：GitHub Actions 矩阵 `{ubuntu, windows, macos} × {py3.11, py3.12}`,
  额外含 H13 跨平台 hash 比对 job 与 100 页 PDF 性能基准 job（1.5× 回归阈值）。
- **安装脚本** `install.{ps1,sh}` / `uninstall.{ps1,sh}`,
  在 `~/.kb-extract/venv` 创建独立 venv，预下载 docling 模型。
- **Copilot CLI 插件清单** `.claude-plugin/{plugin,marketplace}.json`,
  可通过 `/plugin marketplace add XUMAX-GH/kb-extract` 一键安装。

### 已知遗留事项

- `pdf_docling` 适配器目前**仅用 PyMuPDF**，并未真正调用 docling 模型；
  仓库依赖里仍带 `docling`，留作 v1.1 接入。
- `docx` 适配器引用了 `langdetect`，未显式设置 `DetectorFactory.seed`；
  因当前 H8 测试仅覆盖 NoopAdapter，e2e 路径靠 manifest 短路命中也避开了
  这条潜在的不确定性 —— 但若未来在真实 docx 上测试 `--force`，需要修补。
- 性能基线（`tests/fixtures/perf-baseline.json` = 30 秒）非常宽松；
  待 Ubuntu CI 给出实际数字后再收紧到 2 倍左右。

### Bug 修复（v1 实现期间发现）

- **`ExtractionResult.content_sha256()`** 之前对原始 markdown 求 hash，
  但 orchestrator 写盘前会过 `serialize_markdown` 做归一化（去 BOM、
  CRLF→LF、统一末尾换行）。这导致真实适配器（docx/pdf/xlsx/pptx）
  的 verify 步骤总是失败 —— 仅靠 NoopAdapter 的 markdown 恰好已经归一化
  这一巧合，逃过了之前所有测试。修复：`content_sha256` 改为先归一化再 hash。
- **`verify._doc_dirs()`** 之前对 `kb/` 做 `rglob("main.md")`,
  会把 zip 适配器的嵌套 `kb/<zipname>/_unpacked/kb/.../main.md` 也算上，
  而这些嵌套产物的 manifest 是 per-zip 独立的，导致 verify 误报。
  修复：仅取深度为 2 的直接子目录（`kb/<doc>/main.md`）。

两个 bug 都是上线即坏，只有 e2e 测试能暴露 —— 这就是为什么花精力做
端到端验收测试是值得的。

首个公开版本。完成了完整的 34 个 TDD 任务，共 160 个测试用例全部通过、
ruff 静态检查 0 警告。

### 新增

- **`kb` 命令行工具**，4 个子命令：`extract` / `verify` / `manifest` / `adapters`，
  以及全局 `--version`。
- **6 个文档适配器**：
  - `pdf_docling`（基于 PyMuPDF，处理 `.pdf`）
  - `docx`（python-docx，保留章节层级）
  - `xlsx`（openpyxl，逐 sheet → 表格化 Markdown）
  - `pptx`（python-pptx，每页一节）
  - `image`（Pillow，PNG / JPG，仅元数据 + 资产搬运）
  - `zip`（递归调用 orchestrator，深度上限 5 层）
- **13 条 hardness 不变量** 全部机器可验证（H1 socket 封禁、H2 无 LLM 导入、
  H3-H4 段落锚点唯一引用、H5-H7 SHA-256 / 原子写入、H8 跨次运行逐 byte 一致、
  H9 dry-run 不动磁盘、H10 异常不损坏既有产物、H11-H12 manifest 完整性、
  H13 跨平台输出一致性）。
- **Copilot CLI 技能** `skills/kb-extract/`，提供 `extract` / `verify`
  两个 shell 入口，从不绕过 CLI 直接 import 包。
- **VS Code 任务模板** `.vscode/tasks.json.example`。
- **跨平台 CI**：GitHub Actions 矩阵 `{ubuntu, windows, macos} × {py3.11, py3.12}`，
  额外含 H13 跨平台 hash 比对 job 与 100 页 PDF 性能基准 job（1.5× 回归阈值）。
- **安装脚本** `install.{ps1,sh}` / `uninstall.{ps1,sh}`，
  在 `~/.kb-extract/venv` 创建独立 venv，预下载 docling 模型。
- **Copilot CLI 插件清单** `.claude-plugin/{plugin,marketplace}.json`，
  可通过 `/plugin marketplace add XUMAX-GH/kb-extract` 一键安装。

### 已知遗留事项

- `pdf_docling` 适配器目前**仅用 PyMuPDF**，并未真正调用 docling 模型；
  仓库依赖里仍带 `docling`，留作 v1.1 接入。
- `docx` 适配器引用了 `langdetect`，未显式设置 `DetectorFactory.seed`；
  因当前 H8 测试仅覆盖 NoopAdapter，e2e 路径靠 manifest 短路命中也避开了
  这条潜在的不确定性 —— 但若未来在真实 docx 上测试 `--force`，需要修补。
- 性能基线（`tests/fixtures/perf-baseline.json` = 30 秒）非常宽松；
  待 Ubuntu CI 给出实际数字后再收紧到 2 倍左右。

### Bug 修复（v1 实现期间发现）

- **`ExtractionResult.content_sha256()`** 之前对原始 markdown 求 hash，
  但 orchestrator 写盘前会过 `serialize_markdown` 做归一化（去 BOM、
  CRLF→LF、统一末尾换行）。这导致真实适配器（docx/pdf/xlsx/pptx）
  的 verify 步骤总是失败 —— 仅靠 NoopAdapter 的 markdown 恰好已经归一化
  这一巧合，逃过了之前所有测试。修复：`content_sha256` 改为先归一化再 hash。
- **`verify._doc_dirs()`** 之前对 `kb/` 做 `rglob("main.md")`，
  会把 zip 适配器的嵌套 `kb/<zipname>/_unpacked/kb/.../main.md` 也算上，
  而这些嵌套产物的 manifest 是 per-zip 独立的，导致 verify 误报。
  修复：仅取深度为 2 的直接子目录（`kb/<doc>/main.md`）。

两个 bug 都是上线即坏，只有 e2e 测试能暴露 —— 这就是为什么花精力做
端到端验收测试是值得的。
