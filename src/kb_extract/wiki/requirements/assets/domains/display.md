---
name: display
description: "Extract requirements from display subsystem and display experience sections. Covers optical requirements, TCON features (instant-on, overdrive, DRR), display calibration, HDR/Dolby Vision, panel specs, display startup time, and display UX behaviors. Use when content contains display, panel, optical, TCON, HDR, or calibration specs. Note: Keyboard PRDs rarely have display sections."
---

# Display Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **display subsystem** chapters in device-level PRDs
and **display experience** sections in PES/ID-Spec documents.

### Content Patterns (match on these, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| Panel specs | display panel, resolution, refresh rate, color gamut |
| TCON/optical | TCON, overdrive, DRR, instant-on, optical bonding |
| Calibration | display calibration, color profile, adaptive color |
| HDR | HDR, Dolby Vision, peak brightness |
| Display UX | brightness adjustment, ambient light, dark room |

Note: Keyboard PRDs rarely have display sections. This domain is primarily
used for device-level PRDs and PES display experience chapters.
