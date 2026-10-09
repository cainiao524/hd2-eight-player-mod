"""Offline tests for the configurable capacity contract.

The module is executed in LuaJIT with synthetic state only.  No game process,
loader callback, native resolver or network service is used.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".test-deps"))
from lupa.luajit21 import LuaRuntime  # type: ignore


SOURCE = ROOT / "Source" / "player_capacity_contract.lua"


class CapacityContractTests(unittest.TestCase):
    def setUp(self):
        self.runtime = LuaRuntime(unpack_returned_tuples=True)
        self.module = self.runtime.execute(SOURCE.read_text(encoding="utf-8"))

    def lua(self, value):
        if isinstance(value, dict):
            return self.runtime.table_from({key: self.lua(item) for key, item in value.items()})
        if isinstance(value, list):
            return self.runtime.table_from([self.lua(item) for item in value])
        return value

    def state(self, **overrides):
        options = {
            "authority": "host",
            "verified_capacity": 8,
            "configured_max_players": 8,
            "peer_capacity": 8,
            "roster_capacity": 8,
            "entity_capacity": 8,
            "resource_capacity": 8,
            "network_capacity": 8,
        }
        options.update(overrides)
        state, result = self.module.new_state(self.lua(options))
        self.assertTrue(result["accepted"], dict(result.items()))
        return state

    def test_presets_and_component_minimum(self):
        presets = self.module.presets()
        self.assertEqual([presets[i]["value"] for i in range(1, 6)], [4, 5, 8, 12, 16])
        state = self.state(peer_capacity=5)
        effective, result = self.module.effective(state)
        self.assertTrue(result["accepted"])
        self.assertEqual(effective, 5)

    def test_custom_above_verified_capacity_is_rejected(self):
        state = self.state(verified_capacity=8)
        result = self.module.stage(state, self.lua({"preset": "Custom", "max_players": 9}))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "configured_capacity_invalid")
        self.assertIsNone(state["pending"])

    def test_host_stages_and_applies_atomically(self):
        state = self.state(configured_max_players=4)
        staged = self.module.stage(state, self.lua({"preset": "8 Players", "max_players": 8}))
        self.assertTrue(staged["accepted"])
        applied = self.module.apply(state)
        self.assertTrue(applied["accepted"])
        self.assertEqual(state["configured_max_players"], 8)
        self.assertEqual(state["generation"], 1)

    def test_client_cannot_stage(self):
        state = self.state(authority="client")
        result = self.module.stage(state, self.lua({"preset": "8 Players", "max_players": 8}))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "host_authority_required")

    def test_mission_decrease_is_rejected(self):
        state = self.state(configured_max_players=8, mission_active=True, joined_players=5)
        result = self.module.stage(state, self.lua({"preset": "5 Players", "max_players": 5}))
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "mission_capacity_cannot_decrease")

    def test_live_increase_requires_reservation(self):
        state = self.state(
            configured_max_players=8,
            verified_capacity=12,
            peer_capacity=12,
            roster_capacity=12,
            entity_capacity=12,
            resource_capacity=12,
            network_capacity=12,
            mission_active=True,
            apply_mode="next_mission",
        )
        self.assertTrue(self.module.stage(state, self.lua({"preset": "12 Players", "max_players": 12}))["accepted"])
        rejected = self.module.apply(state, self.lua({"ready": False, "quiescent": True}))
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["reason"], "reservation_not_ready")
        applied = self.module.apply(state, self.lua({"ready": True, "quiescent": True}))
        self.assertTrue(applied["accepted"])
        self.assertEqual(state["configured_max_players"], 12)

    def test_metadata_mismatch_is_rejected(self):
        state = self.state()
        local, result = self.module.metadata(state, "0.15.0", self.lua({}))
        self.assertTrue(result["accepted"])
        remote = self.lua({key: value for key, value in local.items()})
        remote["effective_max_players"] = 7
        mismatch = self.module.validate_metadata(local, remote)
        self.assertFalse(mismatch["accepted"])
        self.assertEqual(mismatch["reason"], "metadata_mismatch")


if __name__ == "__main__":
    unittest.main()
