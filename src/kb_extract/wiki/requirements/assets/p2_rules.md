# P2: Precision-Tuned — Variant Rules

<!-- These rules OVERRIDE or EXTEND the base rules for P2 only.
     P2 = Full P1 baseline + precision enhancements.
     Optimised from GPT-5.3 P1 batch evaluation (2026-03-25):
       P1 achieved 97.6% recall, 95% precision.
       Over-extraction: model numbers, ODM process instructions.
       Under-extraction: rare miss of summary-table rows on chunking edge.
     P2 goal: maintain ≥97% recall, push precision toward 100%.            -->


---
## ═══════ PART A: BASELINE RULES (from P1) ═══════
---


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


---
## ═══════ PART B: PRECISION ENHANCEMENTS (P2-only) ═══════
---


## RULE: STRENGTHENED EXCLUSION LIST

The following MUST NOT be extracted, even if they contain "shall" or
appear inside a requirement section:

### Product Identity / Commercial
- Model numbers, product names, SKU identifiers
  (e.g. "Model number: 2100")
- Market / country / channel / shipping information

### Business Process Instructions
- Statements that assign tasks to an organisation
  (ODM, OEM, supplier, partner, vendor)
  → "ODM must review …", "ODM will provide the SOW …"
- Audit, review, approval, or deliverable requirements aimed at
  organisational workflow — NOT at the physical product
- **Test**: If removing the named organisation makes the statement
  meaningless (i.e. it describes WHAT a party must DO, not what
  the PRODUCT must BE), it is a process instruction → SKIP

### Documents & Metadata
- Reference document tables (document name + number columns only)
- Convention / terminology / glossary tables
- Page headers, footers, copyright, revision history

### Explanatory Text Without Constraint
- Pure definitions that explain a concept but impose no constraint
- Setup / background text that leads into a requirement
  (extract the requirement itself, not the lead-in)

**Precision gate**: Before including any item, ask:
> "Is this a property of the **product** that can be **measured or inspected**?"
> If the answer is "no — it describes a process, identity, or document" → SKIP.


## RULE: REQUIREMENT SUMMARY TABLE COMPLETENESS

Requirement Summary tables (e.g. "Table 2.1-2") often contain the
densest concentration of specifications. For these tables:

1. Walk through EVERY data row — do not stop at a few highlights
2. Each independent parameter/area gets its own Requirement
3. Correlated rows (same subsystem, same test setup) may be grouped
   (see grouping examples in REQUIREMENT SUMMARY TABLES above)
4. Even if a row's value appears simple (e.g. "338g +/-7g"), it is
   a standalone spec → extract it

**Edge-case check**: Summary table rows for Dimension, Weight,
Thickness, Material/Color, Touchpad, Key Pitch, Key Travel,
Acoustics, Hinge Force, Backlight, Attach Force — each typically
yields at least one Requirement.


## RULE: SPECIFICATION vs. IDENTITY DISAMBIGUATION

A specification defines a measurable physical property:
- "338g +/-7g" → YES (weight spec with tolerance)
- "Model number: 2100" → NO (product identity label)

When a "shall" statement defines a product identifier rather than
a measurable property, it is NOT a requirement. Ask:
> "Can an engineer set up a test to pass/fail this?"
> "2100" is an identifier, not a pass/fail criterion → SKIP.


## RULE: CONTEXT SCANNING

Actively scan forward and backward **within the same section**
to determine whether setup, load, and acceptance criteria
together define a single requirement.

If setup text (e.g. "place keyboard on flat surface, apply 30N…")
and pass/fail criteria (e.g. "shall not protrude more than 2.5mm")
appear in consecutive blocks, merge them into ONE Requirement
with all relevant EvidenceRef ids.


## RULE: ENHANCED ANTI-OMISSION (5 CHECKS)

Before finalising output, scan through all content once more:

1. Every numeric threshold, tolerance, force, deflection, flatness,
   stiffness, travel, activation distance, gap, step, or trigger
   condition has been evaluated as a potential Requirement
2. Every "must", "shall", "no visible", "must not" statement has
   been evaluated
3. No model number / SKU / country / commercial content is extracted
4. No ODM / OEM / supplier process instruction is extracted
5. Requirement Summary table rows have all been individually checked


## RULE: EVIDENCE REF (EXTENDED)

One Requirement may reference multiple block ids if the content
spans multiple evidence blocks. List all relevant ids.


## RULE: REJECTION JUSTIFICATION

For content that was reviewed but NOT extracted as a Requirement,
output a short justification entry:

```
{ "EvidenceRef": "pN_bN", "Rejected": "reason" }
```

Append these after the main Requirement array inside a wrapper:
```json
[
  { ... requirement 1 ... },
  { ... requirement 2 ... }
]
```

Only include rejections for blocks that a reader might expect to
be requirements (e.g. blocks with numeric values or "shall" keywords).
Do not justify obvious non-requirements (headers, page footers).


## RULE: ADDITIONAL FAILURE CONDITIONS

Output is ALSO INVALID if:
- A model number, SKU identifier, or process instruction appears as
  a Requirement
- A Requirement Summary table row containing a numeric spec is skipped
  without justification
