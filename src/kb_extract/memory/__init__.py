"""Memory layer (v0.4.0, sp5).

Cross-session persistence for user preferences + query history.
Stored in `~/.kb-extract/memory.db` (or `$KB_EXTRACT_HOME/memory.db`).
"""

from __future__ import annotations

from .store import MemoryStore, default_memory_path

__all__ = ["MemoryStore", "default_memory_path"]
