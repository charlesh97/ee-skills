---
name: schematic-review
description: >
  Fresh-eyes review of a KiCad 10 schematic against the datasheets and the house
  house rules. Checks every IC's pins against its datasheet pin table, runs ERC,
  does the electrical checks in Python over the netlist, renders every sheet and
  looks at it, and proposes the bring-up hardware that was missed. Load it for
  "review the schematic", "check my schematic", "did I miss anything", "run ERC",
  "is this ready for layout", "before layout", "check the pinout against the
  datasheet", "is this symbol right", "do I have enough decoupling", "what should
  I add for bring-up", or when handed a .kicad_sch and asked what is wrong with
  it. It is read-only: it writes findings, never the schematic.
---

# Schematic Review

The last point where a mistake costs an afternoon rather than a board spin. This
skill writes findings and nothing else, so it can be run on anything, any time.

Its inputs are the schematic, the netlist exported from it, and the datasheet
captures — not a parallel description of the board. If a capture is missing it
produces one rather than grading around the gap.

## Contract

```
Reads:   <name>.kicad_sch (+ sub-sheets), <name>.kicad_pro
         netlist.net and bom.csv  (exported here in step 1 if absent)
         datasheets/<MPN>/capture.json for every IC  (produced in step 2 if absent)
         ee-schematic-rules
         project.yaml  (optional — the four house asks; defaults if absent)
Writes:  findings/schematic-<date>.yaml, review/ (erc.json, pins.json, parts.json, renders)
         appends to open_items.yaml (shape: board-doc/references/findings.md)
Stops if: kicad-cli cannot open the schematic. Nothing else is a stop.
Does not: fix anything, or edit a schematic, a symbol or a capture.
```

There is no required YAML description of the board. A missing input downgrades a
line to `unanswerable` and names what would answer it; it never halts the review.

## Before you start

1. **Fresh context.** If this session drew or edited the schematic, say so in
   your first line and recommend a new session. The author reads what they meant,
   not what is there. If the human continues anyway, put
   `reviewer: same_session` in the findings header.
2. Load `ee-schematic-rules` in full. The rubric points at it rather than restating
   it, so you need the rule text *and its reason* to grade the case the rule did
   not anticipate.
3. Read `project.yaml` if it exists for the four house asks (0201, test-point
   form, zero-ohm scope, debug header). If it does not, take the defaults in
   `ee-schematic-rules/references/asks.yaml`, say which you took, and grade against
   them. Do not stop for a missing `project.yaml`.
4. `sha256sum` the schematic and every sub-sheet. A finding against an unhashed
   file cannot be tied to what it reviewed.

## Steps

### 1. Export what you will grade against

```bash
kicad-cli sch export netlist --format kicadsexpr -o review/netlist.net <name>.kicad_sch
kicad-cli sch export bom -o review/bom.csv <name>.kicad_sch    # --variant per variant
```

The netlist is the review's spine. Each node carries the pin number, the
symbol's pin name as `pinfunction`, and its `pintype` — which is what makes the
next two steps possible at all.

### 2. Inventory the parts, and extract what is missing

List every IC and its MPN from the netlist. For each, check
`datasheets/<MPN>/capture.json`. **If it is missing, run `datasheet-extraction`
on that part now** — most of this review is a comparison against the datasheet,
and without the capture half the rubric returns `unanswerable`.

If there is no PDF for a part, ask for one or find it, and record the MPN as
ungraded with the lines it blocks. Never fill a gap from recall: a remembered
abs-max reads exactly like an extracted one in a findings file.

### 3. ERC, and keep running it

```bash
kicad-cli sch erc --format json --severity-all --exit-code-violations -o review/erc.json <name>.kicad_sch
```

Read every violation including warnings, and record each one as a finding with
refdes and sheet. You don't fix them, because this review is read-only. An open
ERC error is at least `major`, and it goes at the top of the playback: half the
rubric is what ERC already knows, so recommend the author clears ERC and the
review is re-run before anyone trusts the rest.

An item may remain only as an exclusion with a reason. Each exclusion is its own
finding — `pass` if the reason holds, `warn` if you would challenge it. An
exclusion with no reason you can find is `warn`, never `pass`.

### 4. Check every symbol against its datasheet pin table

```bash
python3 <this skill>/scripts/pincheck.py review/netlist.net \
    --datasheets datasheets --json review/pins.json
```

This is the check nothing else in the flow performs. A wrong symbol passes ERC,
passes DRC, fabs cleanly, and the part is dead on arrival. The script resolves
each MPN to its package from the datasheet's orderable-parts table, picks that
package's column out of the pin table, and diffs pin number → pin name against
the netlist.

Read the output, and read the two flags it raises:

- **`PACKAGE COLUMN UNCONFIRMED`** — the package could not be resolved from the
  orderable table, so the column is a guess. Confirm it against the capture by
  hand before trusting any row. Verifying a symbol against the wrong package's
  column reports a confident pass on a wrong pinout, which is worse than not
  checking.
