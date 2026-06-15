# 设计文档：层级 Taxonomy v2（v0.9.0）

> 日期：2026-06-15
> 作者：@XUMAX-GH + Copilot (Claude Opus 4.7)
> 状态：待实现
> 前置：v0.7.0 PRD-driven taxonomy wiki（已 ship）

## 1. 背景与动机

v0.7.0 的 taxonomy 把 PRD 的 H1 章节作为 **扁平 1 层** category，输出
`wiki/<category>/<topic>.md` 二层目录。这相比 v0.6.0 的"全扁平"已经
是一大进步，但仍然有结构性缺陷：

- **真实工程文档是 3-4 层的**。PRD 是顶层产品需求（system →
  subsystem），PES 是底层工程实现（part → function）。把 PES 的所有
  内容统一压进 PRD H1 这一层，本质上是把两个独立信息源粗暴拍扁。
- **`linked_specs` 字段被低估**。v0.7.0 用它做 routing 匹配，但没用它
  做 **结构归属**——PES 的天然父节点其实就藏在 PRD 的
  `linked_specs` 里。
- **用户无法按 part 浏览**。当一份 PES 描述 10 个不同 part 的 50 个
  function 时，v0.7.0 仍然把它整体路由到一个 subsystem
  category，topic 内部仍然由 Jaccard 聚类决定，**part 与 function 之间
  的层级关系完全丢失**。
- **`_index.md` 缺乏导航深度**。当前 `_index.md` 只列同级 topic，没
  有子目录概念，用户从 root 跳到具体 topic 之间没有中间停留点。

## 2. 目标

- 按 PRD + PES 的真实层级生成 **多层 wiki 目录树**：
  `system → subsystem → part → function`，深度 ≤ 4
- 把 PES 通过 PRD 的 `linked_specs` **挂载** 到对应 subsystem
  下，自然形成 part / function 两层
- evidence routing 从"单一 slug"升级为 **category path**
  （最长前缀匹配），落到能匹配到的 **最深祖先**
- 每层 `_index.md` 自动列出"本层级 topics + 子目录链接"，形成可点击
  的浏览树
- 完全向后兼容 v0.7.0：旧的扁平 taxonomy.json 自动 migrate 到 schema
  v2，行为等价
- 符合所有 hardness 约束，特别是 H4 / H8 / H21

## 3. 数据模型

### 3.1 schema v2 (taxonomy.json)

```json
{
  "version": 2,
  "source_prd": "doc-prd-123",
  "source_pes_glob": "PES-*",
  "categories": [
    {
      "slug": "audio-system",
      "title": "Audio System",
      "layer": "system",
      "prd_headings": ["Audio System"],
      "pes_headings": [],
      "linked_specs": [],
      "keywords": ["audio", "sound"],
      "children": [
        {
          "slug": "speaker",
          "title": "Speaker",
          "layer": "subsystem",
          "prd_headings": ["Audio System / Speaker"],
          "pes_headings": [],
          "linked_specs": ["PES-Speaker-*"],
          "keywords": ["speaker", "driver"],
          "children": [
            {
              "slug": "tweeter",
              "title": "Tweeter",
              "layer": "part",
              "prd_headings": [],
              "pes_headings": ["Tweeter"],
              "linked_specs": [],
              "keywords": ["tweeter", "high-frequency"],
              "children": [
                {
                  "slug": "eq-tuning",
                  "title": "EQ Tuning",
                  "layer": "function",
                  "prd_headings": [],
                  "pes_headings": ["Tweeter / EQ Tuning"],
                  "linked_specs": [],
                  "keywords": ["eq", "tuning", "frequency"],
                  "children": []
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.2 CategoryNode Python 类型

```python
@dataclass(frozen=True, slots=True)
class CategoryNode:
    slug: str
    title: str
    layer: Literal["system", "subsystem", "part", "function"]
    prd_headings: tuple[str, ...]      # "/" 分隔的 heading-path
    pes_headings: tuple[str, ...]      # 新增：PES 侧 heading-path
    linked_specs: tuple[str, ...]      # fnmatch glob
    keywords: tuple[str, ...]
    children: tuple[CategoryNode, ...]
```

注意：
- `prd_headings` / `pes_headings` 用 `"/"` 分隔的 heading-path
  字符串（如 `"Audio System / Speaker / Tweeter"`），便于最长前缀匹配
- `children` 排序键固定为 `slug`，保证 byte-identical
- `layer` 必须从父节点的 layer 严格下降（system → subsystem → part →
  function），不能跳级也不能逆序

### 3.3 schema migrator (v1 → v2)

v0.7.0 的 schema v1（无 `layer` / `children` / `pes_headings` 字段）
按以下规则自动升级：

```python
def migrate_v1_to_v2(v1: dict) -> dict:
    return {
        "version": 2,
        "source_prd": v1["source_prd"],
        "source_pes_glob": None,
        "categories": [
            {
                **cat,
                "layer": "system",
                "pes_headings": [],
                "children": [],
            }
            for cat in v1["categories"]
        ],
    }
