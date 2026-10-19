"""Standard-library tests for the explicit-input offline build gate."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_profile as gate  # noqa: E402


PACKAGE_ROOT = HERE.parent
PROFILE_PATH = HERE / "profile_template.json"


class BuildProfileTests(unittest.TestCase):
    def profile(self) -> dict:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    def test_profile_is_pinned_and_unknown_roles_stay_unresolved(self) -> None:
        profile = self.profile()
        gate.validate_profile(profile)
        self.assertFalse(profile["live_ready"])
        self.assertEqual(profile["required_fingerprints"]["exe"]["trust_status"],
                         "pinned_saved_evidence")
        self.assertIsNone(profile["required_fingerprints"]["party"]["sha256"])
        self.assertEqual(profile["required_fingerprints"]["party"]["trust_status"], "unresolved")

    def test_candidate_manifest_and_all_declared_sources_match(self) -> None:
        result = gate.verify_manifest(PACKAGE_ROOT, "candidate-manifest.json")
        self.assertTrue(result["verified"], result["errors"])
        manifest = json.loads((PACKAGE_ROOT / "candidate-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(result["files"]), len(manifest["source_sha256"]))

    def test_unresolved_observed_party_hash_is_never_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "PartyWin.dll").write_bytes(b"observed bytes")
            result = gate.check(profile=self.profile(), input_root=root,
                                supplied_files={"party": "PartyWin.dll"},
                                package_root=PACKAGE_ROOT,
                                manifest_relative="candidate-manifest.json")
        party = next(row for row in result["files"] if row["role"] == "party")
        self.assertEqual(party["status"], "observed_untrusted")
        self.assertFalse(result["required_fingerprints_verified"])
        self.assertFalse(result["pre_install_gate_passed"])
        self.assertFalse(result["live_ready"])
        self.assertFalse(result["process_accessed"])

    def test_known_file_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "game.dll").write_bytes(b"wrong build")
            result = gate.check(profile=self.profile(), input_root=root,
                                supplied_files={"game_dll": "game.dll"},
                                package_root=PACKAGE_ROOT,
                                manifest_relative="candidate-manifest.json")
        game = next(row for row in result["files"] if row["role"] == "game_dll")
        self.assertEqual(game["status"], "mismatch")
        self.assertIn("required fingerprint mismatch: game_dll", result["errors"])
        self.assertFalse(result["live_ready"])

    def test_path_escape_and_absolute_path_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "file.bin").write_bytes(b"x")
            for value in ("../file.bin", str(root / "file.bin"), "a\\b.bin", "a/../b.bin"):
                with self.subTest(value=value):
                    with self.assertRaises(gate.GateError):
                        gate.checked_path(root, value)

    def test_profile_cannot_be_changed_to_trust_observed_hash(self) -> None:
        profile = self.profile()
        profile["required_fingerprints"]["party"]["sha256"] = "0" * 64
        profile["required_fingerprints"]["party"]["trust_status"] = "pinned_saved_evidence"
        with self.assertRaises(gate.GateError):
            gate.validate_profile(profile)

    def test_missing_required_files_and_unresolved_roles_block_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = gate.check(profile=self.profile(), input_root=Path(temp),
                                supplied_files={}, package_root=PACKAGE_ROOT,
                                manifest_relative="candidate-manifest.json")
        self.assertTrue(result["package_integrity_verified"], result["manifest"]["errors"])
        self.assertFalse(result["pre_install_gate_passed"])
        self.assertFalse(result["live_ready"])
        self.assertIn("required_file_not_supplied:exe", result["blockers"])
        self.assertIn("unresolved_required_fingerprint:party", result["blockers"])


if __name__ == "__main__":
    unittest.main()
