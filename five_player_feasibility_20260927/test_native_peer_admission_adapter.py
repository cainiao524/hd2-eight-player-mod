import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_peer_admission_adapter import (
    CAPTURE_SITE_SHA256, MAX_PLAYERS, NativePlanError, NativeSidecar, NATIVE_SITES,
    plan_from_capture, validate_build_files,
)


class NativePeerAdmissionAdapterTests(unittest.TestCase):
    def test_sidecar_allocates_all_indexes_and_preserves_holes(self):
        sidecar = NativeSidecar()
        for index in range(MAX_PLAYERS):
            result = sidecar.reserve(f"member-{index}", f"peer-{index}", index)
            self.assertTrue(result["accepted"])
            generation = result["generation"]
            self.assertTrue(sidecar.confirm(f"peer-{index}", generation, f"handle-{index}")["accepted"])
        self.assertFalse(sidecar.reserve("member-8", "peer-8", 8)["accepted"])
        removed = sidecar.remove("peer-3", sidecar.generations[3])
        self.assertTrue(removed["accepted"])
        self.assertIsNone(sidecar.peers[3])
        self.assertEqual(sidecar.snapshot()["occupied_count"], 7)

    def test_generation_blocks_stale_confirm_and_reconnect(self):
        sidecar = NativeSidecar()
        first = sidecar.reserve("member-4", "peer-a", 4)
        self.assertTrue(first["accepted"])
        self.assertTrue(sidecar.remove("peer-a", first["generation"])["accepted"])
        second = sidecar.reserve("member-4", "peer-b", 4)
        self.assertTrue(second["accepted"])
        self.assertGreater(second["generation"], first["generation"])
        self.assertEqual(sidecar.confirm("peer-b", first["generation"], "stale")["reason"],
                         "stale_generation")

    def test_duplicate_identity_and_handle_fail_closed(self):
        sidecar = NativeSidecar()
        self.assertTrue(sidecar.reserve("member-0", "peer-0", 0)["accepted"])
        self.assertEqual(sidecar.reserve("member-0", "peer-1", 1)["reason"], "duplicate_identity")
        self.assertTrue(sidecar.confirm("peer-0", 1, "shared")["accepted"])
        self.assertTrue(sidecar.reserve("member-1", "peer-1", 1)["accepted"])
        self.assertEqual(sidecar.confirm("peer-1", 1, "shared")["reason"], "resource_handle_duplicate")

    def test_capture_plan_requires_all_game_roots(self):
        rows = [{"module": "game", "rva": hex(site["rva"]), "size": 4096,
                 "sha256": CAPTURE_SITE_SHA256[site["rva"]]}
                for site in NATIVE_SITES if site["module"] == "game"]
        capture = {"schema": "hd2_live_module_capture_v1", "build": 25480438,
                   "pid": 123, "scope": "test", "rows": rows}
        plan = plan_from_capture(capture)
        self.assertEqual(plan["sidecar"]["host_peer_slots"], 8)
        self.assertFalse(plan["executable"])
        self.assertFalse(plan["multiplayer_verified"])
        missing = dict(capture)
        missing["rows"] = rows[:-1]
        with self.assertRaises(NativePlanError):
            plan_from_capture(missing)

    def test_capture_plan_rejects_wrong_build(self):
        capture = {"schema": "hd2_live_module_capture_v1", "build": 1, "rows": []}
        with self.assertRaisesRegex(NativePlanError, "steam_build_mismatch"):
            plan_from_capture(capture)

    def test_local_native_file_fingerprints(self):
        game_root = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2")
        files = {
            "exe": game_root / "bin" / "helldivers2.exe",
            "game": game_root / "data" / "game" / "game.dll",
            "party": game_root / "bin" / "PartyWin.dll",
            "playfab": game_root / "bin" / "PlayFabMultiplayerWin.dll",
        }
        if not all(path.is_file() for path in files.values()):
            self.skipTest("local build files are unavailable")
        result = validate_build_files(files)
        self.assertTrue(result["verified"])
        self.assertEqual(result["steam_build"], 25480438)


if __name__ == "__main__":
    unittest.main(verbosity=2)
