# Fitting a cell into the space the board has

A cell laid out on an open demo board rarely drops into a real board unchanged.
The board around it is already full, or the rails come from the wrong side, or
two regulators want the same corner. This page covers how to make the cell fit
without losing what made it good, and which costs to accept along the way.

## The cell has three rings

| Ring | Parts and copper | Rule for moving it |
|---|---|---|
| **Core** (rigid) | IC, HF input cap, inductor, the SW neck, the output cap, the shared ground area, the ground vias beside the loop | Moves only as a whole: any of the four rotations, any position. Never stretched. Every core check must still pass (tier 0 below). |
| **Ring** (bends, with a number) | bulk input cap, strap resistors, the sense route, the output cap's orientation round the inductor's output pad, rail entry vias | May move. Each move is re-checked, and its cost is reported as a delta (loop +0.2 mm², VOS +3 mm on In3, and so on). |
| **Periphery** (free) | output 0R link, loop-injection jumper, test pads, PG pull-up, output bulk beyond the first cap | Re-seated after the core is placed, by the anchor placer or by hand, anywhere sensible on the rail. |

Packing the core tighter is nearly always better. Every 0.1 mm taken out of the
HF cap gap, the SW neck or the sense escape shrinks a loop or a coupling length.
The limits on how tight are physical:

- **Courtyards and assembly (L-17).** The nozzle and the rework iron need the
  gap. The EVM is often tighter than the house courtyards allow. Take the
  courtyard, and record the difference.
- **Via room beside the loop.** The ground return vias and the rail entry vias
  need sites. A core packed so tight that its ground vias move away from the
  loop is worse, not better.
- **Copper for heat.** A part that sheds heat through its pins (most SOT and
  small QFN bucks) needs VIN and GND copper around them. θJA on the vendor's EVM
  is often half the JEDEC figure, and that copper is the difference. Shrinking
  the pours costs degrees, so re-check L-29.
- **The inductor's field.** Keep quiet parts of other blocks off the inductor's
  ends as well as its body.
- **Probe and rework access** for the test pads, which belong to the periphery.

So minimise the core and give the slack to the periphery.

## The tiers: what never bends, what bends, what moves

**Tier 0. Never traded.** If a pivot breaks one of these, the pivot is rejected.
- HF loop closed on the component layer, no via, HF cap across its pins (L-11).
- SW neck on one layer, no vias, solid plane under it, of the regulator's ground (L-23, L-28).
- Every cap's ground on the regulator's ground (L-62).
- The high-impedance FB node (divider tap to FB pin) short and at the pin.

**Tier 1. Traded with a stated number.**
- **The sense route can run longer.** Length on a layer under the first solid
  ground plane costs little, because what corrupts regulation is coupling on the
  component layer beside SW. With a divider, lengthen the low-impedance side
  (the divider's top lead to the output cap, which sits at VOUT) and keep the
  divider at the FB pin. Never lengthen the FB node itself. For a VOS pin there
  is no divider, so keep its component-layer part inside the 1 mm escape and let
  the buried part run as long as the placement needs.
- **The output cap's ground can join through the plane.** For a buck the output
  current is smooth, so the output cap may return to the IC ground through the
  plane, with ≥ 2 vias at the cap and ≥ 2 at the IC's ground, instead of sharing
  the input cap's top-layer ground area. The cost is a little ESL in the output
  loop and more output ripple spikes. This is never allowed for the input cap.
  For a boost the roles swap: the output cap is the hot one.
- **The inductor turns about its SW pad.** The SW pad stays at the SW pin. The
  output pad can point in any of three directions, and the output cap follows it.
  Build these as cell variants.
- **The bulk cap can move or go to the other side.** It holds the lower-frequency
  energy. Move it up to about 5 mm back along the VIN pour, or put it on the
  opposite side under the HF cap through ≥ 2 vias per pad. The HF cap still
  closes the hot loop on top.
- **Strap resistors** can go within 2 mm of their pins, or on the other side
  through one via each (shielded by the planes), with their grounds straight to
  the plane.
- **Rail entry vias** can move anywhere along the input or output pour outside the
  loop, as long as there are still two (L-21).

**Tier 2. Moves freely.** The periphery.

**Out of bounds for the layout.** These change the schematic or the BOM, so they
need the owner's yes: a smaller inductor or cap package, a different part, or
splitting one cap into two.

## When the cell doesn't fit: the order of pivots

Run `cell.py fit` at every step and `check_regulator.py` after every change. Stop
at the first step that gives a pose with nothing in the way, or with only things
you are willing to move.

1. **Search poses for the core.** Use all four rotations over a region round
   the preferred spot, fitting only the core (`--parts`). The fit is
   rotation-invariant, and the check doesn't change with rotation.
2. **Try the cell's variants.** Inductor output pointing each way, output cap on
   each side of it, bulk cap behind or beside. Build two to four variants at the
   cell stage, each one checked, and fit them all.
3. **Move the board's other parts, not the cell.** A regulator core outranks
   ordinary parts. List the parts in the way (`fit` names them) and move them, or
   pass them as `--movable` when they are being re-laid anyway.
4. **Bend the ring, one tier 1 trade at a time.** Re-check after each and report
   the delta.
5. **Move the ring to the other side.** Bulk cap, straps and test pads go to the
   bottom.
6. **Take a different region.** Moving the whole cell costs rail length (IR drop,
   L-21) and maybe a longer feed. That is usually cheaper than a degraded loop.
7. **Ask for a part change** if nothing above fits.

**After `cell.py place`, every time.** A cell carries copper below the component
layer: a buried sense route (VOS or FB on In2/In3), its vias, and the rail entry
and exit vias. `fit` counts the board tracks those cross, per layer. Placing the
cell does not move them. Before the cell counts as placed:

- rip or re-route every other-net track the cell's inner routes cross (run DRC
  on the placed copy and read the `clearance` and `shorting_items` entries on
  inner layers);
- move every other-net via that sits on the cell's copper;
- re-run `check_regulator.py` on the placed copy.

A buried sense route that crosses an inner lane is still a short, even when the
component layer is clean.

## Several regulators at once

Pack them jointly, in this order:

1. **Most constrained first.** This is the one with the largest inductor, the
   highest input voltage or the most thermal load (typically the first stage off
   the high-voltage bus).
2. **Follow the power tree.** Put each downstream converter's input next to the
   upstream converter's output, so the intermediate rail is short and doesn't
   cross a hot loop.
3. **Each placed cell is an obstacle for the next.** Place a cell (`cell.py place`
   writes a copy) and fit the next cell on that copy.
4. **Then the periphery, then the rails.** Draw the rails to the cells' entry and
   exit vias (L-36), and only then seed the rest of the board.

## Worked numbers (one 6-layer board, a 1 A SOT-583 buck cell)

- **Dropped unchanged.** At the old IC's spot, unrotated, the cell hit 14
  courtyards.
- **Core fit, nothing movable.** Over a 28 × 24 mm region, the best pose still
  hit one part (the neighbouring 12 V converter's 10 mm inductor) and sat on
  14 vias and 26 tracks of other nets.
- **The two neighbouring converters' parts movable.** All three converters were
  being re-laid anyway. The whole cell then fitted 5.8 mm from its old spot,
  rotated 180°, with no part in the way and 8 vias and 11 tracks to clear. That
  space is also where the other two cells want to go, so the next step is the
  joint packing above.
