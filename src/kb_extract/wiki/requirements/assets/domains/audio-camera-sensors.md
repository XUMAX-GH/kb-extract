---
name: audio-camera-sensors
description: "Extract requirements from audio, camera, biometrics, and sensor subsystem sections. Covers speaker/microphone specs, front/rear camera requirements, camera privacy LEDs, Windows Hello/IR camera, fingerprint reader, ambient color sensor, Hall sensor, accelerometer, gyroscope, magnetometer, and digitizer/touch/pen specs. Use when processing device PRD §5.2-5.6 Subsystems (Digitizer, Audio, Camera, Biometrics, Sensors)."
---

# Audio, Camera & Sensors Skill

> **Status**: Placeholder — not yet developed  
> **Inherits**: `base-extraction`

## Overview

Extracts requirements from **device-level subsystem** chapters covering audio,
camera, biometrics, and sensors. These are primarily found in device PRDs
(not keyboard PRDs).

### Typical Section Patterns

| Document Type | Sections |
|---------------|----------|
| Device PRD | §5.2 Digitizer, §5.3 Audio, §5.4 Camera, §5.5 Biometrics, §5.6 Sensors |
| ID Spec | Fingerprint Reader (M1292405) |
| Keyboard PRD | N/A (keyboard PRDs rarely have these sections) |
