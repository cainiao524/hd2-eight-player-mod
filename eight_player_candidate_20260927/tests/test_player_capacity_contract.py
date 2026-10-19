"""Offline tests for the configurable capacity contract.

The module is executed in LuaJIT with synthetic state only.  No game process,
loader callback, native resolver or network service is used.
"""

from __future__ import annotations

import sys
import unittest
import json
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

    def test_metadata_requires_all_component_capacities(self):
        state = self.state()
        local, result = self.module.metadata(state, "0.15.0", self.lua({}))
        self.assertTrue(result["accepted"])
        missing = self.lua({key: value for key, value in local.items()})
        missing["entity_capacity"] = None
        rejected = self.module.validate_metadata(local, missing)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["reason"], "metadata_missing")

        inconsistent = self.lua({key: value for key, value in local.items()})
        inconsistent["entity_capacity"] = 4
        rejected = self.module.validate_metadata(local, inconsistent)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["reason"], "metadata_mismatch")

    def test_metadata_rejects_effective_capacity_not_derived_from_components(self):
        state = self.state()
        local, result = self.module.metadata(state, "0.15.0", self.lua({}))
        self.assertTrue(result["accepted"])
        forged = self.lua({key: value for key, value in local.items()})
        local["effective_max_players"] = 7
        forged["effective_max_players"] = 7
        rejected = self.module.validate_metadata(local, forged)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["reason"], "effective_capacity_invalid")

    def test_metadata_rejects_fingerprint_drift(self):
        state = self.state()
        local, result = self.module.metadata(
            state, "0.15.0", self.lua({"game.dll": "pinned"}))
        self.assertTrue(result["accepted"])
        remote = self.lua({key: value for key, value in local.items()})
        remote["fingerprints"] = self.lua({"game.dll": "different"})
        rejected = self.module.validate_metadata(local, remote)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["reason"], "metadata_mismatch")
        self.assertEqual(rejected["field"], "fingerprints")

    def test_profile_matches_pinned_build_evidence(self):
        profile = json.loads((ROOT / "Integration/profile_template.json").read_text())
        spec = self.module.spec()
        for field, role in (("exe_sha256", "exe"), ("game_dll_sha256", "game_dll")):
            self.assertEqual(spec[field], profile["required_fingerprints"][role]["sha256"])

    def test_apply_rechecks_players_who_joined_after_staging(self):
        state = self.state(joined_players=2)
        self.assertTrue(self.module.stage(state, self.lua({"preset": 4}))["accepted"])
        state["joined_players"] = 6
        result = self.module.apply(state)
        self.assertFalse(result["accepted"])
        self.assertEqual(state["configured_max_players"], 8)
        self.assertEqual(state["joined_players"], 6)
        self.assertEqual(state["generation"], 0)

    def test_apply_preserves_current_lifecycle_and_component_capacities(self):
        state = self.state(configured_max_players=4, joined_players=1)
        self.assertTrue(self.module.stage(state, self.lua({"preset": 8}))["accepted"])
        state["joined_players"] = 3
        state["peer_capacity"] = 5
        state["quiescent"] = False
        result = self.module.apply(state)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["effective_max_players"], 5)
        self.assertEqual(state["peer_capacity"], 5)
        self.assertEqual(state["joined_players"], 3)
        self.assertFalse(state["quiescent"])

    def test_lobby_request_cannot_reduce_capacity_after_mission_starts(self):
        state = self.state()
        self.assertTrue(self.module.stage(state, self.lua({"preset": 4}))["accepted"])
        state["mission_active"] = True
        result = self.module.apply(state)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["reason"], "mission_capacity_cannot_decrease")
        self.assertTrue(state["mission_active"])

    def test_apply_rechecks_generation_and_quiescence(self):
        state = self.state(configured_max_players=4)
        self.module.stage(state, self.lua({"preset": 8}))
        state["generation"] = 1
        self.assertFalse(self.module.apply(state)["accepted"])
        self.assertEqual(state["configured_max_players"], 4)
        state = self.state(configured_max_players=4, mission_active=True, apply_mode="next_mission")
        self.module.stage(state, self.lua({"preset": 8}))
        state["quiescent"] = False
        self.assertFalse(self.module.apply(state, self.lua({"ready": True, "quiescent": True}))["accepted"])

    def test_generation_has_same_uint32_bound_as_native(self):
        state = self.state(configured_max_players=4)
        state["generation"] = 0xFFFFFFFF
        self.module.stage(state, self.lua({"preset": 8}))
        self.assertFalse(self.module.apply(state)["accepted"])
        self.assertEqual(state["configured_max_players"], 4)

    def test_invalid_configuration_is_not_coerced(self):
        for field, value in (("allow_join_in_progress", 1), ("require_same_mod_version", "false"),
                             ("apply_mode", "immediately")):
            with self.subTest(field=field):
                state = self.state(configured_max_players=4)
                self.assertFalse(self.module.stage(state, self.lua({"preset": 8, field: value}))["accepted"])
                self.assertIsNone(state["pending"])


if __name__ == "__main__":
    unittest.main()
