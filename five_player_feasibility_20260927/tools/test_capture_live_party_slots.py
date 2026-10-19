"""Offline-only scope tests: synthetic process, workspace-saved code, no game IO."""
from collections import Counter
import copy
import json
from pathlib import Path
import struct
import sys

import pytest

import capture_live_party_slots_20261111 as capture
import interface_probe as probe
import party_manager_binding as binding

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "output/native_dispatch_20261010"
EXE, GAME, PARTY, MANAGER = 0x140000000, 0x180000000, 0x200000000, 0x300000000
HANDLE = 0x111D43778D00F0C2


@pytest.fixture(autouse=True)
def forbid_real_process_and_disk_checks(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline test attempted a real process or game file check")
    for name in ("WindowsReader", "check_files", "verify_party_file"):
        monkeypatch.setattr(capture, name, forbidden)
    monkeypatch.setattr(probe, "WindowsReader", forbidden)


class FakeGame:
    def __init__(self):
        self.images = {
            "helldivers2.exe": {"path": "synthetic/helldivers2.exe", "base": EXE, "size": 0x4000000},
            "game.dll": {"path": "synthetic/game.dll", "base": GAME, "size": 0x2000000},
            "PartyWin.dll": {"path": "synthetic/PartyWin.dll", "base": PARTY, "size": 0x400000},
        }
        self.memory = {}
        self.calls = []
        self.corrupt = {}  # (address, size) -> occurrence to corrupt
        self.fail_at = None
        self.closed = 0
        self.metadata_calls = []
        for name, module in self.images.items():
            header = bytearray(4096)
            header[:2] = b"MZ"
            struct.pack_into("<I", header, 0x3C, 0x80)
            header[0x80:0x84] = b"PE\0\0"
            struct.pack_into("<HHI", header, 0x84, 0x8664, 1, 12345)
            struct.pack_into("<H", header, 0x98, 0x20B)
            struct.pack_into("<I", header, 0xD0, module["size"])
            self.memory[module["base"], 4096] = bytes(header)
            module["pe_identity"] = {"timestamp": 12345, "image_size": module["size"]}
            module["sha256"] = {**capture.HASHES, "PartyWin.dll": capture.PARTY_SHA256}[name]
        old = json.loads((DATA / "live_party_slots_external_capture_20261111_pid38492.json").read_bytes())
        helper = bytes.fromhex(old["helper"]["code"])
        self.memory[EXE + capture.HELPER_RVA, 0x500] = helper
        self.memory[EXE + capture.HELPER_RVA, capture.HELPER_SIZE] = helper[:capture.HELPER_SIZE]
        for label, (_, rva, _, helper_rva, helper_hex) in capture.ENTRY_PINS.items():
            self.memory[EXE + rva, 1024] = (DATA / "recovered_party_windows_20261015" / (label + "_d1.bin")).read_bytes()[:1024]
            self.memory[EXE + helper_rva, 14] = bytes.fromhex(helper_hex)
        for index, (label, rva) in enumerate(capture.SLOT_RVAS.items()):
            target = EXE + 0x800000 + index * 512
            self.qword(EXE + rva, target)
            self.memory[target, 512] = b"\xcc" * 512
        for index, pin in enumerate(capture.ENTRY_PINS.values()):
            self.qword(EXE + pin[0], 0xDEADBEEF00000000 + index)
        self.qword(EXE + capture.COMMON_SLOT_RVA, PARTY + 0x300000)
        self.memory[PARTY + 0x300000, 512] = b"\xc3" * 512
        self.qword(EXE + capture.HOLDER_RVA, HANDLE)
        self.qword(PARTY + capture.MANAGER_GLOBAL_RVA, MANAGER)
        self.qword(MANAGER + 0x600, HANDLE)
        for rva in capture.CALLSITE_RVAS.values():
            self.memory[EXE + rva, 1024] = b"\x90" * 1024

    def qword(self, address, value):
        self.memory[address, 8] = struct.pack("<Q", value)

    def executable(self):
        self.metadata_calls.append("executable")
        return "synthetic/helldivers2.exe"

    def modules(self):
        self.metadata_calls.append("modules")
        return list(self.images.values()) + [{"path": "synthetic/unverified.dll", "base": 0x400000000, "size": 0x10000}]

    def read(self, address, size, executable=False):
        assert address != HANDLE, "opaque handle followed"
        key = (address, size)
        self.calls.append((address, size, executable))
        if key == self.fail_at:
            raise OSError("synthetic unreadable or non-executable range")
        raw = self.memory[key]  # Unlisted reads fail instead of inventing bytes.
        occurrence = sum((a, s) == key for a, s, _ in self.calls)
        if self.corrupt.get(key) == occurrence:
            raw = bytes([raw[0] ^ 1]) + raw[1:]
        return raw

    def close(self):
        self.closed += 1


@pytest.fixture
def fake(monkeypatch):
    game = FakeGame()
    # Exercise the actual header/code verifiers with synthetic game/Party code
    # pins of the original sizes. Wrapper/helper pins stay real saved evidence.
    for module, exported, base in ((probe, "PINS", GAME), (binding, "CODE_PINS", PARTY)):
        pins = []
        for index, (rva, size, _) in enumerate(getattr(module, exported)):
            raw = bytes([0x41 + index]) * size
            game.memory[base + rva, size] = raw
            pins.append((rva, size, capture.digest(raw)))
        monkeypatch.setattr(module, exported, tuple(pins))
        monkeypatch.setattr(capture, exported, tuple(pins))
    monkeypatch.setattr(capture, "check_files", lambda modules, path:
                        copy.deepcopy({k: v for k, v in game.images.items() if k in capture.HASHES}))
    monkeypatch.setattr(capture, "verify_party_file", lambda path:
                        {**game.images["PartyWin.dll"]["pe_identity"], "sha256": capture.PARTY_SHA256})
    return game


def test_full_capture_matches_declared_scope_and_maximum(fake):
    reader = capture.BudgetedReader(fake)
    result = capture.capture(reader, 123)
    expected = Counter({(fake.images[r["module"]]["base"] + int(r["rva"], 16), r["bytes_per_read"]):
                        r["maximum_reads"] for r in capture.fixed_reads()})
    expected[MANAGER + 0x600, 8] = 2
    for index in range(6):
        expected[EXE + 0x800000 + index * 512, 512] = 1
    expected[PARTY + 0x300000, 512] = 1
    assert Counter((a, s) for a, s, _ in fake.calls) == expected
    assert reader.used == capture.build_plan()["planned_maximum_memory_bytes"] == 47894
    assert reader.used == sum(s for _, s, _ in fake.calls) < 65536
    assert len(result["entry_qwords"]) == 6
    assert all(row["raw"] == row["reread_raw"] for row in result["entry_qwords"])
    assert result["common_call_slot"]["target_prefix"]["size"] == 512
    assert result["manager_binding_observation"]["manager_data_relationship_observed"]
    for flag in ("calls_made", "writes_made", "hooks_installed", "provider_binding_proven",
                 "runtime_verified", "multiplayer_verified", "atomic_snapshot"):
        assert not result[flag]
    assert fake.metadata_calls == ["executable", "modules"]
    assert all(executable for _, size, executable in fake.calls if size == 512)


def test_wrapper_and_position_helper_pins_match_historical_sources():
    r5 = json.loads((DATA / "live_party_jump_chains_20261111_pid38492_r5.json").read_bytes())
    assert capture.digest((DATA / "live_party_jump_chains_20261111_pid38492_r5.json").read_bytes()) == "dd41ee4dd10021cb2b5e91bba9702d2e5abb5b98698f6bc717017b41d8ea5254"
    manifest = json.loads((DATA / "recovered_party_windows_20261015/manifest.json").read_bytes())
    base = int(manifest["exe_base"], 16)
    for label, (_, rva, expected, helper_rva, helper_hex) in capture.ENTRY_PINS.items():
        saved = next(r for r in manifest["windows"] if r["label"] == label and r["depth"] == 1)
        raw = (DATA / "recovered_party_windows_20261015" / saved["file"]).read_bytes()
        assert capture.digest(raw) == saved["sha256"]
        assert int(saved["rva"], 16) == rva
        assert capture.digest(raw[:1024]) == expected
        helper = next(c for c in r5["chains"] if c["label"] == label)["hops"][-1]["direct_relative_calls"][0]
        assert int(helper["target"], 16) - base == helper_rva
        assert bytes.fromhex(helper["code"])[:14].hex() == helper_hex


@pytest.mark.parametrize("target,allowed", [
    (PARTY + 0x400000 - 512, True), (PARTY + 0x400000 - 511, False),
    (GAME + 0x1000, True), (EXE + 0x1000, True),
    (0x400000000, False), (MANAGER, False), (0, False), (HANDLE, False),
])
def test_common_target_full_range_and_module_boundary(fake, target, allowed):
    fake.qword(EXE + capture.COMMON_SLOT_RVA, target)
    fake.memory[target, 512] = b"\x90" * 512
    result = capture.capture(capture.BudgetedReader(fake), 123)
    assert ((target, 512, True) in fake.calls) == allowed
    assert (result["common_call_slot"]["target_prefix"]["status"] == "read") == allowed


def test_old_candidate_does_not_follow_party_image(fake):
    fake.qword(EXE + next(iter(capture.SLOT_RVAS.values())), PARTY + 0x1000)
    capture.capture(capture.BudgetedReader(fake), 123)
    assert not any(a == PARTY + 0x1000 for a, _, _ in fake.calls)


@pytest.mark.parametrize("manager", [0, HANDLE])
def test_null_or_invalid_manager_never_followed(fake, manager):
    fake.qword(PARTY + capture.MANAGER_GLOBAL_RVA, manager)
    result = capture.capture(capture.BudgetedReader(fake), 123)
    assert not result["manager_binding_observation"]["manager_data_relationship_observed"]
    assert not any(a == MANAGER + 0x600 for a, _, _ in fake.calls)
    assert result["memory_bytes_read"] == 47894 - 16


@pytest.mark.parametrize("rva", [p[0] for p in capture.ENTRY_PINS.values()] + [capture.COMMON_SLOT_RVA])
def test_changed_new_qword_stops_before_target_prefixes(fake, rva):
    fake.corrupt[EXE + rva, 8] = 2
    with pytest.raises(ValueError, match="qword changed"):
        capture.capture(capture.BudgetedReader(fake), 123)
    assert not any(size == 512 for _, size, _ in fake.calls)


def test_changed_manager_stops_before_target_prefixes(fake):
    fake.corrupt[PARTY + capture.MANAGER_GLOBAL_RVA, 8] = 2
    with pytest.raises(ValueError, match="manager data changed"):
        capture.capture(capture.BudgetedReader(fake), 123)
    assert not any(size == 512 for _, size, _ in fake.calls)


@pytest.mark.parametrize("occurrence", [1, 2])
def test_changed_wrapper_fingerprint_stops(fake, occurrence):
    rva = next(iter(capture.ENTRY_PINS.values()))[1]
    fake.corrupt[EXE + rva, 1024] = occurrence
    with pytest.raises(ValueError, match="wrapper fingerprint mismatch"):
        capture.capture(capture.BudgetedReader(fake), 123)
    if occurrence == 1:
        assert not any(size == 8 for _, size, _ in fake.calls)


def test_hard_cap_is_independent_of_shared_budget(monkeypatch):
    class Reader:
        calls = 0
        def read(self, address, size, executable=False):
            self.calls += 1
            return bytes(size)
    backend = Reader()
    reader = capture.BudgetedReader(backend)
    monkeypatch.setattr(probe, "READ_BUDGET", 220 * 1024 * 1024)
    for _ in range(16):
        reader.read(EXE, 4096)
    with pytest.raises(ValueError, match="64 KiB"):
        reader.read(EXE, 1)
    assert reader.used == 65536 and backend.calls == 16


@pytest.mark.parametrize("short", [True, False])
def test_short_or_failed_request_is_charged(short):
    class Reader:
        def read(self, address, size, executable=False):
            if short:
                return b"\0"
            raise OSError("synthetic access denied")
    reader = capture.BudgetedReader(Reader())
    with pytest.raises((ValueError, OSError)):
        reader.read(EXE, 8)
    assert reader.used == 8 and reader.reads[0]["status"] == "failed"


def test_plan_has_no_game_access_and_does_not_overwrite(monkeypatch, tmp_path):
    path = tmp_path / "plan.json"
    monkeypatch.setattr(sys, "argv", ["capture", "--plan", "--output", str(path)])
    assert capture.main() == 0
    original = path.read_bytes()
    plan = json.loads(original)
    assert plan["planned_maximum_memory_bytes"] == 47894
    assert plan["total_memory_read_budget_bytes"] == 65536
    assert plan["new_core_maximum_bytes_with_rereads"] == 160
    with pytest.raises(FileExistsError):
        capture.main()
    assert path.read_bytes() == original


@pytest.mark.parametrize("failure", ["disk", "code", "memory"])
def test_cli_failure_receipt_closes_once_without_retry(fake, monkeypatch, tmp_path, failure):
    opened = []
    def factory(pid):
        opened.append(pid)
        return fake
    monkeypatch.setattr(capture, "WindowsReader", factory)
    if failure == "disk":
        def mismatch(*args):
            raise ValueError("synthetic unsupported file fingerprint")
        monkeypatch.setattr(capture, "check_files", mismatch)
    elif failure == "code":
        fake.corrupt[EXE + next(iter(capture.ENTRY_PINS.values()))[1], 1024] = 1
    else:
        fake.fail_at = (PARTY + 0x300000, 512)
    path = tmp_path / "stopped.json"
    monkeypatch.setattr(sys, "argv", ["capture", "--pid", "123", "--output", str(path)])
    assert capture.main() == 1
    receipt = json.loads(path.read_bytes())
    assert receipt["status"] == "stopped"
    assert not receipt["runtime_verified"] and not receipt["multiplayer_verified"]
    assert opened == [123] and fake.closed == 1
    if failure == "disk":
        assert receipt["memory_bytes_read"] == 0 and not fake.calls
    elif failure == "memory":
        assert receipt["read_ledger"][-1]["status"] == "failed"


def test_existing_output_rejected_before_process_open(monkeypatch, tmp_path):
    path = tmp_path / "existing.json"
    path.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["capture", "--pid", "123", "--output", str(path)])
    with pytest.raises(FileExistsError):
        capture.main()
    assert path.read_text(encoding="utf-8") == "keep"
