import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peer_admission_adapter import PeerAdmissionAdapter


def lobby(count=8, maximum=8):
    return {"member_count": count, "max_member_count": maximum,
            "membership_lock": False, "join_status": "accepted"}


def party(users=8, max_users=8, devices=8, max_devices=8, endpoints=8, max_endpoints=8):
    return {"user_count": users, "max_user_count": max_users,
            "device_count": devices, "max_device_count": max_devices,
            "endpoint_count": endpoints, "max_endpoint_count": max_endpoints,
            "join_status": "accepted"}


def peers(names=8):
    return {"peer_count": names, "records": [
        {"peer_id": f"peer-{index}", "member_id": f"member-{index}", "network_index": index}
        for index in range(names)
    ]}


def confirmed(index=0, member=None, peer=None):
    return {"peer_count": 1, "records": [
        {"peer_id": peer or f"peer-{index}", "member_id": member or f"member-{index}",
         "network_index": index}
    ]}


class PeerAdmissionAdapterTests(unittest.TestCase):
    def ready(self, mode="host_only", role="host"):
        adapter = PeerAdmissionAdapter(mode=mode, role=role)
        self.assertTrue(adapter.observe("playfab_lobby", lobby(), "session-1").accepted)
        self.assertTrue(adapter.observe("party_network", party(), "session-1").accepted)
        self.assertTrue(adapter.observe("host_peer", peers(), "session-1").accepted)
        return adapter

    def test_allocates_all_eight_indexes_and_rejects_ninth(self):
        adapter = self.ready()
        for index in range(8):
            result = adapter.admit_peer(f"member-{index}", f"peer-{index}")
            self.assertTrue(result.accepted)
            self.assertEqual(result.details["network_index"], index)
        before = adapter.snapshot()
        result = adapter.admit_peer("member-8", "peer-8")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "observed_session_capacity_insufficient")
        self.assertEqual(adapter.snapshot()["capacity"]["occupied_count"], before["capacity"]["occupied_count"])

    def test_pending_resource_departure_and_reconnect_generation(self):
        adapter = self.ready()
        reserved = adapter.admit_peer("member-4", "peer-4", 4)
        self.assertTrue(reserved.accepted)
        generation = reserved.details["generation"]
        self.assertTrue(adapter.observe("client_confirmed_peer", confirmed(4), "session-1").accepted)
        self.assertTrue(adapter.bind_resource("peer-4", "handle-0", generation).accepted)
        self.assertTrue(adapter.depart_peer("peer-4", generation).accepted)
        self.assertTrue(adapter.observe("playfab_lobby", lobby(), "session-2").accepted)
        self.assertTrue(adapter.observe("party_network", party(), "session-2").accepted)
        self.assertTrue(adapter.observe("host_peer", {
            "peer_count": 1,
            "records": [{"peer_id": "peer-4-reconnect", "member_id": "member-4", "network_index": 4}],
        }, "session-2").accepted)
        reconnected = adapter.reconnect_peer("member-4", "peer-4-reconnect", 4)
        self.assertTrue(reconnected.accepted)
        self.assertGreater(reconnected.details["generation"], generation)
        self.assertFalse(adapter.bind_resource("peer-4-reconnect", "stale", generation).accepted)
        self.assertFalse(adapter.depart_peer("peer-4-reconnect", generation).accepted)

    def test_host_only_is_a_policy_label_and_snapshot_stays_offline(self):
        adapter = self.ready(mode="host_only", role="host")
        result = adapter.admit_peer("member-0", "peer-0")
        self.assertTrue(result.accepted)
        snapshot = adapter.snapshot()
        self.assertEqual(snapshot["mode"], "host_only")
        self.assertFalse(snapshot["native_adapter_present"])
        self.assertFalse(snapshot["live_ready"])
        self.assertFalse(snapshot["multiplayer_verified"])

    def test_missing_preflight_and_duplicate_identity_fail_closed(self):
        adapter = PeerAdmissionAdapter(mode="all_clients", role="client")
        result = adapter.admit_peer("member-0", "peer-0")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "preflight_observation_missing")
        self.assertTrue(adapter.observe("playfab_lobby", lobby(), "session-1").accepted)
        self.assertTrue(adapter.observe("party_network", party(), "session-1").accepted)
        self.assertTrue(adapter.observe("host_peer", peers(), "session-1").accepted)
        self.assertTrue(adapter.admit_peer("member-0", "peer-0").accepted)
        self.assertEqual(adapter.admit_peer("member-0", "peer-1").reason, "duplicate_member_id")
        self.assertEqual(adapter.admit_peer("member-1", "peer-0").reason, "duplicate_peer_id")

    def test_invalid_party_limits_are_rejected_before_admission(self):
        adapter = PeerAdmissionAdapter()
        self.assertTrue(adapter.observe("playfab_lobby", lobby(), "session-1").accepted)
        invalid = party(endpoints=9, max_endpoints=8)
        result = adapter.observe("party_network", invalid, "session-1")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "endpoint_count_exceeds_max")
        self.assertEqual(adapter.admit_peer("member-0", "peer-0").reason, "preflight_observation_missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
