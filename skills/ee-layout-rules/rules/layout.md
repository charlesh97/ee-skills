# Layout rules

How a board is placed and routed. `pcb-placement` and `pcb-routing` work to
these rules, and `layout-review` grades against them by ID. They are the
practice. The numbers KiCad enforces (floors, net classes, predefined widths and
vias) are in `drc.json` and appear nowhere else. A value here is one that Board
Setup doesn't hold.

Every rule is *(draft)* until signed off. Follow it anyway, but say so when one
drives a real decision. The reason matters more than the rule, because it tells
you what to do in the case the rule didn't anticipate.

Edit a rule here, and keep its ID. Skills and review findings cite IDs, so a
renumbered rule breaks every past finding. Retire a rule by marking it
*(retired)*, never by reusing its number.

---

## Setup — before anything is placed

**L-01 Rules on the board first.** Apply `drc.json` with `../scripts/board_rules.py`
before the first part moves, and `check` it. The placer, the router, DRC and
every review then grade against the same rules from the first move. Rules added
only after routing let a router work below what the fab builds, and nothing
flags it.

**L-02 Profile follows the material.** Polyimide is `flex`, FR-4 is `rigid`.
Ask for the fab, layer count and thickness if the board doesn't say. A
template's stackup is nominal, so replace it with the fab's before any impedance
work.

**L-03 Every rail has a net class.** Assign rails to `Power`, or to a class per
width, with `netclass_patterns`. A rail left on `Default` gets a signal's width.
Any net that needs a width, clearance or length limit carries it in a class or a
rule, because intent that isn't encoded isn't enforced, and the next revision
loses it.

**L-04 Exceptions are scoped `.kicad_dru` rules.** Anything tighter or looser
than `drc.json` in one place goes in a rule scoped to exactly that place, with a
comment saying what geometry forced it. It never becomes a global floor change.
Probe every such rule (layout-review LAY-03a), because a rule that does nothing
looks exactly like a rule that is satisfied. Relaxations you already know you'll
need go in at setup: via-in-pad at a fine-pitch BGA, a WLCSP escape, a
connector tail.

**L-05 Mechanical facts come from the human.** That means the outline, mounting
holes, keep-outs, height limits, and each connector's edge, position and mating
direction. Never invent an outline, because it belongs to the enclosure and not
to the layout. Record the source of each fact, and mark every assumed one.
Lock mechanically fixed parts before placing the rest. Around every mounting
hole, draw an outer-layer copper keep-out at the screw head or washer radius
plus 0.3 mm *(draft)* at setup, so no lane is routed under the head and then
has to be moved. *(draft, review 2026-10-21)* A metal standoff, SMT
spacer or mounting land is on GND, and it is tied to the GND plane by a ring
of evenly spaced vias on its land (six on a 3 mm land), placed with the
mechanical facts so the router works around them. A floating standoff is an
antenna bolted to the chassis.

---

## Placement

**L-10 Decoupling at the pin.** Each bypass cap sits at the power pin it serves,
on the same side, with the smallest loop and no via between cap and pin. The
package is minimised so that it can get this close. Placing it anywhere else
undoes the choice.

**L-11 Regulator hot loop as the datasheet draws it.** Input cap, switch,
inductor and output cap go in the layout the capture's layout-guidelines section
shows, with the loop area kept to a minimum. *(draft, amended 2026-10-23, from a
6-layer motor-driver board whose three bucks all failed this.)* The hot loop is
the one whose current switches every cycle: for a buck, the input cap, the VIN
pin and the GND pin (the `dcdc-layout` skill's `references/topologies.md` lists
the loop for each topology). Close it on the component layer with no via in it.
The high-frequency cap sits across its pins, each pad facing its own pin, within
1.0 mm of the pin's pad edge *(draft)*. Pin vias into the rail and ground planes
go beside the pads as extras (L-39). A rail shape on an inner layer feeds the
loop and is never part of it. State the loop area from the copper path, plan plus
vertical: 2.0 mm² or less on a QFN, SOT or TDFN buck *(draft)*. Lay each switcher
out as a cell first, from its datasheet figure, with the `dcdc-layout` skill, and
place the cell before the rest of the board is seeded. A placer clusters caps by
net, and a router closes loops through whatever plane is there, and both pass DRC.

**L-12 Zone noisy away from quiet.** Switchers, their inductors and switch nodes
are kept away from sensitive analog, crystals and feedback nodes.

**L-13 Crystal tight.** Load caps go beside the crystal on short traces, with a
GND guard or pour, and no signal under it on any layer.

**L-14 Connectors where the enclosure says.** At the edge and position given,
with pin 1 marked and the mating side clear of other parts.

**L-15 Test and debug access.** Test points must be reachable from the probing
side, and GND test points are loops. The debug header goes at an edge and has to
be reachable with the board in its enclosure.

**L-16 Untangle before routing.** Rotate or swap parts until the ratsnest stops
crossing where it doesn't need to, and fix crossed pin-order pairs first. Every
crossing left here becomes a via or a detour later.

**L-17 Assembly.** Courtyards don't overlap, and parts sit at least a pick
nozzle and a rework iron apart. Tall parts don't shadow small ones, and nothing
sits in the assembler's edge rail. A two-sided board is a stated choice, and the
bottom side carries only parts light enough for the second reflow. Each
assembled side gets **two or four** `FID` fiducials, never three *(Worker,
2026-10-22)*, placed asymmetrically.

*(draft; human review of the four encoder test boards, 2026-10-04)* The
fiducials go in the board's corners, not near the middle: two in
diagonally opposite corners, as near the edge as the edge rail, the edge
ground band (L-38) and the fiducial's own mask clearance allow, and that is
the default; four, one per corner, when the assembler asks for it. Either
way one of them sits off its corner's symmetric position, so the set is
asymmetric and the board can't be loaded rotated 180° without the vision
system seeing it. The assembler's
camera corrects offset, rotation and stretch from them, and that
correction is only as good as the baseline between them. A pair a few
millimetres apart near the centre fixes the offset and leaves the
rotation and scale almost unmeasured, so parts at the far edges land off
their pads. If a part sits where a fiducial belongs, move the part, not
the fiducial. Lock the fiducials with the mechanically fixed parts (L-05)
before seeding, so the placer works around them. On a panel the panel
rails carry their own fiducials, and each board still carries its corner
set.

**L-18 Silk.** Refdes are legible, consistently oriented, and not under parts.
Silk stays off pads and mask openings. Every polarised part carries a polarity
or pin-1 mark.

