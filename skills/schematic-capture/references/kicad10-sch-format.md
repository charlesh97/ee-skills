# KiCad 10 `.kicad_sch` — the grammar you need to emit a schematic

Everything here was checked on 2026-09-03 against two sources: the official
"Schematic File Format" page at dev-docs.kicad.org (which documents the format
generically "from 6.0" and does not carry the newer tokens) and the KiCad 10.0
branch source — `eeschema/sch_file_versions.h`, the writer
`sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp`, the library-cache writer
`sch_io_kicad_sexpr_lib_cache.cpp`, the parser `sch_io_kicad_sexpr_parser.cpp`,
`common/project/project_file.cpp`, `eeschema/schematic_settings.cpp` and
`kicad/cli/command_sch_*.cpp`. Where the two disagree the source wins; it is
what `kicad-cli` actually runs. What was **not** verified: the file has not been
round-tripped through a live `kicad-cli` in this environment (none installed
here), so treat the worked example as "matches what the 10.0 writer emits", not
"opened in KiCad 10 today". The first thing the skill does with any emitted file
is run `kicad-cli sch erc` on it, which is the real test.

Units are millimetres. Angles are degrees. Booleans are `yes` / `no`. The
default grid is 1.27 mm and library pins sit on a 2.54 mm pitch; put every pin
end, wire end, junction and label anchor on the 1.27 mm grid or ERC will report
pins that look connected but are not.

## Version and header

```
(kicad_sch (version 20260306) (generator "ee-skills") (generator_version "10.0")
  (uuid "ROOT-FILE-UUID")
  (paper "A4")
  (title_block (title "sensor node") (rev "A") (company "Example Co") (comment 1 "MCU"))
  (lib_symbols ...)
  ;; items: junction, no_connect, wire, bus, label, global_label,
  ;;        hierarchical_label, symbol, sheet — any order
  (sheet_instances (path "/" (page "1")))     ; root file only
  (embedded_fonts no)                          ; root file only
)
```

- The `;;` comments above are for this page only — the format has no comment
  syntax, so never emit them.
