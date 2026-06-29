# Knowledge Graph Rules (P-Graph)

Connect the given atoms with typed engineering relations. Build edges, not
classification. Only relate atoms that the evidence text genuinely links.

Each edge is a JSON object: source_id, target_id, relation, evidence_ref, confidence.
- source_id / target_id: MUST be ids from the provided atom list. Never invent ids.
- relation: one of depends_on|affects|constrained_by|validated_by|implemented_by.
- evidence_ref: the atom id (or section anchor) that justifies the link; OMIT if none.
- confidence: 0..1 self-estimate.

Do NOT create self-edges. Do NOT fabricate links not supported by the text.
Return ONLY a JSON array. No prose.