**L-19 Antenna keep-out**, if the board is wireless: clear of copper and parts on
every layer, per the module's datasheet.

---

## Routing

**L-20 Signals on the Default class.** Neck down to a smaller predefined width
only inside a fine-pitch escape, inside a scoped rule (L-04). Routing everything
at the minimum throws away the etch-tolerance margin for nothing. Every track
width is a net-class width or on the predefined list, and a width changes in
one step. A chain of segments stepping through in-between widths (0.1, 0.13,
0.16, 0.19 … 0.8) is a taper someone drew by hand. It's no stronger than its
narrowest link, and nothing on the board says why it's there.

**L-21 Power by current.** Size each rail's width by IPC-2152 from its peak
current (from the human, or the capture of the part it feeds) at the board's
copper weight. Compute it and state it. Never size a rail by the signal default,
and use at least 0.3 mm. Carry the current with enough vias at the
per-via current in `drc.json` `pin_vias.via_amps` (the method is L-39's), so
no rail hangs on a single via. *(draft, review 2026-10-21)* State each rail's
**IR drop** from the routed copper: the path
resistance from the source to the farthest load at the board's copper weight,
times the rail's peak current, against the rail's tolerance.
`../scripts/rail_check.py --rails` computes it (`rail-drop`). At every **power
entry** (a connector pin, a regulator output pad) a rail has at least two
vias, or the count from the per-via current, and the routing spec says which;
`../scripts/check_copper.py` `entry-vias` counts them. One via at the
connector is one via for the whole board.

**L-22 Diff pairs and length groups.** Pairs are named `_P`/`_N`, so KiCad's
router and DRC detect them. They keep a constant gap and have skew within the
interface's tolerance, with no unpaired stubs. Length-matched groups stay within
the interface spec, and the spec is cited.

**L-23 Planes decided before routing.** Plan the reference planes first, and
pour them first (L-36), so fanout vias land on real fill. A pour laid into the
gaps after signal routing is fill, not a plane. The GND plane is one polygon per layer, or its
islands are justified, and any neck is wider than the widest trace crossing it.
One zone per net per layer: never stack a second zone of the same net over
the first at a different priority. Change clearance or fill locally with a
rule area. A stacked zone leaves seams, fills from whichever zone wins, and
turns stale fills into DRC noise. Split a zone only for a different net or
for a routing channel the layer plan names. This applies to every GND pour on
every layer, not just the plane: a single track that cuts a pour into two
large islands is a defect, so move the track to the island's edge or onto
another layer. On a 6x8 array board (2026-09-29) one 3V3_LED trunk on In2 split the
In2 GND pour into 982 and 737 mm² halves, and moving it 0.7 mm joined them.
High-speed, clock, diff-pair and switch nets have a continuous reference plane
under their full length. Never put a split or slot under a diff pair or a
switch node. *(draft, review 2026-10-21)* A rail that feeds many loads
spread over the board (more than about eight, in more than one cluster) gets a
plane or a split-plane stripe on a plane layer, decided in the layer plan; a
routed trunk is for a rail with a few loads in one place. The sensor array's 1V8
trunk, 97 mm of 0.15 mm track hanging 44 pads, was the reviewer's first
complaint about the power.

**L-24 Return via at every layer change** on a critical net. State the distance
you held it to.

**L-25 Lanes.** Signals running the same way run straight and parallel, at an
even pitch, with 45° bends. Every track is a straight segment at 0, 45 or 90
degrees. There are no arcs, no curved or teardrop-style bends, and no any-angle
segments, unless the geometry truly needs a curve (a round board edge, a
circular sensor ring). Say which one it is when it does. A staircase of tiny
0/45 jogs is a curve by another name, and so is a lane that wraps an obstacle in
short steps. Both are defects: collapse them into long straight runs with single
45 degree bends. No bend is sharper than 90°. A 90° corner is for entering a pad
or where the geometry forces it, not the default. A track leaves a pad along
the pad's axis for at least the thermal gap plus a spoke width before its
first bend, and never through a position a thermal spoke needs on a pad that
connects to a pour. A 45° exit straight off the pad corner starves the relief. A trace that cuts diagonally
across other lanes, a hook around a via, a U-turn that runs away from its target
and comes back, or a loop around a part is a defect even when DRC passes it.
Vias that feed one lane group sit in a row at the lane pitch, so the lanes leave
them straight; vias scattered at random make lanes impossible. Keep holes, test
pads and fiducials out of lane corridors at placement time, because a hole in
the path makes every lane detour around it. Hand-added copper follows the lanes
too. When a net can't be closed tidily, rip up the neighbours and re-route the
region instead of patching across it. `../scripts/check_copper.py` counts the
staircases (`staircase`: more than two alternating 0/45 segments shorter than
three track widths) and the jogs (`jog`: two bends within three widths that
net to less than one pitch of lateral shift), so they are a number in the
report and not an impression from a render.

**L-26 Layer discipline.** Each layer has a job, either a direction (H or V) or
a plane. A board of four or more layers has at least one GND plane (L-37). Write
the jobs into the routing spec before routing, and give adjacent signal layers
opposite directions, so lanes on neighbouring layers cross at right angles
rather than running on top of each other. A plane layer may carry a short
signal hop where nothing else gets through, but the router prices it high
(L-36), and a net's track on a plane stays under 3 mm *(draft)*. A long run on
the plane cuts the return path of every signal above it. On a signal layer, lanes
run on its axis, and 45° is for bends and short jogs. *(draft)* At least 80% of
each inner signal layer's track length runs in its one fixed direction, with 45s
counted against it. This holds whatever laid the copper: any autorouter, a route
table or a hand. A router's direction setting is only a means to it, and none
holds it on its own, so grade the result. A wrong-way stretch walls off every
right-way lane it crosses: when a net has to go the other way, it changes layer.
Copper that must break this (a diff pair, power copper, a fixed critical path)
is named in the routing spec's `direction-exceptions:` line and left out of the
share. Outer layers carry parts and pin escapes, so their share is reported but
doesn't fail. `../scripts/check_copper.py --directions` grades the share and
lists the runs (one net's track chained end to end on one layer) that travel
less than two thirds along their layer's axis, as the places to re-lay; a layer
where H, V and 45° are all heavy has no job. Measured on a 6-layer motor-driver
board (2026-10-23): with an autorouter's soft direction preference, both inner
layers came out under 40% on axis with 167 runs mostly off axis, and about 50 of its
280 signal opens had no clean lane only because of those runs. Avoid needless layer changes, and
keep vias off pads (except required via-in-pad, L-30) and out of finger fields.

**L-27 Fine-pitch escapes are tidy and symmetric**, not a tangle of detours.

**L-28 Keep feedback away from the switch node.** The FB trace runs away from the
SW node and the inductor, and never under the inductor. Switch-node copper is no
bigger than the current needs. *(draft, amended 2026-10-23.)* This covers every
quiet regulator pin: FB, VOS or SENSE, COMP, and the strap pins (VSET, MODE or
S-CONF, RT, SS, ILIM). Their parts sit at the pin and return to the IC's quiet
ground. Past the first 1.0 mm of pin escape, none of these traces runs within
1.0 mm of switch-node copper on the component layer, or over the inductor's body
*(draft)*. Layers below the first solid ground plane are shielded and don't count.
Where the pinout puts the sense pin beside SW, leave the component layer through a
via inside the escape and come up at the output cap. Size the switch-node copper by
L-21 from the peak current limit, on one layer, with no vias. Encode it in the
board's `.kicad_dru` as `via_count (max 0)` on the SW nets and a clearance from FB
nets to SW. A sense line that taps the output cap as L-44 asks can still fail this
rule. On one board, a VOS line ran 5 mm beside the SW pad to reach a cap placed on
the inductor's far side.

**L-29 Heat goes to a plane.** Power and thermal pads connect solid, with no
thermal relief on a switch node or a high-current pad. Every exposed pad has
thermal vias to a plane, with count and pitch stated. Junction temperature
stays ≤ 110 °C at max ambient (the derating rule in `ee-schematic-rules`), from θJA with its board
condition from the capture. *(draft, 2026-10-23)* Some datasheets (TI's small
DCS-Control bucks) ask for thermal vias on the SW pin as well. Add them only when
the thermal budget needs them, and say so in the routing spec, because SW vias add
switch-node capacitance and put the node on every layer. Otherwise SW has no vias
(L-28). Exposed-pad vias sit in a paste-free window, or are filled and capped and
declared (L-30). A pad that carries paste on its whole area has its vias under paste,
whatever paste windows the footprint also draws.

**L-30 Via-in-pad and HDI only where the pitch needs them.**
`../references/fab-and-layout-defaults.md` §2 says when. Via-in-pad is filled and
capped (IPC-4761 Type VII) and called out on the fab drawing. HDI costs a
lamination cycle per build-up step, so it needs a stated reason.
*(draft, 2026-10-04)* Every other via stays out of SMD pads and paste
apertures, the same net included: no part of its annular ring overlaps an SMD
land or an opening in F.Paste/B.Paste. An open via in a joint wicks the solder
down the barrel and starves the joint. On two encoder boards a GND stitching via
sat in the mounting tab (J1.MP) of a JST GH; KiCad DRC passes a same-net via in a
pad, so only KRT's `VIA-IN-PASTE` caught it (2026-10-04). A pad may take a via
only when it is a declared via-in-pad: named on an `allow-via-in-pad:` line of
the routing spec (REF.PAD, filled and capped as above); an exposed or thermal
pad whose paste is split into windows the vias clear (the thermal vias of
L-29 sit in the paste-free cross); or a bare test pad with no paste.
`../scripts/check_copper.py` `via-in-pad` grades it: a via in a paste aperture
fails, one on land copper outside the paste warns.


**L-62 Every regulator part returns on the regulator's ground.** *(draft,
2026-10-23.)* Each input, output and bypass cap's ground pad reaches the
regulator's ground pin on the same net, through copper on the component layer
or through a plane of that net directly under it. A ground via that lands on
another net's plane connects nothing. DRC reports it as one open among hundreds,
and on one board an output cap sat that way, with its regulator running
uncapped. Where the datasheet separates analog and power ground (SGND and PGND
joined at the VCC cap's return, for example), the schematic gives them two nets
with a net tie at that point. The small-signal parts (FB divider, straps, soft
start, VCC cap) return to the analog side. A plane split drawn for another power
stage stays out from under a regulator's SW node and its caps' ground vias.
`dcdc-layout`'s `check_regulator.py` grades it.

**L-63 Enable and mode pins tied to VIN connect at the input cap.** *(draft,
2026-10-23.)* Connect them where the datasheet draws the tie, normally at the
input cap. They carry no current, so they are not power pads for L-39's via count,
and a routing spec's pad-current table doesn't list them.

**L-31 Fab values Board Setup doesn't hold.** Pad-to-pad on different nets
0.15 mm (0.10 in a scoped fine-pitch rule). Soldermask bridge 0.10 mm, or 0.13 on
black or white mask. Silk text 1.0 mm tall where there is room. Paste on every
SMD pad, and none on through-hole pads or fiducials. ENIG when pads are
≤ 0.25 mm or drills are 0.1 mm.

**L-32 Via choice: the no-added-cost via by default.** *(draft; rewritten
after human review of the four encoder test boards, 2026-10-04, which
found their 0.3/0.15 vias were never needed.)* Use the first entry of
`drc.json` `vias`, which is also the Default and Power class via: the
standard via with a 0.3 mm drill, which JLC builds at no added cost. It is
the via on every net of every board, and the only via on a test board.
Price is the reason: the drill sets the price at JLC, and a smaller drill
on a board that didn't need one is money spent on nothing. Keeping one via
size across a board also keeps the rules, the review and the stitching
simple.

Step down only where geometry forces it, and only there:

- **0.2 mm drill** (the second entry): allowed where the default doesn't
  fit, such as a 0.8 mm pitch fanout or a channel a 0.6 mm pad blocks. It
  adds cost. Scope it to the part or region with a `.kicad_dru` rule or
  a net class (L-04), and name the place and the geometry in the routing
  spec.
- **0.15 mm drill** (the third entry): additional cost, and only for a
  genuine fine-pitch escape (0.65 mm pitch and below) or via-in-pad
  (L-30), with the reason recorded in the routing spec. It is functional,
  so it stays available, but it is never the default.
- **0.1 mm drill:** JLC builds it only on a board under 1 mm thick. It isn't
  in the `rigid` profile; a thin board that needs it says so at setup (L-02)
  and carries it in a scoped rule.

The floors in `drc.json` still admit the smallest via, so a scoped use
passes DRC. That means DRC won't flag a small via where it wasn't needed:
`../scripts/check_copper.py` lists every via drilled under the default as
`small-via`, and each one must sit in a place the routing spec names.
KiCadRoutingTools takes its via from the Default class unless
`--via-size`/`--via-drill` override it, which is how a 0.3/0.15 Default
class put the fine via on every net of the encoder boards. So the class
carries the default via, and a smaller one is passed only to the step that
routes the scoped region.

**L-33 Tracks end at via centers.** A track that ends at a via ends at its
center, on every layer. Copper that only overlaps the via is a defect even though
DRC passes it: pcbnew doesn't treat the track as attached, so dragging the via or
push-and-shove leaves it behind and opens the net. It also leaves a notch on the
short side that can trap etchant, and a reviewer can't tell what was meant. Grid
routers produce this all the time, so check it with
`../scripts/check_copper.py` rather than by eye; it reports both a free end
and a T-junction that lands inside a via's pad off its centre
(`via-off-center`, kinds `free` and `tee`). A track entering a pad
off-center is normal and not covered here.

**L-34 No redundant copper.** Each connection is one path of copper. There are
no duplicate segments, no segment lying on or alongside another of the same
net, no segment folded back over itself, no same-layer loops, no zero-length
segments, and no dead stubs or dangling vias. A cleanup that adds copper
without taking out what it replaced leaves these, and so does pcbnew when
tracks are edited by hand. DRC passes all of them, but they hide what the
connection really is, they turn the next edit into a fight, and a stub is an
antenna. Find them with KiCadRoutingTools' `check_weird` (duplicates, dangling
ends and vias, removable copper) and `../scripts/check_copper.py` (overlaps,
and loops on nets with a pour, which `check_weird` skips). In pcbnew, Tools →
Cleanup Tracks & Vias removes most of them.

**L-35 Plane nets connect through the plane.** A net poured on a layer connects
on that layer through its pour, not through track laid over the pour. Track on a
net's own plane layer is a leftover, usually from routing before the pour, and
it hides whether the plane is doing its job. Take it out, refill, and confirm
the net has no unconnected items after the refill. A short stub is fine where a
pad can't reach the fill (thermal spokes blocked); say which. If a plane net
still has opens after refill, the plane is broken (L-23), so fix the plane
rather than patching the gap with track.

**L-36 Order of work.** Route in this order, and don't start a step until the
one before it is done and checked:

1. **Layer plan.** Capacity says how many signal layers the board needs
   (L-37). The rest are planes. Every layer's job and direction goes in the
   routing spec.
2. **Planes, rails and pin vias: drawn, not routed.** *(amended 2026-10-22,
   motor-driver board layout.)* Pour the GND plane, then power: a power plane where
   capacity allows one, otherwise rail shapes, one zone outline per rail per
   layer, drawn from the power tree (L-44) around the pads that rail feeds and
   sized by its current (L-21). Draw the edge ground ring with them (L-38).
   Then the pin-via pass: every power and ground pad gets its own via, or as
   many as its current needs, into its plane (L-39), laid by a script or by
   hand, not by a router pass over the plane nets. *(2026-10-23)* Switching
   regulators are laid as cells before this step (L-11, the `dcdc-layout` skill).
   A rail shape ends at a cell's entry and exit vias and never closes a cell's hot
   loop, and the pin-via pass skips the cell's pads. A pad outside its rail's
   shape reaches its own via by a track at the rail's class width on a signal
   layer; the plane is not stretched to it. Refill, and confirm the planes are
   whole (L-23) and every power and ground pad is connected (L-35). From here
   on no router puts copper on a plane layer: every plane layer is forbidden
   (layer cost -1, not merely priced high) in every routing pass, and the
   router's own plane repair and island welding are off. Plane-layer track a
   router drew is ripped out, never kept. On a motor-driver board (2026-10-22), with
   the plane layers only priced high, KiCadRoutingTools welded GND and the
   rails together with chains of short repair tracks on In1 and In4, and
   coarse rail rectangles pulled fat repair tracks out to outlying pads. The
   fix was hand-drawn rail shapes, a pin-via pass, and -1 on In1 and In4.
3. **Fine-pitch breakout.** BGA, WLCSP, QFN and connector escapes, onto the
   signal layers, with vias landing on real plane fill.
4. **Critical nets, deliberately** (L-49). Every net on the routing spec's
   critical list, not only the ones that cross between blocks: routed by hand
   or as an exact scripted path and looked at, while there is still room to
   route them well. Their copper is locked only during a parallel merge round
   (L-49). No autorouter runs before this step is done.
5. **Everything else,** by the autorouter if you like, on the signal layers
   in their directions, with the critical copper kept (locked on the stage
   copy for the pass only, L-49) and the plane layers forbidden. This is the only step an autorouter runs on its
   own.
6. **Congestion.** If step 5 can't finish because the signal layers are
   full, add layers. Don't route over the plane (L-37).
7. **Stitch, last** (L-43). Once routing is closed and clean, lay the GND
   stitching grid over every pour as one group. Before any later re-route,
   delete the group, route, then stitch again.

Signals first and planes last is what leaves a four-layer board with every
layer full of track and no plane. An autorouter first is what leaves the
critical nets routed for completion instead of for what they carry. Nothing in the pile of copper stops you
doing it, and the board still passes DRC.

**L-37 Layer count comes from capacity.** Before routing, measure how many
signal layers the board needs with `../scripts/layer_capacity.py`. It counts
the nets that must cross each cut through the board and how many tracks fit
across that cut on each layer. Use the fewest signal layers that keep the
worst cut under 60% full *(draft)*, and make the rest planes. A board of four
or more layers keeps at least one solid GND plane. If capacity says that
plane is needed for signal, the board needs more layers: say so and ask. Don't
give up the plane silently. When a request would take the plane ("put the PD
nets on layers 2-4"), show the capacity numbers and the trade-off, and let the
human decide. Run it again after fanout, when the fanout vias exist, and check
that the plane survives them: enough copper left along every cut, and webs
between antipads no thinner than the minimum track.

**L-38 Edge ground ring.** On most boards, keep the outer band of the board
for ground. No signal or power copper (track, via, pad or pour) comes within
the margin of the board edge on any layer: `drc.json` `edge_ring.margin_mm`,
1.0 mm on rigid boards *(draft)*. GND runs around the whole outline in that
band on the outer layers, as a pour or a track no narrower than the Power
class. It is stitched to the GND plane with vias no farther apart than
`edge_ring.stitch_pitch_mm`, 5 mm *(draft)*. Those vias come from the final
stitching pass (L-43), which covers the ring along with every other pour. The ring contains the board's
edge fields, gives the enclosure and cover a ground to land on, and takes an
ESD hit on the edge before it reaches a signal. It has to be planned: draw it
with the planes (L-36 step 2), and route with the router's board-edge
clearance set to the margin. A ring added after routing lands as fragments
between the tracks that already use the band.

What may sit in the band: parts whose courtyard touches or crosses the outline
(edge connectors, overhanging modules, headers) and the copper within the
margin of their pads, and mounting holes. Say so in the routing spec, and bring
the ring up to both sides of such a part. A board too small for the band (a
finger-sized sensor, a flex tail), or an outline that is all connector, skips
the ring. The routing spec says why, and `check_copper.py` runs with
`--edge-margin 0`. How strict the band is depends on the board. By default, copper in the band
is a warning: each piece is either moved or listed in the routing spec with
its reason. A board whose spec says the band is strict (an ESD-exposed edge,
a metal enclosure that clamps the edge) grades it as a failure. Grade it with
`../scripts/check_copper.py`: `edge-ring` (GND on under 90% of the ring path
on an outer layer) fails, `edge-margin` (copper in the band) and
`edge-stitch` warn, and `--edge-margin-fail` makes `edge-margin` fail. The
default is `drc.json` `edge_ring.margin_severity`.

**L-39 A via for every power and ground pin.** *(draft; amended 2026-10-22,
motor-driver board layout: one via per pin as the default for ground as well as
power, a via count by current, and a stated stub.)* Every pad on a power net
gets its own via to that rail's plane or pour, and every ground pad gets its
own via to the GND plane. By default that is one via per pin: a decoupling
cap has one power via and one GND via, an IC supply pin one, its ground pin
one. That covers decoupling capacitors at both ends, IC supply and ground
pins, regulator inputs and outputs, and connector power pins. Ground is not
optional: a ground pad without a via is a miss unless it is on the exception
list below.

*Count by current.* A pad whose current is more than one via carries takes
as many vias as its current needs: `ceil(I / I_via)`, never fewer than one,
where I is the pad's current (the same peak current L-21 sizes the rail with,
from the human or the capture of the part, stated) and `I_via` is the per-via
current in `drc.json` `pin_vias.via_amps` for the via used. For the house
0.6/0.3 via that is 0.7 A, so 1.5 A takes three vias and 5 A takes eight.
The method and the table are in `../references/fab-and-layout-defaults.md`
§3: the barrel's copper cross-section at the fab's plating (JLC 18 µm
average), rated as an internal conductor at a 10 °C rise, rounded down. A
smaller via carries less, so stepping down (L-32) means more vias. Pulsed
and high-current pads (motor and gate drive, LED drive, radio PA, a
regulator's input and output caps, a sense resistor, a connector power pin)
get their count first and never go on the exception list.

*Where the via sits.* In the pad only where it is a declared via-in-pad
(L-30): filled and capped, named on the routing spec's `allow-via-in-pad:`
line. Everywhere else (an unfilled via, fine pitch, a BGA land, a pad whose
reflow a via would starve) the via sits adjacent, as close as the clearance
allows: annular ring to pad edge 0.5 mm or less *(draft)*, and never more
than `pin_vias.max_track_mm` (1.5 mm) of the pad's own track. A BGA
dog-bone via in the diagonal between lands is adjacent. The pad joins its
via by a short, wide stub, at least the smaller of the pad's narrow side and
`pin_vias.stub_min_width_mm` (0.4 mm rigid, the Power class width), and on a
high-current pad wide enough for the pad's current by L-21. Several vias on
one pad sit in a row or cluster along its side, each on the stub or on a
small same-net copper tab off the pad, not strung out along a track. The via
connects solid to its plane, never through a thermal relief; a relief on the
pad's own-layer pour (L-29 allows one on an ordinary pad, for soldering) is
fine, because the via, not the pour, is the pad's connection.

A pad reached only through a pour on its own layer, or daisy-chained along a
track to a neighbour's via, does not count, and neither does one via shared by
two pins. Each pin needs its own short, low-inductance path to the plane, and a
chain puts every pin's current through the first pin's via. A through-hole pad
is its own via.

Where a pad genuinely can't take a via (a landlocked ball at a pitch below the
via floor with no via-in-pad, a pad already fed by a solid pour with no room
beside it), list it in the routing spec with the reason. The list is for ground
pads and low-current power pads only, and each one is a finding at review.

Power nets are the rails: nets in a `Power` or `PWR_*` net class (L-03, L-21),
or those the routing spec names. Grade with `../scripts/check_copper.py`:
`power-pin-via` fails, `gnd-pin-via` warns at `--stage routed` and fails at
`--stage final`, and `shared-pin-via` warns. The script finds a pad's nearest
via; the via count against current and the stub width are graded by hand at
review (layout-review LAY-56), from the `pad-currents:` block of the routing
spec (`Q1.5 = 6 A (capture)`). *(draft, review 2026-10-21)* The pin vias are
placed in the fanout step (L-47), before any track, as one group; a router
that is left to add them adds them where it finds room, which is not at the
pin. Plan the vias at placement: leave room beside every power and ground pad
for its full count, above all at the decoupling caps and the high-current
parts. Work in order of current: pulsed and high-current rails (LED drive,
motor, radio PA, a regulator's input and output caps) get their vias first and
never go on the exception list. *(2026-10-23)* A switching regulator's cell is
the exception to the pass: its hot-loop pads connect on the component layer and its
vias are part of its layout (L-11), so the pass skips its pads. An EN or MODE pin
tied to VIN carries no current and needs no via count (L-63). The `power-pin-via` report names the rail for
each pad, so the highest-current misses get fixed first.

**L-43 Stitch every GND pour, last, as one group.** Every GND pour on every
layer (outer-layer fill, inner pours, the edge ring) ties to the GND plane
through a grid of stitching vias: `drc.json` `stitch.area_pitch_mm`, 2.0 mm
staggered, with the no-added-cost 0.6/0.3 via (L-32) *(draft)*, laid
wherever a via fits clear of other copper, holes and via keep-outs. The
pitch was 1.0 mm, copied from a hand edit on a 6x8 array board. Human review of the
four encoder test boards (2026-10-04) found that stitching worked, but a
1.0 mm staggered grid littered the boards with vias, so 2.0 mm is the
default. A small, slow board may go coarser, up to
`stitch.area_pitch_max_mm` (2.5 mm). A tighter pitch is only for a
high-speed or RF return path (a via fence along an RF line, the return
under a fast edge), and the routing spec states the pitch, the region and
the reason; pass it with `stitch.py add --pitch`. No stitching vias go
in pads (the pin vias of L-39 are part of the connection, not stitching):
a stitching via clears every SMD land and every paste aperture by the
minimum clearance, the stitch net's own pads included, because an open via
in a joint wicks its solder away (L-30; a GND stitching via in J1.MP of a
JST GH on two encoder boards, 2026-10-04). `stitch.py` skips such points as
`smd-pad` or `paste`. A
pour that reaches the plane only through the odd component via isn't
grounded; with island removal on, KiCad deletes most of it, and the rest is
an antenna. After stitching, every fill island of at least
`stitch.min_island_mm2` has a GND via in it, and at least
`stitch.min_island_vias` from `stitch.two_via_mm2` up. No GND zone fills less
than `stitch.min_fill_ratio` of its outline. A sliver too small for a via is
removed by the zone's minimum island area, not left floating.

Stitching is the **last** pass (L-36 step 7), after routing is closed and
checked, because a dense grid blocks push-and-shove and every re-route
through it. Every stitching via goes in the single KiCad group named in
`stitch.group` ("GND stitching"), and nothing else goes in it. The whole grid
can then be selected and deleted in one action. Before any later routing
change: remove the group, make the change, refill, and stitch again.
Stitching doesn't replace a sound plane (L-23). It connects pours to the
plane, but it doesn't fix a plane that routing has cut.

*(draft, review 2026-10-21)* On an HDI stack with no through via
(laser microvias one layer deep plus buried core vias), the grid above can't
be laid: no single hole reaches from an outer pour to the plane. There the
stitching is a microvia in every GND pad (L-39), an outer GND pour that those
microvias tie together, and one shared buried tap per cell from the breakout
layer to the GND plane, placed in the fanout step where it clears the other
fanout vias. A buried via per GND pad does not fit a dense cell and perforates
both planes; the sensor array (2026-10-21) went from 65 GND holes through the planes
to 19 that way.

Lay it and remove it with `../scripts/stitch.py` (`add`, `remove`,
`report`). Grade it with `../scripts/check_copper.py`: `pour-island` fails at
`--stage final` (before the stitching pass it only warns),
and `pour-fill`, `pour-split`, `zone-overlap` and `stitch-group` warn. A
router's own stitching option (KRT `--stitch-vias`, at its 20 mm default and
gated on speed tier) is not this pass. Don't use it for stitching.

**L-44 Power copper follows the power tree.** Each rail's copper runs in the
order the architecture's power tree draws it: source, input protection and
bulk, regulator, output caps, then the loads. No load taps the rail upstream
of the filter, ferrite, load switch or sense resistor that is meant to sit
ahead of it, and no rail picks up a second, undrawn source through a pour
that merges two nets. Each segment carries the sum of the currents
downstream of it, so its width (L-21) and via count come from that sum, not
from the last load's current. Where the architecture says star, trunk or
separate return (an analog rail fed from its own regulator, an LED pulse rail
kept off the logic rail), the copper does the same. A regulator's feedback or
sense line connects where the architecture says to regulate (the output cap,
or the far load, Kelvin), not wherever the router happened to join the rail.
A power tree that is right in the schematic can still be wrong in copper, and
DRC can't tell.

**L-45 Bus topology as the schematic means it.** Grade each shared bus by
segment, where a segment is the copper between buffers, muxes or switches.
For I2C, each segment has exactly one set of pull-ups, where the schematic
puts them (usually at the controller or the mux channel), and no segment is
left without one. SDA and SCL run together, on the same layers, over
continuous GND, with the stub to each device short (≤ 10 mm *(draft)*). No
channel's SDA pairs with another channel's SCL through a crossed lane. The
segment's capacitance (track length × per-mm estimate, plus vias and pin
capacitance), together with its pull-up, meets the rise time of the bus mode
(≤ 400 pF for standard and fast mode); compute it from the routed copper with
`../scripts/rail_check.py --bus`, not by hand, and state the per-pin figure
used. For SPI and other shared clocks,
state whether the topology is star or daisy, route it as stated, and keep
the clock's stubs short. Name the segment, its devices and its pull-ups in
the finding.

