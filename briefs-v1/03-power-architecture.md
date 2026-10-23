# Dispatch Brief — `power-architecture`

**Order 3. Kind: generative. Loops with `part-select` and `part-spec`.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`, `03-elicitation.md`
Coordinate with the authors of briefs 04 and 05 — you share a loop.

## Intent

Derive the power tree from the block diagram's declared loads, choose topologies
and part classes, and emit the sequencing DAG. The model supplies topology
judgement and rationale; **a script does every single sum**. That split is where
consistency comes from: two engineers running the same tree get the same numbers.

## OPEN QUESTION 3 — resolve with the human before schema work

Single-input DC (one supply, a handful of rails), or multi-source with battery,
USB-PD negotiation, and load switching? The second makes `power_tree.yaml` a
**state-dependent graph** rather than a static one, and that is painful to
retrofit. Ask before writing the schema.

## Contract

```
Reads:   system.yaml (required), requirements.yaml (required), project.yaml,
         parts/*.json (optional; presence upgrades estimates to resolved)
Emits:   power_tree.yaml, sequencing.yaml, power.md
Gate:    scripts/gate.py
Refuses: to run without system.yaml. Does not invent loads for blocks that
         declared none — it logs an open item and continues with a flagged gap.
```

## The convergence loop — the defining feature of this skill

The skill runs more than once on a project, and must be idempotent and re-entrant.

```
pass 1:  rails with part_class + assumed efficiency from house default curves
         every rail: resolution: estimated
         -> part-select -> human picks -> part-spec
pass 2:  reload parts/*.json, substitute real efficiency, Iq, theta_JA
         re-run every calculation
         every resolved rail: resolution: resolved
```

Detect on entry whether part records exist for the part classes already emitted,
and if so run pass 2 rather than starting over. Preserve human edits and rationale
across passes — clobbering them is the fastest way to get this skill switched off.

`architecture-review` warns on any rail still `estimated` at maturity v1 or above.

## Deterministic arithmetic — all of it in scripts, none in prose

- per-rail current per mode = sum of declared loads on that rail
- parent current = sum(child power) / efficiency / parent voltage, rolled up the tree
- input current at Vin_min versus the source's limit
- converter dissipation = P_in - P_out; junction temp via theta_JA at max ambient
- headroom versus house-rules derating, per maturity level
- battery runtime per mode profile, if applicable

The model never computes these. It fills fields; `compute_tree.py` produces the
numbers. Show the numbers in `power.md` with their inputs so a human can check them.

## sequencing.yaml

An ordered DAG with per-edge timing. **Constraints are imported from part records,
not authored by the model** — each edge carries a `constraint_source` pointing at
the record and field it came from. Where no record exists yet, the edge is marked
unresolved and logged. Cycle detection is a hard gate failure.

## Gate

Hard: schema valid; no cycles in the power tree or sequencing DAG; no load
referencing a nonexistent rail; no rail referencing a nonexistent parent.

Advisory: rails still `estimated`; margin below house derating; input current over
source limit at Vin_min; junction temp over limit at max ambient; a rail with no
loads or a block with no source; sequencing edges with no constraint source.

## Deliverables

Skill directory, both schemas, `compute_tree.py`, `emit_tree.py`, `emit_sequencing.py`,
`gate.py`, a power-tree renderer for `power.md`, 2-3 evals — including one that
exercises the pass-1-to-pass-2 transition, since that is the hard part.

## Definition of done

Re-running after part selection updates the numbers without losing rationale. All
arithmetic is scripted. Every sequencing constraint is traceable to a datasheet.
