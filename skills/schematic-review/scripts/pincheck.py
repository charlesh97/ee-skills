#!/usr/bin/env python3
"""Diff every IC's schematic pins against its datasheet pin table.

The netlist carries each node's pin number, the symbol's pin name (`pinfunction`)
and its electrical type. `datasheets/<MPN>/capture.json` carries the datasheet's
own pin table. Comparing them is the one check that catches a wrong symbol, and a
wrong symbol is invisible at every later stage: ERC passes, DRC passes, the board
fabs, and the part is dead on arrival.

Usage:
    pincheck.py <netlist.net> --datasheets datasheets/ [--ref U15] [--json out.json]
"""
import argparse, json, os, re, sys


def parse(s):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', s)
    st = [[]]
    for t in toks:
        if t == "(":
            st.append([])
        elif t == ")":
            v = st.pop()
            st[-1].append(v)
        else:
            st[-1].append(t.strip('"'))
    return st[0][0]


def kids(n, k):
    return [c for c in n[1:] if isinstance(c, list) and c and c[0] == k]


def one(n, k, d=None):
    c = kids(n, k)
    return c[0][1] if c and len(c[0]) > 1 else d


def grid(tbl):
    dd = tbl.get("data") or {}
    nr, nc = dd.get("num_rows", 0), dd.get("num_cols", 0)
    g = [[""] * nc for _ in range(nr)]
    for c in dd.get("table_cells") or []:
        r, cc = c.get("start_row_offset_idx", 0), c.get("start_col_offset_idx", 0)
        if r < nr and cc < nc:
            g[r][cc] = (c.get("text") or "").strip()
    return g


def norm_name(s, pin=None):
    """Normalise a pin name for comparison.

    Three differences are cosmetic and must not read as defects:
      ~{RESET}   KiCad's active-low overbar
      SD0_4      symbol names suffixed with the pin number
      "V REF1"   datasheet subscripts, which extract with a space

    The pin-number suffix is stripped only when it equals this pin's number. A
    blind trailing-digit strip turns the datasheet's own "SD0" into "SD" and the
    comparison then passes for the wrong reason."""
    s = re.sub(r"~\{([^}]*)\}", r"\1", s or "")
    if pin:
        s = re.sub(r"[_\-]" + re.escape(str(pin)) + r"$", "", s)
    s = re.sub(r"[^A-Za-z0-9]", "", s)
    return s.upper().lstrip("N") if s.upper().startswith("N") and len(s) > 2 else s.upper()


HDR_WORDS = ("PIN", "NAME", "NO.", "TYPE", "DESCRIPTION")


def header_depth(g):
    """Pin tables stack 1-3 header rows: some vendors use PIN / NAME+packages, others
    PIN / NAME+NO. / packages+I/O+DESCRIPTION. Find the last leading row that
    is still a header; data starts after it.

    Match whole cells, never substrings. A description reading "Enable pin. Drive
    EN high..." contains "PIN", and a substring test walks the header into the
    data rows and silently drops the first pins."""
    last = 0
    for i, row in enumerate(g[:4]):
        cells = {re.sub(r"\s*\(\d+\)\s*$", "", c).strip().upper() for c in row if c.strip()}
        if cells & set(HDR_WORDS):
            last = i
    return last


def find_pin_table(doc):
    for t in doc.get("tables", []):
        g = grid(t)
        if not g:
            continue
        head = " ".join(" ".join(r) for r in g[:3]).upper()
        if "PIN" in head and "NAME" in head and ("TYPE" in head or "DESCRIPTION" in head):
            return g, (t.get("prov") or [{}])[0].get("page_no")
    return None, None


def package_for_mpn(doc, mpn):
    """A datasheet covers several packages; the orderable-parts table says which
    one this MPN is. Getting this wrong verifies the symbol against the wrong
    pinout and reports a clean pass, so it is resolved explicitly or not at all."""
    for t in doc.get("tables", []):
        g = grid(t)
        if not g or "orderable" not in " ".join(g[0]).lower():
            continue
        pkg_col = next((i for i, h in enumerate(g[0]) if "package" in h.lower()), None)
        if pkg_col is None:
            continue
        for row in g[1:]:
            if row and row[0].strip().upper() == mpn.upper():
                return row[pkg_col]
    return None


