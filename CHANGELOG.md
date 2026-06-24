# 更新日志

## [0.12.0] - 2026-06-24

### Added
- `kb source` command (SP-2): converts each input file to a readable,
  image-free, redacted `source.md` via the embedded markitdown library.
  Output is normalized and byte-reproducible for a fixed markitdown version;
  idempotency is tracked in a separate `kb/source.manifest.sqlite` with a
  per-document counts-only `source.meta.json` sidecar. The deterministic
  `kb extract` core and `kb verify` are untouched. markitdown is imported only
  in `source_md.py`, preserving the adapter LLM-import invariant.

## [0.11.0] - 2026-06-24

### Added
- Deterministic redaction layer (SP-1): opt-in `redaction.toml` policy redacts
  part-number text (e.g. M132xxxx / H123xxxx) and drops logo images before the
  extraction output is written. Anchors are preserved and output stays
  byte-reproducible. Adds `kb extract --redaction-policy / --no-redaction`, a
  counts-only `redaction.json` audit sidecar, manifest re-extraction when the
  policy changes, and redaction propagation into nested ZIP children. Text rules
  also redact `index.json` section titles and `meta.json` free-text fields
  (source_path, warnings, skipped_reasons); anchors and node ids are preserved.

所有重要的版本变更都会记录在本文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)；
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

## [0.10.0] — 2026-06-22

**PRD 目录（Table of Contents）驱动的层级**：当 PRD 的 PDF 抽取导致正文
标题退化（章节号 "## 2" / "## 3" 保留，但标题文字 "PRODUCT OVERVIEW" /
"MECHANICAL" 丢失）时，v2 用正文标题构建的树会得到一堆以纯数字命名的垃圾
子系统。本版本改为从 PRD 的 "Contents" 目录页解析干净的编号层级，再用
章节号作为连接键，把正文证据回填到这棵树上。同时增强关键词回退路由：
按 section 标题、再按文档标题逐层下钻到最匹配的节点，让没有目录映射的
规格文档也能落到对应的子系统 / part / function。

### Added
- `parse_prd_toc(main_md)`：解析 PRD "Contents" 目录页，得到有序的
  `(number, title, depth)` 列表，自动跳过页眉 / 页码 / 点线引导符等噪声。
- `generate_taxonomy_v2(..., from_toc=True)`：从目录构建 4 层树，每个节点
  把自己的章节号存入 `prd_headings`，顺序即目录阅读顺序（确定性、不重排）。
- `is_toc_taxonomy(config)`：检测 taxonomy 是否为目录模式（子系统的
  `prd_headings` 为纯章节号）。
- `build_prd_toc_section_map_v2(...)`：从树重建 `{章节号: 路径}`，再把 PRD
  正文锚点按章节号路由进树；缺失的章节号回滚到最近的祖先节点。
- CLI `kb wiki taxonomy generate` 新增 `--from-toc` 开关。
- 关键词回退现在会下钻到关键词重叠最多的最深节点；section 标题无信号时，
  再用文档标题（如 "M9000006 Keyset Backlight LED Test"）整篇路由。

### Changed
- `route_evidence_v2` 的关键词回退由"只命中顶层 system"升级为"下钻到最深
  匹配节点"，并新增文档标题回退（优先级低于 section 标题）。



**分层 Wiki 知识库（Taxonomy v2）**：把 wiki 的扁平 1 层分类升级为 4 层
树（system → subsystem → part → function），完整反映 PRD + PES 文档的
真实组织结构。生成、路由、写盘、orchestrator、CLI 全部贯通，
完全向后兼容（v1 公共 API 全部保留，v1 taxonomy.json 自动迁移）。

### Added

- **数据模型**（`wiki/taxonomy.py`）：
  - `CategoryNode`：frozen+slots dataclass，递归 children；
    携带 `layer / prd_headings / pes_headings / linked_specs / keywords`。
  - `TaxonomyConfigV2`：v2 配置根，新增 `source_pes_glob`。
- **Schema 迁移**（透明、幂等）：
  - `migrate_v1_to_v2(raw_dict)`：v1 dict → v2 dict；v1 类目统一升为
    `layer="system"`、`source_pes_glob=None`、children 为空。
  - `load_taxonomy_v2(path)` / `save_taxonomy_v2(cfg, path)`：原子写入、
    确定性 JSON（每层按 slug 排序）。
- **自动生成**（`generate_taxonomy_v2`）：
  - PRD H1 → system、H2 → subsystem。
  - 通过 `--pes-glob` 启用 PES 挂载：每个匹配的 PES H1 → part、
    H2 → function。
  - 双策略识别 PES 归属：先尝试 subsystem `linked_specs` 精确匹配；
    退化到 system 级 `linked_specs` + PES 文件名 token 与 subsystem
    标题的交集匹配（适配实际 PRD 把 Reference Documents 表格放在
    H1 章节下的常见排版）。
  - 跨 PES 同名零件**不合并**（不同 subsystem 下的同名 part 独立）。
- **路由引擎**（`route_evidence_v2`）：
  - 返回 `tuple[str, ...]` 路径，最长前缀匹配。
  - 优先级：PRD anchor map > PES anchor map > subsystem linked_specs >
    keyword fallback (top-level system) > `('_uncategorized',)`。
  - 辅助函数 `build_prd_section_map_v2` / `build_pes_section_map_v2`。
