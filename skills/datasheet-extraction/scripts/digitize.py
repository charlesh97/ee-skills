#!/usr/bin/env python3
"""Pipeline D: vector-path curve digitizer for TI-style datasheet plots.

Takes a figure's paths.json + the PDF page (for tick-label text), calibrates the
plot axes from tick labels, then maps colored polylines (curves) to physical
(x, y) data points. Exports:
  - out/digitized/<fig>.csv            (per-curve data, long format)
  - out/digitized/<fig>.json           (calibration + curves + metadata)

Axis calibration:
  - Y: linear, from tick label text (baseline y is the tick position)
  - X: log10 for most TI plots (efficiency vs load), from tick values
"""
import argparse, json, math, os
import pymupdf
import numpy as np

def tick_texts(page, region, col_band=None):
    """Collect numeric tick labels inside the plot area (value, cx, cy).
    col_band=(x0, x1) optionally restricts to a caption column band to keep
    neighboring figures' ticks out of the region."""
    r = pymupdf.Rect(*region)
    d = page.get_text("dict")
    out = []
    for b in d["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                if x0 < r.x0 or x1 > r.x1 or y0 < r.y0 or y1 > r.y1:
                    continue
                if col_band and (x1 < col_band[0] - 25 or x0 > col_band[1] + 25):
                    continue
                t = s["text"].strip()
                if not t:
                    continue
                try:
                    v = float(t)
                except ValueError:
                    continue
                out.append({"value": v, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2,
                            "y0": y0, "y1": y1, "x0": x0, "x1": x1})
    return out

def find_gray_box(paths, region):
    """Plot box from the gray grid rectangle (TI figures draw grid in ~0.26 gray).
    Returns None if no gray grid found."""
    r = pymupdf.Rect(*region)
    h_lines, v_lines = [], []
    for p in paths:
        c = p["color"]
        if not c or len(c) != 3 or max(c) - min(c) > 0.05 or max(c) < 0.1:
            continue  # require neutral gray, not black
        for it in p["items"]:
            if it["op"] != "l":
                continue
            x0, y0, x1, y1 = it["x"], it["y"], it["x2"], it["y2"]
            if x0 < r.x0 or x1 > r.x1 or y0 < r.y0 or y1 > r.y1:
                continue  # must be fully inside region (avoid neighbor bleed)
            dx = abs(x1 - x0); dy = abs(y1 - y0)
            if dx > 60 and dy < 1.5:
                h_lines.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif dy > 60 and dx < 1.5:
                v_lines.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    if not h_lines or not v_lines:
        return None
    # grid box = extremes of the longest fully-inside lines
    h = max(h_lines, key=lambda l: l[2] - l[1])
    v = max(v_lines, key=lambda l: l[2] - l[1])
    return {"x0": v[0], "x1": h[2], "y0": v[1], "y1": h[0]}

def find_axis_frame(paths, region, ticks=None):
    """Plot box anchored to tick labels: y-axis = grid line nearest right of the
    y-tick labels, x-axis = grid line nearest below the x-tick labels.
    Falls back to the gray-grid rectangle, then generic long thin lines."""
    r = pymupdf.Rect(*region)
    if ticks:
        xt = [t for t in ticks if t["y0"] > r.y1 - 40]  # x tick labels near bottom
        x_row = min((t["y0"] for t in xt), default=None)
        # y tick labels: above the x-axis row, in the left band of the plot
        yt = [t for t in ticks
              if (x_row is None or t["y0"] < x_row - 5) and t["y0"] > r.y0 - 3
              and t["y0"] < r.y1 - 3 and t["cx"] < r.x0 + 200]
        # collect grid lines (neutral gray, fully inside region)
        h_lines, v_lines = [], []
        for p in paths:
            c = p["color"]
            if not c or len(c) != 3 or max(c) - min(c) > 0.05 or max(c) < 0.1:
                continue
            for it in p["items"]:
                if it["op"] != "l":
                    continue
                x0, y0, x1, y1 = it["x"], it["y"], it["x2"], it["y2"]
                if x0 < r.x0 or x1 > r.x1 or y0 < r.y0 or y1 > r.y1:
                    continue
                dx = abs(x1 - x0); dy = abs(y1 - y0)
                if dx > 60 and dy < 1.5:
                    h_lines.append((y0, min(x0, x1), max(x0, x1)))
                elif dy > 60 and dx < 1.5:
                    v_lines.append((x0, min(y0, y1), max(y0, y1)))
        y_axis = None
        if yt:
            band_x = max(t["cx"] for t in yt) + 3
            if v_lines:
                y_axis = min(v_lines, key=lambda l: abs(l[0] - band_x))
        x_axis = None
        if xt:
            band_y = min(t["y0"] for t in xt) - 3
            if h_lines:
                x_axis = min(h_lines, key=lambda l: abs(l[0] - band_y))
        if y_axis and x_axis:
            # extend y-axis line to where it crosses the x-axis
            return {"x0": y_axis[0], "x1": x_axis[2], "y0": y_axis[1], "y1": x_axis[0]}

    box = find_gray_box(paths, region)
    if box:
        return box
    if ticks:
        xt = [t for t in ticks if t["y0"] > r.y1 - 40]  # x tick labels near bottom
        yt = [t for t in ticks if t["cx"] < r.x0 + 60]  # y tick labels near left
        h_lines, v_lines = [], []
        for p in paths:
            for it in p["items"]:
                if it["op"] != "l":
                    continue
                x0, y0, x1, y1 = it["x"], it["y"], it["x2"], it["y2"]
                dx = abs(x1 - x0); dy = abs(y1 - y0)
                if dx > 60 and dy < 1.5:
                    h_lines.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
                elif dy > 60 and dx < 1.5:
                    v_lines.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))
        # x axis = horizontal line just above the x tick labels (labels hang below axis)
        x_axis = None
        if xt:
            band_y = min(t["y0"] for t in xt)
            cand = [l for l in h_lines if band_y - 10 <= l[0] <= band_y + 2]
            if cand:
                x_axis = max(cand, key=lambda l: l[2] - l[1])
        # y axis = vertical line just right of the y tick labels
        y_axis = None
        if yt:
            band_x = max(t["cx"] for t in yt)
            cand = [l for l in v_lines if band_x + 2 <= l[0] <= band_x + 20]
            if cand:
                y_axis = max(cand, key=lambda l: l[2] - l[1])
        if x_axis and y_axis:
            yline_y0, yline_y1 = y_axis[1], y_axis[2]
            xline_x0, xline_x1 = x_axis[1], x_axis[2]
            return {"x0": y_axis[0], "x1": xline_x1, "y0": yline_y0, "y1": x_axis[0]}
        # final fallback: frame from tick label extremes (labels bracket the plot)
        x_row = min((t["y0"] for t in xt), default=None)
        if x_row is not None:
            yt2 = [t for t in ticks if t["y0"] < x_row - 3]
            xt2 = [t for t in ticks if t["y0"] >= x_row - 3]
            if len(yt2) >= 2 and len(xt2) >= 2:
                x0 = max(t["cx"] for t in yt2) + 6
                y0 = min(t["y0"] for t in yt2) - 4
                y1 = min(t["y0"] for t in xt2) - 2
                x1 = max(t["cx"] for t in xt2) + 18
                return {"x0": x0, "x1": x1, "y0": y0, "y1": y1}

    # fallback: generic long thin lines
    xs, ys = [], []
    for p in paths:
        w = p["width"] or 0
        if not (0.3 <= w <= 0.7):
            continue
        for it in p["items"]:
            if it["op"] != "l":
                continue
            x0, y0, x1, y1 = it["x"], it["y"], it["x2"], it["y2"]
            x0 = max(x0, r.x0); x1 = min(x1, r.x1)
            y0 = max(y0, r.y0); y1 = min(y1, r.y1)
            if x0 >= x1 and y0 >= y1:
                continue
            dx = abs(x1 - x0); dy = abs(y1 - y0)
            if dx > 40 or dy > 40:
                if abs(dy) < 2:
                    xs += [x0, x1]; ys.append((y0 + y1) / 2)
                elif abs(dx) < 2:
                    ys += [y0, y1]; xs.append((x0 + x1) / 2)
    if not xs:
        return None
    return {"x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys)}

def fit(points, xlog):
    """Least-squares line fit: page-coord -> value. Points are (coord, value)."""
    coords = np.array([p[0] for p in points], dtype=float)
    if xlog:
        vals = np.array([math.log10(v) if v > 0 else 0 for _, v in points], dtype=float)
    else:
        vals = np.array([v for _, v in points], dtype=float)
    A = np.vstack([coords, np.ones(len(coords))]).T
    k, b = np.linalg.lstsq(A, vals, rcond=None)[0]
    return k, b

def calibrate(ticks, frame, xlog=True, autodetect=False):
    """Return (x_fn, y_fn) mapping page coords -> physical values.
    y ticks = labels strictly left of the y-axis; x ticks = labels below x-axis.
    If autodetect, choose log vs linear x by least-squares residual."""
    yt = [t for t in ticks if t["cx"] < frame["x0"] and t["y0"] > frame["y0"] - 3
          and t["y0"] < frame["y1"] - 3]
    if len(yt) < 2:
        raise ValueError(f"not enough y ticks ({len(yt)})")
    ky, by = fit([(t["cy"], t["value"]) for t in yt], xlog=False)

    xt = [t for t in ticks if t["y0"] > frame["y1"] - 3 and t["cx"] > frame["x0"] - 2
          and t["cx"] < frame["x1"] + 2]
    if len(xt) < 2:
        raise ValueError(f"not enough x ticks ({len(xt)})")
    if autodetect:
        pts = [(t["cx"], t["value"]) for t in xt]
        k_lin, b_lin = fit(pts, xlog=False)
        res_lin = sum((k_lin * c + b_lin - v) ** 2 for c, v in pts)
        pos = [p for p in pts if p[1] > 0]
        if len(pos) >= 3 and all(p[1] > 0 for p in pos):
            k_log, b_log = fit(pos, xlog=True)
            res_log = sum((math.log10(v) - (k_log * c + b_log)) ** 2 for c, v in pos)
            xlog = res_log < res_lin
        else:
            xlog = False
    kx, bx = fit([(t["cx"], t["value"]) for t in xt], xlog=xlog)

    def x_fn(px):
        v = kx * px + bx
        return 10 ** v if xlog else v

    def y_fn(py):
        return ky * py + by

    return x_fn, y_fn, {"y_ticks": [(t["value"], round(t["cy"], 2)) for t in yt],
                        "x_ticks": [(t["value"], round(t["cx"], 2)) for t in xt]}

def polyline_points(items):
    """Flatten a polyline (l + c segments) to sampled points."""
    pts = []
    for it in items:
        if it["op"] == "l":
            pts.append((it["x"], it["y"]))
            pts.append((it["x2"], it["y2"]))
        elif it["op"] == "c":
            for t in np.linspace(0, 1, 12):
                x = (1-t)**3*it["x1"] + 3*(1-t)**2*t*it["x2"] + 3*(1-t)*t**2*it["x3"] + t**3*it["x3"]
                y = (1-t)**3*it["y1"] + 3*(1-t)**2*t*it["y2"] + 3*(1-t)*t**2*it["y3"] + t**3*it["y3"]
                pts.append((float(x), float(y)))
    return pts

def find_page(doc, figure_id):
    for pg in doc:
        if pg.search_for(f"Figure {figure_id}"):
            return pg
    return doc[0]

def legend_labels(page, region, frame):
    """Extract legend/annotation text inside the plot (non-numeric, short) and
    return (text, cx, cy) — used to label curves by proximity."""
    r = pymupdf.Rect(*region)
    d = page.get_text("dict")
    out = []
    for b in d["blocks"]:
        for l in b.get("lines", []):
            spans = l["spans"]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            x0 = min(s["bbox"][0] for s in spans); y0 = min(s["bbox"][1] for s in spans)
            x1 = max(s["bbox"][2] for s in spans); y1 = max(s["bbox"][3] for s in spans)
            if x0 < r.x0 or x1 > r.x1 or y0 < r.y0 or y1 > r.y1:
                continue
            # must be inside plot box horizontally, near curve area (not axis labels)
            if not (frame["x0"] + 5 < x0 and x1 < frame["x1"] - 5):
                continue
            if y0 < frame["y0"] or y1 > frame["y1"] + 12:
                continue
            try:
                float(text)
                continue  # tick label
            except ValueError:
                pass
            if len(text) > 40:
                continue
            out.append({"text": text, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2})
    return out

def assign_labels(curves, labels):
    """Assign each legend label to the nearest curve (by label midpoint vs curve
    bbox). Returns curves with 'label' filled where confident."""
    if not labels:
        return curves
    for cu in curves:
        xs = [p[0] for p in cu["data"]]; ys = [p[1] for p in cu["data"]]
        # work in page coords: convert back via stored calibration? we keep page
        # coords by passing label cx/cy in physical space — simpler: nearest in
        # (x,y) distance to the curve's sampled points
        best = None; best_d = 1e18
        for lab in labels:
            for px, py in cu.get("_page_pts", [])[:1]:
                pass
            d = min(((lab["cx"] - x) ** 2 + (lab["cy"] - y) ** 2)
                    for x, y in cu.get("_page_pts", []))
            if d < best_d:
                best_d = d; best = lab
        if best and best_d < 900:
            cu["label"] = best["text"]
            labels.remove(best)
    return curves

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("figure", help="e.g. 9-4")
    ap.add_argument("--paths-json", help="paths json (default: out/figures/<part>_p<NN>_fig<F>.paths.json)")
    ap.add_argument("--manifest", default="out/figures/manifest.json")
    ap.add_argument("--out", default="out/digitized")
    ap.add_argument("--xlog", action="store_true", default=True, help="log x-axis (default)")
    ap.add_argument("--no-xlog", action="store_false", dest="xlog", help="linear x-axis")
    ap.add_argument("--autodetect", action="store_true", default=True,
                    help="auto-pick log/linear x-axis by residual (default on)")
    ap.add_argument("--xlabel", default="Output Current (A)")
    ap.add_argument("--ylabel", default="Efficiency (%)")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    manifest = json.load(open(args.manifest))
    entry = None
    page_no = None
    for pg in manifest["pages"]:
        for f in pg["figures"]:
            if f["figure"] == args.figure:
                entry = f; page_no = pg["page"]; break
        if entry: break
    if entry is None:
        raise SystemExit(f"figure {args.figure} not in manifest")
    page = doc[page_no - 1]
    region = entry["region_pt"]
    paths_json = args.paths_json or os.path.join(os.path.dirname(args.manifest), entry["paths_json"])
    paths = json.load(open(paths_json))
    col_band = (entry.get("cap_x0"), entry.get("cap_x1")) if "cap_x0" in entry else None
    ticks = tick_texts(page, region, col_band)

    frame = find_axis_frame(paths, region, ticks=ticks)
    if frame is None:
        raise SystemExit("no axis frame found")
    x_fn, y_fn, calib = calibrate(ticks, frame, xlog=args.xlog, autodetect=args.autodetect)

    # --- curve assembly: chain line segments into full curves -----------------
    # Works for single-path curves, multi-piece paths (older solid
    # curves split across path objects), and dashed curves (older plots draw dashes
    # as tiny dark-filled quads).
    segs = []  # (x0, y0, x1, y1, color) for line segs
    dash_pts = []  # (x, y, color) centroids of filled dash quads
    for p in paths:
        c = p["color"]
        f = p["fill"]
        n_seg = sum(1 for it in p["items"] if it["op"] == "l")
        if n_seg < 1:
            continue
        # dashed curves: color is None, fill is a dark neutral color
        if c is None and f and max(f) < 0.5 and max(f) - min(f) < 0.15:
            pts = polyline_points(p["items"])
            if pts:
                cx = sum(x for x, y in pts) / len(pts)
                cy = sum(y for x, y in pts) / len(pts)
                dash_pts.append((cx, cy, tuple(round(v, 3) for v in f)))
            continue
        if c is None:
            continue
        if max(c) - min(c) < 0.15 and max(c) < 0.5 and (not p["width"] or p["width"] < 0.6):
            continue  # thin black/gray axis line or arrow; curves are colored or thick
        for it in p["items"]:
            if it["op"] != "l":
                continue
            segs.append((it["x"], it["y"], it["x2"], it["y2"], c))
    # keep segments inside the frame, clip to frame
    segs = [(x0, y0, x1, y1, c) for x0, y0, x1, y1, c in segs
            if x0 < frame["x1"] + 2 and x1 > frame["x0"] - 2
            and y0 < frame["y1"] + 2 and y1 > frame["y0"] - 2]
    dash_pts = [(x, y, c) for x, y, c in dash_pts
                if x < frame["x1"] + 2 and x > frame["x0"] - 2
                and y < frame["y1"] + 2 and y > frame["y0"] - 2]
    # chain: sort by min-x, then grow chains where next seg starts at/after the
    # current end within a small gap
    segs.sort(key=lambda s: min(s[0], s[2]))
    chains = []  # list of (list of (x,y) page pts, color)
    for x0, y0, x1, y1, c in segs:
        placed = False
        for ch in chains:
            ch_pts, ch_c = ch
            if ch_c != c:
                continue
            last = ch_pts[-1]
            # current chain ends at `last`; seg can attach at either end
            gap = min(abs(last[0] - x0) + abs(last[1] - y0),
                      abs(last[0] - x1) + abs(last[1] - y1))
            if gap < 3:
                if abs(last[0] - x0) + abs(last[1] - y0) < abs(last[0] - x1) + abs(last[1] - y1):
                    ch_pts.append((x1, y1))
                else:
                    ch_pts.append((x0, y0))
                placed = True
                break
            # also try attaching at chain start
            first = ch_pts[0]
            gapf = min(abs(first[0] - x0) + abs(first[1] - y0),
                       abs(first[0] - x1) + abs(first[1] - y1))
            if gapf < 3:
                if abs(first[0] - x0) + abs(first[1] - y0) < abs(first[0] - x1) + abs(first[1] - y1):
                    ch_pts.insert(0, (x1, y1))
                else:
                    ch_pts.insert(0, (x0, y0))
                placed = True
                break
        if not placed:
            chains.append([[(x0, y0), (x1, y1)], c])
    # dashed curves: chain dash centroids. Dashes from different curves interleave
    # in x, so attach each dash to the NEAREST chain (Euclidean) that also has
    # y-continuity, keeping each dashed curve as its own smooth polyline.
    dash_pts.sort(key=lambda p: p[0])
    for x, y, c in dash_pts:
        best = None; best_d = 1e18
        for ch in chains:
            ch_pts, ch_c = ch
            if ch_c != c:
                continue
            last = ch_pts[-1]
            d = (last[0] - x) ** 2 + (last[1] - y) ** 2
            if d < best_d and abs(last[1] - y) < 4:
                best_d = d; best = ch
        if best is not None and best_d < 25:
            best[0].append((x, y))
        else:
            chains.append([[(x, y)], c])
    curves = []
    for ci, (ch_pts, c) in enumerate(chains):
        # drop tiny fragments (probably tick marks or noise)
        if len(ch_pts) < 6:
            continue
        data = [(round(x_fn(px), 5), round(y_fn(py), 3)) for px, py in ch_pts]
        if data:
            curves.append({"path_idx": ci, "color": [round(v, 3) for v in c],
                           "n_points": len(data), "data": data, "_page_pts": ch_pts})
    # legend label association: labels have black leader-line arrows; follow the
    # arrow head to the nearest curve
    labels = legend_labels(page, region, frame)
    arrows = []
    for p in paths:
        if p["color"] == [0.0, 0.0, 0.0]:
            for it in p["items"]:
                if it["op"] == "l":
                    x0, y0, x1, y1 = it["x"], it["y"], it["x2"], it["y2"]
                    L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                    if 8 < L < 60:
                        arrows.append(((x0, y0), (x1, y1)))
    for cu in curves:
        best = None; best_d = 1e18
        for lab in labels:
            if not arrows:
                break
            best_a = min(arrows, key=lambda a: min(
                ((a[0][0] - lab["cx"]) ** 2 + (a[0][1] - lab["cy"]) ** 2) ** 0.5,
                ((a[1][0] - lab["cx"]) ** 2 + (a[1][1] - lab["cy"]) ** 2) ** 0.5))
            d0 = ((best_a[0][0] - lab["cx"]) ** 2 + (best_a[0][1] - lab["cy"]) ** 2) ** 0.5
            d1 = ((best_a[1][0] - lab["cx"]) ** 2 + (best_a[1][1] - lab["cy"]) ** 2) ** 0.5
            head = best_a[0] if d0 > d1 else best_a[1]
            d = min((head[0] - x) ** 2 + (head[1] - y) ** 2 for x, y in cu["_page_pts"])
            if d < best_d:
                best_d = d; best = lab
        if best and best_d < 2500 and best not in [c.get("label") for c in curves]:
            cu["label"] = best["text"]
            labels.remove(best)
    for cu in curves:
        cu.pop("_page_pts", None)

    os.makedirs(args.out, exist_ok=True)
    base = f"{manifest.get('part', 'part')}_fig{args.figure}"
    result = {"figure": args.figure, "caption": entry["caption"],
              "x_label": args.xlabel, "y_label": args.ylabel,
              "x_log": args.xlog, "calibration": calib, "curves": curves}
    with open(os.path.join(args.out, base + ".json"), "w") as f:
        json.dump(result, f, indent=1)
    with open(os.path.join(args.out, base + ".csv"), "w") as f:
        f.write(f"curve,label,color,x({args.xlabel}),y({args.ylabel})\n")
        for k, cu in enumerate(curves):
            label = cu.get("label", "")
            for x, y in cu["data"]:
                f.write(f"{k},\"{label}\",\"rgb{tuple(cu['color'])}\",{x},{y}\n")
    print(f"figure {args.figure}: {len(calib['y_ticks'])} y-ticks, {len(calib['x_ticks'])} x-ticks, {len(curves)} curves")
    for k, cu in enumerate(curves):
        xs = [d[0] for d in cu["data"]]; ys = [d[1] for d in cu["data"]]
        print(f"  curve {k}: color={cu['color']} label={cu.get('label','')!r} n={cu['n_points']} "
              f"x[{min(xs):.5g}, {max(xs):.5g}] y[{min(ys):.1f}%, {max(ys):.1f}%]")

if __name__ == "__main__":
    main()
