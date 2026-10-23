#!/usr/bin/env python3
"""Anchor-pin placement of small parts (ee-layout-rules L-61; pcb-placement step 5a).

Round 1 is the rule a person follows by eye: every small part (R, C, D, L, FB, small protection
ICs) belongs to the IC or connector pin its private net goes to. Put it as close to that pin as a
legal spot allows, on its own side, turned so its other pin faces where that pin's net goes.
Rounds 2+ re-seat each part with all the others in place and swap same-footprint pairs while the
estimated wirelength drops. All moves are legality-checked against the copper left on the board.

Net roles (from the netlist and the board, nothing hand-written):
  plane   the net has an inner-layer pour under the pin (GND, 3V3 here): the pin needs a via, so it
          only wants to point away from the part's anchor (a weak "outward" pull)
  power   a power net with no pour there (5V, 3V3_AUX ...): routed copper, pulled like a signal
  signal  everything else; the target is the net's spanning tree (MST) over its fixed pads, the
          already placed parts' pads and the stub ends the rip left, so a part taps the trunk
  nc      unconnected-* or single-pad nets: ignored
A part whose pins are all plane/power (decaps, 0R bypass links, ESD diodes on rails) gets an
owner: the fixed part in the same schematic sheet that has pins on all its nets (ICs first for
C/R/L/FB, connectors first for diodes), and each pin is pulled to the owner's pin on that net.

Run with KiCadRoutingTools' venv python ($KV: pcbnew, numpy, shapely). Board options for every command:
  --power-nets GLOB ...   more power/ground nets (default: every net with a pour, every net in a net class
                          named like Power/PWR/GND/Supply/Rail, and bare rail names: GND*, VBUS, VIN,
                          VCC*, VDD*, 3V3, 5V, +12V)
  --hv REGEX              nets that need 0.35 mm instead of 0.25 mm clearance (default none)
  --floorplan JSON        a KRT floorplan intent whose "keepouts" (rect/circle, sides, allow) are honoured
  --via D/DRILL           pin via (default 0.6/0.3; in-pad fallbacks 0.45/0.2 then 0.35/0.15)
place also takes --keep-good MM (leave parts already that close to their pin), --held JSON (no-part zones:
{"areas": [{"rect": [x0,y0,x1,y1], "layers": ["F.Cu"] or null, "active": true}]}) and --overrides FILE
(reviewer lines: "FIX REF" keeps a part; "ANCHOR REF NET REF2.PAD" pulls REF's pin on NET to that pad, or for
a decap names the IC pin it serves).

  $KV anchor_place.py select  BOARD --sheets /sheetA/ /sheetB/ --region X0 Y0 X1 Y1 > movable.txt
  $KV anchor_place.py classify BOARD --movable movable.txt [--csv roles.csv]
  $KV anchor_place.py rip     BOARD OUT --movable movable.txt --region ... (writes OUT.stubs.json, OUT.nets)
  $KV anchor_place.py place   BOARD OUT --movable movable.txt --region ... [--rounds 3] [--plan plan.csv]
                                        [--edits moves.txt] [--only-round1]
  $KV anchor_place.py measure BOARD --movable movable.txt --region ... [--json out.json]
Board mm throughout (KiCad page coordinates). Footprint locks are kept as they were."""
import argparse, csv, json, math, os, re, sys, collections
import numpy as np
import pcbnew
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely import affinity

MM = 1e6
def mm(v): return v / MM
POWER = set()        # filled by Board() from the pours, the net classes, the name pattern and --power-nets
POWER_NAME = re.compile(r"^(A|D|P)?GND\w*$|^VBUS$|^VIN$|^VCC\w*$|^VDD\w*$|^\+?\d+V\d*$")
POWER_CLASS = re.compile(r"power|pwr|gnd|supply|rail", re.I)
POWER_GLOBS = []
HVP = re.compile(r"(?!x)x")
VIA = (0.6, 0.3)
SMALL = re.compile(r"^(R|C|D|L|FB)\d+$")
SAT_IC = re.compile(r"TPD|ESD|TVS|PESD")
EPS = 1e-3     # mm: geometry from KiCad polygons lands a hair under a 0.2 mm design value
W_SIG, W_POWER, W_OWNER, W_OUT, W_LOCAL, W_PRIV = 1.0, 0.6, 1.0, 0.3, 0.1, 3.0
HELD = None
FLOORPLAN = None


def polys(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); pts = [(mm(o.CPoint(k).x), mm(o.CPoint(k).y)) for k in range(o.PointCount())]
        if len(pts) > 2: out.append(Polygon(pts).buffer(0))
    return unary_union(out) if out else None


def side_of(f): return "B" if f.IsFlipped() else "F"
def tht(f): return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads())
def is_conn(f):
    r = f.GetReference(); s = (f.GetFPIDAsString() + " " + f.GetValue()).upper()
    return r.startswith("J") or r.startswith("AUX") or any(k in s for k in ("CONN", "PINHEADER", "JST", "GHS"))
def is_nc(net): return (not net) or net.startswith("unconnected-")
def pxy(p): q = p.GetPosition(); return (mm(q.x), mm(q.y))


def court(f):
    s = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    g = polys(s) if s.OutlineCount() else None
    if g is None or g.is_empty:
        bb = f.GetBoundingBox(False); g = box(mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()))
    return g


def cap_value(f):
    m = re.match(r"([\d.]+)\s*([pnuµm]?)F", f.GetValue())
    if not m: return 1.0
    return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0}[m.group(2)]


def read_refs(path): return [l.split()[0] for l in open(path) if l.strip() and not l.startswith("#")]


# ---------------------------------------------------------------- board model
class Board:
    def __init__(self, path, movable, region=None, stubs=None):
        self.path = path; self.b = pcbnew.LoadBoard(path)
        self.fp = {f.GetReference(): f for f in self.b.GetFootprints()}
        self.movable = [r for r in movable if r in self.fp]
        self.mov = set(self.movable)
        self.region = region
        self.stubs = stubs or {}
        self.netpads = collections.defaultdict(list)   # net -> [(ref, pad)]
        for f in self.b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname(): self.netpads[p.GetNetname()].append((f.GetReference(), p))
        import fnmatch
        zn = {z.GetNetname() for z in self.b.Zones() if not z.GetIsRuleArea() and z.GetNetname()}
        ncls = {str(n): ni.GetNetClassName() for n, ni in self.b.GetNetsByName().items()}
        POWER.clear(); POWER.update(n for n in self.netpads if n in zn or POWER_NAME.match(n.split("/")[-1])
                                    or POWER_CLASS.search(ncls.get(n, "")) or any(fnmatch.fnmatch(n, g) for g in POWER_GLOBS))
        self.planes = []    # (net, shapely outline) inner-layer pours
        for z in self.b.Zones():
            if z.GetIsRuleArea(): continue
            if any(self.b.GetLayerName(l).startswith("In") for l in z.GetLayerSet().CuStack()):
                g = polys(z.Outline())
                if g is not None: self.planes.append((z.GetNetname(), g))

    def plane_at(self, net, xy):
        """an inner pour of the net under the pin, or (with a region) anywhere in the region: a pin that
        moves inside the region can reach that pour with a via"""
        pt = Point(xy); R = box(*self.region) if self.region else None
        return any(n == net and (g.contains(pt) or (R is not None and g.intersection(R).area > 0.25 * R.area)) for n, g in self.planes)

    def role(self, net, xy):
        if is_nc(net) or len(self.netpads[net]) < 2: return "nc"
        if self.plane_at(net, xy): return "plane"
        if net in POWER: return "power"
        return "signal"

    def sheet(self, ref): return self.fp[ref].GetSheetname()

    def fixed_pads(self, net, skip=()):
        return [(r, p) for r, p in self.netpads[net] if r not in self.mov and r not in skip]

    def owner(self, ref):
        """For an all-rail part: the fixed part in its sheet with pins on all its nets."""
        f = self.fp[ref]; nets = {p.GetNetname() for p in f.Pads() if not is_nc(p.GetNetname())}
        if not nets: return None
        cands = []
        for g in self.b.GetFootprints():
            r = g.GetReference()
            if r in self.mov or r == ref or SMALL.match(r) or r.startswith("TP"): continue
            gn = {p.GetNetname() for p in g.Pads()}
            if not nets <= gn: continue
            same = g.GetSheetname() == f.GetSheetname()
            conn = is_conn(g)
            pref = (conn if not ref.startswith("D") else not conn)       # False sorts first
            d = math.dist(pxy(g), pxy(f))
            cands.append((not same, pref, -len(list(g.Pads())) if conn else 0, d, r))
        if not cands: return None
        cands.sort(); return cands[0][-1]


