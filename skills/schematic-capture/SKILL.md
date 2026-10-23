---
name: schematic-capture
description: >
  Draw a KiCad 10 schematic in code, to the house drawing rules, then render every
  sheet to PNG, look at each one, and fix what the look finds — in code, or in
  Eeschema through computer use when that is available. Two modes: a new board
  from a brief (blocks, MPNs, the connections that matter), or a redraw of an
  existing .kicad_sch or netlist with the connectivity held fixed. Load it for
  "draw the schematic", "capture the schematic", "make the KiCad schematic",
  "wire it up", "generate the .kicad_sch", "schematic from this block list",
  "redraw this schematic", "clean up this schematic", "make this sheet
  readable", "hook up the MCU", "pin assignment", "what value pull-up / feedback
  resistor", or "get this into KiCad". It does not place or route a board
  (pcb-placement, pcb-routing) and does not replace schematic-review.
---

# Schematic capture

Connectivity and readability are checked separately, and both have to pass.
ERC and the netlist tell you the wires are right. Only a rendered page tells you
a person can follow them: ERC passes a sheet with the LDO drawn on top of the
MCU, and a tidy sheet can have the SDA pull-up on SCL. So the loop is always
draw in code → check connectivity → render → look → fix → check again.

## Contract

Reads:  a brief from the human (new board) **or** an existing `.kicad_sch` /
        netlist (redraw); `datasheets/<MPN>/capture.json` for every IC;
        symbols from `$EE_LIB`; `project.yaml` if present
Writes: `<name>.kicad_pro`, `<name>.kicad_sch` and one file per sub-sheet;
        `sch_build/` (the emitter script and its inputs, so a re-run is
        deterministic); `pinmap.md` (new board); `review/netlist.net`,
        `review/erc.json`, `review/parts.json`, `review/render/*.png`;
        `project.yaml` answers
Stops if: an IC has no symbol and `symbol-footprint` cannot produce one; a
        connection the brief needs is not stated anywhere and the datasheet does
        not settle it. Ask; never invent a pin or a connection to get past a gap,
        because a guessed connection looks exactly like a verified one in the
        netlist.

## Before you start

1. **Load `ee-schematic-rules`, then read
   `ee-schematic-rules/rules/schematic.md` in full.** Those are
   the rules this skill draws to. The D-rules marked *observed* came from
   comparing a machine-drawn schematic with a hand redraw of the same circuit, so
   they are aimed at exactly the mistakes code-drawn sheets make: labels used
   where a wire belongs (D-20), one rail symbol per pin (D-30), and field text
   that doesn't rotate with its symbol (D-41).
2. **The four house asks** (0201, test-point form, zero-ohm scope, debug
   header). This skill asks them. Ask once, write the answers to `project.yaml`,
   and record a default taken for an unanswered one as `source: default`.
   Redraw mode inherits whatever the existing design did. Note it; don't
   re-litigate it.
3. **Parts.** For each IC and connector: get the symbol from `$EE_LIB`, or run
   `symbol-footprint` for a missing one. Get the datasheet capture, or run
   `datasheet-extraction` for a missing one. You wire from the capture's pin
   table and typical application circuit, not from memory of the part.
4. Read `references/kicad10-sch-format.md` before you write any s-expression.

## Mode A — new board from a brief

The brief is whatever the human gives: a block list, MPNs, "the sensor talks
I²C to the MCU", a sketch. Build the connectivity from three sources and
nothing else: the brief, each IC's typical application circuit and design
procedure in its capture, and the house rules (test access, zero-ohms, debug
header, PWR_FLAGs). A connection with no source among those is a question for
the human, not a guess.

1. **Plan the sheets.** Name each sheet after its block. Order them along the
   power and signal path: this is a topological sort, so do it in Python and
   print it (D-02). Keep the hierarchy shallow (D-03), and play the sheet list
   back to the human before drawing.
2. **Assign MCU pins, and get the assignment approved before any wire exists.**
   Check each pin for: mux legality from the alternate-function table,
   strapping and reset-default pins kept off anything that misbehaves when
   pulled, analog inputs on ADC-capable pins, bank voltage, SWD reserved, and
   bus signals on the package side facing the peripheral. Write `pinmap.md` with
   one row per pin (number, name, net, function, why), and unused pins as
   `NC`, so the decision is recorded.
3. **Derive every value in Python**, from the capture's design-procedure
   equations where the vendor gives them. Print the formula, the result and the
   E-series snap, and put a one-line `Why` property on the part. That covers
   dividers checked at both tolerance extremes, pull-ups sized against bus
   capacitance, crystal load caps and LED resistors. Every value then becomes a
   fully specified part per the house rules. Write the value text in the
   house format (D-45): `100nF`, `1uF`, `10uF`, `2.2uH`, `4.7k`, `120R`,
   `0R`, never `100n`, `1u` or a bare `0`. Have the emitter format it from
   the number, so it can't drift.
