---
name: kb-extract
description: |
  Convert a folder of engineering documents (PDF/DOCX/XLSX/PPTX/PNG/JPG/ZIP)
  into a deterministic, citable Markdown knowledge base under <folder>/kb/.
  Never invokes an LLM during extraction. Always honours hardness invariants.
triggers:
  - "extract this folder"
  - "extract folder"
  - "build kb from folder"
  - "extract documents"
  - "extract knowledge base"
  - "verify kb"
  - "verify knowledge base"
---

# kb-extract skill

This skill is a thin shell around the `kb` CLI. It never parses documents
itself, never modifies extracted artifacts, and never enriches or paraphrases
extracted content. All extraction logic lives in the `kb` CLI.

## Contract (load-bearing — do not bend)

1. The skill never parses documents itself; it only decides what subcommand
   and path to invoke.
2. The skill never modifies `main.md`, `index.json`, or `meta.json`. To
   re-extract, the user must explicitly request `kb extract --force`.
3. Before any extract command, the skill runs `kb adapters` to confirm CLI
   availability; if the command fails, instructs the user to run
   `install.ps1` / `install.sh` from the kb-extract repo root.
4. The skill summarises the CLI's `--json` output to the user. It never
   adds, reorders, or paraphrases extracted content.
5. If `kb verify` exits non-zero, the skill surfaces every violation
   verbatim. It does not suggest "fixes" to extracted content.

## Usage

| User intent | Skill action |
|---|---|
| "Extract this folder" (cwd is a project) | `scripts/extract.{ps1,sh} .` |
| "Extract folder X" | `scripts/extract.{ps1,sh} X` |
| "Re-extract" | `scripts/extract.{ps1,sh} X --force` |
| "Dry run extract" | `scripts/extract.{ps1,sh} X --dry-run` |
| "Verify kb" | `scripts/verify.{ps1,sh} X` |

All scripts use `kb ... --json` and surface the parsed status to the user.
