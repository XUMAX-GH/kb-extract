---
name: compliance-safety
description: "Extract requirements from safety, EMC/RF, environmental compliance, sustainability, quality, and reliability sections. Covers safety certifications, EMC regulatory compliance, restricted substances, EPEAT/TCO, energy efficiency, hazard analysis (HARA), critical-to-safety (CTS), responsible sourcing, and reliability test requirements. Use when processing PRD §10 Quality/Compliance, §13-18 (device PRD), or product-level qualification chapters."
---

# Compliance & Safety Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **compliance, safety, and environmental** chapters.
These sections appear in virtually every PRD type and contain certification
requirements, regulatory mandates, and environmental constraints.

### Typical Section Patterns

| Document Type | Sections |
|---------------|----------|
| Device PRD | §13 Quality, §14 Reliability, §15 Safety, §16 EMC/RF, §17 Environmental, §18 Sustainability |
| Keyboard PRD | §10 Product Quality and Compliance (consolidated) |
| Accessory PRD | §7 Requirements (regulatory, EMC, safety, environmental, reliability) |

### Note

Many compliance sections reference external standards (IEC 62368-1, FCC Part 15,
EN 55032, etc.) without stating explicit pass/fail criteria. The skill must
distinguish between **actionable requirements** (with criteria) and
**reference-only standard citations** (which are not requirements).

---

## Domain-Specific Rules

### RULE: REFERENCE DOCUMENT TABLE HANDLING

Tables that list "Microsoft Specification | Document Number" define the test
standards the product must pass. These ARE requirements — they tell engineers
which test specs to run.

Extract each such table as **ONE requirement**:
- Category: "Quality" or "Reliability" (match the section heading)
- Function: "Test Specification Reference"
- What: "[Table X.X: <Section> Reference Documents] " + full table content

### RULE: LONG COMPLIANCE PARAGRAPHS

Supplier audit, inspection, corrective action, and responsible sourcing
paragraphs often span many sentences without numeric values. These define
verifiable supplier obligations and MUST be extracted.

Extract each major paragraph or numbered clause as ONE requirement:
- Category: "Certification"
- Function: "Supplier Management" or "Records, Inspections and Audits"
- Do NOT skip paragraphs just because they lack numeric specs
- Do NOT truncate — extract the full paragraph text

### RULE: SAFETY DESIGN REQUIREMENTS

Safety sections contain both:
1. **Design constraints** ("shall not contain pinch points") → extract each as requirement
2. **Standard references** ("per UL1439") → include in the same requirement's What field

### RULE: USER MANUAL CONTENT REQUIREMENTS

"The user manual shall contain..." statements define deliverable requirements.
Each such statement is a separate requirement:
- Category: "Safety"
- Function: "User Manual Content"

### RULE: ENVIRONMENTAL / RESTRICTED SUBSTANCE REQUIREMENTS

Environmental compliance sections define analytical testing, FMD, BOM,
marking, and sample requirements. Extract each distinct requirement:
- Category: "Certification"
- Function: "Analytical Testing", "Material Declaration", "Product and Packaging Marking", etc.

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Quality test spec references | Quality | Test Specification Reference |
| Reliability test spec references | Reliability | Test Specification Reference |
| Safety design constraints | Safety | Mechanical/Electrical/Material Safety |
| User manual requirements | Safety | User Manual Content |
| EMC/RF regulatory | Certification | EMC & RF Regulatory |
| Restricted substances | Certification | Restricted Substances |
| Analytical testing | Certification | Analytical Testing |
| FMD/BOM requirements | Certification | Material Declaration |
| Marking requirements | Certification | Product and Packaging Marking |
| Supplier management | Certification | Supplier Management |
| Audit/inspection | Certification | Records, Inspections and Audits |
