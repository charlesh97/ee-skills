---
name: hdi-breakout
description: >
  Plan and place the breakout of every BGA, WLCSP and fine-pitch array on a KiCad 10 board
  before routing: read the ball map and the fab's via menu, count rings and lanes to decide
  how many layers the escape needs, pick a breakout strategy per part (surface escape,
  dogbone, via-in-pad, skip via, staggered microvias, local neck-down, rotation, shared vias),
  place every escape via and stub as one locked group, check it, and write the plan into the
  routing spec. For arrays of identical cells it also builds and checks one cell tile and the
  lane budget between cells. Load it for "BGA breakout", "fan out the BGA", "WLCSP escape",
  "via-in-pad plan", "HDI stack-up", "how many layers does this need", "microvia plan",
  "dogbone", or when pcb-placement hands off a board with a BGA, WLCSP or a repeated cell
  array. Runs between pcb-placement and pcb-routing; it does not route the rest of the board.
---

# HDI breakout

The breakout decides the layer count. Every ball needs a way out, the ways out are counted
in tracks between balls and lanes between cells, and that count is known the moment the
part is placed. Routing a board whose breakout does not fit only finds this out slowly: on a WLCSP sensor-array board, 30 hours of router runs ended where a lane count at placement started
(`references/sensor-array-example.md`). So this skill answers the layer question with geometry,
gets the human's decision while it is cheap, and hands the router a board on which every
ball has already escaped.

## Contract

Reads:  a placed `<name>.kicad_pcb` and its `.kicad_pro` / `.kicad_dru`; the netlist; the
        footprint of each array part; `datasheets/<MPN>/capture.json` (ball map, NC balls,
        layout notes); the fab's HDI capability page or quote; `routing_spec.md` if it exists;
        `ee-layout-rules` (L-30, L-36, L-37, L-39, L-43, L-47, L-48)
Writes: `review/breakout/` (budget JSON, per-part plan, renders of each ball field on every
        layer, check output); the fanout vias and stubs on the board, locked, only after the
        human agrees to the plan; a `breakout:` block in `routing_spec.md`
