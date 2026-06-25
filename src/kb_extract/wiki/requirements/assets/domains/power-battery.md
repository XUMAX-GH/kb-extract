---
name: power-battery
description: "Extract requirements from power management and battery sections. Covers maximum current draw tables, subsystem power budgets, host authentication power limits, battery capacity/life, charging rules/configurations, and power state definitions. Use when content contains power draw, current limits, charging rules, or battery specs."
---

# Power & Battery Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **power management and battery** chapters. These appear
in both device-level PRDs (as major chapters) and keyboard PRDs (as power draw
and host interface sections).

### Content Patterns (match on these, NOT section numbers)

| Content Type | Key Indicators |
|-------------|---------------|
| Current draw | maximum current draw, mA, authentication current |
| Subsystem power | subsystem power draw, mW, active/idle power |
| Battery specs | battery capacity, mAh, charge time, shelf-life |
| Charging rules | charging rules, pen charging, charge to 75% |
| Host authentication | authentication power, mW during auth |
| Power management | power state, standby power, deep doze |
