#!/usr/bin/env python3
"""IPC-7351B land pattern, density level B (nominal). Two-sided or four-sided
row packages plus QFN/DFN thermal-pad paste windows. Numbers are in mm.
Usage:  python3 ipc7351.py gullwing  L=4.80,5.00 T=0.40,1.27 W=0.31,0.51 pitch=1.27 n=8
        python3 ipc7351.py noleads   L=2.90,3.10 T=0.30,0.50 W=0.20,0.30 pitch=0.65 n=8
        python3 ipc7351.py chip      L=1.50,1.70 T=0.25,0.45 W=0.70,0.90
        python3 ipc7351.py paste     W=1.60 H=2.40 [cov=0.6] [n=1 m=2]
L = lead span (tip to tip, min,max), T = lead length along the span, W = lead width.
Tolerance stack on the inner gap is worst case; IPC's own calculator uses an RMS
span and gives slightly shorter pads. Either is fine at level B. Change the
constants below if your copy of IPC-7351 disagrees; nothing else encodes a standard.
"""
import math, sys

F, P, COURTYARD = 0.05, 0.025, 0.25          # fabrication, placement, courtyard excess (level B)
FILLETS = {                                   # toe, heel, side goals, level B
    "gullwing": (0.35, 0.35, 0.03),           # SOIC, TSSOP, QFP, SOT; use side 0.01 if pitch <= 0.625
    "noleads":  (0.30, 0.00, -0.04),          # QFN, DFN, SON (pull-back leads: toe 0.20)
    "chip":     (0.35, 0.00, 0.00),           # 0603 and larger; 0402/0201 need the IPC table, not this
}

def land(kind, L, T, W, pitch=None, n=None):
    Jt, Jh, Js = FILLETS[kind]
    Lmin, Lmax = L; Tmin, Tmax = T; Wmin, Wmax = W
    Smin, Smax = Lmin - 2 * Tmax, Lmax - 2 * Tmin          # gap between lead tips, worst case
    rss = lambda c: math.sqrt(c * c + F * F + P * P)         # tolerance stack, root-sum-square
    Zmax = Lmin + 2 * Jt + rss(Lmax - Lmin)                  # outer extent of the two pads
    Gmin = Smax - 2 * Jh - rss(Smax - Smin)                  # inner gap between the two pads
    Xmax = Wmin + 2 * Js + rss(Wmax - Wmin)                  # pad width
    length, width, centre = (Zmax - Gmin) / 2, Xmax, (Zmax + Gmin) / 4
    r = lambda v: round(v + 1e-9, 2)
    print(f"{kind}: Z={r(Zmax)} G={r(Gmin)} X={r(Xmax)}")
    print(f"pad size {r(length)} x {r(width)}  (long axis along the span), centre at +/-{r(centre)} from body centre")
    if pitch and n:
        ys = [round((i - (n - 1) / 2) * pitch, 3) for i in range(n)]
        print(f"{n} pads per side at pitch {pitch}: {ys}")
        if width > pitch - 0.20:
            print(f"WARNING pad width {r(width)} leaves {r(pitch - width)} between pads; keep >= 0.20 for the mask web")
    print(f"courtyard: body/land extents + {COURTYARD} each side (Zmax/2 + {COURTYARD} = {r(Zmax / 2 + COURTYARD)} from centre)")

def paste(W, H, cov=0.6, n=None, m=None):
    n = n or max(1, round(W / 1.5)); m = m or max(1, round(H / 1.5))
    k = math.sqrt(cov)                                       # each window scales both axes by sqrt(cov)
    w, h = W / n * k, H / m * k
    gx, gy = W / n - w, H / m - h
    print(f"thermal pad {W} x {H}: {n} x {m} paste windows {w:.2f} x {h:.2f}, gaps {gx:.2f}/{gy:.2f}, coverage {n*m*w*h/(W*H):.0%}")
    for i in range(n):
        for j in range(m):
            print(f"  (pad \"\" smd rect (at {((i-(n-1)/2)*W/n):.3f} {((j-(m-1)/2)*H/m):.3f}) (size {w:.2f} {h:.2f}) (layers \"F.Paste\"))")
    if min(gx, gy) < 0.20: print("WARNING stencil web under 0.20 mm; use fewer windows")

if __name__ == "__main__":
    kind, kw = sys.argv[1], {k: [float(x) for x in v.split(",")] for k, v in (a.split("=") for a in sys.argv[2:])}
    if kind == "paste":
        paste(kw["W"][0], kw["H"][0], kw.get("cov", [0.6])[0], int(kw["n"][0]) if "n" in kw else None, int(kw["m"][0]) if "m" in kw else None)
    else:
        land(kind, kw["L"], kw["T"], kw["W"], kw.get("pitch", [None])[0], int(kw["n"][0]) if "n" in kw else None)
