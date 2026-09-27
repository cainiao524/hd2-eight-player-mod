"""Read-only CFG/dataflow pins for the saved EXE 0x8CCFA0 object factory.

Reads two already-saved JSON captures. It never opens the game process.
"""

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

import capstone
from capstone.x86 import X86_OP_IMM

NEW_CAPTURE_SHA = "157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a"
PRIOR_CAPTURE_SHA = "a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f"
ENTRY = 0x8CCFA0
END_EXCLUSIVE = 0x8CD28E

PINS = {
    "inputs_and_three_virtual_allocations": [
        0x8CCFBF, 0x8CCFC6, 0x8CCFC9, 0x8CCFCE,
        0x8CCFDC, 0x8CCFE0, 0x8CCFF7, 0x8CD001,
        0x8CD00C, 0x8CD017, 0x8CD01A, 0x8CD032,
        0x8CD03F, 0x8CD043, 0x8CD046, 0x8CD04F,
        0x8CD059, 0x8CD064,
    ],
    "inner_object_and_return_wrapper": [
        0x8CD06A, 0x8CD071, 0x8CD07E, 0x8CD091,
        0x8CD098, 0x8CD1CC, 0x8CD214, 0x8CD21C,
    ],
    "owner_pointer_vector": [
        0x8CD221, 0x8CD225, 0x8CD229, 0x8CD22C,
        0x8CD22E, 0x8CD232, 0x8CD23B, 0x8CD241,
        0x8CD248, 0x8CD24A, 0x8CD24E, 0x8CD253,
        0x8CD257, 0x8CD25F, 0x8CD261, 0x8CD265,
        0x8CD279, 0x8CD27D, 0x8CD28D,
    ],
}

