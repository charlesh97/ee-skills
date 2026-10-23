#!/usr/bin/env python3
"""Stitch a net's pours to each other with a grid of through vias, all in one group.

Stitching is the LAST copper pass, after routing (layout rule L-43, draft). Every
via this script adds goes into one KiCad group (drc.json stitch.group, "GND
stitching"), so a re-route starts with `remove` (one action, or select the group
and delete it in KiCad) and ends with `add` again. The via size, pitch, net and
group come from rules/drc.json `stitch` for the chosen profile.

Run with KiCad's bundled python, which has pcbnew:
  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
Close the board in KiCad first, or KiCad writes its copy back over this one.

  $KPY stitch.py add <board.kicad_pcb> [--profile rigid|flex] [--pitch 2.0] [--net GND]
                     [--via 0.6,0.3] [--layers F.Cu,In1.Cu,In2.Cu,B.Cu] [--relaxed] [--plane In1.Cu]
                     [--replace | --append] [--grid-only] [--no-drc] [--kicad-cli PATH]
                     [--dry-run] [-o out.kicad_pcb]
      1. Refill every zone (the "before" fill areas).
      2. Refill the net's zones again with island removal off, so copper KiCad
         would delete as an unconnected island still counts as pour to stitch.
      3. Walk a staggered grid (rows --pitch apart, --pitch along a row, every
         other row shifted half a pitch; lattice anchored at the board origin, so
         re-running lands on the same points). A point takes a via when:
           - fill: by default the point is inside the net's fill on EVERY copper
             layer (of --layers) where a zone of the net covers the point, and on
             at least two layers. --relaxed: inside the fill on at least two layers,
             one of them the plane (--plane, default the layer where the net's fill
             is largest); in relaxed mode other nets' pours are not obstacles
             (KiCad refills them around the via), tracks and pads still are;
           - clearance: the via pad clears other-net copper (tracks, vias, pads,
             pours, copper graphics) on every layer by the larger of the two items'
             clearances and the board minimum; it stays off the net's own
             through-hole pads (stitching never goes in a pad) by the board
             minimum clearance (own-pad);
           - hole: the via hole clears other-net copper by the hole clearance, and
             every other hole by hole-to-hole (the larger of the board setting and
             the house floor in drc.json);
           - courtyard: the via pad is outside every footprint courtyard, both sides;
           - smd-pad / paste: the via pad clears every SMD pad's copper and every
             paste aperture (a pad's own opening with its paste margin, or the
             paste-only windows of an exposed pad) by the board minimum clearance,
             on both sides, whatever the pad's net: the stitch net's own SMD pads
             included. A via in a land or a paste opening wicks solder from the
             joint (L-43; a GND via in J1.MP of a JST GH, 2026-10-04). The DRC pass
             below does not catch it: a same-net via in a pad is legal to KiCad;
           - edge: inside the outline, pad at least the copper-to-edge clearance
             from Edge.Cuts;
           - keepout: not in a rule area that forbids vias on any copper layer.
      4. Island rescue (unless --grid-only): every fill island of at least
         stitch.min_island_mm2 still short of stitch.min_island_vias vias (existing
         vias and through-hole pads of the net count) is searched on a 0.2 mm raster
         with the same tests, farthest-first, vias at least a pitch apart. This
         reaches slivers between parts that the lattice steps over. What still has
         no legal point is counted, not forced: check_copper.py pour-island names it.
      5. Add the vias (net set, not locked) to the group, restore island removal,
         refill.
      6. Unless --no-drc, run kicad-cli DRC on a temporary copy (with the project's
         .kicad_pro and .kicad_dru beside it, so custom rules apply) and drop every
         new via DRC names in a violation (silk, text and footprint-library checks
         aside); refill and repeat until clean.
      7. Save (unless --dry-run) and print vias per zone and layer, fill area per
         layer before and after, the rescue count, and lattice points skipped by
         reason (the first test a point fails, in the order above).
      A second `add` refuses if the group already exists: --replace deletes the old
      group and its vias first, --append adds to it (its vias act as obstacles).

  $KPY stitch.py remove <board.kicad_pcb> [--profile ..] [-o out.kicad_pcb]
      Delete the group and every item in it, refill, save. Prints the count removed.

  $KPY stitch.py report <board.kicad_pcb> [--profile ..]
      Is the group there, how many vias in it, and how many free vias of the net at
      the stitch size sit outside it (likely stitching someone forgot to group;
      split into ungrouped and in-another-group). "Free" means no track ends on
      the via and it is not in a pad, so pin vias of the same size are left out.

Exit 1 on a refusal or error; 0 otherwise.
"""
import argparse
import collections
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, "..", "rules", "drc.json")
EPS = 5000             # 5 um of margin on every clearance, so rounding never lands on the limit
CELL = 2_000_000       # 2 mm spatial-index cell
DRC_IGNORE = ("silk_", "text_", "lib_", "courtyards_", "footprint_", "missing_courtyard", "malformed_courtyard")


