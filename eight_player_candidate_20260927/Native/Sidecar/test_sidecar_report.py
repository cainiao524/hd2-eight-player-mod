import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "sidecar_report_20261002.json"


class SidecarReportTests(unittest.TestCase):
    def test_report_artifacts_and_contract(self):
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report["contract"]["capacity"], 8)
        self.assertEqual(report["contract"]["valid_network_indexes"], "0..7")
        self.assertTrue(report["contract"]["generation_safe"])
        self.assertTrue(report["contract"]["hole_preserving"])
        self.assertEqual(report["build"]["test_exit_code"], 0)
        self.assertEqual(report["build"]["test_output"], "ep_sidecar_synthetic_passed")
        self.assertFalse(report["production"]["executable"])
        self.assertFalse(report["production"]["multiplayer_verified"])
        for artifact in report["artifacts"]:
            path = ROOT / artifact["path"]
            self.assertTrue(path.is_file(), artifact["path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"], artifact["path"])


if __name__ == "__main__":
    unittest.main()
