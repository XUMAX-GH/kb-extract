# PageIndex-style 章节树精炼 v0.2.0 设计稿

- 日期：2026-06-09
- 目标版本：`v0.2.0`
- 作者：XUMAX-GH（与 Copilot 协同设计）
- 状态：已批准，待实施

## 1. 目标与背景

v0.1.0 的 `SectionNode` 类型已经设计成 PageIndex 风格的递归节点（含 `children`、`page_start/end`、`anchor`），
但实际所有 adapter 都只输出**两层扁平结构**（一个 root + 多个 level=1 叶子）。
这让下游消费者（PageIndex 风格的 vectorless RAG、LLM-Wiki 子项目）无法享受真正的树状索引。

本子项目把"潜力"兑现成"实际行为"，并把 outline 质量元数据透明化。

## 2. 范围

### 范围内（必须做）

| 格式 | 当前行为 | 新行为 |
|---|---|---|
| **PDF** | TOC 的 level 字段被丢弃，全部压平到 level=1；无 TOC 时按 page 兜底 | (a) 用 TOC 真实 level 构建递归树；(b) 无 TOC 时启用字号 / 字重启发式推断 heading，仍兜底 page |
| **PPTX** | 每张幻灯片是平的 level=1 | 用 PPTX 原生 Section（"节"）分组幻灯片，构建 section → slide 两层结构 |
| **XLSX** | 按 `wb.sheetnames` 原序输出 | 按 sheet 名前缀数字自然排序（`01_Intro` 在 `10_Appendix` 前） |

### 范围外（保持现状）

- **DOCX**：已用 heading-style stack 真正嵌套，本期不动
- **HTML**：已按 `<h1>..<h6>` 嵌套
- **TXT / Image**：天生无层级
- **ZIP**：包装层，自动跟随子文档改善
- **跨文档项目级索引**（`kb/_index.json`）：留给 v0.3.0 或独立子项目

## 3. 数据模型改动

### 3.1 `SectionNode`（无改动）

```python
@dataclass(frozen=True, slots=True)
class SectionNode:
    node_id: str
    title: str
    level: int           # ← 现在会被有意义地使用（>1）
    page_start: int
    page_end: int
    anchor: str
    language: str
    children: tuple[SectionNode, ...] = ()
```

类型本身不变。变的是：`level` 不再 hard-code 为 1；`children` 不再总是空。

### 3.2 `ExtractionMeta`

```python
@dataclass(frozen=True, slots=True)
class ExtractionMeta:
    # ... 已有字段不变 ...
    outline_source: Literal[
        "bookmark",
        "heading_style",
        "docling_layout",
        "page_fallback",
        "heading_inferred",   # 新增 — PDF 字号推断
        "pptx_section",       # 新增 — PPTX 原生 section
    ]
    outline_confidence: Literal["high", "medium", "low"] = "high"  # 新增字段
    # ... 后续字段不变 ...
```

### 3.3 `outline_confidence` 取值规则

| `outline_source` | 默认 `outline_confidence` |
|---|---|
| `bookmark`         | `high` |
| `heading_style`    | `high` |
| `pptx_section`     | `high` |
| `docling_layout`   | `high` |
| `heading_inferred` | 由聚类判定：簇间方差大且层数少 → `medium`，否则 `low` |
| `page_fallback`    | `low` |

下游消费者（如 #3 LLM-Wiki）可以选择只信任 `high`/`medium` 节点用于自动摘要，
对 `low` 节点要求人工 review 或额外验证。

### 3.4 兼容性

- **读取旧 `meta.json`**：dataclass 给 `outline_confidence` 提供默认值，旧文件加载时自动填 `"high"`。但 v0.2.0 不需要回读旧文件，因为重新提取会覆盖。
- **`content_sha256()`**：因为 `index` 树结构变化，所有现有 KB 的内容哈希会变 → 第一次 `kb extract` 会全量重提取。这是预期行为，CHANGELOG 中明确说明。

## 4. 实施细节（按格式）

### 4.1 PDF：递归 TOC 树

**当前代码**（`pdf_docling.py:47-71`）：

```python
toc = doc.get_toc(simple=True)  # [[level, title, page], ...]
if toc:
    outline_source = "bookmark"
    # Build flat children list at level=1; group multi-page ranges.
    for i, (lvl, title, page) in enumerate(toc):
        children.append(SectionNode(..., level=1, ...))  # ← 丢掉了 lvl
```

**新行为**：用栈遍历 TOC，按 level 嵌套：

```python
def _build_pdf_tree(toc: list, n_pages: int) -> tuple[SectionNode, ...]:
    """Build a recursive tree from pymupdf TOC entries.
    
    toc: [[level, title, start_page], ...] (1-based pages, 1-based levels)
    Returns top-level children (level==1) with descendants nested.
    """
    # Compute end_page for each entry: next sibling's start - 1, or n_pages for last.
    # Then walk with a stack: push when child.level > top.level, pop until top.level < child.level.
```

边界处理：
- TOC 中 level 跳跃（1 → 3）：把缺失层补成隐式父节点（title="(implicit)"），或直接挂到最近的合适父节点（推荐：直接挂，避免幻觉假节点）
- 同级连续节点：按顺序追加到当前父节点
- TOC 为空：走 4.2 的启发式

### 4.2 PDF：字号启发式 heading 推断

新模块 `src/kb_extract/adapters/pdf_heading_infer.py`：

