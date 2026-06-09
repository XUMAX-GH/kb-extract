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

所有脚本都使用 `kb ... --json`，并把解析后的状态展示给用户。
