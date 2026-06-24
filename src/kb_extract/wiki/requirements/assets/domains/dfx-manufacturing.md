---
name: dfx-manufacturing
description: "Extract requirements from Design for Excellence (DFX) and manufacturing sections. Covers MFG targets (automation rate, yield), design for automation/fungibility/capital reuse, DFA/DFM rules, manufacturing process requirements, changeover time, and mixed-SKU manufacturing. Use when content contains DFX, DFA, DFM, automation rate, fungibility, or manufacturing targets."
---

# DFX & Manufacturing Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **DFX (Design for Excellence)** and **manufacturing**
chapters. These sections define manufacturability constraints and production
targets.

### Content Patterns (match on these, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| MFG targets | automation rate %, yield target, cycle time |
| Design for automation | automated station, manual station, Class A/B |
| Fungibility | mixed SKU, changeover time, same production line |
| Capital reuse | reconfiguration cost, less than 10%, re-use |
| DFA/DFM | design for assembly, top-down assembly, poka-yoke, 0-ohm resistor |
| Manufacturing process | MPRD, process requirements, SMT, box build |

### Note

DFX sections frequently contain **process instructions** (e.g., "ODM shall
implement automated inspection") that may fall under the exclusion list.
Apply the ODM/OEM test from `base-extraction` carefully here.