- `version` is the file-format date. KiCad 10.0 writes **20260306** ("Variant
  in_bom semantics corrected", `sch_file_versions.h` on the 10.0 branch). A file
  stamped later than the reader's own version is refused as a future format, so
  never write a date later than the installed KiCad's. The date also selects
  parser semantics — at ≥20241004 `hide` is a boolean `(hide yes)`, at ≥20250318
  `~` is literal text not "empty" — so write 20260306 and use the modern forms.
- `generator` is free text; `generator_version` is optional (present since
  20231120). Do not claim to be `eeschema`.
- The root file's `(uuid ...)` **is the root sheet's UUID**. Every instance path
  in the project starts with it. Keep it stable across re-runs.
- `title_block` is optional. `paper` accepts A0–A5, A–E, or `"User" W H`.

## `lib_symbols` — the symbols this file uses, inlined

Every symbol placed on the sheet needs a full copy of its library definition
here, keyed `"LIB:NAME"`. This is a cache, not a reference: copy the definition
verbatim from `$EE_LIB/house*.kicad_sym` (symbol-footprint put it there), renaming the
outer symbol from `"NAME"` to `"LIB:NAME"`; sub-units keep `"NAME_U_S"`.

```
(lib_symbols
  (symbol "Device:R" (pin_numbers (hide yes)) (pin_names (offset 0))
    (exclude_from_sim no) (in_bom yes) (on_board yes)
    (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
    (property "Value" "R" (at 0 0 90) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at -1.778 0 90) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "~" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "Resistor" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
    (symbol "R_0_1"
      (rectangle (start -1.016 -2.54) (end 1.016 2.54)
        (stroke (width 0.254) (type default)) (fill (type none))))
    (symbol "R_1_1"
      (pin passive line (at 0 3.81 270) (length 1.27)
        (name "~" (effects (font (size 1.27 1.27))))
        (number "1" (effects (font (size 1.27 1.27)))))
      (pin passive line (at 0 -3.81 90) (length 1.27)
        (name "~" (effects (font (size 1.27 1.27))))
        (number "2" (effects (font (size 1.27 1.27))))))
    (embedded_fonts no))
)
```

- Unit naming: `NAME_U_S` — `U` = unit (0 = shared by all units), `S` = body
  style (1 normal, 2 DeMorgan). Graphics go in `_0_1`, pins in `_1_1` (or per
  unit for multi-unit parts).
- Pin: `(pin ELECTRICAL GRAPHIC (at X Y ANGLE) (length L) [(hide yes)] (name ...) (number ...))`.
  Electrical: `input output bidirectional tri_state passive free unspecified
  power_in power_out open_collector open_emitter no_connect`. Graphic: `line
  inverted clock inverted_clock input_low clock_low output_low edge_clock
  non_logic`. Angle is the direction the pin points *away from* the body: a pin
  at `(0 3.81 270)` sits above the body and points down into it; its connection
  point is at `(0 3.81)`.
- **Library coordinates are Y-up; the sheet is Y-down.** The writer negates Y on
  save. For a symbol placed at `(at SX SY 0)` a library pin at `(px py)` lands at
  `(SX + px, SY − py)`. At 90° it lands at `(SX − py, SY − px)`; at 180° at
  `(SX − px, SY + py)`; at 270° at `(SX + py, SY + px)`. *(Corrected 2026-09-28:
  an earlier version of this file had 90° and 270° swapped. Verified with
  kicad-cli 10.0.6 by placing `Transistor_FET:BSS138` at 0/90/270 and reading
  the pin positions ERC reports. At (101.6, 101.6, 90) pin 1, library
  (−5.08, 0), is at (101.6, 106.68).)* Symmetric two-pin parts like `Device:R`
  hide this error, because both transforms map their pin pair onto itself. Check
  the transform on an asymmetric part (a transistor or an IC) before trusting
  it. ERC's `pin_not_connected` positions, in units of 100 mm, are a quick
  oracle.
- **Field angles are stored relative to the symbol's rotation; field positions
  are absolute.** Displayed angle = stored angle + symbol rotation (mod 180; KiCad
  keeps text readable). So on a symbol at 90°, a Reference written at angle 0
  displays vertical, and one written at 90 displays horizontal. For example, in
  a hand-drawn sheet, horizontal `R26` at rot 90 stores 90, and
  vertical `R32` at rot 0 also stores 90. `justify` is likewise interpreted in
  the symbol's frame, so a 180° rotation or a mirror flips left and right.
  Compute the stored angle from the angle you want displayed, then confirm by
  rendering.
- **PWR_FLAG placement (KiCad 10 ERC):** a PWR_FLAG on a sheet where its net
  has nothing else but a rail symbol makes ERC report that rail symbol's pin as
  `pin_not_connected`. Put each flag on a real wire of the net it flags, where
  the rail enters: the connector pin or the passive it comes through. Don't put
  them in an isolated block on a sheet of their own. This modifies D-32's "one
  block" to "one block on the sheet where the rails enter".
- Power symbols carry `(power global)` after the name (parser also accepts bare
  `(power)` and `(power local)`). Their single pin is `power_in`, hidden, at the
  origin, and **the Value property is the net name** (since 20230221). So one
  library symbol `power:PWR` can serve every rail: place it and set Value to
  `3V3`, `1V8`, `GND`. Keep the symbol name and Value identical anyway so the
  render reads correctly.
- Multiple inheritance: `(symbol "Device:R_Small" (extends "R") (property ...))`
  — avoid it in emitted files; copy the flattened parent instead.

## Symbol instance on a sheet

```
(symbol (lib_id "Device:R") (at 63.5 63.5 0) [(mirror x|y)] (unit 1) (body_style 1)
  (exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
  (uuid "R1-UUID")
  (property "Reference" "R1" (at 65.278 62.23 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Value" "10k" (at 65.278 64.77 0) (effects (font (size 1.27 1.27)) (justify left)))
  (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Datasheet" "https://..." (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Description" "RES 10k 5% 0402 62.5mW" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "MPN" "RC0402JR-0710KL" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Manufacturer" "Yageo" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "LCSC" "C25744" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Tolerance" "5%" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Voltage" "50V" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (property "Why" "I2C pull-up 400kHz Cb 20pF: Rp_max=tr/(0.8473*Cb)=17.7k, Rp_min=(Vdd-0.4)/3mA=967R; 10k E24" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
  (pin "1" (uuid "R1-P1-UUID"))
  (pin "2" (uuid "R1-P2-UUID"))
  (instances (project "node" (path "/ROOT-FILE-UUID" (reference "R1") (unit 1))))
)
```

- `at` angle must be exactly 0, 90, 180 or 270 and is mandatory.
- `unit`, `body_style`, the five flags and `fields_autoplaced` are all optional
  to the parser; write the flags anyway so intent is explicit.
- Mandatory properties: Reference, Value, Footprint, Datasheet, Description.
  Anything else is a user field — that is where the house descriptor set goes
  (MPN, Manufacturer, LCSC, Tolerance, Voltage, Dielectric, Temp, Why …) and
  `kicad-cli sch export bom --fields` reads them by name.
- A pin `(alternate "NAME")` selects a library alternate function; the MCU
  pinmap uses this rather than renaming pins.
- `instances`: one `path` per sheet instance the symbol appears in. The path is
  `"/" + root file uuid` on the root sheet, `"/ROOT/SHEETSYMBOL"` inside a
  sub-sheet, where `SHEETSYMBOL` is the uuid of the `(sheet ...)` element in the
  parent, **not** the sub-file's own `(uuid)`. `reference` here is the refdes
  that counts; the Reference property is just the displayed text — keep them
  equal.

## Design variants (DNP and stuffing options), KiCad 10

Variant names are declared in the project file and applied per instance path:

```
(instances (project "node"
  (path "/ROOT-FILE-UUID" (reference "R7") (unit 1)
    (variant (name "NO_DEBUG") (dnp yes) (in_bom no) (in_pos_files no)))))
```

Inside `variant`: `dnp`, `exclude_from_sim`, `in_bom`, `on_board`,
`in_pos_files`, and `(field (name "Value") (value "0R"))` for per-variant field
overrides. The writer only emits fields that differ from the base symbol. The
CLI selects with `--variant NAME` (repeatable; use `${VARIANT}` in `-o` when
passing several). The base `dnp`/`in_bom` on the symbol is the default variant.
Prefer this to a bare `(dnp yes)`: a variant says *why* the part is absent.

## Wires, junctions, labels, no-connects

```
(wire (pts (xy 63.5 67.31) (xy 63.5 71.12)) (stroke (width 0) (type default)) (uuid "..."))
(bus  (pts (xy 0 0) (xy 10.16 0))          (stroke (width 0) (type default)) (uuid "..."))
(junction (at 63.5 71.12) (diameter 0) (color 0 0 0 0) (uuid "..."))
(no_connect (at 88.9 60.96) (uuid "..."))
(label "I2C0_SENSORS_SDA" (at 66.04 71.12 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "..."))
(global_label "3V3_EN" (shape input) (at 50.8 50.8 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "...")
  (property "Intersheetrefs" "${INTERSHEET_REFS}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27)))))
(hierarchical_label "I2C0_SENSORS_SDA" (shape bidirectional) (at 50.8 63.5 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "..."))
```

- A wire is exactly two points. A polyline of N points is N−1 wires.
- A junction is needed only where three wire ends meet at one point (T). Two
  wires meeting end-to-end connect without one; a wire ending on a pin connects
  without one. House rule: never four ends at one point — offset the second T.
- The label anchor must lie exactly on a wire or pin end. Angle 0 reads left to
  right from the anchor, 180 reads toward the left; `justify` is where the text
  sits relative to the anchor. Local `label` scope is one sheet.
- `global_label` connects across every sheet by name. Shapes: `input output
  bidirectional tri_state passive`. Use it for named signals that cross sheets
  where a sheet pin would clutter the drawing (`nRESET`, enables). Rails use
  power symbols, not global labels.
- `hierarchical_label` connects to the same-named `pin` on the parent's `sheet`
  element, and to nothing else. Name and direction must match the sheet pin.
- `no_connect` sits on an unused pin's connection point. ERC otherwise reports
  every unconnected pin; every no-connect is a decision, so log which pins.

## Subsystem boxes and titles (D-13)

Sheet-level graphics, siblings of `wire` and `symbol` (not inside
`lib_symbols`). This is what KiCad 10.0.6 wrote back after `kicad-cli sch
upgrade` in the 2026-09-28 redraw test:

```
(rectangle (start 67.31 35.56) (end 220.98 88.9)
  (stroke (width 0.254) (type dash) (color 120 120 120 1))
  (fill (type none))
  (uuid "..."))
(text "I2C bus 0:  MCU 3.3 V  <->  sensor #0, 1.8 V   (U13)"
  (exclude_from_sim no)
  (at 68.58 34.56 0)
  (effects (font (size 1.7 1.7) (bold yes)) (justify left bottom))
  (uuid "..."))
```

Keep `start`/`end` on the 1.27 mm grid. The title sits just above the top edge,
anchored `left bottom`. Graphics carry no connectivity, so a box edge crossing
a wire changes nothing electrically. It still has to stay clear of symbols and
text (D-44).

## Hierarchical sheet element (in the parent file)

```
(sheet (at 76.2 63.5) (size 25.4 15.24)
  (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
  (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0))
  (uuid "SHEET-MCU-UUID")
  (property "Sheetname" "MCU" (at 76.2 62.788 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
  (property "Sheetfile" "mcu.kicad_sch" (at 76.2 79.3246 0) (effects (font (size 1.27 1.27)) (justify left top)))
  (pin "I2C0_SENSORS_SDA" bidirectional (at 76.2 71.12 180) (uuid "...")
    (effects (font (size 1.27 1.27)) (justify right)))
  (instances (project "node" (path "/ROOT-FILE-UUID" (page "2"))))
)
```

- `Sheetname` and `Sheetfile` are the canonical property names (the parser also
  accepts legacy "Sheet name"/"Sheet file"). Sheet name = block name, per
  house rules. `Sheetfile` is relative to the project directory.
- Sheet pin angle encodes the side: **180 = left edge, 0 = right, 90 = top,
  270 = bottom**. The pin sits on the sheet outline; wires attach there.
- The sheet's `instances/path` is the path to the *parent* sheet (root: just
  `/ROOT-FILE-UUID`); `page` is the printed page number and must be unique.
