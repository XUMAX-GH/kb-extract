"""Assemble an Obsidian vault from kb/ artifacts (pure compute, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from ..layout import kb_dir as _kb_dir
from ..serialization import serialize_markdown

_ASSETS = Path(__file__).with_name("assets")


@cache
def agents_md() -> str:
    return (_ASSETS / "AGENTS.md").read_text(encoding="utf-8")


@dataclass(slots=True)
class VaultResult:
    docs: list[str] = field(default_factory=list)

    @property
    def doc_count(self) -> int:
        return len(self.docs)


def _vault_dir(project_root: Path, output_dir: Path | None) -> Path:
    base = output_dir if output_dir is not None else project_root
    return Path(base).resolve() / "vault"


def render_index(docs: list[str]) -> str:
    lines = ["# Knowledge Base Index", ""]
    lines += [f"- [[{d}]]" for d in sorted(docs)]
    lines.append("")
    return serialize_markdown("\n".join(lines))


def build_vault(project_root: Path, *, output_dir: Path | None = None) -> VaultResult:
    kb_root = _kb_dir(project_root, output_dir)
    result = VaultResult()
    if not kb_root.is_dir():
        return result
    vault = _vault_dir(project_root, output_dir)
    (vault / "RawMD").mkdir(parents=True, exist_ok=True)
    (vault / "Graph").mkdir(parents=True, exist_ok=True)
    (vault / "Wiki").mkdir(parents=True, exist_ok=True)
    (vault / "Wiki" / ".keep").write_bytes(b"")
    for doc_dir in sorted(p for p in kb_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        main = doc_dir / "main.md"
        if not main.is_file():
            continue
        result.docs.append(doc_id)
        (vault / "RawMD" / f"{doc_id}.md").write_bytes(main.read_bytes())
        gsrc = doc_dir / "graph"
        if gsrc.is_dir():
            gdst = vault / "Graph" / doc_id
            gdst.mkdir(parents=True, exist_ok=True)
            for f in sorted(gsrc.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(gsrc)
                    (gdst / rel).parent.mkdir(parents=True, exist_ok=True)
                    if f.suffix == ".md":
                        depth = len(rel.parts) + 1
                        up = "../" * depth
                        text = f.read_text(encoding="utf-8").replace(
                            "main.md#", f"{up}RawMD/{doc_id}.md#"
                        )
                        (gdst / rel).write_bytes(text.encode("utf-8"))
                    else:
                        (gdst / rel).write_bytes(f.read_bytes())
    (vault / "AGENTS.md").write_bytes(agents_md().encode("utf-8"))
    (vault / "index.md").write_bytes(render_index(result.docs).encode("utf-8"))
    return result
