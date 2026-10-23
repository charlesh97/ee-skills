---
name: dcdc-layout
description: >
  Lay out a switching regulator (buck first; boost, buck-boost and inverting by
  the same method) on a KiCad 10 board as a self-contained cell built from its
  datasheet's layout figure, check it with numbers, and move it onto the board
  as a unit. Load it for "lay out the buck", "DC-DC layout", "switching
  regulator layout", "place the regulator", "hot loop", "where does the input
  cap go", "switch node copper", "feedback routing", "VOS routing", "is this
  buck layout good", "review the DC-DC", "redo the regulators", or before
  pcb-placement seeds a board that has a switcher on it. It writes a demo
  board and cell files; it changes the real board only through a copy the
  human then accepts.
---

# DC-DC layout

A switcher is the one block on a board whose layout decides whether it works.
Its datasheet already contains a tested layout, so the job is to reproduce that
layout faithfully, measure it, and keep the rest of the board from undoing it.
The failure this skill exists to prevent is the one where every rule is met
locally and the converter is still wrong. A placer clusters the caps near their
nets instead of across their pins. A rail plane closes the hot loop on an inner
layer. A pin-via pass gives the cap and the pin a via each, so connectivity
reads as done and nobody draws the top-layer link. A sense line taps the output
cap as L-44 asks but reaches it by running beside the switch node. Then the
part is locked before anyone measures it.

So the regulator is laid out **first, alone, as a cell**, on a demo board with
the real board's stackup. It is checked against the limits in
`references/cell-check.md`, then placed onto the board as one piece, before
pcb-placement seeds anything else and before planes or pin vias are drawn. The
rest of the board is laid around it.

## Contract

```
Reads:   <name>.kicad_pcb (the parts come from it, read only), its .kicad_pro
         datasheets/<MPN>/capture.json + crops/ for the regulator and inductor
           (run datasheet-extraction if absent), the EVM user's guide if one is captured
         ee-layout-rules: L-10, L-11, L-12, L-21, L-23, L-28, L-29, L-30, L-36, L-39, L-44, L-62, L-63
Writes:  <work>/<cell>/build.py or <cell>.json (the cell), <cell>_demo.kicad_pcb + renders,
         check_<cell>.json (the cell check), and on request a copy of the board with the cell placed
Never:   writes the real board in place. Placing a cell is a copy for the human to accept.
Stops if: the regulator's capture has no pin table, or the netlist and the capture disagree on a pin.
```

Tools: KiCad 10's Python (`$KPY`, with shapely and Pillow; the KiCadRoutingTools venv has both) and
`kicad-cli`.

| Script | What it does |
|---|---|
| `scripts/check_regulator.py BOARD SPEC.json [--json] [--render DIR]` | The cell check: every limit in `references/cell-check.md`, per regulator, PASS/WARN/FAIL with the number; exit 1 on any FAIL. Read only. |
| `scripts/cell.py extract BOARD --refs IC,L,C... --origin X,Y` | Turns a laid-out cell (a demo board, or a good cell on another board) into a cell spec in the IC's frame. |
| `scripts/cell.py build CELL.json --source BOARD -o DEMO` | Builds a demo board from a spec, with the source board's stackup, net classes and footprints. |
| `scripts/cell.py fit CELL.json --target BOARD --region X0,Y0,X1,Y1 [--parts CORE] [--movable REFS]` | Searches positions and rotations for the cell on a board and ranks them by what is in the way (parts, holes, keep-outs, the edge, other-net vias and tracks under its copper). Read only. |
| `scripts/cell.py place CELL.json --target BOARD --at X,Y --rot R -o COPY` | Places a cell onto a copy of a board: moves its parts and replaces the copper on its private nets. Each pour on a shared net is skipped where a board pour of that net covers it, merged into a board pour it overlaps, and added where it touches none, so zones never stack (L-23). It prints which happened. |

## Method

### 1. Read the datasheet's layout, not your memory of the part

From the capture: the pin table, the layout-guidelines section, the layout
figure (in `crops/`), and the application circuit. Write down, for this part:

- **The hot loop.** Its pads in order: for a buck the input cap, VIN, the GND (or
  PGND, or exposed pad), and back. `references/topologies.md` says which loop is
  hot for each topology.
- **The pin order around the package**, and the rotation that makes it match the
  figure. Every later choice follows from where the pins face.
- **Quiet pins:** FB, VOS or SENSE, COMP, and the strap pins (VSET, MODE/S-CONF,
  RT, SS, ILIM). Note which of them sit beside SW in the pinout.
