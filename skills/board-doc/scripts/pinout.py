#!/usr/bin/env python3
"""Per-connector pinout drawings and tables, straight out of the .kicad_pcb.

Everything needed is in the board file: pad number, placed position, size,
shape, and net. No netlist export, no schematic, no KiCad install.

The drawing shows the pads at true scale in their placed orientation with the
pin numbers on them, and pin 1 marked. It deliberately carries no net names --
the table underneath does that. Labelling long net names like
INT4_SENSOR_OUT on a 2.54 mm header means either collisions or leader-line
machinery, and the split keeps every drawing legible on every board.

    pinout.py <board.kicad_pcb> --out DIR [--refdes PATTERN] [--force]

Writes <refdes>.svg per connector into DIR, and prints the markdown for the
Connectors section to stdout.
"""
import argparse, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kx

PX_PER_MM = 20.0
MARGIN_MM = 1.6

COPPER = "#c98a3f"
COPPER_EDGE = "#8a5a22"
PIN1 = "#d23b3b"
NUMBER = "#14110d"
SILK = "#9aa0a6"

SILK_LAYERS = ("F.SilkS", "B.SilkS", "F.CrtYd", "B.CrtYd", "F.Fab", "B.Fab")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def real_net(net):
    """KiCad names an unrouted pad `unconnected-(J2-Pin_1-Pad1)`. That is a
    placeholder, not a signal, and printing it in a pinout table reads as if the
    pin has a purpose."""
    return bool(net) and not str(net).startswith("unconnected-")


def fp_layer(fp):
    lay = kx.find1(fp, "layer")
    return str(lay[1]) if lay else "F.Cu"


def fp_value(fp):
    for p in kx.find(fp, "property"):
        if p[1] == "Value":
            return str(p[2])
    return ""


def graphics(fp, fx, fy, fr):
    """Silk/courtyard segments in placed-local mm, as (x1,y1,x2,y2)."""
    out = []
    for g in kx.find(fp, "fp_line") + kx.find(fp, "fp_rect"):
        lay = kx.find1(g, "layer")
        if not lay or str(lay[1]) not in SILK_LAYERS:
            continue
        s, e = kx.find1(g, "start"), kx.find1(g, "end")
        if not s or not e:
            continue
        ax, ay = kx.rot(float(s[1]), float(s[2]), -fr)
        bx, by = kx.rot(float(e[1]), float(e[2]), -fr)
        if g[0] == "fp_rect":
            out += [(ax, ay, bx, ay), (bx, ay, bx, by), (bx, by, ax, by), (ax, by, ax, ay)]
        else:
            out.append((ax, ay, bx, by))
    return out


def collect(fp):
    """Pads with a real pin number, in placed-local mm. Mounting holes have no
    number and are not pins, so they drop out here."""
    fx, fy, fr = kx.fp_at(fp)
    mirror = fp_layer(fp).startswith("B.")
    pads = []
    for p in kx.pads_abs(fp):
        if not p["name"].strip():
            continue
        x, y = p["x"] - fx, p["y"] - fy
        rot = p["rot"]
        if mirror:
            x, rot = -x, (180.0 - rot)
        pads.append(dict(name=p["name"], x=x, y=y, rot=rot, w=p["w"], h=p["h"],
                         shape=p["shape"], rr=p["rr"], net=p["net"]))
    pads.sort(key=lambda p: (len(p["name"]), p["name"]))
    return pads, mirror


def pad_svg(p, first):
    cx, cy = p["x"] * PX_PER_MM, p["y"] * PX_PER_MM
    w, h = p["w"] * PX_PER_MM, p["h"] * PX_PER_MM
    stroke = PIN1 if first else COPPER_EDGE
    sw = 2.5 if first else 1.2
    xf = f' transform="rotate({-p["rot"]:.3f} {cx:.2f} {cy:.2f})"' if p["rot"] % 360 else ""
    if p["shape"] in ("circle", "oval") and abs(p["w"] - p["h"]) < 1e-6:
        body = (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{w/2:.2f}" '
                f'fill="{COPPER}" stroke="{stroke}" stroke-width="{sw}"/>')
    elif p["shape"] == "oval":
        body = (f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{w/2:.2f}" ry="{h/2:.2f}" '
                f'fill="{COPPER}" stroke="{stroke}" stroke-width="{sw}"{xf}/>')
    else:
        r = min(w, h) * p["rr"] if p["shape"] == "roundrect" else 0.0
        body = (f'<rect x="{cx-w/2:.2f}" y="{cy-h/2:.2f}" width="{w:.2f}" height="{h:.2f}" '
                f'rx="{r:.2f}" fill="{COPPER}" stroke="{stroke}" stroke-width="{sw}"{xf}/>')
    fs = max(9.0, min(w, h) * 0.72)
    label = (f'<text x="{cx:.2f}" y="{cy:.2f}" font-size="{fs:.1f}" fill="{NUMBER}" '
             f'font-family="Helvetica,Arial,sans-serif" font-weight="700" '
             f'text-anchor="middle" dominant-baseline="central">{esc(p["name"])}</text>')
    return body + label


