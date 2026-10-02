"""Build a read-only ABI inventory for the live confirmed-peer sender.

The source capture is produced by an explicitly authorised fixed-site reader.
This module only decodes bytes and emits fail-closed admission requirements;
it never writes or calls the game process.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import capstone  # type: ignore


ROOT = Path(__file__).resolve().parents[3]
CAPTURE = ROOT / "five_player_feasibility_20260927" / "native_admission_confirmed_peer_live_20261002_r3.json"
ENTRY = 0x108C760
BODY_END = 0x108CD7C
BODY_SIZE = BODY_END - ENTRY
BODY_SHA256 = "633d40a8f3815a1451064a62260f6657524ff5159d5b0c48e803ee883a150f4d"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _row(name: str) -> dict:
    doc = json.loads(CAPTURE.read_text(encoding="utf-8"))
    rvas = {
        "host_confirmed_peer_sender": "0x108c760",
        "host_capacity_gate": "0x108c18f",
        "host_index_allocator": "0x108c3d8",
        "client_confirmed_peer_insert": "0xb90b20",
    }
    rows = [row for row in doc["rows"] if row.get("rva") == rvas[name]]
    require(len(rows) == 1, f"missing live row {name}")
    return rows[0]


def _decode(raw: bytes, base: int) -> list[capstone.CsInsn]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    return list(md.disasm(raw, base))


def _instruction_rows(instructions: list[capstone.CsInsn]) -> list[dict]:
    return [{"rva": hex(i.address), "bytes": bytes(i.bytes).hex(), "sha256": sha256(bytes(i.bytes)), "asm": f"{i.mnemonic} {i.op_str}".rstrip()} for i in instructions]


def recover() -> dict:
    source = json.loads(CAPTURE.read_text(encoding="utf-8"))
    sender_row = _row("host_confirmed_peer_sender")
    sender_raw = bytes.fromhex(sender_row["bytes"])
    require(len(sender_raw) >= BODY_SIZE, "live sender row is too short")
    body = sender_raw[:BODY_SIZE]
    require(sha256(body) == BODY_SHA256, "sender body changed")
    instructions = _decode(body, ENTRY)
    require(sum(i.size for i in instructions) == BODY_SIZE, "sender instruction coverage changed")
    require(instructions[-1].mnemonic == "ret", "sender body does not end in ret")

    direct_calls = []
    indirect_calls = []
    branches = []
    for i in instructions:
        if i.mnemonic in {"call", "jmp", "ja", "jae", "jb", "jbe", "je", "jne", "jz", "jnz", "jle", "jg", "jge", "jl", "jlt", "js", "jns"}:
            target = None
            if i.op_str.startswith("0x"):
                target = int(i.op_str, 16)
            row = {"rva": hex(i.address), "mnemonic": i.mnemonic, "target": hex(target) if target is not None else None}
            branches.append(row)
            if i.mnemonic == "call":
                (direct_calls if target is not None else indirect_calls).append(row)

    semantic_sites = [
        {"rva": "0x108c7eb", "asm": "cmp eax, 4", "class": "confirmed_peer_table_capacity", "confidence": "high", "semantic": "searches session+0x20 entries of stride 0x38 and rejects a peer after four entries", "eight_change": "must change to 8 together with allocation, removal, migration and cleanup of session+0x20 table", "independent": False},
        {"rva": "0x108c81a", "asm": "cmp eax, 3", "class": "confirmed_peer_ordinal_gate", "confidence": "high", "semantic": "after decrement, accepts ordinal values 1..4 only", "eight_change": "must change to 7 only when ordinal/resource maps and all readers accept 1..8", "independent": False},
        {"rva": "0x108c8e7", "asm": "mov r12d, 4", "class": "confirmed_peer_send_loop", "confidence": "high", "semantic": "sends exactly four records from session+0x40 with stride 0x38", "eight_change": "must change to 8 with an expanded table and matching sender/cleanup ownership", "independent": False},
        {"rva": "0x108c9bc", "asm": "lea esi, [rdi + 4]", "class": "side_event_loop_count", "confidence": "high", "semantic": "initialises a four-iteration loop over root+0x16418 entries spaced 0x10", "eight_change": "must change loop bound and backing event table together", "independent": False},
        {"rva": "0x108c878", "asm": "mov dword ptr [rcx + 0x20], 4", "class": "state_enum", "confidence": "high", "semantic": "writes state value 4 for a special transport mode", "eight_change": "preserve enum; never replace with 8", "independent": False},
        {"rva": "0x108ca2d", "asm": "mov dword ptr [rbp - 0x54], 4", "class": "event_field", "confidence": "medium", "semantic": "temporary event record field passed to bde430", "eight_change": "ABI unresolved; preserve until event schema is recovered", "independent": False},
        {"rva": "0x108ca3b", "asm": "mov dword ptr [rbp - 0x44], 4", "class": "event_field", "confidence": "medium", "semantic": "temporary event record field passed to bde430", "eight_change": "ABI unresolved; preserve until event schema is recovered", "independent": False},
        {"rva": "0x108cbad", "asm": "mov dword ptr [rbp - 0x64], 4", "class": "event_field", "confidence": "medium", "semantic": "temporary event record field in final host update message", "eight_change": "ABI unresolved; preserve until event schema is recovered", "independent": False},
    ]
    return {
        "schema": "confirmed_peer_admission_live_abi_v1",
        "status": "static_live_abi_blocker",
        "steam_build": source["build"],
        "capture": {"path": str(CAPTURE.relative_to(ROOT)), "pid": source["pid"], "game_base": source["game_base"], "source_row_sha256": sender_row["sha256"], "read_only": True, "calls_made": False, "writes_made": False},
        "function": {
            "name": "host_confirmed_peer_sender",
            "entry_rva": hex(ENTRY),
            "end_exclusive": hex(BODY_END),
            "body_bytes": BODY_SIZE,
            "body_sha256": BODY_SHA256,
            "prologue": _instruction_rows(instructions[:12]),
            "epilogue": _instruction_rows(instructions[-12:]),
            "instructions": _instruction_rows(instructions),
        },
        "abi": {
            "input": {"RCX": "host/session state", "RDX": "peer or platform member handle", "R8": "join/transport context", "R9": "auxiliary value retained by caller contract"},
            "saved_nonvolatile": ["RBX", "RBP", "R13", "R14"],
            "stack_frame": "sub rsp, 0x188; security cookie at rbp+0x60",
            "return": "void-like; callers do not rely on EAX",
            "records": {"confirmed_peer_table": "session+0x20, stride 0x38, original search bound 4", "send_table": "session+0x40, stride 0x38, original send loop 4", "side_event_table": "root+0x16418, stride 0x10, original loop 4"},
            "writes": ["matched_record+0x10", "matched_record+0x20", "matched_record+0x28", "event/message temporary records"],
            "direct_calls": direct_calls,
            "indirect_calls": indirect_calls,
        },
        "semantic_sites": semantic_sites,
        "sidecar_plan": {
            "owner_key": "exact RCX host/session pointer; never peer handle or ordinal",
            "required_storage": "8 confirmed-peer records of 0x38 bytes plus 8 send records and 8 side-event records, or explicit sidecar pointers with equivalent lifetime",
            "required_redirects": ["lookup bound 4 at 0x108c7eb", "ordinal bound 3 at 0x108c81a", "send count 4 at 0x108c8e7", "side-event bound 4 at 0x108c9bc", "all producer/remove/migration/cleanup loops using the same tables"],
            "required_abi": ["host/session owner retain and release", "peer record allocation and duplicate rejection", "ordinal-to-resource mapping 1..8", "host migration and departure cleanup", "event serializer capacity and receiver compatibility", "x64 unwind/reentrancy proof"],
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "blockers": [
            "The sender's four-slot tables are embedded in a host/session object; no writable heap or owner allocation capture is available.",
            "Changing the four bound or ordinal comparison alone would index past the existing session+0x20/session+0x40 tables.",
            "The sender calls transport/event serializers and a client-side confirmed-peer insert path whose receiver capacity and cleanup ABI are not proven for 8.",
            "Host capacity gate and index allocator independently contain four-slot bounds; admission cannot be widened from this sender alone.",
            "This artifact is read-only static evidence; no process write, injection, hook, or multiplayer verification was performed.",
        ],
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = recover()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "body_bytes": result["function"]["body_bytes"], "semantic_sites": len(result["semantic_sites"]), "installable": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
