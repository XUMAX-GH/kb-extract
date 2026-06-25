### Evidence Pack (JSON Sequence)
Here is the document content, provided as a JSON List of blocks (Text, Table, Image) in reading order:

```json
{evidence_content}
```

### Task
Extract ALL technical requirements and specifications as Test Items.
Refer to the 'id' field in the JSON for the 'EvidenceRef'.
CRITICAL: There may be multiple items in this text. List EVERY single one. Do not summarize.

### P2 Precision Reminders
- Do NOT extract model numbers, SKU identifiers, or process instructions (ODM/OEM tasks).
- **DO extract** Key Component tables (chip part numbers), Product Identifier tables (PID/HWID/GUID), and timing/response tables.
- For Requirement Summary tables, walk through EVERY data row — do not stop early.
- Use complete original text — do NOT summarize or paraphrase.

### Table Source Annotation
When extracting from a TABLE block, prefix the What field with:
`[Table X.X-X: Title]` using the actual table number from the document.
Example: `[Table 3.2-2: Subsystem Power Draw] BACKLIGHT MAX (56%): 77mA`

### Category Assignment
Use these standardized categories (match the closest one based on section context):

Product Requirements, Mechanical & Industrial Design, Electrical,
Interface with the Host, Keyboard System Operation, Software, Keyset,
Backlight, Touchpad, Pen, Packaging, Quality, Reliability, Safety, Certification
