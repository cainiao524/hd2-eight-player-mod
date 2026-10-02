import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from admission_observation import ObservationLog, validate_observation


def lobby(count=4, maximum=4):
    return {"member_count": count, "max_member_count": maximum,
            "membership_lock": False, "join_status": "accepted"}


def party(users=4, max_users=4, devices=4, max_devices=4, endpoints=4, max_endpoints=4):
    return {"user_count": users, "max_user_count": max_users,
            "device_count": devices, "max_device_count": max_devices,
            "endpoint_count": endpoints, "max_endpoint_count": max_endpoints,
            "join_status": "accepted"}


class AdmissionObservationTests(unittest.TestCase):
    def test_layers_require_exact_fields_and_safe_bounds(self):
        self.assertEqual(validate_observation("playfab_lobby", lobby()), (True, "observation_valid"))
        invalid = lobby(5, 4)
        self.assertEqual(validate_observation("playfab_lobby", invalid)[1], "member_count_exceeds_max")
        invalid = lobby()
        invalid["extra"] = True
        self.assertEqual(validate_observation("playfab_lobby", invalid)[1], "field_set_mismatch")

    def test_log_is_explicit_and_detached(self):
        log = ObservationLog()
        fields = lobby()
        self.assertEqual(log.append("playfab_lobby", fields), (True, "recorded"))
        fields["member_count"] = 99
        snapshot = log.snapshot()
        snapshot[0]["fields"]["member_count"] = 77
        self.assertEqual(log.snapshot()[0]["fields"]["member_count"], 4)

    def test_roster_cannot_report_active_more_than_occupied(self):
        fields = {"occupied_count": 1, "active_count": 2, "generation": 1, "entries": []}
        self.assertEqual(validate_observation("roster", fields)[1], "active_exceeds_occupied")

    def test_party_limits_cover_users_devices_and_endpoints(self):
        self.assertEqual(validate_observation("party_network", party()), (True, "observation_valid"))
        for key, reason in (("user_count", "user_count_exceeds_max"),
                            ("device_count", "device_count_exceeds_max"),
                            ("endpoint_count", "endpoint_count_exceeds_max")):
            fields = party()
            fields[key] = fields["max_" + key]
            fields[key] += 1
            self.assertEqual(validate_observation("party_network", fields)[1], reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
