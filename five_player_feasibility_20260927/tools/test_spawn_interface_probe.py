"""Saved-evidence and synthetic-memory tests only; never open a process."""
import contextlib
import io
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import spawn_interface_probe as probe


class Memory:
    def __init__(self):
        self.selected = {
            "helldivers2.exe": {"base": 0x140000000, "size": 0x4000000,
                                "path": "helldivers2.exe", "sha256": probe.base.HASHES["helldivers2.exe"]},
            "game.dll": {"base": 0x7FF810000000, "size": 0x4000000,
                         "path": "game.dll", "sha256": probe.base.HASHES["game.dll"]},
        }
        self.api, self.obj, self.vtable = 0x200010000, 0x200020000, 0x200030000
        self.target = self.selected["helldivers2.exe"]["base"] + 0x4000
        self.fields = [self.selected["game.dll"]["base"] + probe.API_RVA,
                       self.api + probe.OBJECT_OFFSET, self.obj, self.vtable + probe.FUNCTION_OFFSET]
        self.data = {a: struct.pack("<Q", v) for a, v in zip(
            self.fields, (self.api, self.obj, self.vtable, self.target))}
        self.data[self.target] = b"\x90" * probe.CODE_BYTES
        self.calls, self.change, self.short = [], None, None
        self.used = 0

    def read(self, address, size, executable=False):
        prior = sum(a == address for a, _, _ in self.calls)
        self.calls.append((address, size, executable))
        self.used += size
        raw = self.data[address]
        if address == self.change and prior:
            raw = bytes([raw[0] ^ 1]) + raw[1:]
        if address == self.short:
            return raw[:size - 1]
        return raw[:size]


