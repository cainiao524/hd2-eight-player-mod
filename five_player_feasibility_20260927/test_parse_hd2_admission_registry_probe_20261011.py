from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).parent))
from parse_hd2_admission_registry_probe_20261011 import build_receipt, latest_section


ROOT = Path(__file__).parents[1]
LOG = ROOT / "output/native_dispatch_20261010/hd2_admission_registry_probe_20261011_r3.log"
RECEIPT = ROOT / "output/native_dispatch_20261010/live_admission_registry_probe_20261011.json"


class AdmissionRegistryProbeReceiptTests(unittest.TestCase):
    def test_receipt_keeps_registry_and_capacity_claims_false(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["build"], 25480438)
        self.assertTrue(receipt["probe"]["read_only"])
        self.assertFalse(receipt["probe"]["calls_made"])
        self.assertFalse(receipt["probe"]["writes_made"])
        self.assertEqual(receipt["marker_observations"]["record_or_hash_pointer_count"], 0)
        self.assertTrue(receipt["interpretation"]["inline_data_record_observed"])
        self.assertFalse(receipt["interpretation"]["callback_registry_binding_proven"])
        self.assertFalse(receipt["interpretation"]["session_party_api_binding_proven"])
        self.assertFalse(receipt["interpretation"]["capacity_semantics_proven"])

    def test_latest_section_is_fail_closed(self) -> None:
        text = LOG.read_text(encoding="utf-8")
        first, _ = latest_section(text)
        self.assertIn("DONE read_only=true no_calls=true no_writes=true", first)
        incomplete = text + "2026-10-11 03:00:00 START newer\n"
        with self.assertRaisesRegex(ValueError, "latest_probe_section_incomplete"):
            latest_section(incomplete)

    def test_nonzero_pointer_reference_is_rejected(self) -> None:
        text = LOG.read_text(encoding="utf-8").replace(
            "target=0x24A836144AC count=0", "target=0x24A836144AC count=1", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.log"
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected_record_or_hash_pointer_reference"):
                build_receipt(path)


if __name__ == "__main__":
    unittest.main()
