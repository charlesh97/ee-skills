#!/usr/bin/env python3
"""Whole-datasheet capture: PDF -> capture.json (DoclingDocument + provenance header).

The output IS the DoclingDocument export, not a mapping of it. Every word, table
cell, figure and formula is already in there with a page and a bbox; a mapped
schema would only be a lossy subset. We add a header saying what was captured
and how, and we nest the flat heading list where the vendor numbers its headings.

Usage:
    capture.py <input.pdf> --out datasheets/<MPN> [--mpn MPN] [--rev REV]
               [--url URL] [--ocr] [--crops]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time

# Leading section number: "7.1", "8.3.2", "10 " -> nesting depth from the dots.
NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\s+\S")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(pdf, do_ocr):
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
    except ImportError:
        sys.exit(
            "docling is not importable. Install it into a venv and run this script "
            "with that venv's python:\n"
            "  python3 -m venv .venv && .venv/bin/pip install docling pymupdf numpy matplotlib pillow"
        )

    opts = PdfPipelineOptions()
    # Born-digital datasheets have an authoritative text layer. OCR adds noise and
    # ~2.4x runtime for no gain; flip it on only for scans.
    opts.do_ocr = do_ocr
    opts.do_table_structure = True
    opts.table_structure_options.do_cell_matching = True
    # Deterministic-first: no generated descriptions or classifications. Figures and
    # equations are cropped and read by the model, which cites the page it read.
    opts.do_picture_classification = False
    opts.do_picture_description = False
    opts.do_formula_enrichment = False

    conv = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    t0 = time.time()
    doc = conv.convert(pdf).document
    return doc, time.time() - t0


def nest_headings(d):
    """Docling returns section headers flat. Where the vendor numbers them, the
    numbering is the tree; where it does not, flat is the honest answer."""
    numbered = 0
    for t in d.get("texts", []):
        if t.get("label") != "section_header":
            continue
        m = NUMBERED.match((t.get("text") or "").strip())
        if m:
            t["level"] = m.group(1).count(".") + 1
            t["section_number"] = m.group(1)
            numbered += 1
        else:
            t["level"] = t.get("level", 1)
    return numbered


def classify_pictures(d):
    """Most 'pictures' in a datasheet are the vendor logo, page rules and package
    marks, repeated on every page. Real figures are large; ornament is tiny, and
    the gap between them is orders of magnitude, not a judgement call.

    Measured across several vendors: real figures start at 2.6% of the page area, the
    largest ornament is 0.76%, and nothing falls in between.

    Deliberately size-only. Filtering by 'this picture repeats on several pages'
    also looks reasonable and is wrong: TI repeats the package mechanical drawing
    across its package variants, so that rule culls the lead span and pitch that
    a footprint is verified against."""
    pages = d.get("pages") or {}
    first = list(pages.values())[0] if pages else {}
    size = first.get("size") or {}
    page_area = (size.get("width") or 612) * (size.get("height") or 792)
    ornament = []
    for i, p in enumerate(d.get("pictures", [])):
        prov = (p.get("prov") or [None])[0]
        if not prov:
            continue
        bb = prov["bbox"]
        area = abs(bb["r"] - bb["l"]) * abs(bb["t"] - bb["b"])
        if area < 0.01 * page_area:
            ornament.append(p.get("self_ref") or "#/pictures/{}".format(i))
    return ornament


def write_crops(doc_dict, pdf, outdir, skip=()):
    """Render every formula and picture block to a PNG from its bbox, so the model
    can read what the text layer cannot. Equation glyphs are symbol-encoded in the
    PDF text layer -- the crop is the only machine-readable route to them."""
    try:
        import pymupdf
    except ImportError:
        print("  ! pymupdf missing, skipping crops", file=sys.stderr)
        return {}
    os.makedirs(os.path.join(outdir, "crops"), exist_ok=True)
    pdf_doc = pymupdf.open(pdf)
    made = {}
    for kind in ("texts", "pictures"):
        for i, block in enumerate(doc_dict.get(kind, [])):
            if kind == "texts" and block.get("label") != "formula":
                continue
            if block.get("self_ref") in skip:
                continue
            prov = (block.get("prov") or [None])[0]
            if not prov:
                continue
            page_no = prov["page_no"]
            bb = prov["bbox"]
            page = pdf_doc[page_no - 1]
            ph = page.rect.height
            # docling bboxes are BOTTOMLEFT (t > b); pymupdf is TOPLEFT.
            if bb.get("coord_origin") == "BOTTOMLEFT":
                rect = pymupdf.Rect(bb["l"], ph - bb["t"], bb["r"], ph - bb["b"])
            else:
                rect = pymupdf.Rect(bb["l"], bb["t"], bb["r"], bb["b"])
            rect = rect & page.rect
            if rect.is_empty or rect.width < 4 or rect.height < 4:
                continue
            label = "formula" if kind == "texts" else "picture"
            name = "{}_p{:02d}_{}{:03d}.png".format(label, page_no, label[:3], i)
            page.get_pixmap(clip=rect, dpi=300).save(os.path.join(outdir, "crops", name))
            made[block.get("self_ref", "{}/{}".format(kind, i))] = "crops/" + name
    pdf_doc.close()
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True, help="output directory, e.g. datasheets/<MPN>")
    ap.add_argument("--mpn", help="defaults to the PDF basename")
    ap.add_argument("--rev", help="datasheet revision, read off the PDF footer")
    ap.add_argument("--url", help="where the PDF came from")
    ap.add_argument("--ocr", action="store_true", help="scanned datasheets only")
    ap.add_argument("--crops", action="store_true",
                    help="render formula and picture crops for the model to read")
    args = ap.parse_args()

    mpn = args.mpn or os.path.basename(args.pdf).rsplit(".", 1)[0]
    os.makedirs(args.out, exist_ok=True)

    doc, secs = convert(args.pdf, args.ocr)
    d = doc.export_to_dict()
    numbered = nest_headings(d)

    ornament = classify_pictures(d)
    crops = write_crops(d, args.pdf, args.out, skip=set(ornament)) if args.crops else {}

    try:
        from importlib.metadata import version as _pkg_version
        docling_version = _pkg_version("docling")
    except Exception:
        docling_version = "unknown"

    d["capture"] = {
        "mpn": mpn,
        "datasheet_rev": args.rev,
        "source_url": args.url,
        "source_pdf": os.path.basename(args.pdf),
        "pdf_sha256": sha256(args.pdf),
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "engine": {
            "docling": docling_version,
            "schema": d.get("version"),
            "do_ocr": args.ocr,
        },
        "runtime_s": round(secs, 1),
        "headings_numbered": numbered,
        "ornament": ornament,
        "crops": crops,
    }

    cap = os.path.join(args.out, "capture.json")
    with open(cap, "w") as f:
        json.dump(d, f, indent=1)
    md = os.path.join(args.out, "capture.md")
    with open(md, "w") as f:
        f.write(doc.export_to_markdown())

    n_head = sum(1 for t in d.get("texts", []) if t.get("label") == "section_header")
    n_form = sum(1 for t in d.get("texts", []) if t.get("label") == "formula")
    prov = sum(1 for k in ("texts", "tables", "pictures")
               for it in d.get(k, []) if it.get("prov"))
    total = sum(len(d.get(k, [])) for k in ("texts", "tables", "pictures"))
    cells = sum(len((t.get("data") or {}).get("table_cells") or []) for t in d.get("tables", []))

    print("{} -> {}".format(mpn, cap))
    print("  pages {}   runtime {}s".format(len(d.get("pages", {})), round(secs, 1)))
    n_pic = len(d.get("pictures", []))
    print("  texts {}   tables {} ({} cells)   pictures {} ({} figures, {} ornament)"
          "   formulas {}".format(
              len(d.get("texts", [])), len(d.get("tables", [])), cells,
              n_pic, n_pic - len(ornament), len(ornament), n_form))
    print("  headings {} ({} numbered -> nested)".format(n_head, numbered))
    print("  provenance {}/{} blocks carry page+bbox".format(prov, total))
    if crops:
        print("  crops {}".format(len(crops)))
    if not numbered and n_head:
        print("  ! no numbered headings: the section tree is flat. Locate sections by "
              "heading text and page, not by nesting.")
    if prov < total:
        print("  ! {} blocks have no provenance; do not cite them.".format(total - prov))


if __name__ == "__main__":
    main()
