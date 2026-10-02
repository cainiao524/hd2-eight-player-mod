import json
import tempfile
import unittest
from pathlib import Path

import player_creation_chain_audit_20261002 as audit


class PlayerCreationChainAuditTests(unittest.TestCase):
    def test_gate_resource_chain_is_pinned(self):
        result = audit.build_audit()
        rows = result["gate"]["rows"]
        self.assertEqual(rows["gate"]["asm"], "cmp dword ptr [rdx + r8 + 0x163ac], 4")
        self.assertEqual(rows["fallback_branch"]["asm"], "jae 0x108624d")
        self.assertIn("0xb04d927afb137b9b", result["gate"]["resource_hashes"]["dummy"])
        self.assertIn("0xcdc1f82ce3337a82", result["gate"]["resource_hashes"]["player"])
        self.assertEqual(rows["player_resource_dispatch"]["asm"], "call 0xfdc140")

    def test_four_to_seven_is_fail_path_in_this_root(self):
        result = audit.build_audit()
        self.assertEqual(result["gate"]["index_4_to_7"], "fallback ring path; no player resource dispatch in this root")
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["multiplayer_verified"])

    def test_all_seven_component_guards_and_session_sites(self):
        result = audit.build_audit()
        self.assertEqual(result["component_capacity_guards"]["fixed_four_guard_components"], [33, 41, 43, 226, 238, 239, 250])
        self.assertEqual(len(result["component_capacity_guards"]["rows"]), 7)
        self.assertEqual([row["rva"] for row in result["session_member_update"]["capacity_sites"]], ["0x1093c91", "0x1093c96", "0x1093cb0", "0x1093d1e"])

    def test_output_is_replayable(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "audit.json"
            result = audit.build_audit()
            target.write_text(json.dumps(result, indent=2), encoding="utf-8")
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "hd2_player_creation_chain_audit_v1")
            self.assertEqual(loaded["capture_sha256"], audit.CAPTURE_SHA)


if __name__ == "__main__":
    unittest.main()
