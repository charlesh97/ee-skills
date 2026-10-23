"""Tests for the L-47 / L-48 / L-21 / L-33 / L-25 findings of check_copper.py and for rail_check.py.

Each test builds a small board in pcbnew, runs the check on it and on a clean variant, and
asserts the finding fires on the one and not on the other.

Run with KiCad's bundled python ($KPY), from anywhere:
  $KPY -m pytest skills/ee-layout-rules/tests/test_check_copper.py     (when pytest is importable)
  $KPY skills/ee-layout-rules/tests/test_check_copper.py               (plain runner, no pytest)
"""
import os
import subprocess
import sys
import tempfile
import traceback

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import check_copper as cc  # noqa: E402
import rail_check as rc    # noqa: E402

MM = pcbnew.FromMM


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


class Board:
    """A two-layer board built in code: pads, tracks and vias, all in mm."""

    def __init__(self, default_width=0.2, default_clearance=0.2):
        self.b = pcbnew.BOARD()
        self.nets = {}
        d = self.b.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
        d.SetTrackWidth(MM(default_width))
        d.SetClearance(MM(default_clearance))

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def pad(self, ref, number, x, y, w, h, net, layer=pcbnew.F_Cu, pth=False):
        fp = next((f for f in self.b.GetFootprints() if f.GetReference() == ref), None)
        if fp is None:
            fp = pcbnew.FOOTPRINT(self.b)
            fp.SetReference(ref)
            fp.SetPosition(V(x, y))
            self.b.Add(fp)
        p = pcbnew.PAD(fp)
        p.SetNumber(number)
        p.SetShape(pcbnew.PAD_SHAPE_RECT)
        p.SetSize(pcbnew.VECTOR2I(MM(w), MM(h)))
        ls = pcbnew.LSET()
        if pth:
            p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            p.SetDrillSize(pcbnew.VECTOR2I(MM(min(w, h) / 2), MM(min(w, h) / 2)))
            for l in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):
                ls.addLayer(l)
        else:
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            side = "F" if layer == pcbnew.F_Cu else "B"
            for l in (layer, getattr(pcbnew, side + "_Paste"), getattr(pcbnew, side + "_Mask")):
                ls.addLayer(l)
        p.SetLayerSet(ls)
        p.SetPosition(V(x, y))
        p.SetNet(self.net(net))
        fp.Add(p)
        return p

    def track(self, x1, y1, x2, y2, net, width=0.1, layer=pcbnew.F_Cu):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(V(x1, y1))
        t.SetEnd(V(x2, y2))
        t.SetWidth(MM(width))
        t.SetLayer(layer)
        t.SetNet(self.net(net))
        self.b.Add(t)
        return t

    def via(self, x, y, net, size=0.6, drill=0.3):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(V(x, y))
        v.SetWidth(MM(size))
        v.SetDrill(MM(drill))
        v.SetNet(self.net(net))
        self.b.Add(v)
        return v

    def save(self, path):
        self.b.Save(path)
        return path


def run_check(bd, directions=None):
    """check_copper.check() on an unsaved board; the .kicad_pro lookup finds nothing in an empty dir."""
    F, _ = cc.check(bd.b, os.path.join(tempfile.mkdtemp(), "none.kicad_pcb"), directions, 0.6, 3.0)
    return F


# ------------------------------------------------------------------ via-over-pad (L-47)
def test_via_over_pad_fires_on_edge_via():
    bd = Board()
    bd.pad("U1", "1", 10, 10, 1.0, 0.5, "N1")
    bd.via(10.4, 10, "N1")                      # ring from 10.1 to 10.7 overlaps the pad's 9.5..10.5
    F = cc.via_over_pad_checks(bd.b)
    assert len(F["via-over-pad"]) == 1, F
    f = F["via-over-pad"][0]
    assert f["pad"] == "U1.1" and f["net"] == "N1" and f["at"] == [10.4, 10.0], f
    assert abs(f["size_mm"] - 0.4) < 1e-6


def test_via_over_pad_fires_on_other_net_too():
    bd = Board()
    bd.pad("U1", "1", 10, 10, 1.0, 0.5, "N1")
    bd.via(10.7, 10, "N2")                      # ring 10.4..11.0 overlaps the pad
    F = cc.via_over_pad_checks(bd.b)
    assert len(F["via-over-pad"]) == 1 and "pad net N1" in F["via-over-pad"][0]["why"], F


