# 设计文档：PRD 驱动的 Taxonomy Wiki（v0.7.0）

> 日期：2026-06-12
> 作者：@XUMAX-GH + Copilot (Claude Opus 4.6)
> 状态：待实现

## 1. 背景与动机

v0.6.0 的 wiki 层使用 Jaccard 聚类自动发现 topic，输出扁平的 `wiki/*.md`。
这种方式的问题：

- **没有领域结构**：`compliance.md`、`slide.md`、`equipment.md` 都在同一级，
  用户无法按子系统（Mechanical / Electrical / Keyboard …）浏览知识。
- **PRD 已经定义了完美的分类体系**：BC PRD 的章节结构就是产品
  子系统的权威划分，且每章都有 Reference Documents 表清晰映射到详细 spec。
- **PES（Product Experience Specification）是重要横切文档**：它的
  56 张幻灯覆盖了工程体验视角，需要按主题路由到对应的子系统文件夹。

## 2. 目标

- 按 PRD 大章节把 wiki 输出组织为 **子目录**（~11 个 category）
- 新增 `kb wiki taxonomy` 命令从 PRD 自动生成 `taxonomy.json` 配置文件
- `kb wiki build --taxonomy` 读取 taxonomy.json，用 **路由引擎** 替代
  Jaccard 聚类，把 evidence 分到对应 category，category 内再做子聚类
- 保持完全向后兼容（不带 `--taxonomy` 时行为不变）
- 符合 hardness 约束（H14/H15/H17）

## 3. Taxonomy 数据模型

### 3.1 taxonomy.json 结构

```json
{
  "version": 1,
  "source_prd": "<PRD doc_id>",
  "categories": [
    {
      "slug": "mechanical",
      "title": "Mechanical",
      "prd_headings": ["Mechanical", "Retractable Hinge", "Flat Bounce", "Typing Rigidity",
                       "Stiffness (X and Y)", "Corner Bend Touchpad Protrusion",
                       "Touchpad Gap/Step", "Keyset Gap/Step", "System Level Flatness",
                       "Touchpad Flatness", "Hall Magnet Strength", "Closure Magnet Force",
                       "Fabric XY Step", "Repairs", "Repairability"],
      "linked_specs": ["id5.M9000010*"],
      "keywords": ["hinge", "bounce", "stiffness", "gap", "step", "flatness",
                    "magnet", "closure", "retractable", "spine", "posture",
                    "attach", "detach", "docking"]
    }
  ]
}
```

### 3.2 Category 清单（BC 项目）

| slug | title | PRD 章节 | 关联 spec | PES 映射 |
|---|---|---|---|---|
| `product-overview` | Product Overview | §1-2 (Conventions, Terminology, Introduction, Product Overview, SKU Matrix) | M9000019 (PES §Product Overview) | Slide 1-12 |
| `industrial-design` | Industrial Design | §3 Industrial Design (Fit, Finish, UX) | M9000016 (PSCS), M9000017-25 (材料 spec) | §Product Detail and Quality |
| `mechanical` | Mechanical | §4 Mechanical (Hinge, Bounce, Stiffness, Gap/Step, Flatness, Magnet) + §4a Repairs | M9000010 (Keyboard Interface) | §Blade Spine + §Posture |
| `electrical` | Electrical | §5 Electrical + §5a Interface with Host + §5b Power Draw + §5c Authentication + §5d Hinge Angle States + §5e Subsystem Power States | M9000011 (Blade Electrical) | — |
| `keyboard` | Keyboard & Keyset | §6.1 Keyset (Layout, Accessibility, Requirements) + §6.4 User Input Latencies | M9000015 (Keyset Spec), M9000004 §Keyset | §Typing & Keyset |
| `backlight` | Backlight | §6.2 Backlight (Illumination, Uniformity, Color, Caps/Fn LED, Controls, Behavior, Fading) | M9000006, M9000007, M9000008 | — |
| `touchpad` | Touchpad | §6.3 Touchpad (Requirements, Specs, Capacitance, Audio, Impedance, Power States, Latency) | M9000004 §Touchpad | — |
| `software` | Software & Firmware | §7 (HID, FW Update, NXP MCU, Adaptive Touchpad, External Flash) | — | — |
| `manufacturing` | Manufacturing & Packaging | §8 MFG (DFA/DFM, Design for Automation/Fungibility/Reuse) + §9.1 Packaging | M9000013 (BB MPRD), M9000014 (SMT MPRD), M9000002 (dotgauge) | — |
| `shipping` | Shipping & Environment | §9.2 Shipping (Specs, Operational/Environmental, Storage) | — | — |
| `compliance` | Safety, EMC & Compliance | §10 (Quality, Reliability, Safety, EMC/SI/RF, Environmental, Sustainability) | H900001, H900002, M9000001, M9000005, M9000009 | — |

