# 更新日志

所有重要的版本变更都会记录在本文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

## [0.1.0] — 2026-06-09

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
