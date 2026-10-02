"""Verify the fixed-build confirmed-peer receive binding boundary.

This is an offline, fail-closed verifier.  It validates the saved code-level
pairing among sender hash, receive wrapper and client insert.  It deliberately
refuses to produce an installable patch because the hash-to-receiver runtime
registry and its writable owner/cleanup ABI are not present in the capture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CAPTURE = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
HASH_VALUE = "0x4804fcf4"
RECEIVER = "0xbaba80"
INSERT = "0xb90b20"
SENDER = "0xbe4910"
DISPATCHER = "0xbde430"


def load(root: Path, name: str):
    return json.loads((root / name).read_text(encoding="utf-8"))


def body_sha(obj: dict) -> str:
    return hashlib.sha256(b"".join(bytes.fromhex(x["bytes"]) for x in obj["instructions"])).hexdigest()


def check(checks: list[dict], name: str, ok: bool, detail: str):
    checks.append({"name": name, "passed": bool(ok), "detail": detail})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("five_player_feasibility_20260927"))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    checks: list[dict] = []
    receiver = load(root, "protocol_client_dispatch_alt.json")
    receiver_xrefs = load(root, "protocol_client_dispatch_xrefs.json")
    insert_disasm = load(root, "protocol_b90b20_disasm.json")
    insert_body = load(root, "protocol_b90b20_body.json")
    sender = load(root, "protocol_confirmed_peer_sender.json")
    host_dispatch = load(root, "protocol_host_to_client_dispatch.json")
    table = load(root, "rpc_binding_callback_table.json")
    hashes = load(root, "rpc_binding_hash_occurrences.json")
    dispatcher = load(root, "live_dispatcher_data_20261002_6.json")
    live_edges = load(root, "live_native_call_edges_20261002.json")

    identities = [obj.get("capture_sha256") for obj in (receiver_xrefs, table, hashes)]
    check(checks, "capture_identity_consistent", all(x == CAPTURE for x in identities), str(identities))
    check(checks, "fixed_game_dll_identity", dispatcher.get("pinned_images", {}).get("game.dll", {}).get("sha256") == "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e", str(dispatcher.get("pinned_images", {}).get("game.dll", {}).get("sha256")))

    check(checks, "receiver_range", receiver.get("range") == [RECEIVER, "0xbabab9"], str(receiver.get("range")))
    check(checks, "receiver_body_sha", body_sha(receiver) == receiver.get("sha256"), body_sha(receiver))
    check(checks, "receiver_calls_insert", any(i.get("asm") == f"call {INSERT}" for i in receiver["instructions"]), "receiver call edge")
    check(checks, "receiver_decodes_five_fields", [i["rva"] for i in receiver["instructions"] if i.get("rva") in {"0xbaba84", "0xbaba88", "0xbaba8c", "0xbaba90", "0xbaba94", "0xbaba97", "0xbaba9b", "0xbaba9e", "0xbabaa5", "0xbabaa8", "0xbabaab"}] == ["0xbaba84", "0xbaba88", "0xbaba8c", "0xbaba90", "0xbaba94", "0xbaba97", "0xbaba9b", "0xbaba9e", "0xbabaa5", "0xbabaa8", "0xbabaab"], "descriptor offsets +8/+18/+28/+38/+48")

    check(checks, "insert_prologue_body_contiguous", insert_disasm["range"][0] == "0xb90b20" and insert_body["range"][0] == "0xb90b59", str((insert_disasm["range"], insert_body["range"])))
    check(checks, "insert_stores_fifth_argument_at_record_14", any(i.get("rva") == "0xb90c12" and "[rdx + 0x14]" in i.get("asm", "") for i in insert_body["instructions"]), "record+0x14")
    check(checks, "insert_has_no_index_clamp_before_store", not any(i.get("rva") in {"0xb90c0b", "0xb90c12"} and "cmp" in i.get("asm", "") for i in insert_body["instructions"]), "no cmp/mask at fifth-argument store")

    sender_hash = next((i for i in sender["instructions"] if i.get("rva") == "0xbe4981"), None)
    check(checks, "sender_embeds_confirmed_peer_hash", bool(sender_hash and sender_hash.get("asm") == f"mov ecx, {HASH_VALUE}"), str(sender_hash))
    host_call = next((i for i in host_dispatch["instructions"] if i.get("rva") == "0x108c960"), None)
    check(checks, "host_direct_insert_call", bool(host_call and host_call.get("asm") == f"call {INSERT}"), str(host_call))
    check(checks, "receiver_xref_is_real_direct_call", any(x.get("rva") == "0xbabaaf" and x.get("asm") == f"call {INSERT}" for x in receiver_xrefs["targets"][INSERT]["branches"]), "receiver->insert")

    check(checks, "static_pointer_run_contains_receiver", table.get("target") == RECEIVER and table.get("target_entry_indices") == [168], str((table.get("target"), table.get("target_entry_indices"))))
    check(checks, "hash_scan_only_sender_immediate", len(hashes.get("hits", [])) == 1 and hashes["hits"][0].get("rva") == "0xbe4982", str(hashes.get("hits")))
    check(checks, "live_image_matches_fixed_build", dispatcher.get("build") == 25480438 and dispatcher.get("pinned_images", {}).get("game.dll", {}).get("sha256") == "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e", str(dispatcher.get("build")))
    check(checks, "live_edges_include_receiver_call", any(x.get("target", {}).get("rva") == RECEIVER for x in live_edges.get("calls", [])) is False, "no direct E8 caller to receiver was reported; receiver is table-dispatched")

    # These are intentionally blocking gates, not failed static checks.
    blocking = [
        {"gate": "hash_to_receiver_runtime_registry", "status": "unresolved", "reason": "captured callback pointer run has no per-entry hashes and no writable dispatch registry"},
        {"gate": "receive_dispatcher_abi", "status": "unresolved", "reason": "0xBDE430 is a send-side generic dispatcher; receiver-side lookup and argument owner are not captured"},
        {"gate": "owner_storage_and_cleanup_abi", "status": "unresolved", "reason": "client +0xD0 inline four-record storage collides at +0x150; relocation aliases, cleanup and unwind are incomplete"},
        {"gate": "installable_patch", "status": "rejected", "reason": "fail-closed until all previous gates are closed"},
    ]
    static_ok = all(x["passed"] for x in checks)
    out = {
        "schema": "hd2_receiver_binding_boundary_verification_v1",
        "build": 25480438,
        "capture_identity_sha256": CAPTURE,
        "static_boundary": "passed" if static_ok else "failed",
        "production_gate": "blocked_receiver_registry_unresolved",
        "installable": False,
        "runtime_invoked": False,
        "game_memory_written": False,
        "multiplayer_verified": False,
        "checks": checks,
        "blocking_gates": blocking,
        "evidence": {
            "hash": HASH_VALUE,
            "receiver": RECEIVER,
            "insert": INSERT,
            "sender": SENDER,
            "generic_send_dispatcher": DISPATCHER,
            "receiver_pointer_run_index": 168,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "static_boundary": out["static_boundary"], "production_gate": out["production_gate"], "installable": out["installable"]}, ensure_ascii=False))
    return 0 if static_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

