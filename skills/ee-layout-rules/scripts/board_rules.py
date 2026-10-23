#!/usr/bin/env python3
"""Put the house board rules (rules/drc.json) into KiCad projects.

Run with KiCad's bundled python, which has pcbnew:
  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3

  $KPY board_rules.py template <out_dir> [--only rigid_4L]
      Build KiCad project templates (one folder each: .kicad_pro, .kicad_pcb with
      the stackup, empty root .kicad_sch, lib tables for the house library ($EE_LIB), meta/info.html).
      KiCad writes the base project itself, so every key is one KiCad knows; the
      house values are then applied on top.

  $KPY board_rules.py apply <project.kicad_pro> --profile rigid|flex [--dry-run]
      Apply the rules to an existing project. Floors are raised to the house
      values (a board's stricter floor is kept unless --exact); the Default net
      class is set; the predefined track and via lists become the union of what the
      board had and the profile's lists; other net classes and their pattern
      assignments are left alone; Power is added if missing. Prints every change,
      and warns when a predefined via or width sits below the floor.
      Close the project in KiCad first, or KiCad writes its copy back over this.

  $KPY board_rules.py check <board.kicad_pcb> --profile rigid|flex
      Load the board through pcbnew and confirm KiCad itself reads back the
      floors, lists and net classes. Exit 1 on any mismatch.
"""
import argparse, json, os, shutil, sys, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, "..", "rules", "drc.json")
EPS = 1e-6


def load_rules():
    return json.load(open(RULES))


