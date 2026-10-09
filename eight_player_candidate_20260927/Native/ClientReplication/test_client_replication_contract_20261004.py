import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from client_replication_contract_20261004 import HERE, build_receipt


class ClientReplicationContractTests(unittest.TestCase):
    def test_receipt_is_fail_closed_and_artifacts_match(self):
        receipt_path = HERE / "client_replication_contract_receipt_20261004.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["build"], 25480438)
        self.assertEqual(receipt["capacity"], 16)
        self.assertFalse(receipt["decision"]["installable"])
        self.assertFalse(receipt["decision"]["multiplayer_verified"])
        self.assertEqual(receipt["array_groups"]["all_mask"], 0x1F)
        for artifact in receipt["artifacts"]:
            path = HERE / artifact["path"]
            self.assertTrue(path.is_file(), artifact["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])

    def test_contract_receipt_rebuilds_without_self_hash(self):
        generated = build_receipt()
        self.assertEqual(generated["checks"], json.loads(
            (HERE / "client_replication_contract_receipt_20261004.json").read_text(encoding="utf-8")
        )["checks"])
        self.assertEqual(generated["build_result"]["test_exit_code"], 0)

    def test_synthetic_binary(self):
        completed = subprocess.run(
            [str(HERE / "ep_client_replication_contract_test.exe")],
            cwd=HERE,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("ep_client_replication_contract_synthetic_passed", completed.stdout)


if __name__ == "__main__":
    unittest.main()