- **Orchestrator v2**（`build_wiki_v2`）：
  - 递归生成 `_index.md`：根 `wiki/_index.md` 列系统，每个 system /
    subsystem / part 节点的目录都有自己的 `_index.md`，列子分类 +
    该节点直接挂载的 topic 文章。
  - 终端 topic 写到对应深度路径，例如
    `wiki/audio/speaker/tweeter/frequency-response/<topic>.md`。
- **Writer 路径泛化**（`build_topic_markdown`）：
  - 新增 `category_path: tuple[str, ...]` 参数，footnote URL 前缀
    自动按深度计算为 `"../" * depth + "../kb"`，支持 1..4 层。
  - 向后兼容 `category_slug`（深度 1）。
- **CLI**：
  - `kb wiki taxonomy generate` 新增 `--pes-glob` 选项；传则生成 v2，
    不传保持 v0.7 v1 行为。
  - `kb wiki build --taxonomy` 自动识别 v1 / v2 schema 并分派到对应
    orchestrator。
- **H21 v2 不变量**（`validate_taxonomy_v2`）：
  - schema version 必须为 2
  - slug 非空、同级 slug 唯一
  - layer 必须 ∈ `{system, subsystem, part, function}`
  - 子节点 layer 必须正好比父深一层（不允许跳跃 / 倒置）
  - 树深度上限 4

### Changed

- `wiki/index.json` 在 v2 模式下新增 `taxonomy_version=2`、
  `source_pes_glob` 字段；每个 topic 含 `category_path: [...]` 数组。
  legacy `category` 字段仍写入（`"/".join(path)`），供 `verify_wiki`
  和旧版工具消费。
- README 全面刷新为中文 v0.9.0 版本，新增"分层 Wiki 知识库"章节，
  含 4 步快速上手与路由优先级说明。

### Tests

- 新增 50 个 v2 测试（8 CategoryNode + 9 migrator + 8 H21 + 9 generate +
  9 router + 7 writer + 6 e2e）。完整套件 446 通过。

### 设计文档

- `docs/superpowers/specs/2026-06-15-taxonomy-v2-design.md`（376 行）

---

## [0.8.0] — 2026-06-15

**MinerU 启发的 Parser v2**：四个核心适配器（docx / pptx / xlsx / pdf）
重写为 v2，原生支持合并单元格 HTML、嵌入图像抽取、PDF 表格识别、页眉/
页脚去重、扫描页警告，以及统一的资产命名约定。v2 适配器自动注册为默认，
原 v1 适配器保留为可显式 import 的兼容入口但不再自动注册。

### Added

- **共享辅助模块** (`src/kb_extract/adapters/_table_utils.py`,
  `src/kb_extract/adapters/_image_utils.py`)：
  - `CellInfo` 数据类 + `cells_to_html(rows)` 把无幻影格的二维网格渲染成
    带 `colspan` / `rowspan` 的 HTML `<table>`。
  - `detect_image_format()` 通过 magic bytes 识别 PNG/JPG/GIF/BMP；
    `save_image()` 写入 `assets/<prefix>_<idx>.<ext>`，自动忽略 < 1 KiB
    的装饰性图标。纯 stdlib，跨平台 byte-identical。
- **`DocxV2Adapter`** (`adapters/docx_v2.py`)：
  - 合并单元格通过直接解析 `<w:tr>` / `<w:tc>` / `<w:vMerge>` XML 实现
    （绕过 python-docx 的虚拟单元格陷阱），输出带 `colspan` /
    `rowspan` 的 HTML 表格。
  - 嵌入图像通过 `<a:blip r:embed>` 解析 → `doc.part.related_parts`，
    走 `save_image()` 写到 `assets/`。
- **`PptxV2Adapter`** (`adapters/pptx_v2.py`)：
  - `MSO_SHAPE_TYPE.PICTURE` 图像抽取 → `assets/slide_N_img_M.ext`。
  - 表格通过 `cell.span_width` / `span_height` 构建无幻影网格 → HTML。
  - `GroupShape` 递归（`_walk_shapes()`），组内文本和图像不再丢失。
  - 演讲者备注切换为 `> **Note:**` blockquote 标记。
- **`XlsxV2Adapter`** (`adapters/xlsx_v2.py`)：
  - `ws.merged_cells.ranges` → HTML 表格保留合并；放弃 `read_only=True`
    以换取合并信息可见。
  - `cell.number_format` 感知：百分比（`0.0%`）、货币（`$#,##0.00`）、
    日期（ISO 8601）均按格式渲染为字符串。
  - 空单元格显示为 U+2014 em-dash，稀疏网格更易识别。
- **`PdfV2Adapter`** (`adapters/pdf_v2.py`)：
  - 页眉/页脚去重：`_detect_running_lines()` 统计每页（去重计数）后
    在 >=50% 页面出现的行视为 running，在 body 文本中剥离。
  - 表格识别：`page.find_tables()` 每页扫描 → `cells_to_html()` 注入
    对应 section 锚点之后。
  - 每页 scanned 警告：少于 50 个非空白字符的页发出
    `pdf.scanned_page:pN`。原 `pdf.scanned_no_text_layer` 仍保留。
  - 图像走 `save_image()` 统一命名 `page_N_img_M.ext`。
