# Dispatch Brief — `layout-constraints`

**Order 10. Kind: constraint authoring.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`

## Intent

Encode design intent as constraints a human or a tool executes. **The AI does not
place parts and does not route traces.** Being honest about that boundary is the
point: an LLM placing components produces garbage, while an LLM writing net
classes, a `.kicad_dru`, and a placement spec is genuinely strong. A skill that
blurred this would fail quietly, which is worse than failing loudly.

## Contract

```
Reads:   netlist.yaml, power_tree.yaml, system.yaml, parts/*.json,
         project.yaml, ee-house-rules (stackups, netclasses, dru profiles)
Emits:   constraints/stackup.yaml, netclasses.yaml, board.kicad_dru,
         critical_nets.yaml, placement_spec.md
Gate:    scripts/gate.py
Refuses: to place components or route traces. If asked, explain that placement is
         a human or tool task and offer the placement spec instead.
```

## Build this

**Stackup selection.** Layer count, dielectrics, copper weights, and impedance
targets, chosen from house stackups against signal speeds, current, and cost.
Impedance calculation is arithmetic and belongs in a script.

**Net classes.** Derive from `netlist.yaml` and `power_tree.yaml`: trace width from
current and copper weight and temperature rise, clearance from voltage, impedance
class from bus type. All computed, not asserted.

**`.kicad_dru`.** Generated from house DRC profiles plus the fab's capability plus
this board's specifics. This file must be byte-identical across runs given the same
inputs, so it is entirely script-generated.

**`critical_nets.yaml`.** Length matching groups and tolerances, differential
pairs, high-di/dt loops, sensitive analog, high-voltage clearance, thermal paths.

**`placement_spec.md`.** Written for a human or an autorouter to execute:
placement zones, keepouts, component-to-component relationships ("input cap within
2mm of the VIN pin, same layer, shortest loop"), connector and mechanical
constraints, thermal placement, and antenna keepouts. Derived from part records'
`required_externals` and from house rules, not from the model's taste.

## Gate

Hard: DRU parses; every net in `netlist.yaml` has a class; no class references a
nonexistent layer; stackup layer count matches the DRU.
Advisory: trace width below the computed minimum for the current; impedance target
not achievable in the chosen stackup; critical net with no constraint; placement
spec missing an entry for a part whose record lists required externals.

## Deliverables

Skill directory, schemas, `calc_widths.py`, `calc_impedance.py`, `emit_dru.py`,
`emit_netclasses.py`, `gate.py`, 2-3 evals.

## Definition of done

The DRU is reproducible. Every width and clearance traces to a calculation. The
skill refuses placement cleanly and offers the spec instead.