def strip(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def lists_for(prof, have_tw=(), have_via=()):
    tw = sorted({round(x, 4) for x in list(prof["track_widths"]) + [x for x in have_tw if x > 0]})
    vias = {(round(v["diameter"], 4), round(v["drill"], 4)) for v in prof["vias"]}
    vias |= {(round(v["diameter"], 4), round(v["drill"], 4)) for v in have_via if v.get("diameter", 0) > 0}
    # KiCad keeps a leading 0 entry meaning "use the net class value"
    return [0.0] + tw, [{"diameter": 0.0, "drill": 0.0}] + [{"diameter": d, "drill": h} for d, h in sorted(vias)]


def apply_to_pro(pro_path, prof, dry=False, exact=False):
    p = json.load(open(pro_path))
    ds = p["board"]["design_settings"]
    changes = []
    # every floor is a minimum, so larger is stricter. By default a board keeps a
    # floor stricter than the house one (someone set it on purpose); --exact forces
    # the house value either way.
    for k, v in strip(prof["floors"]).items():
        old = ds["rules"].get(k)
        if old is not None and not exact and old > v + EPS:
            changes.append(f"rules.{k}: kept {old} (stricter than house {v})")
            continue
        if old is None or abs(old - v) > EPS:
            changes.append(f"rules.{k}: {old} -> {v}")
            ds["rules"][k] = v
    tw, via = lists_for(prof, ds.get("track_widths", []), ds.get("via_dimensions", []))
    if tw != ds.get("track_widths"):
        changes.append(f"track_widths: {ds.get('track_widths')} -> {tw}")
        ds["track_widths"] = tw
    r = ds["rules"]
    for v in via[1:]:
        if v["diameter"] < r["min_via_diameter"] - EPS or v["drill"] < r["min_through_hole_diameter"] - EPS \
                or (v["diameter"] - v["drill"]) / 2 < r["min_via_annular_width"] - EPS:
            changes.append(f"WARNING via {v['diameter']}/{v['drill']} is in the predefined list but below the floor "
                           f"(via {r['min_via_diameter']}, drill {r['min_through_hole_diameter']}, annular {r['min_via_annular_width']}): "
                           "DRC will flag every one; allow it with a scoped .kicad_dru rule where it's needed, or drop it")
    for w in tw[1:]:
        if w < r["min_track_width"] - EPS:
            changes.append(f"WARNING track width {w} is below the floor {r['min_track_width']}")
    if via != ds.get("via_dimensions"):
        changes.append(f"via_dimensions: {[(v['diameter'], v['drill']) for v in ds.get('via_dimensions', [])]} -> {[(v['diameter'], v['drill']) for v in via]}")
        ds["via_dimensions"] = via
    classes = p["net_settings"]["classes"]
    by = {c["name"]: c for c in classes}
    default = by["Default"]
    for name, want in prof["netclasses"].items():
        want = strip(want)
        c = by.get(name)
        if c is None:
            c = dict(default, name=name, priority=len(classes) - 1)
            classes.insert(len(classes) - 1 if classes[-1]["name"] == "Default" else len(classes), c)
            changes.append(f"netclass {name}: added")
            by[name] = c
        for k, v in want.items():
            if abs(c.get(k, -1) - v) > EPS:
                changes.append(f"netclass {name}.{k}: {c.get(k)} -> {v}")
                c[k] = v
    # keep Default last, lowest priority, as KiCad writes it
    classes.sort(key=lambda c: (c["name"] == "Default", c.get("priority", 0)))
    for i, c in enumerate(classes):
        c["priority"] = 2147483647 if c["name"] == "Default" else i
    if not dry and any("->" in c or c.endswith("added") for c in changes):
        shutil.copy(pro_path, pro_path + ".bak")
        json.dump(p, open(pro_path, "w"), indent=2)
    return changes


def check_board(pcb_path, prof):
    import pcbnew
    b = pcbnew.LoadBoard(pcb_path)
    ds = b.GetDesignSettings(); mm = pcbnew.ToMM
    got = {
        "min_clearance": mm(ds.m_MinClearance), "min_track_width": mm(ds.m_TrackMinWidth),
        "min_via_diameter": mm(ds.m_ViasMinSize), "min_through_hole_diameter": mm(ds.m_MinThroughDrill),
        "min_via_annular_width": mm(ds.m_ViasMinAnnularWidth), "min_hole_to_hole": mm(ds.m_HoleToHoleMin),
        "min_hole_clearance": mm(ds.m_HoleClearance), "min_copper_edge_clearance": mm(ds.m_CopperEdgeClearance),
        "min_text_height": mm(ds.m_MinSilkTextHeight), "min_text_thickness": mm(ds.m_MinSilkTextThickness),
    }
    # a floor stricter (larger) than the house one is fine; looser is a mismatch
    bad = [f"{k}: board {got[k]} is looser than house {prof['floors'][k]}" for k in got if got[k] < prof["floors"][k] - EPS]
    tw = [round(mm(x), 4) for x in ds.m_TrackWidthList]
    vias = [(round(mm(v.m_Diameter), 4), round(mm(v.m_Drill), 4)) for v in ds.m_ViasDimensionsList]
    for w in prof["track_widths"]:
        if round(w, 4) not in tw: bad.append(f"track width {w} missing from predefined list {tw}")
    for v in prof["vias"]:
        if (round(v["diameter"], 4), round(v["drill"], 4)) not in vias: bad.append(f"via {v['diameter']}/{v['drill']} missing from {vias}")
    ns = ds.m_NetSettings
    for name, want in prof["netclasses"].items():
        nc = ns.GetDefaultNetclass() if name == "Default" else (ns.GetNetclasses().get(name) if hasattr(ns.GetNetclasses(), "get") else None)
        if nc is None:
            try:
                nc = ns.GetNetClassByName(name)
            except Exception:
                nc = None
        if nc is None or (name != "Default" and nc.GetName() != name):
            bad.append(f"netclass {name} not found"); continue
        for k, getter in (("track_width", "GetTrackWidth"), ("clearance", "GetClearance"), ("via_diameter", "GetViaDiameter"), ("via_drill", "GetViaDrill")):
            v = mm(getattr(nc, getter)())
            if abs(v - want[k]) > EPS: bad.append(f"netclass {name}.{k}: board {v} != {want[k]}")
    return got, tw, vias, bad


EMPTY_SCH = """(kicad_sch
\t(version 20250114)
\t(generator "eeschema")
\t(generator_version "10.0")
\t(uuid "{u}")
\t(paper "A4")
\t(lib_symbols)
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""

LIB_TABLE = """({kind}_lib_table
\t(version 7)
\t(lib (name "house") (type "KiCad") (uri "${{EE_LIB}}/house.{ext}") (options "") (descr "house {what} library"))
\t(lib (name "house_vendor") (type "KiCad") (uri "${{EE_LIB}}/house_vendor.{ext}") (options "") (descr "vendored third-party {what}s"))
)
"""


def stackup_sexpr(layers, thickness, flex):
    """A nominal stackup in KiCad's own form: 0.035 copper, the remaining thickness
    split evenly over the dielectrics, alternating core and prepreg as KiCad's
    default does. Nominal, not a fab's real stackup: for impedance, replace it with
    the fab's (KRT recommend-stackup, or JLC's impedance calculator)."""
    cu, mask = 0.035, (0.05 if flex else 0.01)
    mat, er, tan = ("Polyimide", 3.4, 0.004) if flex else ("FR4", 4.5, 0.02)
    ndiel = layers - 1
    diel = round((thickness - layers * cu - 2 * mask) / ndiel, 4)
    names = ["F.Cu"] + [f"In{i}.Cu" for i in range(1, layers - 1)] + ["B.Cu"]
    out = ['(stackup', '(layer "F.SilkS" (type "Top Silk Screen"))', '(layer "F.Paste" (type "Top Solder Paste"))',
           f'(layer "F.Mask" (type "Top Solder Mask") (thickness {mask}))']
    for i, n in enumerate(names):
        out.append(f'(layer "{n}" (type "copper") (thickness {cu}))')
        if i < ndiel:
            kind = "core" if (i % 2 == (0 if ndiel == 1 else 1)) else "prepreg"
            out.append(f'(layer "dielectric {i + 1}" (type "{kind}") (thickness {diel}) (material "{mat}") (epsilon_r {er}) (loss_tangent {tan}))')
    out += [f'(layer "B.Mask" (type "Bottom Solder Mask") (thickness {mask}))', '(layer "B.Paste" (type "Bottom Solder Paste"))',
            '(layer "B.SilkS" (type "Bottom Silk Screen"))', '(copper_finish "ENIG")', '(dielectric_constraints no)', ')']
    return "\n".join(out)


def insert_stackup(pcb, text):
    s = open(pcb).read()
    i = s.index("(setup")
    j = s.index("\n", i)
    open(pcb, "w").write(s[:j + 1] + text + "\n" + s[j + 1:])


def make_template(out, name, spec, rules):
    import pcbnew
    prof = rules["profiles"][spec["profile"]]
    d = os.path.join(out, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(os.path.join(d, "meta"))
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(spec["copper_layers"])
    b.GetDesignSettings().SetBoardThickness(pcbnew.FromMM(spec["thickness"]))
    pcb = os.path.join(d, name + ".kicad_pcb")
    pcbnew.SaveBoard(pcb, b)
    insert_stackup(pcb, stackup_sexpr(spec["copper_layers"], spec["thickness"], spec["profile"] == "flex"))
    for junk in (".kicad_prl",):
        f = os.path.join(d, name + junk)
        if os.path.exists(f): os.remove(f)
    changes = apply_to_pro(os.path.join(d, name + ".kicad_pro"), prof, exact=True)
    os.remove(os.path.join(d, name + ".kicad_pro.bak"))
    p = json.load(open(os.path.join(d, name + ".kicad_pro")))
    p.setdefault("schematic", {})["top_level_sheets"] = [{"filename": name + ".kicad_sch", "name": name, "uuid": str(uuid.uuid4())}]
    json.dump(p, open(os.path.join(d, name + ".kicad_pro"), "w"), indent=2)
    open(os.path.join(d, name + ".kicad_sch"), "w").write(EMPTY_SCH.format(u=p["schematic"]["top_level_sheets"][0]["uuid"]))
    open(os.path.join(d, "sym-lib-table"), "w").write(LIB_TABLE.format(kind="sym", ext="kicad_sym", what="symbol"))
    open(os.path.join(d, "fp-lib-table"), "w").write(LIB_TABLE.format(kind="fp", ext="pretty", what="footprint"))
    nc = prof["netclasses"]
    open(os.path.join(d, "meta", "info.html"), "w").write(
        f"<html><head><title>{spec['title']}</title></head><body><h2>{spec['title']}</h2>"
        f"<p>House rules ({spec['profile']} profile, draft): Default {nc['Default']['track_width']} mm track / "
        f"{nc['Default']['clearance']} mm clearance, via {nc['Default']['via_diameter']}/{nc['Default']['via_drill']}; "
        f"predefined widths {prof['track_widths']}; vias {[(v['diameter'], v['drill']) for v in prof['vias']]}.</p>"
        f"<p>Generated from ee-skills/skills/ee-layout-rules/rules/drc.json. "
        f"Assign rails to Power (or a class per rail width) before routing.</p></body></html>\n")
    # check in a fresh process: pcbnew caches the project it just saved, so an
    # in-process LoadBoard reads the pre-edit settings, not the file
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "check", pcb, "--profile", spec["profile"]],
                       capture_output=True, text=True)
    bad = [] if r.returncode == 0 else [l.strip() for l in r.stdout.splitlines() if l.startswith("  ")] or [r.stdout[-400:]]
    return d, changes, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template"); t.add_argument("out"); t.add_argument("--only")
    a = sub.add_parser("apply"); a.add_argument("pro"); a.add_argument("--profile", required=True, choices=["rigid", "flex"]); a.add_argument("--dry-run", action="store_true"); a.add_argument("--exact", action="store_true", help="set floors to the house values even where the board's are stricter")
    c = sub.add_parser("check"); c.add_argument("pcb"); c.add_argument("--profile", required=True, choices=["rigid", "flex"])
    args = ap.parse_args()
    rules = load_rules()
    if args.cmd == "template":
        rc = 0
        for name, spec in rules["templates"].items():
            if name.startswith("_") or (args.only and name != args.only): continue
            d, changes, bad = make_template(args.out, name, spec, rules)
            print(f"{name}: {d} ({len(changes)} settings applied){' — CHECK FAILED: ' + '; '.join(bad) if bad else ', read back OK'}")
            rc |= bool(bad)
        sys.exit(rc)
    if args.cmd == "apply":
        changes = apply_to_pro(args.pro, rules["profiles"][args.profile], dry=args.dry_run, exact=args.exact)
        n = sum(1 for c in changes if "->" in c or c.endswith("added"))
        print(("would change" if args.dry_run else "changed") + f" {n} settings in {args.pro}" + (" (backup .bak)" if changes and not args.dry_run else ""))
        for ch in changes: print("  " + ch)
        sys.exit(0)
    got, tw, vias, bad = check_board(args.pcb, rules["profiles"][args.profile])
    print(f"floors {got}\ntrack widths {tw}\nvias {vias}")
    print("OK" if not bad else "MISMATCH:\n  " + "\n  ".join(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