def mst_segments(pts):
    """Prim's MST over points -> list of segments (a single point gives [(p, p)])."""
    pts = list(dict.fromkeys((round(x, 3), round(y, 3)) for x, y in pts))
    if not pts: return []
    if len(pts) == 1: return [(pts[0], pts[0])]
    inn = [0]; out = set(range(1, len(pts))); segs = []
    best = {j: (math.dist(pts[0], pts[j]), 0) for j in out}
    while out:
        j = min(out, key=lambda k: best[k][0]); segs.append((pts[best[j][1]], pts[j])); out.remove(j)
        for k in out:
            d = math.dist(pts[j], pts[k])
            if d < best[k][0]: best[k] = (d, j)
    return segs


def mst_len(pts):
    return sum(math.dist(a, b) for a, b in mst_segments(pts))


def seg_dist(P, segs):
    """P: (N,2) array; segs: list of ((ax,ay),(bx,by)) -> (N,) min distance."""
    if not segs: return np.zeros(len(P))
    A = np.array([s[0] for s in segs]); B = np.array([s[1] for s in segs])
    D = B - A; L2 = (D ** 2).sum(1); L2[L2 == 0] = 1e-12
    V = P[:, None, :] - A[None, :, :]
    t = np.clip((V * D[None]).sum(2) / L2[None], 0, 1)
    C = A[None] + t[..., None] * D[None]
    return np.sqrt(((P[:, None, :] - C) ** 2).sum(2)).min(1)


# ---------------------------------------------------------------- classification
def classify(B):
    """ref -> dict(role, owner, pins=[(padnum, net, kind)], prio)."""
    out = {}
    for ref in B.movable:
        f = B.fp[ref]; pins = []
        for p in f.Pads():
            n = p.GetNetname(); pins.append((p.GetNumber(), n, B.role(n, pxy(p))))
        kinds = [k for _, _, k in pins if k != "nc"]
        sig = [(num, n) for num, n, k in pins if k == "signal"]
        own = B.owner(ref) if kinds and all(k in ("plane", "power") for k in kinds) else None
        anchors = []
        for num, n in sig:
            fx = [x for x in B.fixed_pads(n, skip=(ref,)) if not x[0].startswith("TP")]   # a test point is no anchor
            near = not B.region or box(*B.region).buffer(3).contains(Point(pxy(fx[0][1]))) if fx else False
            if len(fx) == 1 and near: anchors.append(f"{fx[0][0]}.{fx[0][1].GetNumber()}")
        if own:
            role = {"C": "decap", "D": "rail-esd", "R": "rail-link", "L": "rail-filter", "F": "rail-filter"}[ref[0]]; prio = 0
        elif len(f.Pads()) > 3:
            role = "satellite"; prio = 2
        elif len(sig) == 1 and anchors:
            role = "pull/bias"; prio = 1
        elif len(sig) >= 2:
            role = "series"; prio = 3
        elif len(sig) == 1:
            role = "tap"; prio = 3
        else:
            role = "free"; prio = 4
        nfix = sum(len(B.fixed_pads(n, skip=(ref,))) for _, n in sig)
        out[ref] = dict(role=role, owner=own, anchors=anchors, pins=pins, prio=prio, nfix=nfix,
                        cap=cap_value(f) if ref.startswith("C") else 0, chain=None)
    find_chains(B, out)
    return out


def private(B, n):
    """a signal net that only joins movable parts (the link inside an R-R-R or R-D chain)"""
    return len(B.netpads[n]) >= 2 and all(r in B.mov for r, _ in B.netpads[n])


def find_chains(B, C):
    """Chains of small parts joined by private nets (series R-R-R in front of a pin, pull-up + diode) are
    seated the way a person does it: start at the member whose other net reaches a fixed pin (an IC pin in
    the region first, then a connector pin, then anything farther), seat it at that pin, then walk the chain
    outward, each next part beside the one before. Sets C[ref]["chain"] = (root, index) and the walk order."""
    small = [r for r in C if len(B.fp[r].Pads()) <= 3]
    adj = collections.defaultdict(set)
    for r in small:
        for _, n, k in C[r]["pins"]:
            if k == "signal" and private(B, n):
                for q, _ in B.netpads[n]:
                    if q != r and q in C and len(B.fp[q].Pads()) <= 3: adj[r].add(q)
    R = box(*B.region).buffer(3) if B.region else None
    def score(r):
        best = 0
        for _, n, k in C[r]["pins"]:
            if k != "signal" or private(B, n): continue
            for q, p in B.fixed_pads(n, skip=(r,)):
                g = B.fp[q]; near = R is None or R.contains(Point(pxy(p)))
                kind = 2 if not is_conn(g) and not SMALL.match(q) and not q.startswith("TP") else 1
                best = max(best, kind + (2 if near else 0))
        return best
    seen = set()
    for r in sorted(adj):
        if r in seen: continue
        comp, stack = [], [r]
        while stack:
            x = stack.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); stack += sorted(adj[x] - seen)
        if len(comp) < 2: continue
        root = max(sorted(comp), key=score)
        walk, frontier, done = [], [root], {root}
        while frontier:
            x = frontier.pop(0); walk.append(x)
            for y in sorted(adj[x]):
                if y not in done: done.add(y); frontier.append(y)
        gp = min(C[x]["prio"] for x in comp)
        for i, x in enumerate(walk): C[x]["chain"] = (root, i, gp)


def order(C):
    def key(r):
        ch = C[r]["chain"]
        if ch: return (ch[2], 0, -C[ch[0]]["nfix"], ch[0], ch[1])
        return (C[r]["prio"], C[r]["cap"], -C[r]["nfix"], r, 0)
    return sorted(C, key=key)


def main_net(c):
    nets = [n for _, n, k in c["pins"] if k != "nc"]
    return next((n for _, n, k in c["pins"] if k == "power"), nets[0] if nets else None)


def anchor_dist(B, C, r):
    """how far the part's pin sits from the pin it belongs to, as placed on the board (None if it has none)"""
    c = C[r]; f = B.fp[r]
    if c["owner"]:
        n = main_net(c); g = B.fp[c["owner"]]
        mp = [pxy(p) for p in f.Pads() if p.GetNetname() == n]
        return min(math.dist(a, pxy(q)) for a in mp for q in g.Pads() if q.GetNetname() == n)
    if c["anchors"]:
        ref, num = c["anchors"][0].split("."); q = next(q for q in B.fp[ref].Pads() if q.GetNumber() == num)
        return min(math.dist(pxy(p), pxy(q)) for p in f.Pads() if p.GetNetname() == q.GetNetname())
    return None


