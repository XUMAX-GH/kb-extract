---
name: kb-extract
description: |
  将一个工程项目文件夹（包含 PDF / DOCX / XLSX / PPTX / PNG / JPG / ZIP）
  转换为可追溯到段落级别的 Markdown 知识库，输出到 <folder>/kb/ 下。
  抽取过程绝对不调用任何 LLM，每次运行必须满足全部 hardness 不变量。
triggers:
  - "extract this folder"
  - "extract folder"
  - "build kb from folder"
  - "extract documents"
  - "extract knowledge base"
  - "verify kb"
  - "verify knowledge base"
  - "提取这个文件夹"
  - "提取文件夹"
  - "构建知识库"
  - "抽取文档"
  - "校验知识库"
  - "验证知识库"
  - "build wiki"
  - "build wiki from kb"
  - "generate wiki"
  - "构建wiki"
  - "生成知识wiki"
  - "校验wiki"
  - "输出到"
  - "output to"
  - "save to"
  - "保存到"
  - "把结果放到"
---

# kb-extract 技能

本技能只是 `kb` 命令行工具的一层薄壳。它**不会**自己解析文档，**不会**修改
已抽取的产物，也**不会**对抽取内容做改写、补全或润色。所有抽取逻辑都在 `kb`
CLI 里。

## 契约（承重条款，不可绕过）

1. 技能本身不解析文档，只负责决定调用哪个子命令、传入哪个路径。
2. 技能不修改 `main.md`、`index.json`、`meta.json`。如需重新抽取，
   用户必须显式要求 `kb extract --force`。
3. 在 `kb extract` 之前，技能先跑 `kb adapters` 确认 CLI 可用；
   若失败，提示用户去仓库根目录运行 `install.ps1` / `install.sh`。
4. 技能把 CLI 的 `--json` 输出摘要给用户，**绝不**对已抽取内容做
   增添、重排或改写。
5. 若 `kb verify` 返回非零，技能必须**原文**地把每条违规项呈现给
   用户，绝不为产物提议"修复"。

## 使用方式

| 用户意图 | 技能调用 |
|---|---|
| "提取当前文件夹"（cwd 即项目根） | `scripts/extract.{ps1,sh} .` |
| "提取文件夹 X" | `scripts/extract.{ps1,sh} X` |
| "重新抽取" | `scripts/extract.{ps1,sh} X --force` |
| "试运行（dry-run）抽取" | `scripts/extract.{ps1,sh} X --dry-run` |
| "校验知识库" | `scripts/verify.{ps1,sh} X` |
| "构建 wiki / generate wiki" | `kb wiki build X --provider mock --seed 0` |
| "校验 wiki" | `kb wiki verify X` |
| "记住 / remember / 设置偏好" | `kb remember <key> <value>` |
| "列出我的偏好" | `kb remember --list` |
| "忘记 / forget" | `kb forget <key>` |
| "回顾历史 / recall / 我之前跑过什么" | `kb recall [--project X] [--command Y]` |
| "把抽取产物放到 D / output to D" | `kb extract -o D X`（kb/ 和 wiki/ 写到 D 下） |

### 关于 `--output-dir / -o`（v0.5.0+）

如果用户明确说"把 markdown / 结果 / 知识库放到某个目录"（且这个目录与
源文件目录**不同**），技能必须在 `kb extract`、`kb verify`、`kb wiki build`、
`kb wiki verify`、`kb manifest` 上**都**带 `-o <output-dir>`，否则后续命令会
找不到 manifest / kb / wiki。源文件**永远保持只读**。

所有脚本都使用 `kb ... --json`，并把解析后的状态展示给用户。

### 关于 wiki 子命令（v0.3+）

`kb wiki build` **是包内唯一允许调 LLM 的层**。技能在调用它时必须：

1. 默认使用 `--provider mock --seed 0` —— 这样产物是确定性的，无网络
2. 若用户明确要求真实 provider（如 `--provider openai`），先确认环境变量
   `KB_EXTRACT_LLM_PROVIDER` 与对应密钥已就绪
3. 跑完之后立刻调 `kb wiki verify`，若有违规则原文呈现给用户（同 extract 流程）

### 关于 memory 子命令（v0.4+）

- `kb` 自动在 `~/.kb-extract/memory.db`（或 `$KB_EXTRACT_HOME/memory.db`）记录
  每次 extract / verify / wiki build / wiki verify 的执行历史。**技能无需做任何额外动作**。
- 当用户说"记住我喜欢 openai provider"等，调 `kb remember default_provider openai`。
- 当用户问"我上次跑的是啥"，调 `kb recall --limit 5` 并展示结果。
- memory 写入失败时静默；技能不应把 memory 错误当成主流程错误。