- **H22 image-integrity hardness invariant** (`hardness.py`,
  `warnings_registry.py`)：每个 `![](assets/...)` 引用的文件必须通过
  magic-bytes 校验，捕获绕过 `save_image()` 的伪图像文件。
  新增 5 个单元测试。

### Changed

- `kb_extract.adapters.__init__` 不再自动注册 v1 适配器（`DocxAdapter`、
  `PptxAdapter`、`XlsxAdapter`、`PdfDoclingAdapter`），而是注册它们的 v2
  对应物。v1 类仍可显式 import 用于显式对照测试或下游 pinning。
- `assert_invariants()` 在 H3..H11 之后多跑一次 H22 检查。
- `warnings_registry`：新增 `pdf.scanned_page:p\d+` 允许的警告格式。

### Tests

- 12 个 `_table_utils` 单元测试 + 13 个 `_image_utils` 单元测试。
- 每个 v2 适配器各 9–10 个测试，覆盖：baseline 等价、确定性、hardness
  invariants（含新 H22）、合并单元格、图像抽取、特性增强。
- 共新增 **80+ 个测试**；总计 **390 通过**；ruff 全绿。

### Migration notes

- 调用方默认使用 v2，无需任何代码改动。
- 输出格式有以下可见差异：
  - 含合并单元格的表格从 pipe markdown 切换为 HTML `<table>`。
  - 演讲者备注从 `> Note:` 改为 `> **Note:**`。
  - XLSX 空单元格从空字符串改为 em-dash。
  - PDF 多页文档中可能新增 `pdf.scanned_page:p*` 警告。

---


## [0.7.0] — 2026-06-15

按 PRD 文档结构把 wiki 重新组织成**子系统分类**：evidence 经过 4 层优先级
路由（heading-path → linked-spec glob → keyword → fallback）落到对应的
`wiki/<category>/<slug>.md`，每个 category 自动生成 `_index.md` 入口页。
原有的扁平模式完全向后兼容（不带 `--taxonomy` 时行为不变）。

### Added

- **`TaxonomyConfig` 数据模型与 JSON I/O**
  (`src/kb_extract/wiki/taxonomy.py`)：
  - `Category` (`slug` / `title` / `prd_headings` / `linked_specs` /
    `keywords`) + `TaxonomyConfig` (`version` / `source_prd` /
    `categories`)，全部 `frozen=True, slots=True`，确定性序列化。
  - `load_taxonomy(path)` / `save_taxonomy(cfg, path)` — JSON I/O 带
    schema 校验，原子写盘（**H21**）。
- **4 层 evidence 路由**：`route_evidence(ev, cfg, prd_section_map)` 按
  priority 1 (PRD heading-path) → 2 (linked-spec fnmatch) →
  3 (keyword 在 section_title 中) → 4 (`_uncategorized` fallback) 决定
  evidence 归属的 category。`build_prd_section_map(kb_root, cfg)` 从 PRD
  的 `index.json` 递归构建 anchor → category 映射。
- **`generate_taxonomy(kb_root, prd_doc_id=None)`** 自动从 PRD 文档结构
  生成 `TaxonomyConfig`：未指定 `prd_doc_id` 时自动检测含 "PRD" 的目录，
  以 H1 章节为 category，把 H2 子章节与匹配的 spec 文档作为
  `prd_headings` / `linked_specs`。
- **`build_wiki(..., taxonomy=cfg)` 端到端 taxonomy 模式**
  (`wiki/orchestrator.py`)：路由所有 evidence 到 category，每个 category
  内部再做 Jaccard 聚类，输出 `wiki/<cat>/<slug>.md` +
  `wiki/<cat>/_index.md`；`index.json` 新增 `taxonomy_mode=true` 与每个
  topic 的 `category` 字段。
- **`writer.build_topic_markdown(category_slug=..., category_title=...)`**：
  footnote URL 自动深一层（`../../kb/...`），system prompt 追加子系统
  上下文提示。
- **`verify_wiki()` 递归校验**：根据 `taxonomy_mode` 自动处理两种布局
  (`wiki/*.md` vs `wiki/<cat>/<slug>.md`)，H14 行为保持不变。
- **CLI**：
  - `kb wiki taxonomy generate <path> [--prd-doc DOC] [--out FILE] [-o DIR]`
    — 自动生成 `taxonomy.json`（默认写到 `<project>/wiki/taxonomy.json`）。
  - `kb wiki build --taxonomy <taxonomy.json>` — 启用 category 模式。
    无此 flag 时行为与 v0.6.0 完全一致。

### Hardness

- **H21 — Taxonomy schema integrity**：`load_taxonomy` 拒绝 schema 不一致
  的 JSON；`save_taxonomy` 走 `serialize_markdown` 同款的 byte-identical
  序列化（`sort_keys=True`、UTF-8、LF），保证跨平台 hash 稳定。

### 测试

新增 27 个用例：`test_taxonomy_config.py` (5) + `test_taxonomy_router.py`
(13) + `test_taxonomy_generate.py` (5) + `test_wiki_taxonomy_e2e.py` (5) +
`test_cli_taxonomy.py` (4)，全部 `disable_socket`、纯算法、确定性。

### 向后兼容

