# RAG 友好的确定性分块导出（`kb chunk`）设计稿

- 日期：2026-06-24
- 目标版本：`v0.11.0`
- 作者：XUMAX-GH（与 Copilot 协同设计）
- 状态：待批准

## 1. 目标与背景

`kb-extract` 已经把异构文档抽成**确定性**、**段落级可追溯**的 Markdown
知识库（`kb/<doc>/main.md` + `index.json` + `meta.json`），每个段落都带
不可见的 `<a id="...">` 锚点。

下游若要做 RAG / 检索增强的 agent（例如正在准备 demo 的 part-reuse agent），
需要把 `main.md` 切成**检索粒度**的 chunk。但通用分块器有两个老问题：

1. **割裂可追溯性**：在段落中间切开，chunk 无法精确回指到"某文档某页某段"。
2. **不可复现**：同一份 `main.md` 切两次得到不同结果，无法做去重 / 审计 /
   稳定的 embedding 缓存。

本子项目新增一条**纯后处理**命令 `kb chunk`：只读已抽好的 `kb/` 产物，
不重新抽取、不调用 LLM、不联网，把 `main.md` 切成**逐 byte 可复现**、
**每个 chunk 都精确回指锚点**的检索单元。

## 2. 范围

### 范围内（必须做）

- 新增纯函数模块 `src/kb_extract/chunking.py`（**不在** `adapters/` 下，
  但仍不 `import` 任何 LLM SDK，不联网）。
- 新增 `Chunk` 数据契约（`contracts.py`，`frozen=True, slots=True`）。
- 新增确定性序列化 `serialize_chunks_jsonl()`（`serialization.py`）。
- 新增 Click 命令 `kb chunk`（挂在 `main` group 下，与 `extract` / `verify` 同级）。
- TDD 测试 `tests/test_chunking.py` + 一个小型 golden fixture。

### 范围外（保持现状 / YAGNI）

- ❌ 不做 embedding / 向量库 / 相似度检索。
- ❌ 不引入基于模型的 tokenizer（`tiktoken` 等会触发下载 / 联网，违反 H1）。
- ❌ 不做语义分块、不做带 overlap 的滑窗（默认 `overlap=0`；预留参数但本期不实现）。
- ❌ 不改抽取阶段任何行为，不动 `adapters/`。

## 3. 数据模型

### 3.1 新增 `Chunk`（`contracts.py`）

```python
@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str            # 形如 "<doc_stem>#0001"，文档内顺序、确定性
    source_path: str         # 来自 meta.json 的 source_path
    source_sha256: str       # 来自 meta.json，绑定到具体源文件版本
    text: str                # chunk 正文（若干完整段落拼接，含锚点）
    anchors: tuple[str, ...] # 本 chunk 覆盖的所有 <a id> 锚点，按出现顺序
    section_path: tuple[str, ...]  # 从 root 到该 chunk 所属 section 的标题路径
    page_start: int
    page_end: int
    language: str
    char_count: int          # len(text)，确定性预算依据
    oversized: bool = False  # True 表示单段超预算、被迫单独成块
```

修改契约属于 breaking change，需按 §contracts 约定升 minor（新增字段 / 新类型，
不破坏现有 v1 公共 API）。

## 4. 分块算法（确定性、零幻觉）

输入：某文档目录下的 `main.md` 文本、`index.json` 解析出的 `SectionNode` 树、
`meta.json` 的 `ExtractionMeta`；参数 `max_chars`（默认 `1200`）。

1. 解析 `main.md`，建立 `anchor -> 段落文本` 的有序映射。段落以空行分隔，
   每个段落的归属锚点取该段落内（或紧邻其前）的 `<a id="...">`。
2. 按**阅读顺序**遍历 `index` 的叶子节点（树本身已是确定性有序）。
3. 对每个叶子 section，取它覆盖的连续段落，贪心地把**整段**塞进当前 chunk，
   直到再加下一段会超过 `max_chars` 就 emit 当前 chunk。
4. **绝不在段落中间切开**。若单个段落本身就超过 `max_chars`，它单独成块，
   置 `oversized=True`，并经 `warnings_registry` 记一条 `oversized_chunk`。
