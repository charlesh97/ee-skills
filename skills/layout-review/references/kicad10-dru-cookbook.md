# KiCad 10 custom design rules — cookbook

Syntax below was checked against the KiCad 10.0.6 source (the in-app help
files `pcbnew/dialogs/panel_setup_rules_help_*.md`, the rule parser
`pcbnew/drc/drc_rule_parser.cpp`, the expression evaluator
`pcbnew/pcbexpr_evaluator.cpp`, and `common/project/net_settings.cpp` for the
`.kicad_pro` shape). Where something is inferred rather than read, it says so.
Official narrative docs: docs.kicad.org/10.0 → PCB Editor → Custom Design Rules.

## File and skeleton

KiCad loads exactly one rules file: `<name>.kicad_dru` beside `<name>.kicad_pro`
(same basename). Anything else is ignored without an error — a rules file under
any other name is not "not working", it is not being read at all, and the board
is silently held to Board Setup alone.

```
(version 1)

# comment lines start with '#'

(rule "human readable name"
    (condition "A.hasNetclass('PWR_3A')")
    (constraint track_width (min 1.0mm))
    (layer outer)
    (severity error)
)
```

- `(version 1)` must be the first clause.
- `condition` is optional; a rule without one matches everything.
- `layer` accepts `outer`, `inner`, or a layer name such as `"F.Cu"`,
  `"In2.Cu"`, `"F.Courtyard"`. Omit it to apply on all layers.
- `severity` is one of `error`, `warning`, `ignore`, `exclusion`. Default error.
- `(min …)`, `(opt …)`, `(max …)`; which are meaningful depends on the
  constraint (table below). `opt` is what the interactive router uses.
- Values take units: `0.2mm`, `10mil`, `0.008in`, `200um`. A value may be an
  expression in quotes: `(min "1.5mm + 2.0mm")`.
- Later rules take precedence. For a given constraint type, KiCad walks the
  rules from the bottom up and stops at the first match — so put the general
  rule first and the exceptions after it.
- A custom rule relaxing below a Board Setup → Constraints minimum may be
  clamped to it. This has been observed, and also contradicted, on 10.0.6, so
  probe it (layout-review LAY-03a) rather than assume. Either way, put the fab floor (trace/space, drill, annular ring, edge clearance) in Board
  Setup; put design intent in the DRU.
- A unitless number (`(min 0.3)`) is a parse error in KiCad 10, and kicad-cli then runs DRC with **no**
  custom rules and no warning; pcbnew's `WriteDRCReport` prints the error. Prove each rule by tightening
  it on a copy and seeing its name in the report (L-59).

## Conditions

`A` is the item under test, `B` the second item for pairwise checks
(clearance, hole_to_hole, silk_clearance …), `L` the layer under test.

Operators: `==  !=  <  >  <=  >=  &&  ||  !` and `+ - * /`. There is no regex
operator. String comparison with `==` accepts wildcards `*` and `?` on the
right-hand side: `A.NetName == 'SPI0_*'`. All function arguments accept the
same wildcards.

