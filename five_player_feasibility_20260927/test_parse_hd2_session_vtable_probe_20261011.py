from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).parent))
from parse_hd2_session_vtable_probe_20261011 import parse_section


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "output/native_dispatch_20261010/live_session_vtable_object_probe_20261011.json"


class SessionVtableProbeReceiptTests(unittest.TestCase):
    def test_receipt_is_runtime_read_only_and_semantics_are_withheld(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["build"], 25480438)
        self.assertEqual(receipt["schema"], "hd2_live_session_vtable_and_object_probe_v2")
        self.assertTrue(receipt["probe"]["read_only"])
        self.assertFalse(receipt["probe"]["calls_made"])
        self.assertFalse(receipt["probe"]["writes_made"])
        self.assertEqual(receipt["probe"]["vtable_slots"], 42)
        self.assertEqual(len(receipt["runtime_methods"]), 9)
        self.assertEqual({row["slot"] for row in receipt["runtime_methods"]},
                         {"0x18", "0x20", "0x30", "0x38", "0x40", "0x48", "0x50", "0x88", "0x90"})
        for row in receipt["runtime_methods"]:
            self.assertIsNone(row["semantic_name"])
            self.assertEqual(row["code_bytes"], 128)
            self.assertNotIn("candidate_role", row)
        obj = receipt["session_object_candidate"]
        self.assertTrue(obj["first_qword_matches_vtable"])
        self.assertEqual(obj["structural_fields"]["dword_0x138"], 1)
        self.assertNotEqual(obj["structural_fields"]["qword_0x140"], "0x0")
        self.assertTrue(receipt["structural_crosscheck"]["captured_object_has_nonzero_count_field"])
        self.assertTrue(receipt["structural_crosscheck"]["captured_object_has_nonzero_array_pointer"])
        self.assertFalse(receipt["structural_crosscheck"]["semantic_meaning_proven"])
        self.assertFalse(receipt["production"]["installable"])
        self.assertFalse(receipt["production"]["multiplayer_verified"])

    def test_parser_rejects_a_newer_incomplete_run_instead_of_using_stale_success(self) -> None:
        complete = "2026-10-11 00:01:00 START read_only=true\nVTABLE_DONE\nOBJECT_DONE\n"
        incomplete = "2026-10-11 00:02:00 START read_only=true\nVTABLE_DONE\n"
        with self.assertRaisesRegex(SystemExit, "latest_probe_section_incomplete"):
            parse_section(complete + incomplete)

    def test_parser_selects_the_latest_complete_run(self) -> None:
        old = "2026-10-11 00:01:00 START old\nVTABLE_DONE\nOBJECT_DONE\n"
        new = "2026-10-11 00:02:00 START new\nVTABLE_DONE\nOBJECT_DONE\n"
        section, _ = parse_section(old + new)
        self.assertIn("START new", section)
        self.assertNotIn("START old", section)


if __name__ == "__main__":
    unittest.main()
