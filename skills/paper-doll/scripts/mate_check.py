"""Confirm every signal across a direct board-to-board joint (B2B, mezzanine, stacking header, card edge)
from the boards themselves, placed in their assembly pose.

Each board is placed in the assembly frame by a pose: x, y, z (mm), rotation about z (degrees,
counter-clockwise seen from +z) and whether it sits upside down. Each connector's pads are taken to
world coordinates; a pad of one connector mates the pad of the other that lands on it in plan view
(within --tol, default 0.3 x the pitch). Then the nets on the two pads are compared, through an
optional rename table for nets that change name across the joint.

That is the pin-to-pin map read off the CAD, not off the schematic: a footprint placed on the wrong
side, rotated 180°, or a plug numbered against the receptacle shows up here, before fab. For an
unkeyed connector it also grades the joint rotated 180° about its centre, the other way it can go on.

Input JSON:
  {"boards": {"main": {"pcb": "main.kicad_pcb", "pose": {"x": 0, "y": 0, "z": 0, "rot": 0, "flip": false}},
              "daughter": {"pcb": "d.kicad_pcb", "pose": {"x": 0, "y": 0, "z": 5, "rot": 0, "flip": true}}},
   "joints": [{"a": "main:J5", "b": "daughter:J1", "keyed": false, "rename": {"VBUS_D": "VBUS"}}],
   "ground": ["GND"], "power": ["VBUS", "3V3"]}
A board may give "pads": {"J5": [[num, x, y, net], ...]} instead of "pcb", for tests or a board that
is not in KiCad. Coordinates are KiCad's (mm, y down), as on the board.

Usage (KiCad's $KPY when any board has "pcb"):
  mate_check.py joints.json [--tol 0.15] [--json out.json]
Exit status 1 when any joint, as designed, has a net mismatch or an unmated pad.
"""
import argparse
import json
import math
import sys


def load_pads(board, ref):
    if "pads" in board:
        return [tuple(p) for p in board["pads"][ref]]
    import pcbnew
    b = board.setdefault("_pcb", pcbnew.LoadBoard(board["pcb"]))
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        sys.exit(f"{ref} not on {board['pcb']}")
    return [(p.GetNumber(), pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), p.GetNetname())
            for p in fp.Pads()]


def to_world(pose, x, y):
    """KiCad board coords (y down) to the assembly frame (y up), seen from +z."""
    x, y = x, -y
    if pose.get("flip"):
        x = -x                      # the board turned over about its y axis
    a = math.radians(pose.get("rot", 0))
    return (pose.get("x", 0) + x * math.cos(a) - y * math.sin(a),
            pose.get("y", 0) + x * math.sin(a) + y * math.cos(a))


def pitch_of(pads):
    d = [math.hypot(a[1] - b[1], a[2] - b[2]) for i, a in enumerate(pads) for b in pads[i + 1:]]
    d = [v for v in d if v > 1e-6]
    return min(d) if d else 1.0


def pair(pa, pb, tol):
    """Pads of A matched to the pad of B under them; unmatched on either side."""
    used, out, lone_a = set(), [], []
    for a in pa:
        best, bd = None, tol
        for i, b in enumerate(pb):
            dd = math.hypot(a[1] - b[1], a[2] - b[2])
            if dd <= bd and i not in used:
                best, bd = i, dd
        if best is None:
            lone_a.append(a)
        else:
            used.add(best)
            out.append((a, pb[best]))
    lone_b = [b for i, b in enumerate(pb) if i not in used]
    return out, lone_a, lone_b


def classify(na, nb, gnd, pwr):
    if (na in pwr and nb in gnd) or (na in gnd and nb in pwr):
        return "critical", "rail onto ground"
    if na in pwr and nb in pwr:
        return "critical", "wrong rail"
    if na in pwr or nb in pwr:
        return "critical", "rail onto a signal"
    if na in gnd or nb in gnd:
        return "major", "signal grounded"
    return "major", "signals swapped"


def check_joint(cfg, joint, tol, rot180=False):
    gnd, pwr = set(cfg.get("ground", ["GND"])), set(cfg.get("power", []))
    sides = []
    for key in ("a", "b"):
        bname, ref = joint[key].split(":")
        board = cfg["boards"][bname]
        pads = load_pads(board, ref)
        w = [(n, *to_world(board["pose"], x, y), net) for n, x, y, net in pads]
        sides.append((joint[key], w))
    (na_, pa), (nb_, pb) = sides
    if rot180:
        cx = sum(p[1] for p in pb) / len(pb); cy = sum(p[2] for p in pb) / len(pb)
        pb = [(n, 2 * cx - x, 2 * cy - y, net) for n, x, y, net in pb]
    t = tol if tol else 0.3 * pitch_of(pa)
    pairs, la, lb = pair(pa, pb, t)
    ren = joint.get("rename", {})
    rows, issues, worst = [], [], "ok"
    rank = {"ok": 0, "minor": 1, "major": 2, "critical": 3}
    for a, b in sorted(pairs, key=lambda p: str(p[0][0])):
        neta, netb = ren.get(a[3], a[3]), ren.get(b[3], b[3])
        ok = neta == netb or (not a[3] and not b[3])
        rows.append({"a": f"{na_}.{a[0]}", "b": f"{nb_}.{b[0]}", "net_a": a[3], "net_b": b[3], "ok": ok})
        if not ok:
            if not a[3] or not b[3]:
                sev, why = "minor", "one side unconnected"
            else:
                sev, why = classify(neta, netb, gnd, pwr)
            issues.append(f"{na_}.{a[0]} {a[3] or '(nc)'} meets {nb_}.{b[0]} {b[3] or '(nc)'}: {why}")
            worst = max(worst, sev, key=rank.get)
    for p in la:
        issues.append(f"{na_}.{p[0]} {p[3]} has no pad under it"); worst = max(worst, "major", key=rank.get)
    for p in lb:
        issues.append(f"{nb_}.{p[0]} {p[3]} has no pad over it"); worst = max(worst, "major", key=rank.get)
    return {"joint": f"{na_} / {nb_}", "case": "rotated 180" if rot180 else "as designed",
            "severity": worst, "pairs": rows, "issues": issues}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config"); ap.add_argument("--tol", type=float); ap.add_argument("--json")
    o = ap.parse_args(argv)
    cfg = json.load(open(o.config))
    res, bad = [], False
    for j in cfg["joints"]:
        r = check_joint(cfg, j, o.tol)
        res.append(r); bad |= r["severity"] != "ok"
        if not j.get("keyed", True):
            res.append(check_joint(cfg, j, o.tol, rot180=True))
    for r in res:
        print(f"{r['joint']:30s} {r['case']:12s} {r['severity']}  ({len(r['pairs'])} pads mated)")
        for i in r["issues"]:
            print(f"    {i}")
    if o.json:
        json.dump(res, open(o.json, "w"), indent=2)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
