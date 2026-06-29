"""Deterministic atom -> module classifier (no LLM).

Resolution order: (1) atom's chapter category substring-matches a rule, (2)
entity+parameter keyword match, (3) fallback module + 待验证 flag.
"""

from __future__ import annotations

from ..atoms.schema import Atom
from .rules import ModuleRules, load_rules

PENDING = "待验证"


def classify(atom: Atom, category: str, rules: ModuleRules | None = None) -> tuple[str, bool]:
    """Return (module, pending). ``pending`` True means fallback was used."""
    r = rules or load_rules()
    cat = category.strip().lower()
    for key, module in r.category_to_module.items():
        if key in cat:
            return module, False
    hay = f"{atom.entity} {atom.parameter}".lower()
    for module, kws in r.keyword_to_module.items():
        if any(kw in hay for kw in kws):
            return module, False
    return r.fallback, True