- **Ground scheme:** one ground, or separate analog and power grounds joined at a
  named point (L-62).
- **EN or MODE tied to VIN**, and where the datasheet ties it (L-63).
- **Bootstrap cap** pins, if the part has them.
- **Heat:** an exposed pad and its via count, or heat through the pins (some
  vendors ask for vias on the SW pin; L-29 says how to decide).
- **What the figure does that the text doesn't say:** which side the output cap
  sits on, and whether its ground shares the input cap's ground area.

If the vendor's EVM layout is not captured and can't be fetched, say so and work
from the datasheet figure. Never guess at an EVM.

### 2. Lay the cell on a demo board

Copy the regulator's parts out of the real board onto an empty board with the
same stackup and net classes (`cell.py build`, or a `build.py` like the worked
example in `references/cell-recipe.md`). Add input, output and GND pads so the
demo is a complete converter. Then, in this order:

1. Turn the IC so its pins face as in the figure.
2. **HF input cap across its pins**, each pad facing its own pin, on the
   component layer, joined by pours with no via in the loop (L-11). The bulk cap
   sits right behind it, oriented the same way.
3. **Inductor at the SW pin**, joined by the smallest neck the current needs, on
   one layer, with no vias (L-28). Its other pad points away from the IC.
4. **Output cap**, placed so its ground pad lands on the same ground area as the
   input cap's, as the figure draws it. Sense taps go at its outer edge (L-44).
5. **Ground vias beside the loop, never in it**, where the figure draws its dots.
6. **Rail entry and exit at the cell's edges:** two vias at the bulk cap's far side
   and after the output link (L-21). The rail planes feed the cell. They are never
   part of the loop (L-36).
7. **Quiet pins on the quiet side.** Strap resistors go at their pins and ground
   straight to the plane. A sense pin beside SW leaves the component layer within
   1 mm of the pin, through a via under the first ground plane, and comes up at
   the output cap (L-28).
8. Keep courtyards clear (L-17), and say what that costs against the EVM.

Pour the cell's own copper as zones (VIN, SW neck, VOUT, the output rail) and
keep one zone per net per layer (L-23). The board's ground fill is the ground
pour, so don't add a second ground zone on the same layer.

### 3. Check the cell, with numbers

Write the spec (fields in `references/cell-check.md`) and run
`check_regulator.py`. Fix the layout until every check passes, or until a check
that can't pass is a stated, accepted exception. Run KiCad DRC on the demo
(`kicad-cli pcb drc --refill-zones`): 0 unconnected, 0 errors. Render it with
`--render`, and use `kicad-cli pcb render` for a 3D view. Look at both against
the datasheet figure.

### 4. Hand it over, then place it

Show the human the demo, the check table and a side-by-side with the current
layout if there is one. Once they accept the cell, `cell.py extract` stores it as
`<cell>.json`. Then fit it to the board (`references/fitting.md`):

- `cell.py fit` searches poses for the cell's rigid core;
- if nothing is clear, pivot in the order that page gives: variants, then moving
  other parts, then tier 1 trades, each re-checked and reported as a delta;
- with several regulators, pack them together, most constrained first, along
  the power tree.

`cell.py place` writes a copy of the board with the cell at the chosen pose. Run
the check and DRC on that copy, then re-seat the periphery and draw the rails to
the cell's edges.

On the real board:

- the cell goes on before pcb-placement seeds the rest, and its parts are fixed
  for the placer;
- the pin-via pass skips the cell's pads, because its vias are part of its layout
  (L-39);
- rail shapes end at the cell's entry and exit vias (L-36);
- the cell is locked only after the cell check passes on the board, and it is
  re-checked after every merge round that touches its area.

### 5. Review

layout-review grades each regulator with `check_regulator.py` (LAY-62) and
checks every cap's ground net against the plane under it (LAY-63). A failed
check is a finding even when DRC is clean.

## References

- `references/topologies.md` lists which loop is hot for each topology, what to
  read in the datasheet, and part-specific traps.
- `references/cell-check.md` gives every limit, why it is set where it is, and the
  spec fields.
- `references/fitting.md` covers packing a cell into the space the board has:
  the core, ring and periphery, what never bends and what bends with a number,
  the order of pivots, and packing several regulators together.
- `references/cell-recipe.md` is a worked example: a 1 A synchronous buck in an
  8-pin SOT-583, 12 V to 5 V, on a 6-layer board, with its numbers before and
  after.
