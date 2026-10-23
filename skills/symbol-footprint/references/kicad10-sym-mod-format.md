# KiCad 10 `.kicad_sym` and `.kicad_mod` — the grammar you actually need

## What this was verified against

The developer docs at dev-docs.kicad.org ("S-Expression Format", "Symbol Library
File Format", "Footprint Library File Format") describe the token vocabulary but
were written for KiCad 6–7 and have not been updated for the 9/10 changes. So the
tokens, ordering and version stamps below were taken from the KiCad **10.0
release branch writer source** (github.com/KiCad/kicad-source-mirror, branch
`10.0`): `eeschema/sch_file_versions.h`, `eeschema/sch_io/kicad_sexpr/
sch_io_kicad_sexpr_lib_cache.cpp`, `sch_io_kicad_sexpr_common.cpp`,
`pcbnew/pcb_io/kicad_sexpr/pcb_io_kicad_sexpr.h/.cpp`, `pcbnew/footprint.cpp`.
What KiCad 10 writes is what it is guaranteed to read; older stamps also load.

Verified: version stamps, token names and order, boolean form, pin electrical
types and graphic styles, pad types/shapes/properties, footprint attributes,
mandatory field sets, `model` sub-tokens, `kicad-cli sym|fp export svg` and
`sym|fp upgrade` argument names. Not verified: exact parser leniency for every
omitted optional token (the examples below omit only tokens the parser treats
as optional in the switch statements — `uuid`, `show_name`, `do_not_autoplace`,
`in_pos_files`, `duplicate_pin_numbers_are_jumpers`, `embedded_fonts`).

## Shared conventions

- Units are millimetres; angles are degrees. Strings are double-quoted; quote
  every name and pin number even when numeric (`"1"`, `"EP"`, `"A1"`).
- Booleans are `(token yes|no)`. Bare `hide` is the old form; write `(hide yes)`.
- **Y axis flips between the two formats.** Symbols: +Y is up (the writer negates
  the internal y). Footprints: +Y is down, like the board. A pin at `(at 0 -7.62
  90)` is at the *bottom* of a symbol; a pad at `(at 0 -1.4)` is at the *top* of a
  footprint.
- `uuid` tokens are optional in library files; omit them when generating and
  KiCad adds them on first save. Never invent one and reuse it in two places.
- Version stamps (KiCad 10.0): `.kicad_sym` **20251024**, `.kicad_mod` and
  `.kicad_pcb` **20260206**. Generator strings: `"kicad_symbol_editor"` and
  `"pcbnew"`; `generator_version "10.0"`. `kicad-cli sym upgrade lib.kicad_sym`
  and `kicad-cli fp upgrade lib.pretty` rewrite old-stamp files (easyeda2kicad
  emits v6-era stamps) to the current form — run them after any import so the
  house library has one dialect.

## Symbol library (`.kicad_sym`)

```
(kicad_symbol_lib (version 20251024) (generator "kicad_symbol_editor") (generator_version "10.0")
  (symbol "LIBRARY_ID"                 ; = the MPN; per-MPN symbols
    [(power global|local)]             ; only for power symbols
    [(pin_numbers (hide yes))]
    [(pin_names [(offset 1.016)] [(hide yes)])]
    (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at X Y ANGLE) (effects (font (size 1.27 1.27)) [(justify left)]) )
    (property "Value" ...) (property "Footprint" "house:PKG_NAME" ... (hide yes)) (property "Datasheet" ...)
    (property "Description" ...)       ; any further (property "Key" "Value" ...) is a user field
    (symbol "LIBRARY_ID_U_S"           ; U = unit (1..n, 0 = shared by all units), S = body style (1, 2 = DeMorgan)
      [(unit_name "Name")]
      graphics... pins...)
    ...more units...
    (embedded_fonts no))
  (symbol "OTHER_ID" (extends "LIBRARY_ID") properties... )   ; derived symbol: same drawing, new fields
)
```

Mandatory properties on a root symbol: `Reference`, `Value`, `Footprint`,
`Datasheet`, `Description` (Description became a field in v7.99). Footprint
value is `LIBNICKNAME:FOOTPRINT_NAME`.

Graphic items (all take `(stroke (width W) (type default|solid|dash|...))` and
`(fill (type none|outline|background|color|hatch|reverse_hatch|cross_hatch))`):
```
(rectangle (start X1 Y1) (end X2 Y2) [(radius R)] (stroke ...) (fill ...))
(polyline (pts (xy X Y) (xy X Y) ...) (stroke ...) (fill ...))
(circle (center X Y) (radius R) (stroke ...) (fill ...))
(arc (start X Y) (mid X Y) (end X Y) (stroke ...) (fill ...))
(text "..." (at X Y ANGLE) (effects (font (size H W)) [(justify left|right top|bottom)]))
```

Pin:
```
(pin ELECTRICAL_TYPE GRAPHIC_STYLE (at X Y ANGLE) (length L) [(hide yes)]
  (name "NAME" (effects (font (size 1.27 1.27))))
  (number "NUM" (effects (font (size 1.27 1.27))))
  [(alternate "ALT_NAME" ELECTRICAL_TYPE GRAPHIC_STYLE)] ...)
```
`at` is the wire-connection end; `ANGLE` is the direction the pin body points
from there: 0 = right (a left-side pin), 180 = left (right-side pin), 90 = up
(bottom pin), 270 = down (top pin). Length 2.54 default; keep the connection
end on the 1.27 grid or wires will not snap.

**Electrical types (12):** `input` `output` `bidirectional` `tri_state` `passive`
`free` `unspecified` `power_in` `power_out` `open_collector` `open_emitter`
`no_connect`. (`nc` in older docs is `no_connect` in the file.)
**Graphic styles (9):** `line` `inverted` `clock` `inverted_clock` `input_low`
`clock_low` `output_low` `edge_clock_high` `non_logic`. Use `line` unless the
datasheet draws the bubble or the clock wedge.

**Stacked pin notation (new in 9.99/10):** a pin number written `"[5,6,7]"` is
one drawn pin that maps to three pads. Expand these before diffing pin counts.

### Minimal worked example — 8-pin SON with exposed pad, one unit

```
(kicad_symbol_lib (version 20251024) (generator "kicad_symbol_editor") (generator_version "10.0")
  (symbol "EXAMPLE_BUCK_SON8"
    (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "U" (at -7.62 8.89 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "EXAMPLE_BUCK_SON8" (at -7.62 -8.89 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "house:SON-8_3x3mm_P0.65mm_EP1.6x2.4mm" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "https://example.com/ds.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Description" "Example sync buck, 3x3 SON-8 + EP" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Source" "easyeda2kicad C000000 2026-09-03, pins re-verified against DS rev C p.4" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "License" "EasyEDA/LCSC, converted; see library/LICENSES.md" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (symbol "EXAMPLE_BUCK_SON8_0_1"
      (rectangle (start -7.62 7.62) (end 7.62 -7.62) (stroke (width 0.254) (type default)) (fill (type background))))
    (symbol "EXAMPLE_BUCK_SON8_1_1"
      (pin power_in line (at 0 10.16 270) (length 2.54) (name "VIN" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
      (pin input line (at -10.16 2.54 0) (length 2.54) (name "EN" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
      (pin input line (at -10.16 -2.54 0) (length 2.54) (name "FB" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
      (pin power_in line (at 0 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
      (pin passive line (at 10.16 -2.54 180) (length 2.54) (name "BOOT" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
      (pin output line (at 10.16 2.54 180) (length 2.54) (name "SW" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
      (pin open_collector line (at 10.16 5.08 180) (length 2.54) (name "PG" (effects (font (size 1.27 1.27)))) (number "7" (effects (font (size 1.27 1.27)))))
      (pin no_connect line (at -10.16 5.08 0) (length 2.54) (hide yes) (name "NC" (effects (font (size 1.27 1.27)))) (number "8" (effects (font (size 1.27 1.27)))))
      (pin passive line (at 2.54 -10.16 90) (length 2.54) (name "EP" (effects (font (size 1.27 1.27)))) (number "9" (effects (font (size 1.27 1.27))))))
    (embedded_fonts no)))
```
Nine pins, nine pads. The EP is pin `"9"` here and must be pad `"9"` in the
footprint — same string, not "EP" on one side and "9" on the other.

## Footprint (`.kicad_mod`, one footprint per file inside `NAME.pretty/`)

```
(footprint "NAME" (version 20260206) (generator "pcbnew") (generator_version "10.0")
  (layer "F.Cu")                                  ; the side it is defined on
  [(descr "...")] [(tags "kw kw")]
  (property "Reference" "REF**" (at X Y ANGLE) (layer "F.SilkS") [(hide yes)] (effects (font (size 1 1) (thickness 0.15))))
  (property "Value" "NAME" (at X Y ANGLE) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
  (property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects ...))
  (property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects ...))
  [(property "ki_fp_filters" "...")]
  [(solder_paste_margin M)] [(solder_paste_margin_ratio R)] [(clearance C)] [(zone_connect 0|1|2)]
  (attr smd|through_hole [board_only] [exclude_from_pos_files] [exclude_from_bom] [allow_missing_courtyard] [dnp] [allow_soldermask_bridges])
  (fp_text user "TEXT" (at X Y ANGLE) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))
  (fp_line (start X Y) (end X Y) (stroke (width W) (type solid)) (layer "F.SilkS"))
  (fp_rect (start X Y) (end X Y) (stroke ...) (fill no) (layer "F.CrtYd"))
  (fp_circle (center X Y) (end X Y) (stroke ...) (fill no|yes) (layer "F.SilkS"))
  (fp_poly (pts (xy X Y) ...) (stroke ...) (fill yes) (layer "F.Fab"))
  (pad "NUM" TYPE SHAPE (at X Y [ANGLE]) (size X Y) [(drill [oval] D [D2] [(offset X Y)])]
       [(property pad_prop_bga|pad_prop_fiducial_glob|pad_prop_fiducial_loc|pad_prop_testpoint|pad_prop_heatsink|pad_prop_castellated|pad_prop_mechanical|pad_prop_pressfit)]
       (layers "F.Cu" "F.Paste" "F.Mask") [(remove_unused_layers no)] [(roundrect_rratio 0.25)]
       [(solder_mask_margin M)] [(solder_paste_margin M)] [(solder_paste_margin_ratio R)]
       [(clearance C)] [(zone_connect 0|1|2)] [(thermal_bridge_width W)] [(thermal_gap G)])
  (embedded_fonts no)
  (model "PATH.step" (offset (xyz X Y Z)) (scale (xyz 1 1 1)) (rotate (xyz X Y Z))))
```

Pad **TYPE**: `smd` `thru_hole` `np_thru_hole` `connect` (copper, no paste — a
test point or castellation). Pad **SHAPE**: `circle` `rect` `oval` `roundrect`
`trapezoid` `custom`. Mandatory fields: Reference (F.SilkS), Value (F.Fab),
Datasheet, Description. `zone_connect` 0 = none, 1 = thermal relief, 2 = solid.
Layers you will use: `F.Cu F.Paste F.Mask F.SilkS F.Fab F.CrtYd`, `*.Cu *.Mask`
for through-hole, and the `B.` mirror of each. House line widths: silk 0.12,
fab 0.10, courtyard 0.05; courtyard on a 0.01 grid.

### Minimal worked example — SON-8 3×3 mm, 0.65 pitch, 1.6×2.4 EP

Land pattern from `ipc7351.py noleads L=2.90,3.10 T=0.30,0.50 W=0.20,0.30
pitch=0.65 n=4` (pads 0.91×0.23 at ±1.40; rounded here to a 0.05 grid) and
`ipc7351.py paste W=1.60 H=2.40` (1×2 windows, 60 %).

```
(footprint "SON-8_3x3mm_P0.65mm_EP1.6x2.4mm" (version 20260206) (generator "pcbnew") (generator_version "10.0")
  (layer "F.Cu")
  (descr "SON-8 (WSON/DFN) 3x3mm pitch 0.65mm, exposed pad 1.6x2.4mm, IPC-7351B level B; source: generated from datasheet drawing")
  (tags "SON DFN WSON 3x3 0.65 EP")
  (property "Reference" "REF**" (at 0 -2.4 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (property "Value" "SON-8_3x3mm_P0.65mm_EP1.6x2.4mm" (at 0 2.4 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
  (property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))
  (property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))
  (attr smd)
  (fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.5 0.5) (thickness 0.08))))
  (fp_line (start -1.5 -1.5) (end 1.5 -1.5) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
  (fp_line (start 1.5 -1.5) (end 1.5 1.5) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
  (fp_line (start 1.5 1.5) (end -1.5 1.5) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
  (fp_line (start -1.5 1.5) (end -1.5 -1.5) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
  (fp_line (start -1.5 -1.0) (end -1.0 -1.5) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
  (fp_line (start -1.55 1.55) (end -1.35 1.55) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
  (fp_line (start 1.55 -1.55) (end 1.35 -1.55) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
  (fp_line (start 1.55 1.55) (end 1.35 1.55) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
  (fp_circle (center -1.95 -1.55) (end -1.85 -1.55) (stroke (width 0.12) (type solid)) (fill yes) (layer "F.SilkS"))
  (fp_rect (start -2.1 -1.75) (end 2.1 1.75) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
  (pad "1" smd roundrect (at -1.4 -0.975) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "2" smd roundrect (at -1.4 -0.325) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "3" smd roundrect (at -1.4 0.325) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "4" smd roundrect (at -1.4 0.975) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "5" smd roundrect (at 1.4 0.975) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "6" smd roundrect (at 1.4 0.325) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "7" smd roundrect (at 1.4 -0.325) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "8" smd roundrect (at 1.4 -0.975) (size 0.9 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "9" smd rect (at 0 0) (size 1.6 2.4) (layers "F.Cu" "F.Mask") (zone_connect 2))
  (pad "" smd rect (at 0 -0.6) (size 1.24 0.93) (layers "F.Paste"))
  (pad "" smd rect (at 0 0.6) (size 1.24 0.93) (layers "F.Paste"))
  (embedded_fonts no)
  (model "${KIPRJMOD}/library/house.3dshapes/SON-8_3x3mm_P0.65mm_EP1.6x2.4mm.step"
    (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0))))
```
Notes on the example: pin 1 is top-left in the board's +Y-down convention,
marked by a filled silk dot that replaces that corner tick and sits 0.35 mm
clear of pad 1; pads 1–4 run down the left, 5–8 up the right (counter-clockwise from above, as
every JEDEC drawing numbers them). The EP is on `F.Cu F.Mask` only; paste comes
from the two unnumbered `F.Paste`-only pads. A copper pad with an empty number
is not a connection and must be excluded from the pad count.

## Extracting pins and pads for the diff (inline Python, no library)

```python
import re, sys
sym = open("library/house.kicad_sym").read()
blk = re.search(r'\(symbol "MPN"(.*?)\n  \(symbol "', sym, re.S)   # narrow to one root symbol first
pins = re.findall(r'\(pin (\w+) \w+ .*?\(name "([^"]*)".*?\(number "([^"]*)"', blk.group(0), re.S)
# -> [(etype, name, number)]; expand "[a,b]" stacked numbers; unit _0_ pins count once
mod = open("library/house.pretty/PKG.kicad_mod").read()
pads = re.findall(r'\(pad "([^"]*)" (\w+) \w+ .*?\(layers ([^)]*)\)', mod, re.S)
pads = [(n, t) for n, t, lay in pads if n and ("Cu" in lay)]         # drop paste-only and unnumbered
```
Compare `set(numbers)` both ways, then per-number name/type against the part
record. Duplicate pad numbers (two pads both `"5"`) are legal and mean one net;
count unique numbers, not pads.

## easyeda2kicad output, for reference

`easyeda2kicad --full --lcsc_id=Cxxxx --output library/house` writes
`library/house.kicad_sym` (appends to it if present), `library/house.pretty/`,
`library/house.3dshapes/` (WRL and STEP) and points the footprint `model` at
`${EASYEDA2KICAD}/house.3dshapes/NAME.wrl`. Expect: v6-era version stamps
(run `kicad-cli sym|fp upgrade`), footprint named after the EasyEDA package
string (rename to the house package name), the EP as one paste aperture with
paste, `Footprint` property pointing at `easyeda2kicad:` (fix the nickname),
and the WRL scale bug in some versions (see SKILL.md). Treat all of it as a
candidate, not a result.
