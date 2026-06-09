"""Per-project filesystem layout helpers. See spec §2.2, §2.3, §5.2."""

from __future__ import annotations

from pathlib import Path


def target_dir(project_root: Path, src: Path) -> Path:
    """Return the per-document output directory for `src` within `project_root`.

    Example: project=/P, src=/P/sub/doc.pdf -> /P/kb/sub/doc
    """
    project_root = project_root.resolve()
    src = src.resolve()
    try:
        rel = src.relative_to(project_root)
    except ValueError as e:
        raise ValueError(
            f"source {src} is not inside project root {project_root}"
        ) from e
    stem_parts = [*list(rel.parts[:-1]), rel.stem]
    return project_root / "kb" / Path(*stem_parts)


def find_project_root(path: Path) -> Path:
    """Find the project root for a given path.

    Rules (spec §5.2):
    - If `path` is a directory, that directory is the project root.
    - If `path` is a file, walk up looking for an ancestor containing `kb/`;
      return it. If none found, return the file's immediate parent.
    """
    path = path.resolve()
    if path.is_dir():
        return path
    for parent in path.parents:
        if (parent / "kb").is_dir():
            return parent
    return path.parent
