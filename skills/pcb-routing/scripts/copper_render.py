"""Render a KiCad board's copper the way a layout engineer looks at it.

All copper layers composited, colour by layer, tracks at their real width, pads
and vias drawn, outline on top. Geometry comes from pcbnew itself, so it's exact
and it doesn't hit route_render.py's crash on degenerate pads.

Run with KiCad's bundled python ($KPY):
  copper_render.py board.kicad_pcb out.png [--view x0,y0,x1,y1] [--ppmm 45]
                   [--layers F.Cu,In1.Cu] [--fill] [--nozones]

  --view    window in board mm; default the whole board
  --ppmm    pixels per mm; 40-60 reads 0.1 mm tracks, lower for whole-board
  --layers  subset of copper layers (per-layer views); default all
  --fill    refill zones before drawing (a routed board may ship unfilled)
  --nozones leave pours out, so tracks under a plane are visible
"""
import argparse
import pcbnew
from PIL import Image, ImageDraw

# F.Cu red, B.Cu blue, inner layers cycle through these
FRONT, BACK = (200, 52, 52), (40, 90, 210)
INNER = [(194, 150, 0), (170, 60, 190), (30, 150, 120), (230, 120, 20), (110, 110, 110)]

ap = argparse.ArgumentParser()
ap.add_argument("board"); ap.add_argument("out")
ap.add_argument("--view"); ap.add_argument("--ppmm", type=float, default=45)
ap.add_argument("--layers"); ap.add_argument("--fill", action="store_true")
ap.add_argument("--nozones", action="store_true")
a = ap.parse_args()

b = pcbnew.LoadBoard(a.board)
if a.fill:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

copper = [b.GetLayerName(l) for l in b.GetEnabledLayers().CuStack()]  # F.Cu .. B.Cu
col = {}
for i, ln in enumerate(copper):
    col[ln] = FRONT if ln == "F.Cu" else BACK if ln == "B.Cu" else INNER[(i - 1) % len(INNER)]
want = a.layers.split(",") if a.layers else copper
order = [ln for ln in reversed(copper) if ln in want]  # paint bottom first, F.Cu on top

bb = b.GetBoardEdgesBoundingBox()
if a.view:
    x0, y0, x1, y1 = map(float, a.view.split(","))
else:
    x0, y0 = pcbnew.ToMM(bb.GetX()) - 0.5, pcbnew.ToMM(bb.GetY()) - 0.5
    x1, y1 = x0 + pcbnew.ToMM(bb.GetWidth()) + 1, y0 + pcbnew.ToMM(bb.GetHeight()) + 1
W, H = int((x1 - x0) * a.ppmm), int((y1 - y0) * a.ppmm)
BG = (250, 250, 247)
img = Image.new("RGB", (W, H), BG)


def P(v):
    return ((pcbnew.ToMM(v.x) - x0) * a.ppmm, (pcbnew.ToMM(v.y) - y0) * a.ppmm)


def draw_ps(d, ps, fill):
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        pts = [P(o.CPoint(k)) for k in range(o.PointCount())]
        if len(pts) > 2:
            d.polygon(pts, fill=fill)
        for h in range(ps.HoleCount(i)):
            hl = ps.Hole(i, h)
            hp = [P(hl.CPoint(k)) for k in range(hl.PointCount())]
            if len(hp) > 2:
                d.polygon(hp, fill=(0, 0, 0, 0))


def poly(item, lid):
    ps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(ps, lid, 0, pcbnew.FromMM(0.002), pcbnew.ERROR_INSIDE)
    return ps


for ln in order:
    lid, c = b.GetLayerID(ln), col[ln]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if not a.nozones:
        for z in b.Zones():
            if z.GetIsRuleArea() or not z.IsOnLayer(lid) or not z.HasFilledPolysForLayer(lid):
                continue
            draw_ps(d, z.GetFilledPolysList(lid), c + (70,))
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA" and t.IsOnLayer(lid):
            draw_ps(d, poly(t, lid), c + (215,))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(lid):
                draw_ps(d, poly(p, lid), tuple(int(x * 0.6) for x in c) + (235,))
    img.paste(ov, (0, 0), ov)

d = ImageDraw.Draw(img)
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        cx, cy = P(t.GetPosition())
        r = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 * a.ppmm
        h = pcbnew.ToMM(t.GetDrillValue()) / 2 * a.ppmm
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(90, 90, 90))
        d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=BG)
for dr in b.GetDrawings():
    if dr.GetLayerName() == "Edge.Cuts":
        draw_ps(d, poly(dr, pcbnew.Edge_Cuts), (20, 20, 20))
for i, ln in enumerate(order[::-1]):
    d.rectangle([6, 6 + i * 16, 18, 18 + i * 16], fill=col[ln]); d.text((22, 6 + i * 16), ln, fill=(0, 0, 0))
img.save(a.out)
print("wrote", a.out, W, H)
