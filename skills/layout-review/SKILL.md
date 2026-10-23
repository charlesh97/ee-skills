---
name: layout-review
description: >
  Fresh-context review of a KiCad 10 board (.kicad_pcb) against its schematic,
  its own design rules, the datasheet captures and the house layout rules. Load it
  for "review the layout", "check my board", "look at the PCB", "run DRC", "is
  the routing ok", "placement review", "before I send this to fab", "is this
  ready for JLC", "did I miss anything on the board", "check my design rules",
  "does this DRU rule do what I think", or when handed a .kicad_pcb and asked
  what is wrong with it. Also load it at placement stage, before routing — the
  cheapest moment to find a placement error. Read-only: it never edits the board.
---

# Layout Review

Judges a board someone laid out. It writes findings; the human fixes the board.

It grades against the board's own design rules, the schematic it came from, the
datasheet captures and the house rules — not against a separate constraints
directory. Intent that only exists in the reviewer's head is not a constraint,
so where a rule matters and is not encoded, the finding says so.

Run it in a fresh context. If this session laid the board out or wrote its rules,
say so and recommend a new session — the context that wrote a rule is the worst
judge of whether it was met. Continue only if the human insists, and record it in
the findings header.

## Contract

```
Reads:   <name>.kicad_pcb, <name>.kicad_pro, <name>.kicad_sch — required
         <name>.kicad_dru, if the board has one
         datasheets/<MPN>/capture.json for the ICs that matter thermally or
           carry a land-pattern requirement  (run datasheet-extraction if absent)
         project.yaml (optional — house defaults if absent), ee-layout-rules,
           and its rules/layout.md and rules/drc.json, which the rubric grades against
Writes:  findings/layout-<date>.yaml, review/ (DRC json, renders, measurements)
         appends to open_items.yaml (shape: board-doc/references/findings.md)
Stops if: the board, project or schematic file is missing or unparseable, or a
         step 1 precondition fails.
```

Take a `stage` from the human: `placement`, `routed`, or `final`. The rubric
marks which lines apply when. Catching a placement error after routing is
worthless, so a placement-stage review is a real review, not a preview.

Mechanical facts — outline, cutouts, mounting positions, height limits, keepouts,
which edge a connector must face — exist in no file. Ask for the ones a finding
turns on. Do not invent them, and mark any you assumed.

## Steps

### 1. Preconditions — wrong here and every later finding is garbage

**Zones are filled and saved.** KiCad only writes `(filled_polygon …)` if zones
were filled when the file was saved. A board saved with stale or empty fills
reads, to a script and to a render, as "no copper", and every plane, return-path
and thermal check then goes silently wrong. Parse the file: every `(zone` on a
copper layer that is not a keepout must contain a `(filled_polygon`. If one does
not, stop and ask for a refill and save. The file cannot tell you a present fill
is *stale*, so also ask "refilled before save?" and record the answer. At
`placement` stage, `n/a`.

**Board nets match the schematic.** Export the netlist and compare (ref, pin) →
net against the board's pads:

```bash
kicad-cli sch export netlist --format kicadsexpr <name>.kicad_sch -o review/netlist.net
```

Report pads on a different net, footprints missing from the board, and
footprints on the board that are absent from the schematic. A board out of sync
with its schematic voids every other finding — you would be reviewing a design
nobody intends to build. Stop and return the diff.

### 2. DRC, triaged by root cause

```bash
kicad-cli pcb drc --format json --severity-all --schematic-parity \
  --all-track-errors --units mm -o review/drc.json <board>
```

Group by `type`, then by rule name and net, then by location. Two thousand
clearance violations on one net are one finding, not two thousand. Classify each
group as **real** (fix the board), **waivable** (true, accepted for this
revision, with a written reason), or **rule-artifact** (the rule is wrong, and
the finding is against the `.kicad_dru`). Every waiver is an `open_items.yaml`
entry starting "DRC waiver:", with rule, count and reason; a waiver without a
reason is a finding you hid. At `placement` stage unrouted items are expected —
triage only courtyard, edge, hole and keepout classes, and say so.

### 3. Audit the design rules themselves

A clean DRC proves the board satisfies the rules it was given. It says nothing
about whether those were the right rules — and a custom rule that matches more
than its author intended silently relaxes the board.

For each rule in `<name>.kicad_dru`: read the comment, read the condition, and
say whether the condition actually scopes to what the comment claims.
`references/kicad10-dru-cookbook.md` has the syntax and the evaluation order.
The failure that matters: a condition of the form

