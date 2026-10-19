"""Offline safety and byte-recovery tests; never opens a game process."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
import capture_session_dispatch as capture
import verify_c_api_dispatch_20261010 as recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.docs = [json.loads((HERE / name).read_bytes()) for name in recovery.PINS]

    def test_recover_saved_bytes(self):
        result = recovery.recover()
        self.assertEqual(len(result["dispatch"]), 5)
        self.assertTrue(result["findings"]["c_api_0x50_is_not_a_read_only_count_getter_on_captured_session"])
        self.assertFalse(result["findings"]["host_rcx_matches_captured_engine_session"])
        self.assertFalse(result["multiplayer_verified"])
        for row in result["dispatch"]:
            self.assertFalse(row["call_allowed"])

    def test_different_capture_pid_refused(self):
        self.docs[1]["pid"] += 1
        with self.assertRaisesRegex(ValueError, "capture_pid_mismatch"):
            recovery.analyze(*self.docs)

    def test_wrong_module_refused(self):
        self.docs[0]["tables"][0]["entries"][1]["module"] = "game.dll"
        with self.assertRaisesRegex(ValueError, "wrong_wrapper_module"):
            recovery.analyze(*self.docs)

    def test_corrupt_pointer_refused(self):
        self.docs[0]["tables"][1]["entries"][0]["pointer"] = "0x10000"
        with self.assertRaisesRegex(ValueError, "wrapper_pointer_mismatch"):
            recovery.analyze(*self.docs)

    def test_code_tamper_refused(self):
        self.docs[0]["tables"][1]["entries"][0]["prefix"] = "90" * 64
        with self.assertRaisesRegex(ValueError, "wrapper_prefix_hash_mismatch"):
            recovery.analyze(*self.docs)


class Memory:
    def __init__(self):
        self.regions = {}
        self.reads = {}
        self.used = 0
        self.change_at = None
    def put(self, address, data):
        self.regions[address] = data
    def word(self, address, value):
        self.put(address, struct.pack("<Q", value))
    def read(self, address, size, executable=False):
        self.used += size
        assert self.used <= capture.READ_BUDGET
        self.reads[address] = self.reads.get(address, 0) + 1
        data = self.regions[address]
        assert len(data) == size
        if address == self.change_at and self.reads[address] == 2:
            return bytes([data[0] ^ 1]) + data[1:]
        return data


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.exe, self.game, self.api = 0x100000000, 0x200000000, 0x300000000
        self.root, self.context, self.session = 0x400000000, 0x500000000, 0x600000000
        m = self.memory
        m.word(self.game + capture.ROOT_RVA, self.api)
        for offset, rva in capture.TABLE_RVAS.items():
            m.word(self.api + offset, self.exe + rva)
        for slot, label in [(8, "session_08"), (0x50, "session_50"), (0x60, "session_60")]:
            m.word(self.exe + capture.TABLE_RVAS[0x40] + slot, self.exe + capture.WRAPPERS[label][0])
        m.word(self.exe + capture.TABLE_RVAS[0x38] + 8, self.exe + capture.WRAPPERS["network_getter"][0])
        for rva, code in capture.WRAPPERS.values(): m.put(self.exe + rva, code)
        for rva, size in capture.METHODS: m.put(self.exe + rva, bytes(size))
        m.word(self.exe + capture.ENGINE_ROOT_RVA, self.root)
        m.word(self.game + capture.CONTEXT_RVA, self.context)
        m.word(self.root + 0xA8, self.session)
        m.word(self.context + 0xB390, self.session)
        m.word(self.session, self.exe + capture.VTABLE_RVA)
        for slot, target in [(0x80, 0x292C60), (0x38, 0x291110), (0x58, 0x28F9C0), (0x70, 0x292BE0)]:
            m.word(self.exe + capture.VTABLE_RVA + slot, self.exe + target)
    def observe(self):
        return capture.observe(self.memory, self.game, self.exe)

    def test_bounded_observation_is_not_callable(self):
        report = self.observe()
        self.assertEqual(report["status"], "observed_dispatch")
        self.assertLess(self.memory.used, 12000)
        self.assertFalse(report["dispatch_callable"])
        self.assertFalse(report["multiplayer_verified"])

    def test_unknown_host_object_is_not_traversed(self):
        self.memory.word(self.context + 0xB390, 0x700000000)
        report = self.observe()
        self.assertEqual(report["status"], "partial_dispatch_evidence")
        self.assertNotIn(0x700000000, self.memory.reads)

    def test_moved_code_is_refused(self):
        self.memory.word(self.api + 0x40, self.game + capture.TABLE_RVAS[0x40])
        with self.assertRaisesRegex(ValueError, "api_table_module_or_rva_mismatch"):
            self.observe()

    def test_changed_code_reread_refused(self):
        self.memory.change_at = self.exe + 0x291110
        report = self.observe()
        self.assertEqual(report["status"], "partial_dispatch_evidence")
        self.assertIn("method_291110", report["changed_fields"])

    def test_fingerprint_mismatch_refused(self):
        self.memory.put(self.exe + 0x34FDF0, b"\x90" * 15)
        with self.assertRaisesRegex(ValueError, "wrapper_code_mismatch"):
            self.observe()


if __name__ == "__main__":
    unittest.main()
