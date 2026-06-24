---
name: user-experience
description: "Extract requirements from user experience and interaction sections across PRD and PES/ID-Spec documents. Covers open/close/wake/auth behavior, postures, attach/detach, desktop mode, anti-slip, alignment, one-finger opening, closing behavior, and ergonomic specs. Use when processing PES §2.0-2.2, ID-Spec §2.1, or PRD User Experience chapters."
---

# User Experience Skill

> **Status**: Defined — not yet integrated into generation pipeline  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **user experience and interaction sections** covering
postures, attach/detach behaviors, desktop modes, and ergonomic specifications.

See [references/keywords.md](./references/keywords.md) for domain keyword list.

---

## Domain Focus

### Primary Extraction Targets

- Posture definitions (core postures, key usage positions)
- Attach/detach behavior and forces
- Desktop mode specifications (sits flush, alignment)
- One-finger opening behavior
- Anti-slip material behavior
- Closing alignment and behavior
- Roll-out alignment specifications
- Extension length requirements

### Section Patterns

| Document | Sections | Content |
|----------|----------|---------|
| PES | 2.1.1-2.1.2 Retractable Spine Overview | Functional intent of spine mechanism |
| PES | 2.1.3-2.1.4 Attach/Detach | Hang test, auto attach/detach behavior |
| PES | 2.1.5 Roll Out Forces | Force profile 0°-360° (cross-domain with mechanical) |
| PES | 2.1.9 Desktop Mode | Sits flush behavior |
| PES | 2.1.10 Retractable Spine Behavior | Spine mechanism behavior spec |
| PES | 2.1.11 Alignment | Spine-to-blade alignment |
| PES | 2.1.12 Extension Length | Required extension distance |
| PES | 2.2.1 Core Postures | Supported product postures |
| PES | 2.2.2-2.2.3 Key Usage Positions | Positions for keyboard use |
| PES | 2.2.4 Desktop Use | Desktop stability and behavior |
| PES | 2.2.5 Posture Transition | Transition smoothness between postures |
| PES | 2.2.6-2.2.7 One Finger Opening | Opening behavior and edge alignment |
| PES | 2.2.8 Anti-Slip PU Behavior | Anti-slip material specs |
| PES | 2.2.9 Attach & Detach Front/Rear | Directional attach/detach specs |
| PES | 2.2.10-2.2.12 Closing Alignment/Behavior | Closing mechanism specs |
| PES | 2.2.13 360° Roll Out Alignment | Full-rotation alignment |

---

## Domain-Specific Rules

### RULE: FUNCTIONAL CAPABILITY AS REQUIREMENT

User experience sections frequently describe **design-intent functional statements**
that define what the product must achieve. These ARE requirements even without numeric specs.

**Concrete examples from GRR validation** (Golden Sample items that were missed
when this rule was not applied):

- "Retractable functionality eliminates excess material for a clean, uninterrupted
  surface on the bottom of the keyboard" → EXTRACT (verifiable by inspection)
- "Blade spine profile matches keyboard bottom surface when stowed" → EXTRACT
  (verifiable by visual/dimensional inspection)
- "Attaches via magnetic connection and 5 pogo pins" → EXTRACT (verifiable by
  physical inspection — count of pins, magnetic force)
- "enables all core postures" → EXTRACT (verifiable by posture testing)
- "automatically returns to closed position" → EXTRACT (verifiable by functional test)
- "sits flush on desktop surface" → EXTRACT (verifiable by gap measurement)

**Do NOT skip** these as "explanatory text." If the statement describes a verifiable
product behavior or capability, extract it.

> **Decision rule**: Can an engineer demonstrate pass/fail for this statement?
> YES → requirement. NO → explanatory text.

### RULE: TEXT-PLUS-TABLE MERGING (UX-specific)

UX sections frequently have a **text paragraph** immediately followed by a
**specification table** where both address the same requirement.

**Example** (Roll Out Forces — Golden #7):
- Text block `p18_b1`: describes the Roll Out Force requirement context
- Table block `p18_b5`: provides the force values at specific angles

**Action**: Merge into ONE Requirement. The What field should combine the text
preamble with the table data. EvidenceRef includes both block ids: `"p18_b1, p18_b5"`.

Do NOT extract the text and table as separate requirements.

### RULE: ANGULAR VALUE PRESERVATION

UX sections frequently reference angles (0°, 180°, 360°) for:
- Posture positions
- Hinge rotation ranges
- Attach/detach directions

**CRITICAL**: Preserve ALL angular values exactly. Do not drop "360°" when splitting
or merging requirements. Include the full angular context in the What field.

### RULE: BEHAVIORAL DESCRIPTION EXTRACTION

For attach/detach and posture sections:
1. **Behavior description** ("When closing from 360°, the blade shall automatically…")
2. **Acceptance criteria** (if stated — e.g., "within 2 seconds", "without user intervention")
3. **Condition** ("from any angle between 0° and 360°")

Extract as ONE requirement including all parts. If only the behavior is stated without
explicit criteria, extract it with the note that acceptance criteria should be verified.

### RULE: VIDEO/MEDIA NOTES

PES UX sections often include notes like:
> "*Note: this video is only meant to demonstrate…*"

These media reference notes are NOT requirements. But the functional statement
immediately BEFORE the note IS a requirement — do not skip it.

### RULE: OVERVIEW SUBSECTIONS AS REQUIREMENTS

Overview subsections (e.g., "2.1.1 Overview", "2.1.2 Overview") that describe
the functional intent of a mechanism ARE requirements if they state what the
product must do or achieve. Do not skip them as "explanatory."

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Posture definitions | Posture | User Experience |
| Attach/detach behavior | Attach/Detach | User Experience |
| Desktop mode specs | Desktop Mode | User Experience |
| Opening behavior | Opening Behavior | User Experience |
| Closing behavior | Closing Behavior | User Experience |
| Alignment specs | Alignment | User Experience |
| Anti-slip specs | Anti-Slip | User Experience |
| Extension length | Extension | Physical Specification |
| Roll-out alignment | Roll-Out | User Experience |
| Spine behavior | Retractable Spine | User Experience |
