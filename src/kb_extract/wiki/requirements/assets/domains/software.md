---
name: software
description: "Extract requirements from software, firmware, and OS sections. Covers blade firmware, HID functionality, driver/firmware updates, authenticated plug-and-play, on-screen keyboard control, backlight level control, UEFI/BIOS, provisioning (fusing, SAR tables, TPM), and commercial enterprise features (BitLocker, Autopilot, SEMM, DFCI). Use when processing PRD §7 Software/OS or §8 Commercial chapters."
---

# Software Skill

> **Status**: Active — rules defined based on Cantley PRD evaluation
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **software specification sections** covering
firmware, drivers, protocols, connectivity, HID specifications, and
factory-provisioned product identifiers.

---

## Domain Focus

### Primary Extraction Targets

- Authenticated plug-and-play operation
- HID interface requirements (touchpad, keyset)
- On-screen keyboard enable/disable
- Backlight level control interface
- Seamless pairing requirements
- Factory-provisioned identifier tables (PID, HWID, GUID, etc.)
- Communication protocols (Bluetooth, USB HID, wireless)
- Firmware version and update requirements
- Power management state definitions (S0/S3/S4/S5 transitions)

### Section Patterns

| Document | Sections | Content |
|----------|----------|---------|
| PRD | §4 Software | Attach/detach, authentication, HID, keyboard control |
| PRD | §4.x Table of Values | PID, HWID, GUID, RGB, Serial Number, Model# |
| PRD (extended) | §7, §8 | Connectivity, power state definitions |

---

## Domain-Specific Rules

### RULE: PRODUCT IDENTIFIER / TABLE OF VALUES

Tables listing factory-provisioned identifiers are requirements because
these values are flashed/fused during production and verified at every
milestone (EV/DV/PV). They are NOT "model number exclusions".

Product Identifier tables typically contain:
- **PID** — Product ID for MTI test stations
- **HWID** — Hardware ID for device identification
- **GUID** — Printed blade-specific identifier for app experiences
- **RGB** — Color hook for Windows integration
- **Serial Number** format — unique unit identifier
- **Model Number** — regulatory/compliance identifier
- **Product Code** / **Supplier Code** — supply chain identifiers

Extract the ENTIRE table as **ONE requirement** (all rows together):
- Category: "Software"
- Function: "Product Identification Table"
- What: "[Table X.X: Table of Values] " + full table content preserving
  Object | Uses | Unique to Product/Print | Value structure

### RULE: HOST COMMUNICATION REQUIREMENTS

"The Host shall..." statements in software sections define interface
contracts between the host device and the blade/keyboard. These are
functional requirements even though they describe software behavior.

Extract each "shall" statement as a separate requirement:
- Category: "Software"
- Function: "Communication Specification" or "Functional Specification"

### RULE: PAIRING AND CONNECTIVITY

Bluetooth pairing, seamless pairing, and connectivity requirements
define verifiable wireless behaviors:
- Category: "Software"
- Function: "Communication Specification"

---

## Domain-Specific Rules for Device-Level PRDs (§7-§8)

### RULE: OS PROVISIONING REQUIREMENTS (§7)

Factory provisioning sections contain verifiable device configuration mandates.
Extract EACH distinct constraint as a separate requirement:

Key patterns to extract:
- OS image update frequency ("updated with newest available software at least quarterly")
- Signature image requirements ("must meet Microsoft Signature image requirements")
- Pre-approved software restrictions ("must only include Microsoft pre-approved software")
- Driver restrictions ("device drivers must only be from Microsoft-approved sources")
- SYSPREP / OOBE requirements ("SYSPREP must specialize", "boot directly to OOBE")
- OOBE customization restrictions ("No OOBE customization beyond adding languages")
- Regional variant settings (China, Japan specific settings)
- Fusing / ME Lock check requirements
- Wi-Fi power table validation during provisioning
- Secure Boot / Secure Core defaults ("enabled by default")
- OA3 license provisioning
- Battery shipped level ("shipped at 80% battery level or lower")
- UTC time/date provisioning
- SMBIOS name provisioning
- 4K hash extraction requirements
- Manufacturing mode cleanup requirements
- OS performance requirements references
- Stability requirements (ABS/RCADe thresholds)

Category: "Software" | Function: "Provisioning Specification"

### RULE: COMMERCIAL ENTERPRISE FEATURES (§8)

Commercial chapters define enterprise device capabilities. EACH feature
is a separate requirement — these are verified during certification:

| Feature Group | Examples | Function |
|---|---|---|
| Encryption | BitLocker, 3rd party disk encryption, OPAL 2.0 SED, BitLocker timing table | Encryption Specification |
| Management | SEMM, DFCI, Surface Dock Updater, UEFI experiences | Enterprise Management |
| Security | VBS/HVCI, Secured-Core PC, ESS/Secure Bio, TPM 2.0 | Security Specification |
| Deployment | Windows Autopilot, PXE boot, Wake on LAN, Wake on Power | Deployment Specification |
| Battery | Battery Limit (50% RSOC), Battery Protection Mode | Power Management |
| Network | MAC address emulation, USB-C granular security | Network Specification |
| Identity | E-Labeling, Asset Tag (SMBIOS) | Device Identity |
| Drivers | Driver/firmware pack delivery, Hyper-V/WDAG support | Driver Specification |
| Peripherals | External monitor compatibility, Absolute Persistence | Peripheral Specification |

Category: "Software" | Function: per table above

### RULE: ENTERPRISE MANAGEMENT PROTOCOLS

SEMM (Surface Enterprise Management Mode) and DFCI (Device Firmware
Configuration Interface) paragraphs define specific operational modes.
Extract each protocol/mode description as a requirement even if it reads
like documentation — these behaviors must be implemented and verified.

SEMM Mode 3 (host USB-C data disabled) is a distinct requirement from
basic SEMM support.

### RULE: BITLOCKER TIMING TABLE

BitLocker encryption time tables define performance bounds.
Extract as ONE requirement with table annotation:
- Category: "Software" | Function: "Encryption Performance"
- What: "[Table 8-2: BitLocker Encryption Times] 128GB <40min; 256GB <50min; ..."

---

## Category Mapping

| Content Type | Category | Function |
|---|---|---|
| Attach/detach detection | Software | Communication Specification |
| Authentication requirements | Software | Communication Specification |
| HID interface | Software | Communication Specification |
| On-screen keyboard | Software | Functional Specification |
| Backlight control interface | Software | Functional Specification |
| Pairing behavior | Software | Communication Specification |
| Product identifier table | Software | Product Identification Table |
| Firmware requirements | Software | Firmware Specification |
| Power state definitions | Software | Power Specification |
