"""Which pin meets which, across a cable or a board-to-board joint, and what every wrong install does.

The paper doll in code. Given each connector's facts from its datasheet and how the boards sit in the
assembly, it works out the pin-to-pin map for the reference install and for each way the joint can go
together wrong (cable turned over, an extra half twist, ends swapped, a one-contact shift), then grades
each against the two boards' nets: which rails short, which rail lands on which, what opens.

Model (assembly frame, z up). For each end:
  m    the direction from the connector to its board (+z for a connector under a face-up board)
  d    the insertion direction: the way the cable moves to enter the mouth
  pin 1 is on the side  p = m x d.  This encodes the usual datasheet rule "looking into the mouth
       from the cable side, with the connector on its board, pin 1 is on the right"; a connector whose
       datasheet puts pin 1 on the left sets "pin1": "left" and p flips.
The cable is a strip with its conductors counted 1..N across its width along e = +y at end A. A half
twist turns e (and the face) over at end B. Turning the whole cable over flips both ends together.

Contacts: "both" (dual-contact, mates either face), "toward_board" or "away_from_board" (single-sided).
A single-sided end mates only when the cable's exposed face at that end points at the contacts; a
mismatch is an open, which is safe, and is reported as "no contact".

Input JSON (see the sensor-array example in references/sensor-array.json):
  {"pins": 8,
   "ends": {"A": {"name": "main J3", "m": [0,0,1], "d": [-1,0,0], "contacts": "both",
                  "nets": {"1": "3V3_LED", ...}},
            "B": {"name": "sensor J1", "m": [0,0,1], "d": [1,0,0], "contacts": "both", "nets": {...}}},
   "cable": {"twist": false, "exposed_A": [0,0,1], "exposed_B": [0,0,1], "shift_possible": false},
   "ground": ["GND"], "power": ["3V3_LED", "1V8"]}

Usage:
  pin_map.py config.json [--svg doll.svg] [--json out.json]
Exit status 1 when the reference install is not net-for-net correct.
"""
import argparse
import json
import sys


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def neg(a):
    return [-x for x in a]


def pin1_dir(end):
    p = cross(end["m"], end["d"])
    return neg(p) if end.get("pin1", "right") == "left" else p


def pin_for_conductor(j, n, p, e):
    """Pin number at an end for conductor j (1 at the -e edge), when pin 1 lies toward p."""
    s = dot(p, e)
    if abs(s) < 1e-9:
        raise ValueError("pin-1 direction is not across the cable: check m and d")
    return n + 1 - j if s > 0 else j


def contact_ok(end, exposed):
    c = end.get("contacts", "both")
    if c == "both":
        return True
    toward = end["m"] if c == "toward_board" else neg(end["m"])
    return dot(toward, exposed) > 0


def mapping(cfg, twist=False, flip=False, shift=0):
    """Return {pin at A: pin at B} (None where nothing lands) and whether each end makes contact."""
    n = cfg["pins"]
    A, B = cfg["ends"]["A"], cfg["ends"]["B"]
    cab = cfg.get("cable", {})
    eA = [0, 1, 0]
    exA = cab.get("exposed_A", [0, 0, 1])
    exB = cab.get("exposed_B", [0, 0, 1])
    tw = bool(cab.get("twist", False)) ^ twist
    if flip:                       # the whole cable turned over: both ends' width and faces reverse
        eA, exA, exB = neg(eA), neg(exA), neg(exB)
    eB = neg(eA) if tw else eA
    if tw:
        exB = neg(exB)
    pA, pB = pin1_dir(A), pin1_dir(B)
    m = {}
    for j in range(1, n + 1):
        a = pin_for_conductor(j, n, pA, eA)
        jb = j + shift
        m[a] = pin_for_conductor(jb, n, pB, eB) if 1 <= jb <= n else None
    return m, contact_ok(A, exA), contact_ok(B, exB)


def grade(cfg, m, okA, okB):
    A, B = cfg["ends"]["A"], cfg["ends"]["B"]
    gnd, pwr = set(cfg.get("ground", ["GND"])), set(cfg.get("power", []))
    if not (okA and okB):
        return {"verdict": "no contact", "severity": "safe", "issues": []}
    joined = {}
    for a, b in m.items():
        na = A["nets"].get(str(a))
        nb = B["nets"].get(str(b)) if b else None
        if na is None and nb is None:
            continue
        joined.setdefault(na, set()).add(nb)
    issues, sev, seen = [], 0, set()
    for na, nbs in joined.items():
        for nb in nbs:
            if na == nb or frozenset((na, nb)) in seen:
                continue
            seen.add(frozenset((na, nb)))
            if nb is None or na is None:
                issues.append(f"{na or nb} open"); sev = max(sev, 1); continue
            if (na in pwr and nb in gnd) or (na in gnd and nb in pwr):
                issues.append(f"{na} -> {nb}: rail onto ground (short / reverse power)"); sev = max(sev, 3)
            elif na in pwr and nb in pwr:
                issues.append(f"{na} -> {nb}: wrong rail"); sev = max(sev, 3)
            elif na in pwr or nb in pwr:
                issues.append(f"{na} -> {nb}: rail onto a signal"); sev = max(sev, 3)
            elif na in gnd or nb in gnd:
                issues.append(f"{na} -> {nb}: signal grounded"); sev = max(sev, 2)
            else:
                issues.append(f"{na} -> {nb}: signals swapped"); sev = max(sev, 1)
    # a net at A that lands on several nets at B, or the reverse, joins them: a short
    for na, nbs in joined.items():
        real = {x for x in nbs if x}
        if len(real) > 1:
            issues.append(f"{na} joins {sorted(real)} at {B['name']}")
            sev = max(sev, 3 if real & (gnd | pwr) else 2)
    names = ["correct", "degraded (no damage expected)", "fails (signal fault)", "DAMAGE"]
    return {"verdict": names[sev], "severity": ["ok", "minor", "major", "critical"][sev], "issues": issues}


