"""LLM-Wiki 层（v0.3.0，sp3）。

在 `kb/` 抽取产物之上构建带 evidence pin 的 wiki 文档。
**这是包内唯一允许调 LLM 的层**：adapters/* 仍受 H2 不变量约束（无 LLM）。

公共 API:
    - `Topic`, `EvidenceRef`  — 数据类型
    - `discover_topics()`     — 纯算法聚类
    - `LlmClient`             — provider protocol
    - `build_wiki()`          — 顶层 orchestrator
"""

from __future__ import annotations

from .orchestrator import WikiResult, build_wiki
from .providers.base import LlmClient, Message
from .topics import EvidenceRef, Topic, discover_topics

__all__ = [
    "EvidenceRef",
    "LlmClient",
    "Message",
    "Topic",
    "WikiResult",
    "build_wiki",
    "discover_topics",
]
