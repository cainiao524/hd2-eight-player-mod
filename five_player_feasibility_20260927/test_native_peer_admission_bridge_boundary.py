import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_native_peer_admission_bridge_boundary import (  # noqa: E402
    BOUNDARY,
    BoundaryError,
    REQUIRED_GAME_RVAS,
    verify,
)


class NativePeerAdmissionBridgeBoundaryTests(unittest.TestCase):
    def test_saved_boundary_is_static_and_blocked(self):
        result = verify()
        self.assertEqual(result["status"], "passed_static_boundary_checks")
        self.assertEqual(result["checks"]["capture_required_game_sites"],
                         len(REQUIRED_GAME_RVAS))
        self.assertFalse(result["checks"]["production_patch_emitted"])
        self.assertFalse(result["checks"]["multiplayer_verified"])

    def test_boundary_keeps_production_blockers(self):
        result = verify()
        unresolved = " ".join(result["unresolved"])
        self.assertIn("runtime PlayFab/Party", unresolved)
        self.assertIn("hash-to-receiver", unresolved)
        self.assertIn("mid-function", unresolved)

    def test_boundary_file_is_repository_local(self):
        self.assertTrue(BOUNDARY.is_file())
        self.assertEqual(BOUNDARY.parent, Path(__file__).resolve().parent)

    def test_missing_capture_site_fails_closed(self):
        from tempfile import TemporaryDirectory
        import json

        with TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "native_peer_admission_bridge_boundary_20261002.json",
                "native_peer_admission_plan_20261002.json",
                "midgate_bridge_plan_20261002.json",
                "live_native_session_capture_20261002.json",
            ):
                source = Path(__file__).resolve().parent / name
                (root / name).write_bytes(source.read_bytes())
            capture_path = root / "live_native_session_capture_20261002.json"
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            capture["rows"] = [
                row for row in capture["rows"]
                if str(row.get("rva", "")).lower() != "0x108c760"
            ]
            capture_path.write_text(json.dumps(capture), encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "capture_sites_missing"):
                verify(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
