from __future__ import annotations

import unittest

import admission_dispatch_cleanup_contract_20261003 as contract


class AdmissionDispatchCleanupContractTests(unittest.TestCase):
    def test_dispatch_reads_state_with_no_upper_bound(self) -> None:
        dispatch = contract.recover()["host_to_client_dispatch"]
        gate = dispatch["observed_state_gate"]
        self.assertEqual(gate["field"], "record+0x20 (RDI)")
        self.assertEqual(gate["low_inclusive"], 5)
        self.assertIsNone(gate["upper_bound"])
        self.assertTrue(gate["state_ge_7_stack_flag"])
        self.assertFalse(gate["network_index_gate"])
        self.assertNotIn("observed_index_gate", dispatch)
        rows = dispatch["fixed_rows"]
        self.assertEqual(rows["record_state_load"]["bytes"], "8b07")
        self.assertEqual(rows["state_below_5_skip"]["asm"], "jb 0x108c980")
        self.assertEqual(rows["state_ge_7_flag"]["asm"], "setae al")

    def test_state_branch_instruction_drift_is_rejected(self) -> None:
        original = contract.load
        docs, hashes = original()
        row = contract.rows(docs["host_dispatch"])["0x108c912"]
        row["bytes"] = "0f92c0"
        contract.load = lambda: (docs, hashes)
        try:
            with self.assertRaises(ValueError):
                contract.recover()
        finally:
            contract.load = original

    def test_all_runtime_claims_remain_false(self) -> None:
        result = contract.recover()
        self.assertFalse(result["target_resolution"]["player_index_4_to_7_proven"])
        self.assertFalse(result["join_status_and_cleanup"]["cleanup_abi_proven"])
        self.assertTrue(all(value is False for value in result["safety"].values()))


if __name__ == "__main__":
    unittest.main()
