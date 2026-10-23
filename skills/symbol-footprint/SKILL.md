---
name: symbol-footprint
description: >
  Get a verified KiCad 10 symbol, footprint and 3D model for a part into the
  house KiCad library ($EE_LIB). Load it for "make a symbol", "I need a footprint for", "add this
  part to the library", "is this part in the library", "convert from EasyEDA or
  LCSC", "does this footprint match the datasheet", "check the pinout", "land
  pattern", "thermal pad paste", "3D model", "STEP file", or when a schematic
  names a part with no library entry. Three steps in order — look in the
  library, convert from EasyEDA, generate from the datasheet — and the part is
  not done until its pins have been checked against the datasheet.
---

# Symbol, Footprint and 3D Model

Three steps, in order. Each is more work than the one before, so do not start
lower down the list than you have to.

1. **Check the library.** Reuse costs a diff; a new part costs an afternoon.
2. **Convert from EasyEDA**, if the part has an LCSC id.
3. **Generate from the datasheet**, when the first two come up empty.

Whichever step produced it, the part is not finished until its pins have been
checked against the datasheet pin table. That check is the skill; the drawing is
just how you get there.

## Contract

```
Reads:   $EE_LIB                       the house library (see Setup)
         datasheets/<MPN>/capture.json   pins and package dimensions
         the MPN, and its LCSC id if there is one
Writes:  house original -> $EE_LIB/house.kicad_sym, house.pretty/, house.3dshapes/
         third-party    -> $EE_LIB/house_vendor.*   (same three)
         an entry in $EE_LIB/LICENSES.md, always
Stops if: the symbol and the footprint disagree on pin numbers after your fixes.
```

If `datasheets/<MPN>/capture.json` does not exist, run `datasheet-extraction`
first. Do not read pin numbers out of a PDF by eye and do not recall them: a
wrong pin table here blesses a wrong symbol, and the error surfaces at bring-up.

## Setup

`$EE_LIB` points at the house KiCad library (its own `scripts/install.py` sets it,
where it has one). If it is unset, the library is at `~/git/kicad-library`; say
that you assumed it.

EasyEDA conversion needs `pip install easyeda2kicad`.

## Step 1 — Check the library

Look in all three places before concluding the part is missing:

- `house.kicad_sym` and `house.pretty/` — house parts, no restrictions.
- `house_vendor.kicad_sym` and `house_vendor.pretty/` — third-party parts already
  vendored in, with provenance.
- `upstream/` — submodules of the Seeed OPL, SparkFun and Digi-Key libraries,
  there to browse. A part found here is **copied in** with provenance, never
  referenced in place: a board fabbed in 2026 must still open in 2030, and an
  upstream library that moves takes the board with it.

A hit is not automatically a pass. Re-run the pin check below against the
current capture — the datasheet revision may have moved since the part was
drawn. If it passes, say so and stop.

Footprints are per package and shared: one `SON-8_3x3mm_P0.65mm_EP1.6x2.4mm`
serves every chip in that package. Symbols are per MPN. Connectors and
mechanical parts are per MPN, because for them the package is the part.

## Step 2 — Convert from EasyEDA

```bash
easyeda2kicad --full --lcsc_id=<LCSC id> --output /tmp/e2k/house
kicad-cli sym upgrade /tmp/e2k/house.kicad_sym
kicad-cli fp upgrade  /tmp/e2k/house.pretty
```

Work in a scratch directory, never straight into the library — the tool appends
to an existing `.kicad_sym` and you want to look before merging.

**The library is shared, so merging is the human's call.** Whatever step made
the part, verify it in scratch first. Then show the human the diff to
`$EE_LIB` and the verification summary, and merge only after they say yes.

Expect the pinout to be roughly right and the footprint to need work. EasyEDA
footprints are drawn by the LCSC supplier and the upstream project says plainly
that it does not check them. Converted parts are third-party: they go in
`house_vendor.*`.

## Step 3 — Generate from the datasheet

Pins come from the capture's pin table, grouped by function so the symbol reads
correctly when placed: power top, ground bottom, inputs left, outputs right.
Size the body from the pin-name text, not the pin count (D-47): a 1.27 mm name
is about 1.27 mm per character plus the 1.016 mm offset, so a part with `VDD`
on top and `GND` underneath it needs more than two rows of height. A large MCU
is split into one unit per peripheral group plus a supply unit (D-14).

The land pattern comes from the datasheet's own recommended pattern where the
vendor publishes one. Where it does not, compute it:

```bash
python3 <this skill>/scripts/ipc7351.py gullwing L=2.60,3.00 T=0.30,0.60 W=0.30,0.50 pitch=0.95 n=5
python3 <this skill>/scripts/ipc7351.py paste W=1.60 H=2.40      # thermal pad windows
```

Print the numbers into the conversation before using them, and **write in
`LICENSES.md` that the land pattern is yours and not the vendor's.** The library
already does this where it matters; that note is what tells the next person
which dimensions carry a vendor's guarantee.

