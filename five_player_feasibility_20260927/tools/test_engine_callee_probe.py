"""Tests run only against saved bytes and synthetic memory; no Windows handles."""
import json
from pathlib import Path
import struct
import unittest

import engine_callee_probe as probe


class Memory:
    def __init__(self):
        self.exe = {"base": 0x100000000, "size": 0x4000000}
        self.data = {self.exe["base"] + rva: bytes([i+1]) * probe.RANGE_SIZE
                     for i, (rva, _, _) in enumerate(probe.TARGETS)}
        self.calls = []
        self.change = None
        self.short = None

    def read(self, address, size, executable=False):
        prior = sum(1 for a, _, _ in self.calls if a == address)
        self.calls.append((address, size, executable))
        raw = self.data[address]
        if address == self.change and prior:
            raw = bytes([raw[0] ^ 1]) + raw[1:]
        if address == self.short:
            return raw[:size-1]
        return raw[:size]


class CalleeProbeTests(unittest.TestCase):
    def test_whitelist_is_grounded_in_saved_direct_calls(self):
        saved = Path(__file__).resolve().parents[1] / "interface_probe_live_20260927_1.json"
        data = saved.read_bytes()
        self.assertEqual(probe.base.digest(data), probe.FIRST_CAPTURE_SHA)
        capture = json.loads(data)
        prefixes = [(int(f["module_rva"], 16), bytes.fromhex(f["bytes"]))
                    for t in capture["tables"] for f in t["functions"]]
        for target, site, _ in probe.TARGETS:
            owner = [(start, raw) for start, raw in prefixes if start <= site < start+len(raw)]
            self.assertEqual(len(owner), 1)
            start, raw = owner[0]
            offset = site - start
            self.assertEqual(raw[offset], 0xE8)
            self.assertEqual(site+5+struct.unpack_from("<i",raw,offset+1)[0], target)

    def test_only_four_bounded_ranges_each_read_twice(self):
        mem = Memory()
        result = probe.observe_callees(mem, mem.exe)
        self.assertEqual(len(mem.calls), 8)
        self.assertEqual(sum(size for _, size, _ in mem.calls), 32768)
        self.assertTrue(all(executable for _, _, executable in mem.calls))
        self.assertTrue(result["all_ranges_unchanged_on_reread"])
        self.assertFalse(result["atomic_snapshot"])
        self.assertFalse(result["eight_player_verified"])

    def test_changed_code_is_saved_and_not_marked_stable(self):
        mem = Memory()
        mem.change = mem.exe["base"] + probe.TARGETS[2][0]
        result = probe.observe_callees(mem, mem.exe)
        self.assertFalse(result["all_ranges_unchanged_on_reread"])
        changed = result["ranges"][2]
        self.assertNotEqual(changed["bytes"], changed["reread_bytes"])
        self.assertFalse(changed["unchanged_on_reread"])

    def test_short_read_stops(self):
        mem = Memory()
        mem.short = mem.exe["base"] + probe.TARGETS[0][0]
        with self.assertRaisesRegex(ValueError, "Short callee read"):
            probe.observe_callees(mem, mem.exe)

    def test_range_outside_module_is_not_read(self):
        mem = Memory()
        mem.exe["size"] = 0x1000
        with self.assertRaisesRegex(ValueError, "exceeds EXE"):
            probe.observe_callees(mem, mem.exe)
        self.assertEqual(mem.calls, [])

    def test_changed_caller_stops_before_callee_collection(self):
        mem = Memory()
        rva, size, _ = probe.CALLER_PINS[0]
        mem.data[mem.exe["base"]+rva] = b"\0" * size
        with self.assertRaisesRegex(ValueError, "caller changed"):
            probe.verify_callers(mem, mem.exe["base"])
        self.assertEqual(len(mem.calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
