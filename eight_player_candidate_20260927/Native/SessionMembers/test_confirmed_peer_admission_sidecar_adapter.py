import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from confirmed_peer_admission_sidecar_adapter import (  # noqa: E402
    reject_sender_only_patch,
    validate_admission_plan,
)


class ConfirmedPeerAdmissionAdapterTests(unittest.TestCase):
    def test_sender_only_plan_fails_closed(self):
        errors = reject_sender_only_patch()
        self.assertTrue(any("external" in e for e in errors))
        self.assertTrue(any("owner_keyed_sidecar" in e for e in errors))
        self.assertTrue(any("receiver_8" in e for e in errors))

    def test_missing_sender_bound_fails_closed(self):
        ok, errors = validate_admission_plan({"entry_rva": "0x108c760", "body_sha256": "bad", "target_count": 8})
        self.assertFalse(ok)
        self.assertGreaterEqual(len(errors), 3)

    def test_installable_claim_is_always_rejected(self):
        ok, errors = validate_admission_plan({"entry_rva": "0x108c760", "body_sha256": "bad", "target_count": 8, "installable": True})
        self.assertFalse(ok)
        self.assertTrue(any("installability" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
