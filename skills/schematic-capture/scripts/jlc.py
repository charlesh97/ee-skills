#!/usr/bin/env python3
"""Live JLC/LCSC part lookup, and the D-45/D-46 check over a schematic's parts.

Adapted from the encoder project's tools/jlc.py (2026-10-01), which queried the same
JLCPCB parts endpoint. The endpoint is JLC's own web API, not a published one: if it
changes shape, fix it here, and never fall back to a part number from memory.

  python3 jlc.py search "100nF 0402 X7R 16V" [-n 8] [--basic]
      Keyword search, as on jlcpcb.com/parts. One line per hit: LCSC code, MPN,
      manufacturer, basic/extended, stock, package, description. --basic keeps
      basic parts only (no per-part loading fee; prefer them for passives).

  python3 jlc.py code C1525 [C25744 ...]
      Exact lookup by LCSC code: does it exist, what MPN it is, basic or extended,
      stock. Exit 1 if any code is not found.

  python3 jlc.py check review/netlist.net [--boards 5] [--json review/parts.json]
      Every part that reaches the BOM is graded (skipped: exclude_from_bom parts,
      power symbols, MH, FID, NT, and TP pads with no MPN):
        fields     MPN, Manufacturer and LCSC present (D-46). LCSC may be CONSIGNED,
                   with a Consigned field saying who supplies it
        exists     the LCSC code is in JLC's library
        mpn        the code's MPN matches the symbol's MPN
        stock      stock >= uses x --boards (a DNP part only warns)
        basic      a passive (R, C, L, FB) on an extended part: warn, prefer basic
        value      R, C, L, FB value text in the D-45 format
      Prints one line per problem and a summary; exit 1 on any FAIL.

Export the netlist first:
  kicad-cli sch export netlist --format kicadsexpr -o review/netlist.net <name>.kicad_sch
"""
import argparse, collections, json, os, re, sys, time, urllib.request

URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
PASSIVE = ("R", "C", "L", "FB")
# D-45 (ee-schematic-rules/rules/schematic.md): number 1-999 with a decimal point, the
# largest SI prefix that keeps it there, ASCII, and the unit on C and L.
NUM = r"(?:[1-9]\d{0,2}(?:\.\d+)?)"
VALUE_RE = {
    "C": re.compile(rf"^{NUM}[pnum]F$"),
    "L": re.compile(rf"^{NUM}[num]H$"),
    "R": re.compile(rf"^(?:0R|{NUM}(?:mR|R|k|M))$"),
    "FB": re.compile(rf"^{NUM}R@{NUM}[kMG]?Hz$"),
}


def search(kw, n=8):
    req = urllib.request.Request(
        URL, data=json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return (d.get("data") or {}).get("componentPageInfo", {}).get("list") or []


def by_code(code):
    """The exact part for an LCSC code, or None."""
    for c in search(code, 10):
        if c.get("componentCode", "").upper() == code.upper():
            return c
    return None


def kind(c):
    return "basic" if c.get("componentLibraryType") == "base" else (
        "preferred-ext" if c.get("preferredComponentFlag") else "extended")


def line(c):
    return (f"{c['componentCode']} | {c['componentModelEn']} | {c['componentBrandEn']} | {kind(c)} | "
            f"stock {c['stockCount']} | {c.get('componentSpecificationEn')} | {(c.get('describe') or '')[:110]}")


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def prefix(ref):
    m = re.match(r"[A-Z#]+", ref.upper())
    return m.group(0) if m else ""


def load_parts(path):
    """refdes -> {value, fields..., _dnp, _exclude} from a kicadsexpr netlist."""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "..", "schematic-review", "scripts"))
    from netlist import parse, kids, one
    root = parse(open(path).read())
    out = {}
    for c in kids(kids(root, "components")[0], "comp"):
        f = kids(c, "fields")
        flds = {one(x, "name"): (x[2] if len(x) > 2 else "") for x in (kids(f[0], "field") if f else [])}
        props = {one(p, "name") for p in kids(c, "property")}
        out[one(c, "ref")] = dict(flds, value=one(c, "value") or "", _dnp="dnp" in props,
                                  _exclude="exclude_from_bom" in props)
    return out


