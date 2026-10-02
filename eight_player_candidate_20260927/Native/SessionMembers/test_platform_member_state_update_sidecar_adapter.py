import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from platform_member_state_update_sidecar_adapter import (  # noqa: E402
    CAPACITY_SITES,
    prepare_record,
    reject_partial_plan,
    validate_patch_plan,
)


class SidecarAdapterTests(unittest.TestCase):
    def test_eight_ids_are_modelled_without_native_claim(self):
        record = prepare_record(0x1000, range(8), generation=7)
        self.assertEqual(record.count, 8)
        self.assertEqual(record.generation, 7)
        self.assertFalse(record.quiescing)

    def test_nine_ids_rejected(self):
        with self.assertRaises(ValueError):
            prepare_record(0x1000, range(9))

    def test_duplicate_and_null_owner_rejected(self):
        with self.assertRaises(ValueError):
            prepare_record(0, [1])
        with self.assertRaises(ValueError):
            prepare_record(0x1000, [1, 1])

    def test_partial_native_plan_fails_closed(self):
        errors = reject_partial_plan()
        self.assertTrue(any("redirects" in error for error in errors))
        self.assertTrue(any("resolver" in error for error in errors))
        self.assertTrue(any("cleanup" in error for error in errors))

    def test_state_literal_cannot_be_changed_to_eight(self):
        ok, errors = validate_patch_plan(
            {
                "entry_rva": "0x10937a0",
                "body_sha256": "929b6b1a3163e7b405d92d90d44c19dd4b2dc3d592115d2bb3e0383a1e719a69",
                "target_count": 8,
                "changed_immediate_sites": ["0x10939c2"],
                "redirected_sites": sorted(CAPACITY_SITES),
                "sidecar_owner_keyed": True,
                "resolver_bound": True,
                "enumerator_abi_bound": True,
                "cleanup_abi_bound": True,
                "unwind_verified": True,
                "installable": False,
            }
        )
        self.assertFalse(ok)
        self.assertTrue(any("state/status" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
