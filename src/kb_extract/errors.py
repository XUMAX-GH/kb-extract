"""Error types for kb-extract.

`AdapterError`: adapter-internal failure; orchestrator catches and records as failed.
`HardnessViolation`: invariant violated; propagates past orchestrator to surface
the bug to the user. Caught only at CLI boundary.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Recoverable adapter-level failure (file corrupt, encrypted, etc.).

    Orchestrator catches this and marks the source as failed in the manifest,
    then continues with the next source.
    """


class HardnessViolation(Exception):
    """A hardness invariant (H3..H11) was violated.

    Raised by `kb_extract.hardness` checkers. NOT caught by the orchestrator
    main loop — must surface to the user because it indicates an adapter bug.
    """

    def __init__(self, *, invariant: str, detail: str) -> None:
        self.invariant = invariant
        self.detail = detail
        super().__init__(f"[{invariant}] {detail}")
