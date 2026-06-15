"""LLM-Wiki 层（v0.3.0，sp3）。

在 `kb/` 抽取产物之上构建带 evidence pin 的 wiki 文档。
**这是包内唯一允许调 LLM 的层**：adapters/* 仍受 H2 不变量约束（无 LLM）。

公共 API:
    - `Topic`, `EvidenceRef`  — 数据类型
    - `discover_topics()`     — 纯算法聚类
    - `LlmClient`             — provider protocol
    - `build_wiki()`          — 顶层 orchestrator
    - `Category`, `TaxonomyConfig` — taxonomy 配置 (v0.7.0)
    - `load_taxonomy`, `save_taxonomy` — taxonomy I/O (v0.7.0)
"""

from __future__ import annotations

from .orchestrator import WikiResult, build_wiki, build_wiki_v2
from .providers.base import LlmClient, Message
from .taxonomy import (
    Category,
    CategoryNode,
    TaxonomyConfig,
    TaxonomyConfigV2,
    generate_taxonomy_v2,
    load_taxonomy,
    load_taxonomy_v2,
    save_taxonomy,
    save_taxonomy_v2,
)
from .topics import EvidenceRef, Topic, discover_topics

__all__ = [
    "Category",
    "CategoryNode",
    "EvidenceRef",
    "LlmClient",
    "Message",
    "TaxonomyConfig",
    "TaxonomyConfigV2",
    "Topic",
    "WikiResult",
    "build_wiki",
    "build_wiki_v2",
    "discover_topics",
    "generate_taxonomy_v2",
    "load_taxonomy",
    "load_taxonomy_v2",
    "save_taxonomy",
    "save_taxonomy_v2",
]
