#!/usr/bin/env python3
"""Load a KiCad netlist (kicadsexpr) for the electrical checks, and run the first one.

Import it and extend per rubric line rather than rewriting it:

    from netlist import load
    comps, nets, pins_of = load("review/netlist.net")

  comps    refdes -> {value, fp, <every component field>}
  nets     net name -> [(refdes, pin, pinfunction, pintype)]
  pins_of  refdes -> [(net, pin, pinfunction, pintype)]

Run directly, it prints every power_in pin with the caps to GND on its net (C-1).

Usage:
    python3 netlist.py review/netlist.net
"""
import collections, re, sys


def parse(s):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', s); st = [[]]
    for t in toks:
        if t == '(': st.append([])
        elif t == ')': v = st.pop(); st[-1].append(v)
        else: st[-1].append(t.strip('"'))
    return st[0][0]


def kids(n, k): return [c for c in n[1:] if isinstance(c, list) and c and c[0] == k]


def one(n, k, d=None):
    c = kids(n, k); return c[0][1] if c and len(c[0]) > 1 else d


def load(path):
    root = parse(open(path).read())
    comps = {}
    for c in kids(kids(root, 'components')[0], 'comp'):
        f = kids(c, 'fields')
        flds = {one(x, 'name'): (x[2] if len(x) > 2 else '') for x in (kids(f[0], 'field') if f else [])}
        comps[one(c, 'ref')] = dict(value=one(c, 'value'), fp=one(c, 'footprint'), **flds)
    nets, pins_of = {}, collections.defaultdict(list)
    for n in kids(kids(root, 'nets')[0], 'net'):
        name = one(n, 'name')
        nets[name] = [(one(x, 'ref'), one(x, 'pin'), one(x, 'pinfunction') or '', one(x, 'pintype') or '')
                      for x in kids(n, 'node')]
        for ref, pin, fn, ty in nets[name]: pins_of[ref].append((name, pin, fn, ty))
    return comps, nets, pins_of


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    comps, nets, pins_of = load(sys.argv[1])
    # every power_in pin should see a cap to GND on its own net
    for ref, plist in sorted(pins_of.items()):
        for net, pin, fn, ty in plist:
            if ty != 'power_in': continue
            caps = [r for r, p, _, _ in nets[net] if r.startswith('C') and any(
                n2 == 'GND' for n2, _, _, _ in pins_of[r])]
            print(f"{ref}.{pin} {fn:14} {net:20} caps={caps or 'NONE'}")


if __name__ == "__main__":
    main()