**L-46 Fab and silk text, and the title block.** *(draft, review
 2026-10-21)* A refdes on a Fab layer is for the assembly drawing; on a board
with no room for it, it is hidden rather than left to pile up into an
illegible layer. Every board carries one title block on an outer layer where
there are no parts and no other silk: the board name, the revision and the
date, placed at setup with the mechanical facts (L-05) so routing works around
it. Before handoff every layer is rendered on its own and looked at, Fab and
silk included, not only the 3D views; an unreadable layer is a finding.

**L-47 BGA and WLCSP breakout order.** *(draft, review 2026-10-21)*
Decide per ball ring before routing: the outer ring escapes on the surface
layer with a dogbone to a via wholly outside the ball field; the inner rings
take a via-in-pad microvia at the ball centre (L-30, declared). Then place
**every** fanout via first, as one group, together with the pin vias of
L-39 and the shared taps of L-43, and only then route. A via is at a pad's
centre or wholly outside the pad; a via that overlaps a pad's copper partway is
a defect even when DRC passes it, because the paste and the joint don't know
where the via ends. `../scripts/check_copper.py` `via-over-pad` fails on it.
At 0.4 mm pitch a 0.25 mm via pad in every ball leaves 0.15 mm between pads
on the breakout layer, which no track crosses, so a via in every ball
landlocks the inner balls: that is why the outer ring stays on the surface.
The same order holds for a larger BGA. How many layers the escape needs, which
strategy each part takes (surface, dogbone, via-in-pad, skip or staggered
microvias, a neck-down area, rotation) and the lane budget of a repeated cell
are planned in the `hdi-breakout` skill, at placement, before any route.

