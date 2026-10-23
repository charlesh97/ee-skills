# Layout review rubric

One finding per line, id as given, passes included. **How**: `script` (a number
from the inline s-expression check or DRC JSON), `visual` (a render, cited by
layer and x,y — `fail` only when a script confirms, else `warn`), `judgement`
(reasoned against the board's own rules or the house rules, with refs).
**Rule** is the rule graded: an L-rule in `ee-layout-rules/rules/layout.md`, or
`drc.json` for the numbers. Read the rule text there. This table says only what
to measure and when, so a rule edited there needs no edit here.
**Stage**: `P+` applies from placement onward, `R+` from routed onward, `F` at
final only. A line whose input is missing is `unanswerable`, naming what would
answer it. Currents and dissipation come from the human or a datasheet capture;
say which, and mark anything assumed.

| id | Check | Rule | How | Stage |
|---|---|---|---|---|
| LAY-01 | Every copper zone has a `filled_polygon`, and the human confirms fills were refreshed before save | — | script | R+ |
| LAY-02 | Board (ref, pin) → net equals the exported schematic netlist; no missing or extra footprints; DRC `schematic_parity` empty | — | script | P+ |
| LAY-03 | `<name>.kicad_dru` is named for the project basename, so KiCad loads it; it parses; `board_rules.py check` passes for the board's profile | drc.json, L-01, L-02 | script | P+ |
| LAY-03a | Every custom rule's condition scopes to what its comment claims, confirmed by probing an exaggerated constraint on a scratch copy, not by reading the condition | L-04 | script + judgement | P+ |
| LAY-03b | No rule is dead: none placed where a later general rule overrides it, none relaxing a Board Setup minimum without a probe showing it takes effect | L-04 | script | P+ |
| LAY-03c | Every relaxation records what geometry forced it and how far its probe reaches | L-04 | judgement | P+ |
| LAY-03d | Rails and constrained nets carry a class or rule, not `Default` alone | L-03 | judgement | R+ |
| LAY-04 | DRC run; every violation group classified real / waivable / rule-artifact; every waiver in `open_items.yaml` with a reason | — | script + judgement | P+ |
| LAY-05 | Bypass cap pad to IC power pin: distance, same layer, no via between | L-10 | script | P+ |
| LAY-06 | As-built minimum width per net ≥ its class; each rail's width vs its current, current source stated | L-20, L-21 | script | R+ |
| LAY-07 | Diff pairs: gap, skew, stubs | L-22 | script | R+ |
| LAY-08 | Length-match groups within tolerance; tolerance source cited | L-22 | script | R+ |
| LAY-09 | Via count per power net vs current, at `pin_vias.via_amps` per via (or another per-via value, stated with its plating); per pad is LAY-56 | L-21, L-39 | script | R+ |
| LAY-10 | Copper-to-edge on every layer, against both the Board Setup floor and `edge_ring.margin_mm` (the band); a pad whose gap to the edge must carry lanes has room for the band plus those lanes | drc.json, L-38 | script | P+ |
| LAY-11 | Courtyard overlap | L-17 | script | P+ |
| LAY-12 | Silk over pads or mask openings | L-18 | script | R+ |
| LAY-13 | Hot-loop area measured along the copper (plan + vertical) against ≤ 2.0 mm², closed on the component layer with no via, HF cap ≤ 1.0 mm from its pins; switch node identified from the capture's pin table (`dcdc-layout/scripts/check_regulator.py`) | L-11 | script + visual | P+ |
| LAY-14 | FB, VOS/sense and strap traces against SW copper and the inductor body: route within 1.0 mm of SW past a 1.0 mm escape ≤ 0.5 mm on the component layer, none over the inductor; SW on one layer, no vias (`check_regulator.py`) | L-28 | script + visual | R+ |
| LAY-15 | Crystal: load caps, trace length, guard, nothing underneath | L-13 | script + visual | P+ |
| LAY-16 | GND pours on **every** copper layer, not just the plane: island count, largest-island share and filled area against outline per layer; no track splitting a pour into two large islands; one zone per net per layer (no stacked same-net zones); necks wider than the widest trace crossing them | L-23 | script (`pour-fill`, `pour-split`, `zone-overlap`) + visual | R+ |
| LAY-17 | Continuous reference plane under every high-speed, clock, diff-pair and switch net | L-23 | visual + script | R+ |
| LAY-18 | No plane split under a diff pair or switch node | L-23 | visual + script | R+ |
| LAY-19 | Return via at each layer change on a critical net; distance stated | L-24 | script | R+ |
| LAY-20 | Power and thermal pad connections solid; no relief on SW or high-current pads | L-29 | visual | R+ |
| LAY-21 | Each mechanical fact a finding turns on came from the human, or is marked assumed | L-05 | judgement | P+ |
| LAY-22 | Connector placement, keying, pin 1 and mating clearance vs the mechanical input | L-14 | visual + judgement | P+ |
| LAY-23 | Test points: coverage, probing side, GND loops | L-15 | script + visual | P+ |
| LAY-24 | Mounting holes at the given positions, with an outer-layer copper keep-out for head and washer; no lane under the head | L-05 | script | P+ |
| LAY-25 | Outline and keep-outs vs the mechanical input | L-05 | script | P+ |
| LAY-26 | Antenna keep-out, if wireless | L-19 | script + visual | P+ |
| LAY-27 | Debug header per `project.yaml` or the house default; reachable in the enclosure; pin 1 marked | L-15 | visual + judgement | P+ |
| LAY-28 | Polarity and pin-1 marks; refdes legible, oriented, not under parts | L-18 | visual | F |
| LAY-29 | Annular ring, minimum drill and hole-to-copper vs the profile's floors | drc.json | script | R+ |
| LAY-30 | Trace, space and via sizes from the predefined lists, or a scoped rule with its reason; no hand-drawn tapers of in-between widths; via-in-pad or HDI only where the pitch needs it | L-20, L-30, L-32 | script | R+ |
| LAY-31 | Fiducials: ≥ 3 per assembled side, `FID`, asymmetric (where they sit is LAY-53) | L-17 | script | P+ |
| LAY-32 | Parts clear of the edge rail | L-17 | script | P+ |
| LAY-33 | Nozzle and rework clearance; tall parts shadowing small | L-17 | visual | P+ |
| LAY-34 | One- vs two-sided reflow stated; bottom-side mass | L-17 | judgement | P+ |
| LAY-35 | Mask slivers, mask bridge, intentional exposed copper | L-31 | script + visual | F |
| LAY-36 | Paste on every SMD pad, none on through-hole or fiducials | L-31 | script | F |
| LAY-37 | Junction temperature per dissipating part, from dissipation (human or capture), copper area and θJA with its board condition | L-29 | script | R+ |
| LAY-38 | Thermal vias under every exposed pad; count and pitch | L-29 | script | R+ |
| LAY-39 | Zero unrouted items; no dangling stubs or dead vias; no track ends off-center in a via | L-33, L-34 | script | F |
| LAY-40 | Component heights vs the enclosure, where given | L-05 | judgement | P+ |
| LAY-41 | Noisy parts zoned away from quiet ones | L-12 | visual + judgement | P+ |
| LAY-42 | Ratsnest untangled: no avoidable crossings or `CROSSED` pin-order pairs | L-16 | script + visual | P+ |
| LAY-43 | Lanes, layer discipline and fine-pitch escapes. Script: 0 arcs (unless L-25's curve exception is stated), 0 segments off 0/45/90, 0 staircases (3+ chained jogs < 0.3 mm), no bend sharper than 90°; layer jobs declared, each signal layer's length on its axis, adjacent layers opposite. Visual: no lane wrapping a hole or pad in short steps; no hooks, U-turns or hairpins; lane vias in rows | L-25, L-26, L-27 | script + visual | R+ |
| LAY-44 | Flex only: bend areas, coverlay bridges, no controlled impedance on flex | L-40, L-41, L-42 | script + visual | P+ |
| LAY-45 | No redundant copper: no duplicate, overlapping or folded-back same-net segments, no same-layer loops, no zero-length pieces | L-34 | script | R+ |
| LAY-46 | Plane nets connect through their pour: no track on a net's own plane layer beyond a stated stub, and 0 unconnected on plane nets after refill | L-35, L-23 | script | R+ |
| LAY-47 | Layer plan: a board of ≥ 4 layers has a solid GND plane; the signal layer count is justified by `layer_capacity.py` (worst cut and utilization); signal on a plane layer only as short hops; the plane survives its vias (copper along the worst cut, webs between antipads) | L-26, L-36, L-37 | script | P+ |
| LAY-48 | Edge ground ring: no signal or power copper within `edge_ring.margin_mm` of the outline (edge parts excepted and listed); GND on ≥ 90% of the ring path on each outer layer, from the fills as saved; stitching vias no farther apart than `edge_ring.stitch_pitch_mm`. Copper in the band is `warn` unless the routing spec makes the band strict; the ring's coverage is `fail`. A board without a ring has the reason in its routing spec | L-38 | script + visual | R+ |
| LAY-49 | A via for every power and ground pin: each pad on a rail, and each ground pad, has its own via in the pad or within `pin_vias.max_track_mm` of its track (through-hole pads count as their own). A ground pad without one is `fail` unless the routing spec lists it with a reason; a listed one is `warn`. No via shared by several pins. Misses are listed by rail, highest current first | L-39 | script (`power-pin-via`, `gnd-pin-via`, `shared-pin-via`) + judgement | R+ |
| LAY-50 | GND stitching: every GND fill island ≥ `stitch.min_island_mm2` has ≥ `stitch.min_island_vias` vias to the plane; the grid is at `stitch.area_pitch_mm` (coarser up to `stitch.area_pitch_max_mm` on a small, slow board; finer only where the routing spec names a high-speed or RF return path) with the `stitch.via`; every stitching via is in the one `stitch.group` group, and nothing else is in it; no stitching via in a pad or a via keep-out. At `routed`, a board not yet stitched is `info`, not `fail` | L-43 | script (`pour-island`, `stitch-group`, `stitch.py report`) | R+ |
| LAY-51 | Power topology in copper: trace every rail from its source through protection, bulk, regulator and output caps to each load, and compare with the architecture's power tree. No load upstream of its filter or switch; no pour merging two rails; each segment's width and vias by the downstream current sum; feedback and sense taken where the architecture says; star or separate returns kept where specified | L-44, L-21 | script (net and pad trace) + judgement | R+ |
| LAY-52 | Bus topology per segment: for each I2C segment (controller side, and each mux or switch channel), the devices on it, exactly one pull-up set where the schematic places it, SDA/SCL routed together over continuous GND, stubs ≤ the L-45 limit, estimated capacitance and rise time against the bus mode, unique addresses on the segment, no crossed channels. SPI and shared clocks: the stated star or daisy topology, and short stubs | L-45 | script + judgement | R+ |
| LAY-53 | Fiducials in the corners: per assembled side, two `FID` in diagonally opposite corners and a third in another corner. Script: each fiducial's distance to its nearest outline corner, and the distance between the farthest pair against the board diagonal; a set clustered near the middle or along one edge is `fail`. A fiducial pushed inboard by the edge rail, the L-38 band or its mask clearance is fine; one displaced by a part that could have moved is not | L-17 | script | P+ |
| LAY-54 | Via sizes: the Default and Power class via is the first `drc.json` `vias` entry; every via drilled smaller (`check_copper.py` `small-via`, with the size table) sits in a region the routing spec names with the geometry that forced it, and is scoped there by a rule or class. A 0.15 drill outside a fine-pitch escape or via-in-pad, or a small via on a board whose pitch never needed one, is `fail`. Stitching at a pitch finer than `stitch.area_pitch_mm` has a high-speed or RF reason in the spec (LAY-50) | L-32, L-43 | script + judgement | R+ |
| LAY-55 | No via in an SMD pad or paste aperture, same net included: no annular ring overlaps an SMD land or a paste opening unless the pad is a declared via-in-pad (named on the routing spec's `allow-via-in-pad:` line and filled and capped, an exposed pad whose paste windows the vias clear, or a bare test pad). A via in a paste aperture is `fail`; one on land copper outside the paste is `warn` | L-30, L-43 | script (`check_copper` `via-in-pad`) | R+ |
| LAY-56 | Pin vias by current and placement: for each pad on the routing spec's `pad-currents:` block (every pulsed or high-current pad, current from the human or the capture), the vias it reaches on its own stub or tab ≥ `ceil(I / pin_vias.via_amps)` for the via used, the current and its source stated. Each pin via is a declared via-in-pad (L-30) or adjacent: annular ring to pad edge ≤ `pin_vias.stub_target_mm` (over it is `warn`), stub width ≥ the smaller of the pad's narrow side and `pin_vias.stub_min_width_mm`, and wide enough for the pad's current (L-21). Pin vias connect solid to their plane, with no thermal relief. A high-current pad short of its count, or with no current stated, is `fail`; a high-current pad on the exception list is `fail` | L-39, L-21, L-30 | script (pad and via trace) + judgement | R+ |
| LAY-57 | Critical nets routed on purpose: the routing spec has a `critical-nets:` list covering every kind L-49 names that the board has (checked against the schematic and captures, not only the list's own word), each entry routed by hand or as an exact scripted path, recorded in `review/routing/critical.md`, and laid before the bulk autoroute; after a parallel merge round closes no track or via is left locked (L-49). A critical net missing from the list, or autorouted with no stated reason, is `fail` | L-49, L-36 | script (lock flags, net list vs schematic) + judgement | R+ |
| LAY-58 | Shunt Kelvin sense: each sense pair leaves the shunt from the inner edge of its pads (or its sense pads), with no current-path copper, pour or via between the pad and the takeoff; runs as a pair at minimum spacing on one layer to the amplifier or ADC; filter at the amplifier end; clear of switch nodes and the bridge's current loop. Distance to the nearest switch node stated | L-49 | script + visual | R+ |
| LAY-59 | Gate drive: each gate routed with its return (source, Kelvin source or the driver's return pin) as a pair; loop area and length per gate measured and stated; gate resistor where the schematic means it; bootstrap cap loop at its pins; high-voltage clearance kept on the bootstrap and high-side nets | L-49, L-28 | script + visual | R+ |
| LAY-60 | Converter inputs, reference and interfaces: ADC differential inputs as pairs, REFIN/REFOUT caps at the pin, over solid ground and clear of switch nodes and digital clocks; converter and isolator clock, data-ready and SPI lines short, over continuous ground, with the schematic's series terminations, clocks clear of the analog inputs | L-49, L-23 | script + visual | R+ |
| LAY-62 | Every switching regulator passes the cell check (`dcdc-layout/scripts/check_regulator.py`, one spec entry per regulator, every check listed with its number), or each failing check is an accepted exception in the routing spec | L-11, L-23, L-28, L-29, L-62 | script + visual | P+ |
| LAY-63 | Each regulator cap's ground pad reaches the regulator's ground pin on its own net; no ground via lands on another net's plane; separate analog/power grounds joined only where the datasheet says; EN/MODE tied to VIN at the input cap | L-62, L-63 | script | P+ |
| LAY-61 | Planes and rails drawn, not routed: every plane and rail is a zone shape (one outline per rail per layer, from the power tree), the pin vias came from the pin-via pass, and no track on a plane layer was drawn by a router (welds, plane-repair chains); the routing logs show the plane layers forbidden (`-1`) in every pass | L-36, L-35, L-39 | script (`plane-track`, logs) + visual | R+ |

---

LAY-03a is the line with no equivalent anywhere else in the set. A clean DRC
proves the board met the rules it was given; only this line asks whether those
were the right rules. Probe it — an exaggerated constraint on a scratch copy —
rather than reasoning from the condition text.