- `build_wiki(...)` 不传 `taxonomy=` 时输出与 v0.6.0 byte-identical。
- `wiki/index.json` 新增字段 (`taxonomy_mode` / `category`)；旧的扁平
  index 仍能被新 `verify_wiki` 正确识别（`taxonomy_mode` 缺失 → False）。

---



把 wiki 层从 *基于标题的占位 LLM* 升级为 *基于章节正文的真实 LLM*：新增
`cached` provider（用于本地/CI 可复现地驱动任意 LLM 的回放），
新增 `kb wiki dump-prompts` 子命令（导出提示词，便于手工或脚本喂给 LLM），
并把 wiki 提示词从「仅标题」改为「标题 + 节段正文摘要」。

### Added

- **`cached` 真 LLM provider**（`src/kb_extract/wiki/providers/cached.py`）：
  - `CachedLlmClient(responses_path=...)` 接受 `{prompt_hash: response}` 的
    JSON，按 SHA-256 规范化 hash 匹配 prompt → 回复。命中即返回，未命中
    可选择 **strict 抛 `CachedResponseMissing`**，或 **record 模式** 把
    缺失 prompt 落盘并返回占位符（便于把 wiki build 跑完再补回复）。
  - 公开 `prompt_hash(messages)` helper，供工具脚本使用。
- **`kb wiki dump-prompts` 子命令**：把 discover_topics 之后会发给 LLM 的
  *全部* 提示词写到一个 JSON 文件（按 prompt_hash 索引，含 topic_slug /
  topic_title / evidence_count / messages）。供 *人工* 走 Claude / GPT-4 /
  本地 LLM 后再写回 `responses.json`。
- **`kb wiki build --provider cached --responses-file <path>`**：从
  responses.json 读回复驱动 wiki 生成；可选 `--record-missing` 在 cache miss
  时记录而非中断。
- **`--min-evidence N` 与 `--skip-numeric-titles`**（`wiki build` /
  `wiki dump-prompts` 通用）：跳过 evidence 数过少 / 标题全是数字的"噪声"
  topic（在 137-topic 真实数据上，把生成数从 137 → 23，去掉了 77 个仅含
  数字标题、1 evidence 的占位簇）。
- **章节正文抽取 helper**（`src/kb_extract/wiki/sections.py`）：
  `read_section_body(kb_root, doc_id, anchor, *, max_chars=1500)` —— 从
  `kb/<doc_id>/main.md` 中按 `<a id="..."></a>` 锚点定位到下一个
  `<a id="sec-NNNN"></a>` 之间的正文，截断 + 加省略号。供 writer 注入。
- **新增 23 个测试**（4 个测试文件）：
  - `test_section_body.py` × 7
  - `test_writer_body_aware.py` × 4
  - `test_topics_filters.py` × 5
  - `test_cached_provider.py` × 7

### Changed

- **wiki writer 现在向 LLM 注入 evidence 正文摘要**（每条 ≤ 1200 字符 + 省略号）
  而不是只发标题。system message 改进为：(a) 中英语境自适应；(b) 明确硬件
  spec 上下文；(c) 显式 "不准编造 / 必须按 `[^ev-N]` 引证"。
- `wiki/topics.discover_topics()` 增加 `min_evidence` 与
  `skip_numeric_titles` 形参，默认值保持 `1 / False`（向后兼容）。
- `wiki/orchestrator.build_wiki()` 把 `kb_root` 透传给 `build_topic_markdown`，
  以便 writer 注入 section body。
- `wiki/providers/mock.get_provider()` 接受 `**kwargs`，新增分支
  `name == "cached"` 直接构造 `CachedLlmClient`。

### Verification

在 BC 22-doc 真实数据集（13 PDF + 5 DOCX + 4 XLSX）上验证：

- `kb wiki dump-prompts ... --min-evidence 2 --skip-numeric-titles` →
  **23 个提示词**（172 KB），下降比例 23/137 ≈ 17%。
- 用 *Claude Opus 4.7（GitHub Copilot CLI 当前模型）* 在 session 内
  人工 / 半自动写 23 个中文 markdown 回复，落盘 `responses.json`。
- `kb wiki build ... --provider cached --responses-file ...` →
  **23 topics, 180 pins, 0 unresolved**。
- `kb wiki verify ...` → **ok**（所有 `[^ev-N]` 引证均指向真实存在的锚点）。
- 全套 277 + 23 = 300 测试通过；ruff clean。

### Migration / Compatibility

- 既有 `wiki build` 调用（不带新 flag）行为完全不变 —— `mock` provider 仍是默认。
- `discover_topics()` 的新参数都有默认值，旧调用站点不需要改。
- `responses.json` 文件是稳定的（key 是 messages 的规范化 SHA-256，
  与时间 / 顺序无关），便于 Git 跟踪与 CI 复现。

### Known Limitations

- Windows 默认 cp1252 stdout 无法编码 `→` 等 Unicode 字符；在调用
  `kb wiki dump-prompts` 前需设 `$env:PYTHONIOENCODING="utf-8"`。已记入
  v0.6.1 待办（在 CLI entry 加 `sys.stdout.reconfigure(encoding="utf-8")`）。
- `slide` topic（61 evidence）prompt 约 73 KB，对 8K-context LLM 会超长；
  当前数据集下 Claude / GPT-4 family 均可处理。后续可加 `--max-evidence` 截断。

## [0.5.0] — 2026-06-10

