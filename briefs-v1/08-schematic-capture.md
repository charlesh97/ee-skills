# Dispatch Brief — `schematic-capture`

**Order 8. Kind: generative. BLOCKED on open question 4 — do not start the
implementation until the fork is decided.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`

## Intent

Turn the architecture and part records into connectivity, then into schematic
sheets. The hardest skill in the set; build it after the foundation is trusted.

## OPEN QUESTION 4 — the fork this skill turns on

Being decided in a separate session. Two viable sources of truth:

**Direct generation.** `.kicad_sch` is canonical; engineers edit it in KiCad.
Claude writes s-expressions containing both connectivity *and* geometry — every
symbol needs millimetre coordinates, every wire a pair of points. Connectivity
comes out correct; the drawing comes out poorly, and a reviewer fights the layout
instead of reading the circuit. Needs a placement engine.

**Text HDL** (SKiDL, atopile) canonical, KiCad generated from it. No coordinates
exist, so the placement failure mode disappears rather than being managed. Clean
one-line diffs, blessed sub-circuits become callable functions with parameters,
and you gain a compile step as a free gate. The real cost is round-tripping: the
schematic becomes a build output and the schematic editor effectively becomes
read-only, which is a genuine cultural shift for EEs and the thing that kills HDL
adoption — not the syntax.

There is a middle path: HDL for connectivity, one-time human cleanup in KiCad,
`.kicad_sch` canonical from that point. Correct connectivity plus a readable
schematic, at the cost of the HDL going stale after first pass.

**Get the answer before writing code.** You may usefully draft the parts that do
not depend on it: the `netlist.yaml` emission, the required-externals expansion,
and the gate.

## Contract

```
Reads:   system.yaml, power_tree.yaml, sequencing.yaml, parts/*.json,
         house library symbols, project.yaml
Emits:   netlist.yaml (always), schematic (form depends on the fork)
Gate:    scripts/gate.py + kicad-cli sch erc
Refuses: to run without part records for non-generic components. Refuses to
         invent a connection not derivable from architecture or a part record.
```

## Connectivity first, always

`netlist.yaml` is the reviewable intermediate and it exists under either fork
answer, which is why everything downstream depends on it rather than on
`.kicad_sch`. Emit and check connectivity before emitting sheets.

## Required-externals expansion

Each part record lists its `required_externals` — bootstrap caps, feedback
networks, bypass caps, pull-ups, crystal load caps. Expanding these is
deterministic work driven by the record plus `ee-house-rules/generics.yaml`, so it
belongs in a script, not in model prose. This is also the mechanism that makes the
corresponding `schematic-review` check meaningful.

## Gate

Hard: schema valid; every net has at least two connections; every refdes has a
component record; refdes and net naming conform to house rules; ERC clean of
errors.
Advisory: ERC warnings; unconnected pins without an explicit no-connect;
components with no part record; power flags; nets crossing voltage domains without
a translator.

## Deliverables

Skill directory, `netlist.yaml` schema, `expand_externals.py`, `emit_netlist.py`,
fork-dependent emission, `gate.py`, 2-3 evals starting with a single well-understood
sub-circuit rather than a whole board.

## Definition of done

Connectivity is reviewable before any sheet exists. Required externals are expanded
from records, not remembered. No connection appears that is not traceable to an
input.
