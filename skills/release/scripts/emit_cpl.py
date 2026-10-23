#!/usr/bin/env python3
"""KiCad pos CSV -> JLCPCB CPL. Drops MH/FID/TP, renames columns, applies a
per-footprint rotation offset. Offsets marked VERIFY are community starters,
not confirmed against a JLC order; confirm in JLC's placement preview.
usage: emit_cpl.py board-pos.csv out-cpl.csv [--rotations extra.csv]
extra.csv rows: <regex on Package column>,<offset degrees>"""
import csv, re, sys

EXCLUDE = ("MH", "FID", "TP")            # house rule: never in BOM or CPL
# (regex, offset, verified) — first match wins. Applied to top and bottom
# alike; bottom-side handling itself is VERIFY (see jlcpcb-package.md).
STARTERS = [
    (r"^SOT-23", 180, False), (r"^SOT-223", 180, False), (r"^SOT-353", 180, False),
    (r"^SOD-123", 180, False), (r"^SOD-323", 180, False), (r"^D_SOD-", 180, False),
    (r"^SOIC-", 270, False), (r"^SOP-", 270, False), (r"^TSSOP-", 270, False),
    (r"^VSSOP-", 270, False), (r"^MSOP-", 270, False),
    (r"^QFN-", 270, False), (r"^DFN-", 270, False),
    (r"^LQFP-", 270, False), (r"^TQFP-", 270, False),
    (r"^R_Array_Convex_", 90, False), (r"^LED_WS2812B", 180, False),
    (r"^USB_C_Receptacle", 180, False),
]

def load_extra(path):
    with open(path, newline="") as f:
        return [(r[0], float(r[1]), True) for r in csv.reader(f) if r and r[0][0] != "#"]

def main(a):
    rot = load_extra(a[a.index("--rotations") + 1]) if "--rotations" in a else []
    rot += STARTERS                          # explicit (verified) rows win
    unverified, written = set(), 0
    with open(a[0], newline="") as fi, open(a[1], "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in csv.DictReader(fi):
            ref = r["Ref"]
            if re.match(r"^(%s)\d" % "|".join(EXCLUDE), ref):
                continue
            off = 0.0
            for rx, deg, ok in rot:
                if re.search(rx, r["Package"]):
                    off = deg
                    if not ok: unverified.add(r["Package"])
                    break
            side = "Top" if r["Side"].lower() in ("top", "front", "f") else "Bottom"
            w.writerow([ref, f'{float(r["PosX"]):.4f}', f'{float(r["PosY"]):.4f}',
                        side, f'{(float(r["Rot"]) + off) % 360:.1f}'])
            written += 1
    print(f"{written} placements -> {a[1]}")
    for p in sorted(unverified):
        print(f"VERIFY rotation offset in JLC preview: {p}")

if __name__ == "__main__":
    main(sys.argv[1:])
