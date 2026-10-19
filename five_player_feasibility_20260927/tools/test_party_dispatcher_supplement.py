"""Synthetic-only supplement checks; no game process or installed-image IO."""
from collections import Counter
import copy
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

import capture_party_dispatcher_supplement_20261016 as supplement
import interface_probe as probe
from test_capture_live_party_slots import FakeGame, EXE, GAME


@pytest.fixture(autouse=True)
def prohibit_real_access(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline test attempted game access")
    for name in ("WindowsReader", "check_files", "read_party_image"):
        monkeypatch.setattr(supplement, name, forbidden)
    monkeypatch.setattr(probe, "WindowsReader", forbidden)


@pytest.fixture
def fake(monkeypatch):
    backend = FakeGame()
    backend.qword(EXE + supplement.SLOT_RVA, EXE + supplement.ENTRY_RVA)
    backend.memory[EXE + supplement.ENTRY_RVA, 5] = supplement.ENTRY_BYTES
    # Deliberately begins with a jump outside the window: it must not be followed.
    backend.memory[EXE + supplement.DISPATCHER_RVA, 4096] = bytes.fromhex("e9ffffff7f") + b"\xcc" * 4091
    pins = []
    for index, (rva, size, _) in enumerate(probe.PINS):
        raw = bytes([0x41 + index]) * size
        backend.memory[GAME + rva, size] = raw
        pins.append((rva, size, supplement.digest(raw)))
    monkeypatch.setattr(probe, "PINS", tuple(pins))
    monkeypatch.setattr(supplement, "PINS", tuple(pins))
    monkeypatch.setattr(supplement, "check_files", lambda modules, path:
                        copy.deepcopy({k: v for k, v in backend.images.items() if k in supplement.HASHES}))
    monkeypatch.setattr(supplement, "read_party_image", lambda path:
                        {**backend.images["PartyWin.dll"]["pe_identity"], "sha256": supplement.PARTY_SHA256,
                         "exact_export_matches": supplement.match_exports([])})
    return backend


def test_capture_reads_exact_fixed_scope_without_following_window_jump(fake):
    reader = supplement.BudgetedReader(fake)
    report = supplement.capture(reader, 123)
    expected = Counter()
    for row in supplement.build_plan()["fixed_memory_reads"]:
        expected[fake.images[row["module"]]["base"] + int(row["rva"], 16), row["bytes_per_read"]] += row["maximum_reads"]
    assert Counter((a, n) for a, n, _ in fake.calls) == expected
    assert len(fake.calls) == 16
    assert reader.used == sum(n for _, n, _ in fake.calls) == 33018
    assert reader.used == supplement.build_plan()["planned_maximum_memory_bytes"]
    assert report["hard_memory_read_budget_bytes"] == 65536
    assert report["dispatcher_window"]["code"].startswith("e9ffffff7f")
    assert report["dispatcher_window"]["unchanged_on_reread"]
    assert all(executable for address, _, executable in fake.calls
               if address in (EXE + supplement.ENTRY_RVA, EXE + supplement.DISPATCHER_RVA))
    assert not report["follows_new_jumps"]
    assert not report["native_game_calls"] and not report["memory_writes"]
    assert not report["provider_binding_proven"] and not report["runtime_verified"]
    assert not report["multiplayer_verified"]
    assert fake.metadata_calls == ["executable", "modules"]


@pytest.mark.parametrize("where", ["slot", "entry"])
def test_changed_chain_stops_before_any_new_code_read(fake, where):
    key = (EXE + supplement.SLOT_RVA, 8) if where == "slot" else (EXE + supplement.ENTRY_RVA, 5)
    fake.corrupt[key] = 1
    with pytest.raises(ValueError, match="common"):
        supplement.capture(supplement.BudgetedReader(fake), 123)
    assert not any(a == EXE + supplement.DISPATCHER_RVA for a, _, _ in fake.calls)


@pytest.mark.parametrize("where", ["slot", "entry", "dispatcher"])
def test_reread_changes_cannot_produce_success(fake, where):
    key = {"slot": (EXE + supplement.SLOT_RVA, 8),
           "entry": (EXE + supplement.ENTRY_RVA, 5),
           "dispatcher": (EXE + supplement.DISPATCHER_RVA, 4096)}[where]
    fake.corrupt[key] = 2
    with pytest.raises(ValueError):
        supplement.capture(supplement.BudgetedReader(fake), 123)
    assert sum(a == EXE for a, _, _ in fake.calls) == 1  # final identity pass not reached


def test_image_range_must_fit_the_entire_dispatcher_window(fake):
    fake.images["helldivers2.exe"]["size"] = supplement.DISPATCHER_RVA + 4095
    with pytest.raises(ValueError, match="outside verified image"):
        supplement.capture(supplement.BudgetedReader(fake), 123)
    assert fake.calls == []


def test_existing_budget_wrapper_remains_64_kib(monkeypatch):
    class Backend:
        calls = 0
        def read(self, address, size, executable=False):
            self.calls += 1
            return bytes(size)
    backend = Backend()
    reader = supplement.BudgetedReader(backend)
    monkeypatch.setattr(probe, "READ_BUDGET", 220 * 1024 * 1024)
    for _ in range(16):
        reader.read(EXE, 4096)
    with pytest.raises(ValueError, match="64 KiB"):
        reader.read(EXE, 1)
    assert backend.calls == 16 and reader.used == 65536


def test_exact_export_lookup_preserves_aliases_ordinals_and_unknowns():
    symbols = [SimpleNamespace(address=0x19880, name=b"ExampleExport", ordinal=17, forwarder=None),
               SimpleNamespace(address=0x19880, name=b"ExampleAlias", ordinal=18, forwarder=None),
               SimpleNamespace(address=0x19880, name=None, ordinal=19, forwarder=b"Example.Target"),
               SimpleNamespace(address=0x1BE7F, name=b"NeighborNotAnExactMatch", ordinal=20, forwarder=None)]
    rows = supplement.match_exports(symbols)
    assert [m["name"] for m in rows[0]["matches"]] == ["ExampleExport", "ExampleAlias", None]
    assert rows[0]["matches"][2]["forwarder"] == "Example.Target"
    assert rows[1]["status"] == "no_exact_export_match" and rows[1]["matches"] == []


def test_bad_disk_fingerprint_stops_before_pe_parsing(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unverified bytes reached the PE parser")
    monkeypatch.setattr(supplement.pefile, "PE", forbidden)
    with pytest.raises(ValueError, match="unsupported PartyWin fingerprint"):
        supplement.inspect_party_bytes(b"not the pinned image")


@pytest.mark.parametrize("has_exports", [True, False])
def test_verified_disk_bytes_parse_export_directory_and_close(monkeypatch, has_exports):
    raw = b"synthetic fixture, not an installed image"
    monkeypatch.setattr(supplement, "PARTY_SHA256", supplement.digest(raw))
    class FakePE:
        FILE_HEADER = SimpleNamespace(Machine=0x8664, TimeDateStamp=12345)
        OPTIONAL_HEADER = SimpleNamespace(Magic=0x20B, SizeOfImage=0x400000)
        closed = False
        parsed = False
        def parse_data_directories(self, directories):
            assert directories == [0]
            self.parsed = True
            if has_exports:
                self.DIRECTORY_ENTRY_EXPORT = SimpleNamespace(symbols=[SimpleNamespace(
                    address=0x19880, name=b"ExampleExport", ordinal=1, forwarder=None)])
        def close(self):
            self.closed = True
    pe = FakePE()
    def factory(data, fast_load):
        assert data == raw and fast_load is True
        return pe
    monkeypatch.setattr(supplement.pefile, "PE", factory)
    if has_exports:
        result = supplement.inspect_party_bytes(raw)
        assert result["exact_export_matches"][0]["matches"][0]["name"] == "ExampleExport"
        assert result["timestamp"] == 12345
    else:
        with pytest.raises(ValueError, match="export directory unavailable"):
            supplement.inspect_party_bytes(raw)
    assert pe.parsed and pe.closed


def test_plan_never_touches_game_and_cannot_overwrite(monkeypatch, tmp_path):
    path = tmp_path / "plan.json"
    monkeypatch.setattr(sys, "argv", ["capture", "--plan", "--output", str(path)])
    assert supplement.main() == 0
    before = path.read_bytes()
    plan = json.loads(before)
    assert plan["planned_maximum_memory_bytes"] == 33018
    assert plan["hard_memory_read_budget_bytes"] == 65536
    assert plan["requires_new_explicit_authorization"]
    assert plan["disk_export_rvas"] == ["0x19880", "0x1be80"]
    with pytest.raises(FileExistsError):
        supplement.main()
    assert path.read_bytes() == before


@pytest.mark.parametrize("failure", [None, "disk", "window"])
def test_cli_uses_one_fake_handle_and_saves_result(fake, monkeypatch, tmp_path, failure):
    opened = []
    def factory(pid):
        opened.append(pid)
        return fake
    monkeypatch.setattr(supplement, "WindowsReader", factory)
    if failure == "disk":
        def reject(*args):
            raise ValueError("synthetic unsupported file fingerprint")
        monkeypatch.setattr(supplement, "check_files", reject)
    elif failure == "window":
        fake.fail_at = EXE + supplement.DISPATCHER_RVA, 4096
    path = tmp_path / "receipt.json"
    monkeypatch.setattr(sys, "argv", ["capture", "--pid", "123", "--output", str(path)])
    assert supplement.main() == (0 if failure is None else 1)
    receipt = json.loads(path.read_bytes())
    assert receipt["status"] == ("captured" if failure is None else "stopped")
    assert opened == [123] and fake.closed == 1
    if failure == "disk":
        assert receipt["memory_bytes_requested"] == 0 and fake.calls == []
    elif failure == "window":
        assert receipt["read_ledger"][-1]["size"] == 4096
        assert receipt["read_ledger"][-1]["status"] == "failed"


def test_output_collision_prevents_process_open(monkeypatch, tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["capture", "--pid", "123", "--output", str(path)])
    with pytest.raises(FileExistsError):
        supplement.main()
    assert path.read_text(encoding="utf-8") == "keep"


def test_plan_chain_constants_match_the_saved_authorized_capture():
    path = Path(__file__).resolve().parents[2] / "output/native_dispatch_20261010/party_capture_authorized_20261016_pid30776_01.json"
    raw = path.read_bytes()
    assert supplement.digest(raw) == "b5b81a890e9a0e81808bcd74a736a75ac48f59de33cf393f135ef9c5478d13ac"
    receipt = json.loads(raw)
    common = receipt["common_call_slot"]
    assert int(common["rva"], 16) == supplement.SLOT_RVA
    assert int(common["target_owner"]["rva"], 16) == supplement.ENTRY_RVA
    assert bytes.fromhex(common["target_prefix"]["code"])[:5] == supplement.ENTRY_BYTES
    assert supplement.ENTRY_RVA + 5 + struct.unpack_from("<i", supplement.ENTRY_BYTES, 1)[0] == supplement.DISPATCHER_RVA