- The sub-file is a normal `.kicad_sch` with its own `(uuid)` and
  `lib_symbols`, no `sheet_instances`, and symbol instance paths of
  `/ROOT-FILE-UUID/SHEET-MCU-UUID`.

## UUIDs

Version-4 format, quoted. Make them **deterministic**: `uuid5(PROJECT_NS,
"node/R1")`, `uuid5(PROJECT_NS, "node/R1/pin/1")`, `uuid5(PROJECT_NS,
"sheet/MCU")`, `uuid5(PROJECT_NS, "wire/I2C0_SENSORS_SDA/0")` — with
`PROJECT_NS` derived once from `project.yaml` name and persisted. A re-run then
changes only what changed, ERC exclusions keyed on uuids survive, and diffs
are readable. Never reuse a uuid for two objects; KiCad resolves items by it.

## The `.kicad_pro` and how it finds the root sheet

The project is JSON. KiCad finds the root schematic by filename convention —
`<name>.kicad_pro` opens `<name>.kicad_sch` in the same directory. KiCad 10 also
records it explicitly under `schematic.top_level_sheets` (empty list migrates to
the convention). Variant names live under `schematic.variants`; ERC exclusions
under `erc.erc_exclusions` as `[key, comment]` pairs whose key KiCad serialises
itself — do not hand-write those, fix the schematic instead.

