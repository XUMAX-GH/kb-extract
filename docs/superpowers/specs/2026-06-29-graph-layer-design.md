# SP-C: Knowledge Graph layer (`kb wiki graph`)

## Goal

Build the third step of the four-stage knowledge pipeline
(atoms -> modules -> **graph** -> wiki): connect atoms with typed,
evidence-backed edges so the corpus becomes a reasoning network, not a list.
LLM proposes edges; code enforces hardness invariants. Byte-reproducible.

## Inputs / outputs

- Input: `kb/<doc>/graph/atoms.json` + `kb/<doc>/graph/modules.json` (immutable).
- Output per doc:
  - `kb/<doc>/graph/edges.json` — sorted edge list, byte-reproducible.
  - `kb/<doc>/graph/graph.md` — chains grouped by relation, double-linked.

## Edge schema

`{source_id, target_id, relation, evidence_ref, confidence, flags}`

- relations (fixed 5): `depends_on / affects / constrained_by /
  validated_by / implemented_by`. Unknown relation -> dropped.
- `source_id` / `target_id` MUST both be real atom ids in this doc; else drop
  (no hallucinated nodes). No self-edges.
- missing/empty evidence -> `flags=["待验证"]`, confidence forced <= 0.3.
- dedup on (source_id, relation, target_id); sort by same key.

## Generation

- Per module batch: feed the module's atoms (id + entity/parameter/value) to
  the LLM, ask for edges among them + cross-module via shared entity.
- prompt = base_system_rules + graph_rules; same provider/cache as atoms.
- per-batch failures isolated; empty doc skipped.

## Pages

`graph.md`: per relation `## depends_on` then `- [[A.parameter]] -> [[B.parameter]]
([conf], evidence)`; counts in summary; `待验证` shown. Anchors to atoms.

## Determinism / tests

mock provider yields no edges (smoke); cached provider drives CLI reproducibility
test. Unit: coerce drops bad ids/relations, forces 待验证; render sorted/stable.
588+ existing tests stay green; ruff clean.

## CLI

`kb wiki graph PATH --provider {mock,cached,github-models} ... --json` mirrors
`wiki atoms`. Summary: `{docs, edges, pending}`.
