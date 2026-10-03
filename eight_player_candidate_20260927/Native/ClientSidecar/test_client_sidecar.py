import hashlib
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "client_four_slot_patch_manifest_20261002.json"
REPORT = ROOT / "client_sidecar_report_20261002.json"


class ClientSidecarTests(unittest.TestCase):
    def test_manifest_covers_all_fixed_four_paths(self):
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["build"]["steam_build"], 25480438)
        self.assertEqual(data["capacity_contract"]["logical_max_players"], 8)
        self.assertFalse(data["production_executable"])
        ids = {site["id"] for site in data["patch_sites"]}
        self.assertEqual(
            ids,
            {
                "append_registry", "append_direct", "remove_and_compact",
                "reset_primary", "reset_secondary", "peer_keyed_adjacent_search",
                "kicked_path", "player_creation_gate", "index_to_roster_mapping",
            },
        )
        self.assertEqual(
            data["observed_client_layout"]["confirmed_peer_records"]["observed_capacity"], 4
        )
        self.assertTrue(data["capacity_contract"]["compact_ordinal_is_not_network_index"])

    def test_synthetic_build_report(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["build"]["test_exit_code"], 0)
        self.assertEqual(report["build"]["test_output"], "ep_client_sidecar_synthetic_passed")
        self.assertEqual(report["build"]["adapter_test_exit_code"], 0)
        self.assertEqual(report["build"]["adapter_test_output"], "ep_client_bridge_adapter_synthetic_passed")
        self.assertFalse(report["production"]["executable"])
        self.assertFalse(report["production"]["multiplayer_verified"])
        self.assertTrue(report["adapter_contract"]["native_callbacks_required"])
        self.assertTrue(report["adapter_contract"]["native_confirm_failure_preserves_compensation_record"])
        self.assertTrue(report["adapter_contract"]["bridge_owns_native_confirm_compensation"])
        self.assertTrue(report["adapter_contract"]["native_create_required_for_all_indexes"])
        self.assertTrue(report["adapter_contract"]["destroy_requires_no_native_confirmed_flags"])
        self.assertTrue(report["adapter_contract"]["owner_lifetime_delegated"])
        for artifact in report["artifacts"]:
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file(), artifact["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])


if __name__ == "__main__":
    unittest.main()