4. **Name every net** as you plan it, including divider and filter nodes.
   A `Net-(…)` name in the output means a label went missing (O-2 in the
   drawing rules).
5. **Assign refdes** from the house prefix table. Assign each part once from its
   identity and keep it stable on every re-run.
6. **Map every part to a buyable JLC part** (D-46), before you emit. For each
   BOM line, look the part up live and put `MPN`, `Manufacturer` and `LCSC`
   on the symbol, so the board is fab-ready (JLC BOM and CPL) from the
   schematic:
   ```bash
   J=<ee-skills>/skills/schematic-capture/scripts/jlc.py
   python3 $J search "100nF 0402 X7R 16V" --basic   # passives: a JLC basic part first
   python3 $J search "<MPN>"                        # ICs and connectors: the exact MPN
   python3 $J code C1525 C25744                     # confirm a code: exists, which MPN, stock
   ```
   Pick by the house rules first (package, voltage after derating,
   dielectric, tolerance), then basic over extended for passives, then
   stock for the build. Take MPN and Manufacturer from the hit, not from
   memory, and keep them in `sch_build/` with the date of the lookup. A part
   JLC can't supply is `LCSC` = `CONSIGNED` with a `Consigned` field saying
   who supplies it. Ask the human before consigning an IC. Never type an
   LCSC code you didn't just see: a remembered code looks exactly like a
   looked-up one.

## Mode B — redraw an existing schematic

The existing netlist is the specification, so freeze it first:
`kicad-cli sch export netlist --format kicadsexpr -o review/netlist.before.net`.
Refdes, net names, values and fields all carry over unchanged, with two
exceptions the human agrees to first: value text rewritten to the house
format (D-45), and missing `MPN`/`Manufacturer`/`LCSC` fields filled from a
live lookup (D-46). Neither touches connectivity; list each change. What you change is
sheet structure (if asked), placement, wires versus labels, rails, orientation
and text. D-50 is the rule that matters most here. The hand redraw this skill
learned from was tidier in every way, yet it still dropped two labels and
swapped two connector pins, and both errors survived a visual read.

## Drawing it in code

