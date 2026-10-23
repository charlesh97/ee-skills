#!/usr/bin/env python3
"""Regulator cell check: measure each switching regulator on a KiCad 10 board against the dcdc-layout limits.

Read only. The board is loaded, its zones are refilled in memory, and nothing is saved.

usage:  $KPY check_regulator.py BOARD SPEC.json [--json OUT.json] [--render OUTDIR]

SPEC.json is a list of regulators (see ../references/cell-check.md for every field):
  [{"name": "U2 12V->5V", "ic": "U2",
    "hot_loop": ["C116.1", "U2.6", "U2.5", "C116.2"],      # pads in loop order, closing back to the first
    "hf_cap": "C116", "bulk_caps": ["C115"], "out_caps": ["C4"], "inductor": "L1",
    "sw_net": "SW_5V", "gnd_net": "GND", "plane_layer": "In1.Cu",
    "sense_pins": ["U2.3"], "strap_nets": ["VSET_5V"],
    "rail_entries": ["R113.2"], "ep": null, "vippo": false, "crop": [x0, y0, x1, y1]}]

Each check prints PASS, WARN or FAIL with its number; the exit status is 1 if any check fails.
"""
import sys, os, json, math, heapq, argparse, collections
import pcbnew
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

LIMITS = {                       # defaults; a spec entry may override any of them under "limits"
    "loop_area_mm2": 2.0,        # HF loop, plan + vertical (L-11)
    "hf_cap_edge_mm": 1.0,       # HF cap pad edge to its pin (L-11)
    "sense_clear_mm": 1.0,       # sense and strap copper to SW copper, past the escape (L-28)
    "sense_escape_mm": 1.0,      # length of pin escape exempt from sense_clear_mm (L-28)
    "sense_run_tol_mm": 0.5,     # tolerated run inside sense_clear_mm beyond the escape
    "plane_cover_pct": 100.0,    # plane under SW copper on plane_layer (L-23)
    "sw_vias": 0,                # vias on the SW net (L-28, L-29)
    "entry_vias": 2,             # vias at each rail entry or exit pad (L-21)
}

ap = argparse.ArgumentParser()
ap.add_argument("board"); ap.add_argument("spec")
ap.add_argument("--json"); ap.add_argument("--render")
ap.add_argument("--window", help="X0,Y0,X1,Y1: measure only copper inside this box (default: the spec's parts plus --margin)")
ap.add_argument("--margin", type=float, default=10.0, help="mm round the spec's parts for the default window")
ap.add_argument("--no-window", action="store_true", help="measure the whole board (slow on a big ground pour)")
a = ap.parse_args()
SPEC = json.load(open(a.spec))
mm = pcbnew.ToMM
b = pcbnew.LoadBoard(a.board)
# The window. A full board's ground pour makes the ground path search slow (minutes), and nothing a cell check
# measures lies far from the cell, so by default only copper near the spec's parts is read. A sense route or a
# rail entry that leaves the window is reported, so the window can be widened.
WIN = None
if not a.no_window:
    if a.window:
        WIN = box(*[float(v) for v in a.window.split(",")])
    else:
        refs = set()
        for sp_ in SPEC:
            refs |= {sp_["ic"], sp_["hf_cap"], sp_["inductor"]} | set(sp_.get("bulk_caps", [])) | set(sp_.get("out_caps", []))
            refs |= {x.split(".")[0] for x in sp_.get("hot_loop", []) + sp_.get("sense_pins", []) + sp_.get("rail_entries", [])}
        xs, ys = [], []
        for f in b.GetFootprints():
            if f.GetReference() in refs:
                bb = f.GetBoundingBox(False); xs += [mm(bb.GetLeft()), mm(bb.GetRight())]; ys += [mm(bb.GetTop()), mm(bb.GetBottom())]
        if xs:
            WIN = box(min(xs) - a.margin, min(ys) - a.margin, max(xs) + a.margin, max(ys) + a.margin)
inwin = (lambda g: True) if WIN is None else (lambda g: g.intersects(WIN))
zs = [z for z in b.Zones() if not z.GetIsRuleArea()]
pcbnew.ZONE_FILLER(b).Fill(zs)
CU = list(b.GetEnabledLayers().CuStack())
LN = {l: b.GetLayerName(l) for l in CU}
ORDER = [LN[l] for l in CU]

