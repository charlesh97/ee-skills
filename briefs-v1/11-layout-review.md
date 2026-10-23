# Dispatch Brief — `layout-review`

**Order 11. Kind: judgement.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md` (reviewer template)

## Intent

DRC triage plus rubric review of the finished board against the placement spec and
the constraint set. Separate from `layout-constraints` for the same reason review is
always separate: the context that wrote the constraints is the worst judge of
whether they were met.

## Contract

```
Reads:   board file, constraints/, netlist.yaml, power_tree.yaml, project.yaml,
         DRC output, plotted layer images
Emits:   findings.yaml (review: layout)
Gate:    scripts/gate.py
Refuses: to modify the board. Read-only. Refuses to review a board produced in
         the current session.
```

## Two distinct activities

**DRC triage.** Run `kicad-cli pcb drc` via `kicad-files`, then classify each
violation: real, waivable-with-reason, or false positive from a DRU rule that is
too strict. Every waiver needs a written reason and lands in `open_items.yaml`.
Grouping thousands of violations by root cause is more useful than listing them.

**Visual rubric review.** Uses plotted layer images from `kicad-files`. Verify
image legibility empirically — a model cannot review what it cannot read.

## Rubric — `references/rubric.md`

Maturity-tagged, evidence per line. Suggested coverage: placement versus
`placement_spec.md` item by item; decoupling cap proximity and loop area; power
plane integrity and split crossings; return path continuity under high-speed nets;
critical net length matching against `critical_nets.yaml`; differential pair
routing; thermal relief and copper pour for dissipating parts; via count and
current capability on power paths; connector and mechanical fit including 3D
clearance; antenna keepout; test point access; fiducials and tooling holes; silk
legibility and polarity marks; panelization and DFM per fab.

## Gate

Hard: every rubric line has a finding; every finding has refs; every DRC violation
is triaged.
Advisory: waivers without reasons; counts by severity.

## Deliverables

Skill directory, rubric, `triage_drc.py` (grouping and classification),
`emit_findings.py`, `gate.py`, 2-3 evals including a board with real DRC output.

## Definition of done

Every DRC violation is triaged with a reason. Visual findings cite a layer and
location. No empty rubric sections.
