import hashlib
import importlib
import json
from pathlib import Path
import sys


REPORT = Path(__file__).parent / "live_loadout_layout_20261003.json"
EVIDENCE = Path(__file__).parent / "index_slot_mapping_evidence_v2.json"
EXPECTED_GAME_SHA256 = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
TOOLS = Path(__file__).parent / "tools"


def test_live_loadout_layout_preflight_report():
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["schema"] == "hd2_live_loadout_layout_preflight_v1"
    assert report["build"] == 25480438
    assert report["anchor_count"] > 0
    assert report["matched_count"] == report["anchor_count"]
    assert report["unchanged_count"] == report["anchor_count"]
    assert report["mismatched_rvas"] == []
    assert report["bytes_read"] <= 64 * 1024
    assert report["preflight_passed"] is True

    # A code-image preflight remains evidence only.  It must not be promoted
    # to a runtime, install, or multiplayer result by the receipt itself.
    assert report["read_only"] is True
    assert report["calls_made"] is False
    assert report["writes_made"] is False
    assert report["hooks_installed"] is False
    assert report["heap_objects_read"] is False
    assert report["runtime_verified"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False

    module = report["pinned_module"]
    assert module["path"].lower().endswith("game.dll")
    assert module["sha256"] == EXPECTED_GAME_SHA256
    assert len(report["evidence_capture_identity_sha256"]) == 64

    rows = report["rows"]
    assert len(rows) == report["anchor_count"]
    assert len({row["rva"] for row in rows}) == len(rows)
    for row in rows:
        assert row["matches_expected"] is True
        assert row["unchanged_on_reread"] is True
        expected = bytes.fromhex(row["expected_bytes"])
        live = bytes.fromhex(row["live_bytes"])
        assert len(expected) == row["size"]
        assert len(live) == row["size"]
        assert hashlib.sha256(expected).hexdigest() == row["expected_sha256"]
        assert hashlib.sha256(live).hexdigest() == row["live_sha256"]
        assert row["live_sha256"] == row["reread_sha256"]


def test_live_loadout_layout_covers_entire_pinned_evidence_set():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    expected = {}
    for group in evidence["groups"]:
        for anchor in group["anchors"]:
            rva = hex(int(anchor["rva"], 16))
            raw = bytes.fromhex(anchor["bytes"])
            key = (rva, raw.hex())
            expected[key] = {
                "rva": rva,
                "expected_bytes": raw.hex(),
                "expected_sha256": hashlib.sha256(raw).hexdigest(),
            }

    observed = {}
    for row in report["rows"]:
        key = (row["rva"].lower(), row["expected_bytes"])
        observed[key] = {
            "rva": row["rva"].lower(),
            "expected_bytes": row["expected_bytes"],
            "expected_sha256": row["expected_sha256"],
        }

    assert observed == expected
    assert report["anchor_count"] == len(expected)


def test_capture_uses_game_image_and_bounded_mock_reader(monkeypatch, tmp_path):
    # Exercise the capture path without opening a process.  The fake reader
    # serves only canonical code pins and records the same bounded rereads as
    # the live utility.
    sys.path.insert(0, str(TOOLS))
    try:
        capture = importlib.import_module("capture_live_loadout_layout_20261003")
    finally:
        sys.path.pop(0)

    _, pins = capture.load_pins()
    by_rva = {int(pin["rva"], 16): bytes.fromhex(pin["expected_bytes"]) for pin in pins}
    executable = r"F:\Game\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe"
    game_base = 0x180000000
    modules = [{"base": game_base, "size": 0x30000000, "path": r"F:\Game\Steam\steamapps\common\Helldivers 2\bin\game.dll"}]
    selected = {"game.dll": {**modules[0], "sha256": EXPECTED_GAME_SHA256,
                              "pe_identity": {"timestamp": 0, "image_size": modules[0]["size"]}}}

    class FakeReader:
        def __init__(self, pid):
            assert pid == 1234
            self.used = 0
            self.closed = False

        def executable(self):
            return executable

        def modules(self):
            return modules

        def read(self, address, size, executable=False):
            assert executable is True
            rva = address - game_base
            raw = by_rva[rva]
            assert len(raw) == size
            self.used += size
            return raw

        def close(self):
            self.closed = True

    monkeypatch.setattr(capture.base, "WindowsReader", FakeReader)
    monkeypatch.setattr(capture.base, "check_files", lambda got, exe: selected)
    report = capture.capture(1234, tmp_path / "receipt.json")

    assert report["pinned_module"]["path"].lower().endswith("game.dll")
    assert report["anchor_count"] == len(pins)
    assert report["matched_count"] == len(pins)
    assert report["unchanged_count"] == len(pins)
    assert report["bytes_read"] == sum(len(raw) * 2 for raw in by_rva.values())
    assert report["preflight_passed"] is True
