"""Offline normal-CFG evidence for the local network-index creation gate.

Uses only the fixed earlier game.dll capture. No live process APIs or game
installation reads. Calls are recorded and treated as returning, not followed.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import sys

import capstone as cs
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row, sha

ENTRY, END = 0x1085D70, 0x108691D
GATE, ACCEPT, FALLBACK = 0x1086469, 0x108646F, 0x108624D
HANDLE_CALL, SETUP_CALL = 0x10868BF, 0x10868D7
STRINGS = {
    0x22631A8: "from_host_added_to_session",
    0x2262B00: "ClientSynchronizer",
    0x22C83E0: "Found history, player is rejoining a previous game. Loadout is overridden with previous data.",
    0x22C7F58: "PlayerHistory",
    0x2263038: "client_rejoin_state",
    0x2263120: "All peers have synced, sending to host that we are ready.",
}
EXTRA_PINS = [0x134D754, 0x134DD07, 0x134DD28, 0x134DD41,
              0x108692A, 0x108692F, 0x1086942, 0x1086946, 0x108694A,
              0x108694D, 0x108696E, 0x1086974, 0x1086978, 0x108697C,
              0x108697F, 0x1086981, 0x1086984, 0x1086987,
              0x515BD9, 0x515BE0, 0x515DE8]


def proven_instructions(im, start, end):
    fragments = [f for f in im.functions if start <= f[0] < end]
    require(fragments and fragments[0][0] == start and fragments[-1][1] == end,
            "Unexpected fragment extent")
    cursor, result = start, {}
    for fragment in fragments:
        a, b, _ = fragment
        require(a == cursor and im.root(a)[0] == start, "Fragment gap or different root")
        decoded = list(im.md.disasm(im.read(a, b - a), a))
        require(decoded and sum(i.size for i in decoded) == b - a,
                "Incomplete fragment decode")
        for instruction in decoded:
            result[instruction.address] = instruction
        cursor = b
    return fragments, result


def graph(instructions):
    adjacency, branches, calls = {}, [], []
    for address, ins in instructions.items():
        following = address + ins.size
        target = ins.operands[0].imm if ins.operands and ins.operands[0].type == X86_OP_IMM else None
        if ins.group(cs.CS_GRP_RET):
            successors = []
        elif ins.group(cs.CS_GRP_JUMP):
            require(target is not None, "Indirect jump in normal join CFG")
            successors = [target] if ins.mnemonic == "jmp" else [target, following]
            branches.append({"site": hex(address), "kind": ins.mnemonic,
                             "target": hex(target), "fallthrough": hex(following) if ins.mnemonic != "jmp" else None})
        else:
            successors = [following]
            if ins.group(cs.CS_GRP_CALL):
                calls.append({"site": hex(address), "target": hex(target) if target is not None else None,
                              "asm": ins.mnemonic + " " + ins.op_str})
        require(all(s in instructions for s in successors), "Normal CFG leaves proven function extent")
        adjacency[address] = successors
    return adjacency, branches, calls


def reach(adjacency, start, removed_edge=None):
    pending, seen = deque([start]), set()
    while pending:
        address = pending.popleft()
        if address in seen:
            continue
        seen.add(address)
        for successor in adjacency[address]:
            if removed_edge != (address, successor):
                pending.append(successor)
    return seen


def pinned(im, address):
    ins = im.instruction(address)
    require(ins is not None, "Unproven extra instruction boundary")
    return {**row(ins), "root": hex(im.root(address)[0]),
            "fragment": [hex(x) for x in im.containing(address)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing overwrite")
    im = Image(args.evidence)
    fragments, instructions = proven_instructions(im, ENTRY, END)
    adjacency, branches, calls = graph(instructions)
    reachable = reach(adjacency, ENTRY)
    fallback = reach(adjacency, FALLBACK)
    accepted = reach(adjacency, ACCEPT)
    no_accept_edge = reach(adjacency, ENTRY, (GATE, ACCEPT))
    require(adjacency[GATE] == [FALLBACK, ACCEPT], "Gate successors changed")
    require(HANDLE_CALL in reachable and SETUP_CALL in reachable, "Creation calls unreachable")
    require(HANDLE_CALL not in no_accept_edge and SETUP_CALL not in no_accept_edge,
            "Unexpected bypass of index acceptance edge")
    require(HANDLE_CALL not in fallback and SETUP_CALL not in fallback,
            "Unexpected fallback creation route")
    require(FALLBACK not in accepted and 0x10863AF in accepted,
            "Accepted path no longer bypasses fallback ring write")
    require(0x108643C in fallback and 0x108643C in accepted,
            "Common ready continuation changed")
    require(sum(c["target"] == "0xfdc140" for c in calls) == 1,
            "Unexpected additional direct entity setup in root")
    formatted = []
    for address, ins in instructions.items():
        formatted.append({**row(ins), "fragment": [hex(x) for x in im.containing(address)],
                          "rip_reference_rvas": [hex(ins.address + ins.size + op.mem.disp)
                              for op in ins.operands if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]})
    ready_start, ready_end = 0x1086B70, 0x1086C71
    ready_fragment = im.containing(ready_start)
    require(ready_fragment[0] == ready_start and ready_fragment[1] == ready_end,
            "Ready helper extent changed")
    ready = [row(i) for i in im.md.disasm(im.read(ready_start, ready_end-ready_start), ready_start)]
    strings = []
    for rva, expected in STRINGS.items():
        raw = im.read(rva, len(expected.encode()) + 1)
        require(raw == expected.encode() + b"\0", "Evidence string changed")
        strings.append({"rva": hex(rva), "bytes": raw.hex(), "sha256": sha(raw), "text": expected})
    result = {
        "capture_sha256": im.report["capture_sha256"], "source_sha256": EXPECTED,
        "function": {"entry": hex(ENTRY), "end_exclusive": hex(END),
                     "bytes_sha256": sha(im.read(ENTRY, END-ENTRY)),
                     "fragments": [[hex(x) for x in f] for f in fragments],
                     "instructions": formatted, "instruction_count": len(instructions),
                     "normal_reachable_count": len(reachable), "branches": branches, "calls": calls},
        "cfg_claims": {
            "gate_site": hex(GATE), "accepted_edge": [hex(GATE), hex(ACCEPT)],
            "fallback_edge": [hex(GATE), hex(FALLBACK)],
            "handle_call_reachable_from_entry": HANDLE_CALL in reachable,
            "handle_call_unreachable_without_accept_edge": HANDLE_CALL not in no_accept_edge,
            "setup_call_unreachable_without_accept_edge": SETUP_CALL not in no_accept_edge,
            "fallback_cannot_reach_handle_or_setup_within_root": not {HANDLE_CALL, SETUP_CALL} & fallback,
            "accepted_path_skips_fallback_ring_write": FALLBACK not in accepted,
            "both_paths_can_reach_ready_helper_call": 0x108643C in accepted & fallback,
            "direct_fdc140_call_count_in_root": sum(c["target"] == "0xfdc140" for c in calls),
        },
        "extra_pins": [pinned(im, a) for a in EXTRA_PINS],
        "ready_helper": {"entry": hex(ready_start), "end_exclusive": hex(ready_end),
                         "bytes_sha256": sha(im.read(ready_start, ready_end-ready_start)), "instructions": ready},
        "strings": strings,
        "runtime_verified": False, "eight_player_verified": False,
        "limits": [
            "CFG covers normal flow from this function's entry; calls are not expanded and are assumed to return.",
            "Exception handlers, arbitrary external entry into the function, and runtime patches are not modeled.",
            "One direct entity setup in this root does not prove no alternative exists elsewhere in the game.",
            "The fallback ring event's eventual consumer and visible presentation are not identified here.",
            "Passing this index gate alone does not resize any native arrays, prove successful entity setup, or verify multiplayer.",
        ],
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"instructions": len(instructions), "fragments": len(fragments),
                      "normal_reachable": len(reachable), "cfg_claims": result["cfg_claims"]}))


if __name__ == "__main__":
    main()
