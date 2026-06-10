"""Per-project filesystem layout helpers. See spec §2.2, §2.3, §5.2.

v0.5.0: optional ``output_dir`` parameter lets callers redirect kb/ and wiki/
to an arbitrary directory while still computing per-document relative paths
against the original ``project_root``. When omitted, behavior is unchanged
(artifacts go under ``project_root``).
"""

from __future__ import annotations

from pathlib import Path


def artifacts_root(project_root: Path, output_dir: Path | None = None) -> Path:
    """Resolve where kb/ and wiki/ should live.

    When ``output_dir`` is None, artifacts live alongside the source files
    (legacy behavior). When provided, artifacts live under ``output_dir``.
    """
    return Path(output_dir).resolve() if output_dir is not None else Path(project_root).resolve()


def kb_dir(project_root: Path, output_dir: Path | None = None) -> Path:
    """Path of the ``kb/`` artifact directory."""
    return artifacts_root(project_root, output_dir) / "kb"


def wiki_dir(project_root: Path, output_dir: Path | None = None) -> Path:
    """Path of the ``wiki/`` artifact directory."""
    return artifacts_root(project_root, output_dir) / "wiki"


def target_dir(project_root: Path, src: Path, output_dir: Path | None = None) -> Path:
    """Return the per-document output directory for `src`.

    Example with ``output_dir=None``:
      project=/P, src=/P/sub/doc.pdf -> /P/kb/sub/doc

    Example with ``output_dir=/O``:
      project=/P, src=/P/sub/doc.pdf -> /O/kb/sub/doc

    The relative path is always computed against ``project_root`` so that
    nested sources keep their hierarchy under ``<output>/kb/`` even when
    artifacts are redirected.
    """
    project_root_resolved = Path(project_root).resolve()
    src = Path(src).resolve()
    try:
        rel = src.relative_to(project_root_resolved)
    except ValueError as e:
        raise ValueError(
            f"source {src} is not inside project root {project_root_resolved}"
        ) from e
    stem_parts = [*list(rel.parts[:-1]), rel.stem]
    return kb_dir(project_root, output_dir) / Path(*stem_parts)


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