class SpawnInterfaceProbeTests(unittest.TestCase):
    def observe(self, mem):
        return probe.observe_spawn_interface(mem, mem.selected)

    def test_exact_four_fields_and_prefix_each_twice(self):
        mem = Memory()
        result = self.observe(mem)
        expected = [(a, 8, False) for a in mem.fields] + [(mem.target, 4096, True)]
        self.assertEqual(mem.calls, expected + expected)
        self.assertEqual(mem.used, 8256)
        self.assertTrue(result["observed_fields_unchanged_on_reread"])
        self.assertTrue(result["function"]["unchanged_on_reread"])
        self.assertFalse(result["atomic_snapshot"])
        self.assertFalse(result["eight_player_verified"])

    def test_each_changed_pointer_stops_without_following_it(self):
        for index in range(4):
            with self.subTest(index=index):
                mem = Memory()
                mem.change = mem.fields[index]
                with self.assertRaisesRegex(ValueError, "Pointer changed"):
                    self.observe(mem)
                self.assertEqual(len(mem.calls), 6 + index)
                self.assertEqual(sum(a == mem.target for a, _, _ in mem.calls), 1)

    def test_changed_code_stops(self):
        mem = Memory()
        mem.change = mem.target
        with self.assertRaisesRegex(ValueError, "Code prefix changed"):
            self.observe(mem)

    def test_each_short_field_or_code_read_stops(self):
        for index in range(5):
            with self.subTest(index=index):
                mem = Memory()
                mem.short = (mem.fields + [mem.target])[index]
                with self.assertRaisesRegex(ValueError, "Short"):
                    self.observe(mem)
                self.assertEqual(len(mem.calls), index + 1)

    def test_unowned_target_is_not_read(self):
        mem = Memory()
        mem.data[mem.fields[-1]] = struct.pack("<Q", 0x500000000)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.observe(mem)
        self.assertEqual(len(mem.calls), 4)

    def test_partial_prefix_at_image_end_is_rejected(self):
        mem = Memory()
        exe = mem.selected["helldivers2.exe"]
        mem.data[mem.fields[-1]] = struct.pack("<Q", exe["base"] + exe["size"] - 1)
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.observe(mem)
        self.assertEqual(len(mem.calls), 4)

    def test_pointer_addition_overflow_is_not_read(self):
        mem = Memory()
        mem.data[mem.fields[0]] = struct.pack("<Q", probe.USER_END - 1)
        with self.assertRaisesRegex(ValueError, "pointer|overflow"):
            self.observe(mem)
        self.assertEqual(len(mem.calls), 1)

    def test_target_prefix_overflow_is_not_read(self):
        mem = Memory()
        mem.data[mem.fields[-1]] = struct.pack("<Q", probe.USER_END - 1)
        with self.assertRaisesRegex(ValueError, "overflows"):
            self.observe(mem)
        self.assertEqual(len(mem.calls), 4)

    def test_unverified_image_is_rejected_before_reads(self):
        mem = Memory()
        mem.selected["helldivers2.exe"]["sha256"] = "unverified"
        with self.assertRaisesRegex(ValueError, "Unverified"):
            self.observe(mem)
        self.assertEqual(mem.calls, [])

    def test_third_image_is_not_allowed(self):
        mem = Memory()
        mem.selected["another.dll"] = dict(mem.selected["game.dll"])
        with self.assertRaisesRegex(ValueError, "Only two"):
            self.observe(mem)
        self.assertEqual(mem.calls, [])

    def test_game_image_cannot_contain_fixed_locations(self):
        mem = Memory()
        mem.selected["game.dll"]["size"] = 4096
        with self.assertRaisesRegex(ValueError, "locations exceed"):
            self.observe(mem)
        self.assertEqual(mem.calls, [])

    def test_exact_budget_and_no_extra_read(self):
        self.assertEqual(probe.EXPECTED_MEMORY_BYTES, 24966)
        self.assertEqual(probe.READ_COMPONENTS,
                         {"pe_header_pages": 16384, "previous_game_code_pins": 224,
                          "spawn_caller_pin": 102, "four_pointer_fields": 64,
                          "target_code_prefix": 8192})
        mem = Memory()
        reader = probe.BudgetReader(mem)
        reader.used = probe.EXPECTED_MEMORY_BYTES - 8
        reader.read(mem.fields[0], 8)
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            reader.read(mem.fields[0], 8)
        self.assertEqual(len(mem.calls), 1)

    def test_budget_adapter_rejects_short_read(self):
        mem = Memory()
        mem.short = mem.fields[0]
        with self.assertRaisesRegex(ValueError, "Short bounded"):
            probe.BudgetReader(mem).read(mem.fields[0], 8)

    def test_caller_pin_matches_saved_evidence_complete_instructions(self):
        evidence = json.loads((Path(__file__).resolve().parents[1] /
                               "respawn_receiver_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["source_sha256"], probe.SOURCE_SHA256)
        rows = evidence["pins"]["object_creation_boundary_and_handle_association"]
        rows = [row for row in rows if probe.CALLER_RVA <= int(row["rva"], 16)
                < probe.CALLER_RVA + probe.CALLER_SIZE]
        cursor, raw = probe.CALLER_RVA, bytearray()
        for row in rows:
            self.assertEqual(int(row["rva"], 16), cursor)
            self.assertEqual(row["root"], "0xac8800")
            part = bytes.fromhex(row["bytes"])
            self.assertEqual(probe.base.digest(part), row["sha256"])
            cursor += len(part)
            raw.extend(part)
        self.assertEqual(cursor, 0xAC9C1C)
        self.assertEqual(probe.base.digest(raw), probe.CALLER_SHA)
        self.assertEqual(rows[-1]["rva"], hex(probe.CALL_SITE_RVA))
        self.assertEqual(rows[-1]["bytes"], "41ffd1")
        self.assertEqual(probe.CALLER_RVA + 7 + struct.unpack_from("<i", raw, 3)[0], probe.API_RVA)

    def test_changed_caller_is_rejected(self):
        mem = Memory()
        mem.data[mem.selected["game.dll"]["base"] + probe.CALLER_RVA] = b"\0" * probe.CALLER_SIZE
        with self.assertRaisesRegex(ValueError, "caller fingerprint changed"):
            probe.verify_caller(mem, mem.selected["game.dll"])
        self.assertEqual(len(mem.calls), 1)
        self.assertTrue(mem.calls[0][2])

    def test_default_and_explicit_plan_never_open_process(self):
        with patch.object(probe.base, "WindowsReader", side_effect=AssertionError("process opened")) as reader:
            for args in ([], ["--plan"]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    probe.main(args)
                self.assertFalse(json.loads(output.getvalue())["opens_process"])
            reader.assert_not_called()

    def test_pid_without_capture_is_rejected_before_process_open(self):
        with patch.object(probe.base, "WindowsReader") as reader:
            with self.assertRaisesRegex(ValueError, "require --capture"):
                probe.main(["--pid", "1"])
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
