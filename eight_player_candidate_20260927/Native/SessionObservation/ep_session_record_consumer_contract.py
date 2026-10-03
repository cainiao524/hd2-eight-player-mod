"""Fail-closed static cross-reference contract for GameSession opaque records.

This module consumes only committed, saved disassembly/replay JSON.  It does not
open a game process, call a captured target, follow runtime pointers, write
memory, or assign an opaque token/ordinal to PeerId or player-index semantics.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SESSION_SOURCE = ROOT / "five_player_feasibility_20260927" / "live_engine_session_vtable_20261003.json"
PROTOCOL_SOURCE = ROOT / "five_player_feasibility_20260927" / "protocol_slot_consumers.json"
JOIN_SOURCE = ROOT / "five_player_feasibility_20260927" / "join_handler_followup.json"
BUILD = 25480438
MODULE = "helldivers2.exe"
SESSION_TARGET_RVAS = {
    "0x292be0", "0x292bf0", "0x292c20", "0x292cc0",
}
EXPECTED = {
    "0x292be0": ("8b8138010000", "mov eax, dword ptr [rcx + 0x138]"),
    "0x292bf2": ("488d1440", "lea rdx, [rax + rax*2]"),
    "0x292bf6": ("488b8140010000", "mov rax, qword ptr [rcx + 0x140]"),
    "0x292bfd": ("4803d2", "add rdx, rdx"),
    "0x292c00": ("488b04d0", "mov rax, qword ptr [rax + rdx*8]"),
    "0x292c4a": ("4d3914d1", "cmp qword ptr [r9 + rdx*8], r10"),
    "0x292cf7": ("4b3914c2", "cmp qword ptr [r10 + r8*8], rdx"),
    "0x292d07": ("430fb644c229", "movzx eax, byte ptr [r10 + r8*8 + 0x29]"),
    "0x292d20": ("0fb644d029", "movzx eax, byte ptr [rax + rdx*8 + 0x29]"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def instruction_map(doc: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for item in doc.get("rows", []):
        for ins in item.get("instructions", []):
            rva = str(ins.get("rva", "")).lower()
            if not rva:
                continue
            previous = rows.get(rva)
            if previous is not None:
                require(
                    (previous.get("bytes"), previous.get("asm"))
                    == (ins.get("bytes"), ins.get("asm")),
                    f"conflicting duplicate instruction {rva}",
                )
            else:
                rows[rva] = ins
    return rows


def _file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def recover() -> dict:
    session = _json(SESSION_SOURCE)
    require(session.get("build") == BUILD, "session evidence build drift")
    require(session.get("calls_made") is False, "saved session evidence records a call")
    require(session.get("writes_made") is False, "saved session evidence records a write")
    rows = instruction_map(session)
    found: dict[str, dict] = {}
    for rva, (expected_bytes, expected_asm) in EXPECTED.items():
        row = rows.get(rva)
        require(row is not None, f"missing record consumer instruction {rva}")
        require(str(row.get("bytes", "")).lower() == expected_bytes, f"bytes drift at {rva}")
        require(str(row.get("asm", "")).lower() == expected_asm, f"asm drift at {rva}")
        found[rva] = row

    protocol = _json(PROTOCOL_SOURCE)
    join = _json(JOIN_SOURCE)
    require("0x108d9f0" in {str(root.get("root", "")).lower() for root in protocol.get("roots", [])},
            "protocol slot evidence lost game-session log root")
    root = next(root for root in protocol["roots"] if str(root.get("root", "")).lower() == "0x108d9f0")
    strings = [str(item.get("text", "")) for item in root.get("strings", [])]
    require(any("game session with player index" in text.lower() for text in strings),
            "protocol game-session/player-index log evidence missing")
    layout = join.get("host_peer_layout", {})
    entry_array = str(layout.get("entry_array", ""))
    index_bytes = str(layout.get("index_bytes", ""))
    require("four entries" in entry_array.lower(), "join host peer bound evidence drift")
    require("four bytes" in index_bytes.lower(), "join index bound evidence drift")

    # Search only the selected saved protocol/join artifacts for direct textual
    # references to the helldivers2.exe targets.  Absence in this bounded set is
    # not a whole-image xref proof and is reported with that limitation.
    selected_text = _file_text(PROTOCOL_SOURCE) + "\n" + _file_text(JOIN_SOURCE)
    direct_hits = sorted(rva for rva in SESSION_TARGET_RVAS if rva in selected_text)
    require(not direct_hits, "unexpected direct session target reference in selected game.dll evidence")

    instruction_rows = {
        rva: {"rva": rva, "bytes": row["bytes"], "asm": row["asm"]}
        for rva, row in found.items()
    }
    consumers = [
        {
            "kind": "session_count_read",
            "slot": "0x70",
            "rvas": ["0x292be0"],
            "field": "session + 0x138",
            "width": 4,
            "semantic_name": "opaque_count_field",
        },
        {
            "kind": "indexed_record_pointer_read",
            "slot": "0x78",
            "rvas": ["0x292bf2", "0x292bf6", "0x292bfd", "0x292c00"],
            "formula": "record = session[+0x140] + index * 0x30",
            "field": "record pointer table entry",
            "semantic_name": "opaque_record_pointer",
            "bound_requirement": "caller must establish 0 <= index < session[+0x138]",
        },
        {
            "kind": "identity_token_compare",
            "slot": "0x88",
            "rvas": ["0x292c4a"],
            "field": "record + 0x00",
            "comparison": "record qword compared with session + 0x20",
            "semantic_name": "opaque_identity_token",
        },
        {
            "kind": "identity_token_compare_and_byte_read",
            "slot": "0x98 adjacent helper region",
            "rvas": ["0x292cf7", "0x292d07"],
            "field": "record + 0x00, then record + 0x29",
            "semantic_name": "opaque_token_then_observed_byte_29",
            "bound_requirement": "loop uses session count; indexed byte path requires external bound",
        },
        {
            "kind": "indexed_byte_read",
            "slot": "0x98 adjacent helper region",
            "rvas": ["0x292d20"],
            "formula": "byte = session[+0x140][index * 0x30] + 0x29",
            "field": "record + 0x29",
            "semantic_name": "opaque_observed_byte_29",
            "bound_requirement": "caller must establish 0 <= index < session[+0x138]",
        },
    ]
    return {
        "schema": "hd2_game_session_opaque_record_consumer_xref_v1",
        "status": "static_record_consumer_xref_only",
        "build": BUILD,
        "module": MODULE,
        "sources": {
            "session_vtable": {
                "path": str(SESSION_SOURCE.relative_to(ROOT)),
                "sha256": sha256(SESSION_SOURCE),
                "captured_calls": session.get("calls_made"),
                "captured_writes": session.get("writes_made"),
            },
            "protocol_slot_consumers": {
                "path": str(PROTOCOL_SOURCE.relative_to(ROOT)),
                "sha256": sha256(PROTOCOL_SOURCE),
                "scope": protocol.get("scope"),
            },
            "join_handler": {
                "path": str(JOIN_SOURCE.relative_to(ROOT)),
                "sha256": sha256(JOIN_SOURCE),
                "scope": join.get("scope"),
            },
        },
        "record_layout": {
            "table_field": "session + 0x140",
            "count_field": "session + 0x138",
            "stride": "0x30",
            "token_field": "record + 0x00",
            "observed_byte_field": "record + 0x29",
            "self_key_field": "session + 0x20",
            "owner_field": "session + 0x130 (opaque; not interpreted)",
        },
        "consumer_sites": consumers,
        "instruction_evidence": instruction_rows,
        "join_context": {
            "protocol_log": "0x108ddd0: Adding %llx to game session with player index %u",
            "host_peer_storage": "selected join evidence describes a four-entry game.dll host array at host+0x20 + 0x38*i",
            "host_index_storage": "selected join evidence describes four bytes at host+0x100..+0x103",
            "direct_session_target_rvas_in_selected_protocol_join_text": direct_hits,
            "interpretation": "These game.dll records and the helldivers2.exe session record table are kept as separate evidence domains; no alias or call binding is proven.",
        },
        "semantic_limits": {
            "identity_token_is_peer_id": False,
            "identity_token_is_member_id": False,
            "identity_token_is_player_index": False,
            "record_ordinal_is_player_slot": False,
            "observed_byte_29_is_network_state": False,
            "session_owner_is_host": False,
            "protocol_join_calls_session_consumer": False,
            "whole_image_xrefs_exhausted": False,
        },
        "safety": {
            "process_started_in_this_run": False,
            "process_accessed_in_this_run": False,
            "function_calls_made": False,
            "memory_writes": False,
            "hooks_installed": False,
            "injection": False,
            "production_executable": False,
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
        "blockers": [
            "the indexed getter and byte getter have no visible bound check; callers must prove count and lifetime",
            "saved session methods expose opaque token and byte relationships only",
            "selected protocol/join evidence has no direct xref to the session target RVAs and cannot bind the two modules",
            "no constructor, mutation, destruction, callback, or client replication consumer is statically bound",
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
    print(json.dumps({"status": result["status"], "consumer_sites": len(result["consumer_sites"]), "installable": False}))


if __name__ == "__main__":
    main()
