"""Regression checks for handle/object confusion and unavailable PE bytes."""
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import pytest

import party_manager_binding as binding

EXE = 0x140000000
PARTY = 0x180000000
MANAGER = 0x200000000
# Real saved handle: it is intentionally not a canonical process address.
HANDLE = 0x111D43778D00F0C2
ROOT = Path(__file__).resolve().parents[2]


class Reader:
    def __init__(self, handle=HANDLE, manager=MANAGER, stored=HANDLE, changed=None):
        self.values = {EXE + binding.HOLDER_RVA: handle,
                       PARTY + binding.MANAGER_GLOBAL_RVA: manager,
                       MANAGER + binding.STORED_HANDLE_OFFSET: stored}
        self.changed = changed
        self.calls = []

    def read(self, address, size):
        assert size == 8
        assert address in self.values, f"unexpected pointer followed: {address:#x}"
        assert address != HANDLE
        repeated = address in self.calls
        self.calls.append(address)
        value = self.values[address]
        if repeated and address == self.changed:
            value ^= 0x20
        return struct.pack("<Q", value)


def test_saved_helper_and_nonpointer_handle_are_consistent():
    capture = json.loads((ROOT / "output/native_dispatch_20261010/"
                          "live_party_slots_external_capture_20261111_pid38492.json").read_bytes())
    code = bytes.fromhex(capture["helper"]["code"])[:binding.HELPER_SIZE]
    assert hashlib.sha256(code).hexdigest() == binding.HELPER_SHA256
    assert int(capture["manager_holder_candidate"]["value"], 16) == HANDLE
    reader = Reader()
    result = binding.observe(reader, EXE, PARTY)
    assert result["manager_data_relationship_observed"]
    assert not result["handle_dereferenced"]
    assert not result["runtime_provider_ready"]
    assert not result["target_binding_proven"]
    assert not result["owner_lifetime_proven"]
    assert not result["atomic_snapshot"]
    assert len(reader.calls) == 6


@pytest.mark.parametrize("options,status", [
    ({"handle": 0}, "null_game_handle"),
    ({"manager": 0}, "null_party_manager"),
    ({"manager": HANDLE}, "invalid_party_manager_address"),
    ({"handle": HANDLE | 1}, "outside_tagged_manager_path"),
    ({"handle": HANDLE ^ 2}, "outside_tagged_manager_path"),
    ({"stored": HANDLE ^ 0x20}, "manager_handle_mismatch"),
])
def test_missing_or_different_manager_cannot_bind(options, status):
    result = binding.observe(Reader(**options), EXE, PARTY)
    assert result["status"] == status
    assert not result["manager_data_relationship_observed"]
    assert not result["runtime_provider_ready"]


@pytest.mark.parametrize("address", [EXE + binding.HOLDER_RVA,
                                   PARTY + binding.MANAGER_GLOBAL_RVA,
                                   MANAGER + binding.STORED_HANDLE_OFFSET])
def test_changed_samples_are_not_binding_evidence(address):
    result = binding.observe(Reader(changed=address), EXE, PARTY)
    assert result["status"] == "changed_during_read"
    assert not result["manager_data_relationship_observed"]


def test_short_read_is_not_an_empty_holder():
    class ShortReader:
        def read(self, address, size):
            return b"\0" * 4
    with pytest.raises(ValueError, match="short manager data read"):
        binding.observe(ShortReader(), EXE, PARTY)


def test_virtual_only_section_is_not_disassembled_as_file_data():
    section = SimpleNamespace(VirtualAddress=0x1000, Misc_VirtualSize=0x1000,
                              SizeOfRawData=0, PointerToRawData=0x100)
    pe = SimpleNamespace(sections=[section])
    with pytest.raises(ValueError, match="no file-backed bytes"):
        binding.file_backed_bytes(pe, b"unrelated bytes" * 100, 0x1020, 32)
    section.SizeOfRawData = 64
    raw = bytes(range(256)) * 3
    assert binding.file_backed_bytes(pe, raw, 0x1020, 32) == raw[0x120:0x140]
    with pytest.raises(ValueError, match="no file-backed bytes"):
        binding.file_backed_bytes(pe, raw, 0x1021, 32)


def test_unverified_helper_prevents_any_party_reads():
    class WrongCodeReader:
        def __init__(self): self.calls = []
        def read(self, address, size, executable=False):
            self.calls.append(address)
            return b"\0" * size
    reader = WrongCodeReader()
    with pytest.raises(ValueError, match="singleton helper fingerprint"):
        binding.verify_live_layout(reader, EXE, PARTY)
    assert reader.calls == [EXE + binding.HELPER_RVA]


def test_capture_plan_never_opens_a_process(monkeypatch, tmp_path):
    import capture_live_party_slots_20261111 as capture
    def forbidden(*args, **kwargs):
        raise AssertionError("offline plan tried to open a process")
    monkeypatch.setattr(capture, "WindowsReader", forbidden)
    output = tmp_path / "plan.json"
    monkeypatch.setattr(sys, "argv", ["capture", "--plan", "--output", str(output)])
    assert capture.main() == 0
    plan = json.loads(output.read_bytes())
    assert plan["manager_data_reads"]["maximum_bytes_with_rereads"] == 48
    assert not plan["manager_data_reads"]["opaque_handle_dereferenced"]
    assert not plan["native_game_calls"]
    assert not plan["memory_writes"]
    assert not plan["provider_binding_proven"]
