from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import admission_boundary_contract_20261003 as contract


class AdmissionBoundaryContractTests(unittest.TestCase):
    def test_saved_call_shape_is_two_site_and_fail_closed(self) -> None:
        result = contract.recover()
        self.assertEqual(result["status"], "static_call_shape_only")
        self.assertEqual([row["rva"] for row in result["call_sites"]], ["0x108ddc7", "0x108de09"])
        self.assertFalse(result["semantics"]["peer_admission_proven"])
        self.assertFalse(result["safety"]["function_calls_made"])
        self.assertFalse(result["safety"]["memory_writes"])

    def test_call_bytes_drift_is_rejected(self) -> None:
        source = json.loads(contract.SOURCE.read_text(encoding="utf-8"))
        for fragment in source["fragments"]:
            for row in fragment["instructions"]:
                if row["rva"] == "0x108ddc7":
                    row["bytes"] = "90"
        with tempfile.TemporaryDirectory() as temp:
            mutated = Path(temp) / "capture.json"
            mutated.write_text(json.dumps(source), encoding="utf-8")
            old = contract.SOURCE
            contract.SOURCE = mutated
            try:
                with self.assertRaises(ValueError):
                    contract.recover()
            finally:
                contract.SOURCE = old


if __name__ == "__main__":
    unittest.main()
