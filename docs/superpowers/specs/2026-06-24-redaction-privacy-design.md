# 确定性脱敏 / 隐私层（`redaction.toml`）设计稿

- 日期：2026-06-24
- 目标版本：`v0.11.0`
- 子项目：SP-1（隐私脱敏层），属于"工程文档知识库升级"三段式分解的第一段
- 作者：XUMAX-GH（与 Copilot 协同设计）
- 状态：待批准

## 0. 背景：三段式分解

本次升级把 kb-extract 从"确定性抽取核心"扩展为"抽取 + 富化（enrichment）"
两层架构。整体拆成三个相互独立、各自走 spec -> plan -> implement 的子项目：

- **SP-1（本稿）确定性脱敏层**：正则脱敏料号 + 按 hash/文件名隐藏 logo 图片。
  纯确定性、逐 byte 可复现，符合核心硬度承诺；是下游一切产物的"干净证据底座"。
- **SP-2 markitdown 源文件生成器**：上层模块，调用 markitdown MCP，
  为每份源文件生成一份人类可读的 `source.md`，与 `main.md` 并列。
- **SP-3 领域分类 + 证据可溯源的摘要知识库**：移植 CTx_Converter 的
  `domain_skills` / `domain_mapping` 路由 + prompts，用现有 wiki LLM provider
  产出"每条结论都回指 `main.md` 锚点"的结构化摘要。

**硬度承诺保持不变**（AGENTS.md 承重墙）：`adapters/` 不 import LLM SDK、
测试默认禁网络、跨平台逐 byte 可复现。SP-2 / SP-3 的网络 / LLM 行为只存在于
上层富化层；SP-1 完全确定性，可以安全地放进核心写盘路径。

## 1. 目标

工程文档是核心机密资料。需要在**抽取产物落盘之前**：

1. 去除/替换形如 `M132xxxx` / `H123xxxx` 的**料号**（part number）文本。
2. 隐藏带公司 logo 的图片资产。

约束：脱敏必须**确定性**（同输入同策略 -> 逐 byte 一致输出）、**保留段落锚点**
（`<a id="...">` 不被破坏，证据可溯源不受影响）、且在**没有策略文件时完全不改变
现有行为**（现有 golden 测试不回归）。

## 2. 范围

### 范围内（必须做）

- 新增策略文件格式 `redaction.toml`（项目根，或 `--redaction-policy PATH` 指定）。
- 新增确定性模块 `src/kb_extract/redaction.py`（核心层，纯函数、不 import LLM、不联网）。
- 接入 `orchestrator.run()`：在 `_write_result_to_disk` **之前**应用脱敏。
- 新增审计侧车 `redaction.json`（只含计数，不含被脱敏的原值）。
- CLI `kb extract` 新增 `--redaction-policy` / `--no-redaction`，并自动发现根目录
  `redaction.toml`。
- TDD 测试 `tests/test_redaction.py`。

### 范围外（YAGNI / 保持现状）

- ❌ 不做基于视觉/ML 的 logo 识别（只用 sha256 / 文件名 / alt glob 的确定性匹配）。
- ❌ 不做图片内文字 OCR 脱敏（图片要么整张保留，要么整张丢弃）。
- ❌ 不做可逆 / 加密 / tokenize 还原。
- ❌ 不改 `adapters/`、不改 `index.json` 结构、不引入网络或 LLM。

## 3. 策略文件 `redaction.toml`

```toml
[redaction]
enabled = true

# 文本脱敏：按顺序应用每条正则，命中即替换
[[redaction.text]]
pattern = '(?i)\b[MH]\d{6,8}\b'      # 默认料号样式：M/H + 6~8 位数字
replacement = "[PN-REDACTED]"

# logo / 机密图片：满足任一条件即丢弃该图片
[redaction.logos]
sha256 = []                          # 资产 sha256 精确匹配（最确定）
filename_globs = ["*logo*", "*brand*"]
alt_globs = ["*logo*"]
```

字段语义：

- `enabled`：总开关。缺省或 `false` -> 脱敏完全不生效。
- `redaction.text`：有序的 `{pattern, replacement}` 列表，用 Python `re` 语义。
  默认料号正则 `(?i)\b[MH]\d{6,8}\b` 不会命中锚点 id（`sec-0001`）或资产路径
  （`assets/img_1.png`），因此天然不破坏锚点 / 图片链接结构。
- `redaction.logos`：`sha256`（与 `AssetRef.sha256` 比对）、`filename_globs`
  （与 `rel_path` 文件名 `fnmatch`）、`alt_globs`（与 `AssetRef.alt` `fnmatch`）。
  三者**或**关系，命中即整张图片丢弃。

## 4. 数据模型与模块 `redaction.py`

纯确定性、无 LLM / 无网络。

```python
@dataclass(frozen=True, slots=True)
class TextRule:
    pattern: str
    replacement: str

@dataclass(frozen=True, slots=True)
class RedactionPolicy:
    enabled: bool
    text_rules: tuple[TextRule, ...]
    logo_sha256: tuple[str, ...]
    logo_filename_globs: tuple[str, ...]
    logo_alt_globs: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class RedactionStats:
    pn_redacted: int          # 文本替换命中总数
    logos_dropped: int        # 被丢弃的图片数
```

函数：