def assign_owner_pads(B, C, keep=()):
    """spread decaps over the owner's pins on their rail (smallest value first, a pin each before any pin gets a
    second): a part kept where it is claims the owner pin nearest it; the rest take the least-claimed pin,
    nearest to where the part was"""
    groups = collections.defaultdict(list)
    for r, c in C.items():
        if c["owner"] and c["role"] == "decap" and not c.get("owner_fixed"): groups[(c["owner"], main_net(c))].append(r)
    for (own, n), rs in groups.items():
        pads = [p for p in B.fp[own].Pads() if p.GetNetname() == n]
        if len(pads) < 2: continue
        claims = collections.Counter()
        def near(r, ps): return min(ps, key=lambda p: math.dist(pxy(p), pxy(B.fp[r])))
        for r in [r for r in rs if r in keep]:
            p = near(r, pads); C[r]["owner_pad"] = p.GetNumber(); claims[p.GetNumber()] += 1
        for r in sorted((r for r in rs if r not in keep), key=lambda r: (C[r]["cap"], r)):
            low = min(claims[p.GetNumber()] for p in pads)
            p = near(r, [p for p in pads if claims[p.GetNumber()] == low]); C[r]["owner_pad"] = p.GetNumber(); claims[p.GetNumber()] += 1


# ---------------------------------------------------------------- geometry of a part per rotation
class Shape:
    """pad offsets/polygons and courtyard of a footprint at each quarter turn, relative to its origin."""
    def __init__(self, f, rots):
        self.rot = {}
        pos0, r0 = f.GetPosition(), f.GetOrientationDegrees()
        sl = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
        for rot in rots:
            f.SetOrientationDegrees(rot % 360); f.SetPosition(pcbnew.VECTOR2I(0, 0))
            pads = []
            for p in f.Pads():
                g = polys(p.GetEffectivePolygon(sl, pcbnew.ERROR_INSIDE)) if p.IsOnLayer(sl) else None
                pads.append((p.GetNumber(), p.GetNetname(), pxy(p), g))
            self.rot[rot % 360] = (pads, court(f))
        f.SetOrientationDegrees(r0); f.SetPosition(pos0)


