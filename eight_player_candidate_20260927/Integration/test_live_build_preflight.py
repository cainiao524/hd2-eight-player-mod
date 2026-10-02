import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_build_preflight as preflight


class LiveBuildPreflightTests(unittest.TestCase):
    def _plan(self, *, executable=False, multiplayer_verified=False):
        return {
            "steam_build": preflight.STEAM_BUILD,
            "executable": executable,
            "multiplayer_verified": multiplayer_verified,
            "sidecar": {"host_peer_slots": 8, "client_confirmed_slots": 8},
        }

    def test_real_install_matches_all_six_files_and_blocks_non_executable_plan(self):
        root = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2")
        plan = Path(tempfile.gettempdir()) / "hd2-native-plan-test.json"
        plan.write_text(__import__("json").dumps(self._plan()), encoding="utf-8")
        result = preflight.preflight(root, plan, process_check=lambda _: False)
        self.assertTrue(result["build_verified"])
        self.assertTrue(result["files_verified"])
        self.assertFalse(result["staging_preflight_passed"])
        self.assertIn("native_peer_admission_plan_not_executable", result["blockers"])
        plan.unlink(missing_ok=True)

    def test_running_process_blocks_staging(self):
        root = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2")
        plan = Path(tempfile.gettempdir()) / "hd2-native-plan-test-running.json"
        plan.write_text(__import__("json").dumps(self._plan(executable=True)), encoding="utf-8")
        result = preflight.preflight(root, plan, process_check=lambda _: True)
        self.assertTrue(result["build_verified"])
        self.assertFalse(result["stopped_process_gate_passed"])
        self.assertIn("game_process_running_staging_requires_stopped_process", result["blockers"])
        plan.unlink(missing_ok=True)

    def test_multiplayer_true_is_rejected(self):
        root = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2")
        plan = Path(tempfile.gettempdir()) / "hd2-native-plan-test-mp.json"
        plan.write_text(__import__("json").dumps(self._plan(executable=True, multiplayer_verified=True)), encoding="utf-8")
        result = preflight.preflight(root, plan, process_check=lambda _: False)
        self.assertFalse(result["native_peer_admission_plan"]["valid"])
        self.assertIn("native_plan_multiplayer_verified_must_remain_false", result["errors"])
        plan.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