# copper depth of each layer below the top, from the stackup in the file (for the vertical part of a loop)
def stack_depths():
    txt = open(a.board, encoding="utf-8").read()
    i = txt.find("(stackup")
    depth, out, cur = 0.0, {}, None
    if i < 0:
        return {n: k * 1.6 / max(1, len(ORDER) - 1) for k, n in enumerate(ORDER)}
    j = txt.find("(copper_finish", i); seg = txt[i:j if j > 0 else i + 20000]
    import re
    for m in re.finditer(r'\(layer "([^"]+)"(.*?)\(thickness ([0-9.]+)\)', seg, re.S):
        name, th = m.group(1), float(m.group(3))
        if name in ORDER:
            out[name] = depth; depth += th
        elif name.startswith("dielectric"):
            depth += th
    for n in ORDER: out.setdefault(n, 0.0)
    return out
ZD = stack_depths()

def sps(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); pts = [(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]
        if len(pts) < 3: continue
        holes = [[(mm(h.CPoint(k).x), mm(h.CPoint(k).y)) for k in range(h.PointCount())]
                 for h in (ps.Hole(i, n) for n in range(ps.HoleCount(i)))]
        out.append(Polygon(pts, holes).buffer(0))
    return out

def padgeom(p, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    p.TransformShapeToPolygon(ps, layer, 0, pcbnew.pcbIUScale.mmToIU(0.005), pcbnew.ERROR_INSIDE)
    g = sps(ps); return unary_union(g) if g else None

items = collections.defaultdict(list); PADS = {}; PADOBJ = {}
fps = {f.GetReference(): f for f in b.GetFootprints()}
for f in b.GetFootprints():
    if WIN is not None:
        bb = f.GetBoundingBox(False)
        if not box(mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())).intersects(WIN): continue
    for p in f.Pads():
        lab = f"{f.GetReference()}.{p.GetNumber()}"; PADOBJ[lab] = p
        for l in CU:
            if p.IsOnLayer(l):
                g = padgeom(p, l)
                if g is None or g.is_empty: continue
                items[LN[l]].append(dict(net=p.GetNetname(), kind="pad", geom=g, ref=lab))
                PADS.setdefault(lab, {})[LN[l]] = g
TR = []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        c = (mm(t.GetPosition().x), mm(t.GetPosition().y)); w = mm(t.GetWidth(pcbnew.F_Cu))
        top, bot = CU.index(t.TopLayer()), CU.index(t.BottomLayer())
        d = dict(net=t.GetNetname(), kind="via", geom=Point(c).buffer(w / 2, 16), c=c, w=w, drill=mm(t.GetDrillValue()),
                 layers=[LN[l] for l in CU[top:bot + 1]])
        if not inwin(d["geom"]): continue
        for ln in d["layers"]: items[ln].append(d)
    else:
        s, e = t.GetStart(), t.GetEnd(); w = mm(t.GetWidth())
        ls = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))])
        d = dict(net=t.GetNetname(), kind="track", geom=ls.buffer(w / 2, 8), line=ls, w=w, layer=b.GetLayerName(t.GetLayer()), length=ls.length)
        if not inwin(d["geom"]): continue
        items[d["layer"]].append(d)
    TR.append(d)
for z in zs:
    for l in CU:
        if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
            for g in sps(z.GetFilledPolysList(l)):
                if WIN is not None:
                    if not g.intersects(WIN): continue
                    g = g.intersection(WIN)
                    if g.is_empty: continue
                for gg in (g.geoms if hasattr(g, "geoms") else [g]):
                    if gg.geom_type == "Polygon":
                        items[LN[l]].append(dict(net=z.GetNetname(), kind="zone", geom=gg, zname=z.GetZoneName(), layer=LN[l]))
TREE = {ln: STRtree([d["geom"] for d in items[ln]]) for ln in items}

def q(ln, geom, net=None, kinds=None):
    if ln not in TREE: return []
    return [items[ln][i] for i in TREE[ln].query(geom)
            if (net is None or items[ln][i]["net"] == net) and (not kinds or items[ln][i]["kind"] in kinds)
            and items[ln][i]["geom"].intersects(geom)]

