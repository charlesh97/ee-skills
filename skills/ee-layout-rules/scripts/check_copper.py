"""Copper hygiene that DRC passes and KiCadRoutingTools' check_weird misses.

Run it next to KRT's check_weird, not instead of it. check_weird already covers
exact duplicate segments, dangling ends and vias, and removable copper on nets
without a zone. This script covers the rest:

  via-off-center  L-33  a free track end inside a same-net via, not at its center (kind
                        "free"), or a track end attached to another track (a T) inside a
                        same-net via's pad, more than 0.01 mm from its center (kind "tee")
  via-over-pad    L-47  a via whose annular ring overlaps an SMD pad's copper, any net, the
                        via's own net included, with its center more than 0.02 mm from the
                        pad's center. A centered via-in-pad is via-in-pad's business (L-30);
                        an off-center one is a via over a pad. Prints the via position, net
                        and the pad
  pad-junction    L-48  a pad is a leaf: an SMD pad with more than one track exit (a track
                        end inside the pad whose other end is outside it), or with a T within
                        one pad length (the larger of its width and height) of its center on
                        its net and layer: a joint of three or more ends, or an end landing on
                        another track. Counted per pad (exits plus junction branches). FAIL
                        on a BGA / WLCSP ball (a pad under 0.3 mm), warn otherwise
  entry-vias      L-21  every power or ground pad (the pin-via net logic below) of a
                        connector (reference J*) has at least two vias of its net within
                        --entry-radius (1.0 mm) of the pad center. A plated through-hole pad
                        of the net counts as a via. Prints ref.pad, net and the count
  staircase       L-25  on a signal layer, a run of more than two connected segments of one
                        net that alternate between 0/90 and 45 degrees and are each shorter
                        than three track widths: a curve drawn as steps. Prints the run's
                        first point, net, layer and segment count
  jog             L-25  two bends within three track widths of each other whose net effect
                        is a lateral shift smaller than the Default class pitch (track width
                        plus clearance from the board's net settings)
  via-in-pad      L-30  a via whose annular ring overlaps an SMD pad's copper or a paste
                        aperture (F/B.Paste, the pad's own opening with its paste margin or
                        a paste-only window), on any net, the via's own net included: an
                        open via wicks solder out of the joint. FAIL when the ring overlaps
                        a paste aperture; warn when it overlaps only pad copper outside the
                        paste. Not reported, and listed as declared: a pad whose paste is
                        split into paste-only windows that the via clears (thermal vias in
                        an exposed pad's paste-window cross); a pad with no paste at all (a
                        bare test pad); a pad named in --allow-via-in-pad or on an
                        "allow-via-in-pad:" line of the routing spec (--routing-spec,
                        default review/routing/spec.md beside the board), which L-30 says
                        is filled and capped. Prints ref.pad, via size, position and net.
                        KiCad DRC passes a same-net via in a pad; this is the check that
                        doesn't (J1.MP of a JST GH on two encoder boards, 2026-10-04)
  overlap         L-34  two parallel same-net segments lying side by side along
                        their length, or one folded back over another (not exact
                        duplicates; check_weird's stacked-copper has those)
  loop            L-34  a same-layer track cycle on one net, after removing exact
                        duplicates. check_weird skips nets with a zone; this doesn't
  plane-track     L-35  track on a layer where the same net has a filled pour
  sharp-bend      L-25  a joint sharper than 90 degrees (a fold-back is an overlap)
  right-angle     L-25  a 90-degree joint
  odd-angle       L-25  track length that is neither H, V nor 45 degrees
  off-list-width  L-20  a track width in no net class and not in the predefined
                        list (read from the .kicad_pro beside the board)
  small-via       L-32  a via whose drill is smaller than the drc.json Default class via
                        (0.6/0.3 on rigid, the no-added-cost via). A warning: each one must
                        sit where the routing spec names the geometry that forced it
  direction       L-26  each signal layer's length by direction. With --directions,
                        a layer whose declared axis carries less than --min-axis of
                        its length fails. A plane layer may carry short signal hops
                        (the router prices them high, L-36), so there it fails a net
                        whose track on the plane is longer than --plane-max-run
  edge-margin     L-38  signal or power copper (track, via, pad, pour) closer to the
                        board edge than --edge-margin, on any layer. Pads of parts that
                        sit at the edge (connectors, modules, anything whose courtyard
                        reaches the band) and copper within --edge-margin of those pads
                        are exempt: that is the part's job, not the ring's
  edge-ring       L-38  GND copper coverage of the ring path, a line inside the edge
                        at the middle of the band, on each --ring-layers layer, from the
                        fills as saved. Under --ring-coverage fails; exempt stretches
                        (edge parts, mounting holes) count neither way
  edge-stitch     L-38  stretches of the ring with no GND via or GND through-hole in the
                        band within half of --stitch-pitch
  power-pin-via   L-39  a pad on a power net (a Power / PWR_* net class, or --power-nets;
                        ground excluded) with no via of its own: none in the pad, and none
                        within --pin-via-track mm of its own track. A through-hole pad is
                        its own via
  gnd-pin-via     L-39  the same for ground pads (--ground-nets). A warning: "where the
                        pitch allows"; a failure at --stage final
  shared-pin-via  L-39  one via serving as the only via of two or more power or ground pads
  pour-island     L-43  a fill island of a ground net (--ring-net and --ground-nets) of at
                        least stitch.min_island_mm2 with fewer than stitch.min_island_vias
                        vias of that net inside it (one via below stitch.two_via_mm2).
                        Fails only with --stage final; a warning before the stitching pass. A through-hole pad of the net counts as a
                        via. Islands are taken from the union of the net's fills on the
                        layer, so stacked zones count once
  pour-fill       L-43  a ground-net zone whose fill, on one layer, is under
                        stitch.min_fill_ratio of its outline
  pour-split      L-43  a ground layer whose two largest fill islands are each at least
                        100 mm2: the pour is cut in two. Reports the island count, the largest
                        island's share, and the track that splits them when one does.
                        Heuristic: an other-net track on the layer counts as the splitter when
                        it lies within (the larger of its own and the zone's clearance) +
                        0.05 mm of BOTH islands, i.e. the islands' outlines come within about
                        2 x clearance + track width of each other with that track in the gap.
                        A split made by several parallel tracks, another net's pour or a
                        keepout names no track
  zone-overlap    L-43  two zones of the same net on the same layer whose outlines overlap
                        (a stacked, redundant pour; the higher priority one wins the copper,
                        and the other shows a misleadingly small fill)
  stitch-group    L-43  free vias of the stitch net at the stitch size (no track on them, not
                        in a pad) outside the stitch.group group: likely stitching that
                        stitch.py remove would miss before a re-route. With --stage final, also
                        a board with pours of the stitch net and no group. Before final a missing
                        group is expected (stitching is the last pass) and is not reported

Fails (exit 1): via-off-center, via-over-pad, via-in-pad in a paste aperture, pad-junction on a ball, overlap,
loop, sharp-bend, entry-vias, edge-ring, power-pin-via, pour-island and gnd-pin-via at --stage final,
direction when --directions is given, and edge-margin when
edge_ring.margin_severity is "fail" or --edge-margin-fail is given. edge-margin is a
warning by default: whether the band must be clear depends on the board. The rest are
warnings with counts, because some are sometimes right (a 90-degree bend into a pad, a
short stub on a plane layer). Exit 0 otherwise.

Run with KiCad's bundled python ($KPY):
  check_copper.py board.kicad_pcb [--profile rigid|flex] [--stage routed|final]
                  [--directions F.Cu=H,In1.Cu=plane,In2.Cu=V,B.Cu=H]
                  [--min-axis 0.6] [--plane-max-run 3] [--json out.json] [--list 5]
                  [--edge-margin 1.0] [--edge-margin-fail] [--ring-net GND] [--ring-layers F.Cu,B.Cu]
                  [--ring-coverage 0.9] [--stitch-pitch 5]
                  [--pin-via-track 1.5] [--power-nets N,..] [--ground-nets GND] [--entry-radius 1.0]
                  [--no-pours] [--std-via-drill 0.3]
                  [--allow-via-in-pad U1.33,TP1.1] [--routing-spec review/routing/spec.md]

The edge, pin-via, pour and via-size defaults come from rules/drc.json (edge_ring, pin_vias,
stitch and netclasses.Default of --profile, rigid by default). --edge-margin 0 skips the edge checks; the routing
spec must then say why (L-38: a board too small for a ring, or an outline that is all
connector). --no-pours skips the L-43 checks. Fills are read as saved: refill and save
first (kicad-cli pcb drc --refill-zones --save-board, on a copy if need be).

Directions are H, V, plane or any. 45-degree length counts against a layer's
axis: lanes run on the axis, and 45s are for bends and short jogs.
"""
import argparse
import collections
import glob
import json
import math
import os
import sys

