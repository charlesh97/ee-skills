#!/usr/bin/env python3
"""Regulator cells as data: extract one from a board, build a demo board from one, place one onto a board.

A cell is a regulator's parts and its local copper (component-layer pours, the SW neck, its vias and short
tracks), stored as JSON in the cell's own frame (mm, the IC's centre at 0,0 unless the spec says otherwise).

  $KPY cell.py extract BOARD --refs U2,L1,C4,... --origin X,Y [--rot DEG] [--local-layers F.Cu] -o cell.json
        Reads a board (a hand-laid demo, or the cell area of a real board) and writes the cell spec:
        footprint poses, every track and via on the cell's nets inside its box, and the cell's zones on its
        local layers clipped to the box (zones on other layers are kept as demo_planes). Read only. The
        first ref should be the IC.
  $KPY cell.py build cell.json --source BOARD -o demo.kicad_pcb [--project X.kicad_pro]
        Copies the cell's footprints out of BOARD (read only) onto an empty board of the same stackup,
        with the spec's outline, planes and extra pads, and lays the cell copper. For trying a layout
        before it goes onto the real board.
  $KPY cell.py place cell.json --target BOARD --at X,Y [--rot DEG] -o OUT.kicad_pcb [--project X.kicad_pro]
        Writes a copy of BOARD with the cell placed at (X,Y,rot): moves the cell's footprints, removes the
        target's copper on the cell's private nets (nets whose every pad is in the cell), and adds the
        cell's copper. Zones of shared nets (GND, the input and output rails) are added only where the
        target has no zone of that net on that layer, so no zone is stacked (L-23). Never writes BOARD.

pcbnew's SaveBoard drops the net classes from the .kicad_pro, so --project copies a project file next to
the output (pass the source board's).
"""
import sys, os, json, math, argparse, shutil
import pcbnew

mm, iu = pcbnew.ToMM, pcbnew.FromMM
KEEP = []      # SWIG: hold every wrapper the board owns until the save, or SaveBoard can crash


def xf(p, at, rot):
    """Cell frame -> board frame. KiCad rotations are counter-clockwise on screen with y pointing down."""
    t = math.radians(rot); x, y = p
    return (at[0] + x * math.cos(t) + y * math.sin(t), at[1] - x * math.sin(t) + y * math.cos(t))


def ixf(p, at, rot):
    """Board frame -> cell frame."""
    t = math.radians(rot); x, y = p[0] - at[0], p[1] - at[1]
    return (x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t))


def V(p): return pcbnew.VECTOR2I(iu(p[0]), iu(p[1]))
def P(v): return (mm(v.x), mm(v.y))


def outline_pts(z):
    o = z.Outline(); out = []
    for i in range(o.OutlineCount()):
        c = o.Outline(i); out.append([P(c.CPoint(k)) for k in range(c.PointCount())])
    return out