Properties: `A.NetName`, `A.NetClass` (both case-insensitive, special-cased;
`A.NetClass == 'X'` is true if *any* of the net's classes is `X`), `A.Type`
(`'Track'`, `'Via'`, `'Pad'`, `'Zone'`, `'*Text'` appear in the official
examples), `A.Layer`, `A.Reference`, `A.Net`, `A.Name` (zone name),
`A.Pad_Type` (`'SMD'`, `'Through-hole'`, `'NPTH, mechanical'`), `A.Via_Type`
(`'Blind'`, `'Micro'`), `A.Fabrication_Property` (`'Heatsink pad'`),
`A.Hole_Size_X`, `A.Hole_Size_Y`, `A.Line_Width`, `A.Do_not_Populate`,
`A.Soldermask_Margin_Override`. Any property shown in the Properties panel is
reachable by replacing spaces with underscores.

Functions (all take wildcard strings):
`A.hasNetclass('name')` (preferred over `NetClass ==`),
`A.inDiffPair('BASE')` — base name without the `_P`/`_N`,
`AB.isCoupledDiffPair()`, `A.intersectsArea('zone')`, `A.enclosedByArea('zone')`,
`A.intersectsCourtyard('U3')`, `A.intersectsFrontCourtyard()`,
`A.intersectsBackCourtyard()`, `A.memberOfFootprint('J*')`,
`A.memberOfGroup('g')`, `A.memberOfSheet('/Power/')`,
`A.memberOfSheetOrChildren('/Power/')`, `A.existsOnLayer('In1.Cu')`,
`A.fromTo('R1', 'U2')`, `A.isPlated()`, `A.isMicroVia()`, `A.isBlindVia()`,
`A.isBuriedVia()`, `A.hasComponentClass('c')`, `A.getField('f')` (footprints).

## Constraint types (parser token list, 10.0.6)

| constraint | takes | use it for |
|---|---|---|
| `clearance` | min | copper-to-copper between nets (electrical) |
| `creepage` | min | surface path between nets, for mains/HV |
| `physical_clearance` | min | any-object spacing regardless of net; slow, scope it |
| `physical_hole_clearance` | min | hole to anything |
| `hole_clearance` | min | hole to copper of other nets |
| `hole_to_hole` | min | drill to drill |
| `edge_clearance` | min | copper to Edge.Cuts |
| `courtyard_clearance` | min | courtyard to courtyard |
| `silk_clearance` | min | silk to mask/copper |
| `track_width` | min opt max | width by class |
| `connection_width` | min | pad-to-zone neck width |
| `annular_width` | min max | via ring |
| `via_diameter` / `hole_size` | min opt max | via and hole sizes |
| `via_count` | min max | vias per net |
| `via_dangling` | — | flag vias connected on one layer only |
| `length` | min opt max | routed net length |
| `skew` | min opt max, `within_diff_pairs` | length difference in a matched group |
| `diff_pair_gap` | min opt max | gap inside a pair |
| `diff_pair_uncoupled` | max | total uncoupled length in a pair |
| `disallow` | items | keepouts: `track via through_via blind_via buried_via micro_via pad zone text graphic hole footprint` |
| `zone_connection` | `solid` `thermal_reliefs` `none` | pad-to-zone style |
| `thermal_relief_gap` | min | gap in a thermal relief |
| `thermal_spoke_width` | min (opt) | spoke width |
| `min_resolved_spokes` | 0–4 | require N spokes actually connected |
| `solder_mask_expansion` | opt | mask expansion |
| `solder_mask_sliver` | min | mask sliver |
| `solder_paste_abs_margin` / `_rel_margin` | opt | paste |
| `bridged_mask` | — | allow/forbid mask bridging (use with severity) |
| `text_height` / `text_thickness` | min max | silk text |
| `track_angle` / `track_segment_length` | min max | routing style |
| `assertion` | "expression" | anything expressible as a property test |

## Snippets

Class-based clearance and width. Class names must match `.kicad_pro` exactly.

```
(rule "HV clearance"
    (condition "A.hasNetclass('HV')")
    (constraint clearance (min 1.5mm))
)
(rule "HV to HV, both sides high"
    (condition "A.hasNetclass('HV') && B.hasNetclass('HV')")
    (constraint clearance (min "1.5mm + 2.0mm"))
)
(rule "HV creepage"
    (condition "A.hasNetclass('HV') && !B.hasNetclass('HV')")
    (constraint creepage (min 3.0mm))
)
(rule "power width 3A class"
    (condition "A.hasNetclass('PWR_3A')")
    (constraint track_width (min 1.0mm))
    (constraint connection_width (min 0.8mm))
)
(rule "power width, inner layers narrower copper"
    (condition "A.hasNetclass('PWR_3A')")
    (constraint track_width (min 1.5mm))
    (layer inner)
)
```

Differential pairs (needs `_P`/`_N` names; gap/width from stackup.yaml).

```
(rule "USB pair gap"
    (condition "A.inDiffPair('USB_D')")
    (constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.18mm))
    (constraint track_width (opt 0.20mm))
)
(rule "USB uncoupled length"
    (condition "A.inDiffPair('USB_D')")
    (constraint diff_pair_uncoupled (max 3mm))
)
(rule "keep other copper off pairs"
    (condition "A.inDiffPair('*') && !AB.isCoupledDiffPair()")
    (constraint clearance (min 0.3mm))
)
(rule "USB pair skew"
    (condition "A.inDiffPair('USB_D')")
    (constraint skew (max 0.15mm) (within_diff_pairs))
)
```

Length, via count, keepouts, edge.

```
(rule "crystal nets short"
    (condition "A.NetName == 'XTAL_*'")
    (constraint length (max 8mm))
    (constraint via_count (max 0))
)
(rule "switch node stays on one layer"
    (condition "A.NetName == 'SW_3V3'")
    (constraint via_count (max 0))
)
(rule "feedback node few vias"
    (condition "A.NetName == 'FB_3V3'")
    (constraint via_count (max 2))
)
(rule "antenna keepout"
    (condition "A.intersectsArea('KO_ANTENNA')")
    (constraint disallow track via zone pad footprint)
)
(rule "no copper under the mounting flange"
    (condition "A.intersectsArea('KO_FLANGE')")
    (constraint disallow track via zone)
    (layer outer)
)
(rule "copper to edge"
    (condition "A.Type == 'Track' || A.Type == 'Pad' || A.Type == 'Zone'")
    (constraint edge_clearance (min 0.4mm))
)
(rule "courtyards off the edge except connectors"
    (condition "B.Layer == 'Edge.Cuts' && !A.memberOfFootprint('J*')")
    (constraint physical_clearance (min 1.0mm))
    (layer "F.Courtyard")
)
```

Zones, thermals, heatsink pads.

```
(rule "solid connection on power pads"
    (condition "A.hasNetclass('PWR_*') || A.Fabrication_Property == 'Heatsink pad'")
    (constraint zone_connection solid)
)
(rule "thermal reliefs on GND pads of small passives"
    (condition "A.hasNetclass('GND') && A.memberOfFootprint('R*')")
    (constraint zone_connection thermal_reliefs)
    (constraint thermal_relief_gap (min 0.2mm))
    (constraint thermal_spoke_width (min 0.3mm))
    (constraint min_resolved_spokes 2)
)
```

Height-limited region and assertions.

```
(rule "no parts under the shield can"
    (condition "A.intersectsArea('KO_LOWPROFILE')")
    (constraint disallow footprint)
    (severity error)
)
(rule "no per-pad mask overrides"
    (condition "A.Type == 'Pad'")
    (constraint assertion "A.Soldermask_Margin_Override == null")
)
(rule "no paste on DNP parts"
    (condition "A.Do_not_Populate")
    (constraint solder_paste_abs_margin (opt -50mm))
)
```

Waiving something deliberately: same condition, `(severity ignore)`, and a
comment with the reason. Every waiver also goes in `open_items.yaml`.

## What the DRU cannot check

Proximity of a cap to a pin (there is no distance-between-footprints
constraint; `intersectsCourtyard` is boolean), loop area, plane splits under a
signal, return-path continuity, copper area for heat, component orientation,
probe access. Each of those is graded by
layout-review from the plotted layers.

## `.kicad_pro` net_settings (KiCad 10, schema version 5)

The project file is plain JSON. Dimensions are millimetres; `wire_width` and
`bus_width` are schematic mils. Every class carries `name`, `priority`,
`pcb_color`, `schematic_color`; the other keys are written only when set. The
`Default` class sits in the same array. Lower `priority` number wins when a net
has several classes; `Default` is `2147483647` (lowest).

```json
"net_settings": {
  "classes": [
    {
      "bus_width": 12, "clearance": 0.15, "diff_pair_gap": 0.25,
      "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
      "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
      "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647,
      "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.2,
      "tuning_profile": "", "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6
    },
    {
      "clearance": 0.2, "name": "PWR_3A", "pcb_color": "rgba(0, 0, 0, 0.000)",
      "priority": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
      "track_width": 1.0, "tuning_profile": "", "via_diameter": 0.8, "via_drill": 0.4
    },
    {
      "clearance": 0.15, "diff_pair_gap": 0.15, "diff_pair_width": 0.2,
      "name": "USB_FS", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 1,
      "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": 0.2,
      "tuning_profile": "", "via_diameter": 0.6, "via_drill": 0.3
    }
  ],
  "meta": { "version": 5 },
  "net_colors": null,
  "netclass_assignments": {
    "3V3": ["PWR_1A"],
    "VIN": ["PWR_3A"],
    "USB_D_P": ["USB_FS"],
    "USB_D_N": ["USB_FS"]
  },
  "netclass_patterns": [
    { "netclass": "USB_FS", "pattern": "USB_D_*" },
    { "netclass": "PWR_1A", "pattern": "3V3_*" }
  ]
}
```

`netclass_assignments` values are arrays (a net may carry several classes).
`netclass_patterns` entries are `{netclass, pattern}`; the pattern is matched
anchored against the whole net name as a wildcard (`*`, `?`) or as a regex.
Prefer explicit assignments for every net you classified and use patterns only
as a catch-all. Edit with `json.load` → modify → `json.dump(indent=2)` while
KiCad is closed; keep every key you did not touch. Missing per-class keys
inherit from `Default` at resolve time, so only write what you decided.
