# SP-3 设计：`kb wiki requirements` - 领域归类、证据溯源的需求知识库

状态：已批准（设计，v2 - 复用 wiki 层）
日期：2026-06-24
关联：本项目升级三部曲之第三步（SP-1 脱敏层、SP-2 source.md 层已完成，分别见
`2026-06-24-redaction-privacy-design.md`、`2026-06-24-source-md-markitdown-design.md`）。
方法论移植自 `C:\Users\xumax\AI Project\CTx_Converter\generation`
（`domain_skills/` 与 `prompts/`）。

## 1. 背景与目标

`kb extract` 产出确定性、可复现、带段落锚点（`<a id="sec-NNNN"></a>`）的
`main.md` 与 `index.json`，作为**可溯源的证据来源**（evidence substrate）。
本层（SP-3）把工程文档按领域归类，由 LLM 逐段抽取"技术要求 / 规格"
（Requirement / TestItem），输出**结构化、可溯源**的需求知识库，每条都带
`EvidenceRef` 锚点，可回溯到 `main.md` 的出处。

**关键设计决定（v2）**：SP-3 不新建独立的 LLM 层，而是**构建在现有 `wiki`
层之内**。`wiki` 层是本包**唯一被允许调用 LLM 的层**（见
`tests/test_no_llm_imports.py` 的 H2 扩展：adapters 既不许 import LLM SDK，
也不许 import `kb_extract.wiki`）。复用 `wiki` 已有且经测试的基础设施：

- `wiki.providers.base.LlmClient` 协议（`chat(messages) -> str`）；
- `wiki.providers.cached.CachedLlmClient`（按 `prompt_hash` 缓存响应，给出
  **byte-reproducible 的 LLM 输出**，即本项目既定的 H15 确定性机制）与
  `MockLlmClient`（离线测试用）；
- `wiki.sections.read_section_body(kb_root, doc_id, anchor)`（按锚点取段落正文）；
- 锚点引用与 H14 校验（evidence pin 必须解析到真实 anchor）。

核心承诺：

- **证据溯源优先**：每条结果带 `EvidenceRef`=`main.md` 段落锚点，`What`
  字段为原文逐字（verbatim），不改写、不总结。
- **不污染确定性核心**：`kb extract` / `kb verify` / `kb source` 的产物与管线
  零改动；本层只读 `kb/` 产物。
- **测试离线**：测试注入 `MockLlmClient` / `CachedLlmClient`，套件不联网、
  不打 `enable_socket`；真实 GitHub Models 调用只在真实 CLI 运行时发生。

## 2. 不可触碰的承重墙（与 AGENTS.md / hardness 一致）

1. LLM 只在 `wiki` 层调用。SP-3 的 LLM 客户端
   `GitHubModelsLlmClient` 放在 `src/kb_extract/wiki/providers/github_models.py`，
   实现既有 `LlmClient` 协议。`adapters/**` 仍不许 import LLM SDK，也不许
   import `kb_extract.wiki`（`tests/test_no_llm_imports.py` 现有两条 AST
   测试覆盖，不受影响）。
2. 测试默认禁用 socket。SP-3 所有测试通过注入 `MockLlmClient` /
   `CachedLlmClient` 提供 LLM 响应，**不**打 `enable_socket`。
3. 确定性子环节（router、prompt 组合、render）的输出必须经
   `serialization.serialize_markdown(...)` 或规范化 JSON 归一化，byte-reproducible。
4. LLM 子环节的可复现由 `cached` provider（按 `prompt_hash` 缓存）保证，
   与 `kb wiki build` 一致；不引入新的 sqlite 幂等清单。
5. 不修改 `kb extract` 的 `manifest.sqlite`、`main.md`、`index.json`，不修改
   `kb verify`、`kb source`、`kb wiki build`。

## 3. 架构与模块边界

新增子包 `src/kb_extract/wiki/requirements/`（在 wiki 层之内）：

- `router.py`：**确定性**领域路由。移植 `domain_mapping.md` 为版本化关键词 /
  段号模式表，对 `index.json` 的每个叶子段落判定 domain；无匹配回退
  `base-extraction`。无 LLM。v1 只做主路由（primary），跨领域 secondary
  路由暂不实现（YAGNI）。
- `assets/`：移植的 prompt 资产（base-extraction 规则、各 domain SKILL 文本、
  P1 precision 规则、user 模板、`output_schema.json`），作为 package data。
- `prompts.py`：**确定性** prompt 组合，返回 `list[Message]`。
  system = base + domain + P1；user 模板填入该段落的 `main.md` 正文摘录
  （`read_section_body`）+ 锚点作为 evidence 块 id。