Calibration, so a known-good comparison does not read as a fault: on SOT-23-5
this script gives pads 1.5 × 0.57 at ±1.1, against KiCad's 1.325 × 0.6 at
±1.1375. Position and width agree within 0.04 mm; the pad runs about 0.18 mm
longer because the inner gap is stacked worst-case rather than RMS. Both are
valid at density level B, and longer means more toe fillet. A disagreement of
that size is expected; one of half a millimetre is not.

Generated parts are house originals: they go in `house.*`.

## Verify — the part of this that matters

### Pins, against the capture

Compare as sets of strings, and watch the cases that break naive comparisons:

- **Exposed pad.** House rule: the EP is pin N+1 — `"9"` on an 8-pin SON — in
  the capture, the symbol and the footprint alike. This is the single most
  common symbol/footprint mismatch. `easyeda2kicad` usually numbers it N+1
  already; other sources call it `EP` or `PAD`.
- **Repeated names.** Four pins named GND numbered 3, 8, 14, 21 is normal.
  Compare by number, then check each number's name. A symbol that merged them
  into one pin is missing three connections.
- **BGA and CSP.** Alphanumeric, string compare: `A1` is not `A01`. JEDEC skips
  I, O, Q, S, X and Z, so a capture with a pin `I3` is a transcription error.
- **Multi-package datasheets.** One pin table, one column per package. Resolve
  the column from the MPN via the orderable-parts table before comparing
  anything — the wrong column verifies a symbol against a different package and
  reports a clean pass.

### Electrical type, per pin

This is what makes ERC real. A VIN pin typed `passive` will never raise "power
pin not driven"; typed `power_in` it will.

| Datasheet says | KiCad type |
|---|---|
| supply, VDD, VIN, VCC, GND, VSS | `power_in` |
| regulator or charger output, VOUT | `power_out` |
| digital input, enable, reset, analog input | `input` |
| digital or analog output, push-pull, SW node | `output` |
| GPIO, SDA, bidirectional data | `bidirectional` |
| open-drain, open-collector (nINT, PG, I²C on some parts) | `open_collector` |
| FB, COMP, BOOT, CS, RT, crystal pins, EP | `passive` |
| NC, "do not connect" | `no_connect` |
| unknown after reading the datasheet | `unspecified`, and log it |

Never type a pin `passive` to silence an ERC complaint. `passive` on a supply is
the mistake converted symbols make most.

### Footprint, against the package

- **Pad numbers must equal the symbol's pin set.** A hard stop, not a note: a
  symbol pin with no pad silently loses its net at layout and DRC has nothing to
  complain about. Exclude pads with an empty number and paste-only pads.
- **Dimensions** against the capture's package section — pitch, span, pad length
  and width. Flag more than 0.1 mm and say which way: a pad narrower than the
  lead is a real defect, a slightly long toe is not.
- **Pin 1** marked on silk and on fab, on the side the datasheet's top view
  says, pads counter-clockwise from it seen from above. A mirrored footprint
  passes every count.
- **Thermal pad paste.** QFN, DFN, SON, D2PAK: the EP copper carries no paste.
  Paste comes from separate unnumbered paste-only pads in a window array at
  50–80% coverage. One full-size aperture floats the part on a bubble of solder
  and voids under it; shrinking one aperture with `solder_paste_margin_ratio` is
  the same mistake smaller. This is the most common defect in converted EasyEDA
  footprints and it does not show up until X-ray or a hot part on the bench.
- **Silk** at least 0.2 mm clear of any mask opening, or it prints on the pad.

### Look at it

```bash
kicad-cli sym export svg -s <MPN> -o /tmp/svg $EE_LIB/house.kicad_sym
kicad-cli fp  export svg --fp <PKG> -o /tmp/svg $EE_LIB/house.pretty
```

Open both. Pin 1 where the datasheet puts it, names readable and not
overlapping (D-47: check the top and bottom names against each other and
against the side names), power on top and ground at the bottom, nothing off the 1.27 mm grid
— an off-grid pin will not snap to a wire, and the schematic looks wired when it
is not.

### 3D model

KiCad 10 renders STEP natively, so point the footprint's `model` at the `.step`.
Check the file resolves, `offset` is 0 and `scale` is 1, `rotate` puts pin 1
where the footprint has it, and the body sits inside the courtyard. Some
`easyeda2kicad` versions emit WRL geometry in millimetres with scale 1, so the
model renders 2.54× too large — the extents check catches it; prefer the STEP.
No model available? Use a generic package STEP and record it as a placeholder,
so mechanical does not trust it.

## Record it

Every part gets a `LICENSES.md` entry under the right heading — house original,
derived from the KiCad libraries, or vendored third-party — saying where the
pins came from, with the datasheet revision and section. Follow the entries
already there; they are the format. Licence matters because this library is
shared: SnapEDA and Ultra Librarian terms permit use in a design but not
redistribution of the library itself.

Then say plainly what you checked and what you could not: the pin counts, the
dimensions you compared, and anything you took on trust.

## Files

```
SKILL.md
references/kicad10-sym-mod-format.md   KiCad 10 grammar, version stamps, worked examples
scripts/ipc7351.py                     IPC-7351B land patterns and paste windows
```