```python
def infer_headings(doc: fitz.Document) -> tuple[list[InferredHeading], str]:
    """
    Heuristic heading detection from font size + weight.
    
    Algorithm:
    1. Collect (page, y, font_size, is_bold, text) for every span on every page.
    2. Find body font size = mode of font sizes weighted by char count.
    3. Heading candidates = spans where font_size > body * 1.1 OR (font_size >= body AND is_bold).
    4. Cluster heading candidates by rounded font size (nearest 0.5pt).
    5. Map clusters to levels: largest cluster size → level 1, next → level 2, etc. (cap at 4 levels).
    6. Confidence:
       - "medium" if top cluster has >= 3x body size or >= 3 distinct cluster levels
       - "low" otherwise
    
    Returns: (list of InferredHeading(page, level, title), confidence)
    """
```

性质：
- 纯数值，无 LLM（H2 通过）
- 同 PDF 字节输入 → 同字号 → 同推断（H8 通过）
- pymupdf 字号是 float，但 `round(fs * 2) / 2` 量化到 0.5pt，规避浮点抖动

边界：
- 推断结果为空 → 退回 `page_fallback`，confidence=`low`
- 推断结果只有 1 层 → 接受，confidence=`low`

### 4.3 PPTX：原生 Section 支持

PPTX 的 "Section"（节）功能保存在文件 XML 的 `_rels/presentation.xml.rels` 和 `ppt/presentation.xml` 的 `<p:sectionLst>` 元素。

`python-pptx` 在 0.6.21+ 版本暴露 `Presentation.slides.slide_sections`？需要先验证 API 可用性。若不可用，回退到直接读取 `prs.element.findall(...sectionLst...)` XML 解析。

**实施步骤**：
1. 用一个有 section 的 .pptx 测试文件验证 python-pptx API
2. 若 API 缺失，直接 lxml 解析（不引入新依赖；python-pptx 内部就用 lxml）
3. 构建两层树：root → section → slides
4. 无 section 的 PPTX 行为不变（保持 v0.1.0 的扁平 slides 行为，`outline_source` 不变）

### 4.4 XLSX：确定性排序

把 `wb.sheetnames` 通过 natural sort key 排序后再迭代：

```python
import re
def _natural_key(name: str) -> tuple:
    """('01_Intro', ...) → ((1, 'intro'), ...) for stable sort."""
    parts = re.split(r"(\d+)", name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)
```

- 无前缀数字的 sheet 按字典序追加在最后
- 同前缀不同后缀按字典序细排
- `outline_source` 保持 `heading_style`（XLSX adapter 一直用这个，因为每个 sheet 就是一个 "heading"）
- `outline_confidence` = `high`

## 5. 测试策略

### 5.1 新增测试

| 文件 | 验证 |
|---|---|
| `tests/test_pdf_tree.py` | 给一个含 nested TOC 的 PDF（用 pymupdf 编程生成）→ 验证 `index` 是真正的多层树 |
| `tests/test_pdf_heading_inference.py` | 给一个无 TOC 但有清晰字号差的 PDF → 验证 `outline_source=heading_inferred` 且层级合理 |
| `tests/test_pptx_sections.py` | 给一个带 sections 的 .pptx → 验证 root → section → slides 两层结构 |
| `tests/test_xlsx_sort.py` | sheets = `["10_Z", "01_A", "02_B"]` → 输出顺序 `01_A, 02_B, 10_Z` |
| `tests/test_outline_confidence.py` | 各 adapter 的 `meta.json` 都含 `outline_confidence` 字段 |

### 5.2 旧测试更新

- `test_contracts.py`：新枚举值 + 新字段
- `test_meta_schema.py`（若有）：补全断言
- 现有 adapter 测试：在期望的 meta dict 中加 `outline_confidence`

### 5.3 Hardness 不变量

| 不变量 | 影响 |
|---|---|
| H2 (no LLM) | 字号启发式纯数值，OK |
| H8 (deterministic) | 量化 0.5pt 规避浮点抖动；sort 用稳定 key；OK |
| H13 (cross-platform identity) | 不变；既有 H13 fixture 也会被新逻辑跑通 |
| H1 (no网络) | 不变 |
| 其他 | 不变 |

### 5.4 CI

无 CI 改动。现有矩阵会自动跑新测试。

## 6. 版本与发布

- 版本号：`v0.2.0`（minor — 新字段、新枚举值、行为变化）
- CHANGELOG：标"BREAKING for cached outputs"，说明 content_sha256 会变
- README：更新 hardness 表（confidence 列）；更新 "outline" 章节描述新行为
- SKILL.md：更新 `version` 字段；触发短语不变

## 7. 失败 / 回滚预案

若 v0.2.0 发布后发现 PDF 启发式在某类文档上明显失常：

1. **降级开关**：在 CLI 加 `--no-heading-inference` 旗标，跳过 4.2 启发式直接 page_fallback
2. **环境变量**：`KB_EXTRACT_DISABLE_INFER=1` 用于 CI / 批处理
3. **回滚版本**：保留 `v0.1.0` tag，用户可以 `pip install kb-extract==0.1.0` 或 `/plugin install kb-extract@v0.1.0`

## 8. 范围外（未来）

- 跨文档项目级 `kb/_index.json` —— 留给 v0.3.0 或独立子项目
- TOC 文本聚类合并相似 title —— v0.3.0 LLM-Wiki 层做
- 表格 caption 自动识别 —— 不在本次范围
- 多语言 outline title 翻译 —— 不在本次范围

## 9. 实施任务清单（参考 SQL todos）

见 todos 表 `sp2-*` 系列，包含：spec、schema、adapters-baseline、pdf-toc-tree、pdf-infer、pptx-sections、xlsx-sort、tests、docs、ship。