```json
{
  "meta": { "filename": "node.kicad_pro", "version": 3 },
  "sheets": [],
  "text_variables": {},
  "schematic": {
    "meta": { "version": 1 },
    "top_level_sheets": [
      { "uuid": "ROOT-FILE-UUID", "name": "node", "filename": "node.kicad_sch" }
    ],
    "variants": [
      { "name": "NO_DEBUG", "description": "Production: debug header, TPs and zero-ohms not fitted" }
    ]
  }
}
```

Everything else (net classes, ERC severities, page settings) takes defaults.

## `kicad-cli` (10.0 argument names, from `kicad/cli/`)

```
kicad-cli sch erc  node.kicad_sch --format json --severity-all --exit-code-violations -o erc.json
kicad-cli sch export svg     node.kicad_sch --exclude-drawing-sheet --no-background-color -o svg/
kicad-cli sch export svg     node.kicad_sch --pages 2 -o svg/
kicad-cli sch export netlist node.kicad_sch --format kicadsexpr -o node.net
kicad-cli sch export bom     node.kicad_sch --fields "Reference,Value,MPN,Manufacturer,LCSC,Footprint" --variant NO_DEBUG -o bom.csv
```

ERC JSON shape: `{ "$schema", "source", "date", "kicad_version", "sheets": [ {
"uuid_path", "path", "violations": [ { "type", "description", "severity",
"excluded", "comment", "items": [ { "uuid", "description", "pos": {x,y} } ] } ] }
], "included_severities", "ignored_checks" }`. Group by `type`, then walk
`items[].uuid` back to your deterministic uuids to find the refdes.

