#!/usr/bin/env python3
"""Pipeline B: figure detection + extraction for TI datasheets.

Detects figure captions ("Figure N-M. Title") via text extraction, then for each
caption computes the figure region (vector drawings bounding box above the caption)
and exports:
  - out/figures/<part>_p<NN>_fig<M>-<N>.png   (rendered crop, 300 dpi)
  - out/figures/manifest.json                 (machine-readable index)
  - out/figures/<part>_p<NN>_fig<M>-<N>.svg   (vector trace of the plot area)
"""
import argparse, json, os, re, sys
import pymupdf
import numpy as np

CAPTION_RE = re.compile(r"^Figure\s+(\d+)-(\d+)")

def find_captions(page):
    """Return list of (fig_no, caption_text, caption_bbox) sorted top->bottom."""
    out = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines", []):
            spans = l["spans"]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            m = CAPTION_RE.match(text)
            if m:
                out.append((f"{m.group(1)}-{m.group(2)}", text,
                            (spans[0]["bbox"][0], spans[0]["bbox"][1],
                             spans[-1]["bbox"][2], spans[-1]["bbox"][3])))
    out.sort(key=lambda c: (c[2][1], c[2][0]))
    return out

def figure_region(page, caption_bbox, pad=6):
    """Bound the vector drawings above a caption to define the figure box."""
    cap_top = caption_bbox[1]
    drawings = page.get_drawings()
    # candidate paths that lie fully above the caption, in the same column band
    col_center = (caption_bbox[0] + caption_bbox[2]) / 2
    xs, ys = [], []
    for dr in drawings:
        r = dr["rect"]
        if r.y1 > cap_top - 2:          # must be above caption
            continue
        if abs((r.x0 + r.x1) / 2 - col_center) > 75:  # same column
            continue
        xs += [r.x0, r.x1]
        ys += [r.y0, r.y1]
    if not xs:
        return None
    # sanity: figures are roughly 160pt tall; if region is much taller, it bled
    # into the row above -> clamp to ~175pt above caption top
    x0, x1 = min(xs), max(xs)
    y0 = max(min(ys), cap_top - 175)
    return (max(x0 - pad, 0), max(y0 - pad, 0), x1 + pad, cap_top - 2)

def extract_paths(page, region):
    """Serialize vector drawing paths inside the region to JSON-safe primitives.
    Segments are clipped to the region rect so page-spanning lines from
    neighboring figures don't leak in."""
    r = pymupdf.Rect(*region)

    def clip_seg(x0, y0, x1, y1):
        x0 = max(x0, r.x0); x1 = min(x1, r.x1)
        y0 = max(y0, r.y0); y1 = min(y1, r.y1)
        return x0, y0, x1, y1

    paths = []
    for dr in page.get_drawings():
        rect = dr["rect"]
        if not (rect.x0 < r.x1 and rect.x1 > r.x0 and rect.y0 < r.y1 and rect.y1 > r.y0):
            continue
        stroke = dr.get("color")
        fill = dr.get("fill")
        width = dr.get("width") or 0
        items = []
        for item in dr["items"]:
            op = item[0]
            if op == "l":
                p1, p2 = item[1], item[2]
                x0, y0, x1, y1 = clip_seg(p1.x, p1.y, p2.x, p2.y)
                if x0 == x1 and y0 == y1:
                    continue
                items.append({"op": "l",
                              "x": round(float(x0), 3), "y": round(float(y0), 3),
                              "x2": round(float(x1), 3), "y2": round(float(y1), 3)})
            elif op == "c":
                # sample bezier then clip polyline
                p1, p2, p3 = item[1], item[2], item[3]
                prev = None
                for t in np.linspace(0, 1, 12):
                    x = (1-t)**3*p1.x + 3*(1-t)**2*t*p2.x + 3*(1-t)*t**2*p3.x + t**3*p3.x
                    y = (1-t)**3*p1.y + 3*(1-t)**2*t*p2.y + 3*(1-t)*t**2*p3.y + t**3*p3.y
                    if prev:
                        x0, y0, x1, y1 = clip_seg(prev[0], prev[1], x, y)
                        if x0 != x1 or y0 != y1:
                            items.append({"op": "l", "x": round(float(x0), 3), "y": round(float(y0), 3),
                                          "x2": round(float(x1), 3), "y2": round(float(y1), 3)})
                    prev = (x, y)
            elif op == "re":
                p1, p2 = item[1], item[2]
                x0, y0, x1, y1 = clip_seg(p1.x, p1.y, p2.x, p2.y)
                if x0 != x1 or y0 != y1:
                    items.append({"op": "re",
                                  "x0": round(float(x0), 3), "y0": round(float(y0), 3),
                                  "x1": round(float(x1), 3), "y1": round(float(y1), 3)})
        if items:
            paths.append({"color": stroke, "fill": fill, "width": width, "items": items})
    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--pages", default="19-20", help="1-based page range, e.g. 19-20 or 18")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="out/figures")
    ap.add_argument("--vectors", action="store_true", help="also export SVG vector traces")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    part = os.path.splitext(os.path.basename(args.pdf))[0]
    os.makedirs(args.out, exist_ok=True)
    if "-" in args.pages:
        lo, hi = (int(x) for x in args.pages.split("-"))
    else:
        lo = hi = int(args.pages)
    manifest = {"part": part, "pages": [], "dpi": args.dpi}

    for pno in range(lo - 1, min(hi, doc.page_count)):
        page = doc[pno]
        caps = find_captions(page)
        if not caps:
            continue
        entries = []
        for fig_no, text, cap_bbox in caps:
            region = figure_region(page, cap_bbox)
            if not region:
                continue
            fname = f"{part}_p{pno+1:02d}_fig{fig_no}.png"
            mat = pymupdf.Matrix(args.dpi / 72, args.dpi / 72)
            pix = page.get_pixmap(matrix=mat, clip=pymupdf.Rect(*region))
            pix.save(os.path.join(args.out, fname))
            entries.append({
                "figure": fig_no, "caption": text,
                "page": pno + 1,
                "region_pt": [round(v, 1) for v in region],
                "region_px": [pix.width, pix.height],
                "cap_x0": round(cap_bbox[0], 1), "cap_x1": round(cap_bbox[2], 1),
                "png": fname,
            })
            if args.vectors:
                vec_name = f"{part}_p{pno+1:02d}_fig{fig_no}.paths.json"
                paths = extract_paths(page, region)
                with open(os.path.join(args.out, vec_name), "w") as f:
                    json.dump(paths, f, indent=1)
                entries[-1]["paths_json"] = vec_name
        manifest["pages"].append({"page": pno + 1, "figures": entries})
        print(f"page {pno+1}: extracted {len(entries)} figures")

    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("manifest ->", os.path.join(args.out, "manifest.json"))

if __name__ == "__main__":
    main()
