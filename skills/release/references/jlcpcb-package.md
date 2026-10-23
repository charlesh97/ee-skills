# JLCPCB package — formats and the exact kicad-cli calls

Every flag below was checked against docs.kicad.org/10.0/en/cli (gerbers,
drill, pos, ipcd356, ipc2581, pcb pdf, drc, sch bom, sch erc) or the KiCad
10.0 source (`kicad/cli/command_*.cpp` for step, sch pdf, netlist, version).
If a call fails, run it with `--help` and fix the flag; don't guess a new one.
Variables: `$SCH` root schematic, `$PCB` board, `$OUT=releases/<rev>`,
`$V` the variant name from `project.yaml` (omit `--variant` if none).

## 1. Gerbers

JLC reads RS-274X. It accepts X2 attribute headers but its guide asks for
them off, and X2 adds nothing JLC uses — so plot plain RS-274X with no netlist
attributes. Protel extensions (`.GTL`, `.GBL`, …) are the default and are what
JLC's importer keys layer detection on; do not pass `--no-protel-ext`.
Precision 6 (4.6 format, default) is fine.

```
kicad-cli pcb export gerbers --variant $V --no-x2 --no-netlist \
  --subtract-soldermask --check-zones \
  --layers F.Cu,B.Cu,In1.Cu,In2.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Fab,B.Fab \
  -o $OUT/gerbers/ $PCB
```
Drop `In*.Cu` for a two-layer board, and add `In3.Cu,In4.Cu`, … for every inner layer of a 6+ layer board; layer names must exist or the export
errors. Edge.Cuts is its own file — JLC does not want it merged into every
layer, so no `--common-layers`. `--subtract-soldermask` keeps silk off pads.
Origin: absolute (default). Whatever origin you use here you must use for pos
too, or the CPL lands off-board. Absolute for both is the simplest way to
keep them consistent.

## 2. Drill

JLC's KiCad guide: Excellon, absolute origin, millimetres, decimal zeros,
oval holes as route commands, PTH and NPTH in one file. Those are kicad-cli's
defaults; state them anyway so the intent is on the command line.

```
kicad-cli pcb export drill --format excellon --drill-origin absolute \
  --excellon-units mm --excellon-zeros-format decimal --excellon-oval-format route \
  --generate-map --map-format gerberx2 -o $OUT/gerbers/ $PCB
```
Do not pass `--excellon-separate-th`; a separate NPTH file is accepted by JLC
but the merged file is what their guide expects. Zero-suppression variants
(`suppressleading`, `suppresstrailing`, `keep`) exist but decimal avoids the
whole class of leading/trailing ambiguity.

## 3. IPC-D-356 netlist (defence against a bad plot)

```
kicad-cli pcb export ipcd356 -o $OUT/$NAME.d356 $PCB
```
A fab that gets a D-356 can netlist-test the bare board against the design;
a shorted or open plot layer is caught before assembly. No `--variant`.

## 4. Position file and CPL

