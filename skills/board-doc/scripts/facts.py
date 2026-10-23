#!/usr/bin/env python3
"""The mechanical facts for the Spec table and the revision pin.

Board size, stackup and mounting holes come out of the .kicad_pcb. The pin
comes from git, read-only: the last commit that touched the board's own files,
which is the revision the page describes -- not HEAD, which moves whenever
anything else in the repo changes.

    facts.py <board.kicad_pcb>
"""
import argparse, glob, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kx


def outline(board):
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
    return max(xs) - min(xs), max(ys) - min(ys)


def stackup(board):
    setup = kx.find1(board, "setup")
    st = kx.find1(setup, "stackup") if setup else None
    if not st:
        return None
    copper, total, materials = 0, 0.0, []
    for layer in kx.find(st, "layer"):
        typ = kx.find1(layer, "type")
        thick = kx.find1(layer, "thickness")
        mat = kx.find1(layer, "material")
        if thick:
            total += float(thick[1])
        if typ and str(typ[1]) == "copper":
            copper += 1
        if mat and str(mat[1]) not in materials:
            materials.append(str(mat[1]))
    return copper, total, materials


def holes(board):
    """Mounting holes by drill diameter.

    Only H/MH footprints count. Connectors carry non-plated alignment pegs of
    their own -- a pin header's Ø1.4 mm pegs belong to the
    header, and reporting them as mounting holes is wrong."""
    found = {}
    for fp in kx.find(board, "footprint"):
        try:
            ref = kx.fp_ref(fp)
        except (IndexError, KeyError):
            continue
        if not re.match(r"^(MH|H)\d+", ref):
            continue
        for pad in kx.find(fp, "pad"):
            if str(pad[2]) != "np_thru_hole":
                continue
            drill = kx.find1(pad, "drill")
            if drill:
                found.setdefault(float(drill[1]), set()).add(ref)
    return found


def pin(pcb_path):
    """Read-only git. The last commit touching this board's files, and whether
    they are dirty right now."""
    d = os.path.dirname(os.path.abspath(pcb_path)) or "."
    files = [os.path.abspath(pcb_path)] + sorted(glob.glob(os.path.join(d, "*.kicad_sch")))
    files = [f for f in files if os.path.exists(f)]

    def git(*a):
        try:
            r = subprocess.run(["git", "-C", d] + list(a), capture_output=True,
                               text=True, timeout=15)
            return r.stdout.strip() if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            return None

    if git("rev-parse", "--is-inside-work-tree") != "true":
        return None
    rev = git("log", "-1", "--format=%h|%H|%ad", "--date=short", "--", *files)
    dirty = git("status", "--porcelain", "--", *files)
    remote = git("config", "--get", "remote.origin.url") or ""
    tags = git("tag", "--points-at", rev.split("|")[1]) if rev else ""
    return dict(rev=rev, dirty=bool(dirty), dirty_files=(dirty or "").splitlines(),
                remote=remote, tags=[t for t in (tags or "").splitlines() if t],
                files=[os.path.basename(f) for f in files])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcb")
    args = ap.parse_args()
    if not os.path.isfile(args.pcb):
        sys.exit(f"no such board file: {args.pcb}")
    board = kx.load(args.pcb)

    rows = []
    size = outline(board)
    if size:
        rows.append(("Board size", f"{size[0]:.4g} × {size[1]:.4g} mm"))
    sk = stackup(board)
    if sk:
        copper, total, materials = sk
        mat = "/".join(materials) if materials else "FR4"
        rows.append(("Stackup", f"{copper}-layer {mat}, {total:.3g} mm"))
    hs = holes(board)
    if hs:
        rows.append(("Mounting holes",
                     ", ".join(f"{len(refs)} × Ø{d:g} mm" for d, refs in sorted(hs.items()))))

    print("### Spec\n")
    print("| Parameter | Value |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")

    p = pin(args.pcb)
    print("\n<!-- revision pin -->")
    if not p:
        print("*Not in a git repository — revision unknown.*")
        return
    if not p["rev"]:
        print("*Board files are not committed — this page describes uncommitted work.*")
        return
    short, full, date = p["rev"].split("|")
    url = re.sub(r"(\.git)?$", "", p["remote"]).replace("git@github.com:", "https://github.com/")
    link = f"[`{short}`]({url}/commit/{full})" if url.startswith("http") else f"`{short}`"
    tag = f", tag `{p['tags'][0]}`" if p["tags"] else ""
    print(f"| **Pinned revision** | {link}{tag}, {date} |")
    if p["dirty"]:
        print(f"\n**DIRTY** — {len(p['dirty_files'])} of this board's files have uncommitted "
              f"changes, so the page does not describe {short}:")
        for line in p["dirty_files"]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