新增功能：把抽取产物写到任意目录，并修复 v0.4.1 之后在真实 22 文档批量抽取
中暴露的 2 个 H9 / 1 个 H11 假阳性。

### Added

- **`--output-dir / -o` 参数**（对 5 个命令均生效：`extract` / `verify` /
  `wiki build` / `wiki verify` / `manifest`）。
  当提供该参数时，`kb/` 与 `wiki/` 会在 `<output-dir>` 下创建，而不是
  源文件根目录下。源文件本身永远不会被改动（只读）。
  - 例：`kb extract -o D:\out C:\spec` → `D:\out\kb\<file>/main.md`
  - 中间目录会自动创建。
  - 多源批处理时，`<output-dir>/kb/` 下子目录结构仍以 *源根目录* 的相对路径为准，
    保留原始层级。
- 新增 `kb_extract.layout.kb_dir()` 和 `wiki_dir()` 公共 helper。

### Changed (hardness 语义微调，向后兼容)

- **H9 改为基于覆盖的判定（不再是仅 leaves）**。原版规则
  "leaves 必须两两不重叠且联起来正好等于 [1, total_pages]" 在真实数据上对
  两类合法形状报假阳性：
  1. **DOCX/XLSX 单页多 section**：DOCX 的 sections 都标 page=1..1，
     旧规则把它们当作互相重叠。
  2. **PDF 父节点 intro 内容**：父节点 page 1..N、第一个子节点从 page 3+
     开始时，pages 1..2 属于父节点本身的 intro 内容，但旧 leaves-only
     遍历漏算了父节点，触发 "gap before leaf"。
  新规则：**所有非根节点（leaf + interior）的 `[page_start, page_end]`
  联起来必须等于 `{1..total_pages}`**。范围合法性（page_start ≤ page_end，
  在 1..total_pages 范围内）仍然严格检查；真实的"页面缺失"也仍会被捕获。
  对单 leaf-per-page 的 PDF 行为完全不变。
- **H11 docx.unknown_style 允许括号、点号、逗号**。Word 中 "Normal (Web)" /
  "Heading 1 (Char)" 等带括号的 linked 样式名是合法的，原 regex
  `[\w\- ]+` 拒绝了它们；现已放宽到 `[\w\- ().,]+`。

### Notes

- 既有 API 完全向后兼容：`output_dir=None`（默认）时行为与 0.4.x 一致。
- wiki 的相对链接 `../kb/<doc>/main.md#<anchor>` 仍然正确解析 —— 因为 kb/ 和 wiki/
  在 `<output-dir>` 下是兄弟目录。
- 真实环境验证：用本 v0.5.0 把 22 份 Surface 硬件 spec（13 PDF + 5 DOCX +
  4 XLSX，约 20MB）抽到独立 markdown 目录，22/22 ok、137 wiki topics、
  193 evidence pins、0 violations。

### Tests

- 4 个新 CLI 测试覆盖 `--output-dir`（extract/verify/wiki build + 中间目录自动创建）。
- 5 个新测试覆盖 H9 coverage-based 语义。
- 7 个新测试覆盖 docx.unknown_style 括号 / 点号 / 逗号。
- 既有 `test_h9_fails_on_overlap` 调整为反映新语义（覆盖完整就 OK）。
- 既有 `test_wiki_build_records_history` 调整新 args 字段。
- 总计 **254 passed**, ruff clean.

## [0.4.1] — 2026-06-10

修 v0.4.0 在真实 PDF 上首次试用时暴露的 3 个 bug：

### Bug fixes

- **PDF 适配器：image-only 封面页导致 H9 page-range gap**
  当 PDF 的第 1 页是纯图（如扫描封面）、首个文本/TOC 标题落在第 2 页或更后时，
  `_build_pdf_tree_from_toc` 和 `_build_pdf_tree_from_inferred` 都没有覆盖前缀
  页，H9 会抛 `page-range gap before leaf 0001: pages 1..N missing`。
  现在两条路径都会在 `items[0].page > 1` 时前置一个 `# Front matter` 节点覆盖
  pages 1..(first-1)。
- **PDF font-size 推断：同页多个 heading-sized 字段导致 H9 page-range overlap**
  字号推断会把同一页上多段大字识别为多个独立标题，每个生成一个 leaf，全部声
  明 page_start==page_end==P，H9 视作重叠违规。现在 `_build_pdf_tree_from_inferred`
  按 (page, level) 排序后每页只保留第一个标题（即字号最大的）。
- **H18 evidence_origins 在真实工程上一直是空数组**
  `_load_source_sha256_map` 之前查询了不存在的 `manifest` 表（实际表名是
  `sources`，见 `kb_extract.manifest`）。异常被 try/except 吞掉，返回 `{}`，
  导致 `wiki/index.json` 的每个 topic 都显示 `evidence_origins: []`。
  现在先尝试 `sources` 表，回退到 `manifest`（兼容 sketched-out 的旧数据库）。
- **test_h18 fixture**：测试用例之前手写 `CREATE TABLE manifest`，现已对齐
  真实 schema (`CREATE TABLE sources`)，避免假阳性。

### 新增测试

- `tests/test_pdf_front_matter_padding.py` (3 tests)
  - inferred 路径前缀覆盖
  - inferred 路径同页 heading 合并
  - TOC 路径前缀覆盖

