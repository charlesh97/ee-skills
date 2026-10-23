---
name: ee-layout-rules
description: >
  The house board-stage standard: how a board is set up, placed and routed (the
  L-rules), and every number KiCad enforces (Board Setup floors, net classes,
  predefined track widths and vias, per rigid or flex profile), with the script
  that puts them on a board and the KiCad project templates. Load it at the
  start of board work and keep it loaded: starting a new board, placing,
  routing, pouring planes, writing a .kicad_dru rule, or reviewing a layout.
  Also load it whenever the question is "what do we do here" on a board: what
  width for this rail, which via, how close can this cap sit, is via-in-pad
  allowed, what clearance does the fab need. Naming, part choice and schematic
  drawing are ee-schematic-rules.
---

# EE layout rules

Apply these. Where a rule has a reason attached, the reason matters more than
the rule: it tells you what to do in the case the rule didn't anticipate.

Every rule is *(draft)* until signed off. Follow it anyway, but say so when one
drives a real decision.

Net names come from the schematic, named to `ee-schematic-rules`. Layout reads
them and doesn't rename them: power-net and diff-pair classification depend on
those names (L-03, L-22). The project answers (test-point form, debug header,
0201 allowed) are in `project.yaml`. Where it is missing, the defaults are in
`<ee-skills>/skills/ee-schematic-rules/references/asks.yaml`.

---

## The files

Each kind of rule has one file. Nothing else restates them: skills and reviews
cite them by ID. Read the one you need in full before doing that work.

| File | What | IDs | Read before |
|---|---|---|---|
| `rules/layout.md` | how a board is placed and routed: setup, placement, routing, flex | L-01…L-45 | placing, routing or reviewing a board |
| `rules/drc.json` | every number KiCad enforces: Board Setup floors, net classes, predefined widths and vias, per profile (rigid, flex), each with its `_why` | — | setting up a board |
| `scripts/check_copper.py` | grades the copper hygiene that DRC and KiCadRoutingTools' `check_weird` pass: off-center via ends, overlapping copper, loops on poured nets, track on a plane net's own layer, sharp bends, off-list widths, vias drilled smaller than the house default, each layer's direction against its declared job, staircases and jogs, the edge ground ring (copper in the edge band, GND coverage of the ring, stitching gaps), a via on every power and ground pin, vias at every power entry, a via over a pad's copper, a pad with more than one track, and GND pours (islands without stitching, thin fills, pours split by a track, same-net zones stacked on each other, stitching outside its group) | L-20, L-21, L-23, L-25, L-26, L-32…L-35, L-38, L-39, L-43, L-47, L-48 | grading a routed board (`pcb-routing` step 3, `layout-review` step 4) |
| `scripts/rail_check.py` | the rail and bus numbers from the routed copper: each rail's path resistance from its source to the farthest load and the IR drop at its peak current (`rail-drop`), and each bus segment's capacitance from track length, vias and pins against its pull-up and rise-time limit (`bus-cap`) | L-21, L-45 | after routing (`pcb-routing` step 3, `layout-review` step 4b) |
| `scripts/stitch.py` | the last-pass GND stitching grid (L-43): `add` lays it as one group, `remove` deletes the group in one step before a re-route, `report` finds stitching vias left outside the group | L-43 | after routing is closed (`pcb-routing` step 2.6), and before any later re-route |
| `scripts/layer_capacity.py` | how many signal layers the board needs (nets that must cross each cut against tracks that fit), which layers are free to be planes, and whether a plane survives its vias | L-36, L-37 | after placement and before routing; again after fanout; in review |
| `references/fab-and-layout-defaults.md` | the fab research behind the numbers. It is background, not a rule set | — | changing a number in `drc.json` |

To change a rule, edit it in its file and keep its ID. A number changes only in
`drc.json`.

## Putting the rules on a board

`scripts/board_rules.py` is the only way the numbers reach KiCad. Run it with
KiCad's bundled Python (`$KPY`, see `pcb-placement`):

```bash
S=<ee-skills>/skills/ee-layout-rules/scripts/board_rules.py
$KPY $S apply <board>.kicad_pro --profile rigid|flex   # raise floors, add classes and sizes (close KiCad first)
$KPY $S check <board>.kicad_pcb --profile rigid|flex   # exit 1 if KiCad reads back anything looser than drc.json
$KPY $S template <ee-skills>/skills/ee-layout-rules/assets/kicad-templates   # rebuild the templates
```

A new board starts from a copy of `assets/kicad-templates/<rigid|flex>_<2L|4L>`,
which already carries the rules. Pick the template by material and layer count
(L-02).

## Findings

Layout findings and open items use the shared shape in
`<ee-skills>/skills/board-doc/references/findings.md`.
