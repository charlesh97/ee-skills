#!/usr/bin/env python3
"""Render a region of a board for anchor_place.py before/after reviews (KRT venv python: pcbnew + Pillow).

Seen from the top (x not mirrored), board mm on the axes. Bottom courtyards blue, top red; pads of the
movable parts filled in accent, others grey; B.Cu copper blue, F.Cu red, inner layers faint; vias as
rings; each routed-net airwire (MST of its pads in the region, the far end clipped at the frame) dashed.
With --plan, a thin arrow from each moved part's old origin to its new one. Never draws silkscreen.

  $KV anchor_render.py BOARD OUT.png --movable movable.txt --region X0 Y0 X1 Y1 --title "..."
                       [--nets local.nets] [--plan plan.csv] [--no-copper] [--airwires] [--scale 32]"""
import argparse, csv, math, os, sys
import pcbnew
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anchor_place as A

ap = argparse.ArgumentParser()
ap.add_argument("board"); ap.add_argument("out"); ap.add_argument("--movable", required=True)
ap.add_argument("--region", type=float, nargs=4, required=True); ap.add_argument("--title", default="")
ap.add_argument("--nets"); ap.add_argument("--plan"); ap.add_argument("--no-copper", action="store_true")
ap.add_argument("--airwires", action="store_true"); ap.add_argument("--scale", type=float, default=32)
a = ap.parse_args()
B = A.Board(a.board, A.read_refs(a.movable), a.region); b = B.b; mm = A.mm
x0, y0, x1, y1 = a.region; pad_ = 1.0; x0 -= pad_; y0 -= pad_; x1 += pad_; y1 += pad_
S = a.scale; TOP = 40; W, H = int((x1 - x0) * S), int((y1 - y0) * S)
im = Image.new("RGB", (W, H + TOP), (250, 250, 247)); dr = ImageDraw.Draw(im, "RGBA")
P = lambda x, y: ((x - x0) * S, (y - y0) * S + TOP)
def font(sz):
    try: return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sz)
    except Exception: return ImageFont.load_default()
F12, F15, F20 = font(12), font(15), font(20)
ACC = (230, 0, 140); LCOL = {"F.Cu": (200, 60, 50), "B.Cu": (40, 110, 220)}
def polys(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); out.append([P(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())])
    return out
inview = lambda x, y: x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3
# courtyards
for f in b.GetFootprints():
    fx, fy = A.pxy(f)
    if not inview(fx, fy): continue
    bs = f.IsFlipped(); cy = f.GetCourtyard(pcbnew.B_CrtYd if bs else pcbnew.F_CrtYd)
    for pg in polys(cy):
        if len(pg) > 2: dr.line(pg + [pg[0]], fill=(40, 110, 220, 170) if bs else (190, 70, 60, 90), width=2 if bs else 1)
# copper
if not a.no_copper:
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T: continue
        s, e = t.GetStart(), t.GetEnd(); L = t.GetLayerName()
        if not (inview(mm(s.x), mm(s.y)) or inview(mm(e.x), mm(e.y))): continue
        c = LCOL.get(L, (150, 150, 150)); al = 210 if L in LCOL else 70
        if L == "F.Cu": al = 110
        dr.line([P(mm(s.x), mm(s.y)), P(mm(e.x), mm(e.y))], fill=c + (al,), width=max(1, int(mm(t.GetWidth()) * S)))
# pads (B side solid, F side faint)
for f in b.GetFootprints():
    fx, fy = A.pxy(f)
    if not inview(fx, fy): continue
    mv = f.GetReference() in B.mov
    for p in f.Pads():
        for ln, L in ((pcbnew.B_Cu, "B"), (pcbnew.F_Cu, "F")):
            if not (p.IsOnLayer(ln) and p.FlashLayer(ln)): continue
            for pg in polys(p.GetEffectivePolygon(ln, pcbnew.ERROR_INSIDE)):
                if len(pg) < 3: continue
                if L == "B": dr.polygon(pg, fill=(ACC + (210,)) if mv else (90, 90, 90, 200))
                else: dr.polygon(pg, fill=(190, 120, 110, 70))