_COMPS = {}
def comps(net, ln):
    if (net, ln) not in _COMPS:
        g = unary_union([d["geom"] for d in items[ln] if d["net"] == net])
        _COMPS[(net, ln)] = list(g.geoms) if hasattr(g, "geoms") else ([g] if not g.is_empty else [])
    return _COMPS[(net, ln)]

def comp_of(net, ln, geom):
    return next((c for c in comps(net, ln) if c.intersects(geom)), None)

def side(lab):
    return "B.Cu" if "B.Cu" in PADS[lab] and "F.Cu" not in PADS[lab] else "F.Cu"

def pad(lab, ln=None): return PADS[lab][ln or side(lab)]
def ctr(lab):
    c = pad(lab).centroid; return (c.x, c.y)
def netof(lab): return PADOBJ[lab].GetNetname()

def via_planes(v):
    return [ln for ln in v["layers"] if any(d["kind"] == "zone" and d["net"] == v["net"] for d in q(ln, Point(v["c"])))]

_ADJ = {}
def fpath(net, alab, blab_or_pt, ln):
    """Centre-line path over one net's tracks on one layer (pads and vias join track ends; pour bridges up to 0.6 mm)."""
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    adj = _ADJ.get((net, ln))
    if adj is None:
        adj = collections.defaultdict(list)
        for d in items[ln]:
            if d["net"] == net and d["kind"] == "track":
                p0, p1 = key(d["line"].coords[0]), key(d["line"].coords[-1])
                adj[p0].append((p1, d["length"])); adj[p1].append((p0, d["length"]))
        ends = list(adj)
        if ends:
            et = STRtree([Point(n) for n in ends])
            for d in items[ln]:
                if d["net"] == net and d["kind"] in ("pad", "via"):
                    pc = key((d["geom"].centroid.x, d["geom"].centroid.y)); gb = d["geom"].buffer(0.15)
                    for i in et.query(gb):
                        n = ends[i]
                        if n != pc and gb.contains(Point(n)):
                            w = math.dist(n, pc); adj[n].append((pc, w)); adj[pc].append((n, w))
        _ADJ[(net, ln)] = adj
    A = pad(alab, ln); apt = (A.centroid.x, A.centroid.y)
    if isinstance(blab_or_pt, str): Bg = pad(blab_or_pt, ln); bpt = (Bg.centroid.x, Bg.centroid.y)
    else: bpt = tuple(blab_or_pt); Bg = Point(bpt).buffer(0.35)
    starts = {n for n in adj if A.distance(Point(n)) < 0.6}; goals = {n for n in adj if Bg.distance(Point(n)) < 0.6}
    dist = {n: 0.0 for n in starts}; prev = {}; hq = [(0.0, n) for n in starts]
    while hq:
        dd, n = heapq.heappop(hq)
        if n in goals:
            path = [n]
            while path[-1] in prev: path.append(prev[path[-1]])
            return [apt] + path[::-1] + [bpt]
        if dd > dist.get(n, 1e9): continue
        for m, w in adj[n]:
            if dd + w < dist.get(m, 1e9): dist[m] = dd + w; prev[m] = n; heapq.heappush(hq, (dd + w, m))
    return [apt, bpt]

def link(net, alab, blab):
    """How two pads of one net connect: on their own layer, or through which vias and plane."""
    la, lb = side(alab), side(blab)
    ca, cb = comp_of(net, la, pad(alab)), comp_of(net, lb, pad(blab))
    if la == lb and ca is not None and cb is not None and ca.equals(cb):
        return dict(how=la, path=fpath(net, alab, blab, la), vert=0.0)
    va = [v for v in TR if v["kind"] == "via" and v["net"] == net and ca is not None and ca.intersects(v["geom"])]
    vb = [v for v in TR if v["kind"] == "via" and v["net"] == net and cb is not None and cb.intersects(v["geom"])]
    best = None
    for ln in ORDER:
        if ln == la: continue
        for c in comps(net, ln):
            A_ = [v for v in va if c.intersects(v["geom"])]; B_ = [v for v in vb if c.intersects(v["geom"])]
            if A_ and B_:
                x = min(A_, key=lambda v: math.dist(v["c"], ctr(alab))); y = min(B_, key=lambda v: math.dist(v["c"], ctr(blab)))
                path = fpath(net, alab, x["c"], la) + fpath(net, blab, y["c"], lb)[::-1]
                vert = math.dist(x["c"], y["c"]) * abs(ZD[ln] - ZD[la])
                L = sum(math.dist(path[i], path[i + 1]) for i in range(len(path) - 1))
                if best is None or L < best["len"]: best = dict(how=f"via -> {ln} -> via", path=path, vert=vert, len=L)
    return best or dict(how="NOT CONNECTED", path=[ctr(alab), ctr(blab)], vert=0.0)

