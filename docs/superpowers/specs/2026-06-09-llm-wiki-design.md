# 设计：LLM-Wiki 层（v0.3.0，sp3）

## 目标

在 `kb-extract` 产出的确定性 KB 之上，构建一层 **Karpathy LLM-Wiki 风格**
的二级知识网。要求：

- 所有 wiki 文档中的事实必须 **可追溯到 KB 的具体段落锚点**（evidence pin）
- 与抽取层"绝不调 LLM"的硬约束保持一致：**只有 wiki 层可以调 LLM**
- wiki 层调用 LLM 也必须 **可复现**：给定相同 KB + 相同 provider + 相同 seed，
  产物 byte 一致
- LLM provider 必须可插拔（OpenAI / Anthropic / Ollama / Mock），并默认走 Mock，
  让 CI 在零密钥下也能跑

## 非目标（v0.3.0 不做）

- 跨项目（多个 kb/）的 wiki 聚合
- wiki 自动 backlink 图谱可视化
- 增量 wiki 更新（这次先做 full rebuild）
- 真实 LLM provider 的 prompt 工程细化（先给 60 分 baseline）

## 架构

```
<project>/kb/                      ← 已有的确定性 KB（v0.2 sp2 产物）
       │
       ▼
  kb wiki build <project>          ← 新的 CLI 子命令组
       │
       ▼
  TopicDiscovery                   ← 纯算法（无 LLM）：从 index.json 聚类
       │  topics: list[Topic]
       ▼
  WikiBuilder                      ← 调 LLM，但每段都附 evidence pin
       │  for topic in topics:
       │    LlmClient.chat(prompt + evidence sections)
       │    -> markdown with [^ev-N] footnotes
       ▼
  EvidenceResolver                 ← 校验：每个 [^ev-N] 都解析到真实 anchor
       │
       ▼
  <project>/wiki/<topic-slug>.md   ← 输出
  <project>/wiki/index.json        ← topic 列表 + evidence 反查表
```

## 组件

### 1. `src/kb_extract/wiki/providers/`

```
base.py          LlmClient Protocol: chat(messages: list[Message]) -> str
mock.py          MockLlmClient: 给定 seed + input hash 输出确定性内容
openai.py        gated by KB_EXTRACT_LLM_PROVIDER=openai
anthropic.py     gated by KB_EXTRACT_LLM_PROVIDER=anthropic
ollama.py        gated by KB_EXTRACT_LLM_PROVIDER=ollama
```

- `Message` 是 `{"role": "system|user|assistant", "content": str}` 的 dict
- Mock 实现：`sha256(seed + json(messages))` 作为伪随机源，从一个固定的
  evidence-rich 模板池里选段，并自动在每段后插入 `[^ev-N]` —— 这样 wiki 流水线
  的所有 N>0 路径都能在 CI 里跑，且产物 byte 一致

### 2. `src/kb_extract/wiki/topics.py`

```python
@dataclass(frozen=True)
class Topic:
    slug: str           # 文件名安全的 kebab-case
    title: str
    evidence: tuple[EvidenceRef, ...]

@dataclass(frozen=True)
class EvidenceRef:
    doc_id: str         # kb/<doc> 的子目录名
    anchor: str         # main.md 里的 <a id="..."> 值
    section_title: str
    page_start: int | None
    page_end: int | None
```

聚类算法（确定性、无 LLM）：

1. 收集所有 `kb/<doc>/index.json` 的叶子节点 title
2. 把 title 拆词（whitespace + `[-_/.]` split），转小写，去停用词
3. 按词集合做 Jaccard 距离的 single-linkage 聚类（阈值 `0.6`）
4. 每个簇里的所有 section 合成一个 `Topic`，slug 取簇里频次最高的词

### 3. `src/kb_extract/wiki/writer.py`

```python
def build_topic_markdown(
    topic: Topic,
    llm: LlmClient,
    *,
    seed: int = 0,
) -> str: ...
```

