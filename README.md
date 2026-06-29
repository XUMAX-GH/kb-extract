# kb-extract

> 个人知识库抽取流水线：把 PDF / DOCX / XLSX / PPTX / PNG·JPG / ZIP 文档
> 转成**确定性**、**可追溯到段落级别**的 Markdown 知识库；
> 同时以 **Copilot CLI 技能** 与 **VS Code 任务** 的形式封装好，开箱即用。

[![CI](https://github.com/XUMAX-GH/kb-extract/actions/workflows/ci.yml/badge.svg)](https://github.com/XUMAX-GH/kb-extract/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.19.0-blue.svg)](CHANGELOG.md)

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
kb --version          # 0.19.0
kb adapters           # 列出 5 个内置适配器（4 个 v2 + 1 个 image）
```

## 脱敏 / 隐私

工程文档常含机密料号与公司 logo。在项目根放一份 `redaction.toml` 即可在
**抽取产物落盘前**确定性脱敏（不破坏段落锚点，仍逐 byte 可复现）：

```toml
[redaction]
enabled = true

[[redaction.text]]
pattern = '(?i)\b[MH]\d{6,8}\b'   # M132xxxx / H123xxxx 料号
replacement = "[PN-REDACTED]"

[redaction.logos]
sha256 = []                       # 资产 sha256 精确匹配
filename_globs = ["*logo*"]
alt_globs = ["*logo*"]
```

运行 `kb extract .`（或 `--redaction-policy <path>`；`--no-redaction` 可强制关闭）。
每份文档会额外写出 `redaction.json` 审计侧车（只含计数，不含被脱敏原值）。

脱敏范围覆盖落盘的全部产物：`main.md` 正文、`index.json` 的章节标题、以及
`meta.json` 的源文件名 / 警告 / 跳过原因。段落锚点 `<a id="...">` 与节点 id
永不改动。

> 注意：默认规则 `\b[MH]\d{6,8}\b` 用 `\b` 词边界匹配，下划线属于"单词字符"，
> 因此 `M1320001_keyset.pdf` 这种紧跟下划线的料号不会被默认规则命中。如需覆盖此类
> 文件名，请在 `redaction.toml` 自定义不依赖 `\b` 的规则
> （例如 `pattern = '(?i)[MH]\d{6,8}'`）。

## source.md 源文件层（kb source）

`kb source` 用嵌入的 markitdown 把原始文件转换为一份完整、易读的
`source.md`（写在 `kb/<doc>/source.md`），作为人类阅读与后续归纳的源文件。
它与确定性的 `kb extract` 完全独立，不修改抽取产物：

```bash
kb source .                 # 为当前目录下所有文档生成 source.md
kb source . --no-redaction  # 不脱敏
kb source . --json          # 结构化报告
```

特性：

- **始终无图**：所有图片引用都会被移除，杜绝 logo 泄漏，保证可读纯文本。
- **料号脱敏**：若存在 `redaction.toml`，正文中的料号会按规则脱敏
  （复用 `kb extract` 的同一策略）。
- **确定性 + 幂等**：输出经归一化（LF / 无 BOM），对同一输入与同一
  markitdown 版本 byte-identical；`kb/source.manifest.sqlite` 记录哈希，
  未变更的文件再次运行记为 `unchanged`。
- 每份文档附带 `source.meta.json` 侧车（只含哈希与计数，不含被脱敏原值）。

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
kb extract -o D:\kb-out C:\specs\BC
kb verify  -o D:\kb-out C:\specs\BC
kb wiki build  -o D:\kb-out --provider mock --seed 0 C:\specs\BC
kb wiki verify -o D:\kb-out C:\specs\BC
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

## PRD 驱动的 Wiki 分类（v0.7.0）

之前的 wiki 把所有事实塞进 `_uncategorized`，不利于按主题浏览。
从 v0.7.0 起，可以**从 PRD 文档结构自动生成 taxonomy 配置**，
然后按 PRD 章节把事实分流到不同的 wiki 文件。

```bash
# 1) 先做一次 kb extract，让 PRD 进入 kb/
kb extract ./MyProject

# 2) 从 PRD 一级 / 二级标题自动生成 wiki/taxonomy.json
kb wiki taxonomy generate ./MyProject \
    --prd-doc-id <PRD 文档目录名> \
    -o ./MyProject

# 3) 重新构建 wiki，所有 evidence 会按 4 层优先级被路由：
#    显式 doc_id 命中 > PES 文档号引用 > 章节标题映射 > 关键词
kb wiki build ./MyProject --provider mock --seed 0
```

新增不变量：

- **H21**：`taxonomy.json` 必须满足 schema 完整性（version、source_prd、
  唯一 slug、空 keywords 等等都由 `validate_taxonomy` 强制）。

---

## Parser v2（v0.8.0）

v0.8.0 把 4 个核心解析器（PDF / DOCX / PPTX / XLSX）整体重写为 **v2 实现**，
统一引入了：

- **真实图片落盘**：所有内联图片以 `bytes → kb/<doc>/assets/img-<sha8>.<ext>`
  形式确定性命名（基于内容 SHA-256 前 8 位），Markdown 中以
  `![alt](../assets/img-xxxxxxxx.png)` 引用，跨平台 byte-identical。
- **更稳健的章节切分**：合并样式 + 字号启发，避免漏掉无样式但视觉上明显
  的标题；表格转 GFM，列对齐与 NBSP 行为规范化。
- **图像完整性 H22**：任何 adapter 写入 `assets/` 必须经过 `save_image()`
  辅助函数（统一计算 hash、原子写入、防止内容漂移）。AST 静态检查
  禁止 adapters 层绕过 `save_image` 直接 `Path.write_bytes`。

升级是**完全兼容**的：旧产物用 `kb verify` 校验仍然过得了，但建议跑
`kb extract --force` 重新生成以享受图片确定性命名带来的可追溯性。

---

## 分层 Wiki 知识库（v0.9.0）

v0.9.0 把 wiki 的扁平分类升级为按 **PRD + PES 真实层级**的 4 层
分类树（已发布）：

```
system           ← PRD 一级标题 (e.g. Audio System)
 └─ subsystem    ← PRD 二级标题 (e.g. Speaker)
     └─ part     ← PES 文档下的组件 (e.g. Tweeter)
         └─ function ← PES 二级标题（如频响、SPL）
```

### 一键生成 + 构建

```bash
# 1) 抽取所有 PRD/PES 文档到 kb/
kb extract ./MyProject

# 2) 生成 v2 taxonomy（带 --pes-glob 即触发 v2；不带就退化为 v0.7 行为）
kb wiki taxonomy generate ./MyProject \
    --prd-doc "BC PRD" \
    --pes-glob "M*"

# 3) 构建分层 wiki：自动识别 v2 schema 并走 build_wiki_v2
kb wiki build ./MyProject \
    --taxonomy ./MyProject/wiki/taxonomy.json \
    --provider mock --seed 0

# 4) 校验所有 footnote 都能解析回 kb anchor
kb wiki verify ./MyProject
```

### 输出布局

```
wiki/
  _index.md                        ← 系统总览
  audio/_index.md                  ← Audio 系统下的子系统列表
  audio/speaker/_index.md          ← Speaker 子系统下的零件列表
  audio/speaker/tweeter/_index.md  ← Tweeter 零件下的功能列表
  audio/speaker/tweeter/frequency-response/<topic>.md
  audio/microphone/<topic>.md
  electrical/power/<topic>.md
  taxonomy.json                    ← v2 配置（可读、可手改、可重跑）
  index.json                       ← topic 元数据 + provider/seed
```

### 路由优先级（最长前缀匹配）

```
PRD anchor map  >  PES anchor map  >  subsystem linked_specs
  >  section 标题关键词（下钻到最深匹配节点）
  >  文档标题关键词（整篇规格文档按标题路由）
  >  _uncategorized
```

deepest-matchable 优先：能匹配到 function 就不会停在 part；
跨 PES 同名零件（e.g. Audio/Speaker/Tweeter vs Notification/Speaker/Tweeter）
不会被合并。

### 工程需求提取（v0.14.0）

`kb wiki requirements PATH` 对 `kb/` 知识库中的每份文档执行**全文覆盖的工程需求
提取**：遍历 `main.md` 中所有含正文/表格的章节，按文档自身的顶层章节标题分类，
调用 LLM 抽取结构化的 TestItem 记录，并把证据溯源锚定到 `main.md` 中的真实段落。

### 用法

```bash
# 默认离线冒烟（mock provider，不产出 items）
kb wiki requirements ./MyProject

# 离线可复现（--responses-file 提供预录 prompt->response 映射）
kb wiki requirements ./MyProject \
    --provider cached \
    --responses-file ./responses.json

# 真实提取（调用 GitHub Models API；需要 GITHUB_TOKEN）
export GITHUB_TOKEN=<your-token>
kb wiki requirements ./MyProject \
    --provider github-models \
    --model gpt-4o
```

### 选项

| 选项 | 默认值 | 说明 |
|---|---|---|
| `--provider` | `mock` | `mock` / `cached` / `github-models` |
| `--responses-file` | — | `cached` provider 的预录 JSON，按 prompt hash 索引 |
| `--model` | — | 覆盖 provider 使用的模型名称（`github-models` 可用 `KB_GITHUB_MODEL` 环境变量代替） |
| `-o / --output-dir` | — | 重定向产物根目录（默认与 `kb/` 同一根） |
| `--max-chars` | 6000 | 每节传入 LLM 的最大字符数（超出按段落边界自动分块，不截断） |
| `--dry-run` | false | 仍调用 LLM 但不解析结果、不写盘（用于排查 provider/缓存连通性） |
| `--json` | false | 以 JSON 输出运行摘要 |

### Provider 说明

| Provider | 联网 | 说明 |
|---|---|---|
| `mock` | 否 | 离线冒烟，模拟整个流程但不调用 LLM，**不产出任何 items**；适合 CI / 快速测试 |
| `cached` | 否 | 按 prompt SHA-256 hash 从 `--responses-file` 读取预录回复，完全可复现；适合回归测试 |
| `github-models` | 是 | 通过 GitHub Models OpenAI 兼容 API 真实提取；需要 `GITHUB_TOKEN`；可选 `KB_GITHUB_MODEL` / `KB_GITHUB_BASE_URL` 覆盖模型与端点 |

### 输出产物

每份文档在 `kb/<doc>/` 下写入两个文件：

```
kb/
  thermal-spec/
    requirements.json    <- 规范机器产物：TestItem 数组，含 ID / 类别 / 描述等字段
    requirements.md      <- 人类可读版本：按类别分组，含指向 main.md 锚点的链接
```

### 证据溯源

每条 TestItem 的 `EvidenceRef` 字段由**代码**（而非 LLM）自动写入，格式为
`kb/<doc>/main.md#sec-NNNN`，与 `main.md` 中真实存在的段落锚点严格对应。
这保证所有提取结果都可以用 `kb verify` 体系校验和追溯，不存在 LLM 自行捏造的引用。

### 文档自身分类

章节的 Category 直接取自**文档自身的顶层章节标题**（如 Mechanical & Industrial
Design / Electrical / Software / Touchpad 等），由代码确定性地从 `main.md` 的标题
层级推导，而非 LLM 自由生成或关键词启发式。这保证同一文档的分类稳定可复现。

### 原子知识层（v0.15.0，`kb wiki atoms`）

`kb wiki atoms PATH` 把每份文档拆解为**最小可复用知识单元（atom）**：每个原子
描述"一个 entity 的一个 parameter 在一个 condition 下的一个 value"，含
entity / parameter / value / unit / type / condition 字段。产物写入：

```
kb/<doc>/graph/
  atoms.json   <- 权威源：按 section 排序的原子数组，id/source/anchor/evidence 强制
  atoms.md     <- 派生视图：Obsidian 双链 [[entity]] / [[parameter]]，byte-reproducible
```

`id`(entity+parameter+condition+source 的 sha256) 与 `evidence_ref` 由代码写入；
缺失数值或非法 type 标记 `待验证`，绝不臆造尺寸/力/功耗等关键参数。provider /
分块 / 可复现机制与 `wiki requirements` 一致。

### 模块层（v0.16.0，`kb wiki modules`）

`kb wiki modules PATH` 把原子**确定性**归入 8 个固定工程模块（零 LLM）：
Product Definition / Mechanical / Electrical / Subsystems / State Machine /
Validation / Manufacturing-DFX / Compliance。归类顺序：章节标题映射 ->
entity/parameter 关键词 -> 兜底 Subsystems 并标 `待验证`。产物：

```
kb/<doc>/graph/
  modules.json          <- {module: [atom_id]}，含 _pending，byte-reproducible
  modules/<module>.md   <- 8 页，[[entity]]/[[parameter]] 双链 + 锚点 + See also
```

### 图谱层（v0.17.0，`kb wiki graph`）

`kb wiki graph PATH --provider {mock,cached,github-models}` 把原子连成带证据的
有向边（LLM 生成，代码守门）。关系限定 5 类：depends_on / affects /
constrained_by / validated_by / implemented_by。source/target 必须是真实原子
id，幻觉 id、自环、未知关系丢弃；缺证据标 `待验证` 且置信度压到 <=0.3。产物：

```
kb/<doc>/graph/
  edges.json            <- 按 (source,relation,target) 排序去重，byte-reproducible
  graph.md              <- 按关系分组，[[parameter]] 双链
```

### Vault 层（v0.18.0，`kb vault`）

`kb vault build PATH` 装配 Obsidian vault（零 LLM）：`RawMD/` + `Graph/` +
`AGENTS.md` schema + `index.md`。`kb vault wiki PATH --provider ...` 让 LLM 写
叙述层（每文档概览 / 每实体页 / 多文档 `[冲突]` 对比页），新增标 `[新增]/[来源]/
[置信度]`，缺失标 `[待验证]`，不覆盖已有知识。`AGENTS.md` 指导 Copilot 维护四层
知识库。

---

> **数据外发提示**
>
> `--provider github-models` 会将章节正文文本发送到 **GitHub Models API**（Microsoft Azure 托管）。
> 对于含保密信息的工程文档，请在使用前评估数据合规要求，或改用 `mock` / `cached`
> provider 进行离线 / 可复现运行。

---

## 从 PRD 目录（TOC）构建层级（v0.10.0，`--from-toc`）

真实的 Microsoft PRD 用 PDF 抽取时，正文标题常会**退化**：章节号
（`## 2`、`## 3`、`## TX`）保留，但标题文字（`PRODUCT OVERVIEW`、
`MECHANICAL`）丢失。此时用正文标题建树会得到一堆以纯数字命名的垃圾子系统。

干净的编号层级其实只存在于 PRD 的 **"Contents"（目录）页**：

```
3            -> MECHANICAL            （subsystem，depth 1）
3.1          -> INDUSTRIAL DESIGN     （part，     depth 2）
3.2.1        -> RETRACTABLE HINGE     （function， depth 3）
```

`--from-toc` 会解析目录页得到干净的编号树，再用**章节号作为连接键**把正文
证据回填进去（正文节点的标题就是同一个章节号）。缺失的章节号回滚到最近的
祖先节点；非 PRD 的规格文档则通过 section 标题 / 文档标题关键词下钻路由。

```bash
# 用 PRD 目录页构建 4 层层级（替代 --pes-glob 的正文建树）
kb wiki taxonomy generate ./MyProject \
    --prd-doc "BC PRD Rev B" \
    --from-toc \
    --out ./MyProject/wiki/taxonomy.json

# 后续 build / verify 与上面完全一致
kb wiki build ./MyProject --taxonomy ./MyProject/wiki/taxonomy.json \
    --provider mock --seed 0
kb wiki verify ./MyProject
```

什么时候用哪个：正文标题干净 -> 用 `--pes-glob`；正文标题退化、但目录页
完整 -> 用 `--from-toc`。两者输出的 taxonomy.json schema 一致，后续流程不变。


### 设计原则与不变量

- v1 公共 API（`Category` / `TaxonomyConfig` / `load_taxonomy` / 
  `save_taxonomy` / `generate_taxonomy` / `route_evidence`）保持不变；
  v2 在 `taxonomy.py` 内并行新增 `CategoryNode` / `TaxonomyConfigV2` /
  `generate_taxonomy_v2` / `route_evidence_v2` / `load_taxonomy_v2` /
  `save_taxonomy_v2`。
- `load_taxonomy_v2` 自动迁移 v1 → v2（v1 类目统一标记 `layer="system"`,
  `source_pes_glob=None`）。
- 所有层都按 slug 字典序排序后再序列化，输出 byte-identical（H8/H13）。
- **H21 v2**: `layer ∈ {system, subsystem, part, function}`、树深度 ≤ 4、
  父子层严格递降（不允许跳跃）、同级 slug 唯一。

详细设计：`docs/superpowers/specs/2026-06-15-taxonomy-v2-design.md`

---

## Requirements 精确溯源

每条抽取出的需求都附带一段经确定性校验的逐字源文引用(EvidenceQuote)。该引用
必须逐字出现在源 main.md 中,校验不通过则自动丢弃,绝不编造。requirements.md 中
以引用块形式展示,便于直接看到"这条需求来自哪句话"。

## Obsidian 兼容 wiki

`kb wiki build` 生成的 wiki 兼容 Obsidian:

- 每页带 YAML frontmatter(title / domain / category_path / tags / evidence_sources),
  可配合 Dataview 与 graph view 使用。
- 页面间导航使用 `[[wikilinks]]`;证据回链仍指向确定性的 kb 锚点。
- `index.md` 为内容目录(按 domain 分组),`log.md` 为追加式构建日志。
- `entities/` 下为跨 domain 聚合页:同一份被多个 domain 引用的源文档会生成一页,
  用 `## Appears in` 反链回所有引用它的 topic,在 graph view 中即可看到跨域关联。

构建日志的日期可用 `--build-date YYYY-MM-DD` 注入(默认今天),以保证可复现:

```bash
kb wiki build ./MyProject --taxonomy ./MyProject/wiki/taxonomy.json \
    --provider cached --responses-file responses.json --build-date 2026-06-25
```

`kb wiki verify` 额外校验所有 wikilink 均指向存在的页面,防止 Obsidian 死链。

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