def shoelace(pts):
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2

def courtyard(ref):
    f = fps[ref]; g = sps(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd))
    return unary_union(g) if g else None

def trace(start, net):
    """Track/via tree from a pad, stopping at other pads and pours."""
    seen, front, got, hit = set(), [], [], set()
    for ln, g in PADS[start].items():
        for d in q(ln, g, net=net, kinds=("track", "via")):
            if id(d) not in seen: seen.add(id(d)); front.append(d)
    while front:
        d = front.pop(); got.append(d)
        for ln in (d["layers"] if d["kind"] == "via" else [d["layer"]]):
            for e in q(ln, d["geom"], net=net):
                if e["kind"] == "pad":
                    if e["ref"] != start: hit.add(e["ref"])
                elif e["kind"] == "zone": hit.add(f"pour@{ln}")
                elif id(e) not in seen: seen.add(id(e)); front.append(e)
    return got, sorted(hit)

RES, FAILED = [], False
def check(r, name, ok, value, rule, warn=False):
    global FAILED
    st = "PASS" if ok else ("WARN" if warn else "FAIL")
    if st == "FAIL": FAILED = True
    r["checks"].append(dict(check=name, status=st, value=value, rule=rule))

for sp in SPEC:
    lim = dict(LIMITS, **sp.get("limits", {}))
    ic, sw, gnd = sp["ic"], sp["sw_net"], sp["gnd_net"]
    comp_layer = side(f"{ic}.{next(iter(p.GetNumber() for p in fps[ic].Pads()))}")
    plane = sp.get("plane_layer", ORDER[1])
    r = dict(name=sp.get("name", ic), checks=[], loop={})
    # ---- hot loop
    loop = sp["hot_loop"]; pts, vert, hows = [], 0.0, []
    for i in range(len(loop)):
        a_, b_ = loop[i], loop[(i + 1) % len(loop)]
        if netof(a_) != netof(b_): pts.append(ctr(a_)); continue           # through the part (cap or IC)
        lk = link(netof(a_), a_, b_); pts += lk["path"]; vert += lk["vert"]; hows.append(f"{a_}-{b_}: {lk['how']}")
    plan = shoelace(pts)
    r["loop"] = dict(plan=round(plan, 2), vertical=round(vert, 2), links=hows, pts=[tuple(round(v, 3) for v in p) for p in pts])
    check(r, "hot loop area (plan + vertical)", plan + vert <= lim["loop_area_mm2"], f"{plan:.2f} + {vert:.2f} mm²", "L-11")
    check(r, "hot loop closed on the component layer, no via", all(h.endswith(comp_layer) for h in hows), "; ".join(hows), "L-11")
    # ---- HF cap at its pins
    hf = sp["hf_cap"]
    for p in fps[hf].Pads():
        lab = f"{hf}.{p.GetNumber()}"
        pins = [f"{ic}.{q_.GetNumber()}" for q_ in fps[ic].Pads() if q_.GetNetname() == p.GetNetname()]
        if not pins: continue
        dmin = min(pad(lab).distance(pad(x)) for x in pins)
        check(r, f"{lab} ({p.GetNetname().split('/')[-1]}) to its pin, pad edge", dmin <= lim["hf_cap_edge_mm"], f"{dmin:.2f} mm", "L-11")
    # ---- SW node
    swcu = [d for ln in items for d in items[ln] if d["net"] == sw]
    swv = {id(d) for d in swcu if d["kind"] == "via"}
    swall = unary_union([d["geom"] for d in swcu])
    swnp = unary_union([d["geom"] for d in swcu if d["kind"] != "pad"])
    check(r, "SW copper beyond the pads", True, f"{(swnp.area if not swnp.is_empty else 0):.2f} mm² ({len(swv)} vias)", "L-28")
    check(r, "vias on the SW net", len(swv) <= lim["sw_vias"], f"{len(swv)}", "L-28, L-29")
    swc = unary_union([d["geom"] for d in items[comp_layer] if d["net"] == sw])
    cover = unary_union([d["geom"] for d in items[plane] if d["kind"] == "zone" and d["net"] in (gnd, sp.get("plane_net", gnd))]).intersection(swc).area
    pct = 100.0 * cover / swc.area if swc.area else 100.0
    check(r, f"plane under SW copper ({plane})", pct >= lim["plane_cover_pct"] - 0.05, f"{pct:.1f}%", "L-23")
    under = collections.Counter()
    for ln in ORDER:
        if ln == comp_layer: continue
        for d in q(ln, swc, kinds=("track",)):
            if d["net"] != sw: under[(d["net"].split("/")[-1], ln)] += 1
    check(r, "signal tracks under SW (any layer)", not under, ", ".join(f"{n} on {ln}" for (n, ln) in under) or "none", "L-12", warn=True)
    # ---- sense and strap lines
    L = courtyard(sp["inductor"]); body = L.buffer(-0.25) if L is not None else None
    swF = unary_union([d["geom"] for d in items[comp_layer] if d["net"] == sw])
    def run_near(tracks, start_pt):
        tot = 0.0
        for d in tracks:
            if d["layer"] != comp_layer: continue            # below the plane is shielded
            seg = d["line"].intersection(swF.buffer(lim["sense_clear_mm"]))
            for s_ in (seg.geoms if hasattr(seg, "geoms") else [seg]):
                if s_.is_empty or s_.geom_type != "LineString": continue
                if start_pt is not None and all(math.dist(c, start_pt) <= lim["sense_escape_mm"] for c in s_.coords): continue
                tot += s_.length
        return tot
    for lab in sp.get("sense_pins", []):
        got, hit = trace(lab, netof(lab)); trk = [d for d in got if d["kind"] == "track"]
        if WIN is not None and any(not WIN.buffer(-0.5).contains(d["geom"]) for d in got):
            check(r, f"sense {lab} inside the window", False, "the route reaches the window edge: widen --margin or pass --no-window", "-", warn=True)
        run = run_near(trk, ctr(lab))
        lens = collections.Counter(); [lens.update({d["layer"]: d["length"]}) for d in trk]
        check(r, f"sense {lab} near SW past the escape ({comp_layer})", run <= lim["sense_run_tol_mm"],
              f"{run:.2f} mm within {lim['sense_clear_mm']} mm; route " + ", ".join(f"{k} {v:.1f} mm" for k, v in lens.items()) + f"; ends {', '.join(hit)}", "L-28")
        over = body is not None and any(d["geom"].intersects(body) for d in trk if d["layer"] == comp_layer)
        check(r, f"sense {lab} over the inductor body", not over, "yes" if over else "no", "L-28")
    for net in sp.get("strap_nets", []):
        trk = [d for d in TR if d["kind"] == "track" and d["net"] == net]
        run = run_near(trk, None)
        check(r, f"strap {net.split('/')[-1]} near SW", run <= lim["sense_run_tol_mm"], f"{run:.2f} mm within {lim['sense_clear_mm']} mm", "L-28")
    # ---- every cap returns on the regulator's ground (L-62)
    gpins = [f"{ic}.{p.GetNumber()}" for p in fps[ic].Pads() if p.GetNetname() == gnd]
    for cap in [sp["hf_cap"]] + sp.get("bulk_caps", []) + sp.get("out_caps", []):
        cn = next((f"{cap}.{p.GetNumber()}" for p in fps[cap].Pads() if p.GetNetname() == gnd), None)
        if cn is None:
            check(r, f"{cap} ground pad on {gnd}", False, "no pad on the regulator's ground net", "L-62"); continue
        lk = min((link(gnd, cn, g) for g in gpins), key=lambda k: 0 if k["how"] != "NOT CONNECTED" else 1)
        check(r, f"{cap} ground reaches the IC ground", lk["how"] != "NOT CONNECTED", lk["how"], "L-62")
    # ---- rail entries and exits
    for lab in sp.get("rail_entries", []):
        net = netof(lab); cF = comp_of(net, side(lab), pad(lab))
        vv = [v for v in TR if v["kind"] == "via" and v["net"] == net and cF is not None and cF.intersects(v["geom"])]
        planed = [v for v in vv if any(p_ != side(lab) for p_ in via_planes(v))]
        check(r, f"rail entry {lab} ({net.split('/')[-1]}) vias into a plane", len(planed) >= lim["entry_vias"], f"{len(planed)} of {len(vv)}", "L-21")
    # ---- exposed pad
    if sp.get("ep"):
        lab = f"{ic}.{sp['ep']}"; g = pad(lab); p = PADOBJ[lab]
        inpad = [v for v in TR if v["kind"] == "via" and v["net"] == netof(lab) and v["geom"].intersects(g)]
        pasted = p.IsOnLayer(pcbnew.F_Paste) or p.IsOnLayer(pcbnew.B_Paste)
        sizes = ", ".join(sorted({"%.2f/%.2f" % (v["w"], v["drill"]) for v in inpad}))
        check(r, f"thermal vias in {lab}", len(inpad) > 0, f"{len(inpad)} ({sizes})", "L-29")
        check(r, f"{lab} vias vs paste", not (inpad and pasted and not sp.get("vippo")),
              "pad is pasted whole and its vias are open" if inpad and pasted and not sp.get("vippo") else "ok", "L-30")
    RES.append(r)

