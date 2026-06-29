# SP-B 设计：`kb wiki modules` - 模块层（8 大工程模块归类）

状态：已批准（设计）
日期：2026-06-29
关联：可推理工程知识系统四部曲之第二步（SP-A 原子层见 `2026-06-29-atomic-knowledge-design.md`）。
依赖 SP-A 的 `kb/<doc>/graph/atoms.json`，产物供 SP-C 图谱 / SP-D Vault 使用。

## 1. 背景与目标

SP-A 已把文档拆成原子（atom）。本层把每个原子**确定性**归入 8 个标准工程模块，
并产出按模块聚合的可读页面。**零 LLM**：完全由提交在仓库的映射表 + 关键词决定，
byte-reproducible，无 API 成本、无限流。

8 模块（固定）：Product Definition / Mechanical / Electrical / Subsystems /
State Machine / Validation / Manufacturing-DFX / Compliance。

## 2. 范围

- 单文档：读 `kb/<doc>/graph/atoms.json`，写 `modules.json` + `modules/<m>.md`。
- 每个原子归且仅归一个模块；atoms.json **不改动**（纯派生）。
- 跨模块边、跨文档合并不在本层（SP-C）。

## 3. 命令

`kb wiki modules PATH`：无 `--provider`（纯计算）。选项 `-o/--output-dir`、
`--json`。遍历 `kb_dir` 下每个 doc，对有 atoms.json 的文档归类并写盘。

## 4. 归类规则（`assets/module_rules.json`）

原子无 category 字段，故 classifier 复用 `requirements.sections.iter_content_sections`
建 section->category 映射，恢复每个原子所在章节的顶层标题。判定顺序：
1. category 命中 `category_to_module`（子串、忽略大小写）-> 模块；
2. 否则 entity+parameter 命中 `keyword_to_module` 任一关键词 -> 模块；
3. 都不中 -> `Subsystems` 且加 `待验证`。
表是有序 dict，命中取首个，确定性。

## 5. 产物

- `kb/<doc>/graph/modules.json`：`{module: [atom_id 排序]}`，8 键全在（空模块为 [])，
  外加 `{"_pending": [未确定的 atom_id]}`。byte-reproducible。
- `kb/<doc>/graph/modules/<module>.md`（8 页）：按 entity 分组，`[[entity]]`/`[[parameter]]`
  双链、`[待验证]`、`([sec-NNNN](../main.md#sec-NNNN))`。页尾"See also"列出同名 entity
  所在的其他模块（确定性，按名）。

## 6. 复用与隔离

复用 atoms.schema、sections、serialization。新增 `wiki/modules/`（rules.py / classifier.py
/ render.py）+ assets/module_rules.json。adapters 仍禁 LLM/wiki。

## 7. 测试

规则覆盖、每原子恰一模块、未中->Subsystems+待验证、modules.json 可复现、页面双链、
8 键齐全。`uv run pytest` + ruff 全绿。bump 0.16.0。

## 8. 不做

LLM 分类、跨模块边、跨文档合并、AGENTS.md、人工冲突合并。