# ---------------------------------------------------------------- legality
class Legal:
    def __init__(self, B, side):
        self.B = B; self.side = side
        b = B.b; sl = pcbnew.B_Cu if side == "B" else pcbnew.F_Cu; self.sl = sl
        outline = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(outline, True)
        self.inner = polys(outline).buffer(-1.25)
        if B.region: self.inner = self.inner.intersection(box(*B.region))
        self.ko = []
        try:
            for k in (json.load(open(FLOORPLAN))["keepouts"] if FLOORPLAN else []):
                if side not in k["sides"]: continue
                g = box(*k["rect"]) if "rect" in k else Point(k["circle"][:2]).buffer(k["circle"][2])
                self.ko.append((g, k.get("allow", [])))
        except FileNotFoundError:
            pass
        for h in (json.load(open(HELD))["areas"] if HELD else []):     # routing threads' held areas (side layer or all)
            if h.get("active") and (h.get("layers") is None or f"{side}.Cu" in h["layers"]): self.ko.append((box(*h["rect"]), []))
        for z in b.Zones():
            if not z.GetIsRuleArea() or not z.IsOnLayer(sl): continue
            if z.GetDoNotAllowFootprints() or "barrier" in (z.GetZoneName() or ""):
                g = polys(z.Outline())
                if g is not None: self.ko.append((g, []))
        # static obstacles: fixed parts' courtyards and copper (movable parts are added as they are seated)
        self.court = {}; self.copper = []      # copper: (geom, net, owner_ref or None)
        reg = box(*B.region).buffer(6) if B.region else None
        for f in b.GetFootprints():
            r = f.GetReference()
            if r in B.mov: continue
            if side_of(f) == side or tht(f):
                c = court(f)
                if reg is None or c.intersects(reg): self.court[r] = c
            for p in f.Pads():
                if p.IsOnLayer(sl) and p.FlashLayer(sl):
                    g = polys(p.GetEffectivePolygon(sl, pcbnew.ERROR_INSIDE))
                    if g is not None and (reg is None or g.intersects(reg)): self.copper.append((g, p.GetNetname(), r))
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                q = t.GetPosition(); g = Point(mm(q.x), mm(q.y)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2)
            elif t.GetLayer() == sl:
                s, e = t.GetStart(), t.GetEnd()
                g = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2)
            else:
                continue
            if reg is None or g.intersects(reg): self.copper.append((g, t.GetNetname(), None))
        # every copper item on any layer, for pin-via room (a via goes through all of them)
        self.allcu = []
        for f in b.GetFootprints():          # drilled holes, NPTH too: no copper on them, but a via or pad must keep off
            for p in f.Pads():
                d = p.GetDrillSize()
                if d.x > 0:
                    g = Point(pxy(p)).buffer(mm(max(d.x, d.y)) / 2)
                    if reg is None or g.intersects(reg):
                        self.allcu.append((g, "", "hole")); self.copper.append((g, "#hole", None))
        for f in b.GetFootprints():
            if f.GetReference() in B.mov: continue
            for p in f.Pads():
                for ln in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if p.IsOnLayer(ln) and p.FlashLayer(ln):
                        g = polys(p.GetEffectivePolygon(ln, pcbnew.ERROR_INSIDE))
                        if g is not None and (reg is None or g.intersects(reg)): self.allcu.append((g, p.GetNetname(), "pad"))
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T:
                g = Point(pxy(t)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2); k = "via"
            else:
                s_, e_ = t.GetStart(), t.GetEnd(); k = "trk"
                g = LineString([(mm(s_.x), mm(s_.y)), (mm(e_.x), mm(e_.y))]).buffer(mm(t.GetWidth()) / 2)
            if reg is None or g.intersects(reg): self.allcu.append((g, t.GetNetname(), k))
        self.novia = [polys(z.Outline()) for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
        self.novia = [g for g in self.novia if g is not None]
        self.board_in = polys(outline).buffer(-1.0)
        self.placed = {}      # ref -> (courtyard, [(padgeom, net)], [(viageom, net, (x, y), padcentre, stub, w)])
        self.peers = []       # the other side's Legal (set by the caller)
        self._tree()

    def _tree(self):
        self.ctree_items = list(self.court.items()) + [(r, v[0]) for r, v in self.placed.items()]
        self.ctree = STRtree([g for _, g in self.ctree_items])
        self.cu_items = self.copper + [(g, n, r) for r, v in self.placed.items() for g, n in v[1] if g is not None] \
            + [(g, n, r) for r, v in self.placed.items() for g, n, _, _, _, _ in v[2]] \
            + [(st, n, r) for r, v in self.placed.items() for _, n, _, _, st, _ in v[2]]
        self.cutree = STRtree([g for g, _, _ in self.cu_items])
        for P in self.peers:          # the other side's seated parts: their vias go through this side too
            self.cu_items += [(g, n, r) for r, v in P.placed.items() for g, n, *_ in v[2]]
            self.cutree = STRtree([g for g, _, _ in self.cu_items])
        self.va_items = [(g, n, k, None) for g, n, k in self.allcu] \
            + [(g, n, "pad", r) for P in self.peers for r, v in P.placed.items() for g, n in v[1] if g is not None] \
            + [(g, n, "via", r) for P in self.peers for r, v in P.placed.items() for g, n, *_ in v[2]] \
            + [(g, n, "pad", r) for r, v in self.placed.items() for g, n in v[1] if g is not None] \
            + [(g, n, "via", r) for r, v in self.placed.items() for g, n, _, _, _, _ in v[2]]
        self.vatree = STRtree([g for g, _, _, _ in self.va_items])

    def put(self, ref, c, pads):
        self.placed[ref] = (c, pads, self.vias_for(ref, pads, partial=True) or []); self._tree()
        for P in self.peers: P._tree()
    def lift(self, ref):
        self.placed.pop(ref, None); self._tree()
        for P in self.peers: P._tree()

    def vias_for(self, ref, pads, partial=False):
        """one 0.6/0.3 pin via per power/ground pad (L-39), beside the pad as pin_vias3 puts it: centre at
        half-size + 0.5 + k*0.25 mm along 0/45/90 deg, 0.2 mm to other copper on every layer, 0.3 mm to any via,
        0.1 mm to its own pad, ring within 0.5 mm of the pad edge, and a straight stub (min(0.4, narrow side)) that
        clears other-net copper on the part's side. Returns [(geom, net, (x, y), padcentre, stubgeom)], or None."""
        out = []; cen = unary_union([g for g, _ in pads if g is not None]).centroid
        for pg, n in pads:
            if pg is None or n not in POWER: continue
            c = pg.centroid; x0, y0, x1, y1 = pg.bounds; half = max(x1 - x0, y1 - y0) / 2
            sw = max(0.15, min(0.4, x1 - x0, y1 - y0))
            got = None
            for k in range(5):
                r = half + 0.5 + 0.25 * k; opts = []
                for j in range(8):
                    ang = j * math.pi / 4; v = (c.x + r * math.cos(ang), c.y + r * math.sin(ang))
                    out_d = -math.hypot(v[0] - cen.x, v[1] - cen.y)          # prefer the side away from the part
                    opts.append((out_d, v))
                for _, v in sorted(opts):
                    vg = Point(v).buffer(VIA[0] / 2)
                    if pg.distance(vg) > 0.5 + EPS: continue                               # L-39: ring <= 0.5 mm from the pad edge
                    if not self.board_in.contains(vg) or any(z.intersects(vg) for z in self.novia): continue
                    if any(og.distance(vg) < 0.3 for og, *_ in out): continue
                    st = LineString([(c.x, c.y), v]).buffer(sw / 2)
                    bad = False
                    for og, on in pads:
                        if og is None: continue
                        need = 0.1 if og is pg else 0.2
                        if og.distance(vg) < need - EPS or (og is not pg and on != n and og.distance(st) < 0.2 - EPS): bad = True; break
                    if bad: continue
                    for i in self.vatree.query(vg.buffer(0.35)):
                        g, on, kind, r_ = self.va_items[int(i)]
                        if r_ == ref: continue
                        if kind in ("via", "hole"): need = 0.3
                        elif kind == "pad": need = 0.3 if HVP.search(on or "") else 0.2
                        else:
                            if on == n: continue
                            need = 0.3 if HVP.search(on or "") else 0.2
                        if g.distance(vg) < need - EPS: bad = True; break
                    if not bad:
                        for i in self.cutree.query(st.buffer(0.3)):
                            g, on, r_ = self.cu_items[int(i)]
                            if r_ == ref or on == n: continue
                            if g.distance(st) < (0.3 if HVP.search(on or "") else 0.2) - EPS: bad = True; break
                    if not bad: got = (vg, n, v, (c.x, c.y), st, sw); break
                if got: break
            for vr in ((0.225, 0.175) if not got else ()):   # pin_vias3's fallback: via in pad (0.45/0.2, then 0.35/0.15), no stub
                if got: break
                vg = c.buffer(vr); bad = any(z.intersects(vg) for z in self.novia)
                for og, on in pads:
                    if og is not None and og is not pg and og.distance(vg) < 0.2 - EPS: bad = True
                for i in ([] if bad else self.vatree.query(vg.buffer(0.35))):
                    g, on, kind, r_ = self.va_items[int(i)]
                    if r_ == ref or (kind == "trk" and on == n): continue
                    if g.distance(vg) < (0.3 if kind == "via" else 0.2) - EPS: bad = True; break
                if not bad and not any(og.distance(vg) < 0.3 for og, *_ in out):
                    got = (vg, n, (c.x, c.y), (c.x, c.y), c.buffer(0.01), -vr)
            if got: out.append(got)
            elif not partial: return None
        return out

    def check(self, ref, c, pads):
        if not self.inner.contains(c): return "edge/region"
        for g, allow in self.ko:
            if ref not in allow and c.intersects(g) and c.intersection(g).area > 1e-4: return "keepout"
        cb = c.buffer(0.002)          # KiCad flags touching courtyards too; 2 um covers nm rounding
        for i in self.ctree.query(cb):
            r, g = self.ctree_items[int(i)]
            if r != ref and cb.intersects(g): return f"courtyard {r}"
        for pg, n in pads:
            if pg is None: continue
            for i in self.cutree.query(pg.buffer(0.35)):
                g, on, r = self.cu_items[int(i)]
                if r == ref or (on == n and n and not is_nc(n)): continue
                need = 0.35 if (HVP.search(n or "") or HVP.search(on or "")) else 0.25
                if pg.distance(g) < need: return f"copper {on}"
        if self.vias_for(ref, pads) is None: return "no pin-via room"
        return None


# ---------------------------------------------------------------- cost model
class Model:
    def __init__(self, B, C):
        self.B, self.C = B, C
        self.pos = {}       # ref -> (x, y, rot) of seated movable parts (None = lifted)
        self.shape = {r: Shape(B.fp[r], (0, 90, 180, 270)) for r in B.movable}

    def pad_xy(self, ref, num):
        """position of a seated movable part's pad (None while lifted)."""
        if self.pos.get(ref) is None: return None
        x, y, rot = self.pos[ref]
        for n, _, (dx, dy), _ in self.shape[ref].rot[rot][0]:
            if n == num: return (x + dx, y + dy)

    def terminals(self, net, skip):
        B = self.B; pts = []
        stub = B.stubs.get(net, [])
        for r, p in B.netpads[net]:
            if r == skip: continue
            if r in B.mov:
                q = self.pad_xy(r, p.GetNumber())
                if q: pts.append(q)
            else:
                q = pxy(p)
                if stub and B.region and not box(*B.region).buffer(2).contains(Point(q)): continue
                pts.append(q)
        return pts + [tuple(s) for s in stub]

    def targets(self, ref):
        """[(padnum, segments, weight, label)] for the part's pins, given the others' current poses."""
        B, c = self.B, self.C[ref]; out = []
        f = B.fp[ref]
        if c["owner"]:
            g = B.fp[c["owner"]]; nets = [n for _, n, k in c["pins"] if k != "nc"]
            opads = {n: [p for p in g.Pads() if p.GetNetname() == n] for n in nets}
            # owner pins on each net, closest pair first (decap across adjacent pins)
            chosen = {}
            main0 = next((n for _, n, k in c["pins"] if k == "power"), nets[0])
            if c.get("owner_pad"):        # decaps spread over the owner's pins on that rail (assign_owner_pads / ANCHOR)
                named = [p for p in g.Pads() if p.GetNumber() == c["owner_pad"]]
                if named and opads[main0]:
                    chosen[main0] = min(opads[main0], key=lambda p: math.dist(pxy(p), pxy(named[0])))
            for n in nets:
                if n in chosen: continue
                if not opads[n]:      # the named owner has no pin on this net (a GND via will do): pull outward only
                    continue
                others = [pxy(chosen[main0])] if main0 in chosen else [pxy(p) for m in nets if m != n for p in opads[m]]
                chosen[n] = min(opads[n], key=lambda p: min((math.dist(pxy(p), o) for o in others), default=0))
            # the main pin is the non-plane one (the decap's rail, the ESD diode's line); a plane pin is pulled to the
            # owner's pin on that net only when that pin is beside the main one (decap across adjacent pins), else it
            # just wants to sit outward, where its via goes (an ESD diode does not run to a connector's far GND pin)
            main = next((n for _, n, k in c["pins"] if k == "power"), nets[0])
            gc = pxy(g)
            if main not in chosen: return out
            for num, n, k in c["pins"]:
                if k == "nc" or n not in chosen: continue
                q = pxy(chosen[n]); qm = pxy(chosen[main])
                if k == "plane" and n != main and math.dist(q, qm) > 3.0:
                    ux, uy = qm[0] - gc[0], qm[1] - gc[1]; L = math.hypot(ux, uy) or 1
                    q = (qm[0] + 1.6 * ux / L, qm[1] + 1.6 * uy / L)
                    out.append((num, [(q, q)], W_OUT, "outward")); continue
                out.append((num, [(q, q)], W_OWNER, f"{c['owner']}.{chosen[n].GetNumber()}"))
            return out
        anchor_xy = None; anchor_c = None
        for num, n, k in c["pins"]:
            if k in ("signal", "power") and n.split("/")[-1] in {x.split("/")[-1] for x in c.get("force", {})}:
                fr, fp = next(v for x, v in c["force"].items() if x.split("/")[-1] == n.split("/")[-1])
                q = pxy(next(p for p in B.fp[fr].Pads() if p.GetNumber() == fp))
                out.append((num, [(q, q)], 2 * W_SIG, f"{fr}.{fp} (override)")); continue
            if k in ("signal", "power"):
                pts = self.terminals(n, ref)
                if not pts and k == "signal" and private(B, n):
                    # the rest of the chain isn't seated yet: face this pin toward where the chain ends up
                    far = self.chain_ends(ref, n)
                    if far: out.append((num, [(q, q) for q in far], W_OUT, "chain-direction"))
                    continue
                if not pts: continue
                segs = mst_segments(pts)
                w = W_SIG if k == "signal" else W_POWER
                if k == "signal" and all(r in B.mov for r, _ in B.netpads[n]): w = W_PRIV   # private net between two small parts
                out.append((num, segs, w, n))
                if B.region:     # tie-break along a long airwire: tap it near its in-region end, not halfway to the MCU
                    R = box(*B.region); loc = [q for q in pts if R.contains(Point(q))]
                    if loc and len(loc) < len(pts): out.append((num, [(q, q) for q in loc], W_LOCAL, "local"))
                fx = [x for x in B.fixed_pads(n, skip=(ref,)) if not x[0].startswith("TP")]
                if k == "signal" and len(fx) == 1 and anchor_xy is None:
                    anchor_xy = pxy(fx[0][1]); anchor_c = pxy(B.fp[fx[0][0]])
        if anchor_xy:      # plane pins: a little outward from the anchor's body, so their via lands outside
            ux, uy = anchor_xy[0] - anchor_c[0], anchor_xy[1] - anchor_c[1]; L = math.hypot(ux, uy) or 1
            q = (anchor_xy[0] + 1.6 * ux / L, anchor_xy[1] + 1.6 * uy / L)
            for num, n, k in c["pins"]:
                if k == "plane": out.append((num, [(q, q)], W_OUT, "outward"))
        return out

    def chain_ends(self, ref, net):
        """fixed pads (or seated parts' pads) reached by walking the chain from ref through net"""
        B = self.B; seen = {ref}; nets = [net]; out = []; done = set()
        while nets:
            n = nets.pop()
            if n in done: continue
            done.add(n)
            for r, p in B.netpads[n]:
                if r in seen: continue
                seen.add(r)
                for q in B.fp[r].Pads():
                    m = q.GetNetname()
                    if m == n or is_nc(m) or m in done: continue
                    if private(B, m): nets.append(m)
                    elif B.role(m, pxy(q)) == "signal":
                        out += [pxy(pp) for rr, pp in B.netpads[m] if rr not in B.mov]
        return out

    def cost_grid(self, ref, P, rot, T):
        pads = {n: off for n, _, off, _ in self.shape[ref].rot[rot][0]}
        tot = np.zeros(len(P))
        for num, segs, w, _ in T:
            if num in pads: tot += w * seg_dist(P + np.array(pads[num]), segs)
        return tot

    def cost_at(self, ref, x, y, rot, T=None):
        T = T if T is not None else self.targets(ref)
        return float(self.cost_grid(ref, np.array([[x, y]]), rot, T)[0])

    def geom(self, ref, x, y, rot):
        pads, c = self.shape[ref].rot[rot]
        return affinity.translate(c, x, y), [(affinity.translate(g, x, y) if g is not None else None, n) for _, n, _, g in pads]


def seat(M, L, ref, step=0.2, radius=8.0, max_tests=120000):
    """best legal pose for ref given everything else; returns (x, y, rot, cost, T) or None."""
    T = M.targets(ref)
    pts = [q for _, segs, w, _ in T for s in segs for q in s if w >= W_POWER]
    pts = pts or [q for _, segs, w, _ in T for s in segs for q in s]
    if not pts:
        x, y, rot = M.pos.get(ref) or (pxy(M.B.fp[ref]) + (M.B.fp[ref].GetOrientationDegrees() % 360,)); return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = min(xs) - radius, max(xs) + radius; y0, y1 = min(ys) - radius, max(ys) + radius
    if M.B.region:
        rx0, ry0, rx1, ry1 = M.B.region; x0, y0, x1, y1 = max(x0, rx0), max(y0, ry0), min(x1, rx1), min(y1, ry1)
        if (x1 - x0) * (y1 - y0) < 16 or x1 <= x0 or y1 <= y0:      # targets outside the region: search all of it
            x0, y0, x1, y1 = rx0, ry0, rx1, ry1
    def grid(x0, y0, x1, y1, st):
        gx = np.arange(round(x0 / st) * st, x1 + st / 2, st); gy = np.arange(round(y0 / st) * st, y1 + st / 2, st)
        return np.array([(x, y) for x in gx for y in gy])
    def scored(G, rots=(0, 90, 180, 270), keep=None):
        out = []
        for rot in rots:
            c = M.cost_grid(ref, G, rot, T); k = np.argsort(c)[:keep]
            out += [(float(c[i]), float(G[i][0]), float(G[i][1]), rot) for i in k]
        return sorted(out)
    G = grid(x0, y0, x1, y1, step)
    if len(G) == 0: return None
    if len(G) <= 30000:
        cands = scored(G)
    else:        # big window (a net that runs across the board): 1 mm coarse pass, then 0.2 mm round the best spots
        coarse = scored(grid(x0, y0, x1, y1, 1.0), keep=60)
        fine = {}
        for _, cx, cy, rot in coarse:
            for c, x, y, r in scored(grid(cx - 1.0, cy - 1.0, cx + 1.0, cy + 1.0, step), rots=(rot,)):
                fine[(round(x, 2), round(y, 2), r)] = c
        cands = sorted((c, x, y, r) for (x, y, r), c in fine.items()) + scored(grid(x0, y0, x1, y1, 0.5))
    for cost, x, y, rot in cands[:max_tests]:
        cg, pads = M.geom(ref, x, y, rot)
        if L.check(ref, cg, pads) is None:
            return (round(x, 2), round(y, 2), rot, cost, T)
    return None


# ---------------------------------------------------------------- metrics
def ratsnest(B, nets, M=None):
    """sum of MST lengths over each net's pads (seated poses if a model is given) and stub ends."""
    tot = 0.0; per = {}
    for n in nets:
        pts = []
        for r, p in B.netpads[n]:
            q = M.pad_xy(r, p.GetNumber()) if (M and r in B.mov) else pxy(p)
            if q is None: q = pxy(p)
            if B.stubs.get(n) and B.region and r not in B.mov and not box(*B.region).buffer(2).contains(Point(q)): continue
            pts.append(q)
        pts += [tuple(s) for s in B.stubs.get(n, [])]
        per[n] = mst_len(pts); tot += per[n]
    return tot, per


def area_nets(B):
    """nets the movable parts touch that are routed copper (not plane pours, not nc)."""
    out = set()
    for r in B.movable:
        for p in B.fp[r].Pads():
            n = p.GetNetname()
            if B.role(n, pxy(p)) in ("signal", "power"): out.add(n)
    return sorted(out)


def overlaps(B, refs=None):
    """courtyard overlaps on the same side, THT on both: any contact, as KiCad's DRC flags it (touching edges too)."""
    fps = [f for f in B.b.GetFootprints() if not B.region or box(*B.region).buffer(3).intersects(court(f))]
    cs = [(f.GetReference(), side_of(f), tht(f), court(f)) for f in fps]
    out = []
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            a, c = cs[i], cs[j]
            if a[1] != c[1] and not (a[2] or c[2]): continue
            if refs and a[0] not in refs and c[0] not in refs: continue
            if a[3].intersects(c[3]): out.append((a[0], c[0]))
    return out


# ---------------------------------------------------------------- commands
def cmd_select(a):
    b = pcbnew.LoadBoard(a.board); R = box(*a.region)
    for f in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        r = f.GetReference()
        if a.sheets and f.GetSheetname() not in a.sheets: continue
        if not R.contains(Point(pxy(f))) or f.IsLocked() or r.startswith("TP"): continue
        if SMALL.match(r) or (r.startswith("U") and SAT_IC.search(f.GetValue()) and len(f.Pads()) <= 10):
            print(r)


def cmd_classify(a):
    B = Board(a.board, read_refs(a.movable), a.region); C = classify(B)
    rows = []
    for r in order(C):
        c = C[r]; f = B.fp[r]
        pins = " ".join(f"{num}:{n.split('/')[-1]}[{k}]" for num, n, k in c["pins"])
        rows.append(dict(ref=r, value=f.GetValue(), role=c["role"], owner=c["owner"] or "", anchors=" ".join(c["anchors"]), pins=pins))
        print(f"{r:6s} {f.GetValue():12s} {c['role']:10s} owner={c['owner'] or '-':7s} anchors={','.join(c['anchors']) or '-':10s} {pins}")
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def cmd_rip(a):
    """rip the movable parts' routed nets inside the region (tracks with an end in it, vias in it), and their
    plane-pin taps; record where the remaining copper of each net leaves off (stubs) for the placer and router."""
    B = Board(a.board, read_refs(a.movable), a.region); b = B.b; R = box(*a.region)
    nets = set(area_nets(B)) - set(read_refs(a.keep_nets) if a.keep_nets else [])
    inside = lambda q: R.contains(Point(mm(q.x), mm(q.y)))
    mpads = [p for r in B.movable for p in B.fp[r].Pads()]
    gone = []; ends = collections.defaultdict(list)
    tracks = list(b.GetTracks())
    for t in tracks:
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            if n in nets and inside(t.GetPosition()): gone.append(t)
            continue
        s, e = t.GetStart(), t.GetEnd()
        if n in nets and (inside(s) or inside(e)):
            gone.append(t)
            for q in (s, e):
                if not inside(q): ends[n].append((round(mm(q.x), 3), round(mm(q.y), 3)))
        elif not t.IsLocked() or True:
            # plane-pin taps of movable parts: short track with an end on a movable pad
            if t.GetLength() <= pcbnew.FromMM(3.1) and any(p.GetNetCode() == t.GetNetCode() and (p.HitTest(s) or p.HitTest(e)) for p in mpads):
                gone.append(t)
    gone_ids = {x.m_Uuid.AsString() for x in gone}
    use = collections.Counter((q.x, q.y) for t in tracks if t.Type() != pcbnew.PCB_VIA_T and t.m_Uuid.AsString() not in gone_ids for q in (t.GetStart(), t.GetEnd()))
    tap_ends = {(q.x, q.y) for t in gone if t.Type() != pcbnew.PCB_VIA_T for q in (t.GetStart(), t.GetEnd())}
    for v in tracks:      # orphaned tap vias
        if v.Type() == pcbnew.PCB_VIA_T and v.m_Uuid.AsString() not in gone_ids and (v.GetPosition().x, v.GetPosition().y) in tap_ends \
                and use[(v.GetPosition().x, v.GetPosition().y)] == 0 and v.GetNetname() not in nets:
            gone.append(v); gone_ids.add(v.m_Uuid.AsString())
    # stub ends must still be on copper of that net (not a dead end inside another ripped piece)
    stubs = {n: sorted(set(map(tuple, v))) for n, v in ends.items()}
    nv = sum(1 for x in gone if x.Type() == pcbnew.PCB_VIA_T)
    q = lambda n: f'"{n}"' if " " in n else n
    rip = [f"# anchor_place.py rip: {len(gone) - nv} tracks, {nv} vias in region {a.region} (apply_edits.py format)"]
    for x in gone:
        if x.Type() == pcbnew.PCB_VIA_T:
            vx, vy = pxy(x); rip.append(f"DELETE {q(x.GetNetname())} via ({vx:.4f}, {vy:.4f})")
        else:
            s_, e_ = x.GetStart(), x.GetEnd()
            rip.append(f"DELETE {q(x.GetNetname())} track {x.GetLayerName()} ({mm(s_.x):.4f}, {mm(s_.y):.4f})-({mm(e_.x):.4f}, {mm(e_.y):.4f})")
    open(os.path.splitext(a.out)[0] + ".rip.txt", "w").write("\n".join(rip) + "\n")
    for x in gone: b.Remove(x)
    pcbnew.SaveBoard(a.out, b)
    json.dump(stubs, open(a.out + ".stubs.json", "w"), indent=1)
    open(os.path.splitext(a.out)[0] + ".nets", "w").write("\n".join(sorted(nets)) + "\n")
    print(f"ripped {len(gone) - nv} tracks and {nv} vias on {len(nets)} nets; {sum(map(len, stubs.values()))} stub ends on {len(stubs)} nets")


def read_overrides(path, C):
    """reviewer overrides: 'FIX REF' keeps a part where it is; 'ANCHOR REF NET REF2.PAD' pulls REF's pin on NET to
    that one pad (the end it belongs at: an ADC filter at the MCU pin, a terminator at the connector)."""
    if not path: return
    for line in open(path):
        w = line.split("#")[0].split()
        if not w or w[1] not in C: continue
        if w[0] == "FIX": C[w[1]]["role"] = "free"; C[w[1]]["fixed_by"] = "override"
        elif w[0] == "ANCHOR":
            ref2, pad = w[3].split(".", 1); c = C[w[1]]
            if c["owner"] or c["role"] in ("decap", "rail-esd", "rail-link", "rail-filter"):
                c["owner"] = ref2; c["owner_pad"] = pad; c["owner_fixed"] = True   # the IC this decap serves, per the schematic
            else:
                c.setdefault("force", {})[w[2]] = (ref2, pad)


def cmd_place(a):
    stubs = json.load(open(a.stubs)) if a.stubs else {}
    B = Board(a.board, read_refs(a.movable), a.region, stubs); C = classify(B); read_overrides(a.overrides, C)
    M = Model(B, C); seq = order(C)
    before = {r: (pxy(B.fp[r]), B.fp[r].GetOrientationDegrees() % 360) for r in B.movable}
    side = {side_of(B.fp[r]) for r in B.movable}
    Ls = {s: Legal(B, s) for s in ("F", "B")}
    Ls["F"].peers, Ls["B"].peers = [Ls["B"]], [Ls["F"]]
    nets = area_nets(B)
    # cost before (everything where it is)
    for r in B.movable: M.pos[r] = (before[r][0][0] - 0, before[r][0][1], int(round(before[r][1])) % 360)
    # the footprint origin can differ from the pad centroid; Shape offsets are about the origin, so M.pos is the origin
    rn0, _ = ratsnest(B, nets, M); cost0 = {r: M.cost_at(r, *M.pos[r]) for r in B.movable}
    print(f"before: ratsnest {rn0:.1f} mm over {len(nets)} nets, model cost {sum(cost0.values()):.1f}")
    # round 1: lift every part that is not already at its pin (--keep-good), seat in priority order
    keep = {r for r in B.movable if C[r]["role"] == "free"}     # no pin to belong to (a 0R between two rails): stays
    if a.keep_good > 0:
        for r in B.movable:
            d = anchor_dist(B, C, r)
            if d is not None and d <= a.keep_good: keep.add(r)
    assign_owner_pads(B, C, keep)
    for r in B.movable: M.pos[r] = None
    log = {}
    for r in sorted(keep):
        M.pos[r] = (before[r][0][0], before[r][0][1], int(round(before[r][1])) % 360)
        Ls[side_of(B.fp[r])].put(r, *M.geom(r, *M.pos[r])); log[r] = "kept (free)" if C[r]["role"] == "free" else "kept (already at its pin)"
    print(f"kept {len(keep)} parts (already within {a.keep_good} mm of their pin, or with no pin to belong to)")
    for r in seq:
        if r in keep: continue
        L = Ls[side_of(B.fp[r])]
        res = seat(M, L, r, radius=a.radius) or seat(M, L, r, radius=2 * a.radius)
        if res is None:
            x, y = before[r][0]; rot = int(round(before[r][1])) % 360; M.pos[r] = (x, y, rot)
            cg, pads = M.geom(r, x, y, rot); L.put(r, cg, pads); log[r] = "kept (no legal pose)"
            print(f"  {r:6s} KEPT where it was: no legal pose"); continue
        x, y, rot, cost, T = res; M.pos[r] = (x, y, rot); cg, pads = M.geom(r, x, y, rot); L.put(r, cg, pads)
        log[r] = "round 1"
        tg = ", ".join(f"{num}->{lab.split('/')[-1]}" for num, _, _, lab in T)
        print(f"  {r:6s} {C[r]['role']:10s} -> ({x:.2f},{y:.2f}) r{rot:3d} cost {cost:5.2f}  [{tg}]")
    rn1, _ = ratsnest(B, nets, M)
    print(f"round 1: ratsnest {rn1:.1f} mm")
    # rounds 2+: re-seat with all others in place, then same-footprint swaps
    for rd in range(2, (1 if a.only_round1 else a.rounds) + 1):
        gain = 0.0
        for r in seq:
            if C[r]["role"] == "free": continue
            L = Ls[side_of(B.fp[r])]; old = M.pos[r]; c_old = M.cost_at(r, *old)
            L.lift(r); M.pos[r] = None
            res = seat(M, L, r, radius=a.radius)
            M.pos[r] = old
            if res and res[3] < c_old - (0.5 if log.get(r, "").startswith("kept") else 0.05):
                M.pos[r] = res[:3]; gain += c_old - res[3]; log[r] = f"round {rd} re-seat"
            cg, pads = M.geom(r, *M.pos[r]); L.put(r, cg, pads)
        # swaps of identical footprints
        groups = collections.defaultdict(list)
        for r in B.movable:
            if C[r]["role"] != "free": groups[(B.fp[r].GetFPIDAsString(), side_of(B.fp[r]))].append(r)
        nsw = 0
        for key, rs in groups.items():
            L = Ls[key[1]]
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    p, q = rs[i], rs[j]; pp, pq = M.pos[p], M.pos[q]
                    if math.dist(pp[:2], pq[:2]) > 8: continue
                    c_old = M.cost_at(p, *pp) + M.cost_at(q, *pq)
                    best = None
                    for rp in (0, 90, 180, 270):
                        for rq in (0, 90, 180, 270):
                            M.pos[p], M.pos[q] = (pq[0], pq[1], rp), (pp[0], pp[1], rq)
                            c = M.cost_at(p, *M.pos[p]) + M.cost_at(q, *M.pos[q])
                            if best is None or c < best[0]: best = (c, rp, rq)
                    M.pos[p], M.pos[q] = pp, pq
                    if best[0] < c_old - 0.1:
                        L.lift(p); L.lift(q)
                        np_, nq = (pq[0], pq[1], best[1]), (pp[0], pp[1], best[2])
                        g1 = M.geom(p, *np_); g2 = M.geom(q, *nq)
                        ok = L.check(p, *g1) is None
                        if ok: L.put(p, *g1); ok = L.check(q, *g2) is None; L.lift(p)
                        if ok:
                            M.pos[p], M.pos[q] = np_, nq; gain += c_old - best[0]; nsw += 1; log[p] = log[q] = f"round {rd} swap"
                        L.put(p, *M.geom(p, *M.pos[p])); L.put(q, *M.geom(q, *M.pos[q]))
        rnk, _ = ratsnest(B, nets, M)
        print(f"round {rd}: model gain {gain:.1f}, {nsw} swaps, ratsnest {rnk:.1f} mm")
        if gain < 0.2: break
    # write
    b = B.b; plan = []; edits = []
    for r in seq:
        f = B.fp[r]; x, y, rot = M.pos[r]; was = f.IsLocked(); f.SetLocked(False)
        f.SetOrientationDegrees(rot); f.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))); f.SetLocked(was)
        (bx, by), brot = before[r]
        T = M.targets(r)
        plan.append(dict(ref=r, value=f.GetValue(), role=C[r]["role"], owner=C[r]["owner"] or "", anchors=" ".join(C[r]["anchors"]),
                         targets=" ".join(f"{num}->{lab.split('/')[-1]}" for num, _, _, lab in T),
                         x0=round(bx, 2), y0=round(by, 2), rot0=int(round(brot)), x1=x, y1=y, rot1=rot,
                         moved_mm=round(math.dist((bx, by), (x, y)), 2), cost0=round(cost0[r], 2), cost1=round(M.cost_at(r, x, y, rot), 2), how=log.get(r, "")))
        edits.append(f"MOVE {r} ({x:.3f}, {y:.3f}) rot {rot} side {side_of(f)}")
    keep = []; nvias = nvip = 0
    for s_ in Ls:
        for r, (_, _, vias) in Ls[s_].placed.items():
            lay = pcbnew.B_Cu if s_ == "B" else pcbnew.F_Cu
            for _, n, (vx, vy), (px, py), _, sw in vias:
                ni = b.FindNet(n); V = pcbnew.VECTOR2I(int(round(vx * MM)), int(round(vy * MM)))
                vip = sw < 0; d, dr = ((0.45, 0.2) if sw < -0.2 else (0.35, 0.15)) if vip else VIA
                via = pcbnew.PCB_VIA(b); via.SetPosition(V); via.SetWidth(pcbnew.FromMM(d)); via.SetDrill(pcbnew.FromMM(dr)); via.SetNet(ni)
                b.Add(via); keep.append(via); nvias += 1; nvip += vip
                edits.append(f"- {n} via {d}/{dr} at ({vx:.3f}, {vy:.3f})" + ("   # VIPPO" if vip else ""))
                if not vip:
                    tr = pcbnew.PCB_TRACK(b); tr.SetStart(pcbnew.VECTOR2I(int(round(px * MM)), int(round(py * MM)))); tr.SetEnd(V)
                    tr.SetWidth(pcbnew.FromMM(sw)); tr.SetLayer(lay); tr.SetNet(ni); b.Add(tr); keep.append(tr)
                    edits.append(f"- {n} {'B.Cu' if s_ == 'B' else 'F.Cu'} {sw:.2f}: ({px:.3f}, {py:.3f})-({vx:.3f}, {vy:.3f})")
    print(f"pin vias reserved and written: {nvias} ({nvip} in pad)")
    pcbnew.SaveBoard(a.out, b)
    rn, _ = ratsnest(B, nets, M)
    print(f"after: ratsnest {rn:.1f} mm (was {rn0:.1f}), model cost {sum(p['cost1'] for p in plan):.1f} (was {sum(cost0.values()):.1f})")
    if a.plan:
        with open(a.plan, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(plan[0])); w.writeheader(); w.writerows(plan)
    if a.edits:
        open(a.edits, "w").write(f"# anchor_place.py moves for {len(edits)} parts (apply_edits.py format)\n" + "\n".join(edits) + "\n")


