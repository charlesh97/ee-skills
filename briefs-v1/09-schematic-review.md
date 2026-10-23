# Dispatch Brief — `schematic-review`

**Order 9. Kind: judgement. The highest-value skill in the set, and read-only.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md` (reviewer template)

## Intent

Rubric review of the schematic against house rules, the architecture, and the part
records. Highest value because it catches the expensive class of error, and zero
blast radius because it writes nothing but findings. One of the first two skills to
build for exactly that reason.

## Contract

```
Reads:   netlist.yaml, schematic, system.yaml, power_tree.yaml, sequencing.yaml,
         parts/*.json, project.yaml, open_items.yaml, ee-house-rules
Emits:   findings.yaml (review: schematic)
Gate:    scripts/gate.py
Refuses: to review artifacts produced in the current session.
```

## Phase 0 — BOM completeness sweep (the human added this; it comes first)

Before reviewing anything, enumerate every refdes in `netlist.yaml`, join against
the parts DB, and list the gaps. Run `part-spec` on anything missing.

Tiered, because full extraction on a 100nF capacitor is waste:

- **Generic passives** need value, package, voltage rating, tolerance, and
  dielectric from `ee-house-rules/generics.yaml`. No datasheet extraction.
- **Everything non-generic** needs a real part record.

Advisory per Principle 6, but loud, and every gap lands in `open_items.yaml`.

**Why this matters:** it unlocks rubric lines that are otherwise unanswerable —
absolute maximum versus actually applied voltage per pin, required-external
components present, pin function versus connected net, thermal pad connection.
Without records those lines can only return `unanswerable`, and a review full of
`unanswerable` is the "looks good to me" failure wearing a costume.

## Rubric — `references/rubric.md`

Suggested coverage, each line maturity-tagged, each producing a finding with refs:

- Bypass and bulk capacitance per IC against house rules
- Required externals from every part record actually present
- Abs max versus applied voltage, per pin
- Pin type versus net (outputs driving outputs, inputs floating, power pins on
  signal nets)
- Unconnected pins with no explicit no-connect
- Pull-up and pull-down presence and value on every bus and reset line
- Reset and boot strapping
- Sequencing implementation versus `sequencing.yaml`
- Protection on external interfaces
- Test points, debug headers, programming access
- Refdes and net naming conformance
- Differential pairs correctly paired and named
- Crystal and oscillator load capacitance
- Analog reference and ground strategy
- Thermal pad connections
- Unused gates and inputs terminated
- DNP and stuffing options clearly marked
- Traceability: every block in `system.yaml` present in the schematic

## Playback

Sections, worst severity first, stopping between. Forty findings in one message
gets skimmed, and a skimmed review is no review.

## Gate

Hard: every rubric line has a finding; every finding has refs.
Advisory: components with no part record; count by severity.

## Deliverables

Skill directory, rubric, `bom_sweep.py`, `check_abs_max.py`, `check_externals.py`,
`emit_findings.py`, `gate.py`, 2-3 evals including a schematic with planted errors
of varying subtlety.

## Definition of done

The BOM sweep runs first and is loud. No empty rubric sections. Every finding has
evidence. `unanswerable` is used honestly rather than avoided.
