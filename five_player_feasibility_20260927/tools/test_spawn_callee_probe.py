"""Offline tests: fixed saved bytes and synthetic adapters, no live processes."""
import contextlib
import copy
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from exe_capture_cfg import decode
import spawn_callee_probe as probe

CALLER_BYTES = bytes.fromhex(
    "4883ec2848895424384d8bc84c8d442438488d542430e815e4e9ff8b004883c428c3")


def pe_header(timestamp, image_size):
    data = bytearray(4096)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHI", data, 0x84, 0x8664, 1, timestamp)
    struct.pack_into("<H", data, 0x80 + 24, 0x20B)
    struct.pack_into("<I", data, 0x80 + 80, image_size)
    return bytes(data)


class Memory:
    def __init__(self):
        self.selected = {
            "helldivers2.exe": {"base": 0x140000000, "size": 0x4000000,
                "path": "helldivers2.exe", "sha256": probe.base.HASHES["helldivers2.exe"],
                "pe_identity": {"timestamp": 1, "image_size": 0x4000000}},
            "game.dll": {"base": 0x7FF810000000, "size": 0x4000000,
                "path": "game.dll", "sha256": probe.base.HASHES["game.dll"],
                "pe_identity": {"timestamp": 2, "image_size": 0x4000000}},
        }
        self.exe = self.selected["helldivers2.exe"]
        self.target = self.exe["base"] + probe.TARGET_RVA
        self.caller = self.exe["base"] + probe.CALLER_RVA
        self.data = {m["base"]: pe_header(m["pe_identity"]["timestamp"], m["size"])
                     for m in self.selected.values()}
        self.data.update({self.target: b"\x90" * 4096, self.caller: CALLER_BYTES})
        # Preserve the real pin positions and lengths, but use synthetic bytes
        # and their digests only while executing the synthetic transaction.
        self.synthetic_pins = []
        for i, (rva, size, _) in enumerate(probe.base.PINS):
            raw = bytes([i + 1]) * size
            self.data[self.selected["game.dll"]["base"] + rva] = raw
            self.synthetic_pins.append((rva, size, probe.base.digest(raw)))
        self.used, self.calls = 0, []
        self.change, self.short = None, None
        self.short_occurrence = 0
        self.path_queries, self.module_queries = 0, 0
        self.change_path, self.change_modules, self.closed = False, False, False

    def read(self, address, size, executable=False):
        prior = sum(a == address for a, _, _ in self.calls)
        self.calls.append((address, size, executable))
        self.used += size
        raw = self.data[address]
        if address == self.change and prior:
            raw = bytes([raw[0] ^ 1]) + raw[1:]
        if address == self.short and prior == self.short_occurrence:
            return raw[:size - 1]
        return raw[:size]

    def executable(self):
        self.path_queries += 1
        return "changed.exe" if self.change_path and self.path_queries > 1 else "helldivers2.exe"

    def modules(self):
        self.module_queries += 1
        result = copy.deepcopy(list(self.selected.values()))
        if self.change_modules and self.module_queries > 1:
            result[0]["base"] += 0x1000
        return result

    def close(self):
        self.closed = True


