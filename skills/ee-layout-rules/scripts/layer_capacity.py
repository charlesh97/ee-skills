"""How many signal layers does this board need, and does a plane survive its vias?

Run it on a placed board before any routing (L-36), and again after fanout,
when the fanout vias exist. It answers the layer-count question with numbers
instead of with "we used every layer".

Demand. The board is cut at every --step mm, across both axes. A net must
cross a cut when it has pads on both sides of it. That is one crossing at
least, so demand is a lower bound. Plane nets (--plane-nets) are left out,
because they connect through their pour.

Capacity. Along each cut, on each copper layer, it takes the board's width
inside the edge clearance, removes what the pads and vias on that layer
occupy (plus clearance), and counts how many tracks at --pitch fit in what's
left. Existing tracks are ignored: this is about what the board can hold, not
what one attempt left behind.

Result. For each layer count it reports the worst cut's utilization, meaning
demand over the capacity of the layers you'd route signal on. It then
recommends the fewest signal layers that keep the worst cut under --target,
and says which layers are free to be planes.

Plane check (--plane LAYER). Along the same cuts it measures how much of the
plane layer is copper once every via and through-hole pad is cleared. It
reports the worst cut and the thinnest web between two antipads. A plane
that's mostly holes along a line isn't a return path along that line.

Run with KiCad's bundled python ($KPY):
  layer_capacity.py board.kicad_pcb [--plane-nets GND] [--plane In1.Cu]
                    [--pitch 0.25] [--target 0.6] [--step 0.5] [--pre-route] [--json out.json]

--pitch defaults to the Default net class's track width plus clearance.
"""
import argparse
import collections
import json
import sys

import pcbnew

EDGE_MM = 0.25


def mm(v):
    return pcbnew.ToMM(v)


def default_pitch(board):
    ds = board.GetDesignSettings()
    try:
        nc = ds.m_NetSettings.GetDefaultNetclass()
        return mm(nc.GetTrackWidth()) + mm(nc.GetClearance())
    except Exception:
        return 0.25


def outline_spans(outline, axis, at):
    """Board extent along a cut: intervals of the other coordinate inside the outline."""
    bb = outline.BBox()
    lo, hi = (bb.GetY(), bb.GetBottom()) if axis == "x" else (bb.GetX(), bb.GetRight())
    strip = pcbnew.SHAPE_POLY_SET()
    r = pcbnew.SHAPE_LINE_CHAIN()
    a, w = pcbnew.FromMM(at), pcbnew.FromMM(0.005)
    pts = ((a - w, lo), (a + w, lo), (a + w, hi), (a - w, hi)) if axis == "x" else \
          ((lo, a - w), (hi, a - w), (hi, a + w), (lo, a + w))
    for px, py in pts:
        r.Append(int(px), int(py))
    r.SetClosed(True)
    strip.AddOutline(r)
    strip.BooleanIntersection(outline)
    spans = []
    for i in range(strip.OutlineCount()):
        b = strip.Outline(i).BBox()
        s, e = (mm(b.GetY()), mm(b.GetBottom())) if axis == "x" else (mm(b.GetX()), mm(b.GetRight()))
        if e - s > 2 * EDGE_MM:
            spans.append((s + EDGE_MM, e - EDGE_MM))
    return spans


def in_a_pad(board, v):
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == v.GetNetCode() and p.HitTest(v.GetPosition()):
                return True
    return False


def blockers(board, layers, clearance, skip_nets=(), pre_route=False):
    """Per layer: (center_x, center_y, half_x, half_y) boxes that tracks can't use.
    Items on skip_nets are left out (a plane net's own vias join its plane).
    pre_route keeps only vias inside a same-net pad: the via-in-pad fanout a
    board has before routing, not the vias one routing attempt added."""
    out = collections.defaultdict(list)
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() in skip_nets:
                continue
            bb = p.GetBoundingBox()
            box = (mm(bb.GetCenter().x), mm(bb.GetCenter().y),
                   mm(bb.GetWidth()) / 2 + clearance, mm(bb.GetHeight()) / 2 + clearance)
            for l in layers:
                if p.IsOnLayer(l):
                    out[l].append(box)
    for v in board.GetTracks():
        if v.GetClass() != "PCB_VIA" or v.GetNetname() in skip_nets:
            continue
        if pre_route and not in_a_pad(board, v):
            continue
        c = v.GetPosition()
        for l in layers:
            if v.IsOnLayer(l):
                r = mm(v.GetWidth(l)) / 2 + clearance
                out[l].append((mm(c.x), mm(c.y), r, r))
    return out


