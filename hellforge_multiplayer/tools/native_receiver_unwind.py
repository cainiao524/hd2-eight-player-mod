"""Emit the pinned receiver with a single, complete Windows unwind frame.

Offline data only. There is no game access, registration or hook installation.
"""
import importlib.util
import json
import struct

import native_producer_unwind as shared
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

ROOT, PROJECT = shared.ROOT, shared.PROJECT
require, sha, capstone = shared.require, shared.sha, shared.capstone
PROLOGUE = bytes.fromhex('48896c24204156')
# Push R14, then save RBP/RBX/RSI/RDI at their original final addresses.
# All four caller home slots now exist on the sentinel branch as well.
CANONICAL_PROLOGUE = bytes.fromhex('415648896c242848895c2410488974241848897c2420')
UNWIND = bytes.fromhex('0116090016740400116403000c3402000754050002e00000')
DELAYED_SAVES = {0x2F: '48895c2410', 0x34: '4889742418', 0x41: '48897c2420'}


def original(**addresses):
    lock=json.loads((PROJECT/'native-storage.lock.json').read_bytes())
    require(capstone.__version__==lock['capstone'], 'Wrong decoder version')
    rel='eight_player_candidate_20260927/Native/roster_receiver.py'
    path=ROOT/rel
    require(sha(path.read_bytes())==lock['legacy_source_sha256'][rel], 'Changed legacy receiver')
    spec=importlib.util.spec_from_file_location('pinned_unwind_receiver',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    source=module.load_source(ROOT/'five_player_feasibility_20260927/roster_property_receive_evidence.json')
    return module.build(source,**addresses)


def with_unwind(legacy, *, conditional_rejection=True):
    """Transform a freshly emitted pinned candidate without changing data ABI.

    The three original conditional saves are now redundant. NOP their exact
    bytes, retaining the body layout apart from the longer entry sequence.
    All original nonvolatile restores and the final RSP layout remain intact.
    """
    base,reject=legacy['entry_address'],legacy['reject_address']
    code=bytes.fromhex(legacy['code_hex'])
    require(sha(code)==legacy['code_sha256'] and code.startswith(PROLOGUE), 'Changed code/prologue')
    for offset, expected in DELAYED_SAVES.items():
        require(code[offset:offset+5]==bytes.fromhex(expected), 'Changed conditional register save')
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
    insns=list(md.disasm(code,base))
    require(sum(i.size for i in insns)==len(code), 'Undecodable receiver')
    rejection=[]
    for k,ins in enumerate(insns):
        if ins.mnemonic=='jmp' and ins.operands[0].type==X86_OP_IMM and ins.operands[0].imm==reject:
            require(ins.size==5 and ins.bytes[0]==0xE9 and k>0, 'Unexpected rejection branch')
            require(bytes(insns[k-1].bytes) in (bytes.fromhex('41ba01000000'),bytes.fromhex('41ba02000000')),
                    'Missing nonzero rejection reason')
            rejection.append(ins.address)
    require(len(rejection)==2, 'Expected two rejection exits')
    edits={base:CANONICAL_PROLOGUE,base+5:b''}
    edits.update({base+offset:b'\x90'*5 for offset in DELAYED_SAVES})
    mapping={}; cursor=base
    for ins in insns:
        mapping[ins.address]=cursor
        cursor += 9 if conditional_rejection and ins.address in rejection else len(edits.get(ins.address,ins.bytes))
    def target(address):
        if base <= address < base+len(code):
            require(address in mapping and address>=base+len(PROLOGUE), 'Branch into prologue/interior instruction')
            return mapping[address]
        return address
    chunks=[]
    for ins in insns:
        pc=mapping[ins.address]
        if ins.address in edits:
            blob=edits[ins.address]
        elif conditional_rejection and ins.address in rejection:
            delta=reject-(pc+9)
            require(-(1<<31)<=delta<(1<<31), 'Rejection continuation is outside rel32 range')
            blob=b'\x45\x85\xd2\x0f\x85'+struct.pack('<i',delta)
        else:
            blob=bytearray(ins.bytes)
            if (ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL)) and ins.operands[0].type==X86_OP_IMM:
                delta=target(ins.operands[0].imm)-(pc+ins.size)
                blob[ins.imm_offset:ins.imm_offset+ins.imm_size]=delta.to_bytes(ins.imm_size,'little',signed=True)
            for op in ins.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                    delta=target(ins.address+ins.size+op.mem.disp)-(pc+ins.size)
                    blob[ins.disp_offset:ins.disp_offset+ins.disp_size]=delta.to_bytes(ins.disp_size,'little',signed=True)
        chunks.append(bytes(blob))
    result=b''.join(chunks)
    require(len(result)==cursor-base and result.startswith(CANONICAL_PROLOGUE), 'Inconsistent relocation')
    unwind_offset=(len(result)+3)&~3; table_offset=unwind_offset+len(UNWIND)
    image=result+bytes(unwind_offset-len(result))+UNWIND+struct.pack('<III',0,len(result),unwind_offset)
    game=legacy['game_base']
    require(base+len(image)<=1<<47, 'Image outside low canonical addresses')
    regions=[(legacy['roster_address'],0x428),(legacy['property_address'],0x100),(reject,1),
             (game+0x60C890,303),(game+0x3483C20,4)]
    require(all(base>=a+n or a>=base+len(image) for a,n in regions), 'Code/unwind image overlaps a referenced region')
    candidate=dict(legacy)
    candidate.update(code_hex=result.hex(),code_sha256=sha(result),size_bytes=len(result),
                     status='offline_native_receiver_with_unwind',unwind_registered=False,
                     trampoline_address=mapping[legacy['trampoline_address']],resume_address=mapping[legacy['resume_address']])
    splice=mapping[base+legacy['splice']['offset']]-base
    candidate['splice']={**legacy['splice'],'offset':splice,'replacement_hex':result[splice:splice+6].hex()}
    candidate['rip_relocation']={**legacy['rip_relocation'],'displacement_offset':24}
    return {'candidate':candidate,'image':image,'unwind_offset':unwind_offset,'table_offset':table_offset,
            'function_count':1,'conditional_rejection':conditional_rejection,
            'rejection_transfer_offsets':[mapping[p]-base+(3 if conditional_rejection else 0) for p in rejection]}


def build(**addresses):
    return with_unwind(original(**addresses))


if __name__=='__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('game-base','code-address','roster-address','property-address','reject-address'):
        parser.add_argument('--'+name,type=lambda s:int(s,0),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=vars(parser.parse_args()); output=args.pop('output')
    result=build(**args); result['image_hex']=result.pop('image').hex()
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({'output':str(output),'code_bytes':result['candidate']['size_bytes'],
                      'unwind_registered':False,'game_access':False}))
