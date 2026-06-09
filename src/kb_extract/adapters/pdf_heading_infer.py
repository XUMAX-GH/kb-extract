"""Font-based heading inference for PDFs without a TOC.

Deterministic, pure-numerical heuristic — no LLM, no network, no
randomness. Same PDF bytes always produce the same inferred outline.

H2 (no LLM)            : satisfied — only numeric clustering.
H8 (deterministic)     : satisfied — font sizes quantized to 0.5pt to absorb
                         pymupdf floating-point jitter; stable sort.
H13 (cross-platform)   : satisfied — pymupdf reports identical font metrics
                         per glyph regardless of OS.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferredHeading:
    page: int          # 1-based
    level: int         # 1..MAX_LEVELS
    title: str
    font_size_q: float  # quantized size that placed it at this level


@dataclass(frozen=True, slots=True)
class InferenceResult:
    headings: tuple[InferredHeading, ...]
    confidence: str    # "medium" | "low"


MAX_LEVELS = 4
QUANTIZE = 2  # half-point increments
BODY_BOOST = 1.10  # heading must be > body * 1.10 (or bold and >= body)
BOLD_FLAG = 1 << 4   # pymupdf span "flags" bitfield: bold = bit 4


def _q(size: float) -> float:
    """Quantize to nearest 0.5pt to absorb floating-point jitter."""
    return round(size * QUANTIZE) / QUANTIZE


def _is_bold(flags: int) -> bool:
    return bool(flags & BOLD_FLAG)


def infer_headings(doc) -> InferenceResult | None:
    """Detect headings in a pymupdf Document by font size + boldness.

    Returns None when no plausible heading at all is detected (caller should
    fall back to page-based outline).
    """
    # Pass 1: collect every span on every page.
    spans: list[tuple[int, float, int, str]] = []  # (page1, size_q, flags, text)
    # Pass 1b: weighted size histogram for body-size mode.
    size_weight: Counter[float] = Counter()
    for page_idx in range(doc.page_count):
        page = doc.load_page(page_idx)
        try:
            pdict = page.get_text("dict")
        except Exception:
            continue
        for block in pdict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    size_q = _q(float(span.get("size", 0.0)))
                    flags = int(span.get("flags", 0))
                    spans.append((page_idx + 1, size_q, flags, text))
                    size_weight[size_q] += len(text)

    if not spans or not size_weight:
        return None

    body_size = size_weight.most_common(1)[0][0]

    # Pass 2: keep heading candidates.
    candidates: list[tuple[int, float, str]] = []  # (page1, size_q, text)
    seen_keys: set[tuple[int, float, str]] = set()
    for page1, size_q, flags, text in spans:
        is_heading = (
            size_q > body_size * BODY_BOOST
            or (_is_bold(flags) and size_q >= body_size + 1.0)
        )
        if not is_heading:
            continue
        key = (page1, size_q, text)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        candidates.append((page1, size_q, text))

    if not candidates:
        return None

    # Map distinct heading sizes (descending) to outline levels 1..MAX_LEVELS.
    distinct_sizes = sorted({c[1] for c in candidates}, reverse=True)
    distinct_sizes = distinct_sizes[:MAX_LEVELS]
    size_to_level = {s: i + 1 for i, s in enumerate(distinct_sizes)}

    inferred: list[InferredHeading] = []
    for page1, size_q, text in candidates:
        if size_q not in size_to_level:
            continue
        inferred.append(InferredHeading(
            page=page1, level=size_to_level[size_q],
            title=text, font_size_q=size_q,
        ))

    if not inferred:
        return None

    # Sort by (page, level): page-order, then level (so larger heads first per page).
    inferred.sort(key=lambda h: (h.page, h.level, h.title))

    # Confidence: HIGH separation (largest size >= 2x body) AND >=2 distinct
    # levels detected => medium; otherwise low.
    top_size = distinct_sizes[0]
    confidence = (
        "medium"
        if top_size >= body_size * 2.0 and len(distinct_sizes) >= 2
        else "low"
    )

    return InferenceResult(headings=tuple(inferred), confidence=confidence)
