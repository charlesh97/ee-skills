# Worked example: a 1 A SOT-583 buck, 12 V to 5 V

The part is TI TPS629210 (SOT-583, 8 pins, 0.5 mm pitch, no exposed pad, no
external bootstrap), with a 2.2 µH 2520 inductor, a 100 nF 0402 HF input cap, a
10 µF 1206 bulk cap, a 22 µF 1210 output cap, VSET and S-CONF resistors, a 0R
output link and a loop-injection jumper. The board is 6 layers: F parts, In1
solid GND, In2 and In3 signal, In4 rail shapes, B parts and GND fill. This is
the layout from 2026-10-23, done on a demo board and measured against the same
converter as a placer and a router had left it.

## Pinout and rotation

Pin table: 1 FB/VSET, 2 PG, 3 VOS, 4 SW, 5 GND, 6 VIN, 7 EN, 8 MODE/S-CONF.
Figure 11-1 draws GND, VIN, EN and S-CONFIG down the left side and SW, VOS, PG
and FB down the right. The footprint at 0° has pins 1-4 on the left, so the IC
goes at **180°**. VOS (3) sits beside SW (4), on the inductor side, which is the
trap: a top-layer VOS route to the output cap runs beside the SW copper.

## Placement (mm from the IC centre, y down)

| Part | Pose | Why |
|---|---|---|
| IC | 0, 0, 180° | Pin order of figure 11-1 |
| HF cap 0402 | −2.07, −0.50, 90° | Across GND pin 5 (y −0.75) and VIN pin 6 (y −0.25), each pad facing its pin. 0.60 mm pad gap, set by keeping the courtyards clear |
| Bulk cap 1206 | −3.92, −0.50, 90° | Right behind, same orientation |
| Inductor 2520 | 3.07, −2.50, −90° | SW pad level with pin 4, output pad pointing away |
| Output cap 1210 | 1.00, −6.10, 180° | Across the top, its GND pad on the shared GND area |
| VSET, S-CONF 0402 | ±1.50, 2.50, −90° | At pins 1 and 8, GND straight to In1 |
| 0R link, jumper | 5.9, −6.1 and 6.3, −3.75 | Output side, off the loop |

## Copper

- **F zones:** VIN, from the bulk cap's far side into pins 6 and 7, with EN tied
  at the cap. SW, a 0.4 mm neck from pin 4 into the inductor pad. VOUT, the
  inductor output pad, the output cap, the link and the jumper. 5 V after the
  link. One GND zone covers the rest of F, so the input and output caps share
  one ground area.
- **Vias:** 0.6/0.3 GND vias north-west of the IC, beside the loop. Two 12 V vias
  into In4 at the bulk cap's far side, and two 5 V vias after the link. Signal
  vias are 0.3/0.15.
- **VOS:** 0.75 mm on F to a via just past the pin column, then In3 (In1 GND sits
  between it and SW), then up into the VOUT pour at the output cap's outer edge.
- **PG:** a via just past the pin column, then to a test pad on B.

## Result

| Measure | Placer and router | Cell |
|---|---|---|
| HF loop | 0.6 mm² plan + 2.9 mm² vertical, closed through In4 | 0.93 mm², F only |
| HF cap to VIN / GND pin | 0.88 mm (not joined on F) / 1.86 mm | 0.60 / 0.60 mm |
| Bulk loop | 7.9 + 6.2 mm² | 5.4 mm² |
| SW copper beyond the pads | 1.5 mm² | 0.45 mm² |
| VOS within 1 mm of SW | 5.3 mm | 0 mm past the escape |
| Cell check | 7 FAIL | 16 PASS |

What caused the bad version, in order: the placer clustered the caps by net,
the In4 rail shapes were drawn around the "hot loop", the pin-via pass gave the
cap and the pin a via each (so KiCad counted the loop connected), the VOS table
routed to the output cap from the far side of the inductor, and the parts were
locked before anyone measured them.

## Transplant

`cell.py extract demo.kicad_pcb --refs IC,L,...` stores the cell. `cell.py place`
puts it on a copy of the real board. Dropping this cell at the old IC's spot,
unrotated, hit 14 courtyards, and the rail under its output link was the wrong
net. Both are placement and rail-shape work around the cell, and that work comes
next.
