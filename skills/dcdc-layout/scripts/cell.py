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
        cell's copper. A cell pour of a shared net (GND, the input and output rails) is skipped where a board
        pour of that net already covers it, merged into a board pour it overlaps (one zone per net per layer,
        L-23), and added where it touches none. Never writes BOARD.

  $KPY cell.py fit cell.json --target BOARD --region X0,Y0,X1,Y1 [--parts IC,L,CIN,COUT] [--movable REFS] [--prefer X,Y]
        Read only. Tries every pose on a grid in the region at each rotation and ranks them: board parts whose
        courtyards the cell's rigid parts hit, holes, keep-outs and the edge, then other-net vias and tracks
        under the cell's copper on every layer (a buried sense route counts against the board's inner lanes). Fit the rigid core first; the periphery is re-seated around it afterwards.

pcbnew's SaveBoard drops the net classes from the .kicad_pro, so --project copies a project file next to
the output (pass the source board's).
"""
import sys, os, json, math, argparse, shutil, collections
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
        sys.exit(f"locked on the target: {locked}. During a placement fix locks are not a constraint (L-67): "
                 "rerun with --allow-locked (the output is a copy either way).")
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
    # Shared-net cell pours (VIN, the output rail, GND) against the target's pours of the same net on the same layer:
    # covered by one -> it is already copper, skip; overlapping one -> merge into it (one zone per net per layer, L-23);
    # touching none -> add it. A same-net pour elsewhere on the layer is a separate pour and does not count.
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    tz = []
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in shared: continue
        polys = [Polygon(o).buffer(0) for o in outline_pts(z) if len(o) > 2]
        for l in z.GetLayerSet().CuStack(): tz.append((z, b.GetLayerName(l), polys))
    notes, rest = [], []
    for cz in spec.get("zones", []):
        if cz["net"] not in shared: rest.append(cz); continue
        P_ = Polygon([xf(p, at, rot) for p in cz["pts"]]).buffer(0)
        same = [(z, ps) for (z, ln, ps) in tz if z.GetNetname() == cz["net"] and ln == cz["layer"]
                and any(pp.intersection(P_).area > 0.01 for pp in ps)]
        tag = f"{cz['net'].split('/')[-1]}@{cz['layer']}"
        if any(pp.buffer(0.01).contains(P_) for (z, ps) in same for pp in ps):
            notes.append(f"{tag} covered by a board pour, skipped"); continue
        if same:
            z, ps = same[0]
            U = unary_union(ps + [P_])
            if U.geom_type == "Polygon" and len(same) == 1:
                sp = pcbnew.SHAPE_POLY_SET(); sp.NewOutline()
                for (x, y) in list(U.exterior.coords)[:-1]: sp.Append(iu(x), iu(y))
                for h in U.interiors:
                    hi = sp.NewHole()
                    for (x, y) in list(h.coords)[:-1]: sp.Append(iu(x), iu(y), 0, hi)
                z.SetOutline(sp); KEEP.append(sp)
                notes.append(f"{tag} merged into board zone '{z.GetZoneName()}'"); continue
            notes.append(f"{tag} overlaps {len(same)} board pour(s) that do not merge into one outline: added alongside, CHECK L-23")
        rest.append(cz)
    lay_copper(b, dict(spec, zones=rest), at, rot, skip=set())
    print(f"private nets {len(private)}, shared {len(shared)}: removed {len(gone)} tracks/vias and {len(zgone)} zones")
    for n_ in notes: print("  " + n_)
    save(b, a.o, a.project)


# ---------------------------------------------------------------- fit
def fit(a):
    """Search poses for a cell on a board: count what each pose collides with, best first. Read only."""
    from shapely.geometry import Polygon, Point, LineString, box as sbox
    from shapely.ops import unary_union
    from shapely.affinity import affine_transform
    from shapely.strtree import STRtree
    spec = json.load(open(a.cell)); b = pcbnew.LoadBoard(a.target)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    refs = list(spec["footprints"]); rigid = a.parts.split(",") if a.parts else refs
    free_ok = set(a.movable.split(",")) if a.movable else set()
    cellpads = {(r, p.GetNumber()) for r in refs for p in fps[r].Pads()}
    nets = {p.GetNetname() for r in refs for p in fps[r].Pads() if p.GetNetname()}
    private = {n for n in nets if all((p.GetParentFootprint().GetReference(), p.GetNumber()) in cellpads
                                      for p in b.GetPads() if p.GetNetname() == n)}

    def sps(ps):
        out = []
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i); pts = [P(o.CPoint(k)) for k in range(o.PointCount())]
            if len(pts) > 2: out.append(Polygon(pts).buffer(0))
        return unary_union(out) if out else None

    def court(f):
        g = sps(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd))
        if g is None:
            bb = f.GetBoundingBox(False); g = sbox(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom()))
        return g

    # the cell in its own frame
    def to_cell(g, f, e):
        pos = P(f.GetPosition()); d = math.radians((e["rot"] - f.GetOrientationDegrees()) % 360)
        c, s_ = math.cos(d), math.sin(d)
        # rotate about the footprint origin by d (KiCad sense), then put the origin at the spec pose
        g = affine_transform(g, [c, s_, -s_, c, pos[0] - c * pos[0] - s_ * pos[1], pos[1] + s_ * pos[0] - c * pos[1]])
        return affine_transform(g, [1, 0, 0, 1, e["at"][0] - pos[0], e["at"][1] - pos[1]])
    cyd = {r: (to_cell(court(fps[r]), fps[r], spec["footprints"][r]), spec["footprints"][r].get("side", "F")) for r in rigid}
    # target pours of the cell's nets: a cell pour that one of them covers at a pose is not new copper there
    pours = collections.defaultdict(list)
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() in private or z.GetNetname() not in nets: continue
        for l in z.GetLayerSet().CuStack():
            pours[(z.GetNetname(), b.GetLayerName(l))] += [Polygon(o).buffer(0) for o in outline_pts(z) if len(o) > 2]
    cu = []
    for z in spec.get("zones", []):
        if z["layer"] in ("F.Cu", "B.Cu"):
            cu.append((z["layer"], z["net"], Polygon(z["pts"]).buffer(0)))
    for t in spec.get("tracks", []):    # every layer: a buried sense route (VOS on In3) crosses the board's inner lanes too
        cu.append((t["layer"], t["net"], LineString(t["pts"]).buffer(t["w"] / 2)))
    vias = [(v["net"], Point(v["at"]).buffer(v.get("d", 0.6) / 2)) for v in spec.get("vias", [])]

    # obstacles on the target, without the cell's own parts and private copper
    side_of = lambda f: "B" if f.IsFlipped() else "F"
    obs = {"F": [], "B": []}; holes = []
    for f in b.GetFootprints():
        r = f.GetReference()
        if r in refs: continue
        obs[side_of(f)].append((r, court(f)))
        for p in f.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                holes.append((r, Point(P(p.GetPosition())).buffer(max(mm(p.GetSize().x), mm(p.GetSize().y)) / 2)))
    trk = {b.GetLayerName(l): [] for l in b.GetEnabledLayers().CuStack()}; ovias = []
    for t in b.GetTracks():
        if t.GetNetname() in private: continue
        if t.GetClass() == "PCB_VIA":
            ovias.append((t.GetNetname(), Point(P(t.GetPosition())).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2)))
        else:
            g = LineString([P(t.GetStart()), P(t.GetEnd())]).buffer(mm(t.GetWidth()) / 2)
            trk.setdefault(b.GetLayerName(t.GetLayer()), []).append((t.GetNetname(), g))
    keep_out = [sps(z.Outline()) for z in b.Zones() if z.GetIsRuleArea()]
    keep_out = [k for k in keep_out if k is not None]
    edge = None
    try:
        ps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ps); edge = sps(ps)
    except Exception:
        pass
    T = lambda items: (STRtree([g for _, g in items]) if items else None, items)
    TO = {k: T(v) for k, v in obs.items()}; TH = T(holes); TT = {k: T(v) for k, v in trk.items()}; TV = T(ovias)

    def hits(tree, g):
        t, its = tree
        return [] if t is None else [its[i] for i in t.query(g) if its[i][1].intersects(g)]

    x0, y0, x1, y1 = (float(v) for v in a.region.split(","))
    pref = tuple(float(v) for v in a.prefer.split(",")) if a.prefer else ((x0 + x1) / 2, (y0 + y1) / 2)
    rots = [float(r) for r in a.rots.split(",")]
    res = []
    n = 0
    X = x0
    while X <= x1 + 1e-9:
        Y = y0
        while Y <= y1 + 1e-9:
            for R in rots:
                t_ = math.radians(R); c, s_ = math.cos(t_), math.sin(t_); M = [c, s_, -s_, c, X, Y]
                parts, area, bad = set(), 0.0, []
                for r, (g, sd) in cyd.items():
                    G = affine_transform(g, M)
                    if edge is not None and not edge.buffer(-0.3).contains(G): bad.append(f"{r} off the board")
                    for (o, og) in hits(TO[sd], G):
                        if o in free_ok: continue
                        parts.add(o); area += og.intersection(G).area
                    for (o, og) in hits(TH, G):
                        parts.add(o + "(hole)")
                    for k in keep_out:
                        if k.intersects(G): bad.append(f"{r} in a keep-out")
                vh, th = set(), collections.Counter()
                for (ln, net, g) in cu:
                    G = affine_transform(g, M)
                    if any(pp.buffer(0.01).contains(G) for pp in pours.get((net, ln), [])): continue   # the board pours it already
                    th[ln] += sum(1 for (on, og) in hits(TT[ln], G) if on != net)
                    vh |= {id(og) for (on, og) in hits(TV, G) if on != net}
                for (net, g) in vias:
                    G = affine_transform(g, M)
                    for ln in TT: th[ln] += sum(1 for (on, og) in hits(TT[ln], G) if on != net)
                    vh |= {id(og) for (on, og) in hits(TV, G) if on != net}
                th = {k: v for k, v in th.items() if v}
                res.append(dict(at=(round(X, 2), round(Y, 2)), rot=R, parts=sorted(parts), area=round(area, 2), vias=len(vh), tracks=sum(th.values()), by_layer=th,
                                bad=bad, dist=round(math.dist((X, Y), pref), 2)))
                n += 1
            Y += a.step
        X += a.step
    ok = [r for r in res if not r["bad"]]
    ok.sort(key=lambda r: (len(r["parts"]), r["area"], r["vias"] + r["tracks"], r["dist"]))
    print(f"{n} poses tried, {len(ok)} on the board and clear of keep-outs; best {min(a.top, len(ok))}:")
    for r in ok[:a.top]:
        print(f"  at {r['at']} rot {r['rot']:>5}: {len(r['parts'])} parts in the way {r['parts']} ({r['area']} mm²), "
              f"{r['vias']} vias and {r['tracks']} tracks under cell copper ({', '.join(f'{k} {v}' for k, v in r['by_layer'].items()) or 'none'}), "
              f"{r['dist']} mm from the preferred spot")
    if a.json: json.dump(ok[:200], open(a.json, "w"), indent=1)


ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
e = sub.add_parser("extract"); e.add_argument("board"); e.add_argument("--refs", required=True); e.add_argument("--origin", required=True)
e.add_argument("--rot", type=float, default=0.0); e.add_argument("--margin", type=float, default=0.5); e.add_argument("-o", required=True)
e.add_argument("--local-layers", help="layers whose zones belong to the cell (default: the first part's side); zones on other layers are planes")
bd = sub.add_parser("build"); bd.add_argument("cell"); bd.add_argument("--source", required=True); bd.add_argument("-o", required=True)
bd.add_argument("--project")
pl = sub.add_parser("place"); pl.add_argument("cell"); pl.add_argument("--target", required=True); pl.add_argument("--at", required=True)
pl.add_argument("--rot", type=float, default=0.0); pl.add_argument("-o", required=True); pl.add_argument("--project")
pl.add_argument("--allow-locked", action="store_true")
ft = sub.add_parser("fit"); ft.add_argument("cell"); ft.add_argument("--target", required=True); ft.add_argument("--region", required=True)
ft.add_argument("--step", type=float, default=0.5); ft.add_argument("--rots", default="0,90,180,270"); ft.add_argument("--prefer")
ft.add_argument("--parts", help="the cell's rigid parts (default: all); the rest are re-seated after the fit")
ft.add_argument("--movable", help="board parts you are willing to move; they are not counted in the way")
ft.add_argument("--top", type=int, default=10); ft.add_argument("--json")
a = ap.parse_args()
{"extract": extract, "build": build, "place": place, "fit": fit}[a.cmd](a)
