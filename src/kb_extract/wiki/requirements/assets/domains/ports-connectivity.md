---
name: ports-connectivity
description: "Extract requirements from port and connector sections. Covers USB-C (alt modes, PD, CTI rating, cable support), USB-A, HDMI, 3.5mm audio jack, SD card, Surface Connect, and port experience specs. Use when processing PRD §3.3 Ports, PES/ID-Spec §2.5 Port Experiences, or connector compliance subsections."
---

# Ports & Connectivity Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **port and connector** chapters in device-level PRDs
and **port experience** sections in PES/ID-Spec documents. USB-C alone can
have 13+ subsections (USB4, DisplayPort Alt Mode, Thunderbolt, Debug, UCSI, etc.).

### Typical Section Patterns

| Document Type | Sections |
|---------------|----------|
| Device PRD | §3.3 Ports (USB-C, USB-A, HDMI, audio jack, SD, compliance) |
| PES / ID Spec | §2.5 Port Experiences |
| Keyboard PRD | Spine contacts / interface (may overlap with electrical) |

---

## Domain-Specific Rules

### RULE: CONNECTOR COMPLIANCE REQUIREMENTS

Port/connector sections contain compliance and safety paragraphs that ARE
requirements even without numeric values. Extract each as ONE requirement:

- **Material restrictions**: References to H00594 (Restricted Substances),
  H00642, and material compliance mandates for connectors
- **Safety standards**: UL 1977 (Component Connectors for Data/Signal/Control/Power),
  polymeric material flammability, CTI rating requirements
- **EMI/EMC design**: "must be designed and manufactured to minimize EMI
  susceptibility and unintended emissions" — design obligation requirement
- **Cable marking**: Type-C cable marking specification compliance, behavior
  with unmarked cables (data modes not permitted)
- **Debug accessory mode**: Microsoft "Fire Hose" debug accessory support
- **Audio adapter mode**: Explicit "shall not support" statements

Category: "Ports & Connectivity" | Function: "Connector Compliance"

### RULE: AUDIO JACK ENVIRONMENTAL PERFORMANCE

"The environmental and reliability performance must meet the 3.5mm Audio Jack
Industry specification" — this IS a requirement. Extract it even though it
references an external standard without stating specific pass/fail values.

### RULE: HDMI RF DESENSE

HDMI RF desense paragraphs and design guidelines are requirements because
they define mandatory design constraints for the connector implementation.
Extract both the general statement and the specific design guideline list.

### RULE: USB-C PORT POWER GRANULARITY

USB-C power requirements should be extracted at the appropriate granularity:
- Sink PDP (input power) = 1 requirement
- Source implicit contracts (7.5W without PD) = 1 requirement
- Source explicit contracts (15W with PD) = 1 requirement
- Do NOT merge these — each has independent verification

### RULE: UNMARKED CABLE HANDLING

USB-C port behavior with unmarked cables defines safety constraints.
Extract as requirement even if phrased as informational:
- Category: "Ports & Connectivity" | Function: "USB-C Safety"