## Worked example — two sheets, one net crossing between them

Root sheet: a 3V3 rail, a pull-up R1, the net `I2C0_SENSORS_SDA` leaving through
a sheet pin into sheet `MCU`, where it reaches test point TP1 (fitted only in
the default variant). Rails need no sheet pins: a `power:3V3` symbol placed on
`mcu.kicad_sch` would join this same net. The UUIDs are `uuid5` of a project
namespace and the object identity, as the section above recommends.

`node.kicad_sch`
```
(kicad_sch (version 20260306) (generator "ee-skills") (generator_version "10.0")
  (uuid "7d976905-544d-540a-a824-4adba7236c61")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R" (pin_numbers (hide yes)) (pin_names (offset 0))
      (exclude_from_sim no) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at 0 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at -1.778 0 90) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "~" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "Resistor" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "R_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54)
        (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))
    (symbol "power:3V3" (power global) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))
      (exclude_from_sim no) (in_bom no) (on_board yes)
      (property "Reference" "#PWR" (at 0 -3.81 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Value" "3V3" (at 0 3.556 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "Power symbol; Value is the net" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "3V3_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "3V3_1_1"
        (pin power_in line (at 0 0 90) (length 0) (hide yes)
          (name "3V3" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no)))
  (symbol (lib_id "power:3V3") (at 63.5 57.15 0) (unit 1) (body_style 1)
    (exclude_from_sim no) (in_bom no) (on_board yes) (in_pos_files no) (dnp no)
    (uuid "6112e2fb-e2a5-5c43-8b5d-061be881dec5")
    (property "Reference" "#PWR01" (at 63.5 60.96 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Value" "3V3" (at 63.5 53.594 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at 63.5 57.15 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "" (at 63.5 57.15 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "" (at 63.5 57.15 0) (hide yes) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "1f87776b-abe1-5c0b-adcf-a0393cc32328"))
    (instances (project "node" (path "/7d976905-544d-540a-a824-4adba7236c61" (reference "#PWR01") (unit 1)))))
  (symbol (lib_id "Device:R") (at 63.5 63.5 0) (unit 1) (body_style 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
    (uuid "685e713d-fd04-5910-8d84-772a51e9c348")
    (property "Reference" "R1" (at 65.278 62.23 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "10k" (at 65.278 64.77 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "Resistor_SMD:R_0402_1005Metric" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "https://www.yageo.com/upload/media/product/products/datasheet/rchip/PYu-RC_Group_51_RoHS_L_12.pdf" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "RES 10k 5% 0402 50V" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "MPN" "RC0402JR-0710KL" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Manufacturer" "Yageo" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "LCSC" "C25744" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Tolerance" "5%" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Voltage" "50V" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Why" "I2C pull-up 400kHz Cb 20pF: Rp_max=tr/(0.8473*Cb)=17.7k, Rp_min=(Vdd-0.4)/3mA=967R; 10k E24" (at 63.5 63.5 0) (hide yes) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "a1f1e1f2-6c11-502d-8508-4cee724728dd"))
    (pin "2" (uuid "deedaaa9-1b08-511a-86f1-6c1bc3ba21ba"))
    (instances (project "node" (path "/7d976905-544d-540a-a824-4adba7236c61" (reference "R1") (unit 1)))))
  (wire (pts (xy 63.5 57.15) (xy 63.5 59.69)) (stroke (width 0) (type default)) (uuid "938af38d-beac-5944-a9f6-30a25514201c"))
  (wire (pts (xy 63.5 67.31) (xy 63.5 71.12)) (stroke (width 0) (type default)) (uuid "52b9cdad-11ae-5a24-8d49-8271535594c7"))
  (wire (pts (xy 63.5 71.12) (xy 76.2 71.12)) (stroke (width 0) (type default)) (uuid "a1964858-a4c7-508f-8ca7-00463791f7ca"))
  (label "I2C0_SENSORS_SDA" (at 66.04 71.12 0) (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "c6182a1c-d773-5535-bc4c-71e307e1b46e"))
  (sheet (at 76.2 63.5) (size 25.4 15.24) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0))
    (uuid "1399c228-337b-538d-9a29-0055e1a31f13")
    (property "Sheetname" "MCU" (at 76.2 62.788 0) (effects (font (size 1.27 1.27)) (justify left bottom)))
    (property "Sheetfile" "mcu.kicad_sch" (at 76.2 79.3246 0) (effects (font (size 1.27 1.27)) (justify left top)))
    (pin "I2C0_SENSORS_SDA" bidirectional (at 76.2 71.12 180) (uuid "e12cd51b-bd54-5c51-8acf-4d53a108bee9")
      (effects (font (size 1.27 1.27)) (justify right)))
    (instances (project "node" (path "/7d976905-544d-540a-a824-4adba7236c61" (page "2")))))
  (sheet_instances (path "/" (page "1")))
  (embedded_fonts no)
)
```