- `load_policy(project_root: Path, override: Path | None) -> RedactionPolicy | None`
  用标准库 `tomllib` 解析。文件不存在且未显式指定 -> 返回 `None`（脱敏关闭）。
  显式指定却不存在 / TOML 非法 / 正则非法 -> 抛 `errors.py` 既有风格的清晰异常，
  异常文案点名出错的 pattern。
- `apply_to_result(result, policy) -> tuple[ExtractionResult, RedactionStats, tuple[str, ...]]`
  返回（脱敏后的新 `ExtractionResult`、统计、被丢弃的资产 `rel_path` 元组）：
  1. **文本**：对 `result.markdown` 按 `text_rules` 顺序 `re.sub`，累加命中计数。
  2. **logo**：遍历 `result.assets`（按 `rel_path` 排序，保证确定性），命中
     sha256 / filename / alt 任一规则的标记为丢弃；从 markdown 中删除对应的
     `![...](rel_path)` 行，从 `assets` 元组移除该 `AssetRef`。
  3. 重新构造 frozen `ExtractionResult`（`index` 不变）。

锚点保护：只删除图片行、只替换料号文本；`<a id="...">` 行不被触碰
（测试断言锚点集合不变、且 `index.json` 的每个锚点仍存在于脱敏后的 `main.md`）。

## 5. 接入 orchestrator

`run()` 每次运行**只加载一次** policy。对每份文档，在 `_write_result_to_disk`
之前：

1. 若 `policy is None` 或 `not policy.enabled` -> 跳过，行为与现状完全一致。
2. 否则 `apply_to_result` 得到脱敏 result + stats + dropped 路径。
3. 从 `out_dir_tmp/assets` 删除 dropped 路径对应的资产文件（adapter 在 extract
   阶段已把资产写入 tmp）。
4. `_write_result_to_disk` 写出脱敏后的 `main.md` / `index.json` / `meta.json`，
   `content_sha256()` 自然基于脱敏后的内容重算。
5. 额外写出 `redaction.json`（见 §6）。

## 6. 审计侧车 `redaction.json`

每份被脱敏的文档目录写出，确定性、只含计数，**绝不含被脱敏的原值**：

```json
{
  "logos_dropped": 3,
  "pn_redacted": 12,
  "policy_sha256": "<redaction.toml 的 sha256>"
}
```

`policy_sha256` 让审计可确认用了哪份策略，而不泄露料号 / hash 明文。
经 serialization 同源归一化（sort_keys / LF / 末尾单换行）。

## 7. CLI

`kb extract` 新增：

- `--redaction-policy PATH`：显式指定策略文件。
- `--no-redaction`：即使发现 `redaction.toml` 也强制关闭。
- 缺省：自动发现 `find_project_root()` 下的 `redaction.toml`。

机器可解析输出（保持英文）在汇总行追加：`redacted_pn=N redacted_logos=M`；
`--json` 报告新增同名字段。

## 8. 不变量自检

| 不变量 | 如何满足 |
|---|---|
| H1 禁网络 | `redaction.py` 纯本地正则 + `tomllib`，无网络 |
| H2 adapters 不 import LLM | 模块在 `redaction.py`，不在 `adapters/`；本身不 import LLM |
| H3/H4 锚点 | 只删图片行 / 替换料号文本，不动 `<a id>`；测试断言 index 锚点全部仍在 |
| H8 随机种子 | 无随机；资产按 `rel_path` 排序遍历 |
| H13 跨平台 byte-identical | 正则 + 排序 + 归一化写盘 + LF；两次运行 golden 比对 |

## 9. 测试（TDD，默认集，禁 socket）

`tests/test_redaction.py`：

1. **料号脱敏**：`M132xxxx` / `H123xxxx` 被替换为 `[PN-REDACTED]`，计数正确。
2. **锚点保留**：脱敏前后 `<a id>` 集合不变；`index.json` 每个锚点仍存在于
   脱敏后的 `main.md`（H3/H4）。
3. **logo 丢弃（sha256）**：命中的图片行从 `main.md` 消失、资产文件不落盘、
   `AssetRef` 被移除、`content_sha256` 反映移除。
4. **logo 丢弃（filename/alt glob）**：同上，验证两种 glob 路径。
5. **确定性**：同输入 + 同策略，两次运行 `main.md` 与 `redaction.json` 逐 byte 一致。
6. **关闭即零回归**：无策略文件时输出等于本特性引入前的 golden。
7. **错误处理**：TOML 非法 / 正则非法 / 显式策略文件缺失 -> 清晰非零错误，点名 pattern。
8. **侧车不泄密**：`redaction.json` 只含计数（`pn_redacted` / `logos_dropped`）
   与 `policy_sha256`，不含任何被脱敏的料号原文或 logo 资产明文。
9. **LF 保持**：脱敏输出不含 `\r`。

另：扩展 `test_no_llm_imports`（或新增等价断言）覆盖 `redaction.py` 不 import LLM SDK。

## 10. 文档与发版

- README 增补"脱敏 / 隐私"小节（简体中文，用户可见），给出 `redaction.toml` 样例。
- CHANGELOG 新增 `[0.11.0]` 的 Added 项。
- 每个 TDD 任务一个英文 commit：测试先行、再实现、一起提交。
- 提交信息避免 ambiguous unicode（用 `x` / `->` / `sec.`）。
