"""Pin the complete roster property producer from the existing offline capture.

Reads saved bytes only. It does not contact or modify a game process.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

ENTRY, END = 0x60C640, 0x60C882
BODY_SHA256 = '8b9a20e5207ae395e99e45f153cba1994ff50c10cb258101fd16a74285824c34'
RELOCATIONS = {
    0x60C65E: ('rip_memory', 0x3483C20),
    0x60C667: ('rip_memory', 0x3326468),
    0x60C6DA: ('call_rel32', 0x173B8D0),
    0x60C778: ('call_rel32', 0x134F190),
}
STORES = [0x60C6F2, 0x60C720, 0x60C74C, 0x60C77D,
          0x60C7A7, 0x60C7D3, 0x60C807, 0x60C82F]


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    im = Image(args.evidence)
    root = im.root(0x60C77D)
    require(root[:2] == (ENTRY, END) and im.containing(ENTRY) == root,
            'producer unwind boundary changed')
    raw = im.read(ENTRY, END - ENTRY)
    require(sha(raw) == BODY_SHA256, 'producer body fingerprint changed')
    ins = list(im.md.disasm(raw, ENTRY))
    require(len(ins) == 130 and sum(x.size for x in ins) == len(raw),
            'producer body decode incomplete')
    by_addr = {x.address: x for x in ins}
    require(len(by_addr) == len(ins), 'duplicate producer instruction')

    # Calls are external and return to the next instruction. All jumps are
    # internal to this complete unwind fragment, including the epilogue tail.
    edges = {}
    external = {}
    for x in ins:
        rip_ops = [op for op in x.operands
                   if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
        direct_calls = [op for op in x.operands
                        if x.group(cs.CS_GRP_CALL) and op.type == X86_OP_IMM]
        require(len(rip_ops) <= 1 and len(direct_calls) <= 1,
                'unmodeled external instruction form')
        if x.group(cs.CS_GRP_CALL):
            require(len(direct_calls) == 1, 'unmodeled indirect call')
        if rip_ops:
            external[x.address] = ('rip_memory', x.address + x.size + rip_ops[0].mem.disp)
        if direct_calls:
            external[x.address] = ('call_rel32', direct_calls[0].imm)
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unmodeled indirect jump')
            successors = [x.operands[0].imm]
            if x.mnemonic != 'jmp':
                successors.append(x.address + x.size)
        else:
            successors = [x.address + x.size]
        require(all(target in by_addr for target in successors),
                'branch or fallthrough outside producer body')
        edges[x.address] = successors
    require(external == RELOCATIONS, 'external relocation set changed')

    def reach(start, excluded=None):
        seen, pending = set(), [start]
        while pending:
            at = pending.pop()
            if at == excluded or at in seen:
                continue
            seen.add(at)
            pending.extend(edges[at])
        return seen

    require(reach(ENTRY) == set(by_addr), 'producer has unexpected unreachable code')
    cut, resume = 0x60C6C9, 0x60C6CE
    require(by_addr[cut].bytes == bytes.fromhex('488b4c2468') and
            edges[cut] == [resume], 'five-byte cutpoint changed')
    guarded_targets = [0x60C6DA] + STORES
    for target in guarded_targets:
        require(target not in reach(ENTRY, excluded=cut),
                'allocator or property store bypasses cutpoint')
    require(by_addr[0x60C667].op_str == 'rbp, qword ptr [rip + 0x2d19dfa]' and
            by_addr[0x60C6C4].bytes == bytes.fromhex('bbffffffff') and
            by_addr[0x60C878].bytes == bytes.fromhex('438b5cc304'),
            'roster base / map ordinal dataflow changed')
    require(by_addr[0x60C807].op_str == 'dword ptr [rax + rbp], r15d',
            'seventh property store addressing changed')
    caller = im.instruction(0x540AF9)
    require(caller is not None and caller.mnemonic == 'call' and
            caller.operands[0].type == X86_OP_IMM and
            caller.operands[0].imm == ENTRY, 'wrapper direct call changed')
    relocations = []
    for addr, (kind, target) in RELOCATIONS.items():
        x = by_addr[addr]
        relocations.append(dict(rva=hex(addr), kind=kind, target_rva=hex(target),
                                instruction=row(x), displacement_offset=(
                                    x.disp_offset if kind == 'rip_memory' else x.imm_offset),
                                displacement_size=(
                                    x.disp_size if kind == 'rip_memory' else x.imm_size)))
    require(all(x['displacement_size'] == 4 for x in relocations),
            'external relocation is not rel32')
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  producer=dict(entry=hex(ENTRY), end_exclusive=hex(END),
                                unwind=hex(root[2]), size_bytes=len(raw),
                                sha256=sha(raw), instructions=[row(x) for x in ins],
                                cfg={hex(k): list(map(hex, v)) for k, v in edges.items()},
                                relocations=relocations,
                                wrapper_call=row(caller),
                                splice=dict(rva=hex(cut), bytes=by_addr[cut].bytes.hex(),
                                            resume_rva=hex(resume),
                                            dominates_allocator_and_all_property_stores=True),
                                property_store_rvas=list(map(hex, STORES))),
                  limits=[
                      'Complete unwind-bounded body, not a proof of all indirect callers.',
                      'The guard follows entity ID and roster map reads; bad input pointers are not made safe.',
                      'The body calls an allocator and network-index helper; their runtime lifetimes and outcomes are external preconditions.',
                      'No live process, hook, native execution, or multiplayer validation.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), size_bytes=len(raw),
                          instructions=len(ins), relocations=len(relocations),
                          body_sha256=sha(raw))))


if __name__ == '__main__':
    main()