def cases(cfg):
    out = [("reference install", dict())]
    out.append(("cable turned over", dict(flip=True)))
    out.append(("extra half twist", dict(twist=True)))
    out.append(("half twist and turned over", dict(twist=True, flip=True)))
    if cfg.get("cable", {}).get("shift_possible"):
        out.append(("shifted one contact (+1)", dict(shift=1)))
        out.append(("shifted one contact (-1)", dict(shift=-1)))
    res = []
    for name, kw in out:
        m, okA, okB = mapping(cfg, **kw)
        g = grade(cfg, m, okA, okB)
        res.append({"case": name, "map": {str(k): v for k, v in sorted(m.items())}, **g})
    return res


def svg(cfg, res, path):
    """A 1:1 paper doll: each end seen from the cable side, pins and nets, the strip with conductor numbers."""
    n = cfg["pins"]
    pitch = cfg.get("pitch_mm", 0.5)
    scale = max(1.0, 3.0 / pitch)              # enlarged view beside the 1:1 one so labels are legible
    W, H = 190, 120
    A, B = cfg["ends"]["A"], cfg["ends"]["B"]
    ref = res[0]["map"]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" '
         'font-family="Helvetica,Arial,sans-serif">',
         '<rect width="100%" height="100%" fill="white"/>',
         f'<text x="5" y="8" font-size="4">Paper doll: {A["name"]} to {B["name"]}, reference install. '
         'Print at 100%; the 10 mm bar must measure 10 mm.</text>',
         '<line x1="5" y1="12" x2="15" y2="12" stroke="black" stroke-width="0.4"/>'
         '<text x="17" y="13" font-size="3">10 mm</text>']
    for col, (end, label) in enumerate(((A, "A"), (B, "B"))):
        x0 = 10 + col * 95
        s.append(f'<text x="{x0}" y="24" font-size="4" font-weight="bold">{label}: {end["name"]}</text>')
        s.append(f'<text x="{x0}" y="29" font-size="3">seen from the cable side, board above; '
                 f'pin 1 on the {end.get("pin1", "right")}</text>')
        # enlarged pin row; pin 1 at the side the datasheet gives
        # left to right as the viewer sees it: pin 1 at the right unless the datasheet says left
        order = list(range(1, n + 1))
        if end.get("pin1", "right") == "right":
            order = order[::-1]
        for i, k in enumerate(order):
            x = x0 + i * pitch * scale
            s.append(f'<rect x="{x:.2f}" y="34" width="{pitch*scale*0.6:.2f}" height="10" fill="#c8963e"/>')
            s.append(f'<text x="{x+0.3:.2f}" y="49" font-size="2.6">{k}</text>')
            net = end["nets"].get(str(k), "")
            s.append(f'<text x="{x+0.3:.2f}" y="52" font-size="2" transform="rotate(90 {x+0.3:.2f} 52)">{net}</text>')
        # 1:1 tail outline
        tw = n * pitch
        s.append(f'<rect x="{x0}" y="85" width="{tw:.2f}" height="4" fill="none" stroke="black" stroke-width="0.2"/>')
        s.append(f'<text x="{x0}" y="94" font-size="2.6">1:1 tail ({tw:.2f} mm): cut out, mark pin 1, fold</text>')
    y = 100
    for r in res:
        s.append(f'<text x="5" y="{y}" font-size="2.8">{r["case"]}: {r["verdict"]}'
                 + (f' ({"; ".join(r["issues"][:2])})' if r["issues"] else "") + '</text>')
        y += 4
    s.append('</svg>')
    open(path, "w").write("\n".join(s))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--svg")
    ap.add_argument("--json")
    o = ap.parse_args(argv)
    cfg = json.load(open(o.config))
    res = cases(cfg)
    A, B = cfg["ends"]["A"]["name"], cfg["ends"]["B"]["name"]
    for r in res:
        print(f"{r['case']:28s} {r['verdict']}")
        if r["case"] == "reference install":
            print("  " + "  ".join(f"{A}.{a}->{B}.{b}" for a, b in r["map"].items()))
        for i in r["issues"]:
            print(f"    {i}")
    if o.svg:
        svg(cfg, res, o.svg)
    if o.json:
        json.dump(res, open(o.json, "w"), indent=2)
    return 0 if res[0]["severity"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