调 LLM 时的 prompt 模板（写死，不让 LLM 自己决定结构）：

```
SYSTEM: You are summarising technical documentation. Every factual
        claim MUST be followed by [^ev-N] where N indexes the
        evidence sections supplied below. Do not invent claims.

USER:   Topic: {topic.title}

        Evidence sections (numbered):
        [1] {section_title_1}\n{first 2000 chars of section text}\n...
        [2] ...

        Write a 200-400 word wiki entry...
```

写盘前过 `EvidenceResolver`：把 `[^ev-1]` 之类替换成
`[^ev-1]: kb/{doc_id}/main.md#{anchor}` 的标准 markdown 脚注语法。

### 4. `src/kb_extract/wiki/orchestrator.py`

`build_wiki(project_root, *, provider, seed) -> WikiResult`
- 跑 TopicDiscovery
- foreach topic：build_topic_markdown + 写盘（atomic write，沿用 H7）
- 写 `wiki/index.json`：`{topics: [...], evidence_count: N, provider: ..., seed: ...}`

### 5. `src/kb_extract/cli.py` 扩展

新增 `wiki` 子命令组：

```
kb wiki build <project> [--provider mock] [--seed 0] [--force]
kb wiki verify <project>            ← 检查所有 [^ev-N] 能否解析
```

## 数据流（example）

1. 用户：`kb extract ./MyProject`（v0.2 产物，已存在）
2. 用户：`kb wiki build ./MyProject --provider mock --seed 0`
3. 输出：
   ```
   MyProject/wiki/
     index.json
     thermal-management.md   ← 包含 "热管理材料的选择... [^ev-1][^ev-3]"
     power-supply.md
     ...
   ```
4. `kb wiki verify ./MyProject` 退出 0 表示所有 evidence pin 都能找到对应 anchor

## Hardness 不变量（新增）

- **H14（evidence-pin-resolves）**：`wiki/<topic>.md` 中每个 `[^ev-N]` 都对应
  到 `wiki/<topic>.md` 末尾的脚注定义，且脚注 URL 必须指向真实存在的 anchor
- **H15（wiki-determinism-under-seed）**：固定 `--provider mock --seed N`,
  跨次运行的 `wiki/*.md` 与 `wiki/index.json` byte 一致
- **H16（no-extract-side-effect）**：`kb wiki build` 绝不修改 `kb/` 目录下任何
  文件；如果检测到 `kb/manifest.sqlite` 时间戳变化则报错退出

> H14/H15/H16 的真正全集（包含多源 provenance 等）会在 sp4 里继续扩。

## 测试策略

- 全部用 Mock provider，**零网络**（H1 沿用 pytest-socket）
- `tests/test_wiki_topics.py`：jaccard 聚类的边界情况
- `tests/test_wiki_mock_provider.py`：Mock 确定性
- `tests/test_wiki_writer.py`：footnote 替换 + EvidenceResolver
- `tests/test_wiki_e2e.py`：拿现有 e2e fixture，extract → wiki build → verify
- `tests/test_wiki_hardness.py`：H14/H15/H16

## 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| 真实 LLM 返回不含 `[^ev-N]` | EvidenceResolver 报错并写 `warnings.json`，CLI 退出非零 |
| Mock provider 输出过于人工，掩盖真 bug | Mock 的伪随机段池故意包含恶意 case（多余 pin / 缺失 pin / 错号） |
| 聚类把无关 section 拼在一起 | v0.3.0 接受这个，后续 sp4 用多源 provenance 改善 |
| Provider 包未装 | `kb wiki build --provider openai` 时延迟 import；ImportError 报清晰错误 |

## 版本/兼容

- v0.3.0 仅新增能力，不改 v0.2 schema
- `kb extract` 行为完全不变
- 旧版本 KB 也能直接 `kb wiki build`，只要 `index.json` 是 v0.2 格式
