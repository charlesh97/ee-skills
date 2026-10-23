---
name: layout-constraints
description: >
  Set up the board before anyone lays it out: pick the stackup, derive net
  classes and trace widths from the power tree and netlist, write the KiCad
  design rules (.kicad_dru and .kicad_pro net_settings), list the critical
  nets, and write an itemised placement spec a human follows and layout-review
  grades. Load this when someone says "set up the board", "stackup", "how many
  layers", "net classes", "design rules", "DRC rules", "trace widths", "how
  thick should this trace be", "how wide for 3A", "clearance for 48V",
  "placement guidance", "where should the caps go", "what do I need before I
  lay it out", or asks the AI to place parts or route — this skill refuses
  that and hands over the spec instead. Runs after schematic-review passes and
  before the human opens the PCB editor.
---

# Layout Constraints

The AI does not place parts and does not route traces. It encodes intent so
that a human (or KiCad's tools) executes it and `layout-review` can grade the
result. That boundary is the point: an LLM placing components produces
garbage that looks finished; an LLM writing net classes, DRC rules and a
placement spec is genuinely strong. If asked to place or route, say so plainly
and hand over `constraints/placement_spec.md`.

## Contract

Reads:  `project.yaml`, `power_tree.yaml`, `system.yaml`, `parts/*.json`,
        `<name>.kicad_pro`, the netlist (export it:
        `kicad-cli sch export netlist --format kicadsexpr <name>.kicad_sch -o netlist.net`),
        `open_items.yaml` (append)
Writes: `constraints/stackup.yaml`, `constraints/netclasses.yaml`,
        `constraints/board.kicad_dru` (copied to `<name>.kicad_dru` — the only
        filename KiCad loads), `constraints/critical_nets.yaml`,
        `constraints/placement_spec.md`, and the `net_settings` block of
        `<name>.kicad_pro`
Stops if: any of the four inputs is missing or unparseable — name the skill that
        produces it (`requirements`, `power-architecture`, `system-architecture`,
        `part-spec`, `schematic-capture`) and stop. A netlist with unnamed nets
        (`Net-(…)`) is a schematic-review failure; send it back rather than
        classifying nets you cannot name. A load on a rail that is not in
        `power_tree.yaml` is a dangling reference; stop.
Does not: place, route, pour, or edit `.kicad_pcb`.

## Before you start

1. Load `ee-schematic-rules` and `ee-layout-rules`. Three schematic rules become layout constraints here and
   are not restated: decoupling package is minimised *so it can sit at the pin*
   (a placement constraint, not just a BOM one); differential pairs are `_P`/`_N`
   (KiCad's diff-pair detection and `inDiffPair()` key on that suffix — any other
   suffix means the diff-pair constraints silently do nothing); test access
   (probe loops for ground, `TP` refdes, zero-ohm on regulator outputs).
2. Read all inputs in full. Note `project.yaml` `board_size_mm` and `assembly`;
   the fab decides the stackup menu and the DRC floor.
3. Ask the human for the mechanical inputs. They exist in no upstream file:
   board outline and any cutouts, mounting hole positions, connector positions
   and orientations (which edge, which face), height limits per region,
   keepouts (enclosure ribs, antenna, heatsink), and whether the board is
   panelised. One question per message, with a default where one is sensible
   ("connectors on the left edge, all top side?"). Do not invent these; a
   placement spec built on a guessed outline is worse than none.
4. Read `../layout-review/references/kicad10-dru-cookbook.md` before writing any rule. Its
   syntax was checked against the KiCad 10.0.6 parser source; write from it,
   not from memory.

## Steps

### 1. Stackup — choose, don't compute

Pick a published JLCPCB controlled-impedance stackup by name (their
`JLCxxxxxH-yyyy` codes, from jlcpcb.com's impedance/stackup page) rather than
computing your own. Closed-form microstrip equations are about ±15% and the
fab builds to their own materials; their impedance calculator is the truth.
Decide layer count from: any controlled-impedance net (USB, Ethernet, RF, any
net flagged high-speed in step 2) or more than one power domain needing a plane
→ 4 layers minimum with the L1–L2 dielectric thin (the `3313`/`2116`-class
stackups) so 50 Ω is a routable width; otherwise 2 layers is fine below about
40×40 mm and a few hundred mA. Run each impedance target through the fab
calculator and record the trace width and gap it returns, with a URL and date.

Write `stackup.yaml`: fab stackup id, layer order top to bottom with material,
thickness and copper weight per layer, finished thickness, and an `impedance`
list of `{target_ohm, type: single|diff, layer, ref_layer, width_mm, gap_mm,
source}`. Layer roles too (L2 = solid GND is the default for 4-layer; say why
if not).

### 2. Net classes — derived, then written into the board

Parse the netlist and classify every net by rule, in this order; first match
wins and every net gets exactly one class here (KiCad allows several, but one
is auditable):

- `GND` (and any datasheet-justified split ground) → `GND`.
- A net whose name is a rail id in `power_tree.yaml`, or starts with one
  (`3V3`, `3V3_MCU_VDD`) → a power class sized by that rail's
  `computed.i_peak_ma`. Compute width with IPC-2221 inline; group rails into a
  few classes (`PWR_1A`, `PWR_3A`) rather than one per rail:

  ```python
  # IPC-2221 external layer, 1 oz Cu, 10 C rise. I = k * dT^0.44 * A^0.725
  def width_mm(i_a, oz=1.0, dt_c=10, k=0.048):     # k=0.024 for inner layers
      area_mil2 = (i_a / (k * dt_c**0.44)) ** (1/0.725)
      return round(area_mil2 / (1.378 * oz) * 0.0254, 2)
  for i in (0.5, 1, 2, 3): print(i, "A ->", width_mm(i), "mm")
  ```
  Show the table. Where the width exceeds what fits, say so and route to
  copper pour in the placement spec instead of quietly narrowing.
- `_P`/`_N` suffix with a matching partner → the diff class for that interface
  (`USB_FS` 90 Ω, `ETH` 100 Ω, …) using widths and gaps from `stackup.yaml`.
  A lone `_P` with no `_N` is a naming error: log it, send it back.
- High-speed is decided by **rise time, not clock rate**. A net is a
  transmission line when its length exceeds about one sixth of the edge's
  spatial extent: `l_crit_mm ≈ 25 × t_rise_ns` (FR4, v ≈ 150 mm/ns). A 1 MHz
  SPI with 1 ns edges on a 60 mm board is high-speed; a 48 MHz crystal is not.
  Take rise times from `parts/*.json`; if absent, assume 1–2 ns for modern
  CMOS, say so, and log it. Matching nets → `HS_SE` with a 50 Ω width and
  tighter clearance.
- Everything else → `Default`.

Write `netclasses.yaml` with the class table (name, clearance, track_width,
via sizes, diff width/gap, priority, why) and a `nets:` list of every net with
its class and the rule that assigned it — this is what makes the result
auditable. Then write the same thing into `<name>.kicad_pro` `net_settings`
(plain JSON; shape in the cookbook) with a short Python `json.load` →
modify → `json.dump(indent=2)` script, after backing the file up and with
KiCad closed. Use explicit `netclass_assignments` for the nets you classified
and add `netclass_patterns` only as a safety net for nets added later. Emitting
YAML alone means a human retypes it, and review then grades against classes
the board never had.

### 3. Design rules — what the DRU can express

Set the Board Setup minimums (`board.design_settings.rules` in `.kicad_pro`)
from the fab's published capability for the chosen layer count and copper
weight — trace/space, drill, annular ring, edge clearance, mask sliver. Read
them off the JLCPCB capabilities page at the time; do not carry numbers from
memory, they change with layer count and finish. Custom rules can never relax
those minimums, only tighten.

Then assemble `board.kicad_dru` from the cookbook: high-voltage clearance and
creepage by net class; power track widths as `(constraint track_width (min …))`
per class, so a narrowed trace is a DRC error and not a review finding; diff
pair gap and `diff_pair_uncoupled`; length limits on crystal and clock nets;
`via_count` on the switch node and feedback; `disallow` for keepout zones
(name the zones and tell the human to draw them with those names); edge
clearance for copper and for connector courtyards; `zone_connection solid` and
thermal relief settings for power pads; a `physical_clearance` band around
the antenna or a height-limited region; an `assertion` for the things you can
only express as a property test. Each rule gets a comment saying which net,
part or requirement it came from.

Say explicitly what the DRU cannot check — placement proximity, plane splits
under signals, return-path continuity, thermal copper area, loop area — and
put each of those in the placement spec instead.

### 4. Critical nets — derived from topology

Build `critical_nets.yaml` mechanically, not by taste. For each rail in
`power_tree.yaml` with `topology: buck|boost|buck_boost`, look up its part
record and pin functions:

- Switch node: the net on pins named `SW`, `LX`, `SWITCH`, `PH` (and `BOOT`/`BST`
  cap). Constraint: minimum copper area, no vias to other layers, nothing
  sensitive within 2 mm. Why: highest dV/dt on the board; area is an antenna.
- Hot loop: input cap → `VIN` pin → power `GND` pin (buck), or inductor →
  switch → output cap (boost). Constraint: loop on one layer, cap as close as
  the package allows. Why: the di/dt loop sets radiated EMI and switch ringing.
- Feedback: net on `FB`, `VFB`, `VSENSE`. Constraint: short, routed away from
  the switch node and inductor, divider at the pin. Why: high impedance node
  that couples noise straight into the regulation loop.
- Current sense: `CS`, `ISNS`, `ISP/ISN`, or a resistor whose record says
  Kelvin. Constraint: Kelvin connection at the sense resistor pads, routed as a
  pair. Why: milliohms of trace resistance are a large fraction of the shunt.

Then, from `system.yaml` and part records: crystal nets (`XIN/XOUT`,
`OSC_IN/OUT`) — short, guard, no crossing signals, load caps at the pins; every
`_P/_N` pair — coupled, matched length, uncoupled length limit; reset and boot
straps — keep away from switching nodes. Each entry: id, nets, refs, the one
constraint that matters, why, and `checked_by: dru|placement|review`.

### 5. Placement spec — itemised, gradeable, hand-editable

Write `placement_spec.md` as a numbered list with stable ids (`PL-001`…) so
`layout-review` grades item by item. One line per item: id, refs, the
requirement with a number, the source (house rule, part record, requirement id
or critical net id). Cover: every IC's decoupling caps within the distance the
house rule implies (state it as mm, typically ≤ 1.5 mm pad-to-pin for the
0.1 µF, bulk within 5 mm); every hot loop from step 4; FB and compensation away
from SW; crystal and its caps within a few mm with a ground guard; connectors
on the edges the human named, with mating direction; every `TP` reachable
with a probe and ground loops within reach of a spring; keepouts as named
zones (matching the `disallow` rules); thermal copper for any part whose
`computed.p_diss_mw` exceeds what its package dissipates on a bare pad —
compute the area needed from the part's θJA or the datasheet's copper-area
curve, in Python, and state it in mm²; fiducials (three, asymmetric, per
assembly side) and tooling per JLC's assembly requirements; mounting holes at
the positions the human gave, with a keepout ring.

Generated items live between `<!-- generated:start -->` and
`<!-- generated:end -->` markers. On a re-run, rewrite only that block. Anything
the human wrote outside it survives, and a hand-written item that reuses a
generated id overrides it — layout-review grades the override. Say at the top
which items are generated and when.

## Check yourself

- Every net in the netlist appears once in `netclasses.yaml` and in
  `.kicad_pro` `netclass_assignments`; the two agree. Diff the class names in
  the DRU against the class names in the `.kicad_pro`; a rule on a class that
  doesn't exist passes silently.
- Reload the project in KiCad (or run `kicad-cli pcb drc` on the empty board)
  and confirm the rules parse with no syntax error. A `.kicad_dru` that fails to
  parse disables every rule in it.
- Every width and clearance traces to a calculation or a fab number with a
  source. Every critical net has a `checked_by`. Every placement item has a
  number and a source.
- Every mechanical fact came from the human. If one was defaulted, it is marked
  as a default and logged in `open_items.yaml`.
- You wrote no coordinates, no track segments, no zones. If you did, delete
  them.

## Handoff

The human lays the board out in KiCad from `placement_spec.md` with the net
classes and rules already active. `layout-review` (fresh session) then reads
`constraints/`, the `.kicad_pcb`, and the DRC report, and grades placement item
by item against this spec. `release` includes `constraints/` in the release
record.
