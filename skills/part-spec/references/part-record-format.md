# `parts/<mpn>.json` — record format

One file per manufacturer part number, filename exactly the MPN as the
manufacturer writes it (`TPS562201DDCR.json`, not `tps562201.json`). JSON, not
YAML, so that a downstream Python check can load it without a parser argument
and so trailing-comma mistakes fail loudly.

Conventions that hold everywhere in the record:

- **Every number carries a `page`** (datasheet page, PDF numbering) or a
  `section`. A number with no page is one nobody can check.
- **Unknown is `null` with a sibling `<field>_reason`.** Never a typical-looking
  value. `"psi_jt_c_per_w": null, "psi_jt_reason": "not given in rev B"`.
- **Units are in the key name** (`_v`, `_a`, `_ma`, `_ua`, `_mm`, `_c`,
  `_c_per_w`, `_khz`) so a value is never ambiguous and a reviewer never has to
  look up a units field.
- **Tolerances as `[min, typ, max]`** with `null` for a bound not given.
  Package dimensions always have them — the land-pattern check needs the max
  lead span and min lead width, not the nominal.
- **Pin electrical type** is one of: `power_in`, `power_out`, `input`, `output`,
  `bidirectional`, `open_drain`, `passive`, `nc`. These map onto KiCad symbol
  pin types, which is why the vocabulary is fixed.

## Shape

```
mpn, manufacturer, description, part_class_satisfied
substitutable, substitutable_reason
descriptors        the house "fully specified" set: package, value, tolerance,
                   voltage rating, dielectric, temp grade, plus anything the
                   part was chosen for
pins[]             number, name, type, function, page
abs_max[]          pins (list or group name), min/max, condition, page
recommended_operating[]  same shape, the range the design must stay inside
electrical[]       the parameters the design leans on: name, [min,typ,max],
                   unit, condition, page
thermal            theta_ja with board condition, theta_jc, psi_jt, tj_max,
                   page
package            name, pins, pitch, body, lead span/width/length, thermal
                   pad, standoff, all with tolerances; land_pattern_source
required_externals[]  role, between (pins), value or formula, notes, page
sequencing[]       requirement text, pins involved, timing, section
errata             status + items or searched list
model_3d           filled by symbol-footprint, left null here
source             datasheet url/rev/date/local path, lcsc, jlc status,
                   distributor urls seen during Find, retrieved date
checks             pin_crosscheck result, pin count check
confidence         per section: high | medium | low, with reason if not high
revision_diff      only present when re-extracted after a datasheet rev change
```

## Worked example

A 2A synchronous buck in SOT-23-6, the kind of part power-architecture proposes
for a 3V3 rail off a 12V input. **The numbers below are illustrative of the
shape, not a substitute for extraction** — pull the current datasheet and let
the pipeline fill them.