### 3.3 Python Dataclass

```python
@dataclass(frozen=True)
class Category:
    slug: str
    title: str
    prd_headings: tuple[str, ...]
    linked_specs: tuple[str, ...]     # glob 模式
    keywords: tuple[str, ...]

@dataclass(frozen=True)
class TaxonomyConfig:
    version: int                       # 必须为 1
    source_prd: str                    # PRD 的 doc_id
    categories: tuple[Category, ...]
```

## 4. 路由引擎

### 4.1 路由函数签名

```python
def route_evidence(
    ev: EvidenceRef,
    config: TaxonomyConfig,
    prd_section_map: dict[str, str],  # anchor -> category_slug
) -> str:
```

### 4.2 路由优先级（4 层）

1. **PRD evidence → 按锚点位置路由**
   - PRD 自身的 evidence，根据其 anchor 在 PRD `index.json` 中的
     位置，判断它属于哪个一级章节 → 对应 category slug。
   - 实现：预处理 PRD 的 `index.json`，建立 `anchor → category_slug`
     映射表（`prd_section_map`）。

2. **非 PRD evidence → `linked_specs` glob 匹配**
   - 对每个 category 的 `linked_specs`，用 `fnmatch` 检查
     `ev.doc_id` 是否匹配。
   - 如果 evidence 的 doc_id 匹配多个 category（不太可能但理论上可以），
     取第一个匹配的。

3. **Fallback → `keywords` token 匹配**
   - 对 `ev.section_title` 做 tokenize，计算与每个 category 的
     `keywords` 的交集大小，取最大者（至少 1 个 keyword 命中）。

4. **未命中 → `_uncategorized`**

### 4.3 PES 特殊处理

PES（M9000019）不在 PRD 的 Reference Documents 中按章节唯一绑定——
它是横切文档。处理方式：

- PES 的一级标题（`Product Overview` / `Blade Spine Experiences` /
  `Posture Experiences` / `Typing and Keyset Experiences` /
  `Product Detail and Quality`）作为 **PES → category 映射** 写入
  taxonomy.json 的 `linked_specs` 或专用 `pes_section_map` 字段。
- 默认映射：
  - `Product Overview` → `product-overview`
  - `Blade Spine Experiences` → `mechanical`
  - `Posture Experiences` → `mechanical`
  - `Typing and Keyset Experiences` → `keyboard`
  - `Product Detail and Quality` → `industrial-design`
- PES 的 evidence 先按其父级一级标题路由到 category，再在 category
  内参与 Jaccard 聚类。

## 5. CLI 变更

### 5.1 新增 `kb wiki taxonomy`

```
用法: kb wiki taxonomy <src> -o <out> [--prd-doc <doc_id>]

参数:
  <src>           源文件目录
  -o / --output   输出目录
  --prd-doc       显式指定 PRD 的 doc_id（默认自动检测）

输出:
  <out>/wiki/taxonomy.json
```

自动生成逻辑：
1. 扫描 `<out>/kb/` 找 PRD 文档（文件名含 `PRD` 或 `Product Requirements`）
2. 解析 PRD 的 `index.json` 的一级标题作为 category
3. 正则提取 PRD `main.md` 中每个章节的 Reference Documents 表
4. 从 PRD 二级标题 tokenize 生成 keywords
5. PES 自动检测（文件名含 `PES` 或 `Product Experience`）+ 默认映射
6. 写入 `taxonomy.json`

### 5.2 修改 `kb wiki build`

新增选项：
- `--taxonomy`：启用 taxonomy 模式（读取 `<out>/wiki/taxonomy.json`）

当启用时：
- 用 `taxonomy.py::route_evidence()` 替代 `topics.py::discover_topics()` 的聚类
- 每个 category 内部仍然用 Jaccard 聚类生成 sub-topic
- 输出写到 `wiki/<category_slug>/<topic_slug>.md`
- 自动生成 `wiki/<category_slug>/_index.md`

### 5.3 修改 `kb wiki dump-prompts`

新增选项：
- `--taxonomy`：同上，在 prompts 输出中增加 `category` 字段

### 5.4 修改 `kb wiki verify`

- 自动递归 `wiki/**/*.md`
- 相对链接深一级：`../../kb/<doc>/main.md#anchor`

## 6. 输出结构

