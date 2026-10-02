import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from verify_confirmed_peer_external_chain import verify  # noqa: E402

class ExternalChainTests(unittest.TestCase):
    def test_static_chain_is_complete_and_fail_closed(self):
        out = verify(HERE / "confirmed_peer_external_chain_20261002.json")
        self.assertEqual(out["status"], "passed_static_external_chain_verification")
        self.assertEqual(out["sites"], 5)
        self.assertFalse(out["installable"])
        self.assertFalse(out["multiplayer_verified"])

    def test_index_8_is_not_admitted_by_contract(self):
        data = json.loads((HERE / "confirmed_peer_external_chain_20261002.json").read_text(encoding="utf-8"))
        lo, hi = data["sidecar_contract"]["valid_network_index"]
        self.assertEqual((lo, hi), (0, 7))
        self.assertFalse(lo <= 8 <= hi)

if __name__ == "__main__":
    unittest.main(verbosity=2)
