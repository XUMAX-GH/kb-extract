# Atomic Extraction Rules (P-Atom)

Decompose the section into MINIMAL reusable knowledge units ("atoms").
One atom = one entity's one parameter under one condition.

Each atom is a JSON object: entity, parameter, value, unit, type, condition, confidence.
- type: one of requirement|behavior|constraint|spec
- value: numeric or range string; OMIT or null if not stated. NEVER infer dimensions/force/power.
- condition: state or precondition (e.g. hinge state, power state); empty if none.
- confidence: 0..1 self-estimate.

Return ONLY a JSON array. No prose.