- `extractor.py`：抽取编排 `extract_requirements(project_root, llm, *, ...)`。
  逐文档、逐叶子段落：route -> compose -> `llm.chat()` -> 解析 TestItem JSON
  列表 -> 校验 schema -> 盖 `EvidenceRef`=锚点、`SourceSection`=段标题。
  一个坏段落不中断整批（记 failed、continue）。返回 `RequirementsResult`。
- `render.py`：**确定性**渲染，产出 `requirements.json` 与 `requirements.md`。

新增 provider：

- `src/kb_extract/wiki/providers/github_models.py`：`GitHubModelsLlmClient`，
  实现 `LlmClient.chat`。OpenAI 兼容 endpoint，`temperature=0`，
  model/endpoint/token 取自环境变量（`GITHUB_TOKEN`/`GITHUB_MODELS_TOKEN`、
  `KB_ENRICH_MODEL`、可选 base url）。用轻量 HTTP（标准库或已有依赖），
  不引入重型 SDK。

复用：`wiki.providers.base.LlmClient` / `Message`、
`wiki.providers.cached.CachedLlmClient` / `prompt_hash`、
`wiki.providers.mock.MockLlmClient`、`wiki.sections.read_section_body`、
`layout.kb_dir`、`find_project_root`、`serialization`。CLI 在现有
`wiki` group 下新增 `kb wiki requirements` 子命令，选项形状对齐 `kb wiki build`。

## 4. 数据流

```
kb extract  ->  kb/<doc>/main.md (anchored, redacted) + index.json
                          |
                  [SP-3 kb wiki requirements]
                          v
  index.json 叶子段落 --router(确定性)--> domain
        |                                     |
        | read_section_body(锚点) 取正文摘录   | base + domain + P1
        v                                     v
                  prompts.compose --> list[Message]
                          |
                          v
          llm.chat()  (mock / cached / GitHubModels)
                          |
                          v
        解析 + schema 校验 + 盖 EvidenceRef=锚点
                          |
              +-----------+-----------+
              v                       v
  render requirements.json     render requirements.md
   (canonical, 确定性)          (按 domain 分组, 锚点链接)
```

## 5. 输出格式

输出位置：与 `main.md` 同目录 `kb/<doc>/`，便于锚点相对链接。

### 5.1 `kb/<doc>/requirements.json`（机器可读，确定性）

TestItem 列表，schema 移植自 CTx_Converter `output_schema.json`：

```json
{
  "Category": "Mechanical",
  "Function": "Force Specification",
  "What": "<原文逐字>",
  "How": "Not explicitly defined",
  "Sample Size": "Not specified",
  "SourceDocument": "<文档名或 Not explicitly stated>",
  "SourceSection": "<段标题 / 段号>",
  "EvidenceRef": "sec-0003"
}
```

- 列表按 (`EvidenceRef` 在 main.md 中的出现顺序, 段内序号) 确定性排序。
- 经规范化 JSON（sort_keys、统一缩进、末尾换行）写盘。
- `additionalProperties: false`，缺省值用 schema 规定的占位文案
  （`Not explicitly defined` / `Not specified` / `Not explicitly stated`）。

### 5.2 `kb/<doc>/requirements.md`（人类可读，确定性）

按 domain（Category）分组的 Markdown。每条要求渲染 verbatim 的 What/How/
Sample Size，并给出回链 `[sec-0003](main.md#sec-0003)` 以溯源。经
`serialize_markdown` 归一化。

## 6. 确定性、幂等与缓存

- **确定性子环节**（router、prompt 组合、render）对同一输入 byte-reproducible。
- **LLM 子环节**的可复现沿用 wiki 既定机制：`--provider cached
  --responses-file <json>`（按 `prompt_hash` 命中），与 `kb wiki build`
  完全一致；真实 provider 用 `temperature=0` 降低抖动。
- 不引入新的 sqlite 清单。重跑时确定性子环节产物 byte-identical；LLM 子环节
  在 cached 命中下亦 byte-identical。
- 产物不进入 `kb verify` 的确定性校验集（与 wiki/ 输出一致）。

## 7. 隐私与数据外发（重要）

- 本层读取的是**已脱敏**的 `main.md`，因此 logo / 料号在 LLM 看到内容
  **之前**就已被移除；verbatim 的 What 字段天然继承脱敏结果。
- **数据外发**：使用真实 `GitHubModelsLlmClient` 时，已脱敏的工程正文**会被
  发送**到外部 GitHub Models API。这是用户在选择该 provider 时已知并接受的
  事实，将显式记录在 README 与 CLI 帮助中，使其成为可审计的知情决策。
