"""Source-file discovery walker. Spec §5.2."""

from __future__ import annotations

from pathlib import Path

_ALWAYS_SKIP_DIRS = {"kb", ".git", "__pycache__", ".venv", "venv", "node_modules"}


def _load_gitignore_patterns(root: Path) -> set[str]:
    gi = root / ".gitignore"
    if not gi.exists():
        return set()
    patterns: set[str] = set()
    for line in gi.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # v1 supports literal file/dir names only (no globs); full gitignore
        # semantics deferred to a future revision.
        patterns.add(line.rstrip("/"))
    return patterns


def _is_skippable(path: Path, project_root: Path, gitignored: set[str]) -> bool:
    rel = path.relative_to(project_root)
    parts = rel.parts
    if any(p in _ALWAYS_SKIP_DIRS for p in parts):
        return True
    if any(p.endswith(".tmp") for p in parts):
        return True
    for part in parts:
        if part in gitignored:
            return True
    return rel.name in gitignored


def discover_sources(path: Path) -> list[Path]:
    """Return a sorted list of source files under `path`.

    - `path` is a file: returns `[path.resolve()]`.
    - `path` is a directory: walks recursively, applying skip rules.
    """
    path = path.resolve()
    if path.is_file():
        return [path]
    gitignored = _load_gitignore_patterns(path)
    out: list[Path] = []
    for p in sorted(path.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        if _is_skippable(p, path, gitignored):
            continue
        out.append(p.resolve())
    return out
