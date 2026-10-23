"""How many layers does a BGA or WLCSP breakout need, and do an array's lanes fit?

Two questions, answered with geometry before anything is routed (hdi-breakout steps 2 and 3).

ball  -- one part's ball field. For the pitch, the ball pad, the track and space, and each via's
         capture pad, it reports how many tracks pass between two balls orthogonally and
         diagonally, whether a dogbone via fits between four balls, on the surface and on a layer where every ball has a via-in-pad, how many
         rings the field has, and an estimate of the signal layers the escape needs. With
         --board and --ref it reads the footprint from a .kicad_pcb (KiCad's python) and also
         counts the connected balls per ring, leaving out plane nets (--plane-nets), which need a
         via and no lane.

lanes -- an array's lane budget. For each layer, give the free spans a track can run along
         (the gaps between via columns, ball fields, bands), as WIDTHxCOUNT. It counts the
         tracks that fit in each span and compares the total with --demand, the nets that must
         pass the cell. A shortfall is the "needs more layers" answer, before routing.

Estimate, not proof. A layer escapes its outer row directly and one more row per track that fits
between two neighbouring balls (the classic rule); a via-in-pad layer is counted with the capture pad in every
ball. Real fields with NC and plane balls do better; the board mode shows how much.

Usage (plain python3 for the params modes; KiCad's $KPY for --board):
  escape_budget.py ball --pitch 0.4 --pad 0.2 --rows 4 --cols 4 --track 0.1 --space 0.1 \\
                        [--capture 0.25] [--json out.json]
  escape_budget.py ball --board b.kicad_pcb --ref U1 --track 0.1 --space 0.1 --capture 0.25 \\
                        [--plane-nets GND,1V8,3V3_LED]
  escape_budget.py lanes --track 0.1 --space 0.1 --span In1=0.5x11 --span In4=0.9x4 --demand 20
"""
import argparse
import json
import math
import sys
from collections import Counter


def tracks_in_gap(gap, track, space):
    """Tracks of width `track` that fit in a copper-to-copper gap, `space` from each side and each other."""
    if gap < track + 2 * space - 1e-9:
        return 0
    return int((gap - space + 1e-9) // (track + space))


def ball_budget(pitch, pad, rows, cols, track, space, capture=None, via_pad=None):
    rings = (min(rows, cols) + 1) // 2
    out = {
        "pitch": pitch, "pad": pad, "rows": rows, "cols": cols, "track": track, "space": space,
        "rings": rings,
        "surface": {
            "gap_orth": round(pitch - pad, 4),
            "gap_diag": round(pitch * math.sqrt(2) - pad, 4),
        },
    }
    s = out["surface"]
    s["tracks_orth"] = tracks_in_gap(s["gap_orth"], track, space)
    s["tracks_diag"] = tracks_in_gap(s["gap_diag"], track, space)
    # rows a layer escapes: the outer row, plus one per track that passes between two outer-row balls.
    # Those neighbours are orthogonal, so the orthogonal gap decides; the diagonal gap only says whether
    # a track can cut a corner inside the field.
    s["rows_escaped"] = 1 + s["tracks_orth"]
    # a dogbone via in the interstitial site (the centre of four balls) fits when the half diagonal holds
    # half the via pad, half the ball pad and one space
    vp = via_pad if via_pad else capture
    if vp:
        s["interstitial_via"] = {"via_pad": vp, "half_diag": round(pitch * math.sqrt(2) / 2, 4),
                                 "needs": round(vp / 2 + pad / 2 + space, 4)}
        s["interstitial_via"]["fits"] = s["interstitial_via"]["half_diag"] >= s["interstitial_via"]["needs"] - 1e-9
    if capture:
        v = {"capture": capture, "gap_orth": round(pitch - capture, 4),
             "gap_diag": round(pitch * math.sqrt(2) - capture, 4)}
        v["tracks_orth"] = tracks_in_gap(v["gap_orth"], track, space)
        v["tracks_diag"] = tracks_in_gap(v["gap_diag"], track, space)
        v["rows_escaped"] = 1 + v["tracks_orth"]
        v["landlocked"] = v["tracks_orth"] == 0 and rings > 1
        out["via_in_pad_layer"] = v
    # layers: the surface takes its rows, each via layer after it takes its own
    left, layers = rings, 0
    per = [s["rows_escaped"]] + [out.get("via_in_pad_layer", s)["rows_escaped"]] * rings
    for r in per:
        if left <= 0:
            break
        left -= r
        layers += 1
    out["signal_layers_estimate"] = layers
    return out


def read_board(board, ref, plane_nets):
    import pcbnew  # KiCad's python
    b = pcbnew.LoadBoard(board)
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        sys.exit(f"{ref} not on {board}")
    pads = [(p.GetNumber(), pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y),
             pcbnew.ToMM(p.GetSize().x), p.GetNetname()) for p in fp.Pads()]
    xs = sorted({round(p[1], 3) for p in pads})
    ys = sorted({round(p[2], 3) for p in pads})
    pitch = min(min(b2 - a for a, b2 in zip(xs, xs[1:])), min(b2 - a for a, b2 in zip(ys, ys[1:])))
    pad = min(p[3] for p in pads)
    cols, rows = len(xs), len(ys)
    per_ring = Counter()
    for num, x, y, _, net in pads:
        i, j = xs.index(round(x, 3)), ys.index(round(y, 3))
        ring = min(i, j, cols - 1 - i, rows - 1 - j)
        kind = ("nc" if not net or net.startswith("unconnected-") else
                "plane" if net in plane_nets else "signal")
        per_ring[(ring, kind)] += 1
    rings = {}
    for (ring, kind), n in sorted(per_ring.items()):
        rings.setdefault(f"ring{ring}", {})[kind] = n
    return round(pitch, 4), round(pad, 4), rows, cols, rings