**L-48 A pad is a leaf.** *(draft, review 2026-10-21)* A BGA ball, a
connector pin or a passive's pad is the end of exactly one track. A net's
trunk passes beside the pads, and each pad hangs off it by a stub; no track
branches at a pad, and no T-junction sits inside a pad or within one pad
length of its centre. A trunk that forks at a ball puts the ball's current
and the branch's current through one 0.2 mm land, and it is the first thing a
reviewer sees. `../scripts/check_copper.py` `pad-junction` counts pads with
more than one attached track end; it fails on balls and warns elsewhere.

**L-49 Critical nets are routed on purpose, before the autorouter.**
*(draft, 2026-10-22, motor-driver board layout.)* The routing spec carries a
`critical-nets:` list, and every net on it is routed deliberately: by hand
with pcbnew's interactive router, or as an exact path a script lays from the
pad along a stated corridor and layer. Each one is looked at in a render
against its rule below before any autorouter pass. The autorouter gets only
what is left and keeps the critical copper, and its result is checked against
the recorded critical items. **Lock copper only while a parallel merge round is
open; unlock everything except footprints when it closes.** Locked tracks and
vias can't be pushed or moved by the interactive router, and the board is
still being routed after the critical pass. An autorouter pass counts as such
a round: KiCadRoutingTools rips unlocked copper that isn't on its nets even with
`--keep-input-copper`, so lock everything outside the pass's nets on its stage
copy and unlock it when the pass is merged back. An autorouter
works for completion, not for loop area, pairing or what a net runs past: it
routes a Kelvin pair as two unrelated nets and a gate as a long loop. On a
motor-driver board (2026-10-22) the first autoroute pass, at 67% routed, had routed
the Kelvin sense, gate and REFIN nets badly, and they were ripped up to be
routed by hand.