def datasheet_pins(doc, mpn):
    g, page = find_pin_table(doc)
    if not g:
        return None, None, None, None
    pkg = package_for_mpn(doc, mpn)
    hd = header_depth(g)
    cols = {}
    for ci in range(len(g[0])):
        label = " ".join(r[ci] for r in g[:hd + 1] if ci < len(r)).strip()
        if label:
            cols[ci] = label
    name_col = next((ci for ci, l in cols.items() if "NAME" in l.upper()), 0)
    pin_col, ambiguous = None, False
    if pkg:
        codes = set(re.findall(r"[A-Z]{2,}", pkg.upper()))
        scored = []
        for ci, l in cols.items():
            if ci == name_col:
                continue
            scored.append((len(codes & set(re.findall(r"[A-Z]{2,}", l.upper()))), ci))
        scored.sort(reverse=True)
        if scored and scored[0][0] > 0:
            pin_col = scored[0][1]
            ambiguous = len(scored) > 1 and scored[1][0] == scored[0][0]
    if pin_col is None:
        # Single-package datasheet: the column right of NAME. Flag it as a guess.
        pin_col, ambiguous = name_col + 1, True
    pins = {}
    for row in g[hd + 1:]:
        if len(row) <= max(name_col, pin_col):
            continue
        nm, num = row[name_col].strip(), row[pin_col].strip()
        if not nm or not num or num in ("-", "—"):
            continue
        for p in re.split(r"[,/]", num):
            p = p.strip()
            if p:
                pins[p] = nm
    return pins, pkg, cols.get(pin_col), (page, ambiguous)


def load_netlist(path):
    root = parse(open(path).read())
    comps = {}
    for c in kids(kids(root, "components")[0], "comp"):
        f = kids(c, "fields")
        flds = {one(x, "name"): (x[2] if len(x) > 2 else "")
                for x in (kids(f[0], "field") if f else [])}
        comps[one(c, "ref")] = {"value": one(c, "value"), "fp": one(c, "footprint"),
                                "mpn": flds.get("MPN") or ""}
    pins = {}
    for n in kids(kids(root, "nets")[0], "net"):
        net = one(n, "name")
        for nd in kids(n, "node"):
            pins.setdefault(one(nd, "ref"), {})[one(nd, "pin")] = {
                "fn": one(nd, "pinfunction") or "",
                "type": one(nd, "pintype") or "",
                "net": net}
    return comps, pins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--datasheets", default="datasheets")
    ap.add_argument("--ref", help="check only this refdes")
    ap.add_argument("--prefixes", default="U",
                    help="refdes prefixes to check (default U). Passives have no pin "
                         "table and would otherwise flood the ungraded list.")
    ap.add_argument("--json", help="write the result as JSON")
    a = ap.parse_args()

    comps, pins = load_netlist(a.netlist)
    report, ungraded = [], []
    for ref in sorted(comps, key=lambda r: (r[0], len(r), r)):
        if a.ref and ref != a.ref:
            continue
        if not a.ref and not any(ref.startswith(x) for x in a.prefixes.split(",")):
            continue
        mpn = (comps[ref]["mpn"] or "").strip()
        if not mpn or mpn == "-" or ref not in pins:
            continue
        cap = os.path.join(a.datasheets, mpn, "capture.json")
        if not os.path.exists(cap):
            ungraded.append((ref, mpn, "no capture.json — run datasheet-extraction"))
            continue
        doc = json.load(open(cap))
        ds, pkg, col, meta = datasheet_pins(doc, mpn)
        if not ds:
            ungraded.append((ref, mpn, "no pin table found in capture"))
            continue
        page, ambiguous = meta
        rows, bad = [], 0
        for p, info in pins[ref].items():
            dsname = ds.get(p)
            if dsname is None:
                verdict = "not_in_datasheet_table"
            elif norm_name(info["fn"], p) == norm_name(dsname, p):
                verdict = "ok"
            else:
                verdict = "MISMATCH"
            if verdict != "ok":
                bad += 1
            rows.append({"pin": p, "datasheet": dsname, "symbol": info["fn"],
                         "type": info["type"], "net": info["net"], "verdict": verdict})
        absent = sorted(set(ds) - set(pins[ref]), key=lambda x: (len(x), x))
        report.append({"ref": ref, "mpn": mpn, "package": pkg, "pin_column": col,
                       "pin_table_page": page, "package_ambiguous": ambiguous,
                       "matched": len(rows) - bad, "flagged": bad,
                       "datasheet_pins_absent": absent, "pins": rows})

    for r in report:
        flag = "  ** PACKAGE COLUMN UNCONFIRMED **" if r["package_ambiguous"] else ""
        print(f"{r['ref']}  {r['mpn']}  package={r['package']!r} "
              f"column={r['pin_column']!r} (p{r['pin_table_page']}){flag}")
        print(f"   matched {r['matched']}, flagged {r['flagged']}, "
              f"datasheet pins not on the symbol: {r['datasheet_pins_absent'] or 'none'}")
        for p in r["pins"]:
            if p["verdict"] != "ok":
                print(f"   {p['verdict']:>22}  pin {p['pin']:<4} datasheet={p['datasheet']} "
                      f"symbol={p['symbol']} net={p['net']}")
    if ungraded:
        print("\nungraded:")
        for ref, mpn, why in ungraded:
            print(f"  {ref:<6} {mpn:<22} {why}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"checked": report, "ungraded": ungraded}, f, indent=1)
        print(f"\nwrote {a.json}")
    total_bad = sum(r["flagged"] for r in report)
    print(f"\n{len(report)} parts checked, {total_bad} pins flagged, {len(ungraded)} ungraded")


if __name__ == "__main__":
    main()
