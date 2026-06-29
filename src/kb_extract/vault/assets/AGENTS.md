# AGENTS.md — Engineering Knowledge System schema

本 vault 是一个可推理的工程知识系统。GitHub Copilot 按本文件维护它：用户只
负责提问、筛选资料、做判断；AI 负责整理、归档、更新与关联。

## 四层结构

1. **Raw** — 原始资料（pdf/图片/网页），只读，不修改。
2. **RawMD** — extract+parser 后的 Markdown，按 section 拆分。
3. **Wiki** — 大模型整理的页面：概览、实体页、对比分析、概念解释。
4. **Graph** — 原子知识节点（atoms.json）+ 模块归类（modules.json）+ 知识链（edges.json）。

数据流：Raw -> RawMD -> Atomic -> Module -> Graph -> Wiki。

## 链接与标记约定

- 所有概念用双链 `[[概念名]]`。
- 不确定信息标 `[待验证]`，不臆断关键工程参数（尺寸/力/功耗）。
- 新增内容标 `[新增]` `[来源:...]` `[置信度:...]`。
- 冲突信息不覆盖，建对比并标 `[冲突]`。

## Agent 行为约束

1. 不删除已有知识，只允许更新 / 扩展 / 标冲突。
2. 信息不完整 -> 标 `[待验证]`，不自行推断关键参数。
3. 冲突 -> 建对比，标 `[冲突]`，不覆盖。
4. 所有结构必须符合本 schema。

## 语言策略

代码 / 测试名 / commit / docstring 用英文；用户可见文档用简体中文；
机器可解析输出（[violation] / verify: ok=...）保持英文。