```json
{
  "mpn": "TPS562201DDCR",
  "manufacturer": "Texas Instruments",
  "description": "4.5V-17V input, 2A synchronous step-down converter, SOT-23-6",
  "part_class_satisfied": "sync buck, Vin<=17V, Iout>=1A  (power_tree.yaml rail 3V3)",
  "substitutable": false,
  "substitutable_reason": "controller; feedback network, Cbst and inductor selection are specific to this part",

  "descriptors": {
    "package": "SOT-23-6 (TI DDC)",
    "temp_grade": "-40..125C junction",
    "vin_range_v": [4.5, null, 17],
    "iout_max_a": 2.0,
    "rohs": true,
    "lifecycle": "active",
    "lifecycle_source": "https://www.ti.com/product/TPS562201  retrieved 2026-09-03"
  },

  "pins": [
    {"number": 1, "name": "GND",  "type": "power_in",  "function": "ground; return for power stage and analog", "page": 3},
    {"number": 2, "name": "SW",   "type": "output",    "function": "switch node; connect to inductor and Cbst", "page": 3},
    {"number": 3, "name": "VIN",  "type": "power_in",  "function": "input supply, 4.5-17V; bypass to GND close to pin", "page": 3},
    {"number": 4, "name": "VFB",  "type": "input",     "function": "feedback; connect divider from Vout", "page": 3},
    {"number": 5, "name": "EN",   "type": "input",     "function": "enable; high = on, has internal pull-up, may be left floating", "page": 3},
    {"number": 6, "name": "VBST", "type": "passive",   "function": "bootstrap for high-side gate; cap to SW", "page": 3}
  ],

  "abs_max": [
    {"pins": ["VIN"],        "min_v": -0.3, "max_v": 19,  "condition": "dc",                 "page": 4},
    {"pins": ["SW"],         "min_v": -0.3, "max_v": 19,  "condition": "dc",                 "page": 4},
    {"pins": ["SW"],         "min_v": -3.0, "max_v": 21,  "condition": "transient, <10 ns",  "page": 4},
    {"pins": ["EN", "VFB"],  "min_v": -0.3, "max_v": 6.5, "condition": "dc",                 "page": 4},
    {"pins": ["VBST"],       "min_v": -0.3, "max_v": 25,  "condition": "dc, referenced to GND", "page": 4},
    {"pins": ["VBST"],       "min_v": -0.3, "max_v": 6.5, "condition": "referenced to SW",    "page": 4},
    {"pins": "junction",     "max_c": 150,  "condition": "operating Tj",                     "page": 4},
    {"pins": "storage",      "min_c": -55,  "max_c": 150,                                    "page": 4}
  ],

  "recommended_operating": [
    {"pins": ["VIN"], "min_v": 4.5, "max_v": 17, "page": 4},
    {"pins": "junction", "min_c": -40, "max_c": 125, "page": 4}
  ],

  "electrical": [
    {"name": "vfb_ref",       "value": [0.750, 0.765, 0.780], "unit": "V",   "condition": "Tj 25C",          "page": 5},
    {"name": "iq_operating",  "value": [null, 380, null],     "unit": "uA",  "condition": "VIN 12V, EN high, no load, non-switching", "page": 5},
    {"name": "iq_shutdown",   "value": [null, 1.5, null],     "unit": "uA",  "condition": "EN low",          "page": 5},
    {"name": "f_sw",          "value": [null, 580, null],     "unit": "kHz", "condition": "continuous mode", "page": 5},
    {"name": "i_limit_hs",    "value": [2.6, 3.2, null],      "unit": "A",   "condition": "high-side valley", "page": 5},
    {"name": "en_threshold",  "value": [null, 1.2, null],     "unit": "V",   "condition": "rising",          "page": 5}
  ],

  "thermal": {
    "theta_ja_c_per_w": 106,
    "theta_ja_board": "JEDEC JESD51-7 high-K 2s2p, 4-layer",
    "theta_jc_top_c_per_w": 67,
    "psi_jt_c_per_w": 12,
    "psi_jb_c_per_w": 40,
    "tj_max_c": 150,
    "page": 4,
    "note": "theta_ja on a 1s0p board would be roughly 2x; use psi_jt with a top-side measurement for bench checks"
  },

  "package": {
    "name": "SOT-23-6",
    "vendor_code": "DDC",
    "pins": 6,
    "pitch_mm": 0.95,
    "body_length_mm": [2.8, 2.9, 3.0],
    "body_width_mm":  [1.5, 1.6, 1.7],
    "height_mm":      [null, null, 1.45],
    "lead_span_mm":   [2.6, 2.8, 3.0],
    "lead_width_mm":  [0.30, 0.40, 0.50],
    "lead_length_mm": [0.30, 0.45, 0.60],
    "standoff_mm":    [0.00, null, 0.15],
    "thermal_pad": null,
    "thermal_pad_reason": "package has no exposed pad",
    "land_pattern_source": "datasheet mechanical drawing, page 22; TI recommended land pattern page 23",
    "page": 22
  },

  "required_externals": [
    {"role": "input_bypass",  "between": ["VIN", "GND"],  "value": "10uF ceramic, X7R/X5R, >=25V for 12V in per house derating; place at pin", "page": 12},
    {"role": "bootstrap_cap", "between": ["VBST", "SW"],  "value": "100nF ceramic, >=10V", "page": 12},
    {"role": "inductor",      "between": ["SW", "VOUT"],  "formula": "L = (Vin_max - Vout) * Vout / (Vin_max * f_sw * dI), dI = 0.3 * Iout; 2.2uH typical for 3V3 from 12V; Isat >= Iout + dI/2", "page": 13},
    {"role": "output_cap",    "between": ["VOUT", "GND"], "value": "2 x 22uF ceramic, X5R, >=10V (post-DC-bias); stability window 20-68uF effective", "page": 13},
    {"role": "feedback_divider_high", "between": ["VOUT", "VFB"], "formula": "R_high / R_low = Vout / Vref - 1, Vref = 0.765V; R_low 10k recommended", "page": 13},
    {"role": "feedback_divider_low",  "between": ["VFB", "GND"],  "value": "10k, 1%", "page": 13},
    {"role": "enable_pullup", "between": ["EN", "VIN"], "value": "optional; internal pull-up, leave floating or drive from MCU", "page": 12}
  ],

  "sequencing": [
    {"requirement": "Vout starts when EN > 1.2V and VIN > UVLO; internal soft-start ~1ms", "pins": ["EN", "VIN"], "timing_ms": {"min": null, "typ": 1.0, "max": null}, "section": "7.3.2"}
  ],

  "errata": {
    "status": "searched_none_found",
    "searched": ["ti.com TPS562201 errata", "web: \"TPS562201\" errata OR \"known issue\"", "e2e.ti.com TPS562201"],
    "date": "2026-09-03",
    "items": []
  },

  "model_3d": null,

  "source": {
    "datasheet_url": "https://www.ti.com/lit/ds/symlink/tps562201.pdf",
    "datasheet_rev": "SLVSCV9B",
    "datasheet_date": "2016-08",
    "datasheet_local": "datasheets/TPS562201DDCR-SLVSCV9B.pdf",
    "lcsc_id": "C127160",
    "lcsc_url": "https://www.lcsc.com/product-detail/C127160.html",
    "jlc_status": "extended",
    "lcsc_stock_at_retrieval": 12480,
    "lcsc_price_usd_at_100": 0.42,
    "seen_at": [
      "https://www.lcsc.com/product-detail/C127160.html",
      "https://www.ti.com/product/TPS562201",
      "https://www.digikey.com/en/products/detail/texas-instruments/TPS562201DDCR/5352398"
    ],
    "retrieved": "2026-09-03",
    "extraction": "fallback: page-targeted Read (pipeline not hooked up)"
  },

  "checks": {
    "pin_count_matches_package": true,
    "pin_numbers_unique": true,
    "pin_crosscheck": {
      "against": "easyeda2kicad --symbol --lcsc_id=C127160",
      "result": "match",
      "mismatches": []
    }
  },

  "confidence": {
    "pins": "high",
    "abs_max": "high",
    "electrical": "medium",
    "electrical_reason": "iq_operating read from a table cell with a footnote I could not fully parse; confirm",
    "thermal": "high",
    "package": "medium",
    "package_reason": "lead_length tolerance read from drawing; verify against TI land pattern page",
    "required_externals": "high",
    "sequencing": "medium",
    "sequencing_reason": "soft-start time is typical only, no min/max given",
    "errata": "high"
  }
}
```