def cmd_measure(a):
    stubs = json.load(open(a.stubs)) if a.stubs else {}
    B = Board(a.board, read_refs(a.movable), a.region, stubs); b = B.b; R = box(*a.region)
    nets = [l.strip() for l in open(a.nets)] if a.nets else area_nets(B)
    nset = set(nets)
    rn, per = ratsnest(B, nets)
    vias = trk = 0.0; nvia = 0; ntrk = 0
    for t in b.GetTracks():
        if t.GetNetname() not in nset: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            if R.contains(Point(pxy(t))): nvia += 1
        else:
            s, e = t.GetStart(), t.GetEnd(); ls = LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))])
            if ls.intersects(R): trk += ls.intersection(R).length; ntrk += 1
    # vias of every net inside the region (what the user sees)
    allv = sum(1 for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and R.contains(Point(pxy(t))))
    # opens: copper islands per net (pads, tracks, vias, zone fills) minus one
    opens = islands(b, nets)
    ov = overlaps(B)
    # L-39 audit on the movable parts: each power/ground pad needs its own via (in the pad, or a track from the pad to it)
    # (a same-net via within 0.8 mm of the pad edge, each via counted for one pad only; a pour joins them)
    vias = [(Point(pxy(t)), t.GetNetname(), i) for i, t in enumerate(b.GetTracks()) if t.Type() == pcbnew.PCB_VIA_T]
    used = set(); miss = []; served = 0
    for r in B.movable:
        f = B.fp[r]; sl = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
        for p in f.Pads():
            n = p.GetNetname()
            if n not in POWER: continue
            pg = polys(p.GetEffectivePolygon(sl, pcbnew.ERROR_INSIDE))
            near = sorted((pg.distance(v), i) for v, vn, i in vias if vn == n and i not in used and pg.distance(v) <= 0.8 + 0.3)
            if near: used.add(near[0][1]); served += 1
            else: miss.append(f"{r}.{p.GetNumber()}")
    d = dict(board=a.board, nets=len(nets), ratsnest_mm=round(rn, 1), area_net_vias=nvia, all_vias_in_region=allv,
             area_net_track_mm=round(trk, 1), opens=sum(opens.values()), open_nets={k: v for k, v in opens.items() if v},
             courtyard_overlaps=ov, pin_vias_served=served, pin_vias_missing=miss)
    print(json.dumps({k: v for k, v in d.items() if k != "open_nets"}))
    if a.json: json.dump(d, open(a.json, "w"), indent=1)