import re

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stitch import smd_pad_areas  # noqa: E402

FAILS = ("via-off-center", "via-over-pad", "via-in-pad", "pad-junction", "overlap", "loop", "sharp-bend", "direction",
         "entry-vias", "edge-ring", "power-pin-via", "pour-island")
PROMOTABLE = ("edge-margin",)  # warn by default; FAIL with edge_ring.margin_severity "fail" or --edge-margin-fail
SPLIT_MIN_MM2 = 100.0          # pour-split: both of the two largest islands at least this big
TOL_NM = 1000          # 1 um: same point, centered, exact duplicate
MIN_OVERLAP_MM = 0.2   # side-by-side run shorter than this is a joint, not an overlap
TEE_OFF_MM = 0.01      # via-off-center: a T inside a via's pad further than this from its center
VIA_OVER_PAD_MM = 0.02  # via-over-pad: a via further than this from the pad center is not a via-in-pad
BALL_MM = 0.3          # pad-junction: a pad under this is a BGA / WLCSP ball
STEP_WIDTHS = 3        # staircase / jog: a segment or bend spacing under this many track widths is short


def mm(v):
    return round(pcbnew.ToMM(v), 3)


def pt(p):
    return [mm(p.x), mm(p.y)]


def axis(t):
    dx, dy = t.GetEnd().x - t.GetStart().x, t.GetEnd().y - t.GetStart().y
    if abs(dy) <= TOL_NM:
        return "H"
    if abs(dx) <= TOL_NM:
        return "V"
    if abs(abs(dx) - abs(dy)) <= 2 * TOL_NM:
        return "45"
    return "other"


def seg_key(t):
    a, b = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
    return (t.GetNetCode(), t.GetLayer()) + tuple(sorted([a, b]))


def allowed_widths(board_path):
    """Net-class widths and the predefined list from the .kicad_pro, in nm."""
    pro = os.path.splitext(board_path)[0] + ".kicad_pro"
    if not os.path.exists(pro):
        found = glob.glob(os.path.join(os.path.dirname(board_path) or ".", "*.kicad_pro"))
        if len(found) != 1:
            return None
        pro = found[0]
    d = json.load(open(pro))
    ws = set(d.get("board", {}).get("design_settings", {}).get("track_widths", []))
    for c in d.get("net_settings", {}).get("classes", []):
        for k in ("track_width", "diff_pair_width"):
            if c.get(k):
                ws.add(c[k])
    return {pcbnew.FromMM(w) for w in ws if w}


def same_pt(a, b):
    return a.x == b.x and a.y == b.y


def tee_ends(uniq, joints):
    """Keys (net, layer, x, y) of every track end attached to another track: a joint of three or
    more ends, or an end lying on the copper of another same-net, same-layer segment's interior."""
    out = {k for k, lst in joints.items() if len(lst) >= 3}
    by_nl = collections.defaultdict(list)
    for t in uniq:
        by_nl[(t.GetNetCode(), t.GetLayer())].append(t)
    for key, lst in joints.items():
        if key in out:
            continue
        net, layer, x, y = key
        own = {id(t) for t, _ in lst}
        for t in by_nl[(net, layer)]:
            if id(t) in own:
                continue
            a, c = t.GetStart(), t.GetEnd()
            dx, dy = c.x - a.x, c.y - a.y
            L2 = dx * dx + dy * dy
            if L2 == 0:
                continue
            u = ((x - a.x) * dx + (y - a.y) * dy) / L2
            if u <= 0.0 or u >= 1.0:
                continue                           # at an end: that is a joint, counted above
            if math.hypot(x - (a.x + u * dx), y - (a.y + u * dy)) <= t.GetWidth() / 2:
                out.add(key)
                break
    return out


def chains(uniq, joints):
    """Runs of segments joined end to end through two-ended joints, each as its ordered point
    list and segment list, per net and layer. A branch or a free end ends a run."""
    deg2 = {k for k, lst in joints.items() if len(lst) == 2}
    seen = set()
    out = []

    def key(t, p):
        return (t.GetNetCode(), t.GetLayer(), p.x, p.y)

    for t in uniq:
        if id(t) in seen or t.GetLength() == 0:
            continue
        seen.add(id(t))
        chain = [t]
        for forward in (True, False):
            cur, p = t, (t.GetEnd() if forward else t.GetStart())
            while True:
                k = key(cur, p)
                if k not in deg2:
                    break
                nxt = [(tt, q) for tt, q in joints[k] if tt is not cur]
                if not nxt or id(nxt[0][0]) in seen:
                    break
                tt, q = nxt[0]
                seen.add(id(tt))
                if forward:
                    chain.append(tt)
                else:
                    chain.insert(0, tt)
                cur, p = tt, q
        pts = []
        for i, sg in enumerate(chain):
            a, c = sg.GetStart(), sg.GetEnd()
            if i == 0:
                if len(chain) > 1 and (same_pt(a, chain[1].GetStart()) or same_pt(a, chain[1].GetEnd())):
                    a, c = c, a
                pts = [a, c]
            else:
                pts.append(c if same_pt(a, pts[-1]) else a)
        out.append((chain, pts))
    return out


def default_pitch(board):
    """Default class track width + clearance, nm, from the board's net settings."""
    d = board.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    return d.GetTrackWidth() + d.GetClearance()


