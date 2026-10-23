"""Tests for escape_budget.py, on the numbers of a WLCSP sensor-array board (2026-10-22).

Plain python, no KiCad needed:
  python3 skills/hdi-breakout/tests/test_escape_budget.py
  python3 -m pytest skills/hdi-breakout/tests/test_escape_budget.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import escape_budget as eb  # noqa: E402


def test_tracks_in_gap():
    assert eb.tracks_in_gap(0.2, 0.1, 0.1) == 0       # 0.4 pitch, 0.2 pad: needs 0.3
    assert eb.tracks_in_gap(0.3, 0.1, 0.1) == 1
    assert eb.tracks_in_gap(0.5, 0.1, 0.1) == 2
    assert eb.tracks_in_gap(0.15, 0.075, 0.075) == 0


def test_as7150_surface():
    r = eb.ball_budget(0.4, 0.2, 4, 4, 0.1, 0.1, capture=0.25)
    assert r["rings"] == 2
    assert r["surface"]["tracks_orth"] == 0            # nothing passes between two balls in a row
    assert r["surface"]["tracks_diag"] == 1            # the footprint's "diagonal dog-bone" note
    assert r["via_in_pad_layer"]["tracks_orth"] == 0   # 0.15 mm between 0.25 capture pads
    assert not r["surface"]["interstitial_via"]["fits"]  # 0.283 half diagonal < 0.325: no via between balls
    assert r["signal_layers_estimate"] == 2             # outer ring on B.Cu, inner balls via-in-pad to In6


def test_landlocked_flag():
    # 6x6 at 0.4 with a capture pad in every ball: inner rings are landlocked on the via layer
    r = eb.ball_budget(0.4, 0.25, 6, 6, 0.1, 0.1, capture=0.3)
    assert r["via_in_pad_layer"]["landlocked"]


def test_08mm_bga_dogbone():
    # 0.8 mm BGA, 0.4 pad, 0.1/0.1: one track between balls, and a 0.45 via fits between four balls
    r = eb.ball_budget(0.8, 0.4, 10, 10, 0.1, 0.1, via_pad=0.45)
    assert r["surface"]["tracks_orth"] == 1 and r["surface"]["rows_escaped"] == 2
    assert r["surface"]["interstitial_via"]["fits"]


def test_sensor_array_tile_lanes_6L_short():
    # 6L tile: 11 lanes on In1 between the taxel via columns, 8 on In4 between the bands; 20 needed
    r = eb.lanes_budget(["In1=0.35x11", "In4=0.35x8"], 0.1, 0.1, 20)
    assert r["available"] == 19 and not r["fits"] and r["short_by"] == 1


def test_sensor_array_tile_lanes_8L_fits():
    r = eb.lanes_budget(["In1=0.35x11", "In2=0.35x14", "In6=0.35x8"], 0.1, 0.1, 20)
    assert r["fits"]


def test_cli_exit_code():
    assert eb.main(["lanes", "--track", "0.1", "--space", "0.1", "--span", "In1=0.35x2", "--demand", "3"]) == 1
    assert eb.main(["lanes", "--track", "0.1", "--space", "0.1", "--span", "In1=0.35x3", "--demand", "3"]) == 0


if __name__ == "__main__":
    bad = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception:
                bad += 1; print("FAIL", name); traceback.print_exc()
    sys.exit(1 if bad else 0)
