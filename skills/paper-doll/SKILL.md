---
name: paper-doll
description: Prove every connector joint between boards (cable, flex, FFC, B2B, mezzanine, stacking header, card edge) is pin-for-pin right, and that no wrong install damages anything, before either board goes to fab.
---

# Paper doll: pin-to-pin across every board-to-board joint

Use this whenever a design has more than one board, or a board meets a cable, flex or another
board through a connector. The rule: **no board with an inter-board connector goes to fab until
every signal across every joint has a pin-to-pin map, checked in the assembly pose in 3D CAD, and
every way the joint can go together wrong has been graded.**

Why: a connector's pin 1 depends on which side of the board it sits, which way the cable enters,
whether the cable has a half twist, and how the datasheet counts. Schematics hide all of that.
On one past design the flex pinout was reversed end to end: as drawn, a stock flat FFC would have
put the LED rail onto GND. It was caught by hand, late, after the mating board was already laid
out; `references/sensor-array.json` and the tests reproduce that case.

## Contract

Input: both boards (KiCad), the connector datasheets, and how the assembly goes together (which
side each connector is on, cable route, standoff heights).
Output, per joint, in the design's review folder:
1. The pin-to-pin table (A pin, A net, B pin, B net) for the reference install.
2. A table of every mis-install case with its grade: correct, degraded, fails, DAMAGE.
3. 3D CAD evidence that the boards meet in the pose the table assumes.
4. For a cable or flex: a printed 1:1 paper doll checked against the real connectors.
5. A line in the bring-up plan: the continuity check that proves it on the first unit.

## 1. Facts from the datasheet, cited

For each connector, write down, with the datasheet page:
- Pin numbering, and where pin 1 is when looking into the mouth from the mating side.
- Contacts: top, bottom or dual (FFC/FPC); which face of the cable must face them.
- Keying: can it go in rotated 180° or shifted one position? Unkeyed B2B and many FFCs can.
- For a mating pair (B2B plug and receptacle): how the plug's pin numbers meet the receptacle's.
  Vendors differ; some number the plug mirrored. Use the vendor's mated drawing, not a guess.
- Always ask "is there a stock part?" before designing a custom cable; prefer a stock FFC that
  works flat (same-side contacts) over a custom flex.

## 2. Cables and flex: `scripts/pin_map.py`

Describe each end (`m` = direction from the connector to its board, `d` = insertion direction,
contacts, pin-1 side, nets) and the cable (half twist, exposed faces, whether a one-position
shift is possible). See the docstring and `references/sensor-array.json`.

```
python3 scripts/pin_map.py joint.json --svg doll.svg --json joint_cases.json
```

It prints the reference map and grades: the reference install, cable turned over, extra half
twist, both, and ±1 shifts. Exit 1 if the reference install is not net-for-net correct.

Required outcome: reference install **correct**, and no case that a person can plausibly do at
the bench grades **DAMAGE**. If one does, change the pinout (power pins symmetric, grounds between
rails, rails at the centre so a reversed cable lands them on themselves) or key the joint.

## 3. B2B, mezzanine, stacking headers: `scripts/mate_check.py`

Read the pads off both boards, place each board in its assembly pose (x, y, rotation, flipped or
not) and pair the pads that land on each other. That is the map from the CAD itself, so a
footprint on the wrong side, rotated, or a plug numbered against its receptacle shows up.

```
$KPY scripts/mate_check.py joints.json --json mate.json
```

Give a `rename` table for nets that change name across the joint (`VBUS_D` -> `VBUS`). Mark
unkeyed connectors `"keyed": false` to grade the 180° install as well. Exit 1 if any joint, as
designed, has a mismatched net or an unmated pad. Every unmated pad needs a reason in the table.

## 4. Confirm in 3D CAD

The two scripts assume the pose; CAD proves it. For every multi-board assembly:
- Build the assembly (KiCad STEP or VRML per board, placed at the poses in `joints.json`; a
  small fit script does this) and check: the connectors' bodies
  meet, mated height matches the standoffs, pin 1 marks line up, the cable or flex route has its
  bend radius and does not cross a part.
- Post renders of each joint, from the cable side and from above, with pin 1 marked.
- If the assembly lives in MCAD, export the boards from KiCad and check there; record the file.

## 5. Paper doll (cables and flex)

Print the SVG at 100% (the 10 mm bar must measure 10 mm). Cut out the tail, mark pin 1 and the
contact face, and fold it through the route on the real boards or the 1:1 prints of both. If a
real cable and connectors are at hand, use them. Note the result in the review folder.

## 6. Gates

- Before layout of either board: interface and pinout frozen with section 2 or 3 passing. A
  pinout change after one board is fabricated has to be absorbed by the other board or the cable.
- Before fab: rerun both scripts on the final boards; the 3D renders are current.
- Check whether the mating board is already fabricated or ordered; if so its pinout is fixed and
  the new board adapts to it.
- Bring-up: before first power, meter continuity across each joint for the power and ground pins
  against the table, and check for no short between rails.

## Handoff

Put a block in the design's `routing_spec.md` or review notes:

```yaml
joints:
  - a: main:J3
    b: sensor:J1
    kind: ffc            # ffc | flex | b2b | header | card_edge
    part: Wurth 687608152002
    reference: correct
    worst_misinstall: "extra half twist: DAMAGE (not possible with a flat stock FFC)"
    cad: review/joint_J3_J1.png
    paper_doll: "2026-10-22, checked on the real connectors"
```