def check(board, board_path, directions, min_axis, plane_max_run):
    F = collections.defaultdict(list)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = collections.defaultdict(list)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias[t.GetNetCode()].append(t)

    # exact duplicates are check_weird's stacked-copper; drop them before the rest
    seen, uniq = set(), []
    for t in tracks:
        k = seg_key(t)
        if k not in seen:
            seen.add(k)
            uniq.append(t)

    joints = collections.defaultdict(list)  # (net, layer, x, y) -> [(track, other end)]
    for t in uniq:
        for p, q in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            joints[(t.GetNetCode(), t.GetLayer(), p.x, p.y)].append((t, q))

    # via-off-center (L-33): a free end, or a T, inside a same-net via's pad but not at its center
    tees = tee_ends(uniq, joints)
    for (net, layer, x, y), lst in joints.items():
        if len(lst) == 1:
            kind, off = "free", TOL_NM
        elif (net, layer, x, y) in tees:
            kind, off = "tee", pcbnew.FromMM(TEE_OFF_MM)
        else:
            continue
        t = lst[0][0]
        for v in vias[net]:
            if not v.IsOnLayer(layer):
                continue
            c = v.GetPosition()
            d = math.hypot(x - c.x, y - c.y)
            if d <= v.GetWidth(layer) / 2:
                if d > off:
                    F["via-off-center"].append({"net": t.GetNetname(), "layer": t.GetLayerName(),
                                                "at": pt(c), "size_mm": mm(d), "kind": kind,
                                                "why": f"{kind} end {mm(d)} mm off the via center"})
                break

    # sharp-bend / right-angle (L-25)
    for (net, layer, x, y), lst in joints.items():
        if len(lst) != 2:
            continue
        (t1, q1), (t2, q2) = lst
        v1, v2 = (q1.x - x, q1.y - y), (q2.x - x, q2.y - y)
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < TOL_NM or n2 < TOL_NM:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))))
        if ang < 5:
            # folded back over itself: one segment lies on the other. Longer runs
            # are caught by the side-by-side test below, so only count short ones here
            if min(n1, n2) > pcbnew.FromMM(MIN_OVERLAP_MM):
                continue
            F["overlap"].append({"net": t1.GetNetname(), "layer": t1.GetLayerName(),
                                 "at": [mm(x), mm(y)], "size_mm": mm(min(n1, n2))})
        elif ang < 89:
            F["sharp-bend"].append({"net": t1.GetNetname(), "layer": t1.GetLayerName(),
                                    "at": [mm(x), mm(y)], "size_mm": round(ang)})
        elif ang <= 91:
            F["right-angle"].append({"net": t1.GetNetname(), "layer": t1.GetLayerName(),
                                     "at": [mm(x), mm(y)], "size_mm": 90})

    # overlap (L-34): parallel, side by side, sharing a run longer than MIN_OVERLAP_MM
    by_nl = collections.defaultdict(list)
    for t in uniq:
        if t.GetLength() > pcbnew.FromMM(MIN_OVERLAP_MM):
            by_nl[(t.GetNetCode(), t.GetLayer())].append(t)
    for ts in by_nl.values():
        for i, a in enumerate(ts):
            ax, ay = a.GetStart().x, a.GetStart().y
            ux, uy = a.GetEnd().x - ax, a.GetEnd().y - ay
            la = math.hypot(ux, uy)
            ux, uy = ux / la, uy / la
            for b in ts[i + 1:]:
                vx, vy = b.GetEnd().x - b.GetStart().x, b.GetEnd().y - b.GetStart().y
                lb = math.hypot(vx, vy)
                if abs(ux * vy - uy * vx) / lb > 0.02:
                    continue
                # b's ends in a's frame: s along a, n across a
                s1 = (b.GetStart().x - ax) * ux + (b.GetStart().y - ay) * uy
                s2 = (b.GetEnd().x - ax) * ux + (b.GetEnd().y - ay) * uy
                n = abs(-(b.GetStart().x - ax) * uy + (b.GetStart().y - ay) * ux)
                run = min(la, max(s1, s2)) - max(0, min(s1, s2))
                if run > pcbnew.FromMM(MIN_OVERLAP_MM) and n < (a.GetWidth() + b.GetWidth()) / 2:
                    m = max(0, min(s1, s2)) + run / 2
                    F["overlap"].append({"net": a.GetNetname(), "layer": a.GetLayerName(),
                                         "at": [mm(ax + ux * m), mm(ay + uy * m)], "size_mm": mm(run)})

    # loop (L-34): union-find over each net's track graph on one layer
    parent = {}

    def root(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for t in uniq:
        a = root((t.GetNetCode(), t.GetLayer(), t.GetStart().x, t.GetStart().y))
        b = root((t.GetNetCode(), t.GetLayer(), t.GetEnd().x, t.GetEnd().y))
        if a == b:
            F["loop"].append({"net": t.GetNetname(), "layer": t.GetLayerName(),
                              "at": pt(t.GetStart()), "size_mm": mm(t.GetLength())})
        else:
            parent[a] = b

    # plane-track (L-35)
    poured = collections.defaultdict(set)
    for z in board.Zones():
        if z.IsFilled() and not z.GetIsRuleArea():
            for layer in z.GetLayerSet().CuStack():
                poured[z.GetNetCode()].add(layer)
    for t in uniq:
        if t.GetLayer() in poured.get(t.GetNetCode(), ()):
            F["plane-track"].append({"net": t.GetNetname(), "layer": t.GetLayerName(),
                                     "at": pt(t.GetStart()), "size_mm": mm(t.GetLength())})

    # staircase / jog (L-25): on signal layers, over runs of segments joined through 2-ended joints
    plane_layers = {board.GetLayerID(l) for l, w in (directions or {}).items() if w == "plane"}
    pitch = default_pitch(board)
    for chain, pts in chains(uniq, joints):
        t0 = chain[0]
        if t0.GetLayer() in plane_layers or t0.GetLayer() in poured.get(t0.GetNetCode(), ()):
            continue
        cls = []
        for sg in chain:
            k = axis(sg)
            short = sg.GetLength() < STEP_WIDTHS * sg.GetWidth()
            cls.append(("O" if k in ("H", "V") else "D") if short and k != "other" else None)
        run = []

        def flush(run):
            if len(run) > 2:
                a = pts[run[0]]
                F["staircase"].append({"net": t0.GetNetname(), "layer": t0.GetLayerName(), "at": pt(a),
                                       "size_mm": len(run),
                                       "why": f"{len(run)} short 0/90 and 45 steps from ({mm(a.x)}, {mm(a.y)})"})

        for i, c in enumerate(cls):
            if c and (not run or cls[run[-1]] != c):
                run.append(i)
            else:
                flush(run)
                run = [i] if c else []
        flush(run)
        for i in range(len(chain) - 2):
            A, B, C = chain[i], chain[i + 1], chain[i + 2]
            if B.GetLength() >= STEP_WIDTHS * max(A.GetWidth(), B.GetWidth(), C.GetWidth()):
                continue
            ux, uy = pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y
            wx, wy = pts[i + 3].x - pts[i + 2].x, pts[i + 3].y - pts[i + 2].y
            la, lc = math.hypot(ux, uy), math.hypot(wx, wy)
            if la < TOL_NM or lc < TOL_NM:
                continue
            if abs(ux * wy - uy * wx) / (la * lc) > 0.02 or ux * wx + uy * wy <= 0:
                continue                           # not parallel, or folded back (overlap)
            shift = abs(ux * (pts[i + 2].y - pts[i].y) - uy * (pts[i + 2].x - pts[i].x)) / la
            if TOL_NM < shift < pitch:
                F["jog"].append({"net": t0.GetNetname(), "layer": t0.GetLayerName(), "at": pt(pts[i + 1]),
                                 "size_mm": mm(shift),
                                 "why": f"two bends {mm(B.GetLength())} mm apart shift the lane by {mm(shift)} mm "
                                        f"(under the {mm(pitch)} mm Default pitch)"})

    # off-list-width (L-20)
    ok = allowed_widths(board_path)
    if ok is not None:
        for t in uniq:
            if not any(abs(t.GetWidth() - w) <= TOL_NM for w in ok):
                F["off-list-width"].append({"net": t.GetNetname(), "layer": t.GetLayerName(),
                                            "at": pt(t.GetStart()), "size_mm": mm(t.GetWidth())})

    # odd-angle and direction (L-25, L-26); plane nets' own copper is plane-track, not a lane
    per_layer = collections.defaultdict(lambda: collections.Counter())
    per_net_layer = collections.Counter()
    for t in uniq:
        if t.GetLayer() not in poured.get(t.GetNetCode(), ()):
            per_net_layer[(t.GetLayerName(), t.GetNetname())] += pcbnew.ToMM(t.GetLength())
    for t in uniq:
        k = axis(t)
        if k == "other":
            F["odd-angle"].append({"net": t.GetNetname(), "layer": t.GetLayerName(),
                                   "at": pt(t.GetStart()), "size_mm": mm(t.GetLength())})
        if t.GetLayer() not in poured.get(t.GetNetCode(), ()):
            per_layer[t.GetLayerName()][k] += pcbnew.ToMM(t.GetLength())
    table = {}
    for layer in [board.GetLayerName(l) for l in board.GetEnabledLayers().CuStack()]:
        c = per_layer.get(layer, collections.Counter())
        total = sum(c.values())
        want = (directions or {}).get(layer)
        row = {k: round(c[k], 1) for k in ("H", "V", "45", "other")}
        row["total"] = round(total, 1)
        row["declared"] = want
        if want in ("H", "V"):
            row["axis_share"] = round(c[want] / total, 2) if total else None
            if total and c[want] / total < min_axis:
                F["direction"].append({"net": "-", "layer": layer, "at": None, "size_mm": row["axis_share"],
                                       "why": f"{want} carries {row['axis_share']:.0%} of {total:.0f} mm, under {min_axis:.0%}"})
        elif want == "plane" and total > 0:
            row["hops"] = sum(1 for (l, _), v in per_net_layer.items() if l == layer)
            for (l, net), run in per_net_layer.items():
                if l == layer and run > plane_max_run:
                    F["direction"].append({"net": net, "layer": layer, "at": None, "size_mm": round(run, 2),
                                           "why": f"{run:.1f} mm of signal on the plane, over {plane_max_run} mm"})
        table[layer] = row
    return F, table


# ------------------------------------------------------------------ L-38 edge ground ring
def edge_defaults(profile="rigid"):
    return rules_block("edge_ring", {"margin_mm": 1.0, "stitch_pitch_mm": 5.0, "coverage": 0.9,
                                     "margin_severity": "warn"}, profile)


def edge_samples(board, step_mm):
    """Points every step_mm along every Edge.Cuts item, with the unit tangent there."""
    out = []
    items = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    for fp in board.GetFootprints():
        items += [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.Edge_Cuts]
    step = pcbnew.FromMM(step_mm)
    for d in items:
        s = d.GetShape()
        if s == pcbnew.SHAPE_T_SEGMENT:
            polys = [[d.GetStart(), d.GetEnd()]]
        elif s == pcbnew.SHAPE_T_RECTANGLE:
            a, b = d.GetStart(), d.GetEnd()
            c = [pcbnew.VECTOR2I(a.x, a.y), pcbnew.VECTOR2I(b.x, a.y), pcbnew.VECTOR2I(b.x, b.y), pcbnew.VECTOR2I(a.x, b.y)]
            polys = [c + [c[0]]]
        elif s in (pcbnew.SHAPE_T_ARC, pcbnew.SHAPE_T_CIRCLE):
            c = d.GetCenter()
            r = d.GetRadius()
            if s == pcbnew.SHAPE_T_CIRCLE:
                a0, sweep = 0.0, 2 * math.pi
            else:
                a0 = math.atan2(d.GetStart().y - c.y, d.GetStart().x - c.x)
                a1 = math.atan2(d.GetEnd().y - c.y, d.GetEnd().x - c.x)
                am = math.atan2(d.GetArcMid().y - c.y, d.GetArcMid().x - c.x)
                sweep = (a1 - a0) % (2 * math.pi)
                if (am - a0) % (2 * math.pi) > sweep:
                    sweep -= 2 * math.pi
            n = max(8, int(abs(sweep) * r / step) + 1)
            polys = [[pcbnew.VECTOR2I(int(c.x + r * math.cos(a0 + sweep * i / n)), int(c.y + r * math.sin(a0 + sweep * i / n)))
                      for i in range(n + 1)]]
        elif s == pcbnew.SHAPE_T_POLY:
            ol = d.GetPolyShape().Outline(0)
            c = [ol.CPoint(i) for i in range(ol.PointCount())]
            polys = [c + [c[0]]]
        else:
            continue
        for pl in polys:
            for a, b in zip(pl, pl[1:]):
                L = math.hypot(b.x - a.x, b.y - a.y)
                if L == 0:
                    continue
                tx, ty = (b.x - a.x) / L, (b.y - a.y) / L
                n = max(1, int(L / step))
                for i in range(n):
                    out.append((a.x + (b.x - a.x) * i / n, a.y + (b.y - a.y) * i / n, tx, ty))
    return out


def edge_checks(board, margin_mm, ring_net, ring_layers, coverage_min, stitch_pitch_mm):
    F = collections.defaultdict(list)
    info = {}
    if margin_mm <= 0:
        return F, {"skipped": "--edge-margin 0"}
    M = pcbnew.FromMM(margin_mm)
    gnd = board.FindNet(ring_net)
    gnd_code = gnd.GetNetCode() if gnd else -1
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    edges = [d.GetEffectiveShape() for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    cu = list(board.GetEnabledLayers().CuStack())

    # edge parts: a footprint whose courtyard touches or crosses the outline (edge connector, overhanging
    # module, header). A part merely near the edge is not one: its pads in the band are edge-margin findings.
    edge_pads = []
    for fp in board.GetFootprints():
        if all(p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH for p in fp.Pads()):
            continue                                  # mounting holes: exempt as holes below
        crt = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
        if crt.OutlineCount():
            touches = any(crt.Collide(e, 0) for e in edges)
        else:
            touches = any(p.GetEffectiveShape(l).Collide(e, 0) for p in fp.Pads() for l in cu if p.IsOnLayer(l) for e in edges)
        if touches:
            edge_pads += [p for p in fp.Pads()]
    holes = [p for fp in board.GetFootprints() for p in fp.Pads()
             if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    info["edge_parts"] = sorted({p.GetParentFootprint().GetReference() for p in edge_pads})

    def exempt_item(sh, layer):
        return any(p.IsOnLayer(layer) and sh.Collide(p.GetEffectiveShape(layer), M) for p in edge_pads)

    def near_edge(sh):
        return any(sh.Collide(e, M) for e in edges)

    # edge-margin: signal / power copper in the band
    for t in board.GetTracks():
        if t.GetNetCode() == gnd_code:
            continue
        for layer in ([t.GetLayer()] if t.GetClass() != "PCB_VIA" else cu):
            if not t.IsOnLayer(layer):
                continue
            sh = t.GetEffectiveShape(layer)
            if near_edge(sh) and not exempt_item(sh, layer):
                F["edge-margin"].append({"net": t.GetNetname(), "layer": board.GetLayerName(layer),
                                         "at": pt(t.GetStart() if t.GetClass() != "PCB_VIA" else t.GetPosition()),
                                         "size_mm": margin_mm, "why": f"{t.GetClass()[4:].lower()} in the {margin_mm} mm band"})
                break
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p in edge_pads or p.GetNetCode() == gnd_code or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            for layer in cu:
                if p.IsOnLayer(layer) and near_edge(p.GetEffectiveShape(layer)):
                    F["edge-margin"].append({"net": p.GetNetname(), "layer": board.GetLayerName(layer),
                                             "at": pt(p.GetPosition()), "size_mm": margin_mm,
                                             "why": f"pad {fp.GetReference()}.{p.GetNumber()} in the band"})
                    break
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() == gnd_code:
            continue
        for layer in cu:
            if z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer):
                fill = z.GetFilledPolysList(layer)
                if fill.OutlineCount() and any(fill.Collide(e, M) for e in edges):
                    F["edge-margin"].append({"net": z.GetNetname(), "layer": board.GetLayerName(layer), "at": None,
                                             "size_mm": margin_mm, "why": f"pour '{z.GetZoneName()}' in the band"})

    # edge-ring: GND coverage of the path at the middle of the band, fills as saved
    ec = pcbnew.ToMM(board.GetDesignSettings().m_CopperEdgeClearance)
    inset = pcbnew.FromMM((ec + margin_mm) / 2)
    pts = []
    for x, y, tx, ty in edge_samples(board, 0.5):
        for sgn in (1, -1):
            q = pcbnew.VECTOR2I(int(x - sgn * ty * inset), int(y + sgn * tx * inset))
            if outline.Contains(q):
                pts.append(q)
                break
    ex = []
    for q in pts:
        pad_ex = any(p.GetBoundingBox().Distance(q) < M for p in edge_pads)
        hole_ex = any(math.hypot(q.x - h.GetPosition().x, q.y - h.GetPosition().y) < h.GetDrillSize().x / 2 + M for h in holes)
        ex.append(pad_ex or hole_ex)
    gnd_zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetCode() == gnd_code]
    gnd_tracks = [t for t in board.GetTracks() if t.GetNetCode() == gnd_code]
    gnd_pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gnd_code]
    unfilled = [z.GetZoneName() for z in gnd_zones if not any(z.HasFilledPolysForLayer(l) for l in cu if z.IsOnLayer(l))]
    info["ring"] = {}
    info["ring_samples"] = {"path": len(pts), "exempt": sum(ex)}
    for lname in ring_layers:
        layer = board.GetLayerID(lname)
        fills = [z.GetFilledPolysList(layer) for z in gnd_zones if z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer)]
        cov, gaps, run = 0, [], None
        n = 0
        for q, e in zip(pts, ex):
            if e:
                run = None
                continue
            n += 1
            hit = any(f.Contains(q) for f in fills) or \
                any(t.IsOnLayer(layer) and t.HitTest(q) for t in gnd_tracks) or \
                any(p.IsOnLayer(layer) and p.HitTest(q) for p in gnd_pads)
            if hit:
                cov += 1
                run = None
            else:
                if run is None:
                    run = [q, 0]
                    gaps.append(run)
                run[1] += 0.5
        if n == 0:
            info["ring"][lname] = None               # every point exempt: nothing to grade
            continue
        share = cov / n
        info["ring"][lname] = round(share, 3)
        if share < coverage_min:
            for g in sorted(gaps, key=lambda g: -g[1])[:20]:
                F["edge-ring"].append({"net": ring_net, "layer": lname, "at": pt(g[0]), "size_mm": round(g[1], 1),
                                       "why": f"{g[1]:.1f} mm of ring with no {ring_net} (layer {share:.0%} covered, "
                                              f"needs {coverage_min:.0%})"})
    if unfilled:
        info["unfilled_zones"] = unfilled

    # edge-stitch: ring stretches with no GND via / through-hole in the band within half the pitch
    band_vias = [v.GetPosition() for v in gnd_tracks if v.GetClass() == "PCB_VIA" and near_edge(v.GetEffectiveShape(cu[0]))]
    band_vias += [p.GetPosition() for p in gnd_pads if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and near_edge(p.GetEffectiveShape(cu[0]))]
    half = pcbnew.FromMM(stitch_pitch_mm / 2)
    run = None
    for q, e in zip(pts, ex):
        far = not e and all(math.hypot(q.x - v.x, q.y - v.y) > half for v in band_vias)
        if far:
            if run is None:
                run = [q, 0]
                F["edge-stitch"].append(run)
            run[1] += 0.5
        else:
            run = None
    F["edge-stitch"] = [{"net": ring_net, "layer": "-", "at": pt(r[0]), "size_mm": round(r[1] + stitch_pitch_mm, 1),
                         "why": f"about {r[1] + stitch_pitch_mm:.1f} mm of ring between stitching vias (pitch {stitch_pitch_mm} mm)"}
                        for r in F["edge-stitch"] if r[1] > 0]
    info["stitch_vias_in_band"] = len(band_vias)
    return F, info


