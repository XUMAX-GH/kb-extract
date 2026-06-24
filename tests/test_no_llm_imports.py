"""H2: adapters must not import any LLM SDK.

Static AST scan of every file in src/kb_extract/adapters/**/*.py. New LLM
SDKs should be added to LLM_DENYLIST below as they emerge.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

LLM_DENYLIST: tuple[str, ...] = (
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "langchain_core",
    "langchain_community",
    "google.generativeai",
    "google_generativeai",
    "transformers",
    "torch.nn",  # nn implies model code; raw torch ok for docling deps
    "vllm",
    "ollama",
    "groq",
    "mistralai",
    "cohere",
    "instructor",
    "dspy",
)


def _adapter_files() -> list[Path]:
    repo = Path(__file__).resolve().parents[1]
    return sorted((repo / "src" / "kb_extract" / "adapters").rglob("*.py"))


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.add(n.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", _adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_import_any_llm_sdk(path: Path):
    if path.name == "__init__.py" and path.read_text(encoding="utf-8").strip() == "":
        pytest.skip("empty __init__")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = _imports(tree)
    forbidden = []
    for imp in imported:
        for bad in LLM_DENYLIST:
            if imp == bad or imp.startswith(bad + "."):
                forbidden.append(imp)
    assert not forbidden, (
        f"{path} imports forbidden LLM SDK(s): {forbidden}. "
        f"H2 violation. If this is a false positive, justify and update LLM_DENYLIST."
    )


def test_chat_completions_only_in_github_models():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "kb_extract"
    offenders = []
    for p in src.rglob("*.py"):
        if p.name == "github_models.py":
            continue
        if "chat/completions" in p.read_text(encoding="utf-8"):
            offenders.append(str(p.relative_to(src)))
    assert not offenders, f"raw chat/completions outside github_models.py: {offenders}"


@pytest.mark.parametrize("path", _adapter_files(), ids=lambda p: p.name)
def test_adapter_does_not_import_from_wiki_layer(path: Path):
    """H2 extension (v0.3): adapters MUST stay below the wiki layer.

    The wiki layer is the only place allowed to call LLMs. If an adapter starts
    importing from `kb_extract.wiki`, that's a cross-layer leak — fail loud.
    """
    if path.name == "__init__.py" and path.read_text(encoding="utf-8").strip() == "":
        pytest.skip("empty __init__")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("kb_extract.wiki"), (
                f"{path} imports from {mod}; adapters MUST NOT depend on wiki layer."
            )
            assert not mod.startswith("kb_extract.memory"), (
                f"{path} imports from {mod}; adapters MUST NOT depend on memory layer."
            )
            # Catch relative `from ..wiki ...` / `from ..memory ...`
            if node.level and node.module:
                parts = (node.module or "").split(".")
                assert "wiki" not in parts and "memory" not in parts, (
                    f"{path} relative-imports wiki/memory layer; adapters MUST stay below."
                )
        elif isinstance(node, ast.Import):
            for n in node.names:
                assert not n.name.startswith("kb_extract.wiki"), (
                    f"{path} imports {n.name}; adapters MUST NOT depend on wiki layer."
                )
                assert not n.name.startswith("kb_extract.memory"), (
                    f"{path} imports {n.name}; adapters MUST NOT depend on memory layer."
                )