`mcu.kicad_sch`
```
(kicad_sch (version 20260306) (generator "ee-skills") (generator_version "10.0")
  (uuid "ab38f93d-106a-5342-a9d7-a83c621cfdc4")
  (paper "A4")
  (lib_symbols
    (symbol "house:TP" (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes))
      (exclude_from_sim yes) (in_bom yes) (on_board yes)
      (property "Reference" "TP" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Value" "TP" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Datasheet" "~" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (property "Description" "Test point" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
      (symbol "TP_0_1" (circle (center 0 1.27) (radius 0.762) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "TP_1_1"
        (pin passive line (at 0 -2.54 90) (length 2.54)
          (name "1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no)))
  (hierarchical_label "I2C0_SENSORS_SDA" (shape bidirectional) (at 50.8 63.5 180)
    (effects (font (size 1.27 1.27)) (justify right)) (uuid "a08e08b7-b638-5f34-ac88-0b69fc57cb0a"))
  (symbol (lib_id "house:TP") (at 63.5 60.96 0) (unit 1) (body_style 1)
    (exclude_from_sim yes) (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no)
    (uuid "69e3da89-4f82-5662-be3b-3bece60d51a4")
    (property "Reference" "TP1" (at 63.5 57.15 0) (effects (font (size 1.27 1.27))))
    (property "Value" "I2C0_SENSORS_SDA" (at 63.5 58.42 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Footprint" "house:TP_Pad_D1.0mm" (at 63.5 60.96 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Datasheet" "~" (at 63.5 60.96 0) (hide yes) (effects (font (size 1.27 1.27))))
    (property "Description" "Test point, 1mm pad" (at 63.5 60.96 0) (hide yes) (effects (font (size 1.27 1.27))))
    (pin "1" (uuid "c817000e-ccb8-53c2-8c56-2f762e775f7f"))
    (instances (project "node"
      (path "/7d976905-544d-540a-a824-4adba7236c61/1399c228-337b-538d-9a29-0055e1a31f13" (reference "TP1") (unit 1)
        (variant (name "NO_DEBUG") (dnp yes) (in_bom no) (in_pos_files no))))))
  (wire (pts (xy 50.8 63.5) (xy 63.5 63.5)) (stroke (width 0) (type default)) (uuid "03831882-30d8-5e15-b228-6215dad5a395"))
  (embedded_fonts no)
)
```

Read the geometry once to see the rules at work: TP1 at `(63.5 60.96)` with a
library pin at `(0 −2.54)` puts the connection point at `(63.5, 60.96 + 2.54) =
(63.5, 63.5)`, which is where the wire from the hierarchical label ends. R1 at
`(63.5 63.5)` has pin 1 at `(63.5, 59.69)` and pin 2 at `(63.5, 67.31)`; the
wires start exactly there. The sheet pin at `(76.2 71.12 180)` is on the sheet's
left edge (x = 76.2), and the wire from R1 reaches it. ERC on this pair should
report nothing but "no driver" on `I2C0_SENSORS_SDA` (a pull-up and a test point
are both passive), which is exactly the kind of finding the ERC loop exists to
read and reason about rather than suppress.