# ------------------------------------------------------------------ L-39 a via for every power and ground pin
def rules_block(name, fallback, profile="rigid"):
    try:
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rules", "drc.json")))
        return d["profiles"][profile][name]
    except Exception:
        return fallback


def via_size_checks(board, std_drill_mm):
    """small-via (L-32): vias drilled smaller than the house default via, with a count per size."""
    F = collections.defaultdict(list)
    std = pcbnew.FromMM(std_drill_mm)
    sizes = collections.Counter()
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        size = (mm(v.GetWidth(pcbnew.F_Cu)), mm(v.GetDrill()))
        sizes[size] += 1
        if v.GetDrill() < std - TOL_NM:
            F["small-via"].append({"net": v.GetNetname(), "layer": "-", "at": pt(v.GetPosition()),
                                   "size_mm": size[1],
                                   "why": f"{size[0]}/{size[1]} via, drill under the house {std_drill_mm}"})
    return F, dict(sizes)


def spec_allow_list(path):
    """REF.PAD names from "allow-via-in-pad:" lines of the routing spec (markdown or yaml)."""
    out = set()
    if not path or not os.path.exists(path):
        return out
    for line in open(path):
        m = re.search(r"allow[-_ ]via[-_ ]in[-_ ]pad\W*?[:=]\s*(.*)", line, re.I)
        if m:
            for tok in re.split(r"[\s,;\[\]`*]+", m.group(1)):
                if re.fullmatch(r"[A-Za-z][\w-]*\.[\w-]+", tok.strip(".")):
                    out.add(tok.strip("."))
    return out


