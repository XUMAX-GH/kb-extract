---
name: electrical
description: "Extract requirements from electrical specification sections. Covers key component BOM tables, motherboard/MCU selection, spine/pogo pin interface, functional block diagrams, minimum input voltage, and electrical compliance references. Use when content contains electrical component specs, interface connectors, or motherboard BOM tables."
---

# Electrical Skill

> **Status**: Active  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **electrical specification sections** covering
component selections, interface specs, sensor characteristics, and electrical compliance.

**Do NOT rely on section numbers** — match based on content: electrical, key component,
motherboard, MCU, pogo pin, spine contacts, block diagram, authentication IC.

---

## Domain Focus

### Primary Extraction Targets

- Key component / BOM tables (MCU, sensor, controller part numbers)
- Functional block diagrams
- Spine / pogo pin interface specifications
- Minimum input voltage requirements
- Hall sensor specifications (trigger distance, sensitivity)
- Magnet strength (mT at specific distance)
- Closure/wake magnet force and behavior
- Electrical reference documents

### Content Patterns (match on these, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| Key components | MCU, NXP, authentication IC, touch controller, accelerometer |
| Interface specs | pogo pin, spine contacts, UART, 5-pin interface |
| Block diagrams | functional block diagram, system diagram |
| Minimum voltage | deliver at least X V at Y A |
| Sensors | hall sensor, trigger, mT, gauss |

---

## Domain-Specific Rules

### RULE: SENSOR SPECIFICATION EXTRACTION

Sensor specs typically define:
- **Measurement parameter** (e.g., magnetic field strength in mT)
- **Measurement condition** (e.g., "at 2mm distance from sensor surface")
- **Threshold** (e.g., "minimum 5mT for reliable wake trigger")

All related blocks form ONE requirement if they share the same sensor/measurement.

### RULE: UNITS PRESERVATION

Electrical/magnetic units must be preserved exactly:
- mT (millitesla) — magnetic field strength
- V, mV — voltage
- A, mA, μA — current
- Ω, kΩ — resistance
- mm — trigger/clearance distance
- gf, N — magnet attachment force

Do NOT convert units or add unit annotations not present in the source.

### RULE: TRIGGER CONDITION EXTRACTION

Wake/sleep/trigger conditions often combine:
1. **Physical condition** (e.g., "lid closed", "blade attached")
2. **Sensor reading** (e.g., "field strength ≥ 5mT")
3. **System behavior** (e.g., "system enters S3 sleep state")

If the source defines these together, extract as ONE requirement.
If only the physical measurement threshold is defined (no system behavior), extract only that.

### RULE: CROSS-DOMAIN AWARENESS

Some electrical-magnetic specs overlap with mechanical:
- **Closure Magnet Force** (PRD 3.2.11) — involves both force measurement (mechanical) and magnet properties (electrical)
- Extract the FULL spec including both aspects
- Let the Category/Function reflect the primary aspect (magnetic/electrical)

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Key component selection | Electrical | Component Specification |
| Hall sensor trigger | Electrical | Sensor Specification |
| Magnet field strength | Electrical | Magnet Specification |
| Closure magnet force | Electrical | Magnet Specification |
| Wake/sleep trigger | Electrical | Sensor Specification |
| Power consumption | Interface with the Host | Subsystem Power Draw |
| Spine contacts | Interface with the Host | Mechanical/Electrical Specification |
| Max current draw | Interface with the Host | Power Specification |
| Host authentication | Interface with the Host | Authentication Specification |

---

## RULE: KEY COMPONENT TABLE EXTRACTION

Key Component / Functional Block Diagram tables list the chip and module
selections for the product. Each row defines a component category and the
selected part number, which engineers must verify against the BOM at
EV/DV/PV milestones.

Extract EACH component row as a SEPARATE requirement:
- Category: "Electrical"
- Function: the component category name (e.g. "MCU/KIP", "Authentication")
- What: "[Table X.X: Key Components] <Component Category> <Manufacturer> <Part Number> (<key specs>)"

Example inputs (table rows):
```
| Component | Selection |
| MCU/KIP | NXP Kinetis K22 (MK22FN512VFX12) |
| MCU Features | 96MHz, 512KB single-bank FLASH, 128KB RAM |
| Authentication | NXP A7101CWUK |
| Trackpad touch controller | Synaptics S9101 or Elan 3744M |
| Wireless Pen Charging (WLC) NFC | NXP PN7362AUEV |
| Backlight Controller | Richtek RT4531WSC or AWINIC AW9963CSR |
| Accelerometer | Bosch BMA253 (12bit, tri-axial, 140µg/√Hz noise) |
| Flash (Telemetry/Logging) | Winbond W25Q40EWUXIE (4Mbit) |
```

These are NOT "model number identity exclusions" — they define hardware
selections that must match the approved BOM. Extracting them allows
verification that the correct components are populated on the PCBA.