## Notes on specific fields

**`abs_max[].pins`** takes a list of pin names or the strings `"junction"`,
`"storage"`, `"esd_hbm"`, `"esd_cdm"`. Two entries for the same pin with
different `condition` is normal (dc vs transient) — keep both; the review checks
the dc one against rail voltages and the transient one against switch-node
overshoot.

**`required_externals[].between`** always names two pins (or a pin and a net the
part defines, like `VOUT`). A value that depends on the rail is a `formula`
with every constant named; a fixed value is `value`. Include the datasheet's
own recommendation as text — schematic-capture uses it, schematic-review checks
the drawn part against it.

**`thermal.theta_ja_board`** is mandatory when `theta_ja_c_per_w` is set. The
JEDEC condition is the difference between a part that runs at 85°C and one
that runs at 130°C on the same board.

**`package.*` tolerances** exist so symbol-footprint can check an acquired
footprint's pad extents against the max lead span and the pad width against the
min lead width. If the datasheet gives only nominal, record `[null, nom, null]`
and set `confidence.package` to `medium` with the reason.

**`substitutable`** is read by `release` when building the BOM. A `true` here
means purchasing may swap an equivalent; the MPN is still binding in the design
files.

**`revision_diff`** appears only when an existing record was re-extracted
against a newer datasheet:

```json
"revision_diff": {
  "from_rev": "SLVSCV9A", "to_rev": "SLVSCV9B",
  "previous_record": "parts/TPS562201DDCR.SLVSCV9A.json",
  "changed": [
    {"section": "thermal", "field": "theta_ja_c_per_w", "from": 112, "to": 106, "note": "board condition restated as 2s2p"},
    {"section": "abs_max", "field": "SW transient max_v", "from": 20, "to": 21}
  ],
  "unchanged": ["pins", "package", "required_externals", "sequencing"]
}
```

Anyone who consumed the old record — symbol-footprint, schematic-review — reads
`changed` to decide whether their output needs another look.
