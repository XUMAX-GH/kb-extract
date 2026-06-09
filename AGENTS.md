# AGENTS.md — 给 Copilot / Codex / Claude 等 AI 代理的项目指引

本项目对 AI 代理在仓库内做改动时有一些**硬性约束**。开始任何 PR / commit
之前请通读本文件。

## 项目本质

- 这是一个**确定性**文档抽取工具，核心承诺是"零幻觉、可复现、可校验"。
- 任何破坏这一点的改动（哪怕是"看起来更智能"的优化）都不能合入。

## 不可触碰的承重墙

1. **`src/kb_extract/adapters/` 任何文件都不能 `import openai / anthropic /
   transformers / langchain / llama_index / ...` 等 LLM SDK。**
   `tests/test_no_llm_imports.py` 会用 AST 扫描所有适配器源文件，
   命中即测试失败、CI 红。
2. **测试默认禁用 socket**。`pyproject.toml` 的 `addopts` 含
   `--disable-socket`。需要联网的测试必须显式打 `@pytest.mark.enable_socket`，
   并在 PR 里说明理由。
3. **写盘必须经过 `serialization.serialize_markdown(...)` 归一化**
   （strip BOM / CRLF→LF / 统一末尾换行），否则 `content_sha256()`
   会与磁盘内容失配，verify 永远红。
4. **跨平台输出必须 byte-identical**。任何"看起来差不多但 hash 不一样"
   的改动（例如把 `\n` 换成 `os.linesep`、把 `dict` 当作有序集合、
   把 `set` 当作有序集合）都会让 CI 的 H13 job 红。
5. **`langdetect` / 其他基于随机种子的库**必须先设 seed，否则就是
   H8 杀手。

## 提交规范

- 提交信息用英文（已有 38 条历史 commit 都是英文，保持一致）。
- 每个提交对应**一个 TDD 任务**：测试先写、再写实现、最后一起 commit。
- 不要在一次提交里混杂"功能"+"格式调整"+"重命名"。
- 提交说明里别用花哨 unicode（× / → / §），ruff 的 RUF001/RUF002
  会标记为 ambiguous unicode。用 `x` / `->` / `sec.` 替代。

## 测试运行

```bash
uv run pytest                  # 全部 160+ 用例
uv run pytest -m perf          # 性能基准（不在默认集里）
uv run ruff check .            # 静态检查
```

任何 PR 必须通过这两条命令，无一例外。

## 翻译 / 本地化政策

- **用户可见**的说明文档（README / SKILL.md / 安装脚本提示 / CLI 帮助文案）
  使用**简体中文**。
- **代码、测试名、commit 信息、内部 docstring** 使用**英文**。
- **CLI 机器可解析的输出**（如 `[violation]` / `verify: ok=...`）
  保持英文，方便脚本和 grep。
- **LICENSE** 是法律文件，使用原版英文 MIT 文本，不翻译。

## 不要做的事

- ❌ 不要把 `kb-extract` 包 import 进 `skills/kb-extract/scripts/` 里。
  技能层永远只调用 `kb` CLI，不直接接触 Python API。
  （`tests/test_skill_scripts.py::test_skill_scripts_never_import_kb_extract`
  会扫描脚本里的 `import kb_extract` 字串，命中即红。）
- ❌ 不要在不更新 plan.md 或 CHANGELOG.md 的情况下改 hardness 不变量。
- ❌ 不要为了"修测试"去注释或跳过测试。
- ❌ 不要直接 push 到 main 分支；走 PR。