总测试数：235 → 238 (+3)

## [0.4.0] — 2026-06-09

合并 sp4（hardness 扩展）+ sp5（memory layer）到同一发行版。

### 新增 — sp4 hardness extensions

- **H17 `citation-graph-integrity`**：wiki 中每个 `[^ev-N]` 指向的 anchor 不仅
  要存在于对应 `kb/<doc>/main.md`，还必须**唯一**出现。`kb wiki verify` 现在
  会同时检查存在性和唯一性。
- **H18 `multi-source-provenance`**：当一个 topic 的 evidence 跨多份源文档时，
  `wiki/index.json` 的 `topics[].evidence_origins` 字段必须列出全部 source sha256
  （从 `kb/manifest.sqlite` 读取）。`kb wiki verify` 会比对实际 origins 与声明 origins。
- **H19 `wiki-mock-byte-stability`**（CI 强制）：v0.3 的 H15 只保证同进程同
  seed 输出 byte 一致；H19 进一步要求跨 OS 也一致（CI 增加跨平台 hash 比对 job）。
- **H2 边界扩展**：adapters 不仅不能 import LLM SDK，也不能 import `kb_extract.wiki`
  或 `kb_extract.memory`（防止反向依赖）。

### 新增 — sp5 memory layer

- **`src/kb_extract/memory/`** 模块：sqlite 持久层（WAL + BEGIN IMMEDIATE，
  支持多进程并发，对应新 hardness 约束 **H20**）。
- **新 CLI 子命令**：
  - `kb remember <key> <value>` / `kb remember --list` —— 用户偏好读写
  - `kb forget <key>` —— 删偏好
  - `kb recall [--project X] [--command Y] [--limit N]` —— 回顾命令历史
- **自动 history hook**：`kb extract` / `kb verify` / `kb wiki build` /
  `kb wiki verify` 每次运行结束自动记录一条 history（含 exit_code、参数、摘要）。
  写入失败时静默（决不破坏主命令）。
- **路径解析**：默认 `~/.kb-extract/memory.db`；可用 `KB_EXTRACT_HOME` 环境变量覆盖。

### 测试

- 新增 5 个测试文件，25 个测试：`test_h17_citation_uniqueness.py`、
  `test_h18_multi_source.py`、`test_memory_store.py`、`test_memory_cli.py`、
  `test_memory_hooks.py`
- 总用例数：210 → 235 (+25)

### 兼容性

- `wiki/index.json` schema 新增 `evidence_origins` 字段（每个 topic 一份）。
  老 v0.3 的 index.json 缺少该字段，重新跑一次 `kb wiki build` 即可补上。
- v0.4 的 memory.db 不存在时自动创建；卸载 kb 不会自动清除 memory.db
  （保留用户数据；如需彻底删除请手动 `rm ~/.kb-extract/memory.db`）。

## [0.3.0] — 2026-06-09

LLM-Wiki 层 (Karpathy LLM-Wiki 风格)：在 v0.2 抽取产物之上，构建带强制
evidence pin 的二级 wiki 文档。这是包内**唯一**允许调 LLM 的层；
adapters 仍然受 H2 不变量约束。

### 新增

- **新 CLI 子命令组** `kb wiki`：
  - `kb wiki build <project>`：基于 `<project>/kb/` 重建 `<project>/wiki/`
  - `kb wiki verify <project>`：校验所有 evidence pin 都能解析到真实 anchor
- **可插拔的 LLM provider 协议** (`src/kb_extract/wiki/providers/`)：
  - `MockLlmClient`：完全确定性的零网络 provider，CI 默认
  - `openai` / `anthropic` / `ollama` 留了占位接口（NotImplementedError，
    在 v0.4 接真实 SDK）
  - 通过 `--provider` 或 `KB_EXTRACT_LLM_PROVIDER` 环境变量切换
- **纯算法 topic 聚类** (`wiki/topics.py`)：从 `kb/<doc>/index.json` 收集叶子
  section title，按词集合 Jaccard 距离 (≤ 0.85) 做 single-linkage 聚类，
  跨文档自动合并相似主题。无 LLM。
- **Evidence pin 与脚注解析** (`wiki/writer.py`)：LLM 生成的每个 `[^ev-N]`
  自动追加 `[^ev-N]: [Section Title (p.X)](../kb/<doc>/main.md#<anchor>)` 脚注定义。
  越界编号会被显式标记为 `UNRESOLVED`。
- **3 条新增 hardness 不变量**：
  - **H14** `evidence-pin-resolves`: 每个 `[^ev-N]` 都指向真实存在的 kb anchor
  - **H15** `wiki-determinism-under-seed`: 固定 provider + seed 时 wiki/ 全部
    输出 byte 一致
  - **H16** `no-extract-side-effect`: `kb wiki build` 不修改 `kb/` 下任何文件
- **adapters 层导入边界自动检查**：测试 `test_adapter_does_not_import_from_wiki_layer`
  保证 adapters 永远不会反向依赖 wiki 层（H2 扩展）。

### 测试

- 新增 4 个测试文件，22 个测试：`test_wiki_mock_provider.py`、
  `test_wiki_topics.py`、`test_wiki_writer.py`、`test_wiki_e2e.py`
- adapters H2 测试自动从 11 个增长到 22 个（每个 adapter ×2 条不变量）
- 总用例数：177 → 199 (+22 sp3)

