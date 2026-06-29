# SP-D: Obsidian vault + Wiki + AGENTS.md (`kb vault`)

## Goal

Final stage of the pipeline (atoms->modules->graph->**wiki/vault**): assemble an
Obsidian-ready vault and an AGENTS.md schema that lets Copilot maintain the
knowledge base. LLM writes narrative Wiki pages; code enforces invariants.

## Two subcommands

### `kb vault build PATH` (deterministic, no LLM)
Assemble `vault/` from existing `kb/<doc>/`:
- `vault/RawMD/<doc>.md`     <- copy of kb/<doc>/main.md
- `vault/Graph/<doc>/`       <- copy of atoms.json/modules.json/edges.json + *.md
- `vault/AGENTS.md`          <- templated schema (below)
- `vault/index.md`           <- doc list with [[links]]
- `vault/Wiki/.keep`         <- filled by `vault wiki`
byte-reproducible; copies (not symlinks) for Windows portability.

### `kb vault wiki PATH --provider {mock,cached,github-models}` (LLM)
Per doc: **overview.md** (LLM summary of atoms, double-linked, evidence).
Per entity: **Wiki/entities/<entity>.md** aggregating that entity's atoms across
modules. Multi-doc entity -> **Wiki/compare/<entity>.md**. Conflicts -> `[冲突]`
block, never overwrite; missing -> `[待验证]`; new -> `[新增][来源][置信度]`.

## AGENTS.md schema (templated)
Documents: 4 layers Raw/RawMD/Wiki/Graph; pipeline Raw->RawMD->Atomic->Module->
Graph->Wiki; double-link `[[name]]`; markers 新增/来源/置信度/待验证/冲突; agent
rules: no delete (update/extend/mark-conflict only), never infer dims/force/power,
conflict->compare. English code, Chinese user docs.

## Tests
build: deterministic structure + AGENTS.md present, reproducible. wiki: mock/cached
provider, sorted pages, conflict block, 待验证. 594+ stay green; ruff clean.
