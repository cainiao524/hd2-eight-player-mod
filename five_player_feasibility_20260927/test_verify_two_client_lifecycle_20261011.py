from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("two_client", HERE / "verify_two_client_lifecycle_20261011.py")
assert SPEC and SPEC.loader
two_client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(two_client)


def snapshot(count: int, *, pid: int = 10, host: str = "0000000000000001", local: str = "0000000000000001",
             peers: list[tuple[int, str]] | None = None, roster: list[str] | None = None,
             owner: str = "owner") -> dict:
    peers = peers if peers is not None else [(0, "0000000000000001")] if count == 1 else [(0, "0000000000000001"), (1, "0000000000000002")]
    roster = roster if roster is not None else [name for _, name in peers]
    records = []
    for ordinal in range(4):
        peer = roster[ordinal] if ordinal < len(roster) else "0000000000000000"
        records.append({"ordinal": ordinal, "peer_id_hex": peer, "name": ""})
    return {
        "schema": two_client.SCHEMA, "build": two_client.BUILD, "status": "observed_context",
        "pid": pid, "read_only": True, "calls_made": False, "writes_made": False,
        "hooks_installed": False,
        "pinned_images": {
            "helldivers2.exe": {"sha256": two_client.EXE_SHA256},
            "game.dll": {"sha256": two_client.GAME_SHA256},
        },
        "roots": {"context": "0xcontext", "roster": "0xroster", "game_state": "0xstate"},
        "session": {
            "session_owner": owner, "local_peer_hex": local,
            "host_peer_hex": host, "peer_count_raw": count,
            "peers": [{"ordinal": ordinal, "lo": int(peer[-8:], 16), "hi": int(peer[:8], 16),
                       "network_index": index} for ordinal, (index, peer) in enumerate(peers)],
        },
        "roster": {"records": records},
    }


class TwoClientLifecycleTests(unittest.TestCase):
    def write(self, documents: dict[str, dict]) -> dict[str, Path]:
        directory = Path(tempfile.mkdtemp())
        result = {}
        for phase, document in documents.items():
            path = directory / f"{phase}.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result[phase] = path
        return result

    def test_join_scope_accepts_one_to_two_transition(self):
        paths = self.write({"host_before": snapshot(1), "joined": snapshot(2)})
        result = two_client.verify(paths, "join")
        self.assertEqual(result["status"], "passed_two_client_join")
        self.assertFalse(result["capacity_above_two_verified"])

    def test_full_scope_requires_every_lifecycle_phase(self):
        paths = self.write({"host_before": snapshot(1), "joined": snapshot(2)})
        with self.assertRaises(two_client.LifecycleError):
            two_client.verify(paths, "full")

    def test_cleanup_rejects_retained_peer(self):
        documents = {
            "host_before": snapshot(1),
            "joined": snapshot(2),
            "after_leave": snapshot(1),
            "migration_before": snapshot(2, local="0000000000000002", host="0000000000000001"),
            "migration_after": snapshot(1, local="0000000000000002", host="0000000000000002",
                                           peers=[(1, "0000000000000002")], roster=["0000000000000002"]),
            "cleanup": snapshot(1),
        }
        paths = self.write(documents)
        with self.assertRaises(two_client.LifecycleError):
            two_client.verify(paths, "full")


if __name__ == "__main__":
    unittest.main()
