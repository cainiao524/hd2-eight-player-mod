"""Decode bounded normal control-flow from the saved second observation only.

No process APIs. Follow in-window direct branches, not call destinations. A RET
ends one path, not all paths. Unknown indirect jumps and missing bytes are listed.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path

import capstone as cs
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

EXPECTED = "157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(record):
    start = int(record["rva"], 16)
    raw = bytes.fromhex(record["bytes"])
    end = start + len(raw)
    md = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_64)
    md.detail = True
    pending = deque([start])
    decoded, covered = {}, {}
    edges, gaps = [], []
    while pending:
        pc = pending.popleft()
        while pc not in decoded:
            if not start <= pc < end:
                gaps.append({"rva": hex(pc), "reason": "outside captured window"})
                break
            require(pc not in covered, "Branch lands inside an already decoded instruction")
            ins = next(md.disasm(raw[pc-start:pc-start+15], pc, count=1), None)
            if ins is None:
                gaps.append({"rva": hex(pc), "reason": "undecodable or truncated instruction"})
                break
            require(not any(a in covered for a in range(pc, pc+ins.size)), "Overlapping decode")
            for address in range(pc, pc+ins.size):
                covered[address] = pc
            following = pc + ins.size
            row = {"rva": hex(pc), "bytes": ins.bytes.hex(), "sha256": sha(ins.bytes),
                   "asm": ins.mnemonic + " " + ins.op_str}
            refs = [hex(following + op.mem.disp) for op in ins.operands
                    if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
            if refs:
                row["rip_reference_rvas"] = refs
            decoded[pc] = row
            immediate = ins.operands[0].imm if ins.operands and ins.operands[0].type == X86_OP_IMM else None
            if ins.group(cs.CS_GRP_RET):
                edges.append({"from": hex(pc), "kind": "return"})
                break
            if ins.mnemonic in ("ud2", "int3", "int", "hlt"):
                edges.append({"from": hex(pc), "kind": "trap; handler flow unmodeled"})
                break
            is_jump = ins.group(cs.CS_GRP_JUMP) or ins.mnemonic in (
                "loop", "loope", "loopne", "jecxz", "jrcxz")
            if is_jump:
                edge = {"from": hex(pc), "kind": "jump" if ins.mnemonic in ("jmp", "ljmp") else "conditional",
                        "target": hex(immediate) if immediate is not None else None}
                edges.append(edge)
                if immediate is None:
                    gaps.append({"rva": hex(pc), "reason": "indirect branch target unresolved"})
                elif start <= immediate < end:
                    pending.append(immediate)
                else:
                    gaps.append({"rva": hex(pc), "target": hex(immediate), "reason": "direct branch leaves window"})
                if edge["kind"] == "jump":
                    break
            elif ins.group(cs.CS_GRP_CALL):
                edges.append({"from": hex(pc), "kind": "call", "target": hex(immediate) if immediate is not None else None})
            pc = following
    return {"entry_rva": hex(start), "window_size": len(raw), "window_sha256": sha(raw),
        "instruction_count": len(decoded), "decoded_bytes": len(covered),
        "instructions": [decoded[a] for a in sorted(decoded)], "edges": edges, "unresolved": gaps,
        "limits": ["Entry is established by a direct call in a previously saved caller.",
            "Normal static paths only; calls, exceptions, handlers, and computed dispatch are not followed.",
            "A captured window is not an independently established function extent.",
            "No runtime invocation or service response is demonstrated."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.capture.read_bytes()
    require(sha(raw) == EXPECTED, "Saved capture fingerprint mismatch")
    capture = json.loads(raw)
    require(capture["all_ranges_unchanged_on_reread"], "Source code changed during capture")
    for row in capture["ranges"]:
        data = bytes.fromhex(row["bytes"])
        require(len(data) == row["size"] == 4096, "Unexpected range size")
        require(sha(data) == row["sha256"] == row["reread_sha256"], "Range integrity mismatch")
    result = {"capture_file_sha256": EXPECTED, "atomic_snapshot": capture["atomic_snapshot"],
              "entries": [decode(row) for row in capture["ranges"]]}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"entries": [{"rva": e["entry_rva"], "instructions": e["instruction_count"],
                                  "unresolved": len(e["unresolved"])} for e in result["entries"]]}))


if __name__ == "__main__":
    main()
