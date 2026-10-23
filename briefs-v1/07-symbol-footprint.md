# Dispatch Brief — `symbol-footprint`

**Order 7. Kind: generative — but ACQUIRE-THEN-VERIFY, not generate.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`
Coordinate with brief 05 on the `model_3d` field.

## Intent

Get a correct, house-conformant symbol, footprint, **and 3D model** for a part.
Note the identity carefully: this is not a generator with a checker bolted on. It
is an acquisition and verification skill in which generation is the last resort.

## The acquisition ladder

```
1. House library          already blessed -> reuse, done
2. easyeda2kicad --full   symbol + footprint + 3D from an LCSC ID
3. Vendor-supplied        manufacturer KiCad libs, SnapEDA, Ultra Librarian
4. Generate from record   fallback only, from parts/<mpn>.json
```

Step 2 is the human's explicit direction and fits the JLC-assembly-first decision.
`easyeda2kicad --full --lcsc_id=C2040` writes a `.kicad_sym`, a `.pretty` folder,
and a `.3dshapes` folder containing both WRL and STEP.

## The verification gate is the actual content of this skill

**Upstream explicitly does not guarantee the correctness of converted symbols and
footprints.** Acquired parts therefore enter as *candidates* and face exactly the
checks a generated one would. The converter saves the drawing work, not the
checking work. Do not let the skill's structure imply otherwise.

Checks, regardless of source:

- Pin count, number, name, and type diffed against the pin table in
  `parts/<mpn>.json`. This is the single most valuable check in the skill.
- Pad dimensions, pitch, and count against the package drawing
- Courtyard and IPC density class per `ee-house-rules/footprints.yaml`
- Pin-1 marker and silkscreen conventions
- Thermal pad and paste rules
- Normalization to house conventions: library naming, refdes prefix, field set,
  pin ordering and grouping, graphic style

## 3D models — required, not optional

Populate `model_3d` on the part record:

```yaml
model_3d:
  step: "..."                 # MCAD handoff; enclosure fit
  wrl: "..."                  # KiCad render
  source: easyeda2kicad | vendor | generated | placeholder
  license: "..."
  alignment_verified: false
```

Two things to get right. **STEP and WRL are not interchangeable** — KiCad renders
WRL, mechanical needs STEP for enclosure fit, so require both and convert if only
one is available. And **offset and rotation is the common failure mode** with
converted models, so the gate renders a 3D view for a human glance rather than only
checking the file exists.

Track `source` and `license`: EasyEDA model provenance is murky for redistribution
and this library is shared across projects.

## Gate

Hard: symbol parses; pin numbers unique; footprint parses; library naming conforms.
Advisory: pin diff mismatches against the part record; courtyard or density class
deviation; missing STEP or WRL; `alignment_verified` false; placeholder-sourced
model; no license recorded.

## Deliverables

Skill directory, acquisition adapters for each ladder step, `verify_symbol.py`
(the pin diff), `verify_footprint.py`, `normalize_to_house.py`, `render_3d.py`,
`gate.py`, 2-3 evals — include an LCSC part whose converted symbol has a known
defect, so the verify gate is demonstrably doing work.

## Definition of done

Nothing enters the house library unverified against a datasheet pin table. Every
part has both STEP and WRL with provenance recorded.