def test_via_over_pad_quiet_when_centered_or_clear():
    bd = Board()
    bd.pad("U1", "1", 10, 10, 1.0, 0.5, "N1")
    bd.via(10, 10, "N1")                        # centered: via-in-pad's business
    bd.via(10.9, 10, "N1")                      # ring 10.6..11.2 clears the pad edge at 10.5
    F = cc.via_over_pad_checks(bd.b)
    assert F["via-over-pad"] == [], F


# ------------------------------------------------------------------ pad-junction (L-48)
def test_pad_junction_fails_on_ball_with_two_tracks():
    bd = Board()
    bd.pad("U1", "A1", 10, 10, 0.2, 0.2, "N1")
    bd.track(10, 10, 12, 10, "N1")
    bd.track(10, 10, 8, 10, "N1")
    F, checked = cc.pad_junction_checks(bd.b)
    assert checked == 1
    assert len(F["pad-junction"]) == 1, F
    f = F["pad-junction"][0]
    assert f["severity"] == "fail" and f["size_mm"] == 2 and f["pad"] == "U1.A1", f


def test_pad_junction_warns_on_large_pad_with_tee_nearby():
    bd = Board()
    bd.pad("R1", "1", 10, 10, 0.5, 0.6, "N1")
    bd.track(10, 10, 10.5, 10, "N1")            # one exit
    bd.track(10.5, 10, 12, 10, "N1")            # a T 0.5 mm from the pad center (within the 0.6 pad length)
    bd.track(10.5, 10, 10.5, 12, "N1")
    F, _ = cc.pad_junction_checks(bd.b)
    assert len(F["pad-junction"]) == 1, F
    f = F["pad-junction"][0]
    assert f["severity"] == "warn" and f["size_mm"] == 2, f


def test_pad_junction_quiet_on_leaf():
    bd = Board()
    bd.pad("U1", "A1", 10, 10, 0.2, 0.2, "N1")
    bd.track(10, 10, 10.05, 10, "N1")           # a bend inside the pad, then one exit
    bd.track(10.05, 10, 12, 10, "N1")
    bd.track(12, 10, 12, 14, "N1")              # a bend far away is not a junction
    bd.pad("U1", "A2", 10, 10.4, 0.2, 0.2, "N2")  # fed by a via in the pad, no track
    bd.via(10, 10.4, "N2", 0.25, 0.1)
    F, checked = cc.pad_junction_checks(bd.b)
    assert checked == 2 and F["pad-junction"] == [], F


# ------------------------------------------------------------------ entry-vias (L-21)
def test_entry_vias_fails_with_one_via():
    bd = Board()
    bd.pad("J1", "1", 10, 10, 0.3, 0.8, "3V3")
    bd.pad("J1", "2", 10.5, 10, 0.3, 0.8, "SIG")   # not a rail: not checked
    bd.via(10, 10.8, "3V3")
    bd.via(10, 12.5, "3V3")                     # 2.5 mm away: outside the 1 mm radius
    F, checked = cc.entry_via_checks(bd.b, 1.0, {"3V3"}, ["GND"], ["Power", "PWR"])
    assert checked == 1
    assert len(F["entry-vias"]) == 1 and F["entry-vias"][0]["size_mm"] == 1, F
    assert "J1.1" in F["entry-vias"][0]["why"] and F["entry-vias"][0]["net"] == "3V3"


def test_entry_vias_quiet_with_two_vias_and_ignores_non_connectors():
    bd = Board()
    bd.pad("J1", "1", 10, 10, 0.3, 0.8, "3V3")
    bd.via(10, 10.8, "3V3")
    bd.via(10.5, 10.6, "3V3")
    bd.pad("U1", "1", 20, 20, 0.3, 0.8, "3V3")  # not a J*: no via needed here
    F, checked = cc.entry_via_checks(bd.b, 1.0, {"3V3"}, ["GND"], ["Power", "PWR"])
    assert checked == 1 and F["entry-vias"] == [], F


def test_entry_vias_counts_through_hole_pad_as_via():
    bd = Board()
    bd.pad("J1", "1", 10, 10, 1.0, 1.0, "GND", pth=True)
    bd.via(10.6, 10, "GND")
    F, _ = cc.entry_via_checks(bd.b, 1.0, None, ["GND"], ["Power", "PWR"])
    assert F["entry-vias"] == [], F


# ------------------------------------------------------------------ via-off-center (L-33), tee kind
def test_via_off_center_tee_inside_via_pad():
    bd = Board()
    bd.via(10, 10, "N1")                        # 0.6 ring: radius 0.3
    bd.track(5, 10, 10.1, 10, "N1")             # a T 0.1 mm off the via center
    bd.track(10.1, 10, 15, 10, "N1")
    bd.track(10.1, 10, 10.1, 15, "N1")
    F = run_check(bd)
    items = F["via-off-center"]
    assert len(items) == 1 and items[0]["kind"] == "tee" and abs(items[0]["size_mm"] - 0.1) < 1e-6, items


