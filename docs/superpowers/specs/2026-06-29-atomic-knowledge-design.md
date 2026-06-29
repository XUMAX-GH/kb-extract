# SP-A 设计：`kb wiki atoms` - 原子知识层（Atomic Knowledge）

状态：已批准（设计）
日期：2026-06-29
关联：可推理工程知识系统（Engineering Knowledge System）四部曲之第一步。
后续 SP-B 模块归类、SP-C 知识图谱、SP-D Obsidian Vault + AGENTS.md 将依次构建于本层之上。
方法论延续 SP-3（`kb wiki requirements`，见 `2026-06-24-enrichment-kb-design.md`）。

## 1. 背景与目标

`kb extract` 产出确定性、可复现、带段落锚点（`<a id="sec-NNNN"></a>`）的 `main.md`，
作为可溯源的 evidence substrate。SP-3 已在其上抽取"工程需求"（粗粒度记录）。

本层（SP-A）把文档拆解为**最小可复用知识单元（atom）**，每条原子满足：可引用、
可对比、可计算、可推理。原子是上层模块划分、知识图谱、Wiki 页面的共同基石。

核心承诺：原子非文档分页/段落，而按**工程语义**拆解（一个 entity 的一个 parameter
在一个 condition 下的一个 value）。每条原子的 `source`/`id`/`evidence_ref` 由代码强制
写入，可被 `kb verify` 体系追溯，不存在 LLM 捏造的引用。

数据流定位：`Raw -> RawMD -> [SP-A Atomic] -> Module -> Graph -> Wiki`。

## 2. 范围

- 仅**单文档**：每份文档独立产出 `kb/<doc>/graph/atoms.json` + `atoms.md`。
- 跨文档去重/合并**不在本层**，留给 SP-C 图谱层。
- 模块归属、边关系、Obsidian 双链页面**不在本层**，留给 SP-B/C/D。

## 3. 命令

新增 `kb wiki atoms PATH`，参数与 `wiki requirements` 一致：
`--provider {mock|cached|github-models}`、`--responses-file`、`--model`、
`-o/--output-dir`、`--max-chars`(默认 6000)、`--dry-run`、`--json`。
复用 `sections.iter_content_sections` 遍历所有含正文/表格的章节，长节自动分块。

## 4. 原子 Schema（`kb/<doc>/graph/atoms.json`，按 id 排序数组）

| 字段 | 说明 |
|---|---|
| `id` | sha256(entity\|parameter\|condition\|source_doc\|section) 前 16 位，**代码强制**，确定性稳定 |
| `entity` | 对象，如 hinge / touchpad / keyboard |
| `parameter` | 参数，如 force / latency / thickness |
| `value` | 数值或范围；缺失/不确定时为 `null` |
| `unit` | 单位；无则空串 |
| `type` | requirement / behavior / constraint / spec |
| `condition` | 条件或状态，如 hinge state / power state；无则空串 |
| `source_doc` | **代码强制**，文档 id |
| `section` | **代码强制**，真实锚点 sec-NNNN |
| `evidence_ref` | **代码强制** `kb/<doc>/main.md#sec-NNNN` |
| `confidence` | LLM 自评 0-1，写盘保留两位 |
| `flags` | 排序数组；`value` 缺失或不确定 -> 含 `"待验证"` |

约束：不允许自行推断关键工程参数（尺寸/力/功耗）；缺失即 `value:null` + `["待验证"]`，
不臆造。`id`/`source_doc`/`section`/`evidence_ref` 一律覆盖 LLM 输出（`coerce_atom`）。

## 5. 派生视图 `atoms.md`

确定性生成、byte-reproducible（serialize_markdown + sorted）。按 `entity` 分组，
entity 与 parameter 用 Obsidian 双链 `[entity]` / `[parameter]`；待验证项加 `[待验证]`；
每行附 `([sec-NNNN](main.md#sec-NNNN))` 锚点链接。是只读视图，atoms.json 为权威源。

## 6. 复用与隔离

复用：`sections.py` 遍历/分块、`providers`（含 github_models 重试退避、cached 可复现）、
`coerce` 强制模式、`serialization`。本层只新增 `wiki/atoms/`（schema.py / prompts.py /
extractor.py / render.py），不碰确定性核心，adapters 仍禁止 import LLM/wiki。

## 7. 提示词

`build_system_prompt()` = `base_system_rules.md` + 新增 `atoms_rules.md`（说明 atom 粒度、
不推断关键参数、缺失标 待验证）；逐节传 anchor+title+body，LLM 返回 atom 数组 JSON。

## 8. 测试（socket 全禁，cached/mock provider）

- atom id 稳定性、强制覆盖 source/section/evidence；缺 value -> 待验证；
- atoms.md byte-reproducible；CLI mock 不产出、cached 可复现；prompts 无 domain。
验收：`uv run pytest` 全绿 + `uv run ruff check .` 干净。

## 9. 版本与文档

bump 0.15.0；README 增"原子知识层"段；CHANGELOG 简中条目。

## 10. 不做（YAGNI）

模块归类、图谱边、跨文档合并、AGENTS.md、Vault 双链全库、人工策展冲突合并。