The list is every critical net on the board, not only the ones that cross
between blocks. Build it from the schematic and the captures, and include at
least each of these the board has:

- **Diff pairs** (USB, CAN, Ethernet and EtherCAT, LVDS, RS-422 encoder
  lines): routed as pairs (L-22) over a continuous reference (L-23).
- **Shunt Kelvin sense.** Taken from the inner edge of the shunt's pads, or
  its sense pads, never from the current path, a pour or a via in it. The two
  lines run as a tight pair at minimum spacing, on one layer, to the
  amplifier or ADC input, with the filter at the amplifier end, clear of
  switch nodes and the bridge's current loop.
- **Gate drive.** Each gate track runs with its return (the FET's source,
  Kelvin source where the part has one, or the driver's return pin) as a
  pair, with the loop as short and small as placement allows, and its length
  and loop stated. The gate resistor sits where the schematic means it.
- **Bootstrap and switch nodes.** The bootstrap cap's loop tight to its
  pins; switch-node copper no bigger than the current needs (L-28), with its
  high-voltage clearance class kept.
- **ADC inputs and reference.** Differential inputs as pairs; REFIN and
  REFOUT with their caps at the pin; all of it over solid ground, away from
  switch nodes and digital clocks.
- **ADC and isolator interfaces.** Clock, data-ready and SPI data between a
  converter or isolator and the MCU: short, over continuous ground, with the
  series terminations the schematic has, and clocks clear of the analog
  inputs.
- **Clocks and crystals** (L-13), **feedback and sense lines** (L-28, L-44),
  and anything a capture's layout guidance names.

Each entry names the net or nets, the rule it is routed to, its layers, and
what was checked; an entry left to the autorouter says why. layout-review
grades it (LAY-57 to LAY-60).

**L-50 Size a routing reservation to the route, bind it to its layer, and release it when the route
is laid.** *(draft, 2026-10-23, from a motor-driver board routed by parallel threads.)* A corridor or hold
that keeps other work out of a critical route's path is drawn as wide as the route needs, and no wider:
its track widths, its pair gap, the clearances on both sides, and the via sites it will use. It names
its layer. A merge or DRC gate checks tracks in a corridor only on that layer, and checks vias on every
layer, since a via passes through them all. A reservation is lifted, or cut back to the copper laid, as
soon as its route is laid and merged. Area holds are dated, name their owner, and shrink to what is still
in progress. On the motor-driver board:
- Current-amplifier output lanes 1.1 mm wide were checked on every layer, which walled off three test
  points that outer-layer tracks could have reached.
- Reservation boxes blocked 36 pin vias, more than the parts did.
- An undated all-layer hold over a whole strip refused a finished, unrelated batch until it was cut back.

**L-51 Reserve each critical pin's escape before any other copper lands near it.** *(draft,
2026-10-23.)* Before block or housekeeping routing starts near a critical part (a gate driver, a FET
gate, a shunt, a converter or clock pin), list each critical pin's escape. That is the via sites clear
on every layer within a few mm, found with a via-site map, and the one lane to them. Reserve those sites
and lanes to the critical net, even when that net is routed later. A critical pin with a single clear
via site is a placement finding at that point, not a routing problem for later. On the motor-driver
board a brake-chopper FET's gate pin was ringed by its own source vias and its drain pad, with one
through-via site left. A divider net routed earlier took the only outer-layer path past the gate
resistor, and the gate drive had to be re-laid three times. Housekeeping nets routed round the MCU
before the critical escapes were fixed had to be ripped out of the lanes and re-laid. Critical nets land
before housekeeping, not only in the routing order but in the merge order. When MCU sense and
housekeeping nets merged first, six comparator resistor and capacitor pads were left boxed in on the
outer layer with no via site. They needed vias in pad, and the over-current trip into the MCU's break
input could only leave its pin through a via under the MCU body.