- 离线场景（mock / cached / 无 token）不发生任何外发。

## 8. CLI

在现有 `wiki` group 下新增子命令，输入模型与 `kb wiki build` 一致：发现
`kb/<doc>/` 中同时存在 `main.md` 与 `index.json` 的目录，逐个处理；单文档失败
不影响其余。

```bash
kb wiki requirements .                              # mock provider（默认，离线）
kb wiki requirements . --provider cached \
    --responses-file resp.json                      # 可复现真实输出
kb wiki requirements . --provider github-models     # 真实调用（需 token）
kb wiki requirements . --dry-run                    # 只路由+组合 prompt，不调 LLM、不写盘
kb wiki requirements . --json                       # 结构化报告
```

- provider 选项对齐 `kb wiki build`：`mock`（默认）| `cached` | `github-models`。
- 机器可解析摘要行（英文）：`ok=.. failed=.. items=.. docs=..`。
- exit code = 1 当 `failed > 0`，否则 0。
- 调用 `_record_history` 记录历史（对齐 `kb extract` / `kb wiki build`）。
- 真实 provider 缺 token 时给出明确错误（提示设置环境变量），不静默空跑。

## 9. 领域路由（移植自 section-router / domain_mapping）

- 关键词 + 段号模式表移植为 `wiki/requirements/assets/domain_rules`
  （版本化、可扩展）。
- Layer 1 关键词/模式匹配（确定性）；Layer 3 回退 `base-extraction`。
  Layer 2（LLM 分类）在 v1 **不实现**（YAGNI；本设计已选确定性路由）。
- 用户可按文档目录与内容扩展 domain 种类（新增 domain 资产 + 关键词条目即可）。
- 已知 ~19 个 domain：product-overview、mechanical、electrical、user-experience、
  keyboard-input、cosmetics-quality、display、ports-connectivity、power-battery、
  compliance-safety、repair-serviceability、dfx-manufacturing、packaging-logistics、
  wireless-rf、audio-camera-sensors、software、thermal 等。

## 10. 错误处理

- 段落级容错：单段落 `llm.chat` 失败 / JSON 解析失败 / schema 校验失败，
  记 `failed` 并 continue，不中断整批。
- cached provider 缺响应（strict 模式）抛 `CachedResponseMissing`，由编排层
  记 failed 或按 `--record-missing` 录入待办（沿用 wiki 行为）。
- LLM 返回非法 JSON：尝试一次容错解析（剥离围栏/前后噪声）后仍失败则记 failed。
- 真实 provider 缺 token：非 dry-run 时明确报错。

## 11. 测试策略（全部离线）

- `router`：heading/段号 -> domain 的确定性单测；回退路径。
- `prompts`：golden 组合测试（system 含 base+domain+P1；user 含 evidence
  摘录+锚点）。
- `extractor`：注入 `MockLlmClient` 返回固定 TestItem JSON；测试
  happy path、坏段落不中断、schema 非法、dry-run、cached 复现。
- `render`：requirements.json 规范/排序确定；requirements.md 分组 + 锚点链接；
  byte-reproducible。
- `github_models` provider：用注入的 fake transport（不联网）验证请求组装与
  响应解析；缺 token 报错路径。
- guard：复用现有 `test_no_llm_imports.py`（确认新增代码未让 adapters import
  LLM/wiki）；新增断言 LLM SDK / `github-models` 调用仅出现在
  `wiki/providers/github_models.py`。

## 12. 版本与文档

- 版本 bump 到 0.13.0（`pyproject.toml` + `__init__.py` + `uv.lock`）。
- README 增加中文 `需求知识库（kb wiki requirements）` 小节，明确数据外发说明。
- CHANGELOG 增加 `[0.13.0]` 条目。

## 13. 范围与分解

SP-3 是一条顺序流水线（router -> prompts -> provider -> extractor ->
render -> cli -> docs），各环节强耦合、非独立子系统，故采用单一 spec ->
单一 plan（约 7-9 个 TDD 任务）。SP-3 依赖 `kb extract` 产物与现有 `wiki`
层基础设施，**不**依赖 SP-2。

## 14. v1 已知限制（非阻塞）

- `main.md` 锚点为**段落级**，故同一段落抽出的多条 TestItem 共享该段锚点
  （溯源粒度到段落，而非具体句/块）。更细的 block 级锚点为后续增强。
- 仅 P1 precision；P2/P3 由 prompt 组合层预留扩展位，后续接入。
- 仅主路由；跨领域去重为后续增强。