```
kicad-cli pcb export pos --variant $V --format csv --units mm --side both \
  --exclude-dnp -o $OUT/$NAME-pos.csv $PCB
python3 <skill>/scripts/emit_cpl.py $OUT/$NAME-pos.csv $OUT/$NAME-jlc-cpl.csv
```
KiCad's CSV header is `Ref,Val,Package,PosX,PosY,Rot,Side`; Y is already
written bottom-to-top (sign flipped from KiCad's internal frame), which is what
JLC's preview expects. Footprints with the "exclude from position files"
attribute are skipped by KiCad; `emit_cpl.py` also drops `MH*`, `FID*`, `TP*`
by refdes as a second line — the house rule is that they never reach the
assembler. `--exclude-fp-th` is deliberately not used: JLC places many THT
parts now, and dropping a placed THT part from the CPL is a silent omission.
Remove THT lines the assembler won't handle by hand and say which.

**JLC CPL columns**, exactly: `Designator, Mid X, Mid Y, Layer, Rotation`.
Layer is `Top` / `Bottom`; positions in mm, plain numbers.

**JLC BOM columns**, exactly: `Comment, Designator, Footprint, LCSC Part #`.

### The rotation problem

KiCad's footprint zero orientation follows the KiCad library convention
(pin 1 top-left for ICs, cathode left for diodes …). JLC's zero follows their
part library, which is close to EIA-481 tape orientation and differs per
package family — so a footprint that reads 0° in KiCad may need 90°, 180° or
270° in the CPL, and the offset is a property of the footprint, not the part.
The only authoritative check is JLC's placement preview after upload, which
draws each part on the board image: pin 1 dots and polarity marks must match
the silkscreen.

`emit_cpl.py` carries a starter table (SOT-23 family 180, SOD-123/323 180,
SOIC/SOP/TSSOP/MSOP/QFN/DFN/LQFP/TQFP 270, convex R-arrays 90, WS2812B 180,
USB-C receptacles 180). These are the offsets the community tools converge on
for KiCad's stock library footprints, and **none has been verified against a
real order** — the script prints `VERIFY` for every match. Two further things
to check on the first order: (a) whether JLC mirrors rotation on the bottom
side (some tools apply `-rot` or `180-rot` for bottom parts); the script
applies the same offset to both sides until a real order says otherwise;
(b) house-library footprints, which the starters do not cover. When an offset
is confirmed, write it to `<skill>/references/jlc_rotations.csv` as
`<regex>,<degrees>` and pass `--rotations`; rows there take precedence and
are treated as verified. The table grows one order at a time; that is fine.

## 5. STEP

```
kicad-cli pcb export step --variant $V --subst-models --no-dnp --no-unspecified \
  --include-tracks --include-zones --force -o $OUT/$NAME.step $PCB
```
`--subst-models` swaps STEP/IGES for VRML where a same-named file exists,
which is what makes the mechanical model useful. `--no-unspecified` drops
footprints with no SMD/THT attribute (test points, holes) so the mechanical
team does not get phantom bodies.

## 6. PDFs

```
kicad-cli pcb export pdf --variant $V --mode-multipage --include-border-title \
  --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Fab,B.Fab,Edge.Cuts \
  --common-layers Edge.Cuts --crossout-DNP-footprints-on-fab-layers \
  -o $OUT/$NAME-board.pdf $PCB
kicad-cli sch export pdf --variant $V --exclude-pdf-property-popups \
  -o $OUT/$NAME-schematic.pdf $SCH
```
One multipage board PDF is the assembly drawing: fab layers with DNP parts
crossed out, edge on every page. `sch export pdf` prints all pages unless
`--pages` is given. Timestamps make PDFs non-reproducible; record their hash
but do not expect it to match a rebuild.

## 7. BOMs

Field names are the contract with `schematic-capture`; the symbol fields
below are what it writes. If a field is named differently in the schematic,
change `--fields`, not the label.

Engineering BOM — everything the house rule requires, one line per refdes:
```
kicad-cli sch export bom --variant $V --exclude-dnp \
  --fields "Reference,Value,Footprint,Manufacturer,MPN,LCSC,Package,Tolerance,Voltage,Dielectric,Temp,Substitutable,Datasheet,${QUANTITY},${DNP}" \
  --labels "Refs,Value,Footprint,Manufacturer,MPN,LCSC,Package,Tol,V,Dielectric,Temp,Subst,Datasheet,Qty,DNP" \
  --group-by MPN --sort-field Reference \
  -o $OUT/$NAME-bom-eng.csv $SCH
```
`${QUANTITY}` and `${DNP}` are KiCad's built-in pseudo-fields. `--group-by`
collapses identical MPNs into one line with a refdes list; drop it for a
per-refdes listing when diffing against a previous rev. Symbols marked
"exclude from BOM" (MH, FID, TP) stay out unless `--include-excluded-from-bom`
is passed — do not pass it.

JLC BOM — four columns, exact labels:
```
kicad-cli sch export bom --variant $V --exclude-dnp \
  --fields "Value,Reference,Footprint,LCSC" \
  --labels "Comment,Designator,Footprint,LCSC Part #" \
  --group-by LCSC --ref-delimiter "," --ref-range-delimiter "" \
  -o $OUT/$NAME-jlc-bom.csv $SCH
```
`--ref-range-delimiter ""` stops KiCad writing `R1-R4`; JLC wants every
refdes listed. JLC ignores Comment and Footprint for matching — the LCSC
number is the only column that binds the part — so a blank LCSC cell is a
release stop, not a warning.

Stuffing options: KiCad 10 design variants set DNP and field overrides per
variant; `--variant` is accepted by bom, gerbers, pos, step, pcb pdf, sch pdf,
ipc2581 and netlist. Not by drill, ipcd356, erc, drc. Build one `$OUT` per
variant if more than one is being ordered.

## 8. Netlist, checkers, versions

```
kicad-cli sch export netlist --format kicadsexpr -o $OUT/$NAME.net $SCH
kicad-cli sch erc --format json --severity-all -o $OUT/erc.json $SCH
kicad-cli pcb drc --format json --severity-all --schematic-parity --refill-zones -o $OUT/drc.json $PCB
kicad-cli version --format about
```
`--exit-code-violations` makes erc/drc return 5 on violations if you want a
shell check; the JSON is what you read.

## 9. IPC-2581 (optional, only if the fab asks)

```
kicad-cli pcb export ipc2581 --variant $V --units mm --version C \
  --bom-col-mfg Manufacturer --bom-col-mfg-pn MPN --bom-col-dist-pn LCSC \
  -o $OUT/$NAME.xml $PCB
```
JLC takes gerbers; produce this only on request.

## 10. Normalised hashing for the manifest

Gerber (`G04 #@! TF.CreationDate`, `G04 Created by KiCad … date`), Excellon
(`; DATE`, `; #@! TF.CreationDate`) and STEP (`FILE_NAME(...)` timestamp)
headers carry the build time. Hash with those lines removed:

```python
import hashlib, re, sys
DROP = re.compile(rb"^(G04 .*(Created|Creation|date).*|;.*(DATE|Creation).*|FILE_NAME.*)$", re.M | re.I)
for p in sys.argv[1:]:
    b = DROP.sub(b"", open(p, "rb").read())
    print(hashlib.sha256(b).hexdigest(), p)
```
Record both hashes in `manifest.yaml` (`sha256`, `sha256_normalized`).
Reproducibility is judged on the normalised one.