```
(condition "A.intersectsArea('BGA1') && B.intersectsArea('BGA1')")
```

relaxes **any pair of items crossing that area**, along their entire length —
including long tracks that merely pass through and extend far outside it. Adding
`(A.enclosedByArea('BGA1') || B.enclosedByArea('BGA1'))` confines it to the
escape itself.

**Probe rather than reason.** You cannot read a rule's true scope off the text
with confidence. Copy the board, project and `.kicad_dru` to a scratch directory,
exaggerate the rule under test — set its constraint far tighter than any real
geometry — re-run DRC, and count and locate what fires. That set is the rule's
actual reach. A rule whose probe reaches items far outside its intended region is
scoped too loosely, whatever its comment says. Never probe the working copy.

**A probe that changes nothing means the rule is inert**, which is the more
common failure and the easier one to miss. Diagnose in this order: is the file
named for the project basename; is a later rule overriding it; is it trying to
relax below a Board Setup minimum. A worked case: a
`bga_escape` rule relaxes clearance to 0.1 mm inside two BGA areas, and
exaggerating it fires nothing. Board Setup `min_clearance` is 0.15 mm, so the
rule cannot take effect — DRC reports the two escapes as violations against
"board minimum clearance 0.1500 mm", not against the rule. Lowering only the
Board Setup floor to 0.1 mm, with the rule untouched, clears both. The rule's
comment describes an intent the board does not have. (A later probe on KiCad
10.0.6 saw a similar rule take effect below Board Setup, so the clamp may depend
on version or constraint type. Don't assume it either way; the probe decides.)

Also check the three things that make rules silently do nothing:

- KiCad loads exactly one rules file, `<name>.kicad_dru`, matched by basename
  beside the project. Any other filename is ignored **without an error**.
- Rules are walked bottom-up per constraint type and the first match wins, so a
  general rule placed after an exception overrides it.
- A rule that relaxes below a Board Setup minimum may be clamped to it and do
  nothing. This has been seen and also contradicted on KiCad 10.0.6, so probe
  it rather than assume.

Then grade the rules the board does **not** have (L-03). A net that needs a width, a
clearance or a length limit and is held only by `Default` is a finding: the
intent is not encoded, so nothing enforces it and the next revision loses it.

### 4. Geometric checks — a script over the s-expression

Parse the board directly. Pad absolute position is the footprint origin plus the
pad offset rotated by the footprint angle, and KiCad's y axis points down:
`x' = dx·cosθ + dy·sinθ`, `y' = −dx·sinθ + dy·cosθ`. **Check the transform on one
rotated footprint against a coordinate DRC reported before trusting any
distance** — a sign error fails every decoupling cap with great confidence.

Compute and show the numbers: decap pad-to-power-pin distance, as-built minimum
trace width per net, diff-pair gap and skew, via count per power net with a
stated per-via current assumption, copper-to-edge, courtyard overlap, silk over
pads, hot-loop area, feedback-to-switch-node distance, and each fiducial's
distance to its nearest board corner with the spread of the set against the
board diagonal (LAY-53, from placement on). Where a number depends on
current or dissipation, get it from the human or the capture and say which.
Print a table; the numbers are the evidence.

At `routed` and `final`, also grade the copper itself, which DRC passes:

```bash
$KPY <ee-skills>/skills/ee-layout-rules/scripts/check_copper.py <board> \
    --directions "$(cat review/routing/layers.txt)" --json review/copper.json
```

It reports off-center via ends (L-33), overlapping and folded-back same-net
copper, and loops on poured nets (L-34), track on a net's own plane layer
(L-35), sharp bends, 90° corners and off-angle track (L-25), off-list widths and
hand tapers (L-20), and each layer's track length by direction against its
declared job (L-26). Most of these are too small to see in a render, so this is
their only grade. It runs alongside KRT's `check_weird` (step 4a), which covers
exact duplicates, dangling copper and removable copper on nets without a zone.

The layer jobs come from `pcb-routing`'s `review/routing/layers.txt`. If a
board has none, that is a LAY-43 finding in itself (L-26: intent that isn't
written down isn't enforced). Run without `--directions`, report the direction
table, and grade the direction part of LAY-43 `unanswerable`. Don't infer the
jobs from the copper.

Report each category's count and the worst few, by net and (x, y), under LAY-30
(widths), LAY-39, LAY-43, LAY-45 and LAY-46. The same run grades the edge
ground ring (L-38) under LAY-48: `edge-margin` (signal or power copper in the
band), `edge-ring` (GND coverage of the ring path per outer layer, from the
fills as saved) and `edge-stitch` (gaps between stitching vias). If the routing
spec skips the ring, check that it gives a reason and grade LAY-48 against
that. It also grades pin vias (L-39) under LAY-49: `power-pin-via`
(a power pad without its own via), `gnd-pin-via` and `shared-pin-via`.
`edge-margin` is a warn unless the routing spec makes the band strict (then
run with `--edge-margin-fail`). Grade via sizes (L-32) under LAY-54 from
`small-via` and the via-size table it prints: every via drilled smaller
than the Default class via must sit where the routing spec names the
geometry that forced it. Grade vias in pads (L-30) under LAY-55 from
`via-in-pad`: a via whose ring overlaps an SMD land or a paste aperture,
same net included, with the pad, via size, position and net. In a paste
aperture is a fail, on land copper only a warn; pads the routing spec
declares on its `allow-via-in-pad:` line, paste-window thermal pads and bare
test pads are listed as not reported. KiCad DRC passes these.

Grade the GND pours on every copper layer, not just the plane, under LAY-16
and LAY-50: `pour-island` (a fill island with too few vias to the plane),
`pour-fill` (a zone that fills little of its outline, usually because island
removal deleted unconnected copper), `pour-split` (one track cutting a pour
into two large islands), `zone-overlap` (same-net zones stacked on a layer)
and `stitch-group` (run with `--stage final` at final). Also run
`$KPY <ee-skills>/skills/ee-layout-rules/scripts/stitch.py report <board>`.
A plane that passes while the pours on the other layers are fragments is the
failure this catches. An agent's review of a 6x8 array board (2026-09-29) graded only
In1, passed it, and missed an F.Cu fill of 36 mm² over the array and an In2
pour split in two.

For LAY-47, measure the layer plan rather than taking it on trust:

```bash
$KPY <ee-skills>/skills/ee-layout-rules/scripts/layer_capacity.py <board> --pre-route \
    --plane <plane layer from layers.txt> --json review/capacity.json
```

At `placement` it says whether the layer count leaves room for a plane. At
`routed` and `final` it says whether a board with no plane needed one, and
whether the plane that exists survives its vias. A four-layer board whose
capacity fits a plane but has none is a `fail`, however clean the routing is.

### 4a. Router-side QA — KiCadRoutingTools' `review-routed-board` (`routed`, `final`)

KRT maintains measured checkers for things this rubric would otherwise script by
hand: orphan stubs, copper hygiene, length and time match, meander spacing, GND
return vias, impedance and return path, and diff-pair gap and skew. Use them as
an input rather than re-deriving them. Read
`~/git/KiCadRoutingTools/.claude/skills/review-routed-board/SKILL.md` and run
its checks from inside that checkout with KiCad's bundled Python (`$KPY`, see
`pcb-placement`). Don't run its sign-off step, because this review writes the
findings. Save each checker's output to `review/krt/`. If KRT isn't installed,
skip this step and mark the lines below `unanswerable (KRT not available)`.
Don't install it just for a review.

Its results feed these lines, cited by checker and output file:

| KRT check | Rubric line |
|---|---|
| `check_connected.py`, `check_orphan_stubs.py`, `check_weird.py` (`dangling-end`, `dangling-via`, `orphan-island`) | LAY-39 (unrouted, dangling stubs, dead vias) |
| `check_weird.py` (`stacked-copper`, `removable-segment`, `redundant-cycle`, `soft-joint`) | LAY-45 (redundant copper) |
| length/time-match verification, meander arm spacing | LAY-08 |
| diff-pair review | LAY-07 |
| GND return-via coverage | LAY-19 |
| `check_impedance.py` (impedance and return path) | LAY-17, LAY-18 |
| `board_score.py` with the spec flags | LAY-06, LAY-39 |

It doesn't replace the rest of this review. KRT doesn't read the schematic,
the house rules, the captures' layout guidance or the board's own DRU intent. It
also grades whatever specs it's given, and they default to the fab floor. So
pass it the board's real minimums (`--min-track-width`, `--min-via-diameter`,
`--min-via-drill`, `--net-min-widths`), and treat an `ungraded` component as
unexamined, never as passed. KiCad's own DRC (step 2) stays the authority where
the two disagree, because it reads the board's actual rules.