for r in RES:
    print(f"\n== {r['name']}")
    for c in r["checks"]:
        print(f"  {c['status']:4s}  {c['check']:<55s} {c['value']}  [{c['rule']}]")
if a.json: json.dump(RES, open(a.json, "w"), indent=1)

if a.render:
    from PIL import Image, ImageDraw
    os.makedirs(a.render, exist_ok=True)
    for sp, r in zip(SPEC, RES):
        if not sp.get("crop"): continue
        x0, y0, x1, y1 = sp["crop"]; SC = sp.get("px_per_mm", 50); W, H = int((x1 - x0) * SC), int((y1 - y0) * SC)
        win = box(x0, y0, x1, y1); panels = [ORDER[0], sp.get("plane_layer", ORDER[1])] + [n for n in ORDER[2:-1]][-1:]
        img = Image.new("RGB", (len(panels) * (W + 20), H + 30), (255, 255, 255)); dr = ImageDraw.Draw(img, "RGBA")
        col = lambda n: ((225, 45, 45) if n == sp["sw_net"] else (70, 110, 200) if n == sp["gnd_net"] else (240, 140, 30)
                         if n == netof(sp["hot_loop"][0]) else (40, 160, 80) if n in [netof(x) for x in sp.get("sense_pins", [])] else (175, 175, 175))
        for k, ln in enumerate(panels):
            ox = k * (W + 20); T = lambda x, y: (ox + (x - x0) * SC, 25 + (y - y0) * SC)
            dr.text((ox + 4, 4), ln, fill=(0, 0, 0))
            for d in sorted(items[ln], key=lambda d: {"zone": 0, "track": 1, "pad": 2, "via": 3}[d["kind"]]):
                if not d["geom"].intersects(win): continue
                g = d["geom"].intersection(win)
                for gg in (g.geoms if hasattr(g, "geoms") else [g]):
                    if gg.geom_type != "Polygon": continue
                    dr.polygon([T(*p) for p in gg.exterior.coords], fill=col(d["net"]) + ((90,) if d["kind"] == "zone" else (230,)))
            P_ = [T(*p) for p in r["loop"]["pts"]] + [T(*r["loop"]["pts"][0])]
            dr.line(P_, fill=(0, 0, 0, 255), width=3)
            dr.rectangle([ox, 25, ox + W, 25 + H], outline=(0, 0, 0))
        img.save(os.path.join(a.render, f"{sp.get('name', sp['ic']).split()[0]}.png"))
sys.exit(1 if FAILED else 0)
