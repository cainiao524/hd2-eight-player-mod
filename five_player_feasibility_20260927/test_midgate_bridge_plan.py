"""Fail-closed checks for the fixed-build mid-function bridge design."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent


class MidgateBridgePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads((ROOT / "midgate_bridge_plan_20261002.json").read_text(encoding="utf-8"))

    def test_plan_is_design_only_and_refuses_constant_patch(self) -> None:
        self.assertEqual(self.plan["steam_build"], 25480438)
        self.assertEqual(self.plan["capacity_gate"]["four_constant"]["bytes"], "b904000000")
        status = self.plan["status"]
        self.assertFalse(status["safe_to_apply_constant_patch"])
        self.assertFalse(status["safe_to_use_standard_entry_detour"])
        self.assertTrue(status["requires_custom_register_stub"])
        self.assertTrue(status["requires_sidecar_owner_contract"])
        self.assertTrue(status["requires_live_fifth_peer_test"])

    def test_continuations_and_allocator_are_explicit(self) -> None:
        gate = self.plan["capacity_gate"]
        self.assertEqual(gate["original_branch"]["taken"], "0x108c1db")
        self.assertEqual(gate["original_branch"]["fallthrough"], "0x108c1c1")
        allocator = self.plan["allocator_gate"]
        self.assertEqual(allocator["loop_bound_instruction"]["bytes"], "83f904")
        self.assertIn("preserve holes", " ".join(allocator["required_stub_contract"]))


if __name__ == "__main__":
    unittest.main()
