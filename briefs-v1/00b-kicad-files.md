# Dispatch Brief — `kicad-files`

**Wave 0. Kind: mechanics. Called by other skills, never by a person.**

## Read first
`shared/00-project-context.md`, `shared/01-contracts.md`, `shared/02-skill-template.md`

## Intent

Safe read and write of KiCad's file formats, plus wrappers around `kicad-cli`.
Exists so file surgery is written once and correctly rather than reinvented in six
places. Principle 3: anything that should be byte-identical is a script, not a
prompt. This skill is almost entirely scripts.

## OPEN QUESTION 2 — resolve with the human first

**KiCad version: 7, 8, or 9?** The s-expression format changed between them and
this library is version-specific. Do not write for a guessed version. If they run
mixed versions, design a version-detect layer and say so.

## Contract

```
Reads:   project.yaml (for kicad_version)
Emits:   nothing on its own; it is a library
Gate:    its own test suite
Refuses: to write a file it cannot round-trip byte-identically in a test
```

## Build this

**S-expression layer.** Parse and emit `.kicad_sch`, `.kicad_pcb`, `.kicad_sym`,
`.kicad_mod`, `.kicad_pro`, `.kicad_dru`. The hard requirement is **lossless
round-trip**: read a file, write it back, get a byte-identical result. Test that on
real boards before anything else. Formatting drift creates enormous meaningless
git diffs and destroys the review workflow.

**UUID handling.** KiCad identifies objects by UUID. Rules to encode: preserve
UUIDs on edit, generate deterministically on create where possible (a stable hash
of identity beats a random UUID, because it makes regenerated files diffable),
never duplicate.

**Hierarchical sheets.** Sheet instances, hierarchical labels, sheet pins, and the
instance-path mechanics for multi-instance sheets. This is the most error-prone
area of the format; give it a dedicated reference file and thorough tests.

**`kicad-cli` wrappers.** `sch erc`, `pcb drc`, `sch export netlist`,
`sch export python-bom`, `pcb export gerbers/drill/pos/step`, `sch/pcb export pdf
and svg`. Each wrapper returns structured Python, not scraped stdout. Parse the
JSON report formats where the CLI offers them.

**Plot-for-review.** Render schematic sheets and board layers to images at a
resolution a vision model can actually read. `layout-review` depends on this.
Verify legibility empirically rather than assuming a default DPI works.

## Deliverables

1. Python package with the layers above.
2. Round-trip test suite over real KiCad files, including hierarchical designs.
3. `references/format-notes.md` documenting version-specific gotchas found while
   building it. This will save every downstream skill real time.
4. A stable public API documented for the other skills to import.

## Definition of done

Round-trip is byte-identical on every test file. Every `kicad-cli` wrapper returns
typed structured data. No other skill needs to touch an s-expression directly.
