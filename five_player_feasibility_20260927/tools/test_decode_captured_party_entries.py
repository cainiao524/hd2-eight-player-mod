"""Saved-data decoding and emulator-boundary checks; no game access."""
import json
import struct

import pytest

import decode_captured_party_entries_20261016 as decode


@pytest.fixture(scope="module")
def report():
    return decode.analyze()


@pytest.mark.parametrize("label,rva,name", [
    ("create_network_candidate", "0x15720", "PartyCreateNewNetwork"),
    ("async_or_state_candidate", "0x19880", None),
    ("authenticate_or_state_candidate", "0x1be80", None),
    ("create_endpoint_candidate", "0x1c050", "PartyNetworkCreateEndpoint"),
    ("connect_network_candidate", "0x14fe0", "PartyConnectToNetwork"),
    ("auth_network_candidate", "0x1bc80", "PartyNetworkAuthenticateLocalUser"),
])
def test_saved_entries_decode_before_call_with_varied_context(report, label, rva, name):
    row = next(r for r in report["decoded_entries"] if r["candidate_label"] == label)
    assert row["partywin_rva"] == rva
    assert row["matching_saved_export"] == name
    assert len(row["runs"]) == 3
    assert len({r["instruction_path_sha256"] for r in row["runs"]}) == 1
    assert all(r["derived_rax"] == row["derived_target"] for r in row["runs"])
    assert all(r["stopped_before_indirect_call"] for r in row["runs"])
    assert all(r["nonstack_data_reads"] == [{"rva": row["entry_rva"], "size": 8}]
               for r in row["runs"])
    assert not row["actual_native_call_observed"]


def test_common_jump_is_historical_but_destination_not_supplied(report):
    assert report["common_jump"]["entry_rva"] == "0x2c7a94d"
    assert report["common_jump"]["destination_rva"] == "0x2efaf2d"
    assert report["common_jump"]["same_first_jump_in_historical_window"] == "create_network_candidate_d0.bin"
    assert report["common_jump"]["destination_in_recovered_12_windows"] == []
    assert report["unnamed_rvas"] == ["0x19880", "0x1be80"]
    for flag in ("native_game_calls", "new_game_reads", "provider_binding_proven",
                 "runtime_verified", "multiplayer_verified"):
        assert not report[flag]


@pytest.mark.parametrize("label", ["create_network_candidate", "create_endpoint_candidate"])
def test_stack_argument_calls_cannot_assume_dispatcher_is_plain_jump(report, label):
    row = next(r for r in report["decoded_entries"] if r["candidate_label"] == label)
    for run in row["runs"]:
        assert run["four_argument_registers_preserved"]
        assert run["rsp_delta"] == -32
        for arg in run["caller_stack_arguments"]:
            assert arg["original_slot_before_common_call"] == arg["input_marker"]
            assert arg["plain_jump_callee_slot"] != arg["input_marker"]
        fifth = run["caller_stack_arguments"][0]
        assert fifth["original_slot_relative_to_current_rsp"] == "0x48"
        assert fifth["plain_jump_callee_slot"] == run["synthetic_caller_return"]
        assert not run["dispatcher_stack_forwarding_proven"]


def test_changed_source_is_rejected_before_replay(monkeypatch, tmp_path):
    name = next(iter(decode.SOURCES))
    (tmp_path / name).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(decode, "DATA", tmp_path)
    with pytest.raises(ValueError, match="saved source hash mismatch"):
        decode.analyze()


def test_unmapped_padding_cannot_replace_missing_entry_bytes():
    receipt = decode.checked_json("party_capture_authorized_20261016_pid30776_01.json")
    plan = decode.checked_json("party_capture_plan_v2_20261015.json")
    manifest = decode.checked_json("recovered_party_windows_20261015/manifest.json")
    r5 = decode.checked_json("live_party_jump_chains_20261111_pid38492_r5.json")
    entry = receipt["entry_qwords"][0]
    label = entry["label"]
    wrapper = next(w for w in manifest["windows"] if w["label"] == label and w["depth"] == 1)
    helper = next(c for c in r5["chains"] if c["label"] == label)["hops"][-1]["direct_relative_calls"][0]
    raw = (decode.DATA / "recovered_party_windows_20261015" / wrapper["file"]).read_bytes()[:1024]
    with pytest.raises(ValueError, match="unavailable data bytes"):
        decode.replay(int(receipt["exe_base"], 16), int(wrapper["rva"], 16), raw,
                      int(helper["target"], 16) - int(manifest["exe_base"], 16),
                      bytes.fromhex(helper["code"])[:14], int(entry["rva"], 16), b"\0" * 4)


@pytest.mark.parametrize("code,message", [
    (bytes.fromhex("ffd0"), "unexpected indirect call operand"),
    (bytes.fromhex("48b8003000400100000048c70001000000"), "write outside synthetic stack"),
])
def test_unexpected_call_or_image_write_is_not_emulated(code, message):
    with pytest.raises(ValueError, match=message):
        decode.replay(0x140000000, 0x1000, code, 0x2000, b"\xc3", 0x3000, b"\0" * 8)