```

Migrator 在 `load_taxonomy()` 内透明运行；旧的 taxonomy.json 不需要
重新生成即可在 v0.9.0 跑通（行为等价于扁平 1 层）。

## 4. Generator 升级（`generate_taxonomy_v2`）

### 4.1 流程

```
Step 1  扫 PRD index.json
        → 每个 H1 → CategoryNode(layer="system")
        → 每个 H2 → 作为该 system 的 child(layer="subsystem")
        → 抽取每个 subsystem 节点的 linked_specs（沿用 v0.7.0 逻辑）

Step 2  按 --pes-glob 枚举所有 PES 文档
        对每份 PES:
          a) 用其文档名匹配某个 subsystem 的 linked_specs
             - 命中 → 挂到该 subsystem 下
             - 未命中 → 挂到一个新建的虚拟 subsystem
               "_unassigned-specs"
          b) 解析 PES 的 index.json:
             - H1 → child(layer="part")
             - H2 → grandchild(layer="function")
             - H3+ → flatten 到所属 function 的 keywords/pes_headings

Step 3  跨 PES 合并：同一个 part slug 出现在多份 PES 中时
        - 合并 keywords / pes_headings / linked_specs
        - children (function 层) 也对应合并（按 slug 去重）

Step 4  Stable sort
        所有层级的 children 按 slug 排序

Step 5  写盘 schema v2 JSON
```

### 4.2 CLI

```bash
# 仅 PRD（行为 ≈ v0.7.0，但输出 v2 schema）
kb wiki taxonomy generate <kb-root> \
  --prd-doc <id> \
  -o taxonomy.json

# PRD + PES 全量挂载
kb wiki taxonomy generate <kb-root> \
  --prd-doc <id> \
  --pes-glob "PES-*" \
  -o taxonomy.json
```

`--pes-glob` 是 v0.9.0 新增参数；不传时输出深度只有 system+subsystem
两层（part/function 为空）。

## 5. Routing 升级（`route_evidence_v2`）

### 5.1 返回类型变化

```python
# v0.7.0
def route_evidence(ev, cfg, prd_section_map) -> str: ...  # category slug

# v0.9.0
def route_evidence_v2(ev, cfg, prd_section_map, pes_section_map) \
    -> tuple[str, ...]: ...  # category path, e.g. ("audio-system", "speaker", "tweeter")
```

### 5.2 4 层优先级 + 最长前缀匹配

```
Priority 1  heading-path
            ev.section_title chain 在 cfg 树里做 DFS 最长前缀匹配
            匹配 PRD heading 时走 prd_headings 字段
            匹配 PES heading 时走 pes_headings 字段
            返回匹配到的最深节点的 path

Priority 2  linked-spec glob
            ev 所属文档名 fnmatch 任一节点的 linked_specs
            返回该节点的 path
            （注意：fnmatch 同时命中多个节点时取 path 最深的）

Priority 3  keyword
            ev.section_title tokenize → 在每个节点的 keywords 内查
            分数 = 命中 keyword 数 / 节点深度（深的得分 weight 高）
            返回 score 最高的节点 path

Priority 4  fallback
            止步在 Priority 1-3 能匹配到的最深祖先
            如果连 root 都匹配不到，落到 ("_uncategorized",)
```

关键设计：**fallback 不再直接进 `_uncategorized`，而是"止步在最深可
匹配祖先"**。这样：
- 一条 evidence 可能落在 `("audio-system",)`（只匹配到 system 层）
- 也可能落在 `("audio-system", "speaker", "tweeter", "eq-tuning")`
- 只有完全无任何祖先匹配的才进 `("_uncategorized",)`

### 5.3 PES section map

类似 `build_prd_section_map()` 的 PES 版本：枚举所有 PES 文档的
`index.json`，构建 `(pes_doc_id, anchor) → category_path` 映射，供
Priority 1 在 PES heading 上做快速查找。

## 6. Writer / Orchestrator 升级

### 6.1 文件路径与 footnote URL

文件路径：
```python
topic_path = wiki_root / "/".join(category_path) / f"{topic_slug}.md"
```

footnote 相对路径泛化：
```python
# v0.7.0：固定 "../../kb/..."
# v0.9.0：按 category_path 深度算
rel_prefix = "../" * (len(category_path) + 1)
footnote_url = f"{rel_prefix}kb/{doc_id}/main.md#{anchor}"
```

### 6.2 每层 `_index.md`

```
wiki/audio-system/_index.md     # H1 = "Audio System"
                                # 列出本层 topics
                                # 子目录章节：
                                #   ## Subsystems
                                #   - [Speaker](speaker/_index.md)
                                #   - [Amplifier](amplifier/_index.md)