### 兼容性

- v0.3 的 `kb extract` 行为与 v0.2 完全一致
- 旧版本（v0.1 / v0.2）的 `kb/` 产物可以直接 `kb wiki build`，无需重抽
- `meta.json` schema 未改

## [0.2.0] — 2026-06-09

PageIndex 风格的章节树精炼。所有已抽取的 `kb/` 内容哈希都会变化，
首次重新提取会触发全量更新（这是预期行为，见下方"破坏性变更"）。

### 新增

- **真·递归章节树**：之前所有适配器都把章节压成两层（root + level=1 叶子），
  现在 PDF / PPTX 在条件具备时会构建多层嵌套：
  - `PDF` 用 PyMuPDF 的 TOC `level` 字段，原样保留章 / 节 / 小节嵌套
  - `PPTX` 检测 PowerPoint 原生"节"（Sections），形成 root → section → slide 两层
- **PDF 字号启发式 heading 推断**（`pdf_heading_infer.py`）：当 PDF 没有 TOC 时，
  按字号 / 字重纯数值聚类推断 heading 层级。完全确定性，无 LLM、无随机性。
  量化到 0.5pt 规避浮点抖动，保证 H8 / H13 不变量。
  - 标记为 `outline_source="heading_inferred"`，与 bookmark 来源区分
  - 通过 `outline_confidence` 字段（`high`/`medium`/`low`）暴露质量等级
- **XLSX 确定性排序**：sheet 按命名前缀数字自然排序（`01_Intro` 在 `10_Appendix` 前），
  无前缀数字的 sheet 按字典序追加在后面
- **`ExtractionMeta.outline_confidence` 新字段**：三档（`high` / `medium` / `low`），
  下游消费者（LLM-Wiki 层、人工 review 流程）可据此分流处理

### 扩展

- `outline_source` 枚举新增 `heading_inferred` / `pptx_section` 两个值
- `PdfDoclingAdapter.version` → `0.2`；`PptxAdapter.version` → `0.2`

### 破坏性变更（仅影响缓存）

- 由于 index 树结构变化，`ExtractionResult.content_sha256()` 哈希结果会变；
  现有 `kb/<doc>/manifest.sqlite` 中的旧条目会被视为"已变更"，首次运行
  `kb extract` 会全量重新提取所有源文档。这是有意为之 — 老的扁平 index
  本身就是 PageIndex 设计的债务清理对象。
- `meta.json` schema 增加 `outline_confidence`；老的 `meta.json` 仍可读
  （dataclass 提供 `"high"` 默认值），但不建议混用。

### 测试

- 新增 5 个测试文件 / 共 15 个测试：`test_xlsx_sort.py`、`test_pptx_sections.py`、
  `test_pdf_tree.py`、`test_pdf_heading_inference.py`、`test_outline_confidence.py`
- 总用例数：160 → 177（+15 sp2 + 2 baseline migrations）

## [0.1.0] — 2026-06-09

首个公开版本。完成了完整的 34 个 TDD 任务，共 160 个测试用例全部通过、
ruff 静态检查 0 警告。

### 新增

- **`kb` 命令行工具**，4 个子命令：`extract` / `verify` / `manifest` / `adapters`,
  以及全局 `--version`。
- **6 个文档适配器**：
  - `pdf_docling`（基于 PyMuPDF，处理 `.pdf`）
  - `docx`（python-docx，保留章节层级）
  - `xlsx`（openpyxl，逐 sheet → 表格化 Markdown）
  - `pptx`（python-pptx，每页一节）
  - `image`（Pillow，PNG / JPG，仅元数据 + 资产搬运）
  - `zip`（递归调用 orchestrator，深度上限 5 层）
- **13 条 hardness 不变量** 全部机器可验证（H1 socket 封禁、H2 无 LLM 导入、
  H3-H4 段落锚点唯一引用、H5-H7 SHA-256 / 原子写入、H8 跨次运行逐 byte 一致、
  H9 dry-run 不动磁盘、H10 异常不损坏既有产物、H11-H12 manifest 完整性、
  H13 跨平台输出一致性）。
- **Copilot CLI 技能** `skills/kb-extract/`，提供 `extract` / `verify`
  两个 shell 入口，从不绕过 CLI 直接 import 包。
- **VS Code 任务模板** `.vscode/tasks.json.example`。
- **跨平台 CI**：GitHub Actions 矩阵 `{ubuntu, windows, macos} × {py3.11, py3.12}`,
  额外含 H13 跨平台 hash 比对 job 与 100 页 PDF 性能基准 job（1.5× 回归阈值）。
- **安装脚本** `install.{ps1,sh}` / `uninstall.{ps1,sh}`,
  在 `~/.kb-extract/venv` 创建独立 venv，预下载 docling 模型。
- **Copilot CLI 插件清单** `.claude-plugin/{plugin,marketplace}.json`,
  可通过 `/plugin marketplace add XUMAX-GH/kb-extract` 一键安装。

### 已知遗留事项

- `pdf_docling` 适配器目前**仅用 PyMuPDF**，并未真正调用 docling 模型；
  仓库依赖里仍带 `docling`，留作 v1.1 接入。