def test_via_off_center_free_kind_kept_and_bend_not_reported():
    bd = Board()
    bd.via(10, 10, "N1")
    bd.track(5, 10, 10.1, 10, "N1")             # a free end 0.1 mm off center
    bd.via(20, 10, "N1")
    bd.track(15, 10, 20.1, 10, "N1")            # a bend (two ends) inside the ring: not a T
    bd.track(20.1, 10, 20.1, 15, "N1")
    F = run_check(bd)
    items = F["via-off-center"]
    assert len(items) == 1 and items[0]["kind"] == "free" and items[0]["at"] == [10.0, 10.0], items


# ------------------------------------------------------------------ staircase and jog (L-25)
def test_staircase_fires_on_short_alternating_steps():
    bd = Board()
    x, y = 10.0, 10.0
    for i in range(5):                          # H 0.2, 45 0.2, H 0.2, 45 0.2, H 0.2 at width 0.1 (3w = 0.3)
        if i % 2 == 0:
            bd.track(x, y, x + 0.2, y, "N1")
            x += 0.2
        else:
            bd.track(x, y, x + 0.2, y + 0.2, "N1")
            x += 0.2
            y += 0.2
    F = run_check(bd)
    assert len(F["staircase"]) == 1, F["staircase"]
    f = F["staircase"][0]
    assert f["size_mm"] == 5 and f["at"] == [10.0, 10.0] and f["layer"] == "F.Cu" and f["net"] == "N1", f


def test_staircase_quiet_on_long_runs_and_two_steps():
    bd = Board()
    bd.track(10, 10, 15, 10, "N1")              # long H, one 45, long H: a proper bend
    bd.track(15, 10, 16, 11, "N1")
    bd.track(16, 11, 21, 11, "N1")
    bd.track(30, 10, 30.2, 10, "N2")            # only two short steps
    bd.track(30.2, 10, 30.4, 10.2, "N2")
    F = run_check(bd)
    assert F["staircase"] == [], F["staircase"]


def test_staircase_skips_plane_layers():
    bd = Board()
    x, y = 10.0, 10.0
    for i in range(4):
        if i % 2 == 0:
            bd.track(x, y, x + 0.2, y, "N1", layer=pcbnew.B_Cu)
            x += 0.2
        else:
            bd.track(x, y, x + 0.2, y + 0.2, "N1", layer=pcbnew.B_Cu)
            x += 0.2
            y += 0.2
    assert len(run_check(bd)["staircase"]) == 1
    assert run_check(bd, {"B.Cu": "plane"})["staircase"] == []


def test_jog_fires_on_small_lateral_shift():
    bd = Board(default_width=0.2, default_clearance=0.2)   # pitch 0.4
    bd.track(5, 10, 10, 10, "N1")
    bd.track(10, 10, 10.2, 10.2, "N1")          # 0.28 mm bend spacing, 0.2 mm shift
    bd.track(10.2, 10.2, 15, 10.2, "N1")
    F = run_check(bd)
    assert len(F["jog"]) == 1, F["jog"]
    f = F["jog"][0]
    assert abs(f["size_mm"] - 0.2) < 1e-6 and f["at"] == [10.0, 10.0], f


def test_jog_quiet_on_shift_of_a_pitch_or_more():
    bd = Board(default_width=0.2, default_clearance=0.2)
    bd.track(5, 10, 10, 10, "N1")
    bd.track(10, 10, 10.2, 10.4, "N1")          # 0.4 mm shift: one full pitch (and an odd angle, not a jog)
    bd.track(10.2, 10.4, 15, 10.4, "N1")
    bd.track(5, 20, 10, 20, "N2")
    bd.track(10, 20, 11, 21, "N2")              # 1 mm shift over a 1.41 mm 45: a lane change
    bd.track(11, 21, 15, 21, "N2")
    F = run_check(bd)
    assert F["jog"] == [], F["jog"]


