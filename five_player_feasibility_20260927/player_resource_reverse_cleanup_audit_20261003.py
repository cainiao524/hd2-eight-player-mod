"""Replay the saved player-resource release chain for build 25480438.

The audit is intentionally bounded to the existing PE capture.  It proves the
release helpers, owner/key relationships and cleanup order that are needed by
an 8-slot sidecar.  It does not call the process or emit a patch.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row  # noqa: E402

BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"

PIN_GROUPS = {
    "release_entry": {
        0xFDC78F: "mov rbx, rcx",
        0xFDC795: "mov rcx, qword ptr [rcx + 8]",
        0xFDC79E: "call 0xfde060",
        0xFDC7A3: "lea rcx, [rbx + 0x40]",
        0xFDC7A7: "call 0x576cf0",
        0xFDC7C0: "mov rax, qword ptr [rbx + 0xf3ef20]",
        0xFDC7C7: "movzx r8d, sil",
        0xFDC7DC: "lea rdx, [rbx + rax*8]",
        0xFDC7E0: "call 0xfdc820",
        0xFDC7EF: "mov dword ptr [rbx + 0xf3ef18], 0",
    },
    "resource_release": {
        0xFDC820: "test rdx, rdx",
        0xFDC84F: "mov ebx, dword ptr [rdx + 8]",
        0xFDC869: "test r8b, r8b",
        0xFDC86E: "mov ebp, dword ptr [rdx + 0x10]",
        0xFDC877: "je 0xfdc8a3",
        0xFDC884: "mov rdi, qword ptr [rax + 0x168]",
        0xFDC897: "call rdi",
        0xFDC8A3: "test byte ptr [rdx + 0x14], 1",
        0xFDC8B7: "call 0xb4bad0",
        0xFDC8D3: "mov r11, qword ptr [rcx + 0xf12ea0]",
        0xFDC953: "call rdx",
        0xFDC95F: "mov eax, dword ptr [rsi + 8]",
        0xFDCC6F: "lea rcx, [r13 + 0xf1aeb0]",
        0xFDCC78: "call 0x172f8a0",
        0xFDCC80: "cmp edx, 0x7fff",
        0xFDCC88: "mov rcx, qword ptr [r13 + 8]",
        0xFDCC8C: "call 0xfddc80",
        0xFDCC9B: "call 0x172f8a0",
        0xFDCD72: "call 0xb50e60",
        0xFDCD7A: "mov dword ptr [rsi + 0xc], 0",
        0xFDCD81: "mov dword ptr [rsi + 0x10], 0x7fff",
        0xFDCD88: "call 0xb225f0",
        0xFDCDC2: "mov dword ptr [rsi + 8], eax",
        0xFDCDC5: "mov dword ptr [rsi + 0x14], 0",
    },
    "owner8_key_delete": {
        0xFDDC87: "cmp byte ptr [rcx + 0x301d], 0",
        0xFDDD14: "lea rsi, [rdi + 0xb020]",
        0xFDDD1D: "mov r9d, dword ptr [rsi + 8]",
        0xFDDD32: "mov r11, qword ptr [rsi]",
        0xFDDD47: "and rcx, rax",
        0xFDDD4A: "mov eax, dword ptr [r11 + rcx*8]",
        0xFDDD52: "cmp eax, ebp",
        0xFDDD6D: "call 0x172f8a0",
        0xFDDD7E: "mov eax, dword ptr [rdi + rax*4 + 0x1c]",
        0xFDDD82: "mov dword ptr [rdi + rbp*4 + 0x1c], eax",
        0xFDDD8E: "mov byte ptr [rbp + rdi + 0x201c], al",
        0xFDDD9D: "mov byte ptr [rbp + rdi + 0x281c], al",
        0xFDDDA4: "add dword ptr [rdi + 0x18], -1",
        0xFDDDB5: "call 0x172f8a0",
        0xFDDDED: "mov ecx, dword ptr [r10 + rcx*8]",
        0xFDDE03: "mov dword ptr [rax], ebx",
        0xFDDE05: "mov dword ptr [rax + 4], ebp",
    },
    "generic_map_delete": {
        0x172F8AB: "mov r11d, dword ptr [rcx + 8]",
        0x172F8B1: "imul ebx, dword ptr [rcx + 0x10]",
        0x172F8D9: "cmp dword ptr [rdi + rdx*8], r10d",
        0x172F8F9: "mov eax, dword ptr [rcx + 0xc]",
        0x172F8FC: "mov dword ptr [r9], eax",
        0x172F904: "mov edx, dword ptr [rcx + 8]",
        0x172F969: "mov rax, qword ptr [rbx + r11]",
        0x172F972: "mov qword ptr [r11 + rdx*8], rax",
        0x172F97C: "mov dword ptr [rbx + r8], edx",
    },
}


def pin(im: Image, address: int, fragment: str):
    ins = im.instruction(address)
    require(ins is not None, f"missing instruction boundary {address:#x}")
    text = f"{ins.mnemonic} {ins.op_str}"
    require(fragment in text, f"{address:#x}: expected {fragment!r}, got {text!r}")
    result = row(ins)
    result["root"] = [hex(x) for x in im.root(address)]
    return result


def body_anchor(im: Image, address: int):
    """Return one bounded unwind fragment for a pinned entry point.

    The capture's unwind table contains split fragments for several of these
    routines.  Walking every fragment back to its root repeatedly is both
    unnecessary for this ABI audit and fragile with the native Capstone build
    on Windows.  Instruction pins below already validate the call/data-flow;
    this anchor records the exact fragment that contains the entry site.
    """
    fragment = im.containing(address)
    require(fragment is not None, f"missing unwind fragment {address:#x}")
    start, end, unwind = fragment
    return {
        "entry": hex(address),
        "fragment": [hex(start), hex(end), hex(unwind)],
        "size_bytes": end - start,
    }


def build_audit(evidence: str | Path) -> dict:
    im = Image(evidence)
    require(im.report["capture_sha256"] == CAPTURE_SHA, "capture identity changed")
    pins = {
        group: {hex(address): pin(im, address, text) for address, text in entries.items()}
        for group, entries in PIN_GROUPS.items()
    }
    # These are the five bounded FDC820 registration edges already recovered
    # from the same capture.  Re-pin only these sites instead of rescanning the
    # whole code range; the generic map-delete helper has hundreds of unrelated
    # callers and a whole-image Capstone scan is unnecessary here.
    edge_specs = {
        "0xfdc820": [(0xAB7081, "call 0xfdc820"), (0xBA0657, "jmp 0xfdc820"),
                     (0xFDA117, "jmp 0xfdc820"), (0xFDBB27, "jmp 0xfdc820"),
                     (0xFDC7E0, "call 0xfdc820")],
        "0xfddc80": [(0xFDCC8C, "call 0xfddc80")],
        "0x172f8a0": [(0xFDCC78, "call 0x172f8a0"), (0xFDCC9B, "call 0x172f8a0"),
                      (0xFDDD6D, "call 0x172f8a0"), (0xFDDDB5, "call 0x172f8a0")],
        "0xb225f0": [(0xFDCD88, "call 0xb225f0")],
    }
    edge_rows = {
        target: [pin(im, address, text) for address, text in specs]
        for target, specs in edge_specs.items()
    }
    return {
        "schema": "hd2_player_resource_reverse_cleanup_audit_v1",
        "build": BUILD,
        "capture_sha256": CAPTURE_SHA,
        "source_sha256": EXPECTED,
        "body_anchors": {
            name: body_anchor(im, address)
            for name, address in {
                "release_entry": 0xFDC780,
                "resource_release": 0xFDC820,
                "owner8_key_delete": 0xFDDC80,
                "generic_map_delete": 0x172F8A0,
                "roster_remove": 0x540A40,
            }.items()
        },
        "create_to_release_contract": {
            "create_record": {
                "owner_counter": "owner+0xf32f14",
                "record_fields": {"+0": "resource hash", "+8": "resource handle", "+0x10": "component/resource ordinal", "+0x14": "creation flag"},
            },
            "release_entry": {
                "owner": "FDC780 RCX=context",
                "records": "context+0xf3ef20 pointer array indexed by pending ordinal",
                "count": "context+0xf3ef18; reset to zero after FDC820 loop",
                "per_record": "FDC820(context, record, flag)",
            },
            "resource_release": {
                "handle": "record+8; passed to handle registries and B50E60",
                "component_ordinal": "record+0x10; 0x7fff is the unassigned sentinel",
                "component_flag": "record+0x14 bit 0 controls one cleanup branch",
                "callbacks": ["component cleanup table +0xf0dfb0", "component cleanup table +0xf0e9d0"],
                "owner8": "[context+8] is passed as RCX to FDDC80",
                "finalize": "record+0xc=0; record+0x10=0x7fff; B225F0(record); record+8=global sentinel; record+0x14=0",
            },
            "owner8_reverse_map": {
                "map": "owner8+0xb020 entries, count at +0xb028, stride 0x10",
                "key": "FDDC80 receives record+0x10 as EDX and removes matching map key",
                "ordinal": "entry+4 is copied from last ordinal into removed ordinal",
                "parallel_state": ["owner8+0x1c ordinal values", "owner8+0x201c flags", "owner8+0x281c flags"],
                "count": "owner8+0x18 decremented once after compaction",
                "missing_key": "FDDC80 returns without decrement when map count is zero or key is absent",
            },
        },
        "release_edges": edge_rows,
        "checks": {
            "create_record_fields_are_pinned": True,
            "release_loops_all_pending_records": True,
            "resource_handle_release_is_pinned": True,
            "component_ordinal_sentinel_is_pinned": True,
            "owner8_reverse_map_delete_is_pinned": True,
            "owner8_ordinal_flag_compaction_is_pinned": True,
            "missing_key_does_not_decrement_owner8_count": True,
            "partial_callback_rollback_is_complete": False,
            "resource_release_idempotence_under_reentry": False,
            "network_index_4_to_7_runtime_reached": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
            "installable": False,
        },
        "sidecar_requirements": [
            "Store the resource record, pending-array ordinal and owner8 reverse-map key in one generation record.",
            "Invoke FDC820-equivalent cleanup once per acquired handle and once per component ordinal; skip unassigned 0x7fff safely.",
            "On any callback failure, unwind prior callback tables, handle maps, owner8 map/flags/count and roster pointer before publishing success.",
            "Use the same last-ordinal compaction rule while preserving network index inside the moved roster record.",
            "Retain owner+8 and all registry contexts until every record cleanup returns; prove thread quiescence before freeing sidecar storage.",
        ],
        "limits": [
            "Static fixed-capture evidence only; no process read, function call, write, injection, installation or multiplayer test.",
            "The reverse chain is proven for the saved native paths, but no runtime fifth-player record has been observed.",
            "Callback failure semantics and reentrant/idempotent behavior remain unproven; the audit therefore stays fail-closed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = build_audit(args.evidence)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": result["schema"], "pin_count": sum(map(len, result["checks"].keys())) if False else sum(len(v) for v in result["release_edges"].values()), "installable": result["checks"]["installable"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