### 4b. Topology — power tree and buses (`routed`, `final`)

The schematic says what connects. This step checks that the copper connects
it the way the architecture means. Read the architecture (the power tree,
the bus segments, the currents) from the project's architecture or system
files, and the pull-ups and mux channels from the schematic. Then trace the
copper.

- **Power tree (LAY-51, L-44).** For each rail, walk the copper from the
  source pad to every load pad, through tracks, vias and pours. Print the
  order in which it reaches the bulk and output caps, the regulator, any
  filter, ferrite or switch, and the loads, and compare it with the tree.
  Report the width and via count of each segment against the current summed
  downstream of it, any pour that touches two rails, and where the feedback
  or sense line joins the rail.
- **Buses (LAY-52, L-45).** For each I2C segment, list its devices, its
  pull-ups and their location, and the copper length of SDA and of SCL,
  including every stub. Estimate the capacitance (state the pF/mm and the
  pin capacitance you assumed) and the rise time with the fitted pull-up.
  Check that SDA and SCL share layers and a continuous GND reference, and
  that each mux channel's pair stays together and uncrossed. The same goes
  for SPI and shared clocks, against their stated topology.
- **Critical nets (LAY-57 to LAY-60, L-49).** Build the critical-net list
  yourself from the schematic and the captures, then compare it with the
  routing spec's `critical-nets:` list: a kind the board has and the list
  left out is a finding. For each entry, check it was routed deliberately and
  locked before the bulk pass, and measure what its L-49 line asks: where
  each Kelvin pair leaves its shunt and how close it runs to a switch node,
  each gate's loop area and length with its return, the reference caps'
  distance to their pins, and the converter interface lengths. Render each
  one.