def via_in_pad_checks(board, allowed):
    """via-in-pad (L-30): vias whose annular ring overlaps an SMD land or a paste aperture, any net."""
    F = collections.defaultdict(list)
    areas = smd_pad_areas(board)
    info = {"declared": collections.Counter(), "paste-window": collections.Counter(), "bare": collections.Counter()}
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        P = v.GetPosition()
        hits = []
        for a in areas:
            if not v.IsOnLayer(a["cu"]):
                continue
            R = v.GetWidth(a["cu"]) // 2 - TOL_NM          # touching is not overlapping
            if a["bbox"].Distance(P) <= R and a["poly"].Collide(P, R):
                hits.append(a)
        if not hits:
            continue
        live = [a for a in hits if a["name"] not in allowed]
        for a in hits:
            if a["name"] in allowed and a["kind"] == "copper":
                info["declared"][a["name"]] += 1
        paste = [a for a in live if a["kind"] == "paste"]
        land = [a for a in live if a["kind"] == "copper"]
        if paste:
            sev, what = "fail", "in the paste aperture of"
            names = sorted({a["name"] for a in paste})
            pads = [a["pad"] for a in paste]
        else:
            warn = []
            for a in land:
                if a["own_paste"]:
                    warn.append(a)
                elif a["windows"]:
                    info["paste-window"][a["name"]] += 1
                else:
                    info["bare"][a["name"]] += 1
            if not warn:
                continue
            sev, what = "warn", "on the copper (outside the paste) of"
            names = sorted({a["name"] for a in warn})
            pads = [a["pad"] for a in warn]
        pnets = sorted({p.GetNetname() or "no net" for p in pads})
        same = pnets == [v.GetNetname()]
        size = f"{mm(v.GetWidth(pcbnew.F_Cu))}/{mm(v.GetDrill())}"
        F["via-in-pad"].append({"net": v.GetNetname(), "layer": hits[0]["side"] + ".Cu", "at": pt(P),
                                "size_mm": mm(v.GetWidth(pcbnew.F_Cu)), "severity": sev,
                                "why": f"{', '.join(names)}: {size} via {what} the pad "
                                       f"({'same net' if same else 'pad net ' + ', '.join(pnets)})"})
    return F, {k: dict(c) for k, c in info.items()}


def pad_rail_kind(p, power_nets, grounds, class_prefixes):
    """"ground", "power" or None for a pad: ground by name (--ground-nets), power by --power-nets
    (full or leaf name) or, without it, by a Power* / PWR* net class."""
    n = p.GetNetname()
    if n in grounds:
        return "ground"
    if not n or n.startswith("unconnected-"):
        return None
    if power_nets is not None:
        return "power" if (n in power_nets or n.rsplit("/", 1)[-1] in power_nets) else None
    return "power" if any(p.GetNetClassName().startswith(c) for c in class_prefixes) else None


def pin_via_checks(board, max_track_mm, power_nets, ground_nets, class_prefixes):
    """For each pad on a power or ground net, find the nearest same-net via it reaches through its own track."""
    F = collections.defaultdict(list)
    maxlen = pcbnew.FromMM(max_track_mm)
    vias = collections.defaultdict(list)
    segs = collections.defaultdict(list)          # (net, layer) -> tracks
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias[t.GetNetCode()].append(t)
        elif t.GetClass() == "PCB_TRACK":
            segs[(t.GetNetCode(), t.GetLayer())].append(t)
    grounds = set(ground_nets)

    def along(v, a, c, layer):
        """Distance from a along segment a-c to via v, if v sits on the segment (not only at its end)."""
        vx, vy = v.GetPosition().x, v.GetPosition().y
        dx, dy = c.x - a.x, c.y - a.y
        L2 = dx * dx + dy * dy
        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((vx - a.x) * dx + (vy - a.y) * dy) / L2))
        px, py = a.x + u * dx, a.y + u * dy
        if math.hypot(vx - px, vy - py) <= v.GetWidth(layer) / 2:
            return u * math.sqrt(L2)
        return None

    owner = collections.defaultdict(list)         # via -> pads that found it
    count = {"power": 0, "ground": 0}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH or not p.IsOnCopperLayer():
                continue
            kind = pad_rail_kind(p, power_nets, grounds, class_prefixes)
            if not kind:
                continue
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                continue                           # a plated through-hole is its own via
            count[kind] += 1
            net = p.GetNetCode()
            found = None
            for v in vias[net]:                    # via in the pad
                if p.HitTest(v.GetPosition()):
                    found = v
                    break
            if found is None:                      # nearest via along the pad's own track, within maxlen
                best = None
                for layer in board.GetEnabledLayers().CuStack():
                    if not p.IsOnLayer(layer):
                        continue
                    ts = segs[(net, layer)]
                    dist = {}
                    todo = []
                    for t in ts:
                        for a, c in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                            if p.HitTest(a):
                                d0 = t.GetLength()
                                for v in vias[net]:          # a via the track passes through on its way
                                    s0 = along(v, a, c, layer)
                                    if s0 is not None and s0 <= maxlen and (best is None or s0 < best[0]):
                                        best = (s0, v)
                                key = (c.x, c.y)
                                if d0 <= maxlen and d0 < dist.get(key, 1e18):
                                    dist[key] = d0
                                    todo.append((d0, key))
                    while todo:
                        todo.sort()
                        d0, (x, y) = todo.pop(0)
                        if d0 > dist.get((x, y), 1e18):
                            continue
                        for v in vias[net]:
                            c = v.GetPosition()
                            if math.hypot(c.x - x, c.y - y) <= v.GetWidth(layer) / 2:
                                if best is None or d0 < best[0]:
                                    best = (d0, v)
                        for t in ts:
                            for a, c in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                                if (a.x, a.y) == (x, y):
                                    d1 = d0 + t.GetLength()
                                    for v in vias[net]:
                                        s0 = along(v, a, c, layer)
                                        if s0 is not None and d0 + s0 <= maxlen and (best is None or d0 + s0 < best[0]):
                                            best = (d0 + s0, v)
                                    key = (c.x, c.y)
                                    if d1 <= maxlen and d1 < dist.get(key, 1e18):
                                        dist[key] = d1
                                        todo.append((d1, key))
                if best:
                    found = best[1]
            name = f"{fp.GetReference()}.{p.GetNumber()}"
            if found is None:
                cat = "power-pin-via" if kind == "power" else "gnd-pin-via"
                F[cat].append({"net": p.GetNetname(), "layer": p.GetLayerName(), "at": pt(p.GetPosition()),
                               "size_mm": max_track_mm, "why": f"pad {name}: no via in the pad or within "
                                                               f"{max_track_mm} mm of its track"})
            else:
                owner[id(found)].append((name, found, p.GetNetname()))
    for lst in owner.values():
        if len(lst) > 1:
            v = lst[0][1]
            F["shared-pin-via"].append({"net": lst[0][2], "layer": "-", "at": pt(v.GetPosition()), "size_mm": len(lst),
                                        "why": "one via for " + ", ".join(n for n, _, _ in lst)})
    return F, count


