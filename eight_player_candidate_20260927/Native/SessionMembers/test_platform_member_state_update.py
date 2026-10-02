import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from platform_member_state_update_disasm import BODY_SHA256, END_RVA, ENTRY_RVA, recover


class StateUpdateEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = HERE / "platform_member_state_update_disasm_20261002.json"
        cls.doc = json.loads(cls.artifact.read_text(encoding="utf-8"))

    def test_exact_body_and_coverage(self):
        current = recover()
        self.assertEqual(self.doc["entry"]["rva"], hex(ENTRY_RVA))
        self.assertEqual(self.doc["entry"]["end_exclusive"], hex(END_RVA))
        self.assertEqual(self.doc["entry"]["body_sha256"], BODY_SHA256)
        self.assertEqual(self.doc["instructions"], current["instructions"])

    def test_abi_inventory_is_fail_closed(self):
        self.assertEqual(self.doc["control_flow"]["instruction_count"], 819)
        self.assertGreaterEqual(self.doc["control_flow"]["back_edge_count"], 1)
        self.assertGreaterEqual(len(self.doc["owner_field_sites"]), 40)
        self.assertGreaterEqual(len(self.doc["four_immediate_sites"]), 5)
        self.assertEqual(len(self.doc["callers"]), 4)
        self.assertFalse(self.doc["sidecar_patch_assessment"]["installable"])
        self.assertFalse(self.doc["sidecar_patch_assessment"]["safe_leaf_replacement"])


if __name__ == "__main__":
    unittest.main()