def islands(b, nets):
    CU = list(b.GetEnabledLayers().CuStack()); out = {}
    want = set(nets); items = {n: [] for n in nets}
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n in want:
                g = {l: polys(p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)) for l in CU if p.IsOnLayer(l) and p.FlashLayer(l)}
                items[n].append({l: x for l, x in g.items() if x is not None})
    for t in b.GetTracks():
        n = t.GetNetname()
        if n not in want: continue
        if t.Type() == pcbnew.PCB_VIA_T:
            g = Point(pxy(t)).buffer(mm(t.GetWidth(pcbnew.F_Cu)) / 2); items[n].append({l: g for l in CU})
        else:
            s, e = t.GetStart(), t.GetEnd()
            items[n].append({t.GetLayer(): LineString([(mm(s.x), mm(s.y)), (mm(e.x), mm(e.y))]).buffer(mm(t.GetWidth()) / 2 + 1e-4)})
    for z in b.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in want: continue
        for l in z.GetLayerSet().Seq():
            if l in CU and z.HasFilledPolysForLayer(l):
                g = polys(z.GetFilledPolysList(l))
                if g is not None: items[z.GetNetname()].append({l: g})
    for n, its in items.items():
        npad = sum(1 for r in b.GetFootprints() for p in r.Pads() if p.GetNetname() == n)
        par = list(range(len(its)))
        def fd(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        for l in CU:
            idx = [i for i, it in enumerate(its) if l in it]
            if len(idx) < 2: continue
            gs = [its[i][l] for i in idx]; tr = STRtree(gs)
            for ai, g in zip(idx, gs):
                for j in tr.query(g):
                    bj = idx[int(j)]
                    if bj != ai and fd(ai) != fd(bj) and g.intersects(its[bj][l]): par[fd(ai)] = fd(bj)
        # count islands that hold at least one pad
        roots = {fd(i) for i in range(npad)}
        out[n] = len(roots) - 1 if npad > 1 else 0
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def common(p, out=False, region=True):
        p.add_argument("board")
        if out: p.add_argument("out")
        p.add_argument("--movable"); p.add_argument("--stubs")
        p.add_argument("--power-nets", nargs="*"); p.add_argument("--hv"); p.add_argument("--floorplan"); p.add_argument("--via")
        if region: p.add_argument("--region", type=float, nargs=4, required=False)
        return p
    s = common(sp.add_parser("select")); s.add_argument("--sheets", nargs="*")
    s = common(sp.add_parser("classify")); s.add_argument("--csv")
    s = common(sp.add_parser("rip"), out=True); s.add_argument("--keep-nets", help="file of nets whose copper stays (critical paths)")
    s = common(sp.add_parser("place"), out=True); s.add_argument("--rounds", type=int, default=4); s.add_argument("--radius", type=float, default=8.0)
    s.add_argument("--plan"); s.add_argument("--edits"); s.add_argument("--only-round1", action="store_true")
    s.add_argument("--overrides", help="reviewer overrides file: FIX REF / ANCHOR REF NET REF2.PAD")
    s.add_argument("--keep-good", type=float, default=0.0, help="leave parts already within this many mm of their pin")
    s.add_argument("--held", help="held.json of routing reservations: active areas are no-part zones on their layers")
    s = common(sp.add_parser("measure")); s.add_argument("--json"); s.add_argument("--nets")
    a = ap.parse_args()
    global HELD, HVP, FLOORPLAN, VIA
    HELD = getattr(a, "held", None)
    POWER_GLOBS.extend(a.power_nets or []); FLOORPLAN = a.floorplan
    if a.hv: HVP = re.compile(a.hv)
    if a.via: VIA = tuple(float(x) for x in a.via.split("/"))
    {"select": cmd_select, "classify": cmd_classify, "rip": cmd_rip, "place": cmd_place, "measure": cmd_measure}[a.cmd](a)


if __name__ == "__main__":
    main()
