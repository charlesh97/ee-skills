---
name: datasheet-extraction
description: >
  Turn a datasheet PDF into a cited, machine-readable capture — every word,
  table cell, figure and equation with the page and bounding box it came from,
  plus digitized efficiency and characteristic curves. Load it for "extract this
  datasheet", "pull the datasheet", "capture the datasheet", "what are the pins",
  "what's the abs max", "read the electrical characteristics", "digitize this
  efficiency curve", "what does the application circuit use", "get the thermal
  numbers", or any time a design question turns on what a part actually does and
  there is a PDF to answer it from. Read the capture, not the PDF, and not your
  memory of the part.
---

# Datasheet Extraction

One job: a PDF goes in, a capture comes out that every other skill and every
later question reads instead of the PDF. It does not choose parts, price them,
check stock, or write a part record.

The reason it exists is provenance. A remembered pin number and an extracted one
look identical once they are in a YAML file, and only one of them is true. Every
value in the capture carries the page and bounding box it was read from, so
"where did this come from" always has an answer.

## Contract

```
Reads:   a datasheet PDF, and the revision and URL you were given for it
Writes:  datasheets/<MPN>/capture.json   the whole document, cited
         datasheets/<MPN>/capture.md     the same thing, readable
         datasheets/<MPN>/crops/         formula and figure PNGs (--crops)
         datasheets/<MPN>/figures/       figure regions + vector geometry
         datasheets/<MPN>/curves/        digitized curve CSVs
Stops if: no PDF can be obtained. A capture written from memory is worse than
          no capture, because every skill downstream would trust it.
```

## Setup, once per machine

```bash
python3 -m venv .venv && .venv/bin/pip install docling pymupdf numpy matplotlib pillow
```

Run every script below with that venv's python. `capture.py` says so and exits
if docling is missing rather than half-working.

## Steps

### 1. Capture

```bash
S=<this skill>/scripts
$VENV/python $S/capture.py <part>.pdf --out datasheets/<MPN> \
    --mpn <MPN> --rev <rev off the PDF footer> --url <where you got it> --crops
```

Read the revision off the first page or the footer before you run it — TI prints
`SLVSxxxB – MONTH YEAR`, ST prints `DSnnnnn Rev n`. A capture whose revision you
cannot name cannot be checked against the datasheet the design was done from.

`capture.py` prints what it found and warns about what it could not do. Read
those warnings; they decide how much the capture can be trusted.

**Cache check.** If `datasheets/<MPN>/capture.json` already exists and its
`capture.pdf_sha256` matches the PDF, it is current. Say so and stop — a second
extraction only creates a chance to disagree with a capture already in use.

### 2. Curves, only where a number depends on one

Efficiency against load is the one figure a power budget actually needs, and a
headline "92% efficient" is nowhere near true at sleep current. Digitize the
curves that carry a number you will use, not all of them.

```bash
$VENV/python $S/figures.py  <part>.pdf --pages <fig pages> --out datasheets/<MPN>/figures --vectors
$VENV/python $S/digitize.py <part>.pdf <fig-id> --manifest datasheets/<MPN>/figures/manifest.json \
    --out datasheets/<MPN>/curves
$VENV/python $S/verify.py --figure <fig-id> --manifest datasheets/<MPN>/figures/manifest.json \
    --figures-dir datasheets/<MPN>/figures --digitized-dir datasheets/<MPN>/curves \
    --out datasheets/<MPN>/curves      # overlay: source crop vs replot
```

**Always look at the overlay.** Digitization is exact for vector plots and
fragments on older dash-coded ones; the overlay is how you tell which happened.
An unverified curve is an assumption with a CSV around it.

### 3. Read the capture and answer the question

`capture.json` is a DoclingDocument. `texts` carries every block with a `label`
(`section_header`, `text`, `caption`, `formula`, `list_item`, `page_footer`) and
a `prov` giving page and bbox. `tables` carries real tables whose cells each
carry a bbox and row/column spans. `pictures` carries figures with their captions
already associated. `body` is the reading-order tree.

Find the pin table, absolute maximums, recommended operating conditions, thermal
information and electrical characteristics in `tables` by their headers. Cite the
page on every value you carry out.

## Rules

**The capture is the document, not a summary of it.** `capture.json` is the
DoclingDocument export with a provenance header added — nothing is mapped,
filtered or dropped. Do not write a parallel "extracted values" file and then
read that instead; the second copy is where the drift starts. If you need a
subset for a specific job, derive it at the point of use and cite back.

**Equations are not in the text layer.** Equation glyphs are symbol-encoded, so
docling locates every formula correctly and extracts its text as an empty
string — on one part measured, all eight come back `''`. Without `--crops` the equations
are not merely garbled, they are absent, and a formula written from an empty
block is written from memory. `--crops` renders every `formula` block to a PNG at
300 DPI. Read the crop. The same holds for anything drawn rather than typeset:
application circuits, timing diagrams, package drawings.

**You are the semantic stage, and you still cite.** Docling extracts; it does not
interpret. Turning a crop into an equation, or a design procedure into steps, is
your job — and every line of it names the page it came from. Interpretation
without a citation is indistinguishable from recall, which is the failure this
skill exists to prevent.

**Most pictures are not figures.** Roughly 60% of what docling labels a picture
is the vendor logo, a page rule or a package mark, repeated on every page —
77 of 121 on one part measured. `capture.py` lists them in `capture.ornament` by the
one rule that separates them cleanly: anything under 1% of the page area. On the
parts measured, real figures start at 2.6% of the page and the largest ornament
is 0.76%, with nothing in between. Crops are not rendered for ornament.

Do not filter figures by "this one repeats on several pages" instead. It looks
reasonable and it deletes the package mechanical drawings, because TI repeats
that drawing across package variants — and its lead span, pitch and lead width
are what a footprint gets verified against.

**A flat section tree is a real answer.** Docling returns headings flat;
`capture.py` nests them where the vendor numbers them. TI numbers its headings,
so TI parts get a tree. ams, OSRAM and Espressif largely do not, so those come
back flat and `capture.py` says so. When it does, locate sections by heading text
and page number and stop expecting nesting — do not infer a hierarchy that the
document does not have.

**Do not OCR a born-digital PDF.** The text layer is authoritative; OCR adds
noise and roughly 2.4× the runtime for nothing. `--ocr` is for scans, and a
scanned datasheet means every confidence in the capture drops.

**Two reads of the same table beat one.** Where a number matters enough to
design against — a pin number, an absolute maximum, a package dimension — check
the `tables` cell against the rendered `capture.md` or the crop for that page.
Agreement is not proof; disagreement is a signal worth chasing to the PDF.

**Say what you could not get.** A missing thermal section, a mangled table, a
fragmented curve: name it. A gap that is visible gets filled, and a gap that was
quietly papered over gets designed against.

## Files

```
SKILL.md
references/vendor-notes.md   per-vendor quirks and what to spot-check
scripts/capture.py           PDF -> capture.json + capture.md (+ crops)
scripts/figures.py           figure regions, crops and vector geometry
scripts/digitize.py          curve digitizer: axis calibration + legend association
scripts/verify.py            overlay of source crop against the replotted curve
```