def free_slots(spans, boxes, axis, at, pitch):
    """Tracks at pitch that fit across the cut on one layer, between the blocked intervals."""
    cuts = []
    for cx, cy, hx, hy in boxes:
        if axis == "x" and abs(cx - at) < hx:
            cuts.append((cy - hy, cy + hy))
        elif axis == "y" and abs(cy - at) < hy:
            cuts.append((cx - hx, cx + hx))
    cuts.sort()
    slots, copper = 0, 0.0
    for s, e in spans:
        pos = s
        for a, b in cuts:
            if b <= pos or a >= e:
                continue
            if a > pos:
                slots += int((a - pos) / pitch)
                copper += a - pos
            pos = max(pos, b)
        if e > pos:
            slots += int((e - pos) / pitch)
            copper += e - pos
    return slots, copper


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--plane-nets", default="GND", help="comma list of nets that connect through a pour")
    ap.add_argument("--plane", help="a layer to check as a plane: copper left between the antipads")
    ap.add_argument("--pitch", type=float, help="track width + clearance, mm")
    ap.add_argument("--target", type=float, default=0.6, help="worst-cut utilization to stay under (draft)")
    ap.add_argument("--step", type=float, default=0.5, help="mm between cuts")
    ap.add_argument("--pre-route", action="store_true",
                    help="on a routed board, count only via-in-pad vias, as before routing")
    ap.add_argument("--json")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.board)
    pitch = args.pitch or default_pitch(board)
    clearance = pitch / 2  # half the pitch is the clearance side of a track slot
    plane_nets = {n.strip() for n in args.plane_nets.split(",") if n.strip()}
    layers = list(board.GetEnabledLayers().CuStack())
    names = [board.GetLayerName(l) for l in layers]

    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    bb = outline.BBox()

    pads = collections.defaultdict(list)
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n and n not in plane_nets and not n.startswith("unconnected-"):
                c = p.GetPosition()
                pads[n].append((mm(c.x), mm(c.y)))
    pads = {n: v for n, v in pads.items() if len(v) > 1}

    block = blockers(board, layers, clearance, pre_route=args.pre_route)
    cuts = []
    for axis, lo, hi in (("x", mm(bb.GetX()), mm(bb.GetRight())), ("y", mm(bb.GetY()), mm(bb.GetBottom()))):
        at = lo + args.step
        while at < hi:
            k = 0 if axis == "x" else 1
            demand = sum(1 for v in pads.values() if min(p[k] for p in v) < at < max(p[k] for p in v))
            spans = outline_spans(outline, axis, at)
            if demand and spans:
                cap = {nm: free_slots(spans, block[l], axis, at, pitch)[0] for l, nm in zip(layers, names)}
                cuts.append({"axis": axis, "at": round(at, 2), "demand": demand, "capacity": cap})
            at += args.step

    if not cuts:
        sys.exit("no net crosses any cut: is the board placed?")

    # Signal layers in the order they're usually given up to planes: inner layers first,
    # starting next to F.Cu, so F.Cu (parts and escapes) and B.Cu stay signal longest.
    inner = names[1:-1]
    give_up = inner + [names[-1]]
    options = []
    for planes in range(0, len(names)):
        sig = [n for n in names if n not in give_up[:planes]]
        if not sig:
            break
        worst = max(cuts, key=lambda c: c["demand"] / max(1, sum(c["capacity"][n] for n in sig)))
        util = worst["demand"] / max(1, sum(worst["capacity"][n] for n in sig))
        options.append({"planes": give_up[:planes], "signal": sig, "worst_util": round(util, 2),
                        "worst_cut": f"{worst['axis']}={worst['at']}", "demand": worst["demand"],
                        "capacity": sum(worst["capacity"][n] for n in sig)})

    print(f"pitch {pitch:.3f} mm, plane nets {sorted(plane_nets) or '-'}, {len(pads)} nets, {len(cuts)} cuts")
    top = sorted(cuts, key=lambda c: -c["demand"])[:5]
    print("\nbusiest cuts (demand = nets that must cross; tracks that fit per layer)")
    for c in top:
        print(f"  {c['axis']}={c['at']:<7} demand {c['demand']:4}   " +
              "  ".join(f"{n} {c['capacity'][n]}" for n in names))
    print(f"\n{'planes':<22} {'signal layers':<34} worst-cut use")
    for o in options:
        ok = "ok" if o["worst_util"] <= args.target else "over"
        print(f"  {', '.join(o['planes']) or '-':<20} {', '.join(o['signal']):<34} "
              f"{o['worst_util']:.0%} at {o['worst_cut']} ({o['demand']}/{o['capacity']})  {ok}")
    fit = [o for o in options if o["worst_util"] <= args.target]
    best = max(fit, key=lambda o: len(o["planes"])) if fit else None
    if best and best["planes"]:
        print(f"\nrecommend: planes on {', '.join(best['planes'])}; signal on {', '.join(best['signal'])} "
              f"({best['worst_util']:.0%} at the worst cut, target {args.target:.0%})")
    elif best:
        print(f"\nno layer can be a plane under {args.target:.0%} at the worst cut: "
              f"add layers rather than route without a plane (L-37)")
    else:
        print(f"\neven every layer as signal is over {args.target:.0%} at the worst cut: "
              f"add layers or re-place (L-37)")

    plane = None
    if args.plane:
        pl = next((l for l, n in zip(layers, names) if n == args.plane), None)
        if pl is None:
            sys.exit(f"--plane {args.plane}: not a copper layer of this board")
        zc = mm(board.GetDesignSettings().m_MinClearance)
        holes = sorted(set(blockers(board, [pl], zc, plane_nets, args.pre_route)[pl]))
        worst = None
        for c in cuts:
            spans = outline_spans(outline, c["axis"], c["at"])
            total = sum(e - s for s, e in spans)
            _, copper = free_slots(spans, holes, c["axis"], c["at"], 1e9)
            frac = copper / total if total else 1
            if worst is None or frac < worst[0]:
                worst = (frac, c["axis"], c["at"])
        webs = []
        pts = sorted(holes)
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                if b[0] - a[0] > 2:
                    break
                d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 - max(a[2], a[3]) - max(b[2], b[3])
                webs.append((round(max(0.0, d), 3), round(a[0], 2), round(a[1], 2)))
        webs.sort()
        minw = mm(board.GetDesignSettings().m_TrackMinWidth)
        thin = sum(1 for w in webs if w[0] < minw)
        merged = sum(1 for w in webs if w[0] == 0)
        plane = {"layer": args.plane, "worst_copper_fraction": round(worst[0], 2),
                 "worst_cut": f"{worst[1]}={worst[2]}", "holes": len(holes),
                 "thinnest_webs": webs[:5], "webs_under_min_track": thin, "antipads_merged": merged}
        print(f"\nplane {args.plane}: {len(holes)} holes; worst cut {worst[1]}={worst[2]} is "
              f"{worst[0]:.0%} copper; {thin} webs thinner than {minw} mm between antipads "
              f"({merged} where antipads merge, leaving no copper)")
        for w in webs[:3]:
            print(f"  web {w[0]} mm near ({w[1]}, {w[2]})")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"board": args.board, "pitch": pitch, "cuts": cuts, "options": options,
                       "recommend": best, "plane": plane}, fh, indent=1)


if __name__ == "__main__":
    main()