- **`not_in_datasheet_table`** — the symbol has a pin the datasheet's table does
  not list. Often a thermal pad numbered N+1, sometimes a real error.

Every `MISMATCH` is `critical` until you have read the datasheet page yourself
and decided otherwise; the page number is in the output.

### 5. The electrical checks, in Python over the netlist

Most of the rubric is a join, not an opinion: "does every `power_in` pin have a
capacitor to GND on its net" across sixty nets is exactly where an eye misses the
one that matters. Write one script, run it, paste the numbers into the evidence.
The netlist carries every component field, so descriptors join against
`capture.json` for abs-max, pin function and package.

```bash
python3 <this skill>/scripts/netlist.py review/netlist.net   # C-1: caps on every power_in pin
```

`netlist.py` also exposes `load()`, which returns components with every field, nets
and pins per refdes. Import it for the other checks.

For E-7 and E-8, check every BOM part against JLC live, the same check
capture ran, because stock and codes change between capture and review:

```bash
python3 <ee-skills>/skills/schematic-capture/scripts/jlc.py check review/netlist.net \
    --boards <build qty from the human; 5 if not given, and say so> --json review/parts.json
```

Record the lookup date in the findings. If the lookup can't reach JLC, E-7
is `unanswerable` (never `pass`), and the value-format part of the output
still grades E-8.

Extend it per rubric line rather than rewriting it. Where a number matters —
divider output, capacitor derating against the rail, pull-up value against bus
capacitance — compute it and print it.

### 6. Render every sheet and look

```bash
kicad-cli sch export pdf --exclude-drawing-sheet -o review/render/sch.pdf <name>.kicad_sch
pdftoppm -r 200 -png review/render/sch.pdf review/render/sheet   # one PNG per sheet
# no pdftoppm: kicad-cli sch export svg ... then rsvg-convert -w 2600
```

Open every PNG. Flow direction, junction style, whether a connector's pin 1 is
where a technician expects it, whether the sheet is legible at all — only a
picture answers those. Grade the drawing against
`ee-schematic-rules/rules/schematic.md`, citing the D-rule. If you cannot read every refdes, re-render wider: a check
you could not read did not happen. Lines marked *visual* are `unanswerable` if
you did not open the image.

### 7. Walk the rubric, then the bring-up pass

`references/rubric.md`, top to bottom, one finding per line including passes.
Section G is the bring-up and de-risking pass and is run last, deliberately —
by then you know what the board does and what is most likely to be wrong.

### 8. Play back worst-first, in sections

Criticals, stop. Majors, stop. Then minors and info, then the pass list and the
`unanswerable` lines with the captures that would unlock them. Wait between
sections: forty findings in one message get skimmed, and a skimmed review is no
review. Where the human argues a grade down, record their reason in the finding
rather than deleting it.

### 9. Append the open items

Every `fail` and `warn` becomes an `open_items.yaml` entry. Append; never
rewrite.

## Rules

**The datasheet is the authority, and you cite the page.** Every electrical
finding names the value, the pin, the net and the page of the capture it came
from. "Decoupling looks fine" is not evidence; "U3 pin 7 VDDA on `3V3_ANA`: C14
100nF X7R 16V, 16V ≥ 2 × 3.3V, capture p12" is.

**Grade by consequence and say what you assumed.** The part is destroyed or the
board cannot be built → critical; it will not work or needs a respin → major;
bring-up, manufacturing or readability suffers → minor; otherwise info. Do not
soften a finding because the board is "just a v0" — a v0 that cannot be brought
up costs the same three weeks as any other respin.

**`unanswerable` is never `pass`.** A line you could not grade because a capture
is missing says so and names the MPN. An empty section is a skipped check, not a
clean bill.

**A wrong symbol is the worst defect on the board** because every downstream
check passes. Give section A the same weight as everything else combined; it is
the only part of this review that cannot be recovered after fab.

## The bring-up pass is a proposal, not a defect list

Section G asks a different question from the rest: not "is this correct" but
"when this board is on the bench at 2am and something does not work, what will
you wish you had put on it". Two questions generate most of it:

- **What single part, if it is wrong or dead, leaves no way forward?** That part
  wants a bypass. An I²C mux is the standard example: if it does not enumerate,
  every device behind it is unreachable and the board is a paperweight. A pair of
  DNP 0 Ω pads shorting one downstream channel to the upstream bus costs two
  pads, and turns a dead board into a board with one working channel.
- **What will you want to measure, and can you reach it?** Current per rail,
  a bus under load, a strap's state at reset.

Findings here are `info` or `minor` and each one names the failure it de-risks
and what it costs in area and BOM lines. Propose the two or three that matter.
A list of fifteen optional additions gets ignored wholesale, and the one that
would have saved the bring-up goes with it.

## Files

```
SKILL.md
references/rubric.md      every line that gets a finding, grouped A-G
scripts/pincheck.py       symbol pins vs the datasheet pin table, per IC
scripts/netlist.py        netlist loader + the decoupling check, base for the electrical checks
```
