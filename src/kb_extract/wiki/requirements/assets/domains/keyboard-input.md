---
name: keyboard-input
description: "Extract requirements from keyboard, keyset, touchpad, backlight, and keyboard system operation sections. Covers key pitch/travel, acoustics, backlight behavior/fading, touchpad specs/latency/power states, keyboard system operation (hinge angle states, host/cover turn-on angles, turn-on/off delays, host power states, input latency, wake events). Use when content contains keyboard, keyset, touchpad, backlight, hinge angle, turn-on/off delay, or input latency specs."
---

# Keyboard & Input Device Skill

> **Status**: Active  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **keyboard, keyset, touchpad, backlight, and keyboard
system operation** sections. This domain covers a wide range of input device specs
that appear under different section numbers in different products.

**Do NOT rely on section numbers** — different products place these sections
under §5, §6, or other chapters. Match based on content keywords only.

---

## Domain Focus

### Primary Extraction Targets

- Key pitch (horizontal, vertical)
- Key travel distance and tolerance
- Acoustic specifications (click/release sound, spectral centroid)
- Backlight specs (brightness levels, uniformity, fading behavior, events)
- Touchpad specs (active area, resolution, DPI, PCB dimensions, FTF, cycle life)
- Touchpad latency, power states, impedance, baseline capacitance
- Keyboard system operation (hinge angle states, turn-on/off angles/delays)
- Host power state interaction (blade subsystem activity vs host states)
- User input latencies (click-to-bang, blade turn-on/off timers)
- Host wake events (wake on keypress, touchpad, lid)
- Keyboard accessibility (tactile bumps, FN-lock communication)

### Content Patterns (use these for domain matching, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| Keyset specs | Key pitch, key travel, acoustic, keycap |
| Backlight | Illumination levels, uniformity, fading, PWM, brightness control |
| Touchpad | PTP, active area, FTF, snap ratio, cycle life, latency |
| Keyboard system operation | Hinge angle states (A/B/C/D/E), turn-on/off angles |
| Input latency | Click-to-bang, blade turn-on delay, blade turn-off delay |
| Host wake | Wake on keypress, wake on touchpad, wake on lid |
| Keyboard accessibility | Tactile bumps, FN-lock, narrator |

---

## Domain-Specific Rules

### RULE: ACOUSTIC SPECIFICATION GROUPING

Keyset acoustic specs often include multiple related measurements:
- Click sound level (dBA peak, A-weighted)
- Release sound level
- Spectral centroid
- Measurement standard reference (e.g., ISO 532-1)

If these rows appear in the SAME table or consecutive blocks describing the same
keyset's acoustic properties → extract as **ONE** grouped requirement.

If click and release specs have **independent** pass/fail criteria at different
locations → extract as **separate** requirements.

### RULE: TOUCHPAD SPECIFICATION GROUPING

Touchpad specs in summary tables typically include:
- PCB Area dimensions
- Mylar overlay dimensions
- Active area dimensions
- Resolution / DPI
- Digital size

These all describe the same subsystem → extract as **ONE** grouped requirement
(unless they appear in separate detailed sections with independent criteria).

### RULE: BACKLIGHT SPECIFICATIONS

Backlight specs may include:
- Default brightness state (on/off at boot)
- Brightness levels
- Uniformity requirements
- Key illumination patterns

Each **independently testable** backlight property is a separate requirement.
"Default Keyboard Backlight" (on/off state) is independent from brightness uniformity.

### RULE: KEY DIMENSION PRECISION

Key pitch and travel values are typically given with high precision:
- "19.05mm ± 0.1mm" (key pitch)
- "1.5mm ± 0.1mm" (key travel)

Preserve exact values including all decimal places and tolerance notation.

### RULE: ACOUSTIC STANDARD REFERENCES

When an acoustic spec references a measurement standard (e.g., ISO 532-1):
- Include the standard reference in the **How** field (e.g., `"Per ISO 532-1"`)
- This is one of the few cases where How is NOT "Not explicitly defined"
- If the standard defines both the measurement method AND acceptance criteria,
  note both in How (e.g., `"Per ISO 532-1 — A-weighted SPL measured at 10cm"`)
