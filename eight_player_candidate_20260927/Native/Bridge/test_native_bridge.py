from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


HERE = Path(__file__).parent


class NativeBridgeReportTests(unittest.TestCase):
    def test_report_is_fail_closed_and_harness_passed(self):
        report = json.loads((HERE / "native_bridge_report_20261002.json").read_text(encoding="utf-8"))
        self.assertEqual(report["build"]["test_exit_code"], 0)
        self.assertEqual(report["build"]["test_output"], "ep_native_bridge_synthetic_passed")
        self.assertEqual(report["build"]["integration_test_exit_code"], 0)
        self.assertEqual(report["build"]["integration_test_output"], "ep_bridge_client_integration_passed")
        self.assertFalse(report["production"]["executable"])
        self.assertFalse(report["production"]["multiplayer_verified"])
        self.assertIn("real game callback ABI", " ".join(report["production"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
