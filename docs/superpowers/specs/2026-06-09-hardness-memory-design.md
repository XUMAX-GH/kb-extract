# 设计：sp4 hardness extensions + sp5 memory layer（v0.4.0）

合并 sp4 与 sp5 到同一个 v0.4 ship —— 两者都是横切关注点，互相依赖度低，
但都依赖 v0.3 已就绪的 wiki 层。一次性发布减少 release 摩擦。

---

## sp4 — Hardness 扩展（H17 - H19）

### 目标

补齐 wiki 层的三条新硬约束，把 v0.3 在 spec 里允诺但当时只在 e2e 里抽样检查的
内容，提升为**机器可重复验证 + CI 强制**的不变量。

### 新增不变量

| 编号 | 名称 | 定义 |
|---|---|---|
| H17 | citation-graph-integrity | wiki 中每条 `[^ev-N]` 指向的 anchor 必须能在对应 main.md 中**唯一**找到（不止存在） |
| H18 | multi-source-provenance | 当一个 topic 的 evidence 来自多份源文档时，`wiki/index.json` 必须在 `evidence_origins` 字段里列出全部源 sha256 |
| H19 | wiki-mock-byte-stability | `wiki/index.json` 在 `--provider mock` 下不仅在同 seed 下 byte 一致，跨平台（Linux/macOS/Windows）也必须 byte 一致（H13 等价物，但作用于 wiki/） |

### 实现

- 扩展 `verify_wiki()`：
  - 已有：anchor 存在性 → 升级为「存在且唯一」（grep + count）
  - 新增：从 `kb/manifest.sqlite` 反查 source_sha256，与 `wiki/index.json.topics[].evidence_origins` 比对
- 扩展 `wiki/orchestrator.py`：写 `index.json` 时填 `evidence_origins`
- 扩展 CI workflow：增加一个 `wiki-cross-platform-hash` job（仿照 H13），
  在 3 个 OS 上各跑 `kb wiki build` 再 diff `wiki/index.json` 的 sha256

### 测试

- `tests/test_h17_citation_uniqueness.py`：故意造重复 anchor，断言 H17 报错
- `tests/test_h18_multi_source.py`：多文档 evidence 时 origins 字段正确
- `tests/test_h19_wiki_cross_platform.py`：本地 smoke test（CI 做真正跨 OS）

---

## sp5 — Memory layer（用户偏好与提问历史）

### 目标

把"对话记忆"封装成 `kb-extract` 自带的 sqlite 持久层，让 Copilot CLI skill
能记住用户的偏好（比如"我喜欢用 mock provider 默认 seed=42"）与提问历史
（"我之前是不是问过这个文件夹？"）。

### 非目标

- 不做向量检索（v0.5 再说）
- 不做跨用户共享
- 不做加密 —— sqlite 文件在 `~/.kb-extract/memory.db`，由 OS 文件权限保护

### 架构

```
~/.kb-extract/
  memory.db           sqlite，跨项目 / 跨次会话持久
```

表结构（`schema_version = 1`）：

```sql
CREATE TABLE preferences (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL    -- ISO 8601
);

CREATE TABLE query_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,           -- ISO 8601
  project_root TEXT NOT NULL,
  command TEXT NOT NULL,      -- 'extract' / 'wiki build' / 'wiki verify' / 'verify'
  args_json TEXT NOT NULL,    -- canonical-json 序列化
  exit_code INTEGER NOT NULL,
  summary TEXT                -- 人类可读摘要（如 "ok=3 failed=0"）
);

CREATE INDEX idx_history_project ON query_history(project_root, ts);
```

### CLI 接口

```
kb remember <key> <value>          # 设置偏好
kb remember --list                 # 列出所有偏好
kb forget <key>                    # 删除某条偏好

kb recall                          # 显示最近 20 条 query_history
kb recall --project X              # 显示某项目下的历史
kb recall --command "wiki build"   # 按命令过滤
```

### 偏好读写约定

- `default.provider`：被 `kb wiki build` 在未指定 `--provider` 时读取
- `default.seed`：同上
- `default.force`：被 `kb extract` 读取
- 任何 `--xxx` CLI flag 显式给出时，覆盖偏好

### 模块结构

```
src/kb_extract/memory/
  __init__.py
  store.py              MemoryStore 类（with __enter__/__exit__）
  cli.py                kb remember / kb recall 子命令
```

### Hook 点

`cli.py` 在每条 `extract` / `wiki build` / `verify` / `wiki verify` 命令成功
退出时调 `MemoryStore.record(...)` 写一条 history。失败也写，记录 exit_code。

### Hardness 约束

- 沿用 H1：测试期间禁 socket（已在 conftest 启用，无需新代码）
- 新增 H20：`memory.db` 写入用 `BEGIN IMMEDIATE` 事务 + WAL 模式，避免并发损坏
  - 测试：并发 5 个 `record()` 调用后 row count = 5

### 测试

- `tests/test_memory_store.py`：CRUD、迁移、并发
- `tests/test_memory_cli.py`：`kb remember` / `kb recall` CLI
- `tests/test_memory_hooks.py`：CLI 命令真的会写 history（用 monkeypatch 改 HOME）

---

## 版本/兼容

- v0.4.0：bumping 5 文件（pyproject, __init__, plugin.json×2, README）
- `~/.kb-extract/memory.db` 不存在时自动创建（首次运行任何子命令）
- 旧版本卸载后，memory.db **不**会被自动删除（保留用户数据；
  `uninstall.sh` 里加 `--purge-memory` flag 走显式删除）

## 风险

| 风险 | 缓解 |
|---|---|
| sqlite 跨平台行尾差异污染 hash 测试 | memory.db 不参与 H13 hash 测试（每个用户都不一样，本就不该一致） |
| 用户在 CI 跑 `kb extract` 时污染 memory.db | CI 把 HOME 指向 tmp 目录，跑完即弃 |
| Copilot skill 改写 memory 是否危险 | skill 仍走 CLI，不直接 import memory 模块 |