# vias
nv = 0
if not a.no_copper:
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T: continue
        x, y = A.pxy(t)
        if not (a.region[0] <= x <= a.region[2] and a.region[1] <= y <= a.region[3]): continue
        nv += 1; X, Y = P(x, y); r = mm(t.GetWidth(pcbnew.F_Cu)) * S / 2; rd = mm(t.GetDrillValue()) * S / 2
        dr.ellipse([X - r, Y - r, X + r, Y + r], fill=(120, 120, 50, 235)); dr.ellipse([X - rd, Y - rd, X + rd, Y + rd], fill=(250, 250, 247, 255))
# airwires
if a.airwires:
    nets = [l.strip() for l in open(a.nets)] if a.nets else A.area_nets(B)
    for n in nets:
        pts = [A.pxy(p) for _, p in B.netpads[n]]
        for (p, q) in A.mst_segments(pts):
            if not (inview(*p) or inview(*q)): continue
            s, e = P(*p), P(*q); L = math.dist(s, e); k = max(1, int(L / 8))
            for i in range(0, k, 2):
                u0, u1 = i / k, min(i + 1, k) / k
                dr.line([(s[0] + (e[0] - s[0]) * u0, s[1] + (e[1] - s[1]) * u0), (s[0] + (e[0] - s[0]) * u1, s[1] + (e[1] - s[1]) * u1)], fill=(20, 20, 20, 200), width=2)
# moves
if a.plan:
    for r in csv.DictReader(open(a.plan)):
        p, q = (float(r["x0"]), float(r["y0"])), (float(r["x1"]), float(r["y1"]))
        if math.dist(p, q) < 0.3: continue
        dr.line([P(*p), P(*q)], fill=(0, 150, 70, 150), width=2)
        X, Y = P(*p); dr.ellipse([X - 3, Y - 3, X + 3, Y + 3], outline=(0, 150, 70, 220), width=2)
# labels
for f in b.GetFootprints():
    fx, fy = A.pxy(f); r = f.GetReference()
    if not (x0 <= fx <= x1 and y0 <= fy <= y1): continue
    big = not A.SMALL.match(r) and not r.startswith("TP") and r not in B.mov
    if not (r in B.mov or big): continue
    if not big and not f.IsFlipped(): continue
    X, Y = P(fx, fy); fnt = F20 if big else F12
    bb = dr.textbbox((0, 0), r, font=fnt); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    dr.rectangle([X - tw / 2 - 2, Y - th / 2 - 2, X + tw / 2 + 2, Y + th / 2 + 4], fill=(255, 255, 255, 200))
    dr.text((X - tw / 2, Y - th / 2), r, fill=(0, 0, 0, 255) if big else (120, 0, 70, 255), font=fnt)
dr.rectangle([0, 0, W, TOP - 1], fill=(30, 30, 30, 255))
dr.text((8, 9), a.title + (f"   [{nv} vias in frame]" if not a.no_copper else ""), fill=(255, 255, 255), font=F20)
for gx in range(int(math.ceil(x0 / 5) * 5), int(x1) + 1, 5):
    X = (gx - x0) * S; dr.line([(X, TOP), (X, TOP + 8)], fill=(0, 0, 0, 200)); dr.text((X + 2, TOP + 6), str(gx), fill=(0, 0, 0, 200), font=F12)
for gy in range(int(math.ceil(y0 / 5) * 5), int(y1) + 1, 5):
    Y = (gy - y0) * S + TOP; dr.line([(0, Y), (8, Y)], fill=(0, 0, 0, 200)); dr.text((10, Y - 7), str(gy), fill=(0, 0, 0, 200), font=F12)
im.convert("P", palette=Image.ADAPTIVE, colors=200).save(a.out, optimize=True)
print(a.out, W, H + TOP)