def entry_via_checks(board, radius_mm, power_nets, ground_nets, class_prefixes):
    """entry-vias (L-21): every power or ground pad of a connector (J*) has at least two vias of
    its net within radius_mm of its center. A plated through-hole pad of the net is a via."""
    F = collections.defaultdict(list)
    R = pcbnew.FromMM(radius_mm)
    grounds = set(ground_nets)
    vias = collections.defaultdict(list)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias[t.GetNetCode()].append(t.GetPosition())
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetNetCode() > 0:
                vias[p.GetNetCode()].append(p.GetPosition())
    checked = 0
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith("J"):
            continue
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH or not p.IsOnCopperLayer():
                continue
            if not pad_rail_kind(p, power_nets, grounds, class_prefixes):
                continue
            checked += 1
            c = p.GetPosition()
            n = sum(1 for q in vias[p.GetNetCode()] if math.hypot(q.x - c.x, q.y - c.y) <= R)
            if n < 2:
                name = f"{fp.GetReference()}.{p.GetNumber()}"
                F["entry-vias"].append({"net": p.GetNetname(), "layer": p.GetLayerName(), "at": pt(c), "size_mm": n,
                                        "why": f"{name}: {n} {p.GetNetname()} via{'s' if n != 1 else ''} within "
                                               f"{radius_mm} mm of the pad (needs 2)"})
    return F, checked


def via_over_pad_checks(board, allowed=()):
    """via-over-pad (L-47): a via whose ring overlaps an SMD pad's copper, any net, off the pad's center.
    A pad on the spec's allow-via-in-pad line (a standoff land with its via ring, a declared via-in-pad) is skipped."""
    F = collections.defaultdict(list)
    areas = [a for a in smd_pad_areas(board) if a["kind"] == "copper" and a["name"] not in set(allowed)]
    centered = pcbnew.FromMM(VIA_OVER_PAD_MM)
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        P = v.GetPosition()
        for a in areas:
            if not v.IsOnLayer(a["cu"]):
                continue
            R = v.GetWidth(a["cu"]) // 2 - TOL_NM          # touching is not overlapping
            if a["bbox"].Distance(P) > R or not a["poly"].Collide(P, R):
                continue
            c = a["pad"].GetPosition()
            d = math.hypot(P.x - c.x, P.y - c.y)
            if d <= centered:
                continue                                   # a via-in-pad: L-30's business
            pnet = a["pad"].GetNetname() or "no net"
            F["via-over-pad"].append({"net": v.GetNetname(), "layer": a["side"] + ".Cu", "at": pt(P), "size_mm": mm(d),
                                      "pad": a["name"],
                                      "why": f"{a['name']}: {mm(v.GetWidth(a['cu']))}/{mm(v.GetDrill())} via "
                                             f"{mm(d)} mm off the pad center "
                                             f"({'same net' if pnet == v.GetNetname() else 'pad net ' + pnet})"})
    return F


def pad_junction_checks(board):
    """pad-junction (L-48): an SMD pad with more than one track exit, or a T within one pad length of
    its center on its net and layer. FAIL on a ball (under BALL_MM), warn otherwise."""
    F = collections.defaultdict(list)
    ball = pcbnew.FromMM(BALL_MM)
    seen, uniq = set(), []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            k = seg_key(t)
            if k not in seen:
                seen.add(k)
                uniq.append(t)
    joints = collections.defaultdict(list)
    for t in uniq:
        for p, q in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
            joints[(t.GetNetCode(), t.GetLayer(), p.x, p.y)].append((t, q))
    tees = tee_ends(uniq, joints)
    by_nl = collections.defaultdict(list)
    for t in uniq:
        by_nl[(t.GetNetCode(), t.GetLayer())].append(t)
    joints_nl = collections.defaultdict(list)
    for (net, layer, x, y), lst in joints.items():
        joints_nl[(net, layer)].append((x, y, len(lst), (net, layer, x, y) in tees))
    checked = 0
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN) or p.GetNetCode() <= 0:
                continue
            checked += 1
            net, c = p.GetNetCode(), p.GetPosition()
            size = max(p.GetSizeX(), p.GetSizeY())
            exits = branches = 0
            for layer in board.GetEnabledLayers().CuStack():
                if not p.IsOnLayer(layer):
                    continue
                for t in by_nl[(net, layer)]:
                    if p.HitTest(t.GetStart()) != p.HitTest(t.GetEnd()):
                        exits += 1
                for x, y, n, tee in joints_nl[(net, layer)]:
                    if math.hypot(x - c.x, y - c.y) > size or p.HitTest(pcbnew.VECTOR2I(int(x), int(y))):
                        continue
                    if n >= 3:
                        branches += n - 2
                    elif tee:
                        branches += 1
            count = exits + branches
            if count <= 1:
                continue
            name = f"{fp.GetReference()}.{p.GetNumber()}"
            sev = "fail" if size < ball else "warn"
            F["pad-junction"].append({"net": p.GetNetname(), "layer": p.GetLayerName(), "at": pt(c), "size_mm": count,
                                      "severity": sev, "pad": name,
                                      "why": f"{name}: {count} ends ({exits} track exit{'s' if exits != 1 else ''}, "
                                             f"{branches} junction branch{'es' if branches != 1 else ''} within "
                                             f"{mm(size)} mm){' on a ball' if sev == 'fail' else ''}"})
    return F, checked


# ------------------------------------------------------------------ L-43 stitched ground pours
def island_area(fill, i):
    return (fill.Outline(i).Area() - sum(fill.CHole(i, h).Area() for h in range(fill.HoleCount(i)))) / 1e12


def island_poly(fill, i):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.AddOutline(fill.Outline(i))
    for h in range(fill.HoleCount(i)):
        ps.AddHole(fill.CHole(i, h))
    return ps