Stops if: placement fails its gate (courtyards, the dogbone band of L-47); the via menu is
        unknown (ask the human or the fab, don't assume one); the budget says the board needs
        more layers than it has, until the human decides.

## Before you start: the intake

Ask once, record the answers in `routing_spec.md`, and don't rediscover them one round at a
time. Every one of these changed the sensor array's layout after it had been routed.

1. **Layer budget and cost.** How many layers, and is more acceptable for a prototype? Give
   the price step (6 to 8 layers is roughly 30 to 40% per board at JLC prototype volume).
2. **Via menu the human accepts:** laser microvias, skip vias, buried core vias, **stacked or
   staggered only** (stacked microvias are a reliability choice, not a default), through vias,
   via-in-pad filled and capped (IPC-4761 Type VII).
3. **Reserved layers:** which layers are planes with nothing else on them, which face is
   reserved (sensor pads, a cosmetic face), preferred directions.
4. **Package limits:** pad size changes allowed (NSMD shrink needs the assembler), parts that
   may rotate, cells that may be mirrored.
5. **Fab tier:** the exact numbers (track/space, hole-to-track, hole-to-hole by net, capture
   pads, laser aspect ratio, dielectric under the laser layer). Quote them with the source.

## 1. The ball map

For each array part: pitch, pad diameter and type (SMD/NSMD), rows and columns, and every
ball classified as **signal**, **plane** (GND, a rail on a plane: needs a via, not a lane),
or **NC** (no pad copper needed beyond the land; a free channel or via site). Take NC from
the datasheet capture, not from the netlist alone: a ball the datasheet says "must be left
unconnected" (the AS7150's VCSELA) is a channel. Write the map into
`review/breakout/<ref>.json`.

## 2. Escape budget, per part

```bash
B=<ee-skills>/skills/hdi-breakout/scripts/escape_budget.py
$KPY $B ball --board <board> --ref U1 --track 0.1 --space 0.1 --capture 0.25 \
     --plane-nets GND,1V8 --json review/breakout/U1_budget.json
# or from numbers alone, before the footprint exists:
python3 $B ball --pitch 0.4 --pad 0.2 --rows 4 --cols 4 --track 0.1 --space 0.1 --capture 0.25
```

It reports, on the surface and on a via-in-pad layer: tracks that pass between two
neighbouring balls, whether a dogbone via fits in the site between four balls, whether a
via-in-pad layer is landlocked, the ring count, and an estimate of the signal layers the
escape takes (outer row plus one row per track through a channel, per layer). The board mode
also counts signal, plane and NC balls per ring: plane balls only need a via, so a field with
a plane-heavy inner ring needs fewer layers than the estimate.

Read the result before choosing a strategy:

- **No track between balls and no interstitial via** (0.4 mm pitch, 0.2 pad): the outer
  ring escapes outward on the surface; every inner ball needs a via in its pad.
- **Landlocked via-in-pad layer** (capture pads in every ball leave no lane): only the inner
  balls take via-in-pad; the outer ring stays on the surface (L-47). This is the trap the
  sensor array hit on its first 6-layer route.
- **One or more tracks between balls:** ring 2 can escape on the surface between the ring-1
  balls; a classic quadrant dogbone may work.

## 3. Lane budget, for arrays

When the part repeats (an AFE per taxel group, a channel per connector pin), the question is
no longer one part's escape but the lanes between cells. Count, for one cell, the free spans
on each signal layer that a track can run along (gaps between via columns, between ball
fields, between bands) and the nets that must pass through the cell (buses, links to other
cells, power trunks that aren't planes):

```bash
python3 $B lanes --track 0.1 --space 0.1 --span In1=0.35x11 --span In4=0.35x8 --demand 20
```

It exits non-zero when the cell is short. **A shortfall here is the "Needs more layers"
outcome of pcb-routing, reached before routing.** Stop and give the human the table: lanes
per layer, demand, and the options (a layer, a plane given up, finer rules in the field, a
different cell pitch), each with its cost. Re-run it whenever the intake gains a constraint
(a plane, a reserved face, a via per pin): each one removes lanes.

Make the cell grid commensurate with whatever else repeats (the taxel grid on the sensor array),
or the copies are not copies: a via site legal in one cell lands on another part's via in the
next.

## 4. Choose the strategy

Pick per part from `references/strategies.md`, which gives for each: when it applies (pitch,
pad, ring count), what it costs (fab, reliability, assembly), what it needs from the via
menu, and whether the house router supports it. In order of preference when several work:

1. Surface escape of the outer ring (always first; free).
2. Dogbone to an interstitial or outside via (needs the budget's `interstitial_via` to fit,
   or the L-47 band outside the field).
3. Via-in-pad on the inner balls only, filled and capped (L-30, declared per ball).
4. Local rule area in the ball field: neck-down track/space (fab tier permitting).
5. Skip via (L1 to L3 laser) or staggered microvias, to add an escape layer without stacking.
6. Stacked microvias, only if the intake allowed them.
7. Geometry changes that go back to placement: rotate the part 45°, rotate cells so escapes
   face the lanes, a different cell pitch.
8. Shared vias for neighbouring same-net balls: an exception to L-48, recorded as one.

Write the choice and its reason per part into `review/breakout/<ref>.json`.

## 5. Place the fanout, locked

Place every escape via, every dogbone stub, the pin via of every power and ground ball (L-39)
and any shared plane tap (L-43) as one group, before any other track exists (L-47). For an
array, route one cell (or a two-cell tile where neighbours differ) with its copies held as
real neighbours, copy it to every position, and check the copies, not just the original.
Rules for the geometry:

- A via is at a pad's centre (declared via-in-pad) or wholly outside it (L-47).
- Each ball leaves along its row or column for at least one track width before it bends
  (axial exits, L-25).
- A ball is the end of exactly one track (L-48).
- No via cuts a plane stripe of another net; a power via counts as connected only where its
  plane copper really is.

## 6. Check

- `$KPY <ee-skills>/skills/ee-layout-rules/scripts/check_copper.py <board> --stage fanout`
  (`via-over-pad`, `via-in-pad`, `pad-junction`, `power-pin-via`, `gnd-pin-via`,
  `entry-vias`) and KiCad DRC on the fanout alone.
- `layer_capacity.py --plane <GND layer>`: the planes survive the fanout vias (L-37).
- Render each array part's ball field on every copper layer, zoomed, plus one whole-board
  view per layer, and **show them to the human with the plan**. The human reviews from a
  phone as often as not: one page of renders, posted with the result.

## Handoff

Write the `breakout:` block of `routing_spec.md`:

```yaml
breakout:
  U1-U16:            # AS7150 WLCSP-16, 0.4 mm
    strategy: outer ring dogbone on B.Cu to vias in the 0.5 mm bands; inner B2/B3/C3 via-in-pad
    vias: [laser F-In1 0.1/0.25, buried In1-In6 0.15/0.30, laser In6-B 0.1/0.25, no stacking]
    budget: review/breakout/U1_budget.json
    cell: two-cell tile U5/U7, copied x8, checked as copies
    lanes: review/breakout/lanes.json   # 20 needed, 25 available on 8L
  locked_group: fanout   # the router may not move or rip it
```

Then hand to `pcb-routing`, which joins what has escaped and does not re-plan it. The house
router for blind, buried and dogbone stacks is `rr` (PathFinder, periodic tile mode); KRT has
no blind or buried vias.