def lanes_budget(spans, track, space, demand):
    layers, total = {}, 0
    for spec in spans:
        layer, rest = spec.split("=")
        width, _, count = rest.partition("x")
        n = tracks_in_gap(float(width), track, space) * int(count or 1)
        layers.setdefault(layer, 0)
        layers[layer] += n
        total += n
    return {"track": track, "space": space, "per_layer": layers, "available": total,
            "demand": demand, "short_by": max(0, demand - total), "fits": total >= demand}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("ball")
    a.add_argument("--pitch", type=float); a.add_argument("--pad", type=float)
    a.add_argument("--rows", type=int); a.add_argument("--cols", type=int)
    a.add_argument("--board"); a.add_argument("--ref"); a.add_argument("--plane-nets", default="")
    a.add_argument("--track", type=float, required=True); a.add_argument("--space", type=float, required=True)
    a.add_argument("--capture", type=float, help="via capture pad on a via-in-pad layer")
    a.add_argument("--via-pad", type=float, help="dogbone via pad, for the interstitial-site check (default --capture)")
    a.add_argument("--json")
    l = sub.add_parser("lanes")
    l.add_argument("--span", action="append", required=True, help="LAYER=WIDTHxCOUNT, mm")
    l.add_argument("--track", type=float, required=True); l.add_argument("--space", type=float, required=True)
    l.add_argument("--demand", type=int, required=True); l.add_argument("--json")
    o = ap.parse_args(argv)

    if o.mode == "ball":
        rings = None
        if o.board:
            pitch, pad, rows, cols, rings = read_board(o.board, o.ref, set(filter(None, o.plane_nets.split(","))))
        else:
            if None in (o.pitch, o.pad, o.rows, o.cols):
                ap.error("ball needs --pitch --pad --rows --cols, or --board --ref")
            pitch, pad, rows, cols = o.pitch, o.pad, o.rows, o.cols
        res = ball_budget(pitch, pad, rows, cols, o.track, o.space, o.capture, o.via_pad)
        if rings:
            res["balls_per_ring"] = rings
        s = res["surface"]
        print(f"{rows}x{cols} at {pitch} mm, pad {pad}: {res['rings']} rings")
        print(f"  surface: gap {s['gap_orth']} orth / {s['gap_diag']} diag -> "
              f"{s['tracks_orth']} / {s['tracks_diag']} tracks at {o.track}/{o.space}")
        if "interstitial_via" in s:
            iv = s["interstitial_via"]
            print(f"  dogbone via between four balls: half diagonal {iv['half_diag']} vs {iv['needs']} needed -> "
                  + ("fits" if iv["fits"] else "does not fit (escape outward or via-in-pad)"))
        if "via_in_pad_layer" in res:
            v = res["via_in_pad_layer"]
            print(f"  via-in-pad layer (capture {v['capture']}): gap {v['gap_orth']} / {v['gap_diag']} -> "
                  f"{v['tracks_orth']} / {v['tracks_diag']} tracks" + ("  LANDLOCKED" if v["landlocked"] else ""))
        print(f"  signal layers for the escape, estimate: {res['signal_layers_estimate']}")
        if rings:
            for k, v in rings.items():
                print(f"  {k}: {v}")
    else:
        res = lanes_budget(o.span, o.track, o.space, o.demand)
        print(f"lanes {res['per_layer']} = {res['available']} available, {res['demand']} needed: "
              + ("fits" if res["fits"] else f"SHORT BY {res['short_by']}"))
    if o.json:
        json.dump(res, open(o.json, "w"), indent=2)
    return 0 if o.mode == "ball" or res["fits"] else 1


if __name__ == "__main__":
    sys.exit(main())
