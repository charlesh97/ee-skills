#!/usr/bin/env python3
"""A Mermaid block diagram seeded from the board's own connectivity.

Nodes are the ICs and connectors; edges are the signal nets they share. Passives
are dropped, and so are power and ground nets -- a diagram where everything
touches GND says nothing.

This is a *seed*, not the finished diagram. It is drawn from the netlist, so it
shows what is connected, never what matters. Collapse the repeated blocks, name
the buses, drop what is obvious, and order it so it reads left to right. The
value of an architecture diagram is the abstraction a person chose; this just
saves the typing and guarantees nothing was left out.

    blocks.py <board.kicad_pcb> [--parts REGEX]
"""
import argparse, collections, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kx

# Rails and references. A net every part touches is not an architectural edge.
# Matched as a prefix, not an exact name: VCC_LED is a rail, and letting it
# through draws a complete mesh between every part that shares it.
POWER = re.compile(
    r"^(GND|AGND|DGND|GNDA|EARTH|VBUS|VCC|VDD|VSS|VEE|VIN|VOUT|VREF|VREG"
    r"|PDREF|AVDD|DVDD|[+-]?\d+V\d*)([_\-].*)?$", re.I)

# A net reaching this many parts is a bus or a rail whatever it is called, and
# drawing it as pairwise edges turns the diagram into a mesh.
FANOUT_LIMIT = 5

# KiCad's auto-name for a net nobody named. Not worth printing.
AUTONAME = re.compile(r"^Net-\(")


def label(nets):
    """One edge label for a bundle of nets.

    A single net gets its name. Several get their common prefix -- but cut at a
    token boundary, so I2C0_SENSOR_SDA and I2C0_SENSOR_SCL read as
    'I2C0_SENSOR×2' rather than the mid-word 'I2C0_SENSOR_S×2'.
    """
    if len(nets) == 1:
        return nets[0]
    if all(AUTONAME.match(n) for n in nets):
        return f"{len(nets)} nets"
    prefix = os.path.commonprefix(nets)
    if "_" in prefix and not prefix.endswith("_"):
        prefix = prefix[:prefix.rindex("_")]
    prefix = prefix.rstrip("_-")
    return f"{prefix}×{len(nets)}" if len(prefix) >= 3 else f"{len(nets)} nets"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcb")
    ap.add_argument("--parts", default=r"^(U|J|P|A|SW|Y)\d+",
                    help="refdes regex for diagram nodes (default: ICs, connectors, "
                         "switches, crystals)")
    args = ap.parse_args()

    if not os.path.isfile(args.pcb):
        sys.exit(f"no such board file: {args.pcb}")
    pat = re.compile(args.parts)
    board = kx.load(args.pcb)

    values, nets = {}, collections.defaultdict(set)
    for fp in kx.find(board, "footprint"):
        try:
            ref = kx.fp_ref(fp)
        except (IndexError, KeyError):
            continue
        if not pat.match(ref):
            continue
        val = [p[2] for p in kx.find(fp, "property") if p[1] == "Value"]
        values[ref] = str(val[0]) if val else ""
        for pad in kx.pads_abs(fp):
            net = pad["net"]
            if net and not net.startswith("unconnected-"):
                nets[net].add(ref)

    edges = collections.defaultdict(list)
    dropped = []
    for net, refs in nets.items():
        if len(refs) < 2:
            continue
        if POWER.match(net):
            continue
        if len(refs) >= FANOUT_LIMIT:
            dropped.append((net, len(refs)))
            continue
        refs = sorted(refs)
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                edges[(a, b)].append(net)

    if not edges:
        sys.exit("no inter-part signal nets found -- nothing to draw")

    linked = {r for pair in edges for r in pair}
    print("```mermaid")
    print("graph LR")
    for ref in sorted(linked, key=lambda r: (r[0], int(re.sub(r"\D", "", r) or 0))):
        val = values.get(ref, "")
        print(f'  {ref}["{ref}<br/>{val}"]' if val else f"  {ref}[{ref}]")
    print()
    for (a, b), ns in sorted(edges.items(), key=lambda kv: -len(kv[1])):
        print(f"  {a} ---|{label(sorted(ns))}| {b}")
    print("```")
    print(f"\nseed: {len(linked)} parts, {len(edges)} edges, from {os.path.basename(args.pcb)}."
          f" Collapse and rename before publishing.", file=sys.stderr)
    for net, n in sorted(dropped, key=lambda t: -t[1]):
        print(f"  dropped as a bus: {net} ({n} parts)", file=sys.stderr)


if __name__ == "__main__":
    main()