- **Planes drawn, not routed (LAY-61, L-36).** List every track on a plane
  layer by net, and read the routing logs for the layer costs each pass ran
  with. Router welds show as chains of short segments on the plane nets.

Where the architecture doesn't state a rail's current or a bus's mode, the
line is `unanswerable`, naming what's missing. Don't assume a figure.

### 5. Render and look

```bash
kicad-cli pcb export svg --layers F.Cu,F.Mask,F.Silkscreen,Edge.Cuts \
  --page-size-mode 2 --exclude-drawing-sheet -o review/top.svg <board>
kicad-cli pcb render --side top --quality high -w 2400 -h 1600 -o review/top.png <board>
```

One SVG per copper layer plus top and bottom composites, rasterised at 20–40
px/mm, **and one per Fab and silk layer** (L-46): a Fab layer that cannot be
read, refdes under parts, or a title block missing or under a part are
findings. Open every image and confirm you can read refdes text before trusting
it; if it is mush, re-render larger or crop. Look for plane fragmentation, return-path
continuity under the nets that matter, splits under diff pairs and switch nodes,
silk legibility, and assembly sanity.

**Vision proposes, script confirms.** Every visual finding names a layer and an
(x, y) in board millimetres, and is `fail` only if a geometric check agrees;
otherwise `warn`, with the image as evidence. The reverse holds too: an absurd
script result — every cap failing at 40 mm — is a parser bug until the render
agrees.

### 6. Walk the rubric, then play back

`references/rubric.md`, every line that applies at this stage, one finding per
line, passes included. Each line names the rule it grades. Read that rule in
`ee-layout-rules/rules/layout.md`, and cite its ID in the finding. Then present worst-first in sections — preconditions,
DRC, rules audit, electrical geometry, DFM/DFA, thermal — and wait between them.
Lead each section with the one finding that would most change the board. Do not
offer to fix the board; offer the list.

## Rules

**Severity by consequence, and say what you assumed.** The board cannot be built
or a part is destroyed → critical; it will not work or needs a respin → major;
bring-up, manufacturing or readability suffers → minor; otherwise info.

**Every rubric line gets a finding.** The findings file carries every
rubric ID that applies at the stage, including passes and `unanswerable`. A
missing ID is a review that isn't finished, so check the list against
`references/rubric.md` before writing it. A line added to the rubric after
the last review is exactly the one that goes missing.

**`unanswerable` is not `pass`.** A thermal line with no dissipation figure says
so and names what would answer it. A visual line you did not open the image for
is `unanswerable`.

**A relaxation is a finding even when it is right.** Every rule that loosens a
default exists because geometry forced it. Record what forced it and how far it
reaches, so the next revision inherits the reason and not just the number.

**Do not grade against intent that is not in a file.** If the board needed a
constraint nobody encoded, the finding is that it is unencoded — addressed to
the `.kicad_dru`, not to the person who routed it.

## Files

```
SKILL.md
references/rubric.md                  every line that gets a finding, by stage
references/kicad10-dru-cookbook.md    KiCad 10 custom rule syntax, checked against 10.0.6 source
~/git/KiCadRoutingTools/.claude/skills/review-routed-board/   router-side QA, read fresh (step 4a)
```