# ------------------------------------------------------------------ gnd-pin-via severity by stage
def test_gnd_pin_via_fails_only_at_stage_final():
    bd = Board()
    bd.pad("C1", "1", 10, 10, 0.5, 0.6, "GND")  # a ground pad with no via anywhere
    bd.pad("C1", "2", 11, 10, 0.5, 0.6, "N1")
    d = tempfile.mkdtemp()
    path = bd.save(os.path.join(d, "t.kicad_pcb"))
    base = [sys.executable, os.path.join(SCRIPTS, "check_copper.py"), path, "--edge-margin", "0", "--no-pours"]
    routed = subprocess.run(base + ["--stage", "routed"], capture_output=True, text=True)
    final = subprocess.run(base + ["--stage", "final"], capture_output=True, text=True)
    assert "warn  gnd-pin-via     1" in routed.stdout, routed.stdout + routed.stderr
    assert routed.returncode == 0, routed.stdout
    assert "FAIL  gnd-pin-via     1" in final.stdout, final.stdout + final.stderr
    assert final.returncode == 1


# ------------------------------------------------------------------ rail_check.py
def test_rail_drop_track_resistance_and_via():
    bd = Board()
    bd.pad("J1", "1", 0, 0, 0.5, 0.8, "1V8")
    bd.pad("U1", "1", 10, 0, 0.5, 0.8, "1V8")
    bd.track(0, 0, 10, 0, "1V8", width=0.2)     # 10 mm x 0.2 mm x 35 um: 24.57 mOhm
    bd.pad("U2", "1", 10, 5, 0.5, 0.8, "1V8", layer=pcbnew.B_Cu)
    bd.via(10, 0, "1V8")                        # in U1.1, then 5 mm on B.Cu to U2.1
    bd.track(10, 0, 10, 5, "1V8", width=0.2, layer=pcbnew.B_Cu)
    r = rc.rail_drop(bd.b, "1V8", 0.1, 1.0, None)
    assert r["source"] == "J1" and r["missing"] == [], r
    by = {p["pad"]: p for p in r["reached"]}
    assert abs(by["U1.1"]["mohm"] - 24.57) < 0.05, by
    assert abs(by["U2.1"]["mohm"] - (24.57 + 1.0 + 12.29)) < 0.1, by
    assert r["farthest"]["pad"] == "U2.1" and abs(r["farthest"]["drop_mv"] - 3.79) < 0.02, r["farthest"]


def test_rail_drop_half_oz_doubles_and_unrouted_has_no_path():
    bd = Board()
    bd.pad("J1", "1", 0, 0, 0.5, 0.8, "1V8")
    bd.pad("U1", "1", 10, 0, 0.5, 0.8, "1V8")
    r = rc.rail_drop(bd.b, "1V8", 0.1, 1.0, "J1")
    assert r["farthest"] is None and r["missing"] == ["U1.1"], r
    bd.track(0, 0, 10, 0, "1V8", width=0.2)
    r1 = rc.rail_drop(bd.b, "1V8", 0.1, 1.0, "J1")["farthest"]["mohm"]
    r2 = rc.rail_drop(bd.b, "1V8", 0.1, 0.5, "J1")["farthest"]["mohm"]
    assert abs(r2 - 2 * r1) < 0.05, (r1, r2)


def test_bus_cap_rise_time():
    bd = Board()
    bd.pad("U1", "1", 0, 0, 0.5, 0.8, "SCL")
    bd.pad("U2", "1", 20, 0, 0.5, 0.8, "SCL")
    bd.track(0, 0, 20, 0, "SCL")
    bd.via(20, 0, "SCL")
    b = rc.bus_cap(bd.b, "SCL", 1500.0, 0.1, 0.1, 5.0, 300.0)
    assert b["track_mm"] == 20.0 and b["vias"] == 1 and b["pins"] == 2, b
    assert abs(b["pf"] - 12.1) < 1e-6 and abs(b["rise_ns"] - 0.8473 * 1500 * 12.1e-3) < 0.1, b
    assert "error" in rc.bus_cap(bd.b, "NOPE", 1500.0, 0.1, 0.1, 5.0, 300.0)


def test_rail_check_cli_on_saved_board():
    bd = Board()
    bd.pad("J1", "1", 0, 0, 0.5, 0.8, "1V8")
    bd.pad("U1", "1", 10, 0, 0.5, 0.8, "1V8")
    bd.pad("U1", "2", 10, 1, 0.5, 0.8, "SCL")
    bd.track(0, 0, 10, 0, "1V8", width=0.2)
    path = bd.save(os.path.join(tempfile.mkdtemp(), "t.kicad_pcb"))
    out = subprocess.run([sys.executable, os.path.join(SCRIPTS, "rail_check.py"), path, "--rails", "1V8:0.1",
                          "--bus", "SCL", "--pullup", "1500"], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "ok    rail-drop  1V8" in out.stdout and "farthest U1.1" in out.stdout, out.stdout
    assert "ok    bus-cap    SCL" in out.stdout, out.stdout


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok    {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
