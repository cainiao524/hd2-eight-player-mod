"""Tests for the offline client fixed-four inventory."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from client_fixed_four_inventory_20261003 import build_inventory  # noqa: E402


class ClientFixedFourInventoryTests(unittest.TestCase):
    def test_inventory_is_fail_closed_and_non_installable(self):
        result = build_inventory()
        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["checks_passed"], result["checks_total"])
        self.assertFalse(result["decision"]["installable"])
        self.assertFalse(result["decision"]["runtime_verified"])

    def test_all_five_client_arrays_keep_four_capacity(self):
        layout = build_inventory()["layout_contract"]
        self.assertEqual(len(layout), 5)
        self.assertEqual([item["in_object_capacity"] for item in layout], [4] * 5)
        self.assertEqual(layout[3]["record_player_index_offset"], "0x14")

    def test_append_remove_reset_and_handoff_are_covered(self):
        result = build_inventory()
        coverage = result["coverage"]
        for key in (
            "confirmed_peer_append",
            "confirmed_peer_remove_and_neighbor_arrays",
            "client_reset",
            "kicked_path",
            "host_migration_handoff",
        ):
            self.assertTrue(coverage[key], key)
        self.assertFalse(coverage["player_index_semantics"])
        self.assertFalse(coverage["cleanup_abi"])


if __name__ == "__main__":
    unittest.main()
