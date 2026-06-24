---
name: mechanical
description: "Extract requirements from mechanical specification and industrial design sections. Covers force, stiffness, travel, gap/step tolerances, flatness, deflection, hinge specs, structural behavior, device size/weight, fit/finish/UX, enclosure requirements, closure magnet force, lap stability, and tolerance analysis. Use when content contains mechanical specs, forces, dimensions, tolerances, or structural behavior."
---

# Mechanical Skill

> **Status**: Active  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **mechanical specification sections** covering physical
properties, forces, dimensions, tolerances, and structural behavior.

**Do NOT rely on section numbers** — match based on content keywords: mechanical,
hinge, stiffness, flatness, deflection, force, gap, step, bounce, closure, protrusion.

---

## Domain Focus

### Primary Extraction Targets

- Force specifications (hinge force, attach/detach force, closure force, extraction/retraction)
- Stiffness & rigidity (X/Y stiffness, typing rigidity, 3-point bend)
- Dimensional tolerances (gap, step, flatness, fabric XY step)
- Travel & deflection (key travel, hinge travel, bounce, lap stability)
- Physical test criteria (protrusion limits, bend tests, dome switch activation)
- Hall magnet strength and closure magnet force
- Industrial design cosmetics references

### Content Patterns (match on these, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| Hinge / retractable mechanism | hinge force, extraction, retraction, spine |
| Stiffness | N/mm, ASTM D790, three-point bend |
| Gap/Step tolerances | mm +/-, keycap to fabric, mylar to fabric |
| Flatness | mm max, bottom side, touchpad surface |
| Force tests | N, gf, loading rate, probe size, cycles |
| Closure magnets | zero degree position, magnet force, hall sensor |
| Lap stability | lap use, typing stable, 132 degrees |

---

## Domain-Specific Rules

### RULE: FORCE SPECIFICATION EXTRACTION

Force specs typically include:
- **Load value** (e.g., 30N, 50gf)
- **Measurement condition** (e.g., "at center of blade", "applied perpendicular")
- **Pass/fail threshold** (e.g., "shall not exceed 2.5mm deflection")

All three parts (load + condition + threshold) form ONE requirement.
If they appear in separate blocks within the same subsection, **merge** them.

### RULE: TOLERANCE NOTATION

Preserve exact tolerance notation from the source:
- `±0.15mm` — symmetric tolerance
- `+0.1/-0.2mm` — asymmetric tolerance
- `0.2mm max` — upper limit
- `0.0-0.3mm` — range

Do NOT convert between notations or add missing tolerances.

### RULE: GAP/STEP SPECIFICATION HANDLING

Gap and step specs often appear in tables with:
- Location descriptors (e.g., "A-surface to B-surface")
- Condition descriptors (e.g., "at room temperature", "after cycling")
- Min/Max/Nominal values

Each **independent measurement location** with its own tolerance is a separate Requirement.
Rows sharing the same measurement location but different conditions → ONE Requirement.

### RULE: TEST SETUP + CRITERIA MERGING

Mechanical sections frequently split test definition across blocks:
1. **Setup block**: "Place keyboard on flat surface…"
2. **Load block**: "Apply 30N force at center…"
3. **Criteria block**: "Deflection shall not exceed 2.5mm"

**Context Scanning procedure** (from P2 GRR validation):
1. When you encounter a numeric specification, **scan backward** to find the
   test setup or precondition text in the preceding block(s)
2. **Scan forward** to find pass/fail criteria or sample sizes in the next block(s)
3. Limit scanning to **within the same subsection** only
4. Merge all related blocks into ONE Requirement with all relevant EvidenceRef ids
   (e.g., `"p25_b3, p25_b4, p25_b5"`)

This prevents the common failure mode where setup text is orphaned from its
criterion, producing an incomplete or untestable requirement.

### RULE: FIGURES AS CONTEXT

Mechanical sections heavily reference figures for measurement locations.
- The TEXT block referencing the figure IS the requirement
- The figure itself is NOT a requirement
- Include the figure reference in the extracted text (e.g., "as shown in Figure 3.2.1-1")

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Hinge force/travel | Hinge | Mechanical Specification |
| Stiffness values | Stiffness | Mechanical Specification |
| Flatness specs | Flatness | Mechanical Specification |
| Gap tolerances | Gap/Step | Dimensional Specification |
| Step tolerances | Gap/Step | Dimensional Specification |
| Deflection limits | Deflection | Mechanical Specification |
| Protrusion limits | Protrusion | Mechanical Specification |
| Bounce specs | Bounce | Mechanical Specification |
| Rigidity specs | Rigidity | Mechanical Specification |
| Attach/detach force | Force | Mechanical Specification |