def check(path, boards):
    parts = load_parts(path)
    findings = []

    def add(grade, ref, what, why):
        findings.append({"grade": grade, "ref": ref, "check": what, "why": why})

    uses = collections.Counter()
    graded = {}
    for ref, p in sorted(parts.items()):
        pre = prefix(ref)
        if p["_exclude"] or ref.startswith("#") or pre in ("MH", "FID", "NT"):
            continue
        if pre == "TP" and not (p.get("MPN") or p.get("LCSC")):
            continue                     # a pad test point; a bought loop carries an MPN and is graded
        graded[ref] = p
        rx = VALUE_RE.get(pre)
        if rx and not rx.match(p["value"]):
            add("FAIL", ref, "value", f"value {p['value']!r} is not in the D-45 format")
        missing = [k for k in ("MPN", "Manufacturer", "LCSC") if not (p.get(k) or "").strip()]
        if missing:
            add("FAIL", ref, "fields", f"missing {', '.join(missing)} (D-46)")
        code = (p.get("LCSC") or "").strip()
        if code.upper() == "CONSIGNED":
            if not (p.get("Consigned") or "").strip():
                add("FAIL", ref, "fields", "LCSC is CONSIGNED but no Consigned field says who supplies it")
            continue
        if code:
            if not re.fullmatch(r"C\d+", code, re.I):
                add("FAIL", ref, "fields", f"LCSC {code!r} is not an LCSC code (C followed by digits) or CONSIGNED")
                continue
            if not p["_dnp"]:
                uses[code.upper()] += 1

    looked = {}
    for ref, p in graded.items():
        code = (p.get("LCSC") or "").strip().upper()
        if not re.fullmatch(r"C\d+", code):
            continue
        if code not in looked:
            try:
                looked[code] = by_code(code)
            except Exception as e:
                looked[code] = e
            time.sleep(0.3)
        c = looked[code]
        if isinstance(c, Exception):
            add("FAIL", ref, "exists", f"{code}: lookup failed ({c}); not graded, re-run")
            continue
        if c is None:
            add("FAIL", ref, "exists", f"{code} is not in JLC's parts library")
            continue
        if norm(c["componentModelEn"]) != norm(p.get("MPN")):
            add("FAIL", ref, "mpn", f"{code} is {c['componentModelEn']} ({c['componentBrandEn']}), symbol MPN is {p.get('MPN')!r}")
        elif norm(c["componentBrandEn"])[:6] != norm(p.get("Manufacturer"))[:6]:
            add("warn", ref, "mpn", f"{code} manufacturer is {c['componentBrandEn']!r}, symbol says {p.get('Manufacturer')!r}")
        need = uses[code] * boards
        stock = c.get("stockCount") or 0
        if stock <= 0:
            add("warn" if p["_dnp"] else "FAIL", ref, "stock", f"{code} has no stock at JLC: pick another part or mark it CONSIGNED")
        elif stock < need:
            add("warn" if p["_dnp"] else "FAIL", ref, "stock", f"{code} stock {stock} < {need} ({uses[code]} per board x {boards})")
        if prefix(ref) in PASSIVE and kind(c) == "extended":
            add("warn", ref, "basic", f"{code} is an extended part; a passive should be a JLC basic part where one meets the spec")
    return graded, looked, findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("keyword"); s.add_argument("-n", type=int, default=8)
    s.add_argument("--basic", action="store_true")
    c = sub.add_parser("code"); c.add_argument("codes", nargs="+")
    k = sub.add_parser("check"); k.add_argument("netlist"); k.add_argument("--boards", type=int, default=5)
    k.add_argument("--json")
    args = ap.parse_args()

    if args.cmd == "search":
        hits = search(args.keyword, args.n * (4 if args.basic else 1))
        if args.basic:
            hits = [h for h in hits if h.get("componentLibraryType") == "base"][:args.n]
        for h in hits:
            print(line(h))
        if not hits:
            print("no hits")
        return
    if args.cmd == "code":
        bad = 0
        for code in args.codes:
            h = by_code(code)
            print(line(h) if h else f"{code} | NOT FOUND")
            bad |= h is None
        sys.exit(1 if bad else 0)

    graded, looked, findings = check(args.netlist, args.boards)
    for f in sorted(findings, key=lambda f: (f["grade"] != "FAIL", f["ref"])):
        print(f"{f['grade']:4}  {f['ref']:8} {f['check']:7} {f['why']}")
    nfail = sum(f["grade"] == "FAIL" for f in findings)
    nconsigned = sum((p.get("LCSC") or "").strip().upper() == "CONSIGNED" for p in graded.values())
    print(f"\n{len(graded)} BOM parts, {len(looked)} LCSC codes looked up live, {nconsigned} consigned; "
          f"{nfail} FAIL, {len(findings) - nfail} warn (stock for {args.boards} boards)")
    if args.json:
        json.dump({"netlist": args.netlist, "boards": args.boards, "findings": findings,
                   "parts": {c: (None if not isinstance(v, dict) else
                                 {"mpn": v["componentModelEn"], "manufacturer": v["componentBrandEn"],
                                  "type": kind(v), "stock": v["stockCount"]}) for c, v in looked.items()}},
                  open(args.json, "w"), indent=1)
    sys.exit(1 if nfail else 0)


if __name__ == "__main__":
    main()
