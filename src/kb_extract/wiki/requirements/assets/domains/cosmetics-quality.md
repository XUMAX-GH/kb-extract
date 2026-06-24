---
name: cosmetics-quality
description: "Extract requirements from cosmetic inspection and product quality sections. Covers appearance gaps/steps, material codes, logo placement, compliance markings, fabric cosmetics, and color specs. Use when processing PES 3.x quality and appearance sections."
---

# Cosmetics & Quality Skill

> **Status**: Defined — not yet integrated into generation pipeline  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **cosmetic inspection and product quality sections**
covering appearance standards, material specifications, compliance markings, and
visual quality criteria.

See [references/keywords.md](./references/keywords.md) for domain keyword list.

---

## Domain Focus

### Primary Extraction Targets

- Steps & gaps (cosmetic — appearance-level, distinct from mechanical tolerances)
- Material codes and drawing references in inspection specs
- Logo application requirements
- Regulation/compliance marking requirements
- Fabric cosmetic inspection criteria
- Internal parts visibility constraints
- Color specifications and legend

### Section Patterns

| Document | Sections | Content |
|----------|----------|---------|
| PES | 3.0.1 Steps & Gaps | Cosmetic-level gap/step appearance criteria |
| PES | 3.0.2 Lower Ledge Steps & Gaps | Ledge-specific cosmetic tolerances |
| PES | 3.0.3 Lower Ledge Hinge Termination | Hinge-to-ledge visual termination |
| PES | 3.0.4 Internal Parts Visibility | Internal component visibility constraints |
| PES | 3.0.5 Spine Fabric Cosmetics | Fabric appearance and quality |
| PES | 3.0.6 D-Cover Logo Application | Logo placement and quality |
| PES | 3.0.7 Regulation/Compliance Markings | Regulatory label requirements |
| PES | 3.0.8 Color Legend | Color specification reference |

---

## Domain-Specific Rules

### RULE: COSMETIC vs. MECHANICAL GAP/STEP

Cosmetics sections may define gap/step tolerances similar to mechanical sections,
but the focus is **visual appearance** rather than structural integrity.

Key differences:
- Cosmetic: "no visible gap under normal viewing conditions"
- Mechanical: "gap ≤ 0.3mm ± 0.1mm measured with feeler gauge"

Extract both types — Category distinguishes them:
- Cosmetic gap/step → Category: "Cosmetics"
- Mechanical gap/step → Category: "Gap/Step" (handled by mechanical skill)

### RULE: MATERIAL CODE INCLUSION

When material codes or drawing references appear as part of cosmetic/inspection specs:
- **Include them verbatim** in the extracted What field
- Material codes (e.g., "M1234567") are part of the specification
- Drawing references (e.g., "per DWG-12345 Rev C") define the acceptance criteria

**Concrete example from GRR validation** (Golden #33):
> "Clarino SRF150A (Microfiber) H006331 Rev O — No witness lines, No Bubbles"

The material code "Clarino SRF150A", part number "H006331 Rev O", and the
specific acceptance criteria ("No witness lines, No Bubbles") must ALL be
preserved in the What field. Stripping the material code makes the requirement
untraceable to the specific material specification.

Do NOT strip material codes as "metadata" — they are integral to the cosmetic spec.

### RULE: COMPLIANCE MARKING EXTRACTION

Regulation/compliance marking sections define:
- Which marks must be present (CE, FCC, UL, etc.)
- Location requirements (back cover, label area)
- Size requirements (minimum height, legibility)

Each **independent marking requirement** (different regulation) is a separate requirement.
Location + size for the same mark → ONE requirement.

### RULE: COLOR SPECIFICATION

Color legend sections may define:
- Part-specific color codes
- Acceptable color ranges
- Surface finish requirements

Extract color specs ONLY if they define verifiable criteria (specific color code,
Delta-E tolerance, gloss level). Pure reference color swatches without criteria
are NOT requirements.

### RULE: IMAGE-HEAVY SECTIONS

Cosmetics sections rely heavily on annotated images showing acceptable vs. unacceptable
appearance. For specs that depend on visual reference images:

1. **Still extract** the requirement text — it contains verifiable criteria
2. In the How field, add:
   > "User Verification Needed: referenced image/figure not parsed by LLM"
3. This flags the requirement for human review without losing the text-based spec

Do NOT skip a requirement entirely just because it references an image.

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Cosmetic gaps/steps | Cosmetics | Visual Quality |
| Material codes in specs | Cosmetics | Material Specification |
| Logo placement/quality | Logo | Visual Quality |
| Compliance markings | Compliance | Regulatory Requirement |
| Fabric appearance | Cosmetics | Visual Quality |
| Internal parts visibility | Cosmetics | Visual Quality |
| Color specifications | Color | Visual Quality |
| Surface finish | Cosmetics | Visual Quality |
