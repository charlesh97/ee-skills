# Dispatch Brief — `part-spec`

**Order 5. Kind: generative. Loops with 03 and 04. Also runs ad hoc, any time.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`
Coordinate with briefs 03, 04, 07, and 09 — all consume your output.

## Intent

Datasheet to machine-readable part record. This record is the input to symbol
creation, schematic capture, and several review checks that are simply
unanswerable without it. Cached in a shared parts DB keyed by MPN so the second
project does not re-extract.

## Contract

```
Reads:   candidates/<class_id>.yaml with approved_by set (loop path), OR
         an MPN given directly by a human (ad hoc path)
Emits:   parts/<mpn>.json, datasheets/<mpn>-<rev>.pdf
Gate:    scripts/gate.py
Refuses: to extract from an unapproved candidate. Refuses to guess a field it
         could not find — missing is an explicit null with a reason, never a
         plausible-looking number.
```

## Build this

**Phase 1 — Acquire and archive.** Find the datasheet, record its revision, store
the PDF locally. Datasheets change; you need the one the design was done against.
Cache check first: if `parts/<mpn>.json` exists and the datasheet revision matches,
return it and stop.

**Phase 2 — Extract.** Pinout, absolute maximum ratings, thermal (theta_JA, Tj max,
package thermal pad), package geometry, electrical characteristics including
efficiency curve and quiescent current, required external components, sequencing
requirements, and errata.

**Phase 3 — Self-check.** Re-read the extraction against the source. Pin count
must match the package. Every pin must have a number, name, and type. Flag every
field where confidence is low rather than presenting a uniform-looking record.

## The two fields that earn their place downstream

**`required_externals`** — bootstrap caps, feedback networks, bypass requirements,
pull-ups, crystal load caps. This is what lets `schematic-review` check that
required parts are actually present. Without it that rubric line is unanswerable.

**`sequencing_requirements`** — imported verbatim into `sequencing.yaml` edges via
`constraint_source`. The model must never author a sequencing constraint; it
imports one.

## Extraction discipline

Datasheet extraction is the highest-hallucination-risk task in the whole plugin.
Design against it:

- Every extracted field carries a page or section reference from the datasheet.
- Confidence marking per field group, surfaced to the human.
- Absolute maximum ratings get an explicit human confirmation step, because a
  wrong abs-max silently disables a real safety check downstream.
- Null with a reason is always correct. A plausible invented number is never.

## Scripts

`fetch_datasheet.py`, `emit_part_record.py`, `check_pins.py` (pin count vs package,
duplicate numbers, missing types), `cache.py`, `gate.py`.

## Gate

Hard: schema valid; pin numbers unique; pin count matches declared package.
Advisory: missing thermal data; missing efficiency curve; no `required_externals`
for a part class that normally has them; low-confidence fields; abs-max not
human-confirmed.

## Deliverables

Skill directory, schema (coordinate with brief 03 on `sequencing_requirements` and
`thermal`, and brief 07 on `model_3d`), scripts, parts-DB cache design, 2-3 evals —
include a part with a genuinely awkward datasheet, not three easy ones.

## Definition of done

Records are traceable to a datasheet revision and page. Unknown fields are null
with a reason. The cache prevents re-extraction.
