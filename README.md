# kb-extract

> 个人知识库抽取流水线：把 PDF / DOCX / XLSX / PPTX / PNG·JPG / ZIP 文档
> 转成**确定性**、**可追溯到段落级别**的 Markdown 知识库；
> 同时以 **Copilot CLI 技能** 与 **VS Code 任务** 的形式封装好，开箱即用。

[![CI](https://github.com/XUMAX-GH/kb-extract/actions/workflows/ci.yml/badge.svg)](https://github.com/XUMAX-GH/kb-extract/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](CHANGELOG.md)

---

## 为什么需要这个工具

工程师每天都在处理大量异构文档（设计规格、需求 Excel、培训 PPT、签到 PDF……）。
想拿这些资料喂给 LLM / RAG / Wiki，必须先把它们整理成**结构化**、**可引用**、
**可校验**的 Markdown。但市面上大多数文档抽取工具有两个致命问题：

1. **幻觉**：用 LLM 帮你"清洗"文档，结果在抽取阶段就开始改写、补全、瞎猜。
2. **不可复现**：同一份 PDF 抽两次得到不同的 hash，没法做去重和审计。

`kb-extract` 的设计原则非常硬：

- ⛔ **抽取阶段绝不调用任何 LLM**。整个 adapters 层连 `import openai`、`import anthropic`
  这样的语句都被 AST 静态扫描 ban 掉（H2 不变量）。
- ⛔ **抽取过程禁用网络**。`pytest-socket` 在测试期把 socket 全部封死（H1 不变量）。
- ✅ **逐 byte 可复现**。同一份源文件、同一个适配器版本，跨平台、跨次运行
  的输出 SHA-256 必须完全一致（H8 / H13 不变量；GitHub Actions 矩阵自动比对
  Ubuntu / Windows / macOS 三家的输出 hash）。
- ✅ **段落级可追溯**。每个段落都打了不可见的 `<a id="...">` 锚点，
  侧车 `index.json` 保证每个锚点被引用且仅引用一次（H3 / H4 不变量）。

未来在它之上做 LLM 整理（PageIndex 重排、Karpathy LLM-Wiki、Obsidian Wiki……）
时，所有上层产物都能精确引用到 *这一段* 出自 *这一篇文档* 的 *这一页* —— 这就是
"hardness engineering"（硬度工程）的意义。

---

## 安装

### 前置条件

- Python **3.11+**
- [uv](https://github.com/astral-sh/uv)（推荐的 Python 包管理器）

### 一键安装 CLI

```powershell
# Windows
git clone https://github.com/XUMAX-GH/kb-extract.git
cd kb-extract
.\install.ps1
```

```bash
# macOS / Linux
git clone https://github.com/XUMAX-GH/kb-extract.git
cd kb-extract
./install.sh
```

安装脚本会：

1. 在 `~/.kb-extract/venv` 创建独立 venv（不污染系统 Python）。
2. 把 kb-extract 以可编辑模式装进 venv。
3. 预下载 docling 模型（首次几分钟，后续完全离线可用）。
4. 提示你把 `~/.kb-extract/venv/bin`（或 `Scripts`）加进 PATH。

完成后运行：

```bash
kb --version          # 0.1.0
kb adapters           # 列出 5 个内置适配器
```

### 卸载

```powershell
.\uninstall.ps1       # Windows
./uninstall.sh        # macOS / Linux
```

---

## 快速上手

假设你有一个项目文件夹 `~/projects/Surface-Designs/`，里面散落着各种文档：

```
Surface-Designs/
├── thermal-spec.pdf
├── BOM-rev3.xlsx
├── kickoff-deck.pptx
└── reference-images/
    └── flow-diagram.png
```

抽取整个文件夹：

```bash
kb extract ~/projects/Surface-Designs
```

结束后多了一个 `kb/` 子目录：

```
Surface-Designs/
├── ... (原始文件原封不动)
└── kb/
    ├── manifest.sqlite                  # 项目级总索引（含每份源文件的 SHA-256）
    ├── thermal-spec/
    │   ├── main.md                      # 带不可见锚点的 Markdown
    │   ├── index.json                   # PageIndex 风格章节树
    │   ├── meta.json                    # 来源、警告、工具版本
    │   └── assets/                      # 图片、表格渲染
    ├── BOM-rev3/...
    ├── kickoff-deck/...
    └── reference-images/flow-diagram/...
```

校验产物没有被篡改、所有不变量仍然成立：

```bash
kb verify ~/projects/Surface-Designs
```

查看清单：

```bash
kb manifest ~/projects/Surface-Designs                          # 表格
kb manifest ~/projects/Surface-Designs --format json            # JSON
kb manifest ~/projects/Surface-Designs --status partial         # 只看部分失败的
```

---

## CLI 用法

```
kb extract <path> [--force] [--dry-run] [--json] [--only ext[,ext]] [--adapter name] [-o <output-dir>]
kb verify  <path>  [--json] [--fail-fast] [-o <output-dir>]
kb manifest <path> [--status ok|partial|failed|skipped] [--format table|json|csv] [-o <output-dir>]
kb adapters [--json]
kb --version
```

退出码：

| 退出码 | 含义 |
|---|---|
| `0` | 一切正常 |
| `1` | 至少一份源文件失败 / partial |
| `2` | 命令行用法错误（Click 默认） |
| `3` | `verify` 检测到 hardness 违规 |

### `--output-dir / -o`（v0.5.0 起）

默认情况下，`kb/` 和 `wiki/` 直接生成在源文件根目录下；如果你不希望抽取
产物污染源目录（例如源在只读盘、或希望分项目集中管理 markdown 仓库），
可以用 `-o <dir>` 把产物重定向到任意目录：

```bash
# 源文件保持不动，所有 markdown / 资源 / manifest 都生成到 D:\kb-out\
kb extract -o D:\kb-out C:\specs\BerryCreek
kb verify  -o D:\kb-out C:\specs\BerryCreek
kb wiki build  -o D:\kb-out --provider mock --seed 0 C:\specs\BerryCreek
kb wiki verify -o D:\kb-out C:\specs\BerryCreek
```

- 输出目录不存在会自动创建（`mkdir -p`）。
- 多源批处理时，每份源在 `<output-dir>/kb/` 下的相对路径，仍以 *源根目录*
  的相对路径为准，原始层级会被完整保留。
- wiki 的相对链接 `../kb/<doc>/main.md#<anchor>` 仍然可解析（因为 `kb/` 和
  `wiki/` 在 `<output-dir>` 下是兄弟目录）。

---

## LLM-Wiki 层（v0.3+）

在 `kb/` 之上再生成一层带 evidence pin 的 wiki 文档（Karpathy LLM-Wiki 风格）。
**抽取层**仍然 0 LLM；**只有 wiki 层**允许调 LLM。

```bash
# 用默认 mock provider（零网络，CI 可用）构建 wiki
kb wiki build ./MyProject --provider mock --seed 0

# 校验所有 [^ev-N] 都能解析到真实 anchor (H14)
kb wiki verify ./MyProject
```

输出布局：

```
<project>/wiki/
  index.json            ← topic 列表 + provider/seed 元数据
  thermal.md            ← "## ... [^ev-1][^ev-2]" 文末附 footnote 定义
  power.md
  ...
```

每个 wiki 文档的每段事实都附 `[^ev-N]` 脚注，自动指向
`../kb/<doc>/main.md#<anchor>`。新增 3 条 hardness 不变量：

- **H14**：每个 `[^ev-N]` 都解析到真实 kb anchor（`kb wiki verify` 强制）
- **H15**：固定 `--provider mock --seed N` 时输出 byte 一致（确定性）
- **H16**：`kb wiki build` 不修改 `kb/` 下任何文件
- **H17**（v0.4+）：每个 `[^ev-N]` 指向的 anchor 在目标文件中**唯一**出现
- **H18**（v0.4+）：跨多源文档的 topic，`index.json` 必须列全 `evidence_origins`

切换 provider 用环境变量或 `--provider`：

```bash
KB_EXTRACT_LLM_PROVIDER=openai kb wiki build ./MyProject
# v0.3 仅实现了 mock；openai/anthropic/ollama 留了 protocol 占位
```

---

## 用户偏好与命令历史（v0.4+）

`kb` 自带一个轻量本地记忆层（sqlite，WAL 模式，多进程并发安全）。
**默认路径**：`~/.kb-extract/memory.db`（可用 `KB_EXTRACT_HOME` 覆盖）。

```bash
# 偏好
kb remember default_provider mock     # 写
kb remember --list                    # 列出全部
kb forget default_provider            # 删

# 历史（自动记录）—— 每次 kb extract / verify / wiki build / wiki verify 都会写一条
kb recall                             # 默认显示最近 20 条
kb recall --project ./MyProject       # 按项目过滤
kb recall --command "wiki build"      # 按命令过滤
kb recall --json                      # 机器可读
```

写入失败时静默（决不破坏主命令）。新增 hardness：

- **H20**（v0.4+）：memory 写入使用 `WAL + BEGIN IMMEDIATE`，多线程/多进程并发不会损坏数据库

---

## 作为 Copilot CLI 技能安装

本仓库本身就是一个 **Copilot CLI 插件**（含 `.claude-plugin/marketplace.json`
和 `.claude-plugin/plugin.json`）。在你的 Copilot CLI 里运行：

```
/plugin marketplace add XUMAX-GH/kb-extract
/plugin install kb-extract
```

或者直接在 `~/.copilot/settings.json` 的 `extraKnownMarketplaces` 里加上：

```json
{
  "extraKnownMarketplaces": {
    "kb-extract": {
      "source": { "source": "github", "repo": "XUMAX-GH/kb-extract" }
    }
  },
  "enabledPlugins": {
    "kb-extract@kb-extract": true
  }
}
```

启用后，在 Copilot CLI 里说这些短语就会自动触发本技能：

- "提取这个文件夹" / "extract this folder"
- "构建知识库" / "build kb from folder"
- "校验知识库" / "verify kb"

技能会先跑 `kb adapters` 检查 CLI 是否安装，再调 `kb extract --json`，
把摘要原样呈现给你 —— **永远不会**改写或润色抽取产物（这是 SKILL.md
里写死的契约条款）。

---

## VS Code 集成

把 [`.vscode/tasks.json.example`](./.vscode/tasks.json.example) 复制成你项目的
`.vscode/tasks.json`，你就能在 VS Code 命令面板里直接跑：

- `KB: Extract current folder`
- `KB: Extract current folder (force)`
- `KB: Verify project`
- `KB: Show manifest`

---

## 架构概览（v1）

```
kb extract <path> ──► orchestrator ──► Extractor (按格式分派的适配器)
                                              │
                                              ▼
                              ExtractionResult 数据契约
                                              │
                                              ▼
                              hardness.assert_invariants
                                              │
                                              ▼
                              原子写入 <project>/kb/<doc>/
```

### 内置适配器

| 适配器 | 支持扩展名 | 实现 |
|---|---|---|
| `pdf_docling` | `.pdf` | PyMuPDF；v0.2 起按 TOC `level` 字段重建多层嵌套树；无 TOC 时按字号 / 字重确定性聚类推断 heading（`outline_source="heading_inferred"`） |
| `docx` | `.docx` | python-docx，保留章节层级 |
| `xlsx` | `.xlsx` | openpyxl，逐 sheet → 表格化 Markdown；v0.2 起按 sheet 名前缀数字自然排序 |
| `pptx` | `.pptx` | python-pptx；v0.2 起检测 PowerPoint 原生"节"形成 root → section → slide 两层树（`outline_source="pptx_section"`） |
| `image` | `.png` / `.jpg` / `.jpeg` | Pillow，仅元数据 + 资产搬运 |
| `zip` | `.zip` | 递归调用 orchestrator（深度上限 5） |

> **v0.2.0 章节质量分级**：所有 `meta.json` 现在多了 `outline_confidence`
> 字段（`high` / `medium` / `low`）。直接来自源文件结构（DOCX heading style /
> PDF TOC / PPTX section）的为 `high`；通过字号启发式推断出的为 `medium`
> 或 `low`，下游 LLM-Wiki 层据此分流处理。

---

## Hardness 不变量（共 17 条）

| 编号 | 描述 |
|---|---|
| H1 | 抽取过程禁用 socket（`pytest-socket` 在测试中强制） |
| H2 | adapters 层不允许 import 任何 LLM SDK / `kb_extract.wiki` / `kb_extract.memory`（AST 静态扫描） |
| H3 | 每个段落都有不可见的 `<a id="...">` 锚点 |
| H4 | `index.json` 引用且仅引用一次每个锚点 |
| H5 | `main.md` 的 SHA-256 与 manifest 记录一致 |
| H6 | `meta.json` 必须含 `tool_versions` 与 `extraction_time_utc` |
| H7 | 所有写入都是原子的（写临时文件后 rename） |
| H8 | 同一源文件、同一适配器版本，跨次运行输出**逐 byte 一致** |
| H9 | `--dry-run` 绝不改动磁盘 |
| H10 | 适配器抛异常不会损坏既有产物 |
| H11 | manifest 的 source_sha256 ↔ 文件 SHA-256 必须吻合 |
| H12 | 同一源路径在 manifest 中唯一 |
| H13 | 同源文件在 Ubuntu / Windows / macOS 三平台输出 hash 一致 |
| H14 | 每个 wiki `[^ev-N]` 都解析到真实 kb anchor（v0.3+） |
| H15 | 固定 LLM provider + seed 时 wiki 输出 byte 一致（v0.3+） |
| H16 | `kb wiki build` 不修改 `kb/` 下任何文件（v0.3+） |
| H17 | 每个 wiki `[^ev-N]` 指向的 anchor 在目标文件中**唯一**出现（v0.4+） |
| H18 | 跨多源文档的 topic 必须在 `index.json` 中列全 `evidence_origins`（v0.4+） |
| H20 | memory 写入 WAL + IMMEDIATE，多进程并发安全（v0.4+） |

`kb verify` 把抽取相关的约束全部重跑一遍，任何一条违规都返回退出码 3。
`kb wiki verify` 校验 H14/H17/H18。

---

## 项目布局

```
<project>/<source-file>            (原文件原封不动)
<project>/kb/manifest.sqlite       项目级索引
<project>/kb/<doc>/main.md         带不可见锚点的 Markdown
<project>/kb/<doc>/index.json      PageIndex 风格章节树
<project>/kb/<doc>/meta.json       来源、警告、工具版本
<project>/kb/<doc>/assets/         图片、表格渲染
```

---

## 暂不在 v1 范围

- LLM 辅助章节重排（PageIndex / Karpathy LLM-Wiki / Obsidian Wiki 的 v1.1 sub-project）
- 扫描版 PDF 的 OCR
- STP / CAD 元数据抽取、Visio
- 跨文档 wiki 组织
- 用户习惯记忆 / 提问历史
- 真正接入 docling 模型（v1 仅用 PyMuPDF 占位）

每一项都已经列入路线图，会作为独立的 sub-project 写计划再做。

---

## 开发

```bash
# 跑测试
uv run pytest

# 静态检查
uv run ruff check .

# 性能基准（100 页合成 PDF，1.5× 回归阈值）
uv run pytest -m perf
```

CI 在 `{ubuntu, windows, macos} × {py3.11, py3.12}` 矩阵上跑全套测试，
额外有：

- `cross_platform_identity` job：比对三平台输出 hash（H13）
- `performance` job：基线在 `tests/fixtures/perf-baseline.json`

---

## 许可证

[MIT](LICENSE) © XUMAX-GH

---

## 致谢

- 灵感来源：[VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)、
  [karpathy 的 LLM-Wiki 构想](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)、
  [Ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)
- 实现：与 GitHub Copilot CLI 协同完成（commit 中以 `Co-authored-by` 标记）