wiki/audio-system/speaker/_index.md   # H1 = "Speaker"
                                       # 本层 topics + parts 子目录

wiki/audio-system/speaker/tweeter/_index.md  # H1 = "Tweeter"
                                              # 本层 topics + functions 子目录
```

根 `wiki/_index.md` 列出所有 system，作为整个 wiki 的入口。

### 6.3 Orchestrator 递归

```python
def _emit_category_node(node: CategoryNode, parent_path: tuple[str, ...]):
    full_path = (*parent_path, node.slug)
    topics_here = evidence_router.topics_for(full_path)
    _write_topic_files(topics_here, full_path)
    _write_index_md(node, full_path, topics_here)
    for child in node.children:
        _emit_category_node(child, full_path)
```

## 7. Hardness 影响

- **H4 (anchor 完整性)**：footnote URL 跨多层 `../`，writer 必须按
  实际 `len(category_path)` 计算，专门加单测覆盖深度 1/2/3/4 四种
  情形。
- **H8 (determinism)**：CategoryNode.children 排序固定，跨平台
  byte-identical。
- **H13 (cross-platform)**：所有路径用 `"/".join()` 而非
  `os.path.join`，避免 Windows 反斜杠泄漏到 markdown URL。
- **H21 (taxonomy schema)**：新增三条 schema 检查：
  1. `layer` ∈ `{system, subsystem, part, function}`
  2. children 深度 ≤ 4
  3. children 内 slug 在同一 namespace 内唯一（不同分支可重名）

无新的 H 编号。

## 8. 与 v0.7.0 的兼容性

- `Category` 类保留为 `CategoryNode` 的别名（带 deprecation
  warning），存量代码可继续 import。
- `route_evidence()` 旧签名保留：内部调用 `route_evidence_v2()` 然
  后取 path[0]，行为等价于"扁平 1 层"。
- `load_taxonomy()` 自动透明 migrate schema v1 → v2。
- `kb wiki build` 不传 `--taxonomy` 仍走 v0.6.0 Jaccard
  聚类，未受影响。
- 旧的 taxonomy.json 不需要重新生成。

## 9. 测试策略

### 9.1 单元
- `CategoryNode.from_dict / to_dict` 往返
- schema v1 → v2 migrator
- `route_evidence_v2` 4 层优先级 + 最长前缀（合成树）
- writer 相对路径深度 1/2/3/4
- `_index.md` 子目录链接生成

### 9.2 e2e
- 仅 PRD（无 PES）→ system+subsystem 二层输出
- PRD + 单份 PES → 全四层输出
- PRD + 多份 PES 含同名 part → 合并验证
- 未命中任何 linked_specs 的 PES → `_unassigned-specs` 隔离

### 9.3 hardness
- H4: 深嵌 footnote 全部可解析
- H8: 双跑 byte-identical
- H13: Linux + Windows 输出 hash 一致
- H21: schema v2 完整性

## 10. 实现顺序（PR 拆分）

**PR-A：数据模型 + schema migrate**
1. `CategoryNode` 类型 + JSON I/O
2. schema v1 → v2 migrator
3. `Category` 别名保留 + deprecation
4. 单测覆盖

**PR-B：Generator + Routing**
5. `generate_taxonomy_v2`（PRD 两层 + PES 挂载 + 合并）
6. `build_pes_section_map`
7. `route_evidence_v2`（最长前缀匹配）
8. 单测覆盖

**PR-C：Writer + Orchestrator + CLI + e2e**
9. writer footnote 路径泛化
10. orchestrator 递归 + 多层 `_index.md`
11. CLI `--pes-glob` 参数
12. e2e 测试 + 文档 + CHANGELOG

预计代码量 ~700 行 + ~50 个测试。

## 11. 风险与未决问题

| 风险 | 缓解 |
| --- | --- |
| PES 没有 `index.json`（旧 v0.4 之前的提取结果） | 在 generator 内 fallback：从 PES `main.md` 用 H1/H2 正则识别 |
| 同名 part 跨 subsystem（如 "Tweeter" 同时在 Audio 和 Notification） | 不合并：按 (subsystem_slug, part_slug) 作为唯一键 |
| linked_specs glob 同时命中多个 subsystem | 选 path 最深的；并列时按 slug 字典序 |
| evidence 数量爆炸（4 层每层都有 topic） | 引入 `--min-evidence-per-leaf` CLI 参数，少于阈值的 function 合并到 part |

## 12. 非目标（v0.9.0 不做）

- 自动从 PES content 推断 part 类别（pure heading-driven）
- 跨 PRD 合并（假设一个 kb root 只有一份 PRD）
- 任何 LLM 推断（仍然是 deterministic generator）
- UI / 网页浏览（仍然只产 markdown 文件）