- `docx` 适配器引用了 `langdetect`，未显式设置 `DetectorFactory.seed`；
  因当前 H8 测试仅覆盖 NoopAdapter，e2e 路径靠 manifest 短路命中也避开了
  这条潜在的不确定性 —— 但若未来在真实 docx 上测试 `--force`，需要修补。
- 性能基线（`tests/fixtures/perf-baseline.json` = 30 秒）非常宽松；
  待 Ubuntu CI 给出实际数字后再收紧到 2 倍左右。

### Bug 修复（v1 实现期间发现）

- **`ExtractionResult.content_sha256()`** 之前对原始 markdown 求 hash，
  但 orchestrator 写盘前会过 `serialize_markdown` 做归一化（去 BOM、
  CRLF→LF、统一末尾换行）。这导致真实适配器（docx/pdf/xlsx/pptx）
  的 verify 步骤总是失败 —— 仅靠 NoopAdapter 的 markdown 恰好已经归一化
  这一巧合，逃过了之前所有测试。修复：`content_sha256` 改为先归一化再 hash。
- **`verify._doc_dirs()`** 之前对 `kb/` 做 `rglob("main.md")`,
  会把 zip 适配器的嵌套 `kb/<zipname>/_unpacked/kb/.../main.md` 也算上，
  而这些嵌套产物的 manifest 是 per-zip 独立的，导致 verify 误报。
  修复：仅取深度为 2 的直接子目录（`kb/<doc>/main.md`）。

两个 bug 都是上线即坏，只有 e2e 测试能暴露 —— 这就是为什么花精力做
端到端验收测试是值得的。

首个公开版本。完成了完整的 34 个 TDD 任务，共 160 个测试用例全部通过、
ruff 静态检查 0 警告。

### 新增

- **`kb` 命令行工具**，4 个子命令：`extract` / `verify` / `manifest` / `adapters`，
  以及全局 `--version`。
- **6 个文档适配器**：
  - `pdf_docling`（基于 PyMuPDF，处理 `.pdf`）
  - `docx`（python-docx，保留章节层级）
  - `xlsx`（openpyxl，逐 sheet → 表格化 Markdown）
  - `pptx`（python-pptx，每页一节）
  - `image`（Pillow，PNG / JPG，仅元数据 + 资产搬运）
  - `zip`（递归调用 orchestrator，深度上限 5 层）
- **13 条 hardness 不变量** 全部机器可验证（H1 socket 封禁、H2 无 LLM 导入、
  H3-H4 段落锚点唯一引用、H5-H7 SHA-256 / 原子写入、H8 跨次运行逐 byte 一致、
  H9 dry-run 不动磁盘、H10 异常不损坏既有产物、H11-H12 manifest 完整性、
  H13 跨平台输出一致性）。
- **Copilot CLI 技能** `skills/kb-extract/`，提供 `extract` / `verify`
  两个 shell 入口，从不绕过 CLI 直接 import 包。
- **VS Code 任务模板** `.vscode/tasks.json.example`。
- **跨平台 CI**：GitHub Actions 矩阵 `{ubuntu, windows, macos} × {py3.11, py3.12}`，
  额外含 H13 跨平台 hash 比对 job 与 100 页 PDF 性能基准 job（1.5× 回归阈值）。
- **安装脚本** `install.{ps1,sh}` / `uninstall.{ps1,sh}`，
  在 `~/.kb-extract/venv` 创建独立 venv，预下载 docling 模型。
- **Copilot CLI 插件清单** `.claude-plugin/{plugin,marketplace}.json`，
  可通过 `/plugin marketplace add XUMAX-GH/kb-extract` 一键安装。

### 已知遗留事项

- `pdf_docling` 适配器目前**仅用 PyMuPDF**，并未真正调用 docling 模型；
  仓库依赖里仍带 `docling`，留作 v1.1 接入。
- `docx` 适配器引用了 `langdetect`，未显式设置 `DetectorFactory.seed`；
  因当前 H8 测试仅覆盖 NoopAdapter，e2e 路径靠 manifest 短路命中也避开了
  这条潜在的不确定性 —— 但若未来在真实 docx 上测试 `--force`，需要修补。
- 性能基线（`tests/fixtures/perf-baseline.json` = 30 秒）非常宽松；
  待 Ubuntu CI 给出实际数字后再收紧到 2 倍左右。

### Bug 修复（v1 实现期间发现）

- **`ExtractionResult.content_sha256()`** 之前对原始 markdown 求 hash，
  但 orchestrator 写盘前会过 `serialize_markdown` 做归一化（去 BOM、
  CRLF→LF、统一末尾换行）。这导致真实适配器（docx/pdf/xlsx/pptx）
  的 verify 步骤总是失败 —— 仅靠 NoopAdapter 的 markdown 恰好已经归一化
  这一巧合，逃过了之前所有测试。修复：`content_sha256` 改为先归一化再 hash。
- **`verify._doc_dirs()`** 之前对 `kb/` 做 `rglob("main.md")`，
  会把 zip 适配器的嵌套 `kb/<zipname>/_unpacked/kb/.../main.md` 也算上，
  而这些嵌套产物的 manifest 是 per-zip 独立的，导致 verify 误报。
  修复：仅取深度为 2 的直接子目录（`kb/<doc>/main.md`）。

两个 bug 都是上线即坏，只有 e2e 测试能暴露 —— 这就是为什么花精力做
端到端验收测试是值得的。