def pour_checks(board, gnd_nets, st, stage, prof_name):
    """pour-island, pour-fill, pour-split, zone-overlap, stitch-group (L-43), from the fills as saved."""
    F = collections.defaultdict(list)
    info = {"layers": {}, "stitch": None}
    cu = list(board.GetEnabledLayers().CuStack())
    min_area, min_vias, min_ratio = st["min_island_mm2"], st["min_island_vias"], st["min_fill_ratio"]
    two_via_area = st.get("two_via_mm2", 0.0)  # smaller islands need only one via
    zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
    for name in gnd_nets:
        net = board.FindNet(name)
        if net is None or net.GetNetCode() <= 0:
            continue
        code = net.GetNetCode()
        nz = [z for z in zones if z.GetNetCode() == code]
        if not nz:
            continue
        vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == code]
        pths = [p for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetCode() == code and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
        for layer in cu:
            lz = [z for z in nz if z.IsOnLayer(layer)]
            if not lz:
                continue
            lname = board.GetLayerName(layer)
            fill = pcbnew.SHAPE_POLY_SET()
            for z in lz:
                if z.HasFilledPolysForLayer(layer):
                    fill.BooleanAdd(z.GetFilledPolysList(layer))
            # pour-fill: each zone on its own
            for z in lz:
                out_a = z.Outline().Area() / 1e12
                got = z.GetFilledPolysList(layer).Area() / 1e12 if z.HasFilledPolysForLayer(layer) else 0.0
                if out_a > 0 and got / out_a < min_ratio:
                    F["pour-fill"].append({"net": name, "layer": lname, "at": None, "size_mm": round(got / out_a, 3),
                                           "why": f"zone '{z.GetZoneName()}' fills {got / out_a:.0%} of its outline "
                                                  f"({got:.0f} of {out_a:.0f} mm2; needs {min_ratio:.0%})"})
            # pour-island: islands of the union
            areas = []
            bare = 0
            for i in range(fill.OutlineCount()):
                a = island_area(fill, i)
                areas.append((a, i))
                if a < min_area:
                    continue
                n = sum(1 for v in vias if v.IsOnLayer(layer) and fill.Contains(v.GetPosition(), i)) + \
                    sum(1 for p in pths if fill.Contains(p.GetPosition(), i))
                need = min_vias if a >= two_via_area else 1
                if n < need:
                    bare += 1
                    c = fill.Outline(i).BBox().GetCenter()
                    F["pour-island"].append({"net": name, "layer": lname, "at": pt(c), "size_mm": round(a, 1),
                                             "why": f"{a:.1f} mm2 island with {n} {name} via{'s' if n != 1 else ''} "
                                                    f"(needs {need})"})
            areas.sort(reverse=True)
            total = sum(a for a, _ in areas)
            row = {"islands": len(areas), "area_mm2": round(total, 1),
                   "largest_share": round(areas[0][0] / total, 3) if total else None, "bare_islands": bare}
            info["layers"][f"{name} {lname}"] = row
            # pour-split: the two largest islands both big, and what separates them
            if len(areas) >= 2 and areas[1][0] >= SPLIT_MIN_MM2:
                (a1, i1), (a2, i2) = areas[0], areas[1]
                p1, p2 = island_poly(fill, i1), island_poly(fill, i2)
                zclr = max(z.GetOwnClearance(layer) for z in lz)
                tol = pcbnew.FromMM(0.05)
                split = collections.defaultdict(lambda: [0, 0.0])
                for t in board.GetTracks():
                    if t.GetClass() != "PCB_TRACK" or t.GetLayer() != layer or t.GetNetCode() == code:
                        continue
                    sh = t.GetEffectiveShape(layer)
                    clr = max(zclr, t.GetOwnClearance(layer)) + tol
                    if p1.Collide(sh, clr) and p2.Collide(sh, clr):
                        split[t.GetNetname()][0] += 1
                        split[t.GetNetname()][1] += pcbnew.ToMM(t.GetLength())
                by = sorted(split.items(), key=lambda kv: -kv[1][1])
                who = (f"split by {by[0][0]} ({by[0][1][0]} segments, {by[0][1][1]:.1f} mm touch both)"
                       + (f"; also {', '.join(n for n, _ in by[1:4])}" if len(by) > 1 else "")) if by else \
                    "no single track touches both (several tracks, another net's pour or a keepout between them)"
                row["split_by"] = by[0][0] if by else None
                F["pour-split"].append({"net": name, "layer": lname, "at": pt(fill.Outline(i2).BBox().GetCenter()),
                                        "size_mm": round(a2, 1),
                                        "why": f"{len(areas)} islands, largest {row['largest_share']:.0%} of {total:.0f} mm2; "
                                               f"two largest {a1:.0f} and {a2:.0f} mm2, {who}"})
        # zone-overlap: same net, same layer, outlines overlap
        for i, a in enumerate(nz):
            for b in nz[i + 1:]:
                for layer in cu:
                    if not (a.IsOnLayer(layer) and b.IsOnLayer(layer)):
                        continue
                    x = pcbnew.SHAPE_POLY_SET(a.Outline())
                    x.BooleanIntersection(b.Outline())
                    ov = x.Area() / 1e12
                    if ov > 0.01:
                        F["zone-overlap"].append({"net": name, "layer": board.GetLayerName(layer),
                                                  "at": pt(x.BBox().GetCenter()), "size_mm": round(ov, 1),
                                                  "why": f"'{a.GetZoneName()}' (priority {a.GetAssignedPriority()}) and "
                                                         f"'{b.GetZoneName()}' (priority {b.GetAssignedPriority()}) "
                                                         f"overlap by {ov:.0f} mm2"})
    # stitch-group
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from stitch import stitch_status
        ss = stitch_status(board, {"stitch": st})
    except Exception as e:
        info["stitch"] = {"error": str(e)}
        return F, info
    for v in ss["outside_vias"]:
        g = v.GetParentGroup()
        F["stitch-group"].append({"net": ss["net"], "layer": "-", "at": pt(v.GetPosition()), "size_mm": ss["via"][0],
                                  "why": f"free {ss['via'][0]}/{ss['via'][1]} via outside group '{ss['group']}' "
                                         + (f"(in group '{g.GetName()}')" if g else "(ungrouped)")})
    if stage == "final" and ss["has_pours"] and not ss["group_present"]:
        F["stitch-group"].append({"net": ss["net"], "layer": "-", "at": None, "size_mm": 0,
                                  "why": f"no '{ss['group']}' group on a board with {ss['net']} pours "
                                         f"(stitch.py add --profile {prof_name})"})
    info["stitch"] = {k: v for k, v in ss.items() if k != "outside_vias"}
    return F, info


def parse_directions(s):
    if not s:
        return None
    out = {}
    for part in s.split(","):
        layer, _, want = part.partition("=")
        want = want.strip()
        if want not in ("H", "V", "plane", "any"):
            sys.exit(f"--directions: {part!r}: use H, V, plane or any")
        out[layer.strip()] = want
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--profile", default="rigid", choices=["rigid", "flex"],
                    help="drc.json profile for the edge, pin-via and pour defaults")
    ap.add_argument("--stage", default="routed", choices=["routed", "final"],
                    help="final: a board with pours and no stitch group is reported (stitching is the last pass)")
    ap.add_argument("--directions", help="layer jobs from the routing spec, e.g. F.Cu=H,In1.Cu=plane,In2.Cu=V,B.Cu=H")
    ap.add_argument("--min-axis", type=float, default=0.6, help="share of a layer's length its axis must carry (draft)")
    ap.add_argument("--plane-max-run", type=float, default=3.0,
                    help="mm of one net's track a plane layer may carry (draft)")
    ap.add_argument("--json", help="write every finding and the direction table here")
    ap.add_argument("--list", type=int, default=5, help="how many of each to print, worst first")
    # the profile sets the other defaults, so read it first
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--profile", default="rigid", choices=["rigid", "flex"])
    prof = pre.parse_known_args()[0].profile
    ed = edge_defaults(prof)
    ap.add_argument("--edge-margin", type=float, default=ed["margin_mm"],
                    help="L-38 band kept free of signal/power copper, mm (0 skips the edge checks)")
    ap.add_argument("--edge-margin-fail", action="store_true",
                    help="make edge-margin a failure (the routing spec says the band is strict); "
                         f"default is edge_ring.margin_severity, '{ed.get('margin_severity', 'warn')}'")
    ap.add_argument("--ring-net", default="GND")
    ap.add_argument("--ring-layers", default="F.Cu,B.Cu", help="layers that carry the ground ring")
    ap.add_argument("--ring-coverage", type=float, default=ed["coverage"])
    ap.add_argument("--stitch-pitch", type=float, default=ed["stitch_pitch_mm"])
    pv = rules_block("pin_vias", {"max_track_mm": 1.5, "power_class_prefixes": ["Power", "PWR"], "ground_nets": ["GND"]}, prof)
    st = rules_block("stitch", {"area_pitch_mm": 2.0, "via": [0.6, 0.3], "net": "GND", "group": "GND stitching",
                                "min_island_mm2": 2.0, "min_island_vias": 2, "min_fill_ratio": 0.3}, prof)
    ap.add_argument("--pin-via-track", type=float, default=pv["max_track_mm"],
                    help="L-39: mm of a pad's own track within which its via must sit (0 skips the pin-via checks)")
    ap.add_argument("--power-nets", help="comma list of power nets (default: nets in Power*/PWR* net classes)")
    ap.add_argument("--ground-nets", default=",".join(pv["ground_nets"]))
    ap.add_argument("--entry-radius", type=float, default=1.0,
                    help="L-21: mm around a connector's power or ground pad within which two vias of its net must sit")
    ap.add_argument("--no-pours", action="store_true", help="skip the L-43 pour and stitching checks")
    nc = rules_block("netclasses", {"Default": {"via_drill": 0.3}}, prof)
    ap.add_argument("--allow-via-in-pad", help="L-30: comma list of REF.PAD declared via-in-pad (filled and capped); "
                    "added to the routing spec's allow-via-in-pad line")
    ap.add_argument("--routing-spec", help="routing spec to read allow-via-in-pad from "
                    "(default review/routing/spec.md beside the board)")
    ap.add_argument("--std-via-drill", type=float, default=nc["Default"]["via_drill"],
                    help="L-32: vias drilled smaller than this are listed as small-via (default drc.json Default class drill)")
    args = ap.parse_args()
    fails = set(FAILS)
    if args.edge_margin_fail or ed.get("margin_severity") == "fail":
        fails.add("edge-margin")
    if args.stage != "final":
        fails.discard("pour-island")  # stitching is the last pass (L-43): before it, a bare island is expected
    else:
        fails.add("gnd-pin-via")      # L-39: "where the pitch allows" is settled by then

    directions = parse_directions(args.directions)
    board = pcbnew.LoadBoard(args.board)
    F, table = check(board, args.board, directions, args.min_axis, args.plane_max_run)
    EF, einfo = edge_checks(board, args.edge_margin, args.ring_net,
                            [l.strip() for l in args.ring_layers.split(",") if l.strip()],
                            args.ring_coverage, args.stitch_pitch)
    F.update(EF)
    VF, via_sizes = via_size_checks(board, args.std_via_drill)
    F.update(VF)
    spec = args.routing_spec or os.path.join(os.path.dirname(os.path.abspath(args.board)), "review", "routing", "spec.md")
    allowed = spec_allow_list(spec) | {n.strip() for n in (args.allow_via_in_pad or "").split(",") if n.strip()}
    IF, vinfo = via_in_pad_checks(board, allowed)
    F.update(IF)
    F.update(via_over_pad_checks(board, allowed))
    JF, jchecked = pad_junction_checks(board)
    F.update(JF)
    power_nets = None if not args.power_nets else {n.strip() for n in args.power_nets.split(",")}
    ground_nets = [n.strip() for n in args.ground_nets.split(",") if n.strip()]
    EV, echecked = entry_via_checks(board, args.entry_radius, power_nets, ground_nets, pv["power_class_prefixes"])
    F.update(EV)
    pinfo = None
    if args.pin_via_track > 0:
        PF, pinfo = pin_via_checks(board, args.pin_via_track, power_nets, ground_nets, pv["power_class_prefixes"])
        F.update(PF)
    oinfo = None
    if not args.no_pours:
        gnets = [args.ring_net] + [n.strip() for n in args.ground_nets.split(",") if n.strip() and n.strip() != args.ring_net]
        OF, oinfo = pour_checks(board, gnets, st, args.stage, prof)
        F.update(OF)

    def failing(cat, items):
        if cat not in fails or not items:
            return False
        return any(f.get("severity", "fail") == "fail" for f in items)

    order = ["via-off-center", "via-over-pad", "via-in-pad", "pad-junction", "overlap", "loop", "sharp-bend", "direction",
             "entry-vias", "edge-margin", "edge-ring", "edge-stitch", "power-pin-via", "gnd-pin-via", "shared-pin-via",
             "pour-island", "pour-fill", "pour-split", "zone-overlap", "stitch-group",
             "staircase", "jog", "right-angle", "odd-angle", "plane-track", "off-list-width", "small-via"]
    for cat in order:
        items = F.get(cat, [])
        if cat in ("sharp-bend", "pour-fill", "small-via", "entry-vias"):
            items.sort(key=lambda f: f["size_mm"])
        elif cat == "via-in-pad":
            items.sort(key=lambda f: f["severity"] != "fail")
        elif cat == "pad-junction":
            items.sort(key=lambda f: (f["severity"] != "fail", -f["size_mm"]))
        else:
            items.sort(key=lambda f: -(f["size_mm"] or 0))
        grade = "FAIL" if failing(cat, items) else ("warn" if items else "ok")
        extra = ""
        if cat == "plane-track" and items:
            extra = f", {sum(f['size_mm'] for f in items):.1f} mm"
        print(f"{grade:4}  {cat:15} {len(items)}{extra}")
        for f in items[:args.list]:
            where = f"{f['layer']:7} " + (f"({f['at'][0]:.2f}, {f['at'][1]:.2f})" if f["at"] else "")
            sev = f"[{f['severity']}] " if "severity" in f else ""
            print(f"        {where:28} {sev}{f.get('why') or f['size_mm']}  {f['net']}")

    if "skipped" in einfo:
        print(f"\nedge ring (L-38): skipped ({einfo['skipped']}); the routing spec must say why")
    else:
        ring = ", ".join(f"{k} {'n/a' if v is None else f'{v:.0%}'}" for k, v in einfo.get("ring", {}).items())
        print(f"\nedge ring (L-38): {args.edge_margin} mm band; {args.ring_net} on the ring path: {ring}; "
              f"{einfo.get('stitch_vias_in_band', 0)} stitching vias in the band; "
              f"path {einfo['ring_samples']['path']} points at 0.5 mm, {einfo['ring_samples']['exempt']} exempt; "
              f"edge parts exempt: {', '.join(einfo.get('edge_parts', [])) or 'none'}")
        rs = einfo.get("ring_samples", {})
        if rs.get("path") and rs["exempt"] > rs["path"] / 2:
            print(f"  NOTE: {rs['exempt']} of {rs['path']} ring points are exempt (edge parts, holes): the ring is mostly "
                  f"not gradeable. If the board is too small for a ring, say so in the spec and use --edge-margin 0")
        if einfo.get("unfilled_zones"):
            print(f"  WARNING: unfilled {args.ring_net} zones {einfo['unfilled_zones']}: fill and save before grading")

    print(f"\nvia sizes (L-32): " + (", ".join(f"{k} {d}/{h}" for (d, h), k in sorted(via_sizes.items(), key=lambda x: -x[0][1]))
          or "none") + f"; drill under {args.std_via_drill} must be named in the routing spec")

    vfail = sum(1 for f in F.get("via-in-pad", []) if f["severity"] == "fail")
    print(f"\nvia in pad (L-30): {vfail} in a paste aperture (fail), {len(F.get('via-in-pad', [])) - vfail} on land "
          f"copper outside the paste (warn); not reported: "
          + "; ".join(f"{k} {', '.join(f'{n} x{c}' for n, c in sorted(d.items()))}" for k, d in vinfo.items() if d)
          + ("" if any(vinfo.values()) else "none")
          + f"; allow list {', '.join(sorted(allowed)) or 'empty'}"
          + (f" (spec {os.path.relpath(spec)})" if os.path.exists(spec) else " (no routing spec found)"))

    jfail = sum(1 for f in F.get("pad-junction", []) if f["severity"] == "fail")
    print(f"\nleaf pads (L-48): {jchecked} SMD pads checked; {jfail} balls (fail) and "
          f"{len(F.get('pad-junction', [])) - jfail} other pads (warn) with more than one track end; "
          f"{len(F.get('via-over-pad', []))} vias over a pad off its center (L-47)")

    print(f"\nconnector entry (L-21): {echecked} power and ground pads of J* checked for 2 vias within "
          f"{args.entry_radius} mm; {len(F.get('entry-vias', []))} short")

    if pinfo is None:
        print("\npin vias (L-39): skipped (--pin-via-track 0); the routing spec must say why")
    else:
        print(f"\npin vias (L-39): {pinfo['power']} power and {pinfo['ground']} ground SMD pads checked; "
              f"{len(F.get('power-pin-via', []))} power and {len(F.get('gnd-pin-via', []))} ground pads without their own via")

    if oinfo is None:
        print("\npours (L-43): skipped (--no-pours)")
    else:
        print(f"\npours (L-43, {prof}): islands of at least {st['min_island_mm2']} mm2 need 1 via, {st['min_island_vias']} from {st.get('two_via_mm2', 0)} mm2; "
              f"stage {args.stage}")
        for k, r in oinfo["layers"].items():
            share = "-" if r["largest_share"] is None else f"{r['largest_share']:.0%}"
            print(f"  {k:14} {r['area_mm2']:8.1f} mm2 in {r['islands']:3} islands, largest {share:>4}, "
                  f"{r['bare_islands']} under-stitched" + (f", split by {r['split_by']}" if r.get("split_by") else ""))
        ss = oinfo.get("stitch") or {}
        if "error" in ss:
            print(f"  stitch group: not checked ({ss['error']})")
        elif ss:
            outside = sum(ss["outside"].values())
            print(f"  stitch group '{ss['group']}': " + (f"{ss['group_vias']} vias" if ss["group_present"] else
                  "none" + (" (expected before the final stitching pass)" if args.stage != "final" else ""))
                  + f"; {outside} free {ss['via'][0]}/{ss['via'][1]} {ss['net']} vias outside it")

    print("\nsignal length by direction, mm (plane nets' own copper left out)")
    print(f"  {'layer':8} {'H':>7} {'V':>7} {'45':>7} {'other':>6}  declared")
    for layer, r in table.items():
        share = f"  {r['axis_share']:.0%} on axis" if r.get("axis_share") is not None else ""
        if "hops" in r:
            share = f"  {r['hops']} nets hop onto it, {r['total']} mm"
        print(f"  {layer:8} {r['H']:>7} {r['V']:>7} {r['45']:>7} {r['other']:>6}  {r['declared'] or '-'}{share}")
    if directions is None:
        print("  no --directions given: layer discipline (L-26) is reported, not graded")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"board": args.board, "directions": directions, "findings": F, "layers": table,
                       "edge_ring": einfo, "pin_vias": pinfo, "via_in_pad": vinfo, "pours": oinfo,
                       "leaf_pads": {"checked": jchecked}, "entry_vias": {"checked": echecked, "radius_mm": args.entry_radius},
                       "default_pitch_mm": mm(default_pitch(board)),
                       "via_sizes": [{"diameter": d, "drill": h, "count": k} for (d, h), k in sorted(via_sizes.items())],
                       "fails": sorted(fails)}, fh, indent=1)
    sys.exit(1 if any(failing(c, F.get(c, [])) for c in fails) else 0)


if __name__ == "__main__":
    main()
