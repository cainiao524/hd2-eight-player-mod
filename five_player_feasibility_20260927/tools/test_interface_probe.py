"""Offline failure/consistency tests. No process handle is opened."""
import struct
import unittest

import interface_probe as probe


class Fixture:
    def __init__(self):
        self.memory = {}
        self.calls = []
        self.game = 0x100000000
        self.root, self.config = 0x200000000, 0x200001000
        self.table1, self.table2 = 0x200002000, 0x200003000
        self.target1, self.target2 = 0x300001000, 0x300002000
        self.put(self.game + probe.API_RVA, self.root)
        self.put(self.game + probe.CONFIG_RVA, self.config)
        self.put(self.config + 0x20, 0, 4)
        self.put(self.root + 0x30, self.table1)
        self.put(self.root + 0xF8, self.table2)
        self.put(self.table1 + 0x18, self.target1)
        self.put(self.table2 + 0xA0, self.target2)
        self.memory[self.target1] = b"\x90" * probe.CODE_BYTES
        self.memory[self.target2] = b"\xCC" * probe.CODE_BYTES
        self.modules = [{"path": "fixture_engine.dll", "base": 0x300000000, "size": 0x10000}]
        self.change_on_reread = None
        self.short_at = None

    def put(self, address, value, size=8):
        self.memory[address] = value.to_bytes(size, "little")

    def read(self, address, size, executable=False):
        previous = sum(1 for a, _, _ in self.calls if a == address)
        self.calls.append((address, size, executable))
        raw = self.memory[address]
        if previous and address == self.change_on_reread:
            raw = bytes([raw[0] ^ 1]) + raw[1:]
        if address == self.short_at:
            return raw[:size-1]
        if len(raw) < size:
            raise ValueError("Fixture unmapped bytes")
        return raw[:size]


class ProbeTests(unittest.TestCase):
    def test_exact_paths_no_player_memory(self):
        f = Fixture()
        report = probe.observe(f, f.game, f.modules)
        self.assertTrue(report["observed_fields_unchanged_on_reread"])
        self.assertFalse(report["atomic_snapshot"])
        self.assertFalse(report["eight_player_verified"])
        self.assertEqual(report["tables"][1]["functions"][0]["module_rva"], "0x2000")
        self.assertEqual(len(f.calls), 16)  # Seven fields twice and two code prefixes.
        self.assertEqual(sum(n for _, n, _ in f.calls), 616)
        self.assertEqual([a for a, _, x in f.calls if x], [f.target1, f.target2])

    def test_pointer_change_is_reported_not_consistent(self):
        f = Fixture()
        f.change_on_reread = f.root + 0xF8
        report = probe.observe(f, f.game, f.modules)
        self.assertFalse(report["observed_fields_unchanged_on_reread"])
        self.assertEqual(report["changed_fields"], ["table_f8"])

    def test_null_root_stops_before_dereference(self):
        f = Fixture()
        f.put(f.game + probe.API_RVA, 0)
        with self.assertRaisesRegex(ValueError, "pointer"):
            probe.observe(f, f.game, f.modules)
        self.assertEqual(len(f.calls), 1)

    def test_unowned_target_is_not_read(self):
        f = Fixture()
        f.put(f.table2 + 0xA0, 0x400000000)
        with self.assertRaisesRegex(ValueError, "enumerated image"):
            probe.observe(f, f.game, f.modules)
        self.assertNotIn(0x400000000, [a for a, _, _ in f.calls])

    def test_short_field_stops(self):
        f = Fixture()
        f.short_at = f.root + 0xF8
        with self.assertRaisesRegex(ValueError, "Short field"):
            probe.observe(f, f.game, f.modules)

    def test_short_code_stops(self):
        f = Fixture()
        f.short_at = f.target2
        with self.assertRaisesRegex(ValueError, "Short code"):
            probe.observe(f, f.game, f.modules)

    def test_prefix_never_crosses_module_end(self):
        f = Fixture()
        f.modules[0]["size"] = 0x2080
        report = probe.observe(f, f.game, f.modules)
        self.assertEqual(report["tables"][1]["functions"][0]["size"], 128)

    def test_code_pin_mismatch_stops_before_pointer_walk(self):
        header = bytearray(4096)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 0x3C, 0x80)
        header[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HHI", header, 0x84, 0x8664, 1, 123)
        struct.pack_into("<H", header, 0x98, 0x20B)
        struct.pack_into("<I", header, 0xD0, 0x4000000)
        f = Fixture()
        f.memory[f.game] = bytes(header)
        f.memory[f.game + probe.PINS[0][0]] = b"\0" * probe.PINS[0][1]
        selected = {"game.dll": {"base": f.game, "pe_identity": probe.pe_identity(header)}}
        with self.assertRaisesRegex(ValueError, "code pin mismatch"):
            probe.verify_loaded(f, selected)
        self.assertNotIn(f.game + probe.API_RVA, [a for a, _, _ in f.calls])

    def test_pe_rejects_32bit_and_bad_offset(self):
        header = bytearray(4096)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 0x3C, 0xFFFFFFFF)
        with self.assertRaisesRegex(ValueError, "offset"):
            probe.pe_identity(header)
        struct.pack_into("<I", header, 0x3C, 0x80)
        header[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<H", header, 0x84, 0x14C)
        with self.assertRaisesRegex(ValueError, "x64"):
            probe.pe_identity(header)


if __name__ == "__main__":
    unittest.main(verbosity=2)
