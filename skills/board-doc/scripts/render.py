#!/usr/bin/env python3
"""Render the standard board views for a board documentation page.

Two PNGs, top and bottom, orthographic. Nothing else: the isometric view, the
edge views and the dimensioned outline drawing were all considered and cut.

The frame is sized to the board outline and the zoom derived from it, so a long
thin flex and a squat rigid board both fill their image.

    render.py <board.kicad_pcb> --out DIR [--force]
"""
import argparse, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kx

# kicad-cli is not on PATH in a default macOS KiCad install.
CLI_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "/usr/bin/kicad-cli",
    "/usr/local/bin/kicad-cli",
]

SIDES = ("top", "bottom")


def find_cli():
    found = shutil.which("kicad-cli")
    if found:
        return found
    for path in CLI_CANDIDATES:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    sys.exit(
        "kicad-cli not found. Searched PATH and:\n  "
        + "\n  ".join(CLI_CANDIDATES)
        + "\nInstall KiCad 10, or put kicad-cli on PATH."
    )


def board_aspect(pcb_path):
    """Width/height of the Edge.Cuts outline, so the image frame can match the
    board instead of wasting two thirds of a 16:9 render on background."""
    try:
        board = kx.load(pcb_path)
    except Exception:
        return None
    xs, ys = [], []
    for item in board:
        if not isinstance(item, list) or not str(item[0]).startswith("gr_"):
            continue
        layer = kx.find1(item, "layer")
        if not layer or str(layer[1]) != "Edge.Cuts":
            continue
        for key in ("start", "end", "mid", "center"):
            for pt in kx.find(item, key):
                xs.append(float(pt[1]))
                ys.append(float(pt[2]))
        for pts in kx.find(item, "pts"):
            for xy in kx.find(pts, "xy"):
                xs.append(float(xy[1]))
                ys.append(float(xy[2]))
    if len(xs) < 2:
        return None
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    return (w / h) if h > 0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pcb")
    ap.add_argument("--out", required=True, help="asset directory for this board rev")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--zoom", type=float, default=None,
                    help="camera zoom; default is derived from the board aspect ratio "
                         "to fill ~90%% of the frame")
    ap.add_argument("--force", action="store_true",
                    help="overwrite renders that already exist (see the freeze rule in SKILL.md)")
    args = ap.parse_args()

    if not os.path.isfile(args.pcb):
        sys.exit(f"no such board file: {args.pcb}")

    cli = find_cli()
    os.makedirs(args.out, exist_ok=True)

    # Frame the board rather than a fixed 16:9 -- a 76 x 32 mm board in a 16:9
    # frame is mostly background -- then pick a zoom that fills that frame.
    #
    # kicad-cli's --zoom is not a fill fraction. Measured on two real boards
    # across four zoom levels, with the frame matched to the board:
    #
    #   fill_percent ~= 100 * zoom / aspect
    #
    # (aspect 2.375: zoom 2.2 -> 95%. aspect 6.46:
    #  zoom 2.2 -> 34%, 3.5 -> 54%, 5.0 -> 77%, 6.5 -> 100%.)
    #
    # So the zoom has to track the aspect ratio. 0.9 leaves a small margin;
    # filling to the edge crops the silkscreen on some boards.
    aspect = board_aspect(args.pcb)
    if aspect:
        if aspect >= 1.0:
            width = args.width
            height = max(200, round(width / aspect))
        else:
            height = args.width
            width = max(200, round(height * aspect))
        zoom = args.zoom if args.zoom else round(0.9 * max(aspect, 1.0 / aspect), 2)
    else:
        width, height = args.width, round(args.width * 9 / 16)
        zoom = args.zoom or 1.0
        print("warn: no Edge.Cuts outline found; using a 16:9 frame and zoom 1",
              file=sys.stderr)

    for side in SIDES:
        dest = os.path.join(args.out, f"board_{side}.png")
        if os.path.exists(dest) and not args.force:
            print(f"skip  {dest} (exists; --force to overwrite)")
            continue
        cmd = [cli, "pcb", "render", "--side", side,
               "-w", str(width), "-h", str(height),
               "--zoom", str(zoom),
               "--quality", "high", "--background", "opaque",
               "-o", dest, args.pcb]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.exit(f"kicad-cli render failed for {side}:\n{proc.stderr.strip()}")
        print(f"wrote {dest}")


if __name__ == "__main__":
    main()