def load_profile(name):
    d = json.load(open(RULES))
    return d["profiles"][name]


def mmv(v):
    return round(pcbnew.ToMM(v), 3)


def area_mm2(ps):
    return ps.Area() / 1e12


# ------------------------------------------------------------------ zones and fills
def net_zones(board, code):
    return [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == code]


def refill(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def fill_by_layer(board, code, layers):
    out = {}
    for layer in layers:
        u = pcbnew.SHAPE_POLY_SET()
        for z in net_zones(board, code):
            if z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer):
                u.BooleanAdd(z.GetFilledPolysList(layer))
        out[layer] = u
    return out


def fill_table(board, code, layers):
    """{layer name: (area mm2, islands)} for the net's merged fill."""
    return {board.GetLayerName(l): (round(area_mm2(u), 1), u.OutlineCount()) for l, u in fill_by_layer(board, code, layers).items()}


# ------------------------------------------------------------------ spatial index
class Index:
    def __init__(self):
        self.cells = collections.defaultdict(list)

    def add(self, bbox, entry):
        for cx in range(bbox.GetLeft() // CELL, bbox.GetRight() // CELL + 1):
            for cy in range(bbox.GetTop() // CELL, bbox.GetBottom() // CELL + 1):
                self.cells[(cx, cy)].append(entry)

    def near(self, x, y, r):
        seen = set()
        for cx in range((x - r) // CELL, (x + r) // CELL + 1):
            for cy in range((y - r) // CELL, (y + r) // CELL + 1):
                for e in self.cells.get((cx, cy), ()):
                    if id(e) not in seen:
                        seen.add(id(e))
                        yield e


def own_clearance(item, layer):
    try:
        return item.GetOwnClearance(layer)
    except Exception:
        return 0


# ------------------------------------------------------------------ SMD pads and paste apertures
SIDES = (("F", "F_Cu", "F_Paste"), ("B", "B_Cu", "B_Paste"))


def pad_poly(p, layer, margin=0, max_err=5000):
    """The pad's outline on a layer as a SHAPE_POLY_SET, grown (or shrunk) by margin nm."""
    ps = pcbnew.SHAPE_POLY_SET()
    p.TransformShapeToPolygon(ps, layer, 0, max_err, pcbnew.ERROR_INSIDE)
    if margin:
        ps.Inflate(int(margin), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, max_err)
    return ps


def smd_pad_areas(board):
    """Every SMD pad's copper and every paste aperture on the outer layers, all nets.

    Shared with check_copper.py (via-in-pad). Returns a list of dicts:
      kind   "copper" (an SMD or edge-connector pad's land) or "paste" (an opening in
             F.Paste/B.Paste: a pad's own, with its paste margin, or a paste-only pad
             such as an exposed pad's paste windows)
      side   "F" or "B"; cu: the copper layer id on that side
      poly, bbox, pad, ref
      name   REF.PAD; a paste-only window takes the number of the copper pad it sits on
      own_paste, windows   (copper entries) the pad has its own paste opening /
             paste-only windows of its footprint overlap it
    KiCad's paste-layer shape ignores the paste margin, so it is applied here
    (the smaller axis when the margin differs by axis)."""
    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for side, cu_name, paste_name in SIDES:
            cu, paste = getattr(pcbnew, cu_name), getattr(pcbnew, paste_name)
            lands, pastes = [], []
            for p in fp.Pads():
                if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN):
                    continue
                if p.IsOnLayer(cu):
                    lands.append(p)
                if p.IsOnLayer(paste):
                    m = p.GetSolderPasteMargin(paste)
                    pastes.append((p, pad_poly(p, paste, min(m.x, m.y))))
            land_polys = [(p, pad_poly(p, cu)) for p in lands]
            for p, poly in land_polys:
                windows = any(not q.IsOnLayer(cu) and _overlaps(poly, wp) for q, wp in pastes)
                out.append({"kind": "copper", "side": side, "cu": cu, "poly": poly, "bbox": poly.BBox(), "pad": p,
                            "ref": ref, "name": f"{ref}.{p.GetNumber() or '?'}", "own_paste": p.IsOnLayer(paste),
                            "windows": windows})
            for q, wp in pastes:
                if q.IsOnLayer(cu):
                    name = f"{ref}.{q.GetNumber() or '?'}"
                else:
                    host = [p for p, poly in land_polys if _overlaps(poly, wp)]
                    name = f"{ref}.{host[0].GetNumber()}" if host and host[0].GetNumber() else f"{ref}.(paste)"
                out.append({"kind": "paste", "side": side, "cu": cu, "poly": wp, "bbox": wp.BBox(), "pad": q,
                            "ref": ref, "name": name, "own_paste": True, "windows": False})
    return out


def _overlaps(a, b):
    x = pcbnew.SHAPE_POLY_SET(a)
    x.BooleanIntersection(b)
    return x.Area() > 0


# ------------------------------------------------------------------ add
def build_obstacles(board, code, cu, relaxed, floor_clr):
    """Per-layer copper obstacles (shape, clearance, kind), holes, courtyards, edges, keepouts."""
    copper = {l: Index() for l in cu}      # entries: (shape, own clearance, kind)
    holes = Index()                        # entries: (hole shape, same_net)
    for t in board.GetTracks():
        is_via = t.GetClass() == "PCB_VIA"
        if is_via:
            holes.add(t.GetBoundingBox(), (t.GetEffectiveHoleShape(), t.GetNetCode() == code))
        if t.GetNetCode() == code:
            continue
        for l in cu:
            if t.IsOnLayer(l):
                sh = t.GetEffectiveShape(l)
                copper[l].add(sh.BBox(), (sh, own_clearance(t, l), "copper"))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.HasHole():
                holes.add(p.GetBoundingBox(), (p.GetEffectiveHoleShape(), p.GetNetCode() == code and p.GetNetCode() > 0))
            same = p.GetNetCode() == code and code > 0
            for l in cu:
                if p.IsOnLayer(l) and p.IsOnCopperLayer() and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    sh = p.GetEffectiveShape(l)
                    copper[l].add(sh.BBox(), (sh, floor_clr if same else own_clearance(p, l), "own-pad" if same else "copper"))
        for g in fp.GraphicalItems():
            if g.GetLayer() in cu:
                sh = g.GetEffectiveShape(g.GetLayer())
                copper[g.GetLayer()].add(sh.BBox(), (sh, floor_clr, "copper"))
    for d in board.GetDrawings():
        if d.GetLayer() in cu:
            sh = d.GetEffectiveShape(d.GetLayer())
            copper[d.GetLayer()].add(sh.BBox(), (sh, floor_clr, "copper"))
    other_fills = {l: [] for l in cu}
    if not relaxed:
        for z in board.Zones():
            if z.GetIsRuleArea() or z.GetNetCode() == code:
                continue
            for l in cu:
                if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
                    f = z.GetFilledPolysList(l)
                    if f.OutlineCount():
                        other_fills[l].append((f, f.BBox(), own_clearance(z, l)))
    courtyards = []
    for fp in board.GetFootprints():
        for side in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = fp.GetCourtyard(side)
            if c.OutlineCount():
                courtyards.append((c, c.BBox(), fp.GetReference()))
    edges = [d.GetEffectiveShape() for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    for fp in board.GetFootprints():
        edges += [g.GetEffectiveShape() for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.Edge_Cuts]
    keepouts = []
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowVias() and any(z.IsOnLayer(l) for l in cu):
            keepouts.append((z.Outline(), z.Outline().BBox()))
    return copper, holes, other_fills, courtyards, edges, keepouts


def grid_points(bbox, pitch):
    """Staggered lattice anchored at (0,0): rows pitch apart, every even row shifted half a pitch."""
    j0, j1 = math.floor(bbox.GetTop() / pitch), math.ceil(bbox.GetBottom() / pitch)
    for j in range(j0, j1 + 1):
        off = pitch / 2 if j % 2 == 0 else 0
        i0, i1 = math.floor((bbox.GetLeft() - off) / pitch), math.ceil((bbox.GetRight() - off) / pitch)
        for i in range(i0, i1 + 1):
            yield int(round(i * pitch + off)), int(round(j * pitch))


def find_group(board, name):
    return [g for g in board.Groups() if g.GetName() == name]


def delete_group(board, g):
    """Delete a group and its members. BOARD.Delete, not Remove: Remove leaves the
    items to Python's garbage collector, which crashes pcbnew later (KiCad 10)."""
    items = list(g.GetItems())
    n = sum(1 for i in items if i.GetClass() == "PCB_VIA")
    for i in items:
        board.Delete(i)
    board.Delete(g)
    return n, len(items)


def kicad_cli(explicit=None):
    if explicit:
        return explicit
    w = shutil.which("kicad-cli")
    if w:
        return w
    # KiCad.app/Contents/Frameworks/Python.framework/Versions/X/bin/python3 -> KiCad.app/Contents/MacOS/kicad-cli
    p = os.path.realpath(sys.executable)
    while p != "/" and not p.endswith(".app/Contents"):
        p = os.path.dirname(p)
    c = os.path.join(p, "MacOS", "kicad-cli")
    return c if os.path.exists(c) else None


def drc_offenders(board, board_path, cli, ours):
    """Save to a temp copy (project files beside it), run kicad-cli DRC, return {via uuid: [types]}."""
    tmp = tempfile.mkdtemp(prefix="stitch_drc_")
    base = os.path.splitext(os.path.basename(board_path))[0]
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.splitext(board_path)[0] + ext
        if os.path.exists(src):
            shutil.copy(src, os.path.join(tmp, base + ext))
    pcb = os.path.join(tmp, base + ".kicad_pcb")
    pcbnew.SaveBoard(pcb, board, True)
    out = os.path.join(tmp, "drc.json")
    subprocess.run([cli, "pcb", "drc", "--format", "json", "--severity-all", "-o", out, pcb],
                   capture_output=True, text=True)
    hits = collections.defaultdict(list)
    try:
        rep = json.load(open(out))
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"kicad-cli DRC produced no report: {e}")
    for v in rep.get("violations", []):
        if v["type"].startswith(DRC_IGNORE):
            continue
        for it in v.get("items", []):
            if it.get("uuid") in ours:
                hits[it["uuid"]].append(v["type"])
    shutil.rmtree(tmp, ignore_errors=True)
    return hits


def cmd_add(args, prof):
    st = prof["stitch"]
    board = pcbnew.LoadBoard(args.board)
    net = board.FindNet(args.net)
    if net is None or net.GetNetCode() <= 0:
        sys.exit(f"net {args.net!r} not on the board")
    code = net.GetNetCode()
    cu_all = list(board.GetEnabledLayers().CuStack())
    layers = [board.GetLayerID(l) for l in args.layers.split(",")] if args.layers else cu_all
    zones = net_zones(board, code)
    if not zones:
        sys.exit(f"no {args.net} zones: nothing to stitch")
    groups = find_group(board, args.group)
    group, replaced = None, 0
    if groups:
        if args.replace:
            for g in groups:
                replaced += delete_group(board, g)[0]
        elif args.append:
            group = groups[0]
        else:
            sys.exit(f"group '{args.group}' already exists ({len(list(groups[0].GetItems()))} items): "
                     f"use --replace to regenerate it, --append to add to it, or `stitch.py remove` first")

    refill(board)
    before = fill_table(board, code, layers)

    # fill with island removal off: an unconnected island is still pour to stitch
    modes = {id(z): z.GetIslandRemovalMode() for z in zones}
    for z in zones:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    refill(board)
    fills = fill_by_layer(board, code, layers)
    if args.plane:
        plane = board.GetLayerID(args.plane)
    else:
        plane = max(fills, key=lambda l: area_mm2(fills[l]))
    outlines = {l: [z.Outline() for z in zones if z.IsOnLayer(l)] for l in layers}

    ds = board.GetDesignSettings()
    floor_clr = ds.m_MinClearance
    hole_clr = max(ds.m_HoleClearance, pcbnew.FromMM(prof["floors"]["min_hole_clearance"]))
    h2h = max(ds.m_HoleToHoleMin, pcbnew.FromMM(prof["floors"]["min_hole_to_hole"]))
    edge_clr = max(ds.m_CopperEdgeClearance, pcbnew.FromMM(prof["floors"]["min_copper_edge_clearance"]))
    dia, drill = (pcbnew.FromMM(x) for x in args.via)
    R, Rh = dia // 2, drill // 2

    proto = pcbnew.PCB_VIA(board)
    proto.SetNet(net)
    proto.SetWidth(dia)
    proto.SetDrill(drill)
    via_clr = max(floor_clr, own_clearance(proto, pcbnew.F_Cu))

    copper, holes, other_fills, courtyards, edges, keepouts = build_obstacles(board, code, cu_all, args.relaxed, floor_clr)
    smd_areas = smd_pad_areas(board)
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    bbox = outline.BBox()
    reach = R + max([via_clr, hole_clr, h2h, edge_clr]) + pcbnew.FromMM(1.0)

    skipped = collections.Counter()
    placed = []
    near_placed = collections.defaultdict(list)       # 1 mm cell -> placed points
    MMC = pcbnew.FromMM(1.0)
    gap = 2 * Rh + h2h + EPS

    def why_not(x, y):
        """None if a via fits at (x, y), else the first reason it doesn't."""
        P = pcbnew.VECTOR2I(x, y)
        infill = [l for l in layers if fills[l].Contains(P)]
        if args.relaxed:
            ok = len(infill) >= 2 and plane in infill
        else:
            covered = [l for l in layers if any(o.Contains(P) for o in outlines[l])]
            ok = len(infill) >= 2 and all(l in infill for l in covered)
        if not ok:
            return "fill"
        # A via is a circle of radius R (pad) / Rh (hole) at P, so "the via is within c of
        # a shape" is "P is within R + c of it": every test below is a point test.
        if any(e.Collide(P, R + edge_clr + EPS) for e in edges):
            return "edge"
        if any(bb.Distance(P) <= R and o.Collide(P, R) for o, bb in keepouts):
            return "keepout"
        if any(bb.Distance(P) <= R and c.Collide(P, R) for c, bb, _ in courtyards):
            return "courtyard"
        # SMD pads and paste apertures, every net, the stitch net included: a via in a land or a
        # paste opening wicks solder out of the joint (L-43; J1.MP on two encoder boards, 2026-10-04)
        for a in smd_areas:
            if a["bbox"].Distance(P) <= R + floor_clr + EPS and a["poly"].Collide(P, R + floor_clr + EPS):
                return "paste" if a["kind"] == "paste" else "smd-pad"
        # holes: hole-to-hole for every hole, copper-to-hole for other-net and non-plated holes
        for hs, same in holes.near(x, y, reach):
            if hs.Collide(P, Rh + h2h + EPS) or (not same and hs.Collide(P, R + hole_clr + EPS)):
                return "hole"
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for px, py in near_placed.get((x // MMC + i, y // MMC + j), ()):
                    if math.hypot(px - x, py - y) < gap:
                        return "hole"
        for l in cu_all:
            for sh, clr, kind in copper[l].near(x, y, reach):
                if kind == "own-pad":
                    if sh.Collide(P, R + floor_clr + EPS):
                        return "own-pad"
                elif sh.Collide(P, R + max(clr, via_clr) + EPS):
                    return "clearance"
                elif sh.Collide(P, Rh + hole_clr + EPS):
                    return "hole"
            for f, bb, clr in other_fills[l]:
                if bb.Distance(P) <= reach and f.Collide(P, R + max(clr, via_clr) + EPS):
                    return "clearance"
        return None

    def put(x, y):
        placed.append((x, y))
        near_placed[(x // MMC, y // MMC)].append((x, y))

    for x, y in grid_points(bbox, pcbnew.FromMM(args.pitch)):
        if not outline.Contains(pcbnew.VECTOR2I(x, y)):
            continue                                   # off the board: not a skip
        why = why_not(x, y)
        if why:
            skipped[why] += 1
        else:
            put(x, y)

    # island rescue: an island the lattice missed (a sliver between parts, a pocket
    # under a connector) gets vias from a finer search inside it, same tests
    rescued = collections.Counter()
    unrescued = collections.Counter()
    if not args.grid_only:
        min_a, min_n = st["min_island_mm2"], st["min_island_vias"]
        anchors = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == code]
        anchors += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads()
                    if p.GetNetCode() == code and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
        step = pcbnew.FromMM(0.2)
        spread = pcbnew.FromMM(args.pitch)
        for l in layers:
            f = fills[l]
            for i in range(f.OutlineCount()):
                a = (f.Outline(i).Area() - sum(f.CHole(i, h).Area() for h in range(f.HoleCount(i)))) / 1e12
                if a < min_a:
                    continue
                have = [(q.x, q.y) for q in anchors if f.Contains(q, i)] + \
                       [(x, y) for x, y in placed if f.Contains(pcbnew.VECTOR2I(x, y), i)]
                if len(have) >= min_n:
                    continue
                bb = f.Outline(i).BBox()
                st_ = max(step, int(math.sqrt(bb.GetWidth() * bb.GetHeight() / 20000)))
                cand = [(x, y) for x in range(bb.GetLeft(), bb.GetRight() + 1, st_)
                        for y in range(bb.GetTop(), bb.GetBottom() + 1, st_) if f.Contains(pcbnew.VECTOR2I(x, y), i)]
                # farthest from what the island already has first, so the vias spread out
                got = 0
                while len(have) < min_n and cand:
                    if have:
                        cand.sort(key=lambda c: -min(math.hypot(c[0] - hx, c[1] - hy) for hx, hy in have))
                    for k, (x, y) in enumerate(cand):
                        if have and min(math.hypot(x - hx, y - hy) for hx, hy in have) < min(spread, gap * 2):
                            cand = []
                            break
                        if not why_not(x, y):
                            put(x, y)
                            have.append((x, y))
                            got += 1
                            cand = cand[k + 1:]
                            break
                    else:
                        cand = []
                if got:
                    rescued[board.GetLayerName(l)] += got
                if len(have) < min_n:
                    unrescued[board.GetLayerName(l)] += 1

    # place
    if group is None:
        group = pcbnew.PCB_GROUP(board)
        group.SetName(args.group)
        board.Add(group)
    vias = []
    for x, y in placed:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(x, y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(dia)
        v.SetDrill(drill)
        v.SetNet(net)
        v.SetLocked(False)
        board.Add(v)
        group.AddItem(v)
        vias.append(v)
    for z in zones:
        z.SetIslandRemovalMode(modes[id(z)])
    refill(board)

    # verify with KiCad's own DRC, custom rules included
    dropped = collections.Counter()
    drc_note = "skipped (--no-drc)"
    if not args.no_drc and vias:
        cli = kicad_cli(args.kicad_cli)
        if not cli:
            sys.exit("kicad-cli not found: pass --kicad-cli, or --no-drc to skip the DRC pass")
        for rnd in range(5):
            ours = {v.m_Uuid.AsString(): v for v in vias}
            hits = drc_offenders(board, args.board, cli, ours)
            if not hits:
                break
            for u, types in hits.items():
                v = ours[u]
                for t in set(types):
                    dropped[t] += 1
                vias.remove(v)
                board.Delete(v)
            refill(board)
        drc_note = "clean" if not hits else f"dropped {len(hits)} more vias in round 5, not re-checked"
        for t, n in dropped.items():
            skipped[f"drc:{t}"] += n

    after = fill_table(board, code, layers)
    per_zone = collections.Counter()
    for v in vias:
        for z in zones:
            for l in layers:
                if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l) and z.GetFilledPolysList(l).Contains(v.GetPosition()):
                    per_zone[(board.GetLayerName(l), z.GetZoneName() or "(unnamed)")] += 1

    print(f"{'would add' if args.dry_run else 'added'} {len(vias)} {args.net} stitching vias "
          f"{args.via[0]}/{args.via[1]} at a {args.pitch} mm staggered pitch to group '{args.group}'"
          + (f" (replaced {replaced})" if replaced else "") + (" (appended)" if args.append and groups else ""))
    print(f"mode: {'relaxed (>= 2 layers incl. plane ' + board.GetLayerName(plane) + ')' if args.relaxed else 'strict (every layer with a zone there)'}; "
          f"clearance {mmv(via_clr)}+, hole clearance {mmv(hole_clr)}, hole-to-hole {mmv(h2h)}, edge {mmv(edge_clr)} mm; DRC pass: {drc_note}")
    print("\nvias per zone (a via counts once per layer it lands in fill)")
    for (ln, zn), n in sorted(per_zone.items()):
        print(f"  {ln:7} {zn:28} {n}")
    print("\nfill per layer, mm2 (islands): before -> after")
    for ln in before:
        print(f"  {ln:7} {before[ln][0]:8.1f} ({before[ln][1]:3}) -> {after[ln][0]:8.1f} ({after[ln][1]:3})")
    if not args.grid_only:
        print(f"\nisland rescue (islands >= {st['min_island_mm2']} mm2 with < {st['min_island_vias']} vias): "
              f"{sum(rescued.values())} vias added off the lattice "
              f"({', '.join(f'{k} {v}' for k, v in sorted(rescued.items())) or 'none'}); "
              f"{sum(unrescued.values())} islands still short "
              f"({', '.join(f'{k} {v}' for k, v in sorted(unrescued.items())) or 'none'}) with no legal point; "
              f"counted with island removal off, so this includes islands KiCad deletes on the final fill")
    print("\ngrid points skipped, by reason")
    for k in ("fill", "edge", "keepout", "courtyard", "smd-pad", "paste", "own-pad", "clearance", "hole"):
        print(f"  {k:12} {skipped.get(k, 0)}")
    for k, n in sorted(skipped.items()):
        if k.startswith("drc:"):
            print(f"  {k:12} {n}  (placed, then dropped: KiCad DRC flagged it)")
    if not args.dry_run:
        dest = args.output or args.board
        pcbnew.SaveBoard(dest, board, True)
        print(f"\nsaved {dest}")
    else:
        print("\ndry run: nothing saved")


# ------------------------------------------------------------------ remove / report
def cmd_remove(args, prof):
    board = pcbnew.LoadBoard(args.board)
    groups = find_group(board, args.group)
    if not groups:
        print(f"no group '{args.group}': nothing removed")
        return
    nv = ni = 0
    for g in groups:
        a, b = delete_group(board, g)
        nv += a
        ni += b
    refill(board)
    dest = args.output or args.board
    pcbnew.SaveBoard(dest, board, True)
    print(f"removed group '{args.group}': {ni} items ({nv} vias); refilled and saved {dest}")


def free_stitch_vias(board, code, dia, drill):
    """Vias of the net at the stitch size with no track ending on them and not in a pad."""
    ends = collections.defaultdict(list)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == code:
            ends[code].append(t)
    pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
    out = []
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA" or v.GetNetCode() != code:
            continue
        if abs(v.GetWidth(pcbnew.F_Cu) - dia) > 1000 or abs(v.GetDrill() - drill) > 1000:
            continue
        c = v.GetPosition()
        r = v.GetWidth(pcbnew.F_Cu) / 2
        if any(math.hypot(e.x - c.x, e.y - c.y) <= r for t in ends[code] for e in (t.GetStart(), t.GetEnd())):
            continue
        if any(p.HitTest(c) for p in pads):
            continue
        out.append(v)
    return out


def stitch_status(board, prof, net_name=None, group_name=None, via=None):
    """Shared with check_copper.py: the group, its via count, and stitch-size vias outside it."""
    st = prof["stitch"]
    net_name = net_name or st["net"]
    group_name = group_name or st["group"]
    dia, drill = (pcbnew.FromMM(x) for x in (via or st["via"]))
    net = board.FindNet(net_name)
    code = net.GetNetCode() if net else -1
    groups = find_group(board, group_name)
    in_group = set()
    for g in groups:
        for i in g.GetItems():
            in_group.add(i.m_Uuid.AsString())
    outside = collections.Counter()
    where = []
    for v in free_stitch_vias(board, code, dia, drill) if code > 0 else []:
        if v.m_Uuid.AsString() in in_group:
            continue
        pg = v.GetParentGroup()
        outside[pg.GetName() if pg else ""] += 1
        where.append(v)
    nvia = sum(1 for g in groups for i in g.GetItems() if i.GetClass() == "PCB_VIA")
    has_pours = code > 0 and bool(net_zones(board, code))
    return {"net": net_name, "group": group_name, "group_present": bool(groups), "group_vias": nvia,
            "outside": dict(outside), "outside_vias": where, "has_pours": has_pours,
            "via": [mmv(dia), mmv(drill)]}


def cmd_report(args, prof):
    board = pcbnew.LoadBoard(args.board)
    s = stitch_status(board, prof, args.net, args.group, args.via)
    print(f"group '{s['group']}': {'present, ' + str(s['group_vias']) + ' vias' if s['group_present'] else 'absent'}")
    n = sum(s["outside"].values())
    print(f"free {s['net']} vias at the stitch size {s['via'][0]}/{s['via'][1]} outside the group: {n}")
    for g, k in sorted(s["outside"].items()):
        print(f"  {k:5}  {'ungrouped' if not g else 'in group ' + repr(g)}")
    if n:
        print("  if these are stitching, fold them into the group so `remove` clears them before a re-route")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("board")
    common.add_argument("--profile", default="rigid", choices=["rigid", "flex"])
    common.add_argument("--net", help="stitch net (default drc.json stitch.net)")
    common.add_argument("--group", help="group name (default drc.json stitch.group)")
    common.add_argument("--via", help="via diameter,drill in mm (default drc.json stitch.via)")
    a = sub.add_parser("add", parents=[common])
    a.add_argument("--pitch", type=float, help="grid pitch, mm (default drc.json stitch.area_pitch_mm)")
    a.add_argument("--layers", help="comma list of copper layers the fill test uses (default all)")
    a.add_argument("--relaxed", action="store_true", help="fill on >= 2 layers, one the plane, instead of every layer")
    a.add_argument("--plane", help="plane layer for --relaxed (default: the layer with the net's largest fill)")
    m = a.add_mutually_exclusive_group()
    m.add_argument("--replace", action="store_true", help="delete an existing group and its vias first")
    m.add_argument("--append", action="store_true", help="add to an existing group")
    a.add_argument("--grid-only", action="store_true",
                   help="lattice only: skip the island rescue that adds off-lattice vias to under-stitched islands")
    a.add_argument("--no-drc", action="store_true", help="skip the kicad-cli DRC pass")
    a.add_argument("--kicad-cli", help="path to kicad-cli (default: PATH, then beside KiCad's python)")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("-o", "--output", help="save here instead of over the board")
    r = sub.add_parser("remove", parents=[common])
    r.add_argument("-o", "--output", help="save here instead of over the board")
    sub.add_parser("report", parents=[common])
    args = ap.parse_args()

    prof = load_profile(args.profile)
    st = prof["stitch"]
    args.net = args.net or st["net"]
    args.group = args.group or st["group"]
    args.via = [float(x) for x in args.via.split(",")] if args.via else list(st["via"])
    if args.cmd == "add":
        args.pitch = args.pitch or st["area_pitch_mm"]
        # L-43: area_pitch_mm is the default; coarser up to area_pitch_max_mm on a small, slow
        # board; finer only for a high-speed or RF return path. Either way the spec says why.
        pmax = st.get("area_pitch_max_mm", st["area_pitch_mm"])
        if args.pitch < st["area_pitch_mm"] - 1e-6:
            print(f"NOTE: pitch {args.pitch} mm is finer than the house {st['area_pitch_mm']} mm (L-43): only for a "
                  "high-speed or RF return path, and the routing spec must say which and why")
        elif args.pitch > pmax + 1e-6:
            print(f"NOTE: pitch {args.pitch} mm is coarser than the house maximum {pmax} mm (L-43): say why in the routing spec")
        if not st.get("stagger", True):
            sys.exit("drc.json stitch.stagger false: only the staggered grid is implemented")
        cmd_add(args, prof)
    elif args.cmd == "remove":
        cmd_remove(args, prof)
    else:
        cmd_report(args, prof)


if __name__ == "__main__":
    main()