class SpawnCalleeProbeTests(unittest.TestCase):
    def transaction(self, mem):
        with patch.object(probe.base, "PINS", tuple(mem.synthetic_pins)), \
             patch.object(probe.base, "check_files", return_value=copy.deepcopy(mem.selected)):
            return probe.capture_once(mem, 1)

    def test_fixed_caller_and_target_derived_from_saved_full_capture(self):
        path = Path(__file__).resolve().parents[1] / "spawn_interface_live_20260927_1.json"
        raw = path.read_bytes()
        self.assertEqual(probe.base.digest(raw), probe.PRIOR_CAPTURE_SHA)
        saved = json.loads(raw)
        function = saved["function"]
        data = bytes.fromhex(function["bytes"])
        self.assertEqual(len(data), 4096)
        self.assertEqual(probe.base.digest(data), function["sha256"])
        self.assertEqual(function["sha256"], function["reread_sha256"])
        self.assertTrue(function["unchanged_on_reread"])
        self.assertEqual(int(function["module_rva"], 16), probe.CALLER_RVA)
        self.assertEqual(data[:probe.CALLER_SIZE], CALLER_BYTES)
        self.assertEqual(probe.base.digest(CALLER_BYTES), probe.CALLER_SHA)
        cfg = decode({"rva": function["module_rva"], "bytes": function["bytes"]})
        self.assertEqual(cfg["instruction_count"], 9)
        self.assertEqual(cfg["decoded_bytes"], 34)
        self.assertEqual(cfg["unresolved"], [])
        self.assertEqual(cfg["edges"], [
            {"from": "0x30ff66", "kind": "call", "target": "0x1ae380"},
            {"from": "0x30ff71", "kind": "return"}])
        site = probe.CALL_SITE_RVA - probe.CALLER_RVA
        self.assertEqual(CALLER_BYTES[site], 0xE8)
        self.assertEqual(probe.CALL_SITE_RVA + 5 + struct.unpack_from("<i", CALLER_BYTES, site + 1)[0],
                         probe.TARGET_RVA)

    def test_only_fixed_callee_prefix_twice(self):
        mem = Memory()
        result = probe.observe_callee(mem, mem.selected)
        self.assertEqual(mem.calls, [(mem.target, 4096, True)] * 2)
        self.assertEqual(mem.used, 8192)
        self.assertTrue(result["function"]["unchanged_on_reread"])
        self.assertFalse(result["atomic_snapshot"])
        self.assertFalse(result["eight_player_verified"])

    def test_full_synthetic_transaction_exact_sequence_and_budget(self):
        mem = Memory()
        result = self.transaction(mem)
        checks = [(m["base"], 4096, False) for m in mem.selected.values()]
        checks += [(mem.selected["game.dll"]["base"] + r, n, False)
                   for r, n, _ in mem.synthetic_pins]
        self.assertEqual(mem.calls, checks + [(mem.caller, 34, True)] +
                         [(mem.target, 4096, True)] * 2 + [(mem.caller, 34, True)] + checks)
        self.assertEqual(result["memory_bytes_read"], 24868)
        self.assertEqual(probe.READ_COMPONENTS,
            {"pe_header_pages": 16384, "previous_game_code_pins": 224,
             "wrapper_caller_pin": 68, "target_code_prefix": 8192})

    def test_short_first_or_second_callee_read_stops(self):
        for occurrence in (0, 1):
            with self.subTest(occurrence=occurrence):
                mem = Memory()
                mem.short, mem.short_occurrence = mem.target, occurrence
                with self.assertRaisesRegex(ValueError, "Short callee"):
                    probe.observe_callee(mem, mem.selected)
                self.assertEqual(len(mem.calls), occurrence + 1)

    def test_code_change_stops(self):
        mem = Memory()
        mem.change = mem.target
        with self.assertRaisesRegex(ValueError, "Callee code changed"):
            self.transaction(mem)

    def test_caller_mismatch_before_and_after_prefix_stops(self):
        for post in (False, True):
            with self.subTest(post=post):
                mem = Memory()
                if post:
                    mem.change = mem.caller
                else:
                    mem.data[mem.caller] = b"\0" * 34
                with self.assertRaisesRegex(ValueError, "wrapper caller changed"):
                    self.transaction(mem)
                self.assertEqual(sum(a == mem.target for a, _, _ in mem.calls), 2 if post else 0)

    def test_loaded_pe_identity_change_stops(self):
        mem = Memory()
        mem.data[mem.exe["base"]] = pe_header(999, mem.exe["size"])
        with self.assertRaisesRegex(ValueError, "Loaded PE identity mismatch"):
            self.transaction(mem)
        self.assertEqual(len(mem.calls), 1)

    def test_post_path_and_module_identity_change_stop(self):
        for flag in ("change_path", "change_modules"):
            with self.subTest(flag=flag):
                mem = Memory()
                setattr(mem, flag, True)
                with self.assertRaisesRegex(ValueError, "Process image/module list changed"):
                    self.transaction(mem)

    def test_post_disk_identity_change_stops(self):
        mem = Memory()
        changed = copy.deepcopy(mem.selected)
        changed["game.dll"]["sha256"] = "changed"
        with patch.object(probe.base, "PINS", tuple(mem.synthetic_pins)), \
             patch.object(probe.base, "check_files", side_effect=[copy.deepcopy(mem.selected), changed]):
            with self.assertRaisesRegex(ValueError, "Disk identity changed"):
                probe.capture_once(mem, 1)

    def test_image_hash_name_and_size_fail_before_reads(self):
        for field, value in (("sha256", "changed"), ("path", "another.exe"), ("size", 4096)):
            with self.subTest(field=field):
                mem = Memory()
                mem.exe[field] = value
                with self.assertRaises(ValueError):
                    probe.observe_callee(mem, mem.selected)
                self.assertEqual(mem.calls, [])

    def test_exe_window_boundary_and_address_overflow_stop(self):
        mem = Memory()
        mem.exe["size"] = probe.TARGET_RVA + 4095
        mem.exe["pe_identity"]["image_size"] = mem.exe["size"]
        with self.assertRaisesRegex(ValueError, "Fixed code exceeds"):
            probe.observe_callee(mem, mem.selected)
        self.assertEqual(mem.calls, [])
        mem = Memory()
        mem.exe["base"] = probe.USER_END - 4096
        with self.assertRaisesRegex(ValueError, "Image range overflows"):
            probe.observe_callee(mem, mem.selected)
        self.assertEqual(mem.calls, [])

    def test_ambiguous_image_ownership_stops(self):
        mem = Memory()
        mem.selected["game.dll"]["base"] = mem.exe["base"]
        with self.assertRaisesRegex(ValueError, "does not belong to one"):
            probe.observe_callee(mem, mem.selected)
        self.assertEqual(mem.calls, [])

    def test_budget_rejects_extra_read_and_short_result(self):
        mem = Memory()
        reader = probe.BudgetReader(mem)
        reader.used = probe.EXPECTED_MEMORY_BYTES - 34
        reader.read(mem.caller, 34, executable=True)
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            reader.read(mem.caller, 34, executable=True)
        self.assertEqual(len(mem.calls), 1)
        mem = Memory()
        mem.short = mem.caller
        with self.assertRaisesRegex(ValueError, "Short bounded"):
            probe.BudgetReader(mem).read(mem.caller, 34, executable=True)

    def test_default_and_explicit_plan_do_not_open_process(self):
        with patch.object(probe.base, "WindowsReader", side_effect=AssertionError("opened")) as opener:
            for args in ([], ["--plan"]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    probe.main(args)
                self.assertFalse(json.loads(output.getvalue())["opens_process"])
            opener.assert_not_called()

    def test_missing_capture_arguments_invalid_pid_and_existing_output_stop_before_open(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(probe.base, "WindowsReader") as opener:
            path = Path(folder) / "existing.json"
            path.write_text("keep", encoding="utf-8")
            for args in (["--pid", "1"], ["--capture"],
                         ["--capture", "--pid", "0", "--output", str(path) + ".new"],
                         ["--capture", "--pid", "1", "--output", str(path)]):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    probe.main(args)
            self.assertEqual(path.read_text(), "keep")
            opener.assert_not_called()

    def test_failure_closes_synthetic_handle_without_saving(self):
        mem = Memory()
        mem.change = mem.target
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(probe.base, "WindowsReader", return_value=mem), \
             patch.object(probe.base, "PINS", tuple(mem.synthetic_pins)), \
             patch.object(probe.base, "check_files", return_value=copy.deepcopy(mem.selected)):
            output = Path(folder) / "never-created.json"
            with self.assertRaisesRegex(ValueError, "Callee code changed"):
                probe.main(["--capture", "--pid", "1", "--output", str(output)])
            self.assertFalse(output.exists())
            self.assertTrue(mem.closed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