**L-52 Run one router search at a time on a machine.** *(draft, 2026-10-23.)* Autorouter and other
search-heavy passes (whole-board via-site and placement searches) run one after another on a machine,
not once per thread. When parallel threads share a host, a queue or lock decides which search runs,
and the critical-net work goes first. Each search is limited by its net list to the nets that reach the
block. On the motor-driver board, four router runs at once on one host starved the critical-net
thread, and an unscoped run of another thread's route table on a block copy took over an hour.

**L-53 Work on a copy of the current head, and re-run the merge gate before every submission.**
*(draft, 2026-10-23.)* A block routed in parallel is re-based onto the head it will merge into: its
finished nets are transplanted onto a fresh copy of that head, not re-routed. Then the gate runs again,
because the gate's own inputs change between heads, not only the board: held areas, corridors, the DRC
rules, the reserved-net list. The submission states the head it was checked on. Near the busiest part
(the MCU periphery, a BGA or QFN escape field), expect a copy to go stale within the hour, and submit
small batches. On the motor-driver board one block was refused three times in two hours: once for a
dangling stub, once for a crossing with a newly merged sense net, and once by a new all-layer hold.
Each time it had been clean on the head it was built on. Two blocks round the MCU needed explicit
re-lane lists and add-only merges sequenced after each other.

