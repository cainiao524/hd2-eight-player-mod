from __future__ import annotations

import json
import copy
import tempfile
import unittest
from pathlib import Path

import admission_callback_abi_contract_20261003 as contract


class AdmissionCallbackAbiContractTests(unittest.TestCase):
    def test_contract_is_version_locked_and_fail_closed(self) -> None:
        result = contract.recover()
        self.assertEqual(result["status"], "static_abi_contract_fail_closed")
        self.assertEqual(result["build"], 25480438)
        self.assertEqual(len(result["callbacks"]), 6)
        self.assertEqual(result["callbacks"][0]["target"]["table_offset"], "0x08")
        self.assertEqual(result["callbacks"][1]["target"]["table_offset"], "0x50")
        self.assertFalse(result["callbacks"][0]["target"]["resolved"])
        self.assertFalse(result["callbacks"][0]["return"]["semantics_proven"])
        self.assertFalse(result["cleanup_contract"]["cleanup_abi_proven"])
        self.assertFalse(result["safety"]["process_accessed"])
        self.assertFalse(result["safety"]["function_calls_made"])
        self.assertFalse(result["safety"]["memory_writes"])
        self.assertFalse(result["safety"]["installable"])

    def test_source_mutation_is_rejected(self) -> None:
        original = contract.SOURCE_FILES["host_admission"]
        raw = original.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            mutated = Path(temp) / "host.json"
            doc = json.loads(raw.decode("utf-8"))
            for fragment in doc["fragments"]:
                for row in fragment.get("instructions", []):
                    if row.get("rva") == "0x108ddc7":
                        row["bytes"] = "90"
            mutated.write_text(json.dumps(doc), encoding="utf-8")
            contract.SOURCE_FILES["host_admission"] = mutated
            try:
                with self.assertRaises(ValueError):
                    contract.recover()
            finally:
                contract.SOURCE_FILES["host_admission"] = original

    def test_known_direct_targets_remain_candidates(self) -> None:
        result = contract.recover()
        sender = result["callbacks"][2]
        insert = result["callbacks"][3]
        self.assertEqual(sender["target"]["address_rva"], "0xbe4910")
        self.assertEqual(insert["target"]["address_rva"], "0xb90b20")
        self.assertFalse(sender["proven"])
        self.assertFalse(insert["proven"])
        self.assertFalse(result["state_contract"]["state_transition_abi_proven"])

    def test_artifact_cannot_promote_a_candidate_to_proven(self) -> None:
        result = contract.recover()
        self.assertEqual(contract.verify(result)["status"], "passed_static_callback_abi_replay")
        altered = copy.deepcopy(result)
        altered["callbacks"][0]["proven"] = True
        with self.assertRaises(ValueError):
            contract.verify(altered)

    def test_dispatch_state_is_not_network_index(self) -> None:
        state = contract.recover()["state_contract"]["dispatch_state_tests"]
        self.assertEqual(state["lower_bound_inclusive"], 5)
        self.assertEqual(state["bool_flag_lower_bound_inclusive"], 7)
        self.assertIsNone(state["upper_bound"])
        self.assertFalse(state["network_index_gate"])

    def test_nested_status_mask_and_branch_are_not_success_enums(self) -> None:
        probe = contract.recover()["callbacks"][4]["return"]
        self.assertEqual([value for value in range(16) if (((value-1) & 0xffffffff) & 0xfffffffa) == 0], probe["mask_pass_values"])
        self.assertEqual(probe["branch_0x108c043_without_cleanup_candidate"], [1, 5, 6])
        self.assertFalse(probe["semantics_proven"])


if __name__ == "__main__":
    unittest.main()