5. 每个 chunk 记录：顺序 `chunk_id`、`section_path`（root→leaf 标题）、
   `anchors`、`page_start/end`、`language`、`char_count`。页码与语言不在段落级
   维护，而是取自该 chunk 所覆盖叶子 `SectionNode` 的 `page_start` / `page_end`
   / `language`（跨多个叶子时取最小 `page_start` 与最大 `page_end`）。

阅读顺序 + 整段打包 + 固定 `max_chars` 共同保证：同一份 `main.md`、
同一参数，跨平台、跨次运行得到**完全一致**的 chunk 序列。

## 5. 输出格式与落盘

- 每个文档目录写出 `kb/<doc>/chunks.jsonl`：每行一个 JSON 对象（一个 `Chunk`），
  字段 `sort_keys=True`、`ensure_ascii=False`，**行内紧凑**（`separators=(",", ":")`），
  行间以单个 `\n` 分隔，文件以单个 `\n` 收尾。
- 整份文本在写盘前经 `serialize_markdown` 同源的归一化逻辑（strip BOM /
  CRLF->LF / 末尾单换行），保证 `content` 与磁盘 byte 一致。
- 不使用 `os.linesep`，不依赖 `dict` / `set` 的遍历顺序作为有序集合。

> 选择 JSONL 而非单个大 JSON：便于流式消费、逐行 grep、增量 append；
> 且逐行确定性更易做 golden 比对。

## 6. CLI

```
kb chunk [PATH] [--max-chars N] [--output-dir DIR] [--json]
```

- `PATH`：某个 `kb/<doc>/` 目录，或项目根（缺省）。缺省时遍历 `kb/` 下所有
  已抽取文档，逐个写 `chunks.jsonl`。
- `--max-chars`：默认 `1200`。
- `--output-dir`：沿用现有 `-o/--output-dir` 语义重定向 `kb/`。
- `--json`：把汇总（每文档 chunk 数、oversized 数、总字符数）以 JSON 打到 stdout，
  机器可解析；非 `--json` 时打人类可读摘要。机器输出文案保持英文。

## 7. 错误处理

- 缺 `main.md` / `index.json`：用 `errors.py` 既有风格抛清晰错误并非零退出。
- `index.json` 锚点在 `main.md` 中找不到：记 `warnings_registry` 警告，跳过该锚点。
- 单段超预算：`oversized_chunk` 警告 + `oversized=True`，仍然 emit（不静默丢数据）。

## 8. 不变量自检

| 不变量 | 如何满足 |
|---|---|
| H1 禁网络 | 纯本地、char 预算，不下载任何模型；测试不需 `enable_socket` |
| H2 adapters 不 import LLM | 新模块在 `chunking.py`，不在 `adapters/`；且本身不 import LLM SDK |
| H3/H4 锚点 | 每个 chunk 只引用 `main.md` 中已存在的锚点；测试断言每个锚点被引用且仅一次 |
| H8 随机种子 | 算法无随机性，不调用 `langdetect`（语言取自 `index` 节点） |
| H13 跨平台 byte-identical | 确定性顺序 + 归一化写盘 + `\n`，golden 测试比对 |

## 9. 测试（TDD）

`tests/test_chunking.py`（默认集，禁 socket）：

1. **确定性**：同一输入两次 `serialize_chunks_jsonl` 得到 byte-identical 结果。
2. **段落不被切开**：每个 chunk 的 `text` 由若干完整段落拼成，无半截段落。
3. **锚点保真**：所有 chunk 的 `anchors` 并集等于 `main.md` 锚点全集，且每个
   锚点恰好出现在一个 chunk 中。
4. **预算遵守**：除 `oversized` 外，每个 chunk `char_count <= max_chars`。
5. **section_path 正确**：chunk 的 `section_path` 与其锚点在 `index` 树中的祖先链一致。
6. **golden fixture**：一个小型 `main.md` + `index.json` 切出已知 `chunks.jsonl`。
7. **跨平台 LF**：输出不含 `\r`。

## 10. 文档与发版

- README 增补 `kb chunk` 用法（简体中文，用户可见）。
- CHANGELOG 新增 `[0.11.0]` 段落，记录 Added。
- 每个 TDD 任务一个英文 commit：测试先行、再实现、一起提交。
