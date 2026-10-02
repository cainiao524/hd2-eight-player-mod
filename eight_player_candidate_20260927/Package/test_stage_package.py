from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("stage_package", HERE / "stage_package.py")
assert SPEC and SPEC.loader
stage_package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage_package)


class StagePackageTests(unittest.TestCase):
    def test_fixed_build_offline_audits_are_present_and_fail_closed(self):
        audits = stage_package.validate_offline_audits()
        self.assertTrue(audits["valid"], audits)
        self.assertEqual(audits["reports"]["player_creation_abi"]["build"], stage_package.BUILD)
        self.assertEqual(audits["reports"]["loadout_layout"]["build"], stage_package.BUILD)
        self.assertEqual(audits["reports"]["player_resource_reverse_cleanup"]["build"], stage_package.BUILD)
        self.assertEqual(audits["reports"]["player_resource_rollback"]["build"], stage_package.BUILD)
        self.assertFalse(audits["reports"]["player_creation_abi"]["production_flags"]["installable"])
        self.assertFalse(audits["reports"]["loadout_layout"]["production_flags"]["installable"])
        self.assertFalse(audits["reports"]["player_resource_reverse_cleanup"]["production_flags"]["installable"])
        self.assertFalse(audits["reports"]["player_resource_reverse_cleanup"]["production_flags"]["runtime_verified"])
        self.assertFalse(audits["reports"]["player_resource_reverse_cleanup"]["production_flags"]["multiplayer_verified"])
        self.assertFalse(audits["reports"]["player_resource_rollback"]["production_flags"]["production_patch_ready"])
        self.assertFalse(audits["reports"]["player_resource_rollback"]["production_flags"]["installable"])
        self.assertFalse(audits["reports"]["player_resource_rollback"]["production_flags"]["runtime_verified"])
        self.assertFalse(audits["reports"]["player_resource_rollback"]["production_flags"]["multiplayer_verified"])
        self.assertEqual(audits["reports"]["peer_lifecycle"]["build"], stage_package.BUILD)
        self.assertFalse(audits["reports"]["peer_lifecycle"]["production_flags"]["native_owner_quiescence_proven"])
        self.assertFalse(audits["reports"]["peer_lifecycle"]["production_flags"]["installable"])
        self.assertFalse(audits["reports"]["peer_lifecycle"]["production_flags"]["runtime_verified"])
        self.assertFalse(audits["reports"]["peer_lifecycle"]["production_flags"]["multiplayer_verified"])

    def test_missing_offline_audit_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            audits = stage_package.validate_offline_audits(Path(td))
            self.assertFalse(audits["valid"])
            self.assertIn("offline_audit_missing:player_creation_abi", audits["errors"])
            self.assertIn("offline_audit_missing:loadout_layout", audits["errors"])
            self.assertIn("offline_audit_missing:player_resource_reverse_cleanup", audits["errors"])
            self.assertIn("offline_audit_missing:player_resource_rollback", audits["errors"])
            self.assertIn("offline_audit_missing:peer_lifecycle", audits["errors"])

    def test_peer_lifecycle_checks_are_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "five_player_feasibility_20260927"
            root.mkdir(parents=True)
            peer = json.loads(
                stage_package.OFFLINE_AUDITS["peer_lifecycle"].read_text(encoding="utf-8")
            )
            peer["checks"]["token_identity_type_guard"] = False
            (root / "peer_lifecycle_sidecar_contract_20261003.json").write_text(
                json.dumps(peer), encoding="utf-8"
            )
            audits = stage_package.validate_offline_audits(Path(td))
            self.assertFalse(audits["valid"])
            self.assertIn("offline_audit_mismatch:peer_lifecycle", audits["errors"])

    def test_resource_rollback_contract_checks_are_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "five_player_feasibility_20260927"
            root.mkdir(parents=True)
            rollback = json.loads(
                stage_package.OFFLINE_AUDITS["player_resource_rollback"].read_text(encoding="utf-8")
            )
            rollback["checks"]["thread_quiescence_gate_proven"] = False
            (root / "resource_rollback_quiescence_contract_20261003.json").write_text(
                json.dumps(rollback), encoding="utf-8"
            )
            audits = stage_package.validate_offline_audits(Path(td))
            self.assertFalse(audits["valid"])
            self.assertIn("offline_audit_mismatch:player_resource_rollback", audits["errors"])

    def test_reverse_cleanup_audit_schema_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "five_player_feasibility_20260927"
            root.mkdir(parents=True)
            reverse = json.loads(
                stage_package.OFFLINE_AUDITS["player_resource_reverse_cleanup"].read_text(encoding="utf-8")
            )
            reverse["schema"] = "tampered"
            (root / "player_resource_reverse_cleanup_audit_20261003.json").write_text(
                json.dumps(reverse), encoding="utf-8"
            )
            audits = stage_package.validate_offline_audits(Path(td))
            self.assertFalse(audits["valid"])
            self.assertIn("offline_audit_mismatch:player_resource_reverse_cleanup", audits["errors"])

    def test_reverse_cleanup_pinned_check_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "five_player_feasibility_20260927"
            root.mkdir(parents=True)
            reverse = json.loads(
                stage_package.OFFLINE_AUDITS["player_resource_reverse_cleanup"].read_text(encoding="utf-8")
            )
            reverse["checks"]["owner8_ordinal_flag_compaction_is_pinned"] = False
            (root / "player_resource_reverse_cleanup_audit_20261003.json").write_text(
                json.dumps(reverse), encoding="utf-8"
            )
            audits = stage_package.validate_offline_audits(Path(td))
            self.assertFalse(audits["valid"])
            self.assertIn("offline_audit_mismatch:player_resource_reverse_cleanup", audits["errors"])

    def _plan(self, *, executable=False):
        return {
            "steam_build": stage_package.BUILD,
            "sidecar": {"host_peer_slots": 8, "client_confirmed_slots": 8},
            "executable": executable,
            "multiplayer_verified": False,
            "requires": sorted(stage_package.REQUIRED_PLAN_FIELDS),
        }

    def test_non_executable_plan_blocks_and_does_not_create_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = root / "plan.json"
            plan.write_text(json.dumps(self._plan()), encoding="utf-8")
            diagnostics = root / "diagnostics.json"
            output = root / "stage"
            rc = stage_package.main([
                "--game-root", str(root / "game"),
                "--native-plan", str(plan),
                "--diagnostics", str(diagnostics),
                "--stage-output", str(output),
            ])
            self.assertEqual(rc, 2)
            self.assertFalse(output.exists())
            saved = json.loads(diagnostics.read_text(encoding="utf-8"))
            self.assertFalse(saved["activation_allowed"])
            self.assertIn("native_plan_not_executable", saved["errors"])

    def test_exact_hashes_and_payload_are_required_before_stage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            for rel, digest in stage_package.FILES.items():
                path = game / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            # Replace the expected profile only inside this test; production constants stay pinned.
            expected = {rel: stage_package.sha256(game / rel) for rel in stage_package.FILES}
            plan = root / "plan.json"
            plan.write_text(json.dumps(self._plan(executable=True)), encoding="utf-8")
            payload = root / "bridge.dll"
            payload.write_bytes(b"native-payload-fixture")
            with patch.object(stage_package, "FILES", expected):
                diagnostics = stage_package.build_diagnostics(game, plan, payload)
                self.assertTrue(diagnostics["activation_allowed"], diagnostics)
                output = root / "stage"
                stage_package.stage(HERE, output, diagnostics, payload)
                self.assertTrue((output / "manifest.json").is_file())
                self.assertTrue((output / "native" / "bridge.dll").is_file())
                self.assertEqual(json.loads((output / "rollback.json").read_text())["installed_files"], [])
            # Staging never writes into the game root.
            self.assertEqual(sorted(p.relative_to(game).as_posix() for p in game.rglob("*") if p.is_file()), sorted(stage_package.FILES))

    def test_plan_build_mismatch_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.json"
            plan = self._plan(executable=True)
            plan["steam_build"] = stage_package.BUILD + 1
            path.write_text(json.dumps(plan), encoding="utf-8")
            result = stage_package.validate_plan(path)
            self.assertFalse(result["valid"])
            self.assertIn("native_plan_build_mismatch", result["errors"])

    def test_stage_refuses_output_inside_game_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "game"
            game.mkdir()
            for rel in stage_package.FILES:
                path = game / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"fixture")
            plan = root / "plan.json"
            plan.write_text(json.dumps(self._plan(executable=True)), encoding="utf-8")
            payload = root / "bridge.dll"
            payload.write_bytes(b"payload")
            expected = {rel: stage_package.sha256(game / rel) for rel in stage_package.FILES}
            with patch.object(stage_package, "FILES", expected):
                diagnostics = stage_package.build_diagnostics(game, plan, payload)
                self.assertTrue(diagnostics["activation_allowed"])
                with self.assertRaisesRegex(RuntimeError, "inside the game installation"):
                    stage_package.stage(HERE, game / "staging", diagnostics, payload)


if __name__ == "__main__":
    unittest.main()
