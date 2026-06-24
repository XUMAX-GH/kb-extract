---
name: repair-serviceability
description: "Extract requirements from repairability and serviceability sections. Covers FRU (Field Replaceable Unit) definitions, internal wayfinding, liquid damage indicators, connector/FPC repair guidelines, battery replaceability, in-region repair (IRR), same-unit repair (SUR), serial number placement, and design-for-repair constraints. Use when processing PRD §3.3/§3.5 Repair, PES/ID-Spec §2.7 Repair Experience, or accessory repairability sections."
---

# Repair & Serviceability Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **repair and serviceability** chapters. These sections
define what must be repairable, how components are accessed, and repair process
constraints.

### Typical Section Patterns

| Document Type | Sections |
|---------------|----------|
| Device PRD | §3.5 Repair (FRU, wayfinding, LDI, connectors, modules) |
| Keyboard PRD | §3.3 Repairs (serial number, FRU, repair requirements) |
| PES / ID Spec | §2.7 Repair Experience |
| Accessory PRD | §4.6 Repairability Experiences, §6.5 Design for Service & Repair |

---

## Domain-Specific Rules

### RULE: BULLET-LEVEL GRANULARITY

Repair sections often use bullet-point lists where EACH bullet is an
independent verifiable constraint. Extract each bullet as a SEPARATE requirement.

Examples — each of these is its OWN requirement:
- "All screws shall utilize one screwdriver size and type for the entire device"
- "All FRU fasteners should be the same for all joints for all FRUs"
- "An indicator shall be used to show if a liquid has entered the device"
- "TDM calibration data must be stored on the TDM FRU"
- "For field repair, the TDM FRU must be self contained for all calibration"
- "Thermal modules must be sufficiently robust to enable reuse"
- "The material shall enable touch up or alternate repair process"
- "The enclosure must not have a coating that chips, peels, or flakes"
- "Edge bonding on critical ICs is allowed only if required to meet reliability"
- "ASPs must be able to replace individual components utilizing SW/FW restore"
- "When disconnecting a cable/FPC, the plug must be disconnected from..."

Do NOT merge multiple bullets into one requirement — each has an
independent pass/fail verification at build milestones.

### RULE: FRU LIFECYCLE REQUIREMENTS

FRU shelf-life and manufacturer capability requirements are separate:
- "Manufacturer must provide FRU capability for 7 years" → 1 requirement
- "Manufacturer must provide RA capability for 5 years" → 1 requirement
- "Development teams shall assess shelf-life of all FRUs" → 1 requirement

### RULE: SCREW & TOOL REQUIREMENTS

Screw specifications in repair sections have independent verification:
- "Each FRU max 2 unique screws plus device access screws" → 1 requirement
- "All FRUs require only 2 screwdriver sizes total" → 1 requirement
- "Screw differences must be obvious to end user" → 1 requirement

### RULE: INTERNAL WAYFINDING

Wayfinding requirements define design markings verified at build milestones:
- Screw labels with tool type/size, quantity, and component symbol
- QR code linked to service guide visible when TDM removed
- Each distinct wayfinding element is a separate requirement

### RULE: LIQUID DAMAGE INDICATOR

LDI requirements (visibility, success rate, placement) are requirements
even when stated as a design guideline — they have measurable criteria
("visible from outside device with >=80% success rate in field").

### RULE: BATTERY REMOVABILITY

"Battery removable with common hand tools (non-thermal) in less than N minutes"
is a requirement with both a method constraint and a time limit.

### RULE: CONNECTOR CYCLING IN REPAIR CONTEXT

"All connectors must be rated for >= N connect/disconnect cycles" is a
requirement when stated in a repair section — it defines a verification
criterion for repair durability.