CALLER_PINS = [
    0x8C67AD, 0x8C67B2, 0x8C67B4, 0x8C67B7,
    0x8C67BB, 0x8C67BE, 0x8C67C2,
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def insist(condition, message):
    if not condition:
        raise ValueError(message)


def load_verified(path, expected):
    raw = path.read_bytes()
    insist(digest(raw) == expected, f"saved capture fingerprint mismatch: {path}")
    return json.loads(raw)


def instruction_row(ins):
    return {
        "rva": hex(ins.address), "bytes": ins.bytes.hex(),
        "sha256": digest(ins.bytes),
        "asm": ins.mnemonic + (" " + ins.op_str if ins.op_str else ""),
    }


def one(md, blob, base, address):
    offset = address - base
    insist(0 <= offset < len(blob), f"decode outside saved range: {address:#x}")
    ins = next(md.disasm(blob[offset:offset + 15], address, count=1), None)
    insist(ins is not None, f"could not decode {address:#x}")
    return ins


def reachable_cfg(md, blob):
    pending = deque([ENTRY])
    reached = {}
    branch_edges = []
    calls = []
    returns = []
    while pending:
        address = pending.popleft()
        if address in reached:
            continue
        insist(ENTRY <= address < END_EXCLUSIVE,
               f"function edge leaves established prefix: {address:#x}")
        ins = one(md, blob, ENTRY, address)
        insist(ins.address + ins.size <= END_EXCLUSIVE,
               f"instruction crosses inferred boundary: {address:#x}")
        reached[address] = ins
        next_address = address + ins.size
        if ins.group(capstone.CS_GRP_RET):
            returns.append(address)
            continue
        if ins.group(capstone.CS_GRP_CALL):
            target = (hex(ins.operands[0].imm)
                      if ins.operands[0].type == X86_OP_IMM else ins.op_str)
            calls.append({**instruction_row(ins), "target": target,
                          "followed": False})
            pending.append(next_address)
            continue
        if ins.group(capstone.CS_GRP_JUMP):
            insist(ins.operands[0].type == X86_OP_IMM,
                   f"unresolved indirect jump: {address:#x}")
            target = ins.operands[0].imm
            if ins.mnemonic == "jmp":
                successors = [target]
            else:
                successors = [target, next_address]
            branch_edges.append({**instruction_row(ins),
                                 "successors": [hex(x) for x in successors]})
            pending.extend(successors)
            continue
        pending.append(next_address)
    insist(returns == [0x8CD28D], f"unexpected return set: {returns}")
    insist(len(reached) == 188, f"unexpected reachable count: {len(reached)}")
    insist(all(ENTRY <= int(s, 16) < END_EXCLUSIVE
               for x in branch_edges for s in x["successors"]),
           "branch escaped inferred function interval")
    return reached, branch_edges, calls, returns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--saved", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    insist(not args.output.exists(), "refusing overwrite")

    saved = load_verified(args.saved, NEW_CAPTURE_SHA)
    prior = load_verified(args.prior, PRIOR_CAPTURE_SHA)
    row = next(x for x in saved["ranges"] if x["rva"] == hex(ENTRY))
    blob = bytes.fromhex(row["bytes"])
    insist(len(blob) == row["size"] == 4096, "wrong bounded prefix size")
    insist(digest(blob) == row["sha256"] == row["reread_sha256"],
           "saved prefix/reread mismatch")
    insist(row["unchanged_on_reread"], "reread was not unchanged")

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    reached, branches, calls, returns = reachable_cfg(md, blob)
    insist(blob[END_EXCLUSIVE - ENTRY] == 0xCC,
           "missing padding after inferred return boundary")
    pins = {}
    for group, addresses in PINS.items():
        insist(all(x in reached for x in addresses),
               f"pin outside reachable CFG: {group}")
        pins[group] = [instruction_row(reached[x]) for x in addresses]

    table = next(x for x in prior["tables"] if x["root_offset"] == "0xf8")
    caller = next(x for x in table["functions"] if x["slot"] == "0xa0")
    insist(caller["module_rva"] == "0x8c6730", "caller entry changed")
    prior_blob = bytes.fromhex(caller["bytes"])
    insist(digest(prior_blob) == caller["sha256"], "caller prefix mismatch")
    caller_ins = {ins.address: ins for ins in md.disasm(prior_blob, 0x8C6730)}
    insist(all(x in caller_ins for x in CALLER_PINS),
           "caller pin not a sequentially decoded boundary")
    caller_pins = [instruction_row(caller_ins[x]) for x in CALLER_PINS]

    result = {
        "saved_file_sha256": NEW_CAPTURE_SHA,
        "prior_caller_file_sha256": PRIOR_CAPTURE_SHA,
        "build": saved["build"],
        "exe_sha256": saved["pinned_images"]["helldivers2.exe"]["sha256"],
        "reread_unchanged": row["unchanged_on_reread"],
        "entry": hex(ENTRY),
        "saved_range_size": len(blob),
        "saved_range_sha256": digest(blob),
        "inferred_function_end_exclusive": hex(END_EXCLUSIVE),
        "inferred_boundary_basis": "reachable ret at 0x8cd28d, then int3 padding; no runtime unwind boundary captured",
        "reachable_instruction_count": len(reached),
        "direct_branch_edges": branches,
        "calls_not_followed": calls,
        "returns": [hex(x) for x in returns],
        "factory_pins": pins,
        "caller_pins": caller_pins,
        "limits": [
            "CFG follows only instructions reachable from saved 0x8ccfa0 and local direct branch edges. It records but does not follow call targets or exception edges.",
            "The 4096-byte saved range is a bounded prefix that includes following code; the function end is inferred from reachable ret plus padding, not a captured unwind record.",
            "The function builds and appends an object to an owner pointer vector. The first caller integer is stored in wrapper +0x20 and forwarded to 0x8e1370; its business meaning remains unknown.",
            "Virtual slot +0x30 calls and other direct callees were not resolved to service APIs; no backend capacity claim follows.",
            "Reread equality does not make the capture atomic or establish runtime multiplayer behavior.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
