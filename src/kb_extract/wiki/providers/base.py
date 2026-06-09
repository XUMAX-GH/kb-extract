"""LLM provider protocol (wiki 层用)。

Adapters 层永远不会 import 这里：H2 不变量按 import 路径检查，
`src/kb_extract/adapters/**` 不允许出现 `from ..wiki ...`。
"""

from __future__ import annotations

from typing import Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LlmClient(Protocol):
    """协议：所有 wiki provider 必须实现。

    `chat` 是无状态的 — 每次都把完整 messages 列表传进去，不要在 client 内部
    维护 conversation history（这是为了 H15 确定性：同 messages 同输出）。
    """

    name: str

    def chat(self, messages: list[Message]) -> str: ...
