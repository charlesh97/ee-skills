---
name: pcb-routing
description: >
  First-pass routing of a placed KiCad 10 board with KiCadRoutingTools, then
  verify, render, look, and clean up in pcbnew with the interactive router
  through computer use where it is available. Derives the routing spec (power
  widths, diff pairs, impedance, length groups) from the schematic, the
  datasheet captures and the human; draws the planes, rails and pin vias;
  routes the critical nets deliberately and locks them; runs KRT's router on
  the rest; and fixes what DRC, connectivity and the renders find. Load it for "route the board",
  "autoroute", "first pass routing", "route this with KiCadRoutingTools",
  "pour the ground plane", "route the diff pairs", "finish the routing",
  "clean up the routing", or when a board is placed and has no copper yet. It
  does not move parts (pcb-placement) and does not replace layout-review.
---

# PCB routing

A router finishes what it was asked to finish. So most of the value here is
asking for the right thing: widths that carry the real current, pairs routed as
pairs, the planes the board needs. Then check it with graders that don't trust
the router's own tally. The first pass runs in code. The cleanup is where a
person's eye, or computer use in pcbnew, earns its place.

## Contract

Reads:  a placed `<name>.kicad_pcb` (no copper, or copper to finish) and its
        `.kicad_pro` / `.kicad_dru`; the schematic and netlist;
        `datasheets/<MPN>/capture.json`; `floorplan.json` if placement made one
Writes: the routed board (only after the human agrees to replace theirs;
        otherwise `<name>.routed.kicad_pcb`); `review/routing/` (spec files,
        scores, DRC and connectivity JSON, renders, verdicts); any new
        `.kicad_dru` rule, each with its comment and probe
