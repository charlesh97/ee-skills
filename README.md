# ee-skills

Skills a Claude agent loads while designing a PCB in KiCad 10, so the output
is consistent board to board and follows one set of house rules.

## Layout

    skills/                   the eleven skills — install this directory
    shared-v2.md              the brief the first cut was written against (history)
    briefs-v1/                the original, over-built dispatch briefs (history)

## The skills

| Skill | Kind | Reads → Writes |
|---|---|---|
| `ee-schematic-rules` | data | — → the schematic-stage standard (naming, part descriptors, passives, derating, debug, the four project asks), plus `rules/schematic.md` (D-rules) |
| `ee-layout-rules` | data | — → the board-stage standard: `rules/layout.md` (L-rules), `rules/drc.json` (every DRC number, applied by `board_rules.py`), KiCad templates in `assets/` |
| `datasheet-extraction` | extract | a datasheet PDF → `datasheets/<MPN>/capture.json`, crops, curves |
| `symbol-footprint` | acquire + verify | a capture + LCSC id → `$EE_LIB/house*.{kicad_sym,pretty,3dshapes}` |
| `schematic-capture` | generative | a brief, or an existing `.kicad_sch` to redraw → `.kicad_sch` drawn to the drawing rules, per-sheet PNG verdicts |
| `schematic-review` | judgement | `.kicad_sch`, netlist, captures → `findings/schematic-*.yaml` |
| `pcb-placement` | generative | schematic + mechanical facts → placed `.kicad_pcb` via KiCadRoutingTools, per-block verdicts |
| `hdi-breakout` | generative | placed `.kicad_pcb` + ball maps + fab via menu → escape and lane budget, breakout plan per part, locked fanout vias, `breakout:` block of the routing spec |
| `pcb-routing` | generative | placed `.kicad_pcb` + routing spec → routed `.kicad_pcb` via KiCadRoutingTools, per-layer verdicts |
| `layout-review` | judgement | `.kicad_pcb`, its own `.kicad_dru`, schematic → `findings/layout-*.yaml` |
| `board-doc` | generative | `.kicad_pcb` → `docs/notion/<board>.md` + renders and pinouts |
| `paper-doll` | judgement | both boards, connector datasheets, assembly pose → pin-to-pin map and mis-install grading for every board-to-board joint (cable, flex, B2B, mezzanine), confirmed in 3D CAD |

## Design principle

Every skill here reads an artifact that already exists — a board file, a
schematic, a netlist, a datasheet PDF, or a brief the human states — and
produces judgement or a concrete file from it. None of them requires you to
have run the one before it.

The three authoring skills (`schematic-capture`, `pcb-placement`,
`pcb-routing`) share one loop: first pass in code, render every page and look
at it, fix in code or through computer use in the KiCad GUI where available,
then re-run the checks. The scripts are the verdict; a render or a GUI edit is
not verified until they agree. Each hands off to its review skill in a fresh
context, because the author reads what it meant rather than what is there.
Layout delegates the first pass to
[KiCadRoutingTools](https://github.com/drandyhaas/KiCadRoutingTools)' own
`pcb-free-agent` playbook, read fresh each run, rather than copying it.

That is the lesson of the 2026-09-17 cut, which removed seven skills
(`requirements`, `system-architecture`, `power-architecture`,
`architecture-review`, `part-spec`, `schematic-capture`, `release`). They formed
a strictly serial chain: each declared the previous skill's YAML output as a
required input, so the tenth was unreachable without running the first nine from
a blank page. They also maintained a parallel description of the board —
`system.yaml`, `power_tree.yaml`, `parts/*.json` — whose only producer and only
consumer was the chain itself. `git log` has them if any are wanted back.

`layout-constraints` went the same way on 2026-09-21, for a sharper reason: it
assumed constraints are encoded up front, a human executes them and a review
grades the result. The three boards of the reference project each carry exactly
one net class, `Default`, with no patterns and no assignments — the skill's main
output has never been used. What those boards do carry is hand-written
`.kicad_dru` rules that **relax** a clearance in a narrowly scoped place, each
written after routing hit a real geometry it could not avoid. The work runs the
other way round from the skill, so grading the rules the board actually has
moved into `layout-review`, and its DRU cookbook with it.

Two things worth rescuing from the cut and not yet re-homed:

- the power-tree arithmetic from `power-architecture` (Iq broken out of
  efficiency, dissipation at Vin_max against input current at Vin_min);
- the commonly-forgotten-blocks checklist from `system-architecture`.

The part-sourcing rule from `part-spec` (an MPN you remember but did not see at
a source is a lead, not a part) now lives in `ee-schematic-rules`.

## Status

`board-doc` is the only skill exercised end to end on a real board.
`schematic-review`'s pin check and `datasheet-extraction` have been run against
a sensor-array dev board and the TI/ams/OSRAM datasheets behind it.

The three authoring skills were tested against a no-skill baseline on copies
of the reference project's boards on 2026-09-28:
- **schematic-capture:** redrew a flex driver board from its netlist alone. The
  netlist diff was empty, ERC 0, and the sheets were judged against the hand
  redraw.
- **pcb-placement:** placed a flex driver board from a pile, honouring the
  mechanical facts.
- **pcb-routing:** routed a flex LED board with its copper stripped, to 0
  unconnected and 0 copper DRC. The round-1 baseline left 2 nets open.

Computer use was not available, so the GUI cleanup path is untested. Several
things were added after those runs and have not yet been exercised by a test
run: the board-rules setup step, the routing budget, the 2-round caps on
schematic and placement cleanup, and the human gate before a part is merged
into `$EE_LIB`. Known gaps:

- `kicad-library/LICENSES.md` cites a `scripts/gen_library.py` that is not
  in that repo — a dangling reference in the library, not in these skills.
- Maturity and severity definitions are deferred; reviews grade by consequence
  and say what they assumed.
- KiCad format references were verified against KiCad 10.0 source. The
  schematic one has since been round-tripped against `kicad-cli` 10.0.6, and
  its rotated-pin transform and field-angle rules corrected. The symbol and
  footprint one has not.
- A routing probe on a copper-stripped flex LED board found `bga_escape` live on
  10.0.6. That contradicts the Board-Setup clamp recorded in `layout-review`
  (22273c0) and is unresolved. `layout-review` and its DRU cookbook now say to
  probe the clamp rather than assume it either way.
