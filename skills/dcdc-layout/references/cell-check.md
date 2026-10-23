# The cell check

`scripts/check_regulator.py` measures each regulator against these limits. They
are drafts (2026-10-23), set from two datasheet layout figures (a 1 A SOT-583
buck and a 1 A 3 × 3 mm TDFN buck) and the evaluation of one 6-layer board.
Tighten them as parts and boards teach more. A spec entry can override any of
them under `"limits"`, and the reason goes in the routing spec.

| Check | Limit (default) | Rule | Why this number |
|---|---|---|---|
| Hot loop area, plan + vertical | ≤ 2.0 mm² | L-11 | A 0402 across adjacent pins at 0.5 mm pitch gives 0.6–1 mm². 2 mm² allows a 0603 and a courtyard gap. The boards that failed were at 3.5 to 9 mm². |
| Hot loop on the component layer, no via | every link on the IC's layer | L-11 | A via pair adds about 1 nH and its run to an inner layer adds vertical area (depth × run). |
| HF cap pad edge to its pin | ≤ 1.0 mm, both pads | L-11 | Keeps the cap across the pins, with room for a courtyard gap. |
| SW copper beyond the pads | reported | L-28 | Size it by L-21 from the peak current limit. The number is for the review to judge. |
| Vias on SW | 0 | L-28, L-29 | Unless the thermal budget needs the datasheet's SW-pin vias (L-29), stated in the spec. |
| Plane under SW | 100% of the SW copper, on `plane_layer`, of `gnd_net` (or `plane_net`) | L-23 | The SW node's displacement current returns on the plane under it. A split or the wrong ground there sends it the long way. |
| Signal tracks under SW | none (WARN) | L-12 | Below a solid plane they are shielded, so this is a warning. References, ADC inputs and dividers should still move. |
| Sense line near SW | ≤ 0.5 mm of route within 1.0 mm of SW copper on the component layer, past a 1.0 mm escape from the pin | L-28 | The escape allows the pin pitch. Beyond it, parallel coupling into a high-impedance node is what corrupts regulation. Layers below the first plane are shielded and not counted. |
| Sense line over the inductor body | no (component layer) | L-28 | The inductor's field couples into a line under its body. |
| Strap nets near SW | same as sense, with no escape | L-28 | Strap resistors sit at their pins and away from SW. |
| Cap ground reaches the IC ground | each HF, bulk and output cap, on `gnd_net` | L-62 | A ground via that lands on another net's plane connects nothing, and DRC reports it only as one open among hundreds. |
| Rail entry/exit vias | ≥ 2 into a plane | L-21 | No rail hangs on one via. |
| Exposed-pad vias | ≥ 1, and none under paste unless `"vippo": true` | L-29, L-30 | Heat path, and solder wicking. |

How the numbers are measured:

- **Loop area** follows the copper. Between two pads of one net, the path runs
  over that net's track centre lines on the component layer, joined through pads
  and vias, with pour bridges up to 0.6 mm taken straight. If the pads only meet
  on another layer, the path goes through the nearest via pair, and the vertical
  area is that run times the layer's depth below the component layer, from the
  stackup in the board file. Plan area is the shoelace area of the path.
- **Distances** are copper edge to copper edge, from pad shapes, track widths
  and filled zones after an in-memory refill.
- **Inductor body** is its courtyard shrunk by 0.25 mm.

## Spec fields

```json
[{
  "name": "U5 12V->5V",
  "ic": "U5",
  "hot_loop": ["C21.1", "U5.6", "U5.5", "C21.2"],
  "hf_cap": "C21", "bulk_caps": ["C20"], "out_caps": ["C24"], "inductor": "L3",
  "sw_net": "/power/SW_5V", "gnd_net": "GND", "plane_layer": "In1.Cu",
  "plane_net": "GND",
  "sense_pins": ["U5.3"],
  "strap_nets": ["/power/VSET_5V", "/power/MODE_5V"],
  "rail_entries": ["R12.2", "J1.1"],
  "ep": null, "vippo": false,
  "limits": {"loop_area_mm2": 2.0},
  "crop": [70, 100, 88, 112], "px_per_mm": 50
}]
```

- `hot_loop` lists pads in loop order. Consecutive pads on one net are joined by
  copper; consecutive pads on different nets are joined through the part (a cap,
  the IC's switches). The loop closes back to the first pad.
- `sense_pins` are traced from the pin along their own net until they reach
  another pad or a pour.
- `plane_net` defaults to `gnd_net`. Set it when the plane under the regulator is
  a different ground by design, and say why.
- `crop` and `px_per_mm` only matter for `--render`.
