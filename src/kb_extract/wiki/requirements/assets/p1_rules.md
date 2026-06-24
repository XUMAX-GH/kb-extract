# P1: Baseline (Production) — Variant Rules

<!-- These rules OVERRIDE or EXTEND the base rules for P1 only -->


## RULE: EXTRACTION SCOPE

Your sole objective is to extract ALL engineering requirements from a
Product Requirement Document (PRD). This includes:

- Dimensional specifications (length, width, thickness, area, resolution)
- Mechanical specifications (force, travel, stiffness, deflection, flatness)
- Gap and step tolerances
- Acoustic specifications
- Magnetic/electrical specifications (magnet strength, sensor trigger distance)
- Qualitative constraints (no visible gap, no protrusion, no activation)
- Test definitions with pass/fail criteria

Extract conservatively: if content is ambiguous between a requirement and
pure description, lean toward extraction — missing a requirement is worse
than over-extracting.


## RULE: DOCUMENT STRUCTURE AWARENESS

PRD documents typically follow this pattern:

- **Sections 1.x** (Document Overview, Conventions, Terminology)
  → Generally NOT requirements — skip unless a verifiable spec is embedded
- **Section 2.x** (Product Overview)
  → Contains reference doc tables (skip) and **Requirement Summary tables** (extract)
  → SKU Matrix and Shipping Countries sections are NOT requirements
- **Sections 3.x+** (Mechanical, Electrical, etc.)
  → Primary requirement-containing sections — extract thoroughly

Pay attention to section numbering (e.g. 3.2.1, 3.2.2) — each numbered
subsection typically defines one or more distinct requirements.


## RULE: HANDLING EXPLANATORY TEXT WITH EMBEDDED CONSTRAINTS

Some blocks contain a mix of explanation and constraint. Example:

> "The Step refers to the difference in Z-height between the mylar
> and fabric and the trackpad cannot be protruding out of the fabric."

In this case:
- The explanation alone is not a requirement
- BUT the constraint "trackpad cannot be protruding out of the fabric"
  IS a requirement
- Extract the **full block text** as the requirement — do not try to
  isolate just the constraint sentence


## RULE: REQUIREMENT SUMMARY TABLES

When encountering a Requirement Summary table (e.g. "Table 2.1-2"):

- Each distinct **area/parameter group** in the table is one Requirement
- Use row correlation to judge grouping:
  - "Dimension", "Weight", "Thickness" → separate requirements (independent measurements)
  - "Touchpad" rows listing PCB Area + Mylar overlay + Active area + Resolution + Digital size
    → ONE requirement (all describe the same subsystem's specs)
  - "Keyset Acoustics" rows → ONE requirement (all related acoustic measurements)
  - "Retractable Hinge Force" → ONE requirement (initial force + extraction force together)
- The "Areas" column label helps identify grouping boundaries


## RULE: FIGURES AND IMAGES

- Figures/images themselves are NOT requirements
- Figure captions are NOT requirements
- BUT if a text block references a figure to define a test setup or measurement
  location, the TEXT block is the requirement (not the figure)


## RULE: UNCERTAINTY HANDLING

If uncertain whether content qualifies as a Requirement:

→ Lean toward extraction — include it with the full original text
→ If truly non-requirement (pure metadata, reference list), skip and
  briefly note why


## RULE: REVIEWED-BUT-NOT-CONVERTED

If content is reviewed but not extracted as a Requirement:

→ Briefly explain why (e.g. "reference document list", "SKU matrix",
  "document metadata", "figure caption only")