def build_svg(pads, gfx):
    xs, ys = [], []
    for p in pads:
        r = max(p["w"], p["h"]) / 2.0
        xs += [p["x"] - r, p["x"] + r]
        ys += [p["y"] - r, p["y"] + r]
    for x1, y1, x2, y2 in gfx:
        xs += [x1, x2]
        ys += [y1, y2]
    x0, x1 = min(xs) - MARGIN_MM, max(xs) + MARGIN_MM
    y0, y1 = min(ys) - MARGIN_MM, max(ys) + MARGIN_MM
    w, h = (x1 - x0) * PX_PER_MM, (y1 - y0) * PX_PER_MM

    parts = [f'<g transform="translate({-x0*PX_PER_MM:.2f} {-y0*PX_PER_MM:.2f})">']
    for gx1, gy1, gx2, gy2 in gfx:
        parts.append(f'<line x1="{gx1*PX_PER_MM:.2f}" y1="{gy1*PX_PER_MM:.2f}" '
                     f'x2="{gx2*PX_PER_MM:.2f}" y2="{gy2*PX_PER_MM:.2f}" '
                     f'stroke="{SILK}" stroke-width="1" stroke-linecap="round"/>')
    for p in pads:
        parts.append(pad_svg(p, p["name"] == "1"))
    parts.append("</g>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
            f'viewBox="0 0 {w:.2f} {h:.2f}">\n  ' + "\n  ".join(parts) + "\n</svg>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcb")
    ap.add_argument("--out", required=True, help="asset directory for this board rev")
    ap.add_argument("--refdes", default=r"^[JP]\d+$", help="refdes regex (default ^[JP]\\d+$)")
    ap.add_argument("--asset-path", default=None,
                    help="image path prefix used in the emitted markdown, relative to the "
                         "doc page (default: the --out path)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite drawings that already exist (see the freeze rule in SKILL.md)")
    args = ap.parse_args()

    if not os.path.isfile(args.pcb):
        sys.exit(f"no such board file: {args.pcb}")
    if args.asset_path is None:
        args.asset_path = args.out
    pat = re.compile(args.refdes)
    board = kx.load(args.pcb)
    os.makedirs(args.out, exist_ok=True)

    found = []
    for fp in kx.find(board, "footprint"):
        try:
            ref = kx.fp_ref(fp)
        except (IndexError, KeyError):
            continue
        if pat.match(ref):
            found.append((ref, fp))
    found.sort(key=lambda t: (len(t[0]), t[0]))

    if not found:
        print(f"no connector footprints matched {args.refdes}", file=sys.stderr)
        return

    blocks = []
    for ref, fp in found:
        pads, mirror = collect(fp)
        if not pads:
            print(f"warn: {ref} has no numbered pads, skipped", file=sys.stderr)
            continue
        fx, fy, fr = kx.fp_at(fp)
        dest = os.path.join(args.out, f"{ref}.svg")
        if os.path.exists(dest) and not args.force:
            print(f"skip  {dest} (exists; --force to overwrite)", file=sys.stderr)
        else:
            with open(dest, "w") as fh:
                fh.write(build_svg(pads, graphics(fp, fx, fy, fr)))
            print(f"wrote {dest}", file=sys.stderr)

        side = "bottom" if mirror else "top"
        view = "viewed from the bottom" if mirror else "viewed from the top"
        rows = "\n".join(
            f'| {p["name"]} | `{p["net"]}` | |' if real_net(p["net"]) else f'| {p["name"]} | *NC* | |'
            for p in pads)
        blocks.append(
            f'#### {ref} — {fp_value(fp)}\n\n'
            f'![{ref} pinout]({args.asset_path.rstrip("/")}/{ref}.svg)\n\n'
            f'{len(pads)}-way, `{str(fp[1])}`, {side} side at '
            f'({fx:g}, {fy:g}) mm rotated {fr:g}°. Drawing {view}; pin 1 outlined in red.\n\n'
            f'| Pin | Net | Note |\n|---|---|---|\n{rows}\n')

    print("### Connectors\n\n" + "\n".join(blocks))


if __name__ == "__main__":
    main()
