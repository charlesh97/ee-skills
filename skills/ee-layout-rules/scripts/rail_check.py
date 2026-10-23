"""Copper resistance of a routed rail and capacitance of a routed bus (L-21, L-45).

Two gradings, one line each, from the copper as routed:

  rail-drop  L-21  for each --rails NET:AMPS, the resistance of the routed copper from the
                   source footprint's pads of that net (--source, default the first J*
                   footprint with a pad on the net) to every other pad of the net: the
                   shortest path over tracks and vias. A track is rho * L / (w * t) with
                   rho 1.72e-8 ohm-m and t 35 um per oz (--copper-oz, 1.0); a via is 1 mOhm
                   end to end; a filled pour of the net is 0 ohm between everything that
                   sits in it. Copper joins where KiCad's connectivity joins it: a track end
                   whose copper overlaps a pad, a via ring or another track is attached there
                   (L-33 and L-48 grade those joints; this script only follows them). Prints the farthest pad, its path resistance and the IR drop
                   at the given current. A pad with no path is listed (an unrouted rail has
                   none); with --max-drop-mv the drop is graded, otherwise reported
  bus-cap    L-45  for each --bus NET, the capacitance from the routed track length
                   (--pf-per-mm), via count (--pf-per-via) and pad count (--pf-per-pin), and
                   the 10-90 % rise time 0.8473 * R * C with the --pullup resistance, against
                   --limit-ns (300, fast mode) and the 400 pF bus limit

Fails (exit 1): rail-drop with no path from the source to any pad, or a drop over --max-drop-mv;
bus-cap over the rise time or capacitance limit. A rail with some unreached pads warns.

Run with KiCad's bundled python ($KPY):
  rail_check.py board.kicad_pcb --rails 1V8:0.032,3V3_LED:0.24 [--copper-oz 0.5] [--source J1]
                [--max-drop-mv 50]
  rail_check.py board.kicad_pcb --bus I2C0_SENSOR_SCL --pullup 1500 --pf-per-mm 0.1 --pf-per-via 0.1
                --pf-per-pin 5 [--limit-ns 300]
  either with [--json out.json] [--list 5]
"""
import argparse
import collections
import heapq
import json
import math
import sys

import pcbnew

RHO_OHM_M = 1.72e-8     # copper
OZ_M = 35e-6            # copper thickness per oz
VIA_OHM = 1e-3          # one via, end to end
BUS_MAX_PF = 400.0      # L-45: standard and fast mode
RISE_K = 0.8473         # 10-90 % of an RC step


def mm(v):
    return round(pcbnew.ToMM(v), 3)


def pt(p):
    return [mm(p.x), mm(p.y)]


def find_net(board, name):
    """A net by its full name, or by its leaf name after the last '/'."""
    n = board.FindNet(name)
    if n is not None and n.GetNetCode() > 0:
        return n
    for code, n in board.GetNetInfo().NetsByNetcode().items():
        if code > 0 and n.GetNetname().rsplit("/", 1)[-1] == name:
            return n
    return None


def net_pads(board, code):
    return [(fp, p) for fp in board.GetFootprints() for p in fp.Pads()
            if p.GetNetCode() == code and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]


# ------------------------------------------------------------------ L-21 rail resistance
def on_interior(t, P, tol):
    """Where along track t (0..1, ends excluded) the point P sits within tol of its centerline, else None."""
    a, c = t.GetStart(), t.GetEnd()
    dx, dy = c.x - a.x, c.y - a.y
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return None
    u = ((P.x - a.x) * dx + (P.y - a.y) * dy) / L2
    if u <= 0.0 or u >= 1.0:
        return None
    return u if math.hypot(P.x - (a.x + u * dx), P.y - (a.y + u * dy)) <= tol else None


