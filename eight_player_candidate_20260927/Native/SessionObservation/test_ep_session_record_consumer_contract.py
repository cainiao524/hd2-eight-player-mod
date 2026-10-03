from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import ep_session_record_consumer_contract as contract


class SessionRecordConsumerContractTests(unittest.TestCase):
    def test_saved_consumers_are_bounded_and_opaque(self) -> None:
        result = contract.recover()
        self.assertEqual(result["status"], "static_record_consumer_xref_only")
        self.assertEqual(result["record_layout"]["stride"], "0x30")
        self.assertEqual(result["record_layout"]["token_field"], "record + 0x00")
        self.assertEqual(result["record_layout"]["observed_byte_field"], "record + 0x29")
        self.assertFalse(result["semantic_limits"]["identity_token_is_peer_id"])
        self.assertFalse(result["semantic_limits"]["record_ordinal_is_player_slot"])
        self.assertFalse(result["semantic_limits"]["whole_image_xrefs_exhausted"])
        self.assertFalse(result["safety"]["process_accessed_in_this_run"])
        self.assertEqual(result["join_context"]["direct_session_target_rvas_in_selected_protocol_join_text"], [])

    def test_instruction_drift_fails_closed(self) -> None:
        source = json.loads(contract.SESSION_SOURCE.read_text(encoding="utf-8"))
        for row in source["rows"]:
            for ins in row["instructions"]:
                if str(ins.get("rva", "")).lower() == "0x292d20":
                    ins["bytes"] = "90"
        with tempfile.TemporaryDirectory() as temp:
            mutated = Path(temp) / "session.json"
            mutated.write_text(json.dumps(source), encoding="utf-8")
            old = contract.SESSION_SOURCE
            contract.SESSION_SOURCE = mutated
            try:
                with self.assertRaises(ValueError):
                    contract.recover()
            finally:
                contract.SESSION_SOURCE = old

    def test_direct_cross_module_reference_fails_closed(self) -> None:
        old = contract.PROTOCOL_SOURCE
        try:
            with tempfile.TemporaryDirectory() as temp:
                mutated = Path(temp) / "protocol.json"
                source = json.loads(old.read_text(encoding="utf-8"))
                source["roots"][0]["strings"].append({"text": "target 0x292d20"})
                mutated.write_text(json.dumps(source), encoding="utf-8")
                contract.PROTOCOL_SOURCE = mutated
                with self.assertRaises(ValueError):
                    contract.recover()
        finally:
            contract.PROTOCOL_SOURCE = old


if __name__ == "__main__":
    unittest.main()
