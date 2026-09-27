"""Pin the full roster four-array mover from the saved offline capture."""
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

ENTRY, END = 0x60C410, 0x60C5BE
BODY_SHA256 = 'b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b'
PRIMARY = [0x60C44B, 0x60C463, 0x60C46B, 0x60C474, 0x60C47C,
           0x60C485, 0x60C48D, 0x60C496, 0x60C49E, 0x60C4A7,
           0x60C4AF, 0x60C4B8, 0x60C4C0, 0x60C4C9]
AUX = [0x60C4D9, 0x60C4E5, 0x60C4ED, 0x60C4F5,
       0x60C4FD, 0x60C505, 0x60C50D, 0x60C516]
PROPERTY = [0x60C51F, 0x60C528, 0x60C531, 0x60C53A]
POINTER = [0x60C438, 0x60C440, 0x60C543]


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    im = Image(args.evidence)
    fragments = [f for f in im.functions if im.root(f[0])[0] == ENTRY]
    require([(a, b) for a, b, _ in fragments] ==
            [(0x60C410, 0x60C454), (0x60C454, 0x60C5BD),
             (0x60C5BD, 0x60C5BE)], 'mover fragments changed')
    raw = im.read(ENTRY, END - ENTRY)
    require(sha(raw) == BODY_SHA256, 'mover body fingerprint changed')
    ins, fragment_rows = [], []
    for a, b, unwind in fragments:
        fragment_raw = im.read(a, b - a)
        part = list(im.md.disasm(fragment_raw, a))
        require(sum(x.size for x in part) == len(fragment_raw),
                'fragment decode incomplete')
        ins.extend(part)
        fragment_rows.append(dict(start=hex(a), end_exclusive=hex(b),
                                  unwind=hex(unwind), sha256=sha(fragment_raw)))
    require(len(ins) == 78 and sum(x.size for x in ins) == len(raw),
            'mover instruction count/coverage changed')
    by_addr = {x.address: x for x in ins}
    require(len(by_addr) == len(ins), 'duplicate instruction boundary')
    edges, branches = {}, []
    for x in ins:
        require(not x.group(cs.CS_GRP_CALL), 'unexpected mover call')
        require(not any(op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP
                        for op in x.operands), 'unexpected mover RIP operand')
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unexpected indirect mover jump')
            successors = [x.operands[0].imm]
            if x.mnemonic != 'jmp':
                successors.append(x.address + x.size)
            branches.append(row(x))
        else:
            successors = [x.address + x.size]
        require(all(target in by_addr for target in successors),
                'mover edge outside captured body')
        edges[x.address] = successors
    require(len(branches) == 5, 'mover internal branch set changed')

    def reach(start, excluded=None):
        pending, seen = [start], set()
        while pending:
            at = pending.pop()
            if at == excluded or at in seen:
                continue
            seen.add(at)
            pending.extend(edges[at])
        return seen

    require(reach(ENTRY) == set(by_addr), 'unexpected unreachable mover instruction')
    require(by_addr[0x60C413].operands[0].imm == 0x60C5BD and
            by_addr[0x60C419].bytes == bytes.fromhex('48895c2420') and
            by_addr[0x60C54A].bytes == bytes.fromhex('448b9bd8000000'),
            'equal path or two splices changed')
    require(all(t not in reach(ENTRY, excluded=0x60C419)
                for t in [0x60C438, 0x60C440, 0x60C543, 0x60C5B7]),
            'entry guard does not dominate writes')
    require(edges[0x60C543] == [0x60C54A] and
            edges[0x60C54A] == [0x60C551],
            'map restore splice predecessors changed')

    def patch_rows(sites, group, delta, expected_base):
        rows = []
        for address in sites:
            x = by_addr[address]
            mem = [op.mem for op in x.operands if op.type == X86_OP_MEM]
            require(len(mem) == 1 and x.disp_size == 4 and
                    x.disp_offset + 4 == x.size,
                    'patch operand is not terminal disp32')
            require(expected_base <= mem[0].disp < expected_base +
                    ({'primary':0x70, 'aux':0x38, 'property':0x20}[group]),
                    'array displacement changed')
            rows.append(dict(rva=hex(address), instruction=row(x), group=group,
                             displacement_offset=x.disp_offset,
                             original_displacement=mem[0].disp,
                             new_displacement=mem[0].disp + delta,
                             delta=delta))
        return rows

    patches = (patch_rows(PRIMARY, 'primary', 0x20, 0x108) +
               patch_rows(AUX, 'aux', 0x1E0, 0x2C8) +
               patch_rows(PROPERTY, 'property', 0x2C0, 0x3A8))
    for address in POINTER:
        x = by_addr[address]
        mem = [op.mem for op in x.operands if op.type == X86_OP_MEM]
        require(len(mem) == 1 and mem[0].disp == 0xE8,
                'pointer-array access changed')
    require(by_addr[0x60C430].op_str == 'r11, [rcx + r14*8]' and
            by_addr[0x60C420].op_str == 'rbx, rcx' and
            by_addr[0x60C557].op_str == 'edi, dword ptr [rax + 8]' and
            by_addr[0x60C5B7].op_str == 'dword ptr [r8 + 4], r14d',
            'base propagation or map update changed')
    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  move=dict(entry=hex(ENTRY), end_exclusive=hex(END),
                            size_bytes=len(raw), sha256=sha(raw),
                            fragments=fragment_rows,
                            instructions=[row(x) for x in ins],
                            cfg={hex(k): list(map(hex, v)) for k, v in edges.items()},
                            branches=branches, external_relocations=[],
                            same_ordinal_return=hex(0x60C5BD),
                            guard_splice=dict(rva=hex(0x60C419),
                                              bytes=by_addr[0x60C419].bytes.hex(),
                                              resume_rva=hex(0x60C41E)),
                            map_restore_splice=dict(rva=hex(0x60C54A),
                                                    bytes=by_addr[0x60C54A].bytes.hex(),
                                                    resume_rva=hex(0x60C551)),
                            pointer_sites=list(map(hex, POINTER)),
                            displacement_patches=patches,
                            layout=dict(pointer_base=0, primary_base=0x40,
                                        aux_base=0x3C0, property_base=0x580,
                                        total_bytes=0x680)),
                  limits=[
                      'Complete captured mover body only; not a global roster alias inventory.',
                      'The original map lookup can fail and then write to address 4; valid map membership is an integration precondition.',
                      'The eight-slot sidecar and all other writers/readers are not allocated or redirected by this replay.',
                      'No game process access, hook, native execution, or multiplayer validation.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), body_sha256=sha(raw),
                          instructions=len(ins), patches=len(patches),
                          branches=len(branches))))


if __name__ == '__main__':
    main()
