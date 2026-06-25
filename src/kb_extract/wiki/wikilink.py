"""Obsidian wikilink formatting helper.

Obsidian resolves ``[[target]]`` by note path/name. We always emit a
relative-style target (without the ``.md`` extension) and an optional display
label.
"""

from __future__ import annotations


def to_wikilink(target: str, label: str) -> str:
    """Return an Obsidian ``[[target|label]]`` (or ``[[target]]`` when equal)."""
    if target.endswith(".md"):
        target = target[: -len(".md")]
    if label == target:
        return f"[[{target}]]"
    return f"[[{target}|{label}]]"
