"""Tests for pin_map.py (cables) and mate_check.py (direct board-to-board joints).

Plain python, no KiCad needed:
  python3 skills/paper-doll/tests/test_paper_doll.py
"""
import copy
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import mate_check as mc  # noqa: E402
import pin_map as pm     # noqa: E402

SENSOR_ARRAY = json.load(open(os.path.join(HERE, "..", "references", "sensor-array.json")))
OLD_J1 = {"1": "3V3_LED", "2": "3V3_LED", "3": "GND", "4": "1V8", "5": "GND", "6": "SCL", "7": "GND", "8": "SDA"}


def case(res, name):
    return next(r for r in res if r["case"] == name)


def test_sensor_array_reversed_j1_is_correct():
    res = pm.cases(SENSOR_ARRAY)
    assert case(res, "reference install")["severity"] == "ok"
    assert case(res, "reference install")["map"]["1"] == 8       # main k -> sensor 9-k, flat, both face up
    assert case(res, "cable turned over")["severity"] == "ok"   # dual contact: turning it over changes nothing
    assert case(res, "extra half twist")["severity"] == "critical"


def test_sensor_array_old_j1_reverse_powers():
    cfg = copy.deepcopy(SENSOR_ARRAY)
    cfg["ends"]["B"]["nets"] = OLD_J1                            # the pinout before 2026-10-22
    ref = case(pm.cases(cfg), "reference install")
    assert ref["severity"] == "critical"
    assert any("rail onto ground" in i for i in ref["issues"])
    assert case(pm.cases(cfg), "extra half twist")["severity"] == "ok"   # only a twisted cable worked


def test_single_sided_contact_mismatch_is_open():
    cfg = copy.deepcopy(SENSOR_ARRAY)
    cfg["ends"]["A"]["contacts"] = "toward_board"
    cfg["cable"]["exposed_A"] = [0, 0, -1]                       # exposed face points away from the board
    assert case(pm.cases(cfg), "reference install")["verdict"] == "no contact"


def test_pin1_left_flips():
    cfg = copy.deepcopy(SENSOR_ARRAY)
    cfg["ends"]["B"]["pin1"] = "left"
    assert case(pm.cases(cfg), "reference install")["map"]["1"] == 1


def _b2b(flip_daughter, rot=0, daughter_nets=None):
    # a 2x3 0.5 mm mezzanine: plug on the main's top, receptacle on the daughter's bottom (daughter flipped)
    pads = [(1, 0.0, 0.0), (2, 0.0, 0.8), (3, 0.5, 0.0), (4, 0.5, 0.8), (5, 1.0, 0.0), (6, 1.0, 0.8)]
    nets = ["GND", "3V3", "SDA", "SCL", "GND", "INT"]
    main = [[n, x, y, net] for (n, x, y), net in zip(pads, nets)]
    # the receptacle footprint is drawn from its own top view; turned over, its pin 1 lands on the plug's pin 1
    dn = daughter_nets or nets
    dpads = [[n, -x, y, net] for (n, x, y), net in zip(pads, dn)]
    return {"boards": {"main": {"pads": {"J5": main}, "pose": {"x": 0, "y": 0}},
                       "d": {"pads": {"J1": dpads}, "pose": {"x": 0, "y": 0, "z": 5, "rot": rot, "flip": flip_daughter}}},
            "joints": [{"a": "main:J5", "b": "d:J1", "keyed": False}],
            "ground": ["GND"], "power": ["3V3"]}


def test_b2b_mates_when_flipped():
    cfg = _b2b(True)
    r = mc.check_joint(cfg, cfg["joints"][0], 0.15)
    assert r["severity"] == "ok" and len(r["pairs"]) == 6


def test_b2b_not_flipped_misses():
    cfg = _b2b(False)
    r = mc.check_joint(cfg, cfg["joints"][0], 0.15)
    assert r["severity"] != "ok"


def test_b2b_rotated_180_is_graded():
    cfg = _b2b(True)
    r = mc.check_joint(cfg, cfg["joints"][0], 0.15, rot180=True)
    assert r["severity"] == "critical"                           # GND meets INT / 3V3 meets SDA


def test_b2b_rename_table():
    cfg = _b2b(True, daughter_nets=["GND", "3V3_D", "SDA", "SCL", "GND", "INT"])
    cfg["joints"][0]["rename"] = {"3V3_D": "3V3"}
    assert mc.check_joint(cfg, cfg["joints"][0], 0.15)["severity"] == "ok"


if __name__ == "__main__":
    bad = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception:
                bad += 1; print("FAIL", name); traceback.print_exc()
    sys.exit(1 if bad else 0)