Write the emitter as a script in `sch_build/`, never as one-off string edits. The
first render always needs adjustments, and a script lets you change one
coordinate and re-emit. It also makes UUIDs reproducible (uuid5 of a persisted
namespace plus the object's identity), so a re-run diffs cleanly.

Draw to every D-rule in `ee-schematic-rules/rules/schematic.md`. Treat the layout as
arithmetic, then check it by eye. What the rules don't say, and code needs:

- **Lay out clusters before wires** (D-10…D-13). Size each D-13 box from the
  cluster's bounding box plus a margin of at least 2.54 mm, and place clusters so
  their boxes don't touch.
- **Place field text explicitly** (D-41), because KiCad's default for `Device:R`
  puts the value on the body.
- **Compute pin endpoints from the library pin coordinates** (D-44 grid). The
  library is Y-up and the sheet is Y-down, and the format reference covers the
  transform. Check it on one rotated symbol before trusting the rest. A sign
  error puts every wire end a pin-length off, and ERC then reports every pin as
  dangling.
- **Split a sheet past about 40 symbols**, which is roughly what A4 landscape
  fits.
- **Choose each label's kind from the netlist, after every sheet is emitted**
  (D-25). Collect the global-label names per sheet file; a name on one sheet
  only, not matching any power symbol, on a sheet used once, becomes a local
  label at the same point. Run it as the last build step, so a hand edit or a
  later sheet cannot leave a stale global behind, and expect only
  `NAME -> /<Sheet>/NAME` renames in the D-50 diff.
- **Draw a large MCU as a multi-unit symbol split by function** (D-14), one
  boxed unit per peripheral group plus a supply unit, each labelled with what
  it serves.
- **Size generated box symbols from their pin-name text** (D-47): about
  1.27 mm per character at 1.27 mm text plus the 1.016 mm offset. Check every
  pair of name boxes for overlap and grow the body downward until none does;
  growing it moves only the bottom pins, so re-emit the sheets that use it and
  diff the netlist.

Write a fresh `.kicad_pro` (D-60: never copy one from another project), with
`top_level_sheets` and the variant list. Emit `(body_style 1)` and
`(in_pos_files yes)` on every instance (D-61).

## Check connectivity

Nothing is worth looking at until its connections are right.

```bash
kicad-cli sch erc --format json --severity-all --exit-code-violations -o review/erc.json <name>.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o review/netlist.net <name>.kicad_sch
python3 <ee-skills>/skills/schematic-review/scripts/pincheck.py review/netlist.net --datasheets datasheets/
```

- **ERC:** fix the schematic, not the severity (D-52). The format reference
  maps each violation type to its usual cause. Hand-written exclusions are not
  a fix.
- **Pins:** every IC's pins against its datasheet pin table. If the script
  reports `PACKAGE COLUMN UNCONFIRMED`, that is unresolved, not a pass.
- **Net names:** grep the netlist for `Net-(` and find nothing.
- **Mode B:** diff the net membership of `netlist.net` against
  `netlist.before.net`. It must be identical: every net's name and its set of
  (refdes, pin). Print the diff. An empty diff is the evidence; "looks the same"
  isn't.
- **Mode A:** walk every connection in the brief and every part of each
  application circuit, and find it in the netlist by refdes and net. Write the
  walk down; a pass with no evidence isn't a pass.
- **Parts:** `python3 <this skill>/scripts/jlc.py check review/netlist.net
  --boards <build qty> --json review/parts.json`. It checks every BOM part
  live: `MPN`, `Manufacturer` and `LCSC` present, the LCSC code exists, its
  MPN is the symbol's, stock covers the build, passives on basic parts, and
  the value format. Zero `FAIL` before handoff; each warning fixed or
  explained. The build quantity comes from the human; 5 is the default for
  a test board, so say if you took it.

## Look at every page

```bash
# one PDF page per sheet, then one PNG per page (sheet-1.png is the root)
kicad-cli sch export pdf --exclude-drawing-sheet -o review/render/sch.pdf <name>.kicad_sch
pdftoppm -r 200 -png review/render/sch.pdf review/render/sheet
# no pdftoppm: kicad-cli sch export svg ... then rsvg-convert -w 3000
```

On macOS `kicad-cli` is not on PATH by default:
`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`.

Open every PNG with the Read tool. If you can't read every refdes and net
label, re-render wider or crop, because a check you couldn't read didn't
happen (D-51). For each sheet, write a short verdict. It is either **looks
good**, or a list of issues, each naming the D-rule, the refdes or region, and
what is wrong:

```
sheet: power.kicad_sch — 2 issues
  D-41  R3, R4: reference and value overlap (fields not rotated with symbol)
  D-20  U2 cluster: VDD_1V8 carried by 3 local labels; both ends in view, draw the wire
```

Judge it the way the hand redraw would. Can someone follow the circuit without
tracing every wire? Does each cluster read as one thing? Is anything crowded,
colliding, or running against the flow? The D-rules name the known failures,
but they aren't the whole of legibility, so report anything that makes a sheet
hard to read.

## Fix what the look found

**In code first**, when the fix is a known change: a coordinate, a rotation, a
field offset, or swapping a label pair for a wire. Edit `sch_build/`, re-emit,
then re-run the connectivity checks and the render.

**Computer use in Eeschema**, when it is available (a screenshot/click tool in
your tool list) and the fix needs an eye rather than arithmetic, such as
clearing a crowded cluster or rebalancing a whole sheet. Open the project with
`open -a KiCad <name>.kicad_pro`, then open the sheet. Use `G` (drag, keeps
wires attached) rather than `M` (move, breaks them). Keep the grid at 1.27 mm.
Save with ⌘S, then **close Eeschema before any script touches the file again**.
KiCad holds the file in memory and writes it back on its next save, so an edit
made in code while the GUI is open is silently lost. A GUI edit leaves no
evidence of its own. After every GUI session, re-run the connectivity checks
(the Mode B netlist diff must still be empty) and re-render.

If computer use isn't available and a fix can't reasonably be made in code,
don't force it. List the issue for the human, with sheet, region and D-rule,
in the handoff.

**Budget: up to 2 fix rounds** after the first render, each one fix → connectivity
→ render → look. Stop sooner if a round changes nothing, or if all that is left
has been listed for the human. When the budget runs out, hand back what remains
with sheet, region and D-rule. Don't start a third round.

## Handoff

- The files, with ERC empty or every item justified, pins matched, no `Net-(`,
  and (Mode B) an empty netlist diff.
- `jlc.py check` clean, with the date of the lookup, the build quantity, and
  the consigned parts listed with who supplies them.
- The per-sheet verdicts from the final look, with the PNGs in `review/render/`.
- `pinmap.md` approved (Mode A), and `project.yaml`.
- A line saying you drew this, so you are the wrong reviewer of it. Recommend
  `schematic-review` in a fresh session or subagent before layout.
