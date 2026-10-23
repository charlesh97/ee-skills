# Vendor notes

What the capture does and does not recover, per vendor, measured rather than
assumed. Add a row when you capture a part from a vendor not listed.

## Measured

| Part type | Vendor | Pages | Headings | Numbered | Tables | Pictures → figures | Formulas | Runtime |
|---|---|---|---|---|---|---|---|---|
| LDO | TI | 51 | 100 | 56 | 25 (3999 cells) | 121 → 44 | 9 | 51s |
| I²C level translator | TI | 38 | 91 | 51 | 19 (767 cells) | 86 → 35 | 8 | 17s |
| optical sensor | OSRAM | 22 | 37 | 0 | 8 (242 cells) | 61 → 26 | 0 | 8s |

Provenance was 100% on both — every text, table and picture block carried a page
and a bbox. That is the number to check first on a new vendor; if it drops below
100%, the blocks without `prov` cannot be cited and should not be used.

## What varies

**Heading numbering.** TI numbers its headings (`7.1 Absolute Maximum Ratings`),
so `capture.py` nests them into a real tree. OSRAM, ams and Espressif largely do
not. On those, `headings_numbered` is 0, the tree is flat, and `capture.py` says
so. Locate sections by heading text and page; do not infer nesting.

**Table density.** TI datasheets put the specifications in a handful of large
tables with clean `PARAMETER / TEST CONDITIONS / MIN / TYP / MAX / UNIT` headers.
OSRAM uses `Parameter / Symbol / Values` and splits across more, smaller tables.
Both extract correctly; find them by header, not by index.

**Front matter as tables.** The table of contents and the revision history come
through as tables — often tables 1 and 2. They are real page
content, so they are kept rather than dropped. Skip them by their headers; do not
assume table 0 is the pin table.

**Text inside figures.** Docling extracts the text drawn within a figure — axis
labels, legend entries, tick values — and parents it to that picture rather than
to the body. On one TI part measured that was 1534 of 2077 text blocks. It means a chart's
axis calibration and legend are available as cited text without OCR and without
digitizing. Find them by filtering `texts` on
`parent.$ref == "#/pictures/<n>"`. A figure with no child text is almost always
ornament.

**Ornament ratio.** Around 60% of pictures are logos and page furniture on every
vendor measured. `capture.ornament` lists them; see the SKILL.md rule. Figure
count in the table above is after filtering.

**Graph-heavy parts.** The optical sensor above is 22 pages and 61 pictures with comparatively
little prose, because the characteristics are curves rather than tables. On parts
like this the capture alone will not answer a numeric question — the number is in
a figure, and `figures.py` + `digitize.py` are how you get it.

## Known limits

**Dash-coded curves.** Older TI plots encode curves as dashes,
which `digitize.py` chains by centroid proximity. Same-colour interleaved dashed
curves fragment. Solid vector curves digitize exactly. `verify.py`'s overlay is
how you tell the two apart — always look at it.

**Polar and non-cartesian plots.** `digitize.py` calibrates from cartesian tick
labels, so it cannot digitize a polar plot — a directional-characteristics
figure is one. Read the crop instead.

**Digitize or just read the crop.** Digitizing earns its cost when you need the
curve at many points, such as interpolating efficiency at each mode's actual
load. When you need one or two values off a figure, the 300 DPI crop is legible
enough to read directly — cite the page and say you read it off the figure.

**Scanned datasheets.** `--ocr` works but every confidence drops. Say in the
finding that the source was scanned.

**Multi-column reading order** is handled by docling's layout model rather than
by geometry heuristics, which is why non-TI layouts no longer collapse. This was
the specific failure of the previous PyMuPDF-based capture: on OSRAM and
Espressif parts it returned zero headings and left the section tree empty.
