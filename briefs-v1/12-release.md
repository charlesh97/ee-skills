# Dispatch Brief — `release`

**Order 12. Kind: generative. TWO PHASES WITH A HUMAN CHECKPOINT BETWEEN THEM.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`

## Intent

Produce the fab and assembly package — but only when a human says so. The human's
explicit instruction: this must not run automatically.

## Contract

```
Reads:   everything
Emits:   phase 1 -> a preflight report only
         phase 2 -> gerbers, drill, BOM, CPL, assembly drawings, release checklist
Gate:    scripts/gate.py
Refuses: to run phase 2 without an explicit instruction from the human. A clean
         layout-review is not authorization. "I think we're done" is not
         authorization.
```

## Anti-trigger — put this in the description, not just the body

The phrases most likely to fire this skill wrongly are exactly the ones that occur
naturally at the end of a project: "I think we're done", "looks good, ship it", or
simply a `layout-review` finishing clean. The description must state that this
skill runs only on an explicit release request, and that completion of review is
not a trigger.

## Phase 1 — Preflight (read-only, then STOP)

Prints, and does nothing else:

- Findings by severity aggregated across all three reviews
- The full `open_items.yaml` ledger: every assumption, deferral, and skip, with
  the reason and the maturity level that justified it
- Any rails still `resolution: estimated`
- Missing part records, missing 3D models, unverified model alignment
- The verification matrix, built from the `verify` field on every requirement
- Version pins: house rules version, KiCad version, tool versions

Then it stops and waits. This is the checkpoint.

The ledger is the whole point. Because gates are advisory, nothing was blocked
along the way — so the record is what preserves consistency. The output an engineer
should be able to read is "we knowingly skipped thermal analysis because this is a
v0 bring-up board," never "nobody remembers whether we did thermal."

## Phase 2 — Build (only on explicit instruction)

Fab outputs, drill files, BOM in house format, CPL/pick-and-place, assembly
drawings, and a release checklist. JLC-assembly-first per the human's decision, so
BOM and CPL formats should default to what JLC expects, with the format
configurable in house rules.

All of it scripted through `kicad-files`. Nothing here is model-generated: outputs
must be byte-identical given the same board.

## Gate

Hard: every declared output exists; BOM refdes set matches the board exactly;
CPL covers every placed part.
Advisory: critical or major findings outstanding; open items unresolved;
requirements with no verification evidence.

## Deliverables

Skill directory, `preflight.py`, `emit_bom.py`, `emit_cpl.py`, `build_package.py`,
`gate.py`, release checklist template, 2-3 evals — including one that verifies the
skill does NOT fire on "looks good, ship it".

## Definition of done

Phase 2 never runs unasked. The preflight ledger is complete and readable. Outputs
are reproducible.
