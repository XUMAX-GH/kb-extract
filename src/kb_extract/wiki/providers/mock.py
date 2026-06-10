"""Mock LLM provider —— 确定性、无网络，CI 默认使用。

策略：对每个 USER 消息，从一个固定的"句式模板池"里挑句子拼接。
挑选种子 = sha256(seed_int || canonical(messages))，保证同输入同输出。

输出规则：
1. 每个段落（4-6 句）后面追加 `[^ev-1]` `[^ev-2]` 等 pin，编号从 1 起
2. pin 个数 = min(段落里实际句子数, evidence 总数)
3. 末尾不附 footnote 定义 —— 那是 EvidenceResolver 的活
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable

from .base import LlmClient, Message

# 固定的句式池 —— 故意写得像 LLM 输出，但完全无 LLM。
_SENTENCES = (
    "本节内容综合多份资料整理。",
    "其设计思路在工程实践中已被多次验证。",
    "关键参数与边界条件已在原始文档中记录。",
    "实现细节遵循团队既定的硬度约束。",
    "测试覆盖率与性能基线均满足验收要求。",
    "已知限制将在后续迭代中逐步解除。",
    "该模块与相邻系统的接口契约保持稳定。",
    "异常路径在多次回归中得到了充分覆盖。",
    "升级路径不会破坏既有部署的兼容性。",
    "配置项保留了清晰的迁移说明。",
    "权限与审计字段全部按照规范填充。",
    "可观测性指标接入到了统一的监控面板。",
    "上下游服务的限流策略经过实测调优。",
    "数据一致性靠幂等键 + 事务日志双重保证。",
    "构建产物的 SHA-256 与发布记录逐 byte 对齐。",
    "灰度发布过程中未发现新增的故障类型。",
)


def _canonical_messages_bytes(messages: list[Message]) -> bytes:
    return json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _select_indices(seed_bytes: bytes, n_out: int, pool_size: int) -> list[int]:
    out: list[int] = []
    h = hashlib.sha256(seed_bytes).digest()
    cursor = 0
    while len(out) < n_out:
        if cursor + 4 > len(h):
            h = hashlib.sha256(h).digest()
            cursor = 0
        idx = int.from_bytes(h[cursor : cursor + 4], "big") % pool_size
        cursor += 4
        out.append(idx)
    return out


class MockLlmClient:
    """无网络 / 无 LLM 的确定性 client。"""

    name = "mock"

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    def chat(self, messages: list[Message]) -> str:
        # 统计 USER 消息里的 evidence 编号：扫描 "[1] " / "[2] " 之类的前缀
        user_concat = "\n".join(m["content"] for m in messages if m["role"] == "user")
        ev_count = 0
        for i in range(1, 50):
            if f"[{i}]" in user_concat:
                ev_count = i
        if ev_count == 0:
            ev_count = 1  # 至少留一个 pin，方便测试
        seed_bytes = (
            self._seed.to_bytes(8, "big", signed=False) + _canonical_messages_bytes(messages)
        )

        # 生成 2 个段落，每段 4 句
        paragraphs: list[str] = []
        sentence_indices = _select_indices(seed_bytes, n_out=8, pool_size=len(_SENTENCES))
        for p in range(2):
            chunk = sentence_indices[p * 4 : (p + 1) * 4]
            sentences = [_SENTENCES[i] for i in chunk]
            # 在段尾追加 pin
            pin_count = min(2, ev_count)
            pin_start = (p * pin_count) % ev_count + 1
            pins = "".join(
                f"[^ev-{((pin_start - 1 + k) % ev_count) + 1}]" for k in range(pin_count)
            )
            paragraphs.append("".join(sentences) + pins)
        return "\n\n".join(paragraphs)


def get_provider(name: str | None = None, *, seed: int = 0, **kwargs: object) -> LlmClient:
    """工厂：按名字返回 provider。

    `name` 默认从 KB_EXTRACT_LLM_PROVIDER 环境变量读，再 fallback 到 "mock"。
    真实 provider 用 lazy import，包未装时会给出清晰错误。

    Extra kwargs are forwarded to the chosen provider (used by "cached" for
    ``responses_path`` / ``record_missing_path`` / ``placeholder``).
    """
    if name is None:
        name = os.environ.get("KB_EXTRACT_LLM_PROVIDER", "mock")
    name = name.lower()
    if name == "mock":
        return MockLlmClient(seed=seed)
    if name == "cached":
        from .cached import CachedLlmClient

        return CachedLlmClient(**kwargs)  # type: ignore[arg-type]
    if name == "openai":
        raise NotImplementedError(
            "OpenAI provider 尚未在 v0.3.0 实现；只接好了 protocol。请使用 --provider mock 或 cached。"
        )
    if name == "anthropic":
        raise NotImplementedError(
            "Anthropic provider 尚未在 v0.3.0 实现；只接好了 protocol。请使用 --provider mock 或 cached。"
        )
    if name == "ollama":
        raise NotImplementedError(
            "Ollama provider 尚未在 v0.3.0 实现；只接好了 protocol。请使用 --provider mock 或 cached。"
        )
    raise ValueError(f"未知的 LLM provider: {name!r}（支持: mock, cached）")


def _consume(_: Iterable[object]) -> None:  # pragma: no cover - 占位，禁止误用
    pass