def rail_graph(board, code, oz):
    """Resistance graph of one net: track ends, per-layer via nodes, pads and pours as nodes.
    Copper joins the way KiCad's connectivity sees it: a track end whose copper overlaps a pad, a
    via's ring or another track's copper is attached there, not only an end exactly at the center."""
    adj = collections.defaultdict(list)
    t_m = OZ_M * oz
    cu = list(board.GetEnabledLayers().CuStack())

    def link(a, b, r):
        adj[a].append((b, r))
        adj[b].append((a, r))

    def ohm(t):
        L = pcbnew.ToMM(t.GetLength()) * 1e-3
        w = pcbnew.ToMM(t.GetWidth()) * 1e-3
        return RHO_OHM_M * L / (w * t_m) if w > 0 else 0.0

    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == code]
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetCode() == code]
    ends = collections.defaultdict(dict)                       # layer -> {(x, y): half width}
    by_layer = collections.defaultdict(list)
    for t in tracks:
        a, c, layer = t.GetStart(), t.GetEnd(), t.GetLayer()
        link((layer, a.x, a.y), (layer, c.x, c.y), ohm(t))
        for q in (a, c):
            ends[layer][(q.x, q.y)] = max(ends[layer].get((q.x, q.y), 0), t.GetWidth() // 2)
        by_layer[layer].append(t)
    # a track end on another track's copper splits it (a T drawn onto a track)
    for layer, ts in by_layer.items():
        for (x, y), hw in ends[layer].items():
            P = pcbnew.VECTOR2I(x, y)
            for t in ts:
                u = on_interior(t, P, hw + t.GetWidth() // 2)
                if u is not None:
                    r = ohm(t)
                    a, c = t.GetStart(), t.GetEnd()
                    link((layer, x, y), (layer, a.x, a.y), r * u)
                    link((layer, x, y), (layer, c.x, c.y), r * (1 - u))
    # vias: a node per layer they span, VIA_OHM end to end; track ends touching the ring join at 0;
    # a via sitting on a track's interior splits that track
    via_nodes = []
    for i, v in enumerate(vias):
        P = v.GetPosition()
        layers = [l for l in cu if v.IsOnLayer(l)]
        if not layers:
            continue
        step = VIA_OHM / max(1, len(layers) - 1)
        for la, lb in zip(layers, layers[1:]):
            link(("via", i, la), ("via", i, lb), step)
        via_nodes.append((v, i, layers))
        for layer in layers:
            R = v.GetWidth(layer) / 2
            for (x, y), hw in ends[layer].items():
                if math.hypot(x - P.x, y - P.y) <= R + hw:
                    link(("via", i, layer), (layer, x, y), 0.0)
            for t in by_layer[layer]:
                u = on_interior(t, P, R)
                if u is not None:
                    r = ohm(t)
                    a, c = t.GetStart(), t.GetEnd()
                    link(("via", i, layer), (layer, a.x, a.y), r * u)
                    link(("via", i, layer), (layer, c.x, c.y), r * (1 - u))
    # stacked or touching vias sharing a layer
    for i, (va, ia, la) in enumerate(via_nodes):
        for vb, ib, lb in via_nodes[i + 1:]:
            pa, pb = va.GetPosition(), vb.GetPosition()
            for l in set(la) & set(lb):
                if math.hypot(pa.x - pb.x, pa.y - pb.y) <= (va.GetWidth(l) + vb.GetWidth(l)) / 2:
                    link(("via", ia, l), ("via", ib, l), 0.0)
    # pads: track ends whose copper reaches the pad, and vias through it, join at 0
    pads = net_pads(board, code)
    for fp, p in pads:
        node = ("pad", fp.GetReference(), p.GetNumber())
        adj[node]                                               # exists even when unreached
        for layer in cu:
            if not p.IsOnLayer(layer):
                continue
            for (x, y), hw in ends[layer].items():
                if p.HitTest(pcbnew.VECTOR2I(x, y), hw):
                    link(node, (layer, x, y), 0.0)
            for v, i, layers in via_nodes:
                if layer in layers and p.HitTest(v.GetPosition(), v.GetWidth(layer) // 2):
                    link(node, ("via", i, layer), 0.0)
    # pours: a filled zone of the net is 0 ohm between everything that sits in its fill
    pours = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != code:
            continue
        for layer in cu:
            if not (z.IsOnLayer(layer) and z.HasFilledPolysForLayer(layer)):
                continue
            fill = z.GetFilledPolysList(layer)
            if not fill.OutlineCount():
                continue
            node = ("pour", z.GetZoneName() or str(id(z)), layer)
            pours.append(board.GetLayerName(layer))
            for (x, y), hw in ends[layer].items():
                if fill.Collide(pcbnew.VECTOR2I(x, y), hw):
                    link(node, (layer, x, y), 0.0)
            for v, i, layers in via_nodes:
                if layer in layers and fill.Collide(v.GetPosition(), v.GetWidth(layer) // 2):
                    link(node, ("via", i, layer), 0.0)
            for fp, p in pads:
                if p.IsOnLayer(layer) and fill.Collide(p.GetPosition(), max(p.GetSizeX(), p.GetSizeY()) // 2):
                    link(node, ("pad", fp.GetReference(), p.GetNumber()), 0.0)
    return adj, pads, {"tracks": len(tracks), "vias": len(vias), "pours": pours}


def dijkstra(adj, sources):
    dist = {s: 0.0 for s in sources}
    todo = [(0.0, repr(s), s) for s in sources]
    while todo:
        d, _, n = heapq.heappop(todo)
        if d > dist.get(n, math.inf):
            continue
        for m, r in adj[n]:
            nd = d + r
            if nd < dist.get(m, math.inf):
                dist[m] = nd
                heapq.heappush(todo, (nd, repr(m), m))
    return dist


def rail_drop(board, name, amps, oz, source):
    net = find_net(board, name)
    if net is None:
        return {"rail": name, "error": "no such net"}
    code = net.GetNetCode()
    adj, pads, info = rail_graph(board, code, oz)
    src = source
    if src is None:
        for fp, p in sorted(pads, key=lambda fp_p: fp_p[0].GetReference()):
            if fp.GetReference().startswith("J"):
                src = fp.GetReference()
                break
    src_pads = [("pad", fp.GetReference(), p.GetNumber()) for fp, p in pads if fp.GetReference() == src]
    out = {"rail": net.GetNetname(), "amps": amps, "copper_oz": oz, "source": src, "pads": len(pads), **info}
    if not src_pads:
        out["error"] = f"no pad of {net.GetNetname()} on {src or 'any J* footprint'} (--source)"
        return out
    dist = dijkstra(adj, src_pads)
    reached, missing = [], []
    for fp, p in pads:
        node = ("pad", fp.GetReference(), p.GetNumber())
        if node in src_pads:
            continue
        name_ = f"{fp.GetReference()}.{p.GetNumber()}"
        if node in dist:
            reached.append({"pad": name_, "at": pt(p.GetPosition()), "mohm": round(dist[node] * 1e3, 2),
                            "drop_mv": round(dist[node] * amps * 1e3, 2)})
        else:
            missing.append(name_)
    reached.sort(key=lambda r: -r["mohm"])
    out.update({"reached": reached, "missing": missing, "farthest": reached[0] if reached else None})
    return out


# ------------------------------------------------------------------ L-45 bus capacitance
def bus_cap(board, name, pullup, pf_mm, pf_via, pf_pin, limit_ns):
    net = find_net(board, name)
    if net is None:
        return {"bus": name, "error": "no such net"}
    code = net.GetNetCode()
    length = sum(pcbnew.ToMM(t.GetLength()) for t in board.GetTracks()
                 if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == code)
    vias = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == code)
    pins = len(net_pads(board, code))
    c_pf = length * pf_mm + vias * pf_via + pins * pf_pin
    rise = RISE_K * pullup * c_pf * 1e-12 * 1e9
    return {"bus": net.GetNetname(), "track_mm": round(length, 1), "vias": vias, "pins": pins, "pullup_ohm": pullup,
            "pf": round(c_pf, 1), "rise_ns": round(rise, 1), "limit_ns": limit_ns, "max_pf": BUS_MAX_PF}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board")
    ap.add_argument("--rails", help="L-21: comma list of NET:AMPS, e.g. 1V8:0.032,3V3_LED:0.24")
    ap.add_argument("--copper-oz", type=float, default=1.0, help="copper weight, oz (35 um per oz)")
    ap.add_argument("--source", help="footprint the rails enter the board through (default: the first J* on the net)")
    ap.add_argument("--max-drop-mv", type=float, help="L-21: grade the IR drop against this (default: report only)")
    ap.add_argument("--bus", help="L-45: comma list of bus nets, e.g. I2C0_SENSOR_SCL")
    ap.add_argument("--pullup", type=float, default=1500.0, help="bus pull-up, ohm")
    ap.add_argument("--pf-per-mm", type=float, default=0.1)
    ap.add_argument("--pf-per-via", type=float, default=0.1)
    ap.add_argument("--pf-per-pin", type=float, default=5.0)
    ap.add_argument("--limit-ns", type=float, default=300.0, help="rise time limit (300 fast mode, 1000 standard)")
    ap.add_argument("--json", help="write every rail and bus here")
    ap.add_argument("--list", type=int, default=5, help="how many pads of each rail to print, farthest first")
    args = ap.parse_args()
    if not args.rails and not args.bus:
        ap.error("give --rails and/or --bus")

    board = pcbnew.LoadBoard(args.board)
    rails, buses = [], []
    fail = False
    for spec in (args.rails or "").split(","):
        if not spec.strip():
            continue
        name, _, amps = spec.partition(":")
        try:
            amps = float(amps)
        except ValueError:
            sys.exit(f"--rails: {spec!r}: use NET:AMPS")
        r = rail_drop(board, name.strip(), amps, args.copper_oz, args.source)
        rails.append(r)
        if "error" in r:
            grade, why = "FAIL", r["error"]
            fail = True
        elif r["farthest"] is None:
            grade = "FAIL"
            fail = True
            why = (f"no path from {r['source']} to any of {len(r['missing'])} pads "
                   f"({r['tracks']} tracks, {r['vias']} vias on the net)")
        else:
            f = r["farthest"]
            over = args.max_drop_mv is not None and f["drop_mv"] > args.max_drop_mv
            grade = "FAIL" if over else ("warn" if r["missing"] else "ok")
            fail = fail or over
            why = (f"farthest {f['pad']} ({f['at'][0]:.2f}, {f['at'][1]:.2f}): {f['mohm']:.1f} mOhm, "
                   f"{f['drop_mv']:.2f} mV at {amps} A from {r['source']}; "
                   f"{len(r['reached'])} of {len(r['reached']) + len(r['missing'])} pads reached"
                   + (f", no path to {', '.join(r['missing'][:6])}" + (" ..." if len(r['missing']) > 6 else "")
                      if r["missing"] else "")
                   + (f"; pour on {', '.join(r['pours'])} taken as 0 ohm" if r["pours"] else "")
                   + (f" (limit {args.max_drop_mv} mV)" if args.max_drop_mv is not None else ""))
        print(f"{grade:4}  rail-drop  {r['rail']:16} {why}")
        for p in r.get("reached", [])[:args.list]:
            print(f"        {p['pad']:10} ({p['at'][0]:.2f}, {p['at'][1]:.2f})  {p['mohm']:8.1f} mOhm  {p['drop_mv']:7.2f} mV")
    for name in (args.bus or "").split(","):
        if not name.strip():
            continue
        b = bus_cap(board, name.strip(), args.pullup, args.pf_per_mm, args.pf_per_via, args.pf_per_pin, args.limit_ns)
        buses.append(b)
        if "error" in b:
            grade, why = "FAIL", b["error"]
            fail = True
        else:
            over = b["rise_ns"] > args.limit_ns or b["pf"] > BUS_MAX_PF
            grade = "FAIL" if over else "ok"
            fail = fail or over
            why = (f"{b['track_mm']} mm of track, {b['vias']} vias, {b['pins']} pins: {b['pf']} pF; "
                   f"{args.pullup:.0f} ohm pull-up: {b['rise_ns']} ns rise (limit {args.limit_ns:.0f} ns, {BUS_MAX_PF:.0f} pF)")
        print(f"{grade:4}  bus-cap    {b['bus']:16} {why}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"board": args.board, "rails": rails, "buses": buses}, fh, indent=1)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