Stops if: the board isn't placed, or its placement fails `check_assembly`
        or KiCad DRC reports courtyard overlaps (route a bad placement and
        you'll re-route after you re-place); schematic parity fails; the layer
        plan (step 1) says the board needs more layers than it has, until the
        human decides.

## Success, and when to stop

This skill does the bulk of the routing and then hands back. It does not
iterate until the board is perfect. The last few connections around a
fine-pitch part are often faster by hand in pcbnew than by an agent trying a
twenty-fifth router variant. **This budget replaces KRT `pcb-free-agent`'s own
stop rules** (three failed approaches, a 10-hour cap). Give the free agent
these limits instead, or drive the tools yourself.

**Measure progress one way, every time:** KiCad's unconnected-item count from
`kicad-cli pcb drc --refill-zones`, taken first on the unrouted input as the
total. "Routed %" is `1 − unconnected / total`. Record every attempt in
`review/routing/progress.json` (attempt, what changed, unconnected, copper DRC
errors, vias, minutes). Don't use KRT's own failure tally, which undercounts.

**Outcomes:**

| Outcome | Condition | Then |
|---|---|---|
| **Done** | 0 unconnected, 0 copper DRC errors, spec widths met, every `critical-nets:` entry routed deliberately, accepted and locked (L-49), no router-drawn copper on a plane layer (L-36), the planes from the layer plan whole, the edge ground ring in place (L-38), a via on every power pin (L-39), every GND pour stitched as one group (L-43), and clean copper: `check_weird` finds nothing, and `check_copper.py` fails nothing but `via-off-center` (step 3) | hand back |
| **Good enough (the target)** | ≥ 90% routed, **and** 0 shorts or clearance errors in the routed copper, no part moved, no floor loosened | stop, hand back, and ask whether to keep going |
| **Out of budget** | the budget below is spent and good-enough isn't reached | stop, hand back the best board, and ask |
| **Needs more layers** | the layer plan, or a congestion diagnosis re-checked with `layer_capacity.py`, says the signal layers can't hold the nets without taking a plane (L-37) | stop, hand back the numbers, and ask: add layers, re-place, or give up the plane knowingly |

Never trade a hard rule for a lower count: a short, a clearance violation, a
moved part or a loosened floor makes an attempt worse, whatever it does to
the count. Keep the best board so far, `best.kicad_pcb`, and hand that back,
not the last one tried.

**Budget** (the defaults; the human can set others in the request). It is for
the autorouting steps (step 2's 4 and 5) and cleanup. The planes, the pin vias
and the critical nets (step 2's 1 and 3) are done properly however long they
take, and are never cut short to save the budget.

- **1 first pass:** the KRT chain in step 2.
- **Up to 3 re-route attempts.** One attempt is one diagnosis
  (`diagnose-routing-failures`) and one targeted change: a retry command, a rip-up of
  one region, a parameter the diagnosis names. **Stop early when an attempt
  doesn't lower the unconnected count.** A second approach to the same stuck
  region rarely does better than the first, and never after two have failed.
- **Up to 2 cleanup rounds** (step 5), each a look → fix → re-verify.
- **About 60 minutes of wall clock** for the whole skill. Check the clock after
  each attempt, and stop at the next attempt boundary once it's past.

A placement failure (`check_reachability` says CAGED, or failures cluster at
one part's escape face) ends the attempts at once. So does congestion that
`layer_capacity.py` confirms: the worst cut over its target on the signal
layers means more attempts can only succeed by using the plane. That outcome
is **Needs more layers**. Say so, because more
routing won't fix it; it needs `pcb-placement`.

**Asking to continue.** At good-enough or out-of-budget, hand back first: the
board, the table, and every remaining connection with its net, pads, location
and why it's stuck. Then ask one question (AskUserQuestion when you have it):

- **Keep going:** another budget of 3 attempts, aimed at the named remainder.
- **Stop here:** I'll finish these by hand. Say which are easiest by hand.
- **Back to placement:** when the remainder is geometric.
- **Add layers:** when the remainder is congestion, and `layer_capacity.py`
  on the current board agrees the signal layers are full (L-37). Never offer
  "route over the plane" as the way to finish.

Put the recommended option first, with the reason, such as "the 6 left are
all one BGA's inner balls, which are fastest by hand". Don't ask before
good-enough or before the budget is spent. Asking mid-run just interrupts the
bulk of the work.

## Before you start

1. **Update KiCadRoutingTools and read its playbook fresh**, exactly as
   `pcb-placement` does: `git pull --ff-only` (stop if the checkout is dirty),
   `"$KPY" build_router.py`, record the commit. Run KRT with KiCad's bundled
   Python (`$KPY`, defined in `pcb-placement`), which has KRT's dependencies.
   Then read
   `.claude/skills/pcb-free-agent/SKILL.md` and `plan-pcb-routing`. They hold
   the toolbox, the DONE conditions and the routing traps, and they change
   faster than this skill could track.
2. Load `ee-layout-rules`, then read `ee-layout-rules/rules/layout.md`: L-01…L-05
   (setup) and L-20…L-39 and L-43…L-49 (routing), plus L-40…L-42 on flex, are the rules this
   skill routes to.
3. **The rules are on the board before routing starts.** Run
   `$KPY <ee-skills>/skills/ee-layout-rules/scripts/board_rules.py check <board> --profile rigid|flex`.
   If it fails, run `pcb-placement` step 0 (apply, resolve the warnings,
   check again) before any copper goes down. A board routed against loose or
   missing rules has to be re-graded, and usually re-routed, once the rules
   arrive.

## 1. The routing spec

### 1a. Layer plan, before anything else (L-36, L-37)

Measure how many signal layers the board needs before deciding anything else,
because every later step assumes the answer:

```bash
C=<ee-skills>/skills/ee-layout-rules/scripts/layer_capacity.py
$KPY $C <board> --plane-nets GND --plane In1.Cu --json review/routing/capacity.json
```

It cuts the board every 0.5 mm in both axes and counts the nets that must
cross each cut, against how many tracks fit across it on each layer once pads
and vias are cleared. It prints the worst-cut utilization for each choice of
plane layers and recommends the fewest signal layers under 60% *(draft)*. On a
routed board, add `--pre-route` so the vias from an earlier attempt don't count
as blockage. Pass `--pitch` as the Default class's track plus the router
clearance you'll use.

- **On four or more layers, at least one layer is a solid GND plane.** On four
  layers that's normally In1.Cu, next to the parts. A second plane (In2.Cu for
  power) only if capacity still fits.
- **If the recommendation has no plane, stop and ask.** The board needs more
  layers or a different placement. Don't route it without a plane.
- **A request that takes the plane is a decision, not a default.** If the
  human asked for signals on the plane layer ("PD on layers 2-4"), show them
  the capacity table and the trade-off, and let them choose.
- **The plane has to survive its vias.** Read the `plane` block: copper left
  along the worst cut, and webs between antipads. Re-run after fanout, when the
  fanout vias exist.

Write the chosen plan into the spec: which layers are planes, which carry
signal, and the capacity numbers that justify it.

Write each item to a file in `review/routing/`, with its source. KRT only
grades against the specs it's given: without them, widths grade at the fab
floor, and KRT once read 141 of 141 vias as clean against a 0.6 mm spec.

KRT has an analysis skill for each item. Use them: they know how to classify
nets from the board, and they emit the exact flags the router takes. Read each
one's SKILL.md from `~/git/KiCadRoutingTools/.claude/skills/<name>/` and run
its commands from inside the checkout with `$KPY`. They aren't discoverable
from a session started anywhere else, and they assume the repo root.

**One substitution, everywhere: where a KRT skill says to WebSearch a
datasheet, read `datasheets/<MPN>/capture.json` instead.** Run
`datasheet-extraction` for a part that has none. A current, impedance or pin
function recalled from a search result is a lead, not a fact, and a wrong one
gets routed into copper. Where KRT's classification and the capture disagree,
the capture wins. Write the disagreement into the spec file so the next run
doesn't argue it again.

| Spec item | KRT skill | What it gives you | What to check against the capture |
|---|---|---|---|
| Power nets and widths | `analyze-power-nets` | which nets are power, `--power-nets` / `--power-nets-widths` | each rail's peak current, from the human or the capture of the part it feeds, then width at the copper weight (L-21, computed in Python and printed). Also put it in `--net-min-widths`. |
| Diff pairs | `identify-diff-pairs` | pairs found by pin function (catches pairs with non-`_P`/`_N` names), impedance, intra-pair match, `polarity_swappable` | the pin functions in the capture's pin table; the interface's impedance |
| High-speed nets | `find-high-speed-nets` | speed tier per net, which nets need controlled impedance or length matching | the interface clock/edge rate from the capture's electrical characteristics |
| Stackup | `recommend-stackup` | whether the target impedances are buildable, `--impedance` values | the fab's real stackup; ask the human which fab |
| Planes | `recommend-plane-mappings` | net → plane layer with the return-path reasoning, as a `RESULT=` line | the rails' currents from the power-width step |

**Put the spec into the board, not only into files.** Each width decision
becomes a net class (`Power`, or `PWR_0p5` and so on, one per width) with
`netclass_patterns` assigning the rails (L-03). Signals stay on Default (L-20).
KRT reads the classes from the `.kicad_pro`. When
`--track-width` is left off, `route.py` routes each net at its own class width
and honours the class clearances. Keep `--net-min-widths` on the graders too,
so necks get counted.

Also:

- **Widths are requests.** After routing, read `power_widths.<net>.under_mm`.
- **Length and time groups**, where an interface needs them (from
  `find-high-speed-nets` and the interface spec).
- **Decide planes before routing** (L-23): the layer plan in 1a does it.
- **Critical nets** (L-49). Write the `critical-nets:` list into
  `review/routing/spec.md`: every critical net on the board, not only the
  ones that cross between blocks. Go through the schematic and the captures
  for each kind L-49 names (diff pairs, shunt Kelvin sense, gate drive with
  its return, bootstrap and switch nodes, ADC inputs and reference, ADC and
  isolator clock and data, clocks and crystals, feedback and sense lines,
  and whatever a capture's layout guidance names). Each entry gives the net
  or nets, the rule, the layers and the corridor, and how it will be routed
  (by hand, or an exact scripted path). Show the list to the human before
  routing it.
- **Rough in the planes before any signal routing** (L-23, L-36), and fill
  them. Don't just decide them. Draw the GND and rail zones on the layers the
  plan gives them, rails as one hand-drawn outline per rail per layer from the
  power tree, around the pads the rail feeds (not a coarse rectangle per
  region, which makes the router reach out to the pads it left out), fill them (`pcbnew.ZONE_FILLER`, or `route_planes.py`), and
  only then route. Leave a plane out of a region only where the layer plan (1a)
  makes that layer a routing channel there, and write the region down in the
  spec. A plane added after routing lands as fragments around the tracks.
  Meanwhile the router has spent its effort wiring GND and the rails as
  tracks, and those become the opens. Measured on a 6x8 sensor-array main board (2026-09-28):
  signals first with no planes gave 74 unconnected, 22 of them GND. With GND
  roughed in and filled first (F.Cu and In1/B in the host region, the PD layers
  kept free over the array), the same run gave 57, with 6 GND. One zone per
  net per layer (L-23): where the plan needs a channel, cut it out of the one
  zone, or leave the plane out of that region. Don't stack a second same-net
  zone over the first to change it locally; use a rule area. On a 6x8 array board
  (2026-09-29) two priority-1 GND zones stacked on the board-wide fills left
  seams at x = 62 (B.Cu) and x = 56.5 (F.Cu), and the human deleted both.
- **Edge ground ring** (L-38). Keep the outer band for GND. Pass
  `--board-edge-clearance <edge_ring.margin_mm>` (1.0 mm rigid, from
  `drc.json`) to every routing step, so no signal or power copper goes into
  the band. Draw the ring with the planes: a GND pour or track in the band on
  F.Cu and B.Cu. Its stitching vias come from the final pass (L-43). List
  the edge parts that are allowed in the band (connectors, overhanging
  modules). A board too small for a ring says so in the spec, and the graders
  run with `--edge-margin 0`. Measured on a 6x8 sensor-array main board (2026-09-29), routed at a
  0.25 mm edge clearance with no ring planned: 52 signal and power pieces in
  the 1 mm band, GND on only 53% of the F.Cu ring path, and 1 stitching via
  around the whole board. Copper left in the band is a warning by default
  (`edge_ring.margin_severity`): move it or list it with its reason. If the
  spec says the band is strict on this board, grade with `--edge-margin-fail`.
- **Stitching, last** (L-43). Plan it in the spec (pitch, via, layers, and any
  region that stays via-free, such as under a fine-pitch part or a cover
  keep-out that forbids vias), but lay it only after routing is closed (step
  2.6). This overrides KRT `plan-pcb-routing`'s advice to stitch only
  high-speed boards at its 20 mm default. On this house's boards, the pours
  on the outer and inner layers must be tied to the plane whatever the speed
  tier. Measured on a 6x8 sensor-array main board (2026-09-29): with no stitching, the F.Cu GND
  fill over the array came to 36 mm², because island removal deleted the
  rest, and In2 filled as two halves. A human then added 529 vias at a 1 mm
  stagger. That pitch became the default and, on the four encoder test
  boards, littered them with vias; the human review of 2026-10-04 set it to
  `stitch.area_pitch_mm` (2.0 mm) with the 0.6/0.3 via. Write the pitch in
  the spec. Coarser, up to `stitch.area_pitch_max_mm`, is fine on a small,
  slow board. Tighter is only for a high-speed or RF return path: name the
  region, the pitch and the reason, and lay that region with
  `stitch.py add --pitch`.
- **Via sizes** (L-32). Every net routes with the Default and Power class
  via, the first `drc.json` `vias` entry (0.6/0.3, no added cost at JLC).
  List every place that needs a smaller via, with the geometry that forces
  it: the part, its pitch, and why the default doesn't fit. A 0.2 drill for
  a tight fanout or channel; a 0.15 drill only for a genuine fine-pitch
  escape or via-in-pad. Scope each with a rule or class (L-04), and pass
  `--via-size`/`--via-drill` only to the step that routes that region,
  because KRT otherwise takes the Default class via. A test board normally
  lists none. `check_copper.py` `small-via` (step 3) must then find vias
  only in the places listed.
- **Via-in-pad** (L-30). No via goes in an SMD pad or paste aperture, same
  net included. A pad that needs one (filled and capped) is named on one line
  of the spec, `allow-via-in-pad: U1.33, U4.5`, which `check_copper.py`
  `via-in-pad` reads from `review/routing/spec.md`. Thermal vias in an exposed
  pad's paste-free cross and vias in bare test pads need no entry.
- **A via for every power and ground pin** (L-39). Each pad on a rail, and
  each ground pad, gets its own via to the plane or pour: one per pin by
  default, in the pad only as a declared via-in-pad, otherwise adjacent
  (ring to pad edge ≤ `pin_vias.stub_target_mm`, 0.5 mm, and within
  `pin_vias.max_track_mm`, 1.5 mm, of its own track) on a stub at least the
  smaller of the pad's narrow side and `pin_vias.stub_min_width_mm`. A pad
  reached only through a same-layer pour, or chained to a neighbour's via,
  doesn't count. Write down the pads that can't take a via, and why (ground
  and low-current power pads only). List every pulsed or high-current pad
  with its current and source on a `pad-currents:` block of the spec
  (`Q1.5 = 6 A (capture)`), and give each `ceil(I / pin_vias.via_amps)` vias:
  1.5 A takes three 0.6/0.3 vias. The table is in
  `ee-layout-rules/references/fab-and-layout-defaults.md` §3. Measured on a 6x8 array board (2026-09-29), routed before this rule: 110
  of 207 power pads without their own via, among them all 48 taxel anodes fed
  from an F.Cu bus, and 97 of 111 ground pads reaching GND only through the
  F.Cu pour.
- **Layer jobs** (L-26), from the layer plan: each copper layer is a plane or
  a direction, H or V, with adjacent signal layers opposite. Write them to
  `review/routing/layers.txt` as one line, `F.Cu=H,In1.Cu=plane,In2.Cu=H,B.Cu=V`,
  which is exactly what `check_copper.py --directions` takes.
  - **Directions.** KRT can't take a direction per layer. It alternates H, V,
    H, V down the order of `--layers`, so the order F.Cu In1.Cu In2.Cu B.Cu
    gives F=H, In1=V, In2=H, B=V. With a plane on In1, that puts the one
    adjacent signal pair, In2 and B, at right angles, as L-26 wants. Pass the
    same order to every step. The preference is a soft cost
    (`--direction-preference-cost`, taken by `route.py` and `route_diff.py`).
    Read its current default in `py_router/routing_defaults.py`, because KRT's
    playbook and code have disagreed on it, and record the value used.
  - **Plane layers are forbidden** (L-36). Pass `--layer-costs` in
    `--layers` order with `-1` on every plane layer, GND and rail planes
    alike, in every KRT step, for example
    `--layers F.Cu In1.Cu In2.Cu B.Cu --layer-costs 1.0 -1 3.0 3.0`. A high
    cost (100) is not enough: on a motor-driver board (2026-10-22) KRT still welded
    GND and the rails with chains of short repair tracks on In1 and In4. Turn
    KRT's in-run island welding off too (`KICAD_PLANE_FINALIZE=0`). The other
    costs are yours to set; record them all.
  - Grade both in step 3, rather than trusting the settings.
- **Floors and sizes** are `ee-layout-rules/rules/drc.json`, which the
  `board_rules.py check` above has confirmed are on the board. Via-in-pad goes
  only where L-30 says. Going below a floor is sometimes right around a
  fine-pitch part: do it in a scoped `.kicad_dru` rule (L-04), and disclose it.

A two-layer board with no fast interfaces needs only the power-width and plane
rows. Say so and skip the rest, rather than running every analysis for the
sake of it.

## 2. First pass — planes, critical nets, then KRT

The autorouter is for the bulk, not for the planes or the critical nets (L-36,
L-49). KRT's `pcb-free-agent` skill in `route` mode, which never moves a part,
may run step 4 below, after steps 1 to 3 are done and locked. Its toolbox and
traps apply throughout. Its stop rules don't: use the budget in "Success,
and when to stop" above.
From inside the checkout that is
`/pcb-free-agent route <abs board> <abs floorplan.json>`; from anywhere else,
follow its SKILL.md.

**Either way, the order is L-36's, and each step is checked before the next.**
If you use `pcb-free-agent`, hand it a board with steps 1 to 3 done and
locked, give it the layer order and the layer costs, and check its manifest
didn't touch the locked copper or the plane layers. If you run the chain yourself:

1. **Planes, rails and pin vias, drawn, not routed** (L-36 step 2), with the
   edge ground ring (L-38): draw the ring in the edge band on the outer layers
   alongside the plane. Draw the GND plane and the rail shapes as zones in
   code or in pcbnew, and fill them. Then the pin-via pass: lay each power and
   ground pad's own via, or as many as its `pad-currents:` entry needs (L-39),
   with a script that places each via adjacent to its pad on a stub and
   checks clearance before it commits, or by hand. A pad outside its rail's
   shape gets a track at the rail's class width on a signal layer to its own
   via. Don't run `route.py --nets GND <power nets>` to do this: a router
   pass over the plane nets is what welds them with track on the plane
   layers. Check with `check_copper.py` (`power-pin-via`, `gnd-pin-via`,
   `plane-track`), refill, and confirm the plane is whole and the plane nets
   have no opens before going on (L-23, L-35).
2. **Fanout, all of it, before any track** (L-47, L-39, L-43). On a board
   with a BGA, a WLCSP or a repeated cell array, run `hdi-breakout` first: it
   plans and places this group and writes the `breakout:` block of the spec,
   and this step only checks that the group is there and locked. Otherwise decide per ball
   ring: outer ring on the surface with a dogbone to a via wholly outside the
   ball field, inner rings via-in-pad at the ball centre (declared on the
   spec's `allow-via-in-pad:` line). Place every fanout via, the vias at every power
   entry (two or more per
   rail, L-21) and, on an HDI stack, the shared GND taps, as one locked group with
   the pin vias from step 1.
   `bga_fanout.py` / `qfn_fanout.py --component <ref>` for each BGA, WLCSP, QFN
   and dense connector, with the layer order from step 1, so the escape vias
   land on real plane fill. Check the group with `check_copper.py`
   (`via-over-pad`, `via-in-pad`, `entry-vias`, `power-pin-via`,
   `gnd-pin-via`) before the first track exists: a via that overlaps a pad
   partway is a defect even when DRC passes it, and it is cheapest to move
   now. On a stack with blind or buried vias KRT cannot do this step or the
   next (it has no blind/buried support); the sensor-array board used its own
   project router, which honours the same rules
   (via at a pad centre or outside it, pads as leaves, ends at via centres)
   and is graded by the same checks afterwards.
3. **Critical nets, deliberately** (L-49). Every entry of the spec's
   `critical-nets:` list, before any autorouting: by hand in pcbnew (the
   interactive router `X`, the diff-pair router `6`), or as an exact path a
   script lays along the corridor the spec names. `route_diff.py` or
   `route.py --nets` on one entry at a time is allowed only as a draft that
   you then inspect and accept or redo; never a batch of critical nets in one
   pass. Render each one, check it against its L-49 line (pairing, loop,
   where a Kelvin pair leaves the shunt, what it runs past), then lock it.
   Record each entry's result in `review/routing/critical.md`. Show the
   human the critical copper before step 4.
4. **Everything else.** `route.py --nets '*'` with the layer costs (plane
   layers `-1`), `--keep-input-copper`, and no `--track-width`, so the net
   classes set the widths. This is the only unattended autorouting step.
5. **Congestion.** If step 4 leaves nets open and the diagnosis is congestion,
   re-run `layer_capacity.py --pre-route` on the result. If the worst cut is
   over its target on the signal layers, the outcome is **Needs more layers**.
   Lowering the plane cost to push the rest through isn't a fix.
6. **Stitch, last** (L-43). Once 0 unconnected and the step 3 gates pass on
   the routed copper, lay the grid as one group:
   `$KPY <ee-skills>/skills/ee-layout-rules/scripts/stitch.py add <board>
   --profile rigid|flex`. Don't use KRT's `--stitch-vias`. Refill, and run
   step 3 again. Every routing change from here on starts with
   `stitch.py remove <board>` and ends with `stitch.py add` again, so the grid
   never gets in the router's way, and a grid that moved around new copper is
   never half-stale.

From step 2 on, pass `--keep-input-copper --no-stub-layer-swap` (`route.py`,
`route_diff.py`), so a later step can't rip or layer-swap an earlier one's
copper (the third trap below).
Pass every spec flag from step 1 to each step and to the graders, and pass
`--no-fix-drc-settings` to every step that accepts it, so KRT can't loosen the
board's floors mid-run. In round-1 testing, `bga_fanout` silently lowered
`min_clearance` from 0.15 to 0.10.

Three more KRT traps, all measured on a 6x8 array board (2026-09-28):

- **KRT checks copper-to-copper only, not plated-hole clearance.** At a 0.20
  house hole clearance, routing at 0.125 (which is exactly 0.20 from a 0.30/0.15
  via hole) left 199 `hole_clearance` hits from diagonal rounding. Route at the
  Default-class 0.15.
- **`--escalation board` walks clearance down to the board floor.** It went to
  0.10, which brings the hole hits back. Use `--escalation off` when the floor
  is below what hole clearance needs.
- **A second `route.py` pass rips and layer-swaps the first pass's copper.**
  The result was 91 shorts. Stage passes with `--keep-input-copper
  --no-stub-layer-swap`, and DRC each stage's board on its own.
- **KRT rewrites the output board's project file.** Even with
  `--no-fix-drc-settings`, every `route.py` output `.kicad_pro` came back with
  `min_hole_clearance` at 0.15 against the house 0.20, and a
  `kicad_routing_tools.fab_floor_origin` block. A DRC of a stage copy grades
  against the looser floor, and hid 37 pour-to-mounting-hole hits on a 6x8 array board
  (2026-09-29). Grade every stage against the human's own `.kicad_pro`: copy
  only the `.kicad_pcb` back, and re-run `board_rules.py check`.
- **KRT won't `--force-reroute` a net that carries locked copper**, such as a
  pre-laid via-in-pad, even when you name it exactly. Rip its unlocked copper
  yourself, then route it with `--keep-input-copper`.

Capture every routing step's output, `2>&1 | tee review/routing/<step>.log`.
Without the logs, a failure can't be diagnosed.

**When nets fail, diagnose before retrying.** Each diagnosis plus the change
it leads to is one attempt against the budget. Follow KRT's
`diagnose-routing-failures` with the board and the step's log. It reads the
JSON summary, the failed-net histories and the blocking reports, sorts the
failure into its type, and gives a targeted retry command. Note that
`open_single` counts as a failure even when `failed_single` is empty. If it
comes back as a parameter failure, run its retry. If it's a placement failure
(geometry at the floor, failures clustered at one part's escape face,
`check_reachability` says CAGED), go back to `pcb-placement`, because a finer
grid never widens a gap.

## 3. Verify

A board can be DRC-clean and disconnected, so run both checks every time:

```bash
$KPY py_router/check_connected.py <board>
$KPY py_router/check_drc.py <board>
$KPY py_tools/board_score.py <board> --json review/routing/score.json <spec flags>
kicad-cli pcb drc --refill-zones --schematic-parity --severity-all --format json -o review/routing/drc.json <board>
# copper hygiene: DRC passes all of this
$KPY py_router/check_weird.py <board> --thorough --max-print 0 > review/routing/weird.txt
$KPY <ee-skills>/skills/ee-layout-rules/scripts/check_copper.py <board> \
    --directions "$(cat review/routing/layers.txt)" --json review/routing/copper.json
```

The last two grade the copper itself, which DRC and connectivity don't, and
neither of them covers everything alone:

| Defect | Rule | Caught by |
|---|---|---|
| exact duplicate segments and vias | L-34 | `check_weird` `stacked-copper` |
| dangling ends and vias | L-34 | `check_weird` `dangling-end`, `dangling-via`; KiCad DRC |
| removable copper and loops, on nets without a zone | L-34 | `check_weird` `removable-segment`, `redundant-cycle` |
| segments lying alongside or folded back over their own net | L-34 | `check_copper` `overlap` |
| loops on nets with a pour, which `check_weird` skips | L-34 | `check_copper` `loop` |
| track on a layer where the same net is poured | L-35 | `check_copper` `plane-track` |
| track ends inside a via but off its center | L-33 | `check_copper` `via-off-center` |
| a via drilled smaller than the Default class via outside a place the spec names | L-32 | `check_copper` `small-via` |
| a via in an SMD pad or paste aperture, same net included, not declared via-in-pad | L-30 | `check_copper` `via-in-pad` |
| bends sharper than 90°, 90° corners, off-angle track | L-25 | `check_copper` `sharp-bend`, `right-angle`, `odd-angle` |
| widths in no class and not on the list (hand tapers) | L-20 | `check_copper` `off-list-width` |
| a layer's length not on its declared axis; a net running more than 3 mm on a plane layer | L-26 | `check_copper` `direction` |
| signal or power copper within the edge margin; the GND ring missing or broken; ring stretches without stitching vias | L-38 | `check_copper` `edge-margin`, `edge-ring`, `edge-stitch` |
| a power pad without its own via; a ground pad without one; one via shared by several pins | L-39 | `check_copper` `power-pin-via`, `gnd-pin-via`, `shared-pin-via` |
| a GND fill island with too few vias to the plane; a GND zone that fills little of its outline; a pour cut into two large islands by one track | L-23, L-43 | `check_copper` `pour-island`, `pour-fill`, `pour-split` |
| same-net zones stacked on one layer; stitching vias outside the stitch group, or no group at final | L-23, L-43 | `check_copper` `zone-overlap`, `stitch-group` (`--stage final`) |

Record each category's count in `progress.json` alongside the unconnected
count. KRT's grid router leaves off-center via ends as a matter of course, so
report that count rather than chasing it to zero.

KiCad's own DRC is the final word: it reads the board's own rules, which KRT's
checker approximates. **Grade the file as saved.** Refill and save first
(`kicad-cli pcb drc --refill-zones --save-board`), then run the graded DRC
without `--refill-zones`. A DRC that refills its own copy passes a board whose
saved fills are stale, and the Gerbers come from the saved fills. On a 6x8 array board
(2026-09-29) the stale fills shorted two nets to GND while every refilled DRC
read clean. Refill again after any rule change too: a pour fills to the
clearance in force when it was filled.

**Scope every `.kicad_dru` exception to the geometry that forced it.** Use a
named rule area over exactly that geometry, such as one box per BGA/WLCSP ball
field, with `enclosedByArea` / `intersectsArea`, and `A.Type != 'Zone' &&
B.Type != 'Zone'`. A courtyard glob (`intersectsCourtyard('U1??')`) matches
every pour that touches the part. On a 6x8 array board it carried a 0.10 clearance to
92 nets up to 11 mm away. An `||` between the two items' conditions makes a
rule board-wide. Probe each rule both ways: make it extreme (it must fire only
inside its area) and delete it (it must be doing something).

## 4. Look at it

Render the board the way a layout engineer looks at it: every copper layer
composited and coloured by layer, tracks at their real width, pads and vias
drawn. A per-layer, per-net diagram hides the thing being judged. In review, a
routed board shown that way read worse than a less complete board shown as
copper.

```bash
R=<ee-skills>/skills/pcb-routing/scripts/copper_render.py
# whole board, all layers, pours left out so tracks under a plane are visible
$KPY $R <board> review/routing/all.png --ppmm 20 --nozones
# a zoom on every fine-pitch part, every connector and any congested region;
# 40-60 px/mm reads 0.1 mm tracks
$KPY $R <board> review/routing/zoom_U2.png --view x0,y0,x1,y1 --ppmm 45 --nozones
# one per copper layer, pours included, for plane integrity
$KPY $R <board> review/routing/In2_Cu.png --layers In2.Cu --ppmm 20 --fill
# the assembled look, silk included:
kicad-cli pcb render --side top --quality high -w 2400 -h 1600 -o review/routing/top.png <board>
```

`copper_render.py` reads geometry through `pcbnew`, so it is exact. It also
avoids `route_render.py`'s crash on zero-size pads.
Refill before judging pours (`--fill`, or `kicad-cli pcb drc --refill-zones
--save-board` on a copy), because a routed board may ship unfilled.

Open every image. Write a verdict for each region and layer, either **looks
good** or issues with the L-rule, net, layer and (x, y) in board mm. Judge it as
a layout engineer would sign it off, not only as DRC does, against L-20…L-39:
lanes (L-25), layer discipline (L-26), escapes (L-27), power and return (L-21,
L-23, L-24, L-28), redundant copper and plane nets (L-34, L-35), and silk
(L-18).

Look for these by name. Each has turned up on a KRT-routed board, and none is
a DRC error:

- a hook around a via, or a U-turn that runs away from its target and back
  (L-25);
- a V-shaped hairpin where a branch doubles back (L-25);
- vias scattered at random instead of in a row at lane pitch (L-25);
- 45° runs heading opposite ways on one layer, crossing each other (L-26);
- a fat blob or taper on a plane net, built from stepped widths (L-20, L-35);
- a wide track with a notch where a second copy of it ends (L-34);
- two paths from one via to the same trace, making a parallelogram (L-34);
- ratsnest lines still showing, above all on GND after the refill (L-35);
- every layer full of track and no layer that reads as a plane (L-36, L-37).

Vision proposes and a script confirms: a visual issue is a `fail` only when a
measurement agrees, and a `warn` with the image otherwise.

Then spawn a subagent for a fresh `layout-review` at `stage: routed`. Give it
the spec files from step 1. Its step 4a runs KRT's `review-routed-board`
checkers (length match, return vias, impedance, diff pairs) against those
specs, so don't run that skill separately here.

## 5. Clean up

**Remove the stitch group first** (L-43) if the board has one:
`stitch.py remove <board>`. Clean up, then `stitch.py add` again as the last
change before grading. Never re-route through a stitching grid, and never
patch individual stitching vias by hand. Regenerate the whole group.

**In code** where KRT has the lever: rip up and re-route a net set, repair a
broken plane by fixing its zone outline or moving what cut it (not with
`repair_planes.py` or any other router track on the plane layer, L-36), clean up copper, or reconnect with the
KiCad oracle. KRT's playbook lists these. `route.py`'s own cleanup pass removes
what `check_weird` calls removable.

**Copper hygiene, in this order:**

1. **Plane-net track (L-35).** Delete the track `check_copper` lists as
   `plane-track`, refill, and re-check connectivity. If the net opens, the
   plane is broken: fix the zone outline or move the copper that cut it,
   rather than putting the track back or letting a router weld it.
2. **Duplicates, overlaps, fold-backs, loops, zero-length pieces (L-34).** In
   pcbnew, Tools → Cleanup Tracks & Vias clears most of them. Re-run both
   checkers after it, and take out by hand what's left.
3. **Via centres, pads as leaves, staircases (L-33, L-48, L-25).** Every
   `via-off-center` end (free or tee) moves to the via centre; every
   `pad-junction` on a ball is re-routed so the trunk passes beside the pad
   and the ball hangs off it by one stub; every `staircase` and `jog` is
   straightened into one run with single 45° bends. A grid router leaves all
   three, so budget this pass; it is where the reviewer's eye goes first.
4. **The rail numbers (L-21, L-45).** `rail_check.py --rails` for each rail's
   IR drop and `--bus` for each I2C/SPI segment's capacitance and rise time,
   from the routed copper; both go in the handoff with the per-pin and per-mm
   figures used.
3. **Tapers (L-20).** Replace each stepped chain with one segment at the net's
   class width.
4. **Layer direction (L-26) and hooks and hairpins (L-25).** These can't be
   patched in place. Rip up the region's nets and re-route them with the layer
   order and direction cost from step 1, then grade again. If a layer still
   misses its axis, say so in the handoff rather than loosening `--min-axis`.

**Straighten before you grade (L-25).** A grid router ships two kinds of
geometry the house rules reject. The first is chains of tiny 0/45 jogs, which
read as curves. The second is short any-angle taps where the grid meets an
off-grid pad centre. After every routing pass, and before DRC:
1. De-stair. For each chain of segments on one net and layer whose inner
   joints touch no pad, via or tee, rebuild it greedily as the fewest 0/45/90
   doglegs that clear all other-net copper (and hole clearance to NPTH holes).
   Keep the chain ends fixed, and revert any rebuild that would orphan a tee.
2. Snap. Replace each remaining any-angle segment with a 45-then-straight or
   straight-then-45 dogleg. The endpoints stay fixed.
3. Gate. Fail on any arc, any segment off 0/45/90, or any chain of 3 or more
   jogs each under 0.3 mm. Arcs are allowed only where L-25 allows a curve.
   Re-run DRC and confirm that the unconnected count didn't move.
Measured on a 6x8 sensor-array main board (2026-09-28): KRT left 808 staircase chains and 52
any-angle taps. De-stair took 8,726 segments down to 3,254, the snap fixed all
52, and DRC stayed clean with unconnected unchanged. A reference implementation
(`destair.py`, `snap45.py`, `check_angles.py`) lived with that project, not here. If a lane still wraps a hole after this, the hole is in the
corridor, and the fix is at placement.

**Hand-written copper follows the lanes (L-25).** A cleanup that closes an open
net with a wide diagonal slash has traded one defect for another. Re-render the
region after each change and compare it with the render before.

**Computer use in pcbnew** where it's available and the job is inherently
interactive: pushing awkward traces with the interactive router (`X`), tuning
and length-matching diff pairs (`6`, `7`, `8`), fixing a via fence or a neck
by hand, and tidying silk. Save with ⌘S, and close pcbnew before any script
reads or writes the board. Otherwise KiCad writes its in-memory copy over the
script's edit on its next save.

**A clearance the geometry genuinely can't meet** gets a scoped `.kicad_dru`
relaxation (L-04). Probe it as `layout-review`'s LAY-03a describes: exaggerate
it on a scratch copy and confirm DRC fires where the comment says and nowhere
else.

After every change, in code or GUI: refill (`--refill-zones --save-board`, or
`B` in pcbnew), save, and re-run step 3. Stop after 2 cleanup rounds, when a
round changes nothing, or at the wall-clock limit, whichever comes first. Then hand back and ask, as "Success,
and when to stop" says.

## Handoff

- The board, and whether it replaced the human's.
- **The layer plan:** the capacity table (worst cut, utilization per choice of
  planes), the planes chosen, the layer jobs, the layer order and costs, and
  the plane's copper fraction and thinnest web after fanout.
- **The outcome** (done / good-enough / out of budget), with routed % and
  `progress.json`: attempts used, what each changed, and the count after
  each.
- **Every remaining connection:** net, pads, (x, y), why it's stuck, and
  whether it looks faster by hand.
- The DONE table measured: unrouted, broken, KiCad DRC by type, vias,
  copper_mm, every `check_weird` category, and every `check_copper` category
  with the worst few by net and location. Include the per-layer direction
  table against the declared layer jobs, the layer order and the direction
  cost used. Include the specs graded against, every place the run went below
  the board's floors, and the KRT commit.
- Per-layer verdicts from the final look, the renders, and the `layout-review`
  findings with what was fixed.
- Any new DRU rule with its probe result.
- Every via size used, with its count (the `check_copper` via-size table),
  and where each smaller-than-default via sits and why (L-32).
- `via-over-pad`, `pad-junction`, `entry-vias`, `staircase` and `jog` counts,
  each at zero or with the ones left named and justified.
- The `rail_check.py` lines: each rail's IR drop to its farthest load and each
  bus segment's capacitance and rise time (L-21, L-45).
- The stitch group: via count, pitch and via size, the regions left
  via-free, and `pour-island` / `pour-fill` per layer after it.
- Next: `layout-review` at `stage: final` in a fresh session, then fab.