- The spec value itself (e.g., "≤ 42 dBA peak") still goes in the What field

### RULE: TYPING EXPERIENCE FUNCTIONAL SPECS

PES typing sections include qualitative requirements:
- "Stable typing experience on desk and lap"
- "No key wobble during normal typing"
- "Consistent key feel across all keys"

These are functional requirements — extract them even though they lack numeric values.

### RULE: KEYBOARD SYSTEM OPERATION — HINGE ANGLE STATES

Hinge angle state tables define device behavior at different keyboard orientations
(e.g., State A=closed, B=productivity, C=kickstand, D=slate, E=portrait).

Extract the ENTIRE state table as ONE requirement:
- Category: "Keyboard System Operation"
- Function: "Hinge Angle States"
- What: all states and their descriptions, preserving A/B/C/D/E labels

### RULE: KEYBOARD SYSTEM OPERATION — TURN-ON/OFF ANGLES

Turn-on/off angle tables define the hinge angle thresholds where keyboard
enables/disables input.

Extract the ENTIRE angle table as ONE requirement:
- Category: "Keyboard System Operation"
- Function: "Host/Cover Turn-on Angles"

### RULE: KEYBOARD SYSTEM OPERATION — HINGE STATE STABILITY

Stability tables define behavior during user events
(pounding keys, flipping open, mobile typing).

Extract as ONE requirement per table.

### RULE: KEYBOARD SYSTEM OPERATION — HOST POWER STATE INTERACTION

Tables showing blade subsystem activity under various host power states
(S0, CS/DS, S4/S5, Deep Doze) and hinge angles — extract as ONE requirement.

### RULE: INPUT LATENCY — CLICK-TO-BANG AND BLADE DELAYS

Input timing tables (click-to-bang delays, blade turn-on/off delays) define
maximum response times. Extract EACH timing table as ONE grouped requirement:
- Category: "Keyboard System Operation"

### RULE: HOST WAKE EVENTS

Tables defining which blade events wake the host (keypress, touchpad, lid)
under different power states — extract as ONE requirement.

### RULE: TOUCHPAD SPECIFICATION TABLE

Touchpad spec tables combine multiple parameters (FTF, snap ratio, cycle life,
travel, temperature, latency). Extract the full table as ONE requirement unless
individual rows have independent pass/fail criteria with different test methods.

### RULE: TOUCHPAD POWER STATE TABLE

Touchpad power state tables (Active, Idle, Sleep, Deep Sleep, Reset, OFF) with
IRQ latency and power draw — extract as ONE grouped requirement.

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Key pitch, travel, layout | Keyset | Dimensional/Layout Specification |
| Acoustic specs | Keyset | Acoustic Performance |
| Keyset accessibility | Keyset | Accessibility |
| Backlight levels, uniformity | Backlight | Electrical Specification |
| Backlight fading, events | Backlight | Electrical Specification |
| Touchpad specs, FTF, latency | Touchpad | Input Device Specification |
| Touchpad power states | Touchpad | Input Device Specification |
| Touchpad impedance | Touchpad | Input Device Specification |
| Hinge angle states | Keyboard System Operation | Functional Specification |
| Turn-on/off angles | Keyboard System Operation | Mechanical Specification |
| Turn-on/off delays | Keyboard System Operation | Timing Specification |
| Host wake events | Keyboard System Operation | Functional Specification |
| Host power state interaction | Keyboard System Operation | Functional Specification |

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Key pitch (H/V) | Key Pitch | Dimensional Specification |
| Key travel | Key Travel | Mechanical Specification |
| Click/release sound | Acoustics | Acoustic Performance |
| Spectral centroid | Acoustics | Acoustic Performance |
| Backlight default state | Backlight | Electrical Specification |
| Backlight uniformity | Backlight | Electrical Specification |
| Touchpad dimensions | Touchpad | Input Device Specification |
| Touchpad resolution | Touchpad | Input Device Specification |
| Typing stability | Typing Experience | User Experience |
| Lapability | Typing Experience | User Experience |
| Display visibility | Display | User Experience |