```
<out>/
  kb/
    <doc_id>/
      main.md
      index.json
      assets/
  wiki/
    taxonomy.json                    # 分类配置
    product-overview/
      _index.md                      # 自动生成的 category 概览
      product-overview.md            # PRD §1-2 的综合
      pes-overview.md                # PES Product Overview slides
      sku-matrix.md
    industrial-design/
      _index.md
      fit-finish-ux.md
      color-gloss.md                 # M9000017-25 颜色数据
      material-spec.md
      pes-product-detail.md
    mechanical/
      _index.md
      retractable-hinge.md
      flat-bounce.md
      gap-step.md                    # Touchpad Gap/Step + Keyset Gap/Step
      flatness.md
      magnet.md
      blade-spine-experiences.md     # PES §Blade Spine
      posture-experiences.md         # PES §Posture
      pogo-connector.md              # M9000010 接口机械部分
    electrical/
      _index.md
      interface-host.md
      power-draw.md
      authentication.md
      hinge-angle-states.md
      subsystem-power-states.md
      blade-electrical.md            # M9000011
    keyboard/
      _index.md
      layout-requirements.md
      force-to-fire.md
      accessibility.md
      input-latency.md
      keyset-spec.md                 # M9000015
      pes-typing-keyset.md
    backlight/
      _index.md
      brightness-uniformity.md
      caps-fn-led.md
      light-leakage.md
      backlight-behavior.md
    touchpad/
      _index.md
      requirements-specs.md
      force-to-fire.md
      baseline-capacitance.md
      gesture-recognition.md
    software/
      _index.md
      firmware-update.md
      hid-functionality.md
      nxp-mcu.md
    manufacturing/
      _index.md
      dfa-dfm.md
      bb-mprd.md                     # M9000013
      smt-mprd.md                    # M9000014
      packaging.md
    shipping/
      _index.md
      shipping-specs.md
      environmental-envelope.md
    compliance/
      _index.md
      safety.md                      # H900001
      emc.md                         # M9000001
      hsc.md                         # M9000005
      energy-efficiency.md           # M9000009
      ccl-parts.md                   # H900002
      environmental.md
    _uncategorized/                  # 如果有未路由的
      ...
```

## 7. _index.md 格式

每个 category 自动生成的 `_index.md`：

```markdown
# Mechanical

> BC 项目 Mechanical 子系统知识库

## 概述

本目录收录了与 Mechanical 子系统相关的所有知识条目，
涵盖 PRD §4 Mechanical 章节及其关联 spec 文档的内容。

## 关联文档

| 文档 | 编号 | 用途 |
|---|---|---|
| Keyboard Accessory Interface Spec | M9000010 Rev B | 接口机械设计与测试 |
| BC PES | M9000019 Rev A | §Blade Spine + §Posture 体验 |

## 文章列表

- [retractable-hinge](retractable-hinge.md) — 可伸缩铰链
- [flat-bounce](flat-bounce.md) — 平弹
- [gap-step](gap-step.md) — 间隙与台阶
- ...
```

## 8. Hardness 约束

| 约束 | 影响 | 处理 |
|---|---|---|
| H14（evidence pin） | 不变 | `[^ev-N]` 仍指向真实锚点 |
| H15（确定性） | taxonomy.json 是确定性输入 | 路由算法无随机数，同输入同输出 |
| H17（链接可验证） | 相对路径深一级 | `../../kb/<doc>/main.md#anchor` |
| H21（新增） | taxonomy.json schema | version=1, slug 非空, 无重复 slug |

## 9. 测试策略

| 文件 | 测试点 | 数量 |
|---|---|---|
| `test_taxonomy_config.py` | TaxonomyConfig 加载/序列化/schema 校验 | ~5 |
| `test_taxonomy_router.py` | route_evidence 4 层优先级、PES 映射、边界情况 | ~8 |
| `test_taxonomy_generate.py` | 从 mock PRD 自动生成 taxonomy | ~5 |
| `test_wiki_subdirs.py` | orchestrator taxonomy 模式输出子目录 + _index.md | ~5 |
| `test_verify_recursive.py` | verify 递归 wiki/**/*.md | ~3 |

**预计 +26 个测试**。

## 10. 向后兼容

- `kb wiki build` 不带 `--taxonomy` → 行为不变（扁平 Jaccard）
- `kb wiki verify` → 自动检测子目录，兼容新旧结构
- `discover_topics()` 不修改签名，taxonomy 模式走独立路径
- taxonomy.json 不存在时 `--taxonomy` 报友好错误

## 11. 版本

**v0.7.0**。

## 12. 范围外（不在本版本做）

- 直接调用外部 LLM API（继续用 `cached` provider）
- 跨 category 交叉引用（如 mechanical 中提到 electrical 的链接）
- 多 PRD 支持（当前假设一个项目一个 PRD）
- taxonomy.json 的 GUI 编辑器
