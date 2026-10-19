from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from parse_hd2_party_api_probe_20261011 import latest_complete_section, parse_log


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "output/native_dispatch_20261010/live_party_api_pointer_probe_20261011.json"


class PartyApiProbeReceiptTests(unittest.TestCase):
    def test_receipt_is_read_only_and_keeps_abi_semantics_unproven(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["build"], 25480438)
        self.assertEqual(receipt["schema"], "hd2_live_party_api_pointer_probe_v1")
        self.assertTrue(receipt["probe"]["read_only"])
        self.assertFalse(receipt["probe"]["calls_made"])
        self.assertFalse(receipt["probe"]["writes_made"])
        self.assertFalse(receipt["probe"]["hooks_installed"])
        self.assertEqual(len(receipt["exe_indirect_slots"]), 6)
        self.assertTrue(receipt["findings"]["all_six_slots_point_into_exe"])
        self.assertTrue(receipt["findings"]["all_six_slots_have_first_jump"])
        self.assertTrue(receipt["findings"]["named_party_iat_binding_observed"])
        self.assertTrue(receipt["findings"]["named_playfab_iat_binding_observed"])
        self.assertFalse(receipt["findings"]["direct_party_export_pointer_binding_proven"])
        self.assertFalse(receipt["findings"]["call_target_semantics_proven"])
        self.assertFalse(receipt["findings"]["session_party_abi_proven"])
        self.assertFalse(receipt["production"]["installable"])
        self.assertFalse(receipt["production"]["multiplayer_verified"])
        self.assertEqual(receipt["probe"]["playfab_base"], "0x7fff96f80000")
        iat = {row["label"]: row for row in receipt["runtime_iat"]}
        party_base = int(receipt["probe"]["party_base"], 16)
        playfab_base = int(receipt["probe"]["playfab_base"], 16)
        self.assertEqual(int(iat["PartyNetworkSetCustomContext"]["target"], 16), party_base + 0x1EBF0)
        self.assertEqual(int(iat["PFLobbySendInvite"]["target"], 16), playfab_base + 0x3D340)
        party_rows = receipt["exe_slot_table_window"]["partywin_pointer_rows"]
        self.assertIn("PartyNetworkLeaveNetwork", {row["known_export"] for row in party_rows})
        self.assertIn("PartyNetworkRemoveLocalUser", {row["known_export"] for row in party_rows})
        callsite_windows = {row["label"]: row for row in receipt["exe_callsite_windows"]}
        self.assertEqual(set(callsite_windows), {"create_network_callsite", "follow_on_callsite"})
        self.assertEqual(callsite_windows["create_network_callsite"]["rva"].lower(), "0x8e1370")
        self.assertEqual(callsite_windows["follow_on_callsite"]["rva"].lower(), "0x8e1970")

        callsite = json.loads(
            (ROOT / "output/native_dispatch_20261010/live_party_callsite_shape_20261011.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(callsite["runtime"]["read_only"])
        self.assertFalse(callsite["runtime"]["calls_made"])
        self.assertTrue(callsite["findings"]["live_create_callsite_references_candidate_slot"])
        self.assertTrue(callsite["findings"]["live_config_shape_prefix_observed"])
        self.assertFalse(callsite["findings"]["session_party_abi_proven"])

        abi_candidate = json.loads(
            (ROOT / "output/native_dispatch_20261010/party_create_abi_candidate_20261011.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(abi_candidate["findings"]["live_callsite_shape_consistent_with_official_create_signature"])
        self.assertEqual(
            abi_candidate["evidence"]["manager_holder_candidate"]["holder_rva"].lower(),
            "0x27ced10",
        )
        self.assertFalse(abi_candidate["findings"]["manager_holder_pointer_runtime_bound"])
        self.assertFalse(abi_candidate["findings"]["session_party_abi_proven"])

        session_candidates = json.loads(
            (ROOT / "output/native_dispatch_20261010/party_session_abi_candidates_20261011.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(session_candidates["candidate_calls"]["connect_network"]["shape_consistent"])
        self.assertTrue(session_candidates["candidate_calls"]["authenticate_local_user"]["shape_consistent"])
        self.assertTrue(session_candidates["candidate_calls"]["create_endpoint"]["shape_consistent"])
        self.assertFalse(session_candidates["findings"]["candidate_targets_bound_to_partywin_exports"])
        self.assertFalse(session_candidates["findings"]["host_client_tested"])

    def test_parser_rejects_a_newer_incomplete_run(self) -> None:
        complete = (
            "2026-10-11 00:01:00 START read_only=true\n"
            "DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true\n"
        )
        incomplete = "2026-10-11 00:02:00 START read_only=true\n"
        with self.assertRaisesRegex(ValueError, "latest section is incomplete"):
            latest_complete_section(complete + incomplete)

    def test_parser_selects_the_latest_complete_run(self) -> None:
        old = (
            "2026-10-11 00:01:00 START old\n"
            "DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true\n"
        )
        new = (
            "2026-10-11 00:02:00 START new\n"
            "DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true\n"
        )
        section = latest_complete_section(old + new)
        self.assertIn("START new", section)
        self.assertNotIn("START old", section)

    def test_parser_reads_extended_holder_and_indirect_records(self) -> None:
        log_path = ROOT / "output/native_dispatch_20261010/hd2_party_api_probe_20261011_r9.log"
        raw = log_path.read_text(encoding="utf-8")
        done = "2026-10-11 03:55:49 DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true"
        extra = (
            "2026-10-11 03:55:49 EXE_GLOBAL_POINTER rva=0x27CED10 label=party_manager_holder_candidate "
            "address=0x7FF63038ED10 target=0x7FFF08320000 in_party=true in_playfab=false in_exe=false "
            "raw=00003208FF7F0000 target_code64=48895C241048896C2418\n"
            "2026-10-11 03:55:49 HOP_WINDOW label=create_network_candidate depth=0 "
            "address=0x7FF63083A7C8 size=0x1000 code4096=" + "90" * 4096 + "\n"
            "2026-10-11 03:55:49 RIP_INDIRECT label=create_network_candidate_d0 kind=call "
            "at=0x7FF63083A800 slot=0x7FF630E00000 target=0x7FFF0833EBF0 in_party=true "
            "in_playfab=false in_exe=false raw=F0EB3308FF7F0000\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".log", delete=False) as temp:
            temp.write(raw.replace(done, extra + done))
            temp_path = Path(temp.name)
        try:
            receipt = parse_log(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
        self.assertEqual(receipt["exe_global_pointers"][0]["label"], "party_manager_holder_candidate")
        self.assertEqual(len(receipt["jump_chain_4096_windows"]), 1)
        self.assertTrue(receipt["rip_indirect_targets"][0]["in_party"])
        holder = receipt["exe_global_pointers"][0]
        self.assertEqual(holder["value_kind"], "opaque_handle_not_object_pointer")
        self.assertFalse(holder["manager_object_binding_proven"])

    def parse_holder_record(self, target: str, raw: str,
                            address: str = "0x7FF63038ED10") -> dict:
        saved = (ROOT / "output/native_dispatch_20261010/hd2_party_api_probe_20261011_r9.log").read_text(
            encoding="utf-8"
        )
        done = "2026-10-11 03:55:49 DONE read_only=true no_calls=true no_writes=true hooks_installed=false direct_slot_capture=true"
        record = (
            "2026-10-11 03:55:49 EXE_GLOBAL_POINTER rva=0x27CED10 label=party_manager_holder_candidate "
            f"address={address} target={target} in_party=false in_playfab=false in_exe=false "
            f"raw={raw} target_code64=nil\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "saved.log"
            path.write_text(saved.replace(done, record + done), encoding="utf-8")
            return parse_log(path)

    def test_non_pointer_handle_is_preserved_without_object_binding(self) -> None:
        # Value and bytes from the saved PID38492 capture. Its address is
        # relocated to the r9 fixture; this is a parser test, not a live sample.
        receipt = self.parse_holder_record("0x111D43778D00F0C2", "C2F0008D77431D11")
        holder = receipt["exe_global_pointers"][0]
        self.assertEqual(holder["handle_value"], "0x111d43778d00f0c2")
        self.assertTrue(receipt["findings"]["party_manager_holder_candidate_runtime_observed"])
        self.assertTrue(receipt["findings"]["party_manager_handle_nonzero_observed"])
        self.assertFalse(receipt["findings"]["party_manager_object_binding_proven"])
        self.assertFalse(receipt["production"]["runtime_verified"])

    def test_zero_handle_and_unread_holder_are_distinct(self) -> None:
        for target, raw, observed in [("0x0", "0000000000000000", True), ("nil", "nil", False)]:
            with self.subTest(target=target):
                findings = self.parse_holder_record(target, raw)["findings"]
                self.assertEqual(findings["party_manager_holder_candidate_runtime_observed"], observed)
                self.assertFalse(findings["party_manager_handle_nonzero_observed"])
                self.assertFalse(findings["party_manager_object_binding_proven"])

    def test_inconsistent_holder_record_is_rejected(self) -> None:
        for target, raw, address in [
            ("0x2", "0100000000000000", "0x7FF63038ED10"),
            ("0x1", "01000000", "0x7FF63038ED10"),
            ("0x1", "nil", "0x7FF63038ED10"),
            ("nil", "0100000000000000", "0x7FF63038ED10"),
            ("0x1", "0100000000000000", "0x7FF63038ED18"),
        ]:
            with self.subTest(target=target, raw=raw, address=address):
                with self.assertRaisesRegex(ValueError, "Party manager holder"):
                    self.parse_holder_record(target, raw, address)


if __name__ == "__main__":
    unittest.main()
