# Worked example: a WLCSP sensor-array board (2026-10-20 to 2026-10-22)

A tactile sensor-array board: 16 AS7150 AFEs (WLCSP-16, 4 x 4, 0.4 mm pitch, 0.20 mm
NSMD pads) on the back, 48 SFH 7061 taxels on the front, JLC HDI, dogbone (no stacking) by the
human's choice, 0.1 mm laser vias with 0.25 mm pads, 0.15/0.30 mm buried core vias, 0.1/0.1 mm
track and space.

## What the budget says

```
$ python3 escape_budget.py ball --pitch 0.4 --pad 0.2 --rows 4 --cols 4 --track 0.1 --space 0.1 --capture 0.25
4x4 at 0.4 mm, pad 0.2: 2 rings
  surface: gap 0.2 orth / 0.3657 diag -> 0 / 1 tracks at 0.1/0.1
  dogbone via between four balls: half diagonal 0.2828 vs 0.325 needed -> does not fit (escape outward or via-in-pad)
  via-in-pad layer (capture 0.25): gap 0.15 / 0.3157 -> 0 / 1 tracks  LANDLOCKED
  signal layers for the escape, estimate: 2
```

So: the 12 outer balls escape outward on B.Cu, the inner balls take via-in-pad, and a
capture pad in every ball would landlock them. The first 6L route put a via in all 14
connected balls and failed on every AFE's 3V3_LED ball for exactly that reason
(2026-10-21 06:28); the fix was the plan above.

## What the lane count says

The two-cell tile (6.0 mm wide) had 11 lanes on In1 between the taxel via columns and 8 on
In4 between the dogbone bands, against 20 nets that pass it (14 taxel links, SDA, SCL, 1V8):

```
$ python3 escape_budget.py lanes --track 0.1 --space 0.1 --span In1=0.35x11 --span In4=0.35x8 --demand 20
lanes {'In1': 11, 'In4': 8} = 19 available, 20 needed: SHORT BY 1
```

## What happened instead

The capacity check at placement (2026-10-21 05:14) warned 83% against a 60% target and the board
was routed anyway. Six more approaches followed over about 30 hours (stacked vias, dogbone,
two planes, the feedback rules, shared GND taps, a split plane, a front-layer bus). The lane
count above was only done at 01:55 on 10-22, after the cell grid was made commensurate with the
taxels. The human chose 8 layers (1+6+1) at 17:17, and it routed clean on the first full run,
about 90 minutes later, with the same tile method.

## What this skill would have done

1. Intake: dogbone, planes for 3V3_LED, 1V8 and GND, front for taxels only, cost tolerance for
   8L: asked once, at the start.
2. Budget at placement: two escape layers per AFE; the tile one lane short on 6L.
3. Stop with the table: 6L short by one lane per tile; options 8L (+30 to 40%), 3V3_LED as a
   trunk instead of a plane, or 3/3 mil in the field. The human picks in minutes.
4. Fanout and tile on the chosen stack, renders of one AFE per layer, then routing.