def add_zone(b, net, layer, pts, prio=0, name="", thermal=False, clearance=0.2, minw=0.2):
    z = pcbnew.ZONE(b); z.SetLayer(b.GetLayerID(layer)); z.SetNet(b.FindNet(net)); z.SetAssignedPriority(prio)
    z.SetZoneName(name or f"{net.split('/')[-1]} {layer}")
    ol = z.Outline(); ol.NewOutline()
    for p in pts: ol.Append(iu(p[0]), iu(p[1]))
    z.SetLocalClearance(iu(clearance)); z.SetMinThickness(iu(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z); KEEP.append(z); return z


def add_track(b, net, layer, a, c, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(V(a)); t.SetEnd(V(c)); t.SetWidth(iu(w))
    t.SetLayer(b.GetLayerID(layer)); t.SetNet(b.FindNet(net)); b.Add(t); KEEP.append(t)


def add_via(b, net, p, d, drill):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(p)); v.SetWidth(iu(d)); v.SetDrill(iu(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(b.FindNet(net)); b.Add(v); KEEP.append(v)


def save(b, out, project):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(out, b)
    if project:
        shutil.copy(project, os.path.splitext(out)[0] + ".kicad_pro")
    print("wrote", out)


# ---------------------------------------------------------------- extract
def extract(a):
    b = pcbnew.LoadBoard(a.board)
    refs = a.refs.split(","); at = tuple(float(v) for v in a.origin.split(",")); rot = a.rot
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    missing = [r for r in refs if r not in fps]
    if missing: sys.exit(f"not on the board: {missing}")
    nets = {p.GetNetname() for r in refs for p in fps[r].Pads() if p.GetNetname()}
    # the cell's box: its footprints' courtyards plus a margin
    xs, ys = [], []
    for r in refs:
        bb = fps[r].GetBoundingBox(False)
        xs += [mm(bb.GetLeft()), mm(bb.GetRight())]; ys += [mm(bb.GetTop()), mm(bb.GetBottom())]
    m = a.margin
    X0, Y0, X1, Y1 = min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m
    inside = lambda p: X0 <= p[0] <= X1 and Y0 <= p[1] <= Y1
    spec = dict(origin_rot=0.0, refs=refs, footprints={}, tracks=[], vias=[], zones=[],
                note="extracted by cell.py; coordinates in mm in the cell frame")
    for r in refs:
        f = fps[r]
        spec["footprints"][r] = dict(at=[round(v, 4) for v in ixf(P(f.GetPosition()), at, rot)],
                                     rot=round((f.GetOrientationDegrees() - rot) % 360, 3),
                                     side="B" if f.IsFlipped() else "F")
    for t in b.GetTracks():
        if t.GetNetname() not in nets: continue
        if t.GetClass() == "PCB_VIA":
            p = P(t.GetPosition())
            if inside(p):
                spec["vias"].append(dict(net=t.GetNetname(), at=[round(v, 4) for v in ixf(p, at, rot)],
                                         d=round(mm(t.GetWidth(pcbnew.F_Cu)), 3), drill=round(mm(t.GetDrillValue()), 3)))
        else:
            s, e = P(t.GetStart()), P(t.GetEnd())
            if inside(s) and inside(e):
                spec["tracks"].append(dict(net=t.GetNetname(), layer=b.GetLayerName(t.GetLayer()), w=round(mm(t.GetWidth()), 3),
                                           pts=[[round(v, 4) for v in ixf(s, at, rot)], [round(v, 4) for v in ixf(e, at, rot)]]))
    from shapely.geometry import Polygon, box as sbox
    cbox = sbox(X0, Y0, X1, Y1)
    spec["demo_planes"] = []
    local = set(a.local_layers.split(",")) if a.local_layers else {"B.Cu" if fps[refs[0]].IsFlipped() else "F.Cu"}
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in nets: continue
        for pts in outline_pts(z):
            poly = Polygon(pts).buffer(0)
            for l in z.GetLayerSet().CuStack():
                rec = dict(net=z.GetNetname(), layer=b.GetLayerName(l), prio=z.GetAssignedPriority(), name=z.GetZoneName(),
                           thermal=z.GetPadConnection() == pcbnew.ZONE_CONNECTION_THERMAL)
                if b.GetLayerName(l) not in local:     # a plane layer: the real board has its own planes
                    spec["demo_planes"].append(dict(rec, pts=[[round(v, 4) for v in ixf(p, at, rot)] for p in pts]))
                    continue
                clip = poly.intersection(cbox)
                for g in (clip.geoms if hasattr(clip, "geoms") else [clip]):
                    if g.geom_type == "Polygon" and g.area > 0.05:
                        spec["zones"].append(dict(rec, pts=[[round(v, 4) for v in ixf(p, at, rot)] for p in list(g.exterior.coords)[:-1]]))
    spec["demo_origin"] = [100.0, 100.0]
    c0, c1 = ixf((X0, Y0), at, rot), ixf((X1, Y1), at, rot)
    spec["demo_outline"] = [round(min(c0[0], c1[0]) - 2, 2), round(min(c0[1], c1[1]) - 2, 2), round(max(c0[0], c1[0]) + 2, 2), round(max(c0[1], c1[1]) + 2, 2)]
    spec["extra_pads"] = []
    json.dump(spec, open(a.o, "w"), indent=1)
    print(f"wrote {a.o}: {len(refs)} footprints, {len(spec['tracks'])} tracks, {len(spec['vias'])} vias, {len(spec['zones'])} zones")


# ---------------------------------------------------------------- build
def build(a):
    spec = json.load(open(a.cell))
    b = pcbnew.LoadBoard(a.source)
    allf, allt, allz, alld, allg = list(b.GetFootprints()), list(b.GetTracks()), list(b.Zones()), list(b.GetDrawings()), list(b.Groups())
    KEEP.extend(allf + allt + allz + alld + allg)
    for g in allg: b.Remove(g)
    for t in allt: b.Remove(t)
    for z in allz: b.Remove(z)
    for d in alld: b.Remove(d)
    refs = set(spec["footprints"]) | {e["copy_of"] for e in spec.get("extra_pads", [])}
    for f in allf:
        if f.GetReference() not in refs: b.Remove(f)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    at = tuple(spec.get("demo_origin", [100.0, 100.0]))
    place_fps(b, fps, spec, at, 0.0)
    for e in spec.get("extra_pads", []):
        f = pcbnew.FOOTPRINT(fps[e["copy_of"]]); f.SetReference(e["ref"]); b.Add(f); KEEP.append(f)
        want_b = e.get("side", "F") == "B"
        if f.IsFlipped() != want_b: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetPosition(V(xf(e["at"], at, 0.0)))
        for p in f.Pads(): p.SetNet(b.FindNet(e["net"]))
    for e in spec.get("extra_pads", []):
        if e["copy_of"] not in spec["footprints"]: b.Remove(fps[e["copy_of"]])
    x0, y0, x1, y1 = spec["demo_outline"]
    corners = [xf(p, at, 0) for p in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(corners[i])); s.SetEnd(V(corners[(i + 1) % 4]))
        s.SetLayer(b.GetLayerID("Edge.Cuts")); s.SetWidth(iu(0.1)); b.Add(s); KEEP.append(s)
    E = spec.get("demo_inset", 0.5)
    box = [(x0 + E, y0 + E), (x1 - E, y0 + E), (x1 - E, y1 - E), (x0 + E, y1 - E)]
    for z in spec.get("demo_planes", []):        # whole-board pours for the demo only (the real board has its own)
        pts = z.get("pts") or box
        add_zone(b, z["net"], z["layer"], [xf(p, at, 0) for p in pts], z.get("prio", 0), z.get("name", ""), z.get("thermal", False))
    lay_copper(b, spec, at, 0.0, skip=set())
    save(b, a.o, a.project)


def place_fps(b, fps, spec, at, rot):
    for r, e in spec["footprints"].items():
        f = fps[r]
        want_b = e.get("side", "F") == "B"
        if f.IsFlipped() != want_b: f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        f.SetPosition(V(xf(e["at"], at, rot))); f.SetOrientationDegrees((e["rot"] + rot) % 360)


def lay_copper(b, spec, at, rot, skip):
    for z in spec.get("zones", []):
        if (z["net"], z["layer"]) in skip: continue
        add_zone(b, z["net"], z["layer"], [xf(p, at, rot) for p in z["pts"]], z.get("prio", 0), z.get("name", ""), z.get("thermal", False))
    for t in spec.get("tracks", []):
        pts = [xf(p, at, rot) for p in t["pts"]]
        for p0, p1 in zip(pts, pts[1:]): add_track(b, t["net"], t["layer"], p0, p1, t["w"])
    for v in spec.get("vias", []):
        add_via(b, v["net"], xf(v["at"], at, rot), v.get("d", 0.6), v.get("drill", 0.3))


# ---------------------------------------------------------------- place
def place(a):
    spec = json.load(open(a.cell))
    if os.path.abspath(a.o) == os.path.abspath(a.target): sys.exit("refusing to overwrite the target; write a copy")
    b = pcbnew.LoadBoard(a.target)
    at = tuple(float(v) for v in a.at.split(",")); rot = a.rot
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    refs = list(spec["footprints"])
    missing = [r for r in refs if r not in fps]
    if missing: sys.exit(f"cell parts missing on the target: {missing}")
    locked = [r for r in refs if fps[r].IsLocked()]
    if locked and not a.allow_locked:
        sys.exit(f"locked on the target: {locked}. Moving them needs the owner's yes; rerun with --allow-locked on a copy.")
    cellpads = {(r, p.GetNumber()) for r in refs for p in fps[r].Pads()}
    nets = {p.GetNetname() for r in refs for p in fps[r].Pads() if p.GetNetname()}
    private = {n for n in nets if all((p.GetParentFootprint().GetReference(), p.GetNumber()) in cellpads
                                      for p in b.GetPads() if p.GetNetname() == n)}
    shared = nets - private
    gone = [t for t in b.GetTracks() if t.GetNetname() in private]
    zgone = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() in private]
    KEEP.extend(gone + zgone)
    for t in gone: b.Remove(t)
    for z in zgone: b.Remove(z)
    place_fps(b, fps, spec, at, rot)
    have = {(z.GetNetname(), b.GetLayerName(l)) for z in b.Zones() if not z.GetIsRuleArea() for l in z.GetLayerSet().CuStack()}
    skip = {(z["net"], z["layer"]) for z in spec.get("zones", []) if z["net"] in shared and (z["net"], z["layer"]) in have}
    lay_copper(b, spec, at, rot, skip)
    print(f"private nets {len(private)}, shared {len(shared)}: removed {len(gone)} tracks/vias and {len(zgone)} zones; "
          f"skipped cell zones already poured on the target: {sorted(f'{n.split(chr(47))[-1]}@{l}' for n, l in skip)}")
    save(b, a.o, a.project)


ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
e = sub.add_parser("extract"); e.add_argument("board"); e.add_argument("--refs", required=True); e.add_argument("--origin", required=True)
e.add_argument("--rot", type=float, default=0.0); e.add_argument("--margin", type=float, default=0.5); e.add_argument("-o", required=True)
e.add_argument("--local-layers", help="layers whose zones belong to the cell (default: the first part's side); zones on other layers are planes")
bd = sub.add_parser("build"); bd.add_argument("cell"); bd.add_argument("--source", required=True); bd.add_argument("-o", required=True)
bd.add_argument("--project")
pl = sub.add_parser("place"); pl.add_argument("cell"); pl.add_argument("--target", required=True); pl.add_argument("--at", required=True)
pl.add_argument("--rot", type=float, default=0.0); pl.add_argument("-o", required=True); pl.add_argument("--project")
pl.add_argument("--allow-locked", action="store_true")
a = ap.parse_args()
{"extract": extract, "build": build, "place": place}[a.cmd](a)