**L-54 Plan a breakout for every fine-pitch power and ground pin at placement.** *(draft, 2026-10-23;
extends L-39.)* Every power or ground pin on a part with a pitch of 0.8 mm or less gets either its own
via site within 1.5 mm, or a breakout. A breakout is a short straight stub (0.25 mm, at 0, 45 or 90
degrees, on the pad's layer) out to the first legal via spot 0.6-3 mm away. It steps the via down
(0.6/0.3, then 0.45/0.2, then 0.35/0.15) as far as the pin's current allows, and never lands a via in a
pad (L-30). Two same-net pins may share one via. The placement review checks that each such pin has a
site, because after routing most don't. On the motor-driver board, 2 of 28 fine-pitch plane pins on one
side had a breakout spot after routing, and 2 of 4 on the other. The rest were caged by other nets'
inner tracks and vias, or by L-39 pin vias round SOT-23 and VSSOP parts.

**L-55 A moved via or a part pose must not land on another net's copper.** *(draft, 2026-10-23.)*
Every via nudge and every pose for a moved part is checked against the board it will land on: the
current head with the other moves applied. A pad or via that lands on another net's via or track
re-nets it silently. The editor gives the via the pad's net, and DRC then reports only a dangling via or
a missing connection, not a short. Find poses with a clearance-checked placement search on a fresh base,
and only then freeze them as exact poses. After each nudge pass, compare every moved via's net with the
plane or pour under it, and run DRC on a refilled copy. On the motor-driver board a part pose turned a
GND via into a dangling signal via. A stray re-netted via had to be removed in a later rip pass, and 4 of
7 proposed via nudges round a QFN added DRC errors and were refused. A merge gate therefore counts `via_dangling` as
an error and treats one new dangling via as a possible short, never as noise. A transplanted signal
track that passed over a moved resistor's ground via showed up only as +1 dangling via.

**L-56 Don't use Freerouting on a planed, held multilayer board; use KRT and scripted exact paths.**
*(draft, 2026-10-23.)* On a board with plane layers, rule areas and reserved corridors, Freerouting
(the DSN/SES round trip) does not keep out of the planes and rule areas, and its run time grows past
any useful bound. Route what is left with KiCadRoutingTools, plane layers costed out (L-36). Route what
KRT can't close as exact scripted paths or by hand, and check them with KiCad DRC. Freerouting is an
experiment on a copy, never a pass in the flow. On a 6-layer motor-driver board (Freerouting 2.5.0,
headless):
- One trial took 210 s for 2 nets and returned 2230 DRC violations, with the planes and rule areas
  not kept out.
- A second trial, on five boxed nets with a 900 s bound, spent 691 s in its first pass and ended it
  with 53 unrouted and 3987 violations. It wrote no session file.

**L-57 A join to existing copper is anchored to a named pad's copper and checked by the CAD tool's own
connectivity.** *(draft, 2026-10-23.)* A scripted route that ends on "any copper of the net" (the nearest track
or via of that net) can land on a fragment that reaches no pad: a stub, an island, or a leftover from a rip-up.
The route then reports success while the net stays open, or a new island forms. A join names its anchor:
the pad, or a point on copper that is connected to that pad when the join is laid. After every pass, the
nets it touched are graded by the CAD tool's own connectivity, either its unconnected count or DRC on a copy
with the other nets cleared, not by the router's report or a home-made geometric check. On the motor-driver
board, a route table's "join to the net" step landed on unconnected copper, formed islands and reported OK. It
was fixed by anchored joins. Separately, a geometric connectivity check disagreed with the router both ways, so
only the tool's own count was trusted.

**L-58 Near the busiest part, freeze a box for each merge round.** *(draft, 2026-10-23.)* Where several
threads route around one part (the MCU periphery, a fine-pitch converter, a gating strip), a copy taken
from the head goes stale in about 15 minutes. Its routes then collide with copper merged in the meantime,
and the run that made them is wasted. Each round, the integrator freezes a box (an area, its layers and an
end time), names the one thread that routes in it, and merges that thread's list before anyone else
lands inside the box. Others work outside it or wait for the next round. A thread that can't finish
inside its round hands the box back and re-checks on the next head. On the motor-driver board, a
comparator block routed over 40 minutes on a 25-minute-old copy was refused on transplant. Four merges
had landed in its area: shorts with a newly locked sense net, a moved resistor's ground via under one of
its tracks, and two crossings. It had to be routed again from scratch.

**L-59 Prove every custom DRC rule loads and fires.** *(draft, 2026-10-23.)* KiCad 10 rejects a rules
file with a unitless number (`(min 0.3)` instead of `(min 0.3mm)`), and kicad-cli then runs DRC with no
custom rules at all and says nothing. Only pcbnew's own report (`WriteDRCReport`) prints the parse error.
After writing or editing `.kicad_dru`, tighten each rule on a copy until it must fail, and see the rule's
name in the report ("rule 'kelvin_hv'"). Then loosen it and see the expected hits clear. Any script that
carries its own copy of a clearance (a router's extra clearance per class, a merge gate) takes it from
the rules file or is checked against it. A rule declared in one route table and missing from the next
lets that table route at the class default beside nets the rule protects. On the motor-driver board,
the HV clearance for Kelvin sense nets and three fine-pitch pad rules were never enforced until the
units were added. One route table then laid two Kelvin-clearance violations the router didn't know about.

**L-60 An isolation barrier is a wall: plan every crossing at placement.** *(draft, 2026-10-23.)* A row
of digital isolators with its creepage keep-out, between the MCU and the gate drivers, splits the board
for every signal that runs from one side to the other. At placement, list the nets that must cross it:
each through its own isolator channel, and each non-isolated net (a PWM to a non-isolated gate stage, a
fault line, a shared enable) through a planned gap in the row, on a named layer. Keep the gaps clear of
pin vias and test points. A barrier with no planned gaps leaves those nets to a router, which goes round
the end of the row or never closes. On the motor-driver board, one phase's isolator row stood between
the MCU's PWM pins and that phase's gate inputs with no gap planned, and those PWM nets had to be routed
round it after the fact.

---

## Flex

**L-40 Bend areas.** Traces of at least 0.15 mm, and no vias, pads or stiffener
edges in the bend. The bend radius is ≥ 10× thickness for multilayer, and 10–15×
if the bend is dynamic.

**L-41 Coverlay isn't LPI mask.** Coverlay bridges are ≥ 0.5 mm, because it can't
hold a 0.1 mm dam.

**L-42 No controlled impedance on JLC flex.** Route impedance-controlled nets on
the rigid board.
