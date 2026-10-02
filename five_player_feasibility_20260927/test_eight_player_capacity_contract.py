import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eight_player_capacity_contract import AdmissionState, CapacitySpec, validate_snapshot


class EightPlayerCapacityContractTests(unittest.TestCase):
    def test_profile_is_pinned_to_build_and_eight_slots(self):
        spec = CapacitySpec()
        self.assertEqual(spec.validate_profile(spec.profile()), (True, "profile_match"))
        wrong = spec.profile()
        wrong["build"] = 1
        self.assertEqual(spec.validate_profile(wrong), (False, "profile_mismatch:build"))
        with self.assertRaises(ValueError):
            AdmissionState(profile={})

    def test_indices_zero_through_seven_are_reserved_then_eight_is_rejected(self):
        state = AdmissionState()
        generations = []
        for index in range(8):
            result = state.insert(f"peer-{index}", index)
            self.assertTrue(result.accepted)
            generations.append(result.details["generation"])
        self.assertEqual(state.active_count, 0)
        self.assertEqual(state.occupied_count, 8)
        self.assertEqual(state.insert("peer-8", 8).reason, "network_index_out_of_range")
        for index, token in enumerate(generations):
            self.assertTrue(state.bind_resource(index, f"handle-{index}", token).accepted)
        self.assertEqual(state.active_count, 8)

    def test_duplicate_index_and_peer_have_no_mutation(self):
        state = AdmissionState()
        state.insert("peer-a", 4)
        generation = state.generation
        self.assertEqual(state.insert("peer-b", 4).reason, "duplicate_network_index")
        self.assertEqual(state.insert("peer-a", 5).reason, "duplicate_peer_id")
        self.assertEqual((state.occupied_count, state.generation), (1, generation))

    def test_remove_preserves_hole_and_stale_token_cannot_bind_reused_index(self):
        state = AdmissionState()
        first = state.insert("peer-a", 4)
        second = state.insert("peer-b", 5)
        ordinal_b = state.lookup(5)[1].ordinal
        self.assertEqual(state.remove(4, first.details["generation"]).reason, "removed")
        new = state.insert("peer-c", 4)
        self.assertEqual(state.lookup(5)[1].ordinal, ordinal_b)
        self.assertEqual(state.lookup(4)[1].ordinal, 0)
        self.assertEqual(state.bind_resource(4, "old-resource", first.details["generation"]).reason, "stale_generation")
        self.assertEqual(state.bind_resource(4, "new-resource", new.details["generation"]).reason, "confirmed")

    def test_snapshot_rejects_duplicate_or_mismatched_entries(self):
        state = AdmissionState()
        reserved = state.insert("peer-a", 0)
        state.bind_resource(0, "handle-a", reserved.details["generation"])
        snapshot = state.snapshot()
        self.assertTrue(validate_snapshot(snapshot).accepted)
        broken = copy.deepcopy(snapshot)
        broken["active_count"] = 2
        self.assertEqual(validate_snapshot(broken).reason, "active_count_mismatch")
        broken = copy.deepcopy(snapshot)
        broken["entries"].append(copy.deepcopy(broken["entries"][0]))
        broken["occupied_count"] = 2
        self.assertEqual(validate_snapshot(broken).reason, "duplicate_network_index")
        broken = copy.deepcopy(snapshot)
        broken["entries"][0]["resource_handle"] = ""
        self.assertEqual(validate_snapshot(broken).reason, "resource_handle_missing")

    def test_corrupt_reverse_map_is_rejected_before_mutation(self):
        state = AdmissionState()
        state.insert("peer-a", 0)
        state.by_network_index[7] = 0
        before = state.snapshot if False else state.generation
        self.assertEqual(state.insert("peer-b", 1).reason, "index_ordinal_mismatch")
        self.assertEqual(state.generation, before)

    def test_resource_binding_and_unknown_removal_fail_closed(self):
        state = AdmissionState()
        self.assertEqual(state.bind_resource(0, "h", 1).reason, "network_index_missing")
        inserted = state.insert("peer-a", 0)
        self.assertEqual(state.bind_resource(0, "", inserted.details["generation"]).reason, "resource_handle_missing")
        self.assertEqual(state.remove(8, inserted.details["generation"]).reason, "network_index_out_of_range")

    def test_corrupt_diagnostics_is_rejected_before_mutation(self):
        state = AdmissionState()
        state.diagnostics = None
        self.assertEqual(state.insert("peer-a", 0).reason, "diagnostics_invalid")

    def test_snapshot_and_diagnostics_are_detached(self):
        state = AdmissionState()
        inserted = state.insert("peer-a", 0)
        state.bind_resource(0, "handle-a", inserted.details["generation"])
        snapshot = state.snapshot()
        snapshot["entries"][0]["resource_handle"] = "mutated"
        snapshot["diagnostics"][0]["reason"] = "mutated"
        self.assertEqual(state.lookup(0)[1].resource_handle, "handle-a")
        self.assertNotEqual(state.diagnostics[0]["reason"], "mutated")


if __name__ == "__main__":
    unittest.main(verbosity=2)
