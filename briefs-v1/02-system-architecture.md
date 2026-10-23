# Dispatch Brief — `system-architecture`

**Order 2. Kind: generative.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`, `03-elicitation.md`

## Intent

Turn requirements into a block-and-bus graph with resource allocation and per-mode
current declarations. This is where the most expensive architecture misses get
caught, because they are catchable with arithmetic months before anyone draws a
sheet. Discovering at capture time that the SoC does not have enough SPI instances
is the canonical example.

Separate from `power-architecture` because the loads in the power tree are derived
from the block diagram. If one skill owned both, a model would invent a load when a
block was underspecified rather than failing. Two skills with a file boundary means
`power-architecture` opens `system.yaml`, finds a block with no current numbers,
and stops.

## Contract

```
Reads:   requirements.yaml (required), project.yaml (required),
         ee-house-rules (approved parts, naming)
Emits:   system.yaml, architecture.md (block diagram + narrative)
Gate:    scripts/gate.py
Refuses: to run without requirements.yaml. Does not emit a power tree.
```

## Build this

**Phase 1 — Block decomposition.** Requirements to functional blocks. Every block
traces to at least one requirement id; every `must` requirement is covered by at
least one block. Both directions are checkable.

**Phase 2 — Interface and bus definition.** Buses with type, voltage domain, speed,
membership, and addressing. Every endpoint needs a matching endpoint.

**Phase 3 — Resource allocation.** This is the high-value phase. Allocate SPI,
I2C, UART, USB, ADC, GPIO, timers, and memory against the candidate `part_class`,
and check totals against availability plus the spare margin house rules require.
Pin and interface allocation lives here, not in `schematic-capture`.

**Phase 4 — Per-mode load declaration.** Every block declares current in every mode
from `requirements.yaml`. This feeds everything in `power-architecture`. Where a
number is unknown, use the elicitation pattern to get an estimate and log it to
`open_items.yaml` with an owner — never silently insert a plausible figure.

**Phase 5 — Playback and emit.**

## The MPN rule

Emit `part_class` strings — parametric requirements — never part numbers. `mpn`
stays null until `parts/<mpn>.json` exists. Fabricated MPNs are the most likely
failure mode in this phase, and the fix is structural rather than a warning: the
model is never in a position where guessing a part number is the easy path.

## Checks the graph gives you for free (all in gate.py)

Structural (hard): every block has a power source; every bus endpoint has a match;
no dangling references.

Advisory: I2C addresses unique per bus; bus voltage domains match or a translator
block exists; allocated resources <= available with house spare margin; every
`must` requirement referenced by a block; every external interface has a declared
protection element; every bus has declared test/debug access; bus member count and
estimated capacitance within limits.

Tag each with the maturity at which it becomes expected.

## Scripts

`emit_system.py`, `allocate_resources.py` (deterministic allocation and margin
arithmetic), `trace_requirements.py`, `gate.py`.

Also: a block-diagram renderer (graphviz or mermaid from `system.yaml`) for
`architecture.md`. Humans need to see the graph.

## Deliverables

Skill directory, schema, scripts, renderer, 2-3 evals.

## Definition of done

Resource over-allocation is caught mechanically. No MPNs appear. A block with
undeclared loads produces an open item, not an invented number.
