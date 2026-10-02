"""Run the already-built x64 synthetic hook harness and verify its receipt."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parent


class HookScaffoldTests(unittest.TestCase):
    def test_report_is_fail_closed_and_harness_passes(self) -> None:
        report = json.loads((ROOT / "hook_scaffold_report_20261002.json").read_text(encoding="utf-8"))
        self.assertEqual(report["steam_build"], 25480438)
        self.assertFalse(report["production_status"]["executable"])
        self.assertFalse(report["production_status"]["multiplayer_verified"])
        self.assertFalse(report["production_status"]["install_game_rva_export"])
        result = subprocess.run([str(ROOT / "native_hook_test.exe")], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("native_hook_scaffold_synthetic_passed", result.stdout)

    def test_host_join_prologue_matches_authorized_capture(self) -> None:
        capture_path = ROOT.parents[2] / "five_player_feasibility_20260927" / "live_native_session_capture_20261002.json"
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        row = next(item for item in capture["rows"]
                   if item.get("module") == "game" and item.get("rva") == "0x108bc70")
        prologue = bytes.fromhex(row["bytes"])[:18]
        self.assertEqual(prologue.hex(), "405553564154488d6c24e94881ecc8000000")
        report = json.loads((ROOT / "hook_scaffold_report_20261002.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(prologue).hexdigest(),
                         report["hook_model"]["production_candidate"]["prologue_sha256"])


if __name__ == "__main__":
    unittest.main()
