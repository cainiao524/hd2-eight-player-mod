from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent

class RuntimeProbeTests(unittest.TestCase):
    def test_report_is_build_pinned_and_non_executable(self):
        report = json.loads((HERE / "runtime_probe_report_20261002.json").read_text(encoding="utf-8"))
        self.assertEqual(report["build"]["steam_build"], 25480438)
        self.assertEqual(report["build"]["host_join_rva"], "0x108bc70")
        self.assertEqual(report["test"]["exit_code"], 0)
        self.assertEqual(report["test"]["marker"], "ep_runtime_probe_synthetic_passed")
        self.assertFalse(report["production"]["executable"])
        self.assertFalse(report["production"]["multiplayer_verified"])
        self.assertNotIn("install_game_rva", report["exports"])
        self.assertIn("copied host-join entry frame", report["scope"])

    def test_prologue_hash_is_pinned(self):
        raw = bytes.fromhex("405553564154488d6c24e94881ecc8000000")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "8deecd0b4075eee3e436db6d5787ba68feb5ade0b9401ce1eee9814995309624")

if __name__ == "__main__":
    unittest.main()

