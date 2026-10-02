from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("acceptance", HERE / "verify_multiplayer_acceptance.py")
assert SPEC and SPEC.loader
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


def make_log(index: int, *, live: bool = True) -> dict:
    events = [{"name": name} for name in acceptance.REQUIRED_EVENTS]
    events.append({"name": "host_migration"})
    return {
        "account_id": f"account-{index}",
        "client_id": f"client-{index}",
        "steam_build": acceptance.BUILD,
        "exe_version": acceptance.EXE_VERSION,
        "mission_id": "mission-1",
        "session_id": "session-1",
        "network_index": index,
        "peer_id": f"peer-{index}",
        "resource_handle": f"resource-{index}",
        "entity_id": f"entity-{index}",
        "roster_ordinal": index,
        "multiplayer_verified": live,
        "events": events,
    }


class AcceptanceTests(unittest.TestCase):
    def write_logs(self, logs):
        directory = Path(tempfile.mkdtemp())
        paths = []
        for index, log in enumerate(logs):
            path = directory / f"client-{index}.json"
            path.write_text(json.dumps(log), encoding="utf-8")
            paths.append(path)
        return paths

    def test_eight_live_clients_pass(self):
        result = acceptance.verify(self.write_logs([make_log(i) for i in range(8)]))
        self.assertEqual(result["status"], "passed_live_multiplayer_acceptance")
        self.assertEqual(result["network_indexes"], list(range(8)))
        self.assertFalse(result["synthetic"])

    def test_seven_logs_fail_closed(self):
        with self.assertRaises(acceptance.AcceptanceError):
            acceptance.verify(self.write_logs([make_log(i) for i in range(7)]))

    def test_duplicate_index_fails_closed(self):
        logs = [make_log(i) for i in range(8)]
        logs[7]["network_index"] = 6
        with self.assertRaises(acceptance.AcceptanceError):
            acceptance.verify(self.write_logs(logs))

    def test_not_live_input_fails_closed(self):
        with self.assertRaises(acceptance.AcceptanceError):
            acceptance.verify(self.write_logs([make_log(i, live=(i != 3)) for i in range(8)]))
