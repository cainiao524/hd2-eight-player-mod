"""Offline, pinned producer clone plus Windows x64 unwind data.

No game access, executable allocation, hook or function-table registration.
The caller still owns a reviewed interior-frame rejection continuation.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'hellforge_multiplayer'
sys.path.insert(0, str(ROOT / 'eight_player_candidate_20260927/.native-test-deps'))
import capstone
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PROLOGUE = bytes.fromhex('48895c240848896c2410488974241857415641574883ec20')
# Same 24 bytes and final frame, but establish the fixed RSP BEFORE home-slot
# saves. One unwind record can now describe every partial prologue without
# interpreting a save offset against several different intermediate RSPs.
CANONICAL_PROLOGUE = bytes.fromhex('57415641574883ec2048895c244048896c24484889742450')
UNWIND = bytes.fromhex('01180a0018640a00135409000e340800093205f003e00170')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def original(**addresses):
    lock = json.loads((PROJECT / 'native-storage.lock.json').read_bytes())
    require(capstone.__version__ == lock['capstone'], 'Wrong decoder version')
    rel = 'eight_player_candidate_20260927/Native/roster_producer.py'
    path = ROOT / rel
    require(sha(path.read_bytes()) == lock['legacy_source_sha256'][rel], 'Changed legacy emitter')
    spec = importlib.util.spec_from_file_location('pinned_unwind_producer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = module.load_source(ROOT / 'five_player_feasibility_20260927/roster_property_producer_native_evidence.json')
    return module.build(source, **addresses)


def with_unwind(legacy, *, conditional_rejection=True):
    """Accept only a freshly emitted pinned candidate; preserve its normal ABI.

    The old E9 to an external rejection continuation looks like a tail-call
    epilogue to RtlVirtualUnwind, although its frame is still live. Test the
    existing nonzero R10D reason and use JNZ instead. Flags are not preserved
    by the existing rejection ABI; no GPR, stack or data value changes.
    """
    base, reject = legacy['entry_address'], legacy['reject_address']
    code = bytes.fromhex(legacy['code_hex'])
    require(sha(code) == legacy['code_sha256'] and code.startswith(PROLOGUE), 'Changed code/prologue')
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    insns = list(md.disasm(code, base))
    require(sum(i.size for i in insns) == len(code), 'Undecodable candidate')
    replacements = []
    for k, ins in enumerate(insns):
        if ins.mnemonic == 'jmp' and ins.operands[0].type == X86_OP_IMM and ins.operands[0].imm == reject:
            require(bytes(ins.bytes)[0] == 0xE9 and ins.size == 5 and k > 0, 'Unexpected rejection branch')
            previous = insns[k - 1]
            require(bytes(previous.bytes) in (bytes.fromhex('41ba01000000'), bytes.fromhex('41ba02000000')),
                    'Rejection reason must be a nonzero constant in R10D')
            replacements.append(ins.address)
    require(len(replacements) == 2, 'Expected both rejection reasons')

    def moved(address):
        return address + (4 * sum(p < address for p in replacements) if conditional_rejection else 0)

    def target(address):
        return moved(address) if base <= address < base + len(code) else address

    chunks = []
    for ins in insns:
        pc = moved(ins.address)
        if conditional_rejection and ins.address in replacements:
            # test r10d,r10d; jnz reject. Never interpreted as an epilogue.
            delta = reject - (pc + 9)
            require(-(1 << 31) <= delta < (1 << 31), 'Rejection continuation is outside rel32 range')
            blob = b'\x45\x85\xd2\x0f\x85' + struct.pack('<i', delta)
        else:
            blob = bytearray(ins.bytes)
            if ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL):
                if ins.operands[0].type == X86_OP_IMM:
                    delta = target(ins.operands[0].imm) - (pc + ins.size)
                    blob[ins.imm_offset:ins.imm_offset + ins.imm_size] = delta.to_bytes(ins.imm_size, 'little', signed=True)
            for op in ins.operands:
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    delta = target(ins.address + ins.size + op.mem.disp) - (pc + ins.size)
                    blob[ins.disp_offset:ins.disp_offset + ins.disp_size] = delta.to_bytes(ins.disp_size, 'little', signed=True)
        chunks.append(bytes(blob))
    result = b''.join(chunks)
    require(result.startswith(PROLOGUE) and len(CANONICAL_PROLOGUE)==len(PROLOGUE), 'Prologue moved')
    for ins in insns:
        if (ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL)) and ins.operands[0].type==X86_OP_IMM:
            require(not base <= ins.operands[0].imm < base+len(PROLOGUE), 'Unexpected branch into rewritten prologue')
    result = CANONICAL_PROLOGUE + result[len(PROLOGUE):]
    unwind_offset = (len(result) + 3) & ~3
    table_offset = unwind_offset + len(UNWIND)
    image = result + bytes(unwind_offset - len(result)) + UNWIND + struct.pack('<III', 0, len(result), unwind_offset)
    # Validate the WHOLE code+metadata allocation, including the added bytes.
    require(base + len(image) <= 1 << 47, 'Image outside low canonical addresses')
    game = legacy['game_base']
    protected = [(legacy['roster_address'], 0x428), (legacy['property_address'], 0x100), (reject, 1),
                 (game + 0x60C640, 578), (game + 0x3326468, 8), (game + 0x3483C20, 4),
                 (game + 0x173B8D0, 1), (game + 0x134F190, 92), (game + 0x347CEF0, 8)]
    require(all(base >= a + n or a >= base + len(image) for a, n in protected), 'Code/unwind image overlaps a referenced region')
    candidate = dict(legacy)
    candidate.update(code_hex=result.hex(), code_sha256=sha(result), size_bytes=len(result),
                     status='offline_native_producer_with_unwind', unwind_registered=False)
    return {'candidate': candidate, 'image': image, 'unwind_offset': unwind_offset,
            'table_offset': table_offset, 'function_count': 1,
            'legacy_rejection_offsets': [p - base for p in replacements],
            'conditional_rejection': conditional_rejection}


def build(**addresses):
    return with_unwind(original(**addresses))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('game-base','code-address','roster-address','property-address','reject-address'):
        parser.add_argument('--'+name, type=lambda s: int(s,0), required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=vars(parser.parse_args()); output=args.pop('output')
    result=build(**args); result['image_hex']=result.pop('image').hex()
    # No silent replacement of an earlier address-bound build.
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({'output':str(output),'code_bytes':result['candidate']['size_bytes'],
                      'unwind_registered':False,'game_access':False}))
