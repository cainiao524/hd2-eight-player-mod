"""Offline receiver for the roster's complete 32-byte property record.

Only reads fixed captured files; no process access, capture, or patching.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image, EXPECTED, require, row, scan

PRIOR={
    'roster_component_binding_evidence_v3.json':'274833c418bfa7dec4e4097dda5031f3a11e8c69689ae4ed758e75a40481c2e2',
    'roster_property_apply_evidence_v3.json':'d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22',
}
LOADS=[0x60C932,0x60C940,0x60C94E,0x60C95C,0x60C96A,0x60C978,0x60C986,0x60C994]
STORES=[0x60C938,0x60C946,0x60C954,0x60C962,0x60C970,0x60C97E,0x60C98C,0x60C9A2]
SPANS={
    'common_owner_and_aliases':[(0xFDA352,0xFDA37A),(0x551B7A,0x551B82),(0x568236,0x568249)],
    'roster_publication':[(0x568EC8,0x568ED6)],
    'caller_owner_payload_and_cursor':[(0xBC2D7C,0xBC2DA1),(0xBD13A2,0xBD13B8)],
    'producer_index_bridge':[(0x60C6EB,0x60C6FD),(0x60C778,0x60C7A7)],
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    im=Image(args.evidence)
    prior_instruction_checks=0
    def check_prior(value):
        nonlocal prior_instruction_checks
        if isinstance(value,dict):
            if isinstance(value.get('rva'),str) and isinstance(value.get('bytes'),str):
                raw=bytes.fromhex(value['bytes'])
                require(im.read(int(value['rva'],16),len(raw))==raw,'prior bytes changed')
                prior_instruction_checks+=1
            for v in value.values():check_prior(v)
        elif isinstance(value,list):
            for v in value:check_prior(v)
    for name,digest in PRIOR.items():
        raw=(HERE/name).read_bytes()
        require(sha(raw)==digest,'prior artifact changed: '+name)
        check_prior(json.loads(raw))

    fs=[f for f in im.functions if im.root(f[0])[0]==0x60C890]
    require(len(fs)==4 and fs[0][0]==0x60C890 and fs[-1][1]==0x60C9BF,'receiver extent changed')
    instructions={};fragments=[]
    for a,b,u in fs:
        raw=im.read(a,b-a);ds=list(im.md.disasm(raw,a))
        require(sum(i.size for i in ds)==len(raw),'incomplete receiver decode')
        fragments.append(dict(start=hex(a),end_exclusive=hex(b),unwind=hex(u),sha256=sha(raw)))
        instructions.update((i.address,i) for i in ds)
    edges={};branches=[]
    for addr,i in instructions.items():
        if i.group(cs.CS_GRP_RET):successors=[]
        elif i.group(cs.CS_GRP_JUMP):
            require(i.operands[0].type==X86_OP_IMM,'unexpected indirect receiver jump')
            successors=[i.operands[0].imm]
            if i.mnemonic!='jmp':successors.append(addr+i.size)
            branches.append(row(i))
        else:successors=[addr+i.size]
        require(not i.group(cs.CS_GRP_CALL),'unexpected receiver call')
        require(all(s in instructions for s in successors),'receiver edge outside proven instructions')
        edges[addr]=successors
    def reach(start):
        seen=set();q=[start]
        while q:
            a=q.pop()
            if a in seen:continue
            seen.add(a);q.extend(edges[a])
        return seen
    require(set(instructions)==reach(0x60C890),'unexpected unreachable instructions')

    writes=[]
    for k,(load,store) in enumerate(zip(LOADS,STORES)):
        li,si=instructions[load],instructions[store]
        require(li.mnemonic==si.mnemonic=='mov','record operation changed')
        require(li.operands[1].type==X86_OP_MEM and li.operands[0].size==4,'input load is not DWORD')
        require(si.operands[0].type==X86_OP_MEM and si.operands[0].size==4 and
                si.operands[0].mem.disp==0x3A8+4*k,'record store changed')
        require(li.operands[0].reg==si.operands[1].reg,'load/store value register differs')
        writes.append(dict(record_dword=k,payload_relative_to_entry_cursor=4*k,
            roster_base_relative_offset=hex(0x3A8+4*k),width_bits=32,
            load=row(li),store=row(si)))
    critical={
        0x60C89D:'mov r14, r9',0x60C8A0:'mov rbp, r8',0x60C8A3:'mov r11, rcx',
        0x60C9B5:'mov eax, dword ptr [rbx + r8*8 + 4]',
        0x60C928:'mov ecx, dword ptr [r14]',0x60C92B:'mov r8d, eax',
        0x60C92E:'shl r8, 5',0x60C95C:'mov ecx, dword ptr [rdx + rbp]',
        0x60C95F:'add edx, 4',0x60C962:'mov dword ptr [r8 + r11 + 0x3b4], ecx',
        0x60C99F:'mov dword ptr [r14], eax',
    }
    for a,asm in critical.items():require(instructions[a].mnemonic+' '+instructions[a].op_str==asm,'critical pin changed')
    require(all(i.mnemonic=='mov' or i.mnemonic in ['lea','add','shl','pop','ret']
                for a,i in instructions.items() if 0x60C928<=a<0x60C9AD),'write path gained unmodeled operation')

    pins={}
    for name,spans in SPANS.items():
        pins[name]=[]
        for lo,hi in spans:
            require(im.instruction(lo) is not None and im.instruction(hi) is not None,'caller/bridge span unaligned')
            for a,b,u in im.functions:
                if a>=hi or b<=lo:continue
                for i in im.md.disasm(im.read(a,b-a),a):
                    if lo<=i.address<hi:pins[name].append(dict(**row(i),root=hex(im.root(i.address)[0]),
                                                             fragment=[hex(a),hex(b),hex(u)]))
    require(im.instruction(0xBD13B3).op_str=='0x60c890','direct caller changed')
    xrefs=scan(im,{0x60C890})
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        prior_artifact_sha256=PRIOR,prior_byte_records_rechecked=prior_instruction_checks,
        receiver=dict(entry='0x60c890',end_exclusive='0x60c9bf',size_bytes=0x12F,
            sha256=sha(im.read(0x60C890,0x12F)),fragments=fragments,
            instructions=[row(i) for i in instructions.values()],
            cfg={hex(k):list(map(hex,v)) for k,v in edges.items()},branches=branches),
        abi=dict(rcx='roster S = owner + 0xEA0818',edx='entity ID, not network index',
                 r8='payload buffer base',r9='pointer to uint32 payload cursor'),
        entity_to_ordinal=dict(map_pointer='S+0xD0',capacity='S+0xD8',invalid_key='S+0xDC',
            multiplier='S+0xE0',hit_value='map entry +4',miss_result='0xFFFFFFFF',
            miss_can_reach_record_store=0x60C962 in reach(0x60C914)),
        record_writes=writes,record_stride=32,cursor_increment_bytes=32,
        network_index=dict(input='payload + entry_cursor + 0xC',
            destination='S + ordinal*0x20 + 0x3B4',width_bits=32,bit_preserving=True,
            index_compare_or_clamp_in_receiver=False),
        selected_instruction_groups=pins,bounded_direct_caller_scan=xrefs,
        limits=[
            'This callee consumes a schema-selected fixed record; upstream selector/payload and handle-to-ID validation are separate evidence.',
            'No callee check establishes valid entity ID, ordinal bounds, input length, or network-index range.',
            'Failure to find an ID reaches the write path with ordinal 0xFFFFFFFF; valid membership is a required precondition.',
            'Record fields have raw 32-bit copies; absence of a local <4 check does not remove other native four-slot limits.',
            'The direct caller uses owner+EA0818 and bypasses the roster global; relocation must update this alias and all eight store offsets.',
            'Bounded E8/E9 scan validates unwind-covered direct callers; it does not exclude indirect or uncovered paths.',
            'No current runtime metadata, network execution, new capture, patch, install, or multiplayer validation.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),receiver_instructions=len(instructions),
        fragments=len(fragments),record_writes=len(writes),pins=sum(map(len,pins.values())),
        prior_byte_records_rechecked=prior_instruction_checks,sha256=sha(out.read_bytes()))))


if __name__=='__main__':main()
