---
name: product-overview
description: "Extract requirements from product overview and introduction sections (PRD §1-2, PES §1.0). Handles Requirement Summary Tables row-by-row, filters reference document lists and SKU matrices. Also covers accessories/compatibility sections (pen attachment, dock compatibility, in-box accessories). Use when processing overview, summary, strategy, product features, or compatibility sections."
---

# Product Overview Skill

> **Status**: Defined — not yet integrated into generation pipeline  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **product overview sections** (PRD 2.x, PES 1.x).
These sections contain Requirement Summary Tables, reference document lists, and
SKU/shipping matrices.

---

## Domain Focus

### Primary Extraction Targets

- **Requirement Summary Tables** (e.g., "Table 2.1-2")
  - Densest concentration of specifications in overview sections
  - Each independent parameter/area → one Requirement
  - Correlated rows (same subsystem) → one grouped Requirement

- **Product spec overview blocks**
  - Dimension, weight, thickness statements
  - Component-level specifications listed in overview format

### Section Patterns

| Document | Section | Content |
|----------|---------|---------|
| PRD | 2.1.3 (Product Overview Summary) | Summary table with all key specs |
| PES | 1.0 (Product Overview) | Component list, assembly, weight |

---

## Domain-Specific Rules

### RULE: REQUIREMENT SUMMARY TABLE HANDLING

When encountering a Requirement Summary table (e.g. "Table 2.1-2"):

1. Walk through **EVERY** data row — do not stop at a few highlights
2. Each independent parameter/area gets its own Requirement
3. Correlated rows (same subsystem, same test setup) may be grouped

**Grouping examples**:
- "Dimension", "Weight", "Thickness" → **separate** requirements (independent measurements)
- "Touchpad" rows (PCB Area + Mylar overlay + Active area + Resolution + Digital size)
  → **ONE** requirement (all describe the same subsystem's specs)
- "Keyset Acoustics" rows → **ONE** requirement (all related acoustic measurements)
- "Retractable Hinge Force" → **ONE** requirement (initial force + extraction force together)
- The "Areas" column label helps identify grouping boundaries

**Edge-case check** (P2 completeness rule): Walk through ALL rows of the summary
table and verify each has been evaluated. Typical rows include:
Dimension, Weight, Thickness, Material/Color, Touchpad, Key Pitch, Key Travel,
Acoustics, Hinge Force, Backlight, Attach Force and others.

If ANY summary table row is skipped, it must fall under the exclusion list
(e.g., SKU, shipping, model number). Otherwise, it is a missed requirement.

### RULE: REFERENCE DOCUMENT FILTERING

Reference document tables (columns: document name + number only) are NOT requirements.

Identify by:
- Column headers like "Document Name", "Document Number", "Rev", "Description"
- No specification values, tolerances, or criteria in the table
- Section titles containing "Reference Documents" or "Industry Standards"

**Action**: Skip entirely. Do not extract any rows.

### RULE: SKU / SHIPPING EXCLUSION

The following subsections MUST be completely skipped:
- SKU Matrix
- Hardware Device Config Matrix
- Shipping Countries
- Model Number

These contain commercial/logistics data, not engineering requirements.

---

## Category Mapping

When extracting from overview sections, use these Category values:

| Content Type | Category | Function |
|---|---|---|
| Overall dimensions | Dimension | Physical Specification |
| Weight specs | Weight | Physical Specification |
| Thickness specs | Thickness | Physical Specification |
| Material/color specs | Materials and Colors | Physical Specification |
| Touchpad specs (grouped) | Touchpad | Input Device Specification |
| Key pitch/travel | Keyboard | Dimensional Specification |
| Acoustic specs (grouped) | Acoustics | Acoustic Performance |
| Hinge force specs | Hinge | Mechanical Specification |
| Backlight specs | Backlight | Electrical Specification |
