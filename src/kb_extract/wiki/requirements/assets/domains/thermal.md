---
name: thermal
description: "Extract requirements from thermal specification sections. Covers system thermal capacity, SoC cooling (sustained/burst), storage cooling, skin/touch temperature limits, fan noise requirements, and thermal design constraints. Use when processing PRD §3.4 Thermal, PES/ID-Spec §2.6 Thermal Experience, or Kabini thermal sections."
---

# Thermal Skill (Placeholder)

> **Status**: Placeholder — to be developed when thermal spec documents are processed  
> **Inherits**: `base-extraction`

## Overview

Reserved for extracting requirements from **thermal specification sections** covering
temperature limits, thermal dissipation, and environmental operating conditions.

---

## Domain Focus (Planned)

### Expected Extraction Targets

- Operating temperature range
- Storage temperature range
- Skin temperature limits (user-facing surfaces)
- Thermal dissipation requirements (TDP)
- Thermal resistance specifications
- Environmental test conditions (thermal cycling, humidity)

### Expected Section Patterns

| Document | Sections | Content |
|----------|----------|---------|
| Thermal Spec | TBD | Temperature limits, dissipation specs |
| Environmental Spec | TBD | Thermal cycling, humidity requirements |

---

## Domain-Specific Rules

*To be defined based on actual thermal specification documents.*

### Anticipated Rules

- Temperature range extraction with condition context
- Thermal cycling test spec merging (setup + conditions + criteria = ONE requirement)
- Surface temperature limit extraction with measurement location

---

## Category Mapping (Draft)

| Content Type | Category | Function |
|---|---|---|
| Operating temperature | Thermal | Environmental Specification |
| Storage temperature | Thermal | Environmental Specification |
| Skin temperature limit | Thermal | Safety Specification |
| Thermal dissipation | Thermal | Power Specification |
| Thermal cycling test | Thermal | Reliability Specification |
