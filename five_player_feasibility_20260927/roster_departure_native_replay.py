"""Pin the complete 605950 departure wrapper and its direct 606820 reader.

This is a bounded static replay of one saved code capture. Other direct callees
are recorded as boundaries, not recursively expanded. No live process access,
native emission, hook installation, or runtime reachability inference.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_R10, X86_REG_R13, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

DEPARTURE = 0x605950
EXPLICIT_READER = 0x606820
S_GLOBAL = 0x3326468
INVALID_ID_GLOBAL = 0x3483C20

BODIES = {
    DEPARTURE: dict(end=0x605F2F, instructions=346,
                    sha256='4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681',
                    fragments=[
                        (0x605950,0x605969,0x2424974,'b1c99b45ebc2eb4d64b806a33ab1acdfbe8179f76dc15d02950d3ce07c822746'),
                        (0x605969,0x60596D,0x2424980,'6e79aa3ae4a0e8bccfa68fe9a1cd174954b08cdfa6b696817360ce24cced8a97'),
                        (0x60596D,0x605A63,0x2424994,'e5dfa9d2132fba7abe81e5413b988dd1977770150d5bf59b16eaffd8a9a76d96'),
                        (0x605A63,0x605B7C,0x24249AC,'3eb6f8351c2ce540653957ab9b0d5266ed3e9437a00d785e695c8bf63ed2336a'),
                        (0x605B7C,0x605BD3,0x24249C4,'41d97af4e764b55265fa44d40103f7693d9969a06643beea3b90f235b3c0bee4'),
                        (0x605BD3,0x605BF9,0x24249D4,'9df83c9a68bbafa69d0f4b885972b4417fec611cffaa729b75418ee02b880de0'),
                        (0x605BF9,0x605C50,0x24249EC,'0e5ab38b839b492c3c3d5a7f2741647129b217408fb2d3224dc17667c76d6a35'),
                        (0x605C50,0x605CCF,0x2424A00,'031e78dfb8c8efbfa3db8802f448b33305bff553d79bb550e85bb83f2b61334c'),
                        (0x605CCF,0x605CE1,0x2424A10,'749207688c5c9fd551cd85001cb033594cbf153af4c00a510fe61ad26118a889'),
                        (0x605CE1,0x605D18,0x2424A24,'b05a2dc42356c63fccd820436d7d0aafbf40ec951b4d674e1aa60816400556a0'),
                        (0x605D18,0x605DE1,0x2424A34,'4471939007ce1706fc074c1bac571309ce388bf07d4d669633dbef7f94a763da'),
                        (0x605DE1,0x605E4C,0x2424A48,'7e4f3b84495fe9855302d34ec904ded967904825799868a46229127d89b1e856'),
                        (0x605E4C,0x605F2F,0x2424A60,'dcfa6f42a3b5151da8a426c63cb1cce76bac75000cb63d9353674977f9b03bda')]),
    EXPLICIT_READER: dict(end=0x6068E5, instructions=51,
                          sha256='0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce',
                          fragments=[
                              (0x606820,0x606851,0x2424BD4,'816eae408b2cd52d729e6928d9cbfd4cd2e441f2e8d04e364c5d908b04ff5801'),
                              (0x606851,0x6068DB,0x2424BDC,'1e938354daf9c74f5d61bb9300c89ff87d069514cb8d2e34bb8b11622d0e42c3'),
                              (0x6068DB,0x6068E5,0x2424BFC,'306eb69d73576df0b8dc155186c516c5eea35f4e603b5bdffdbac33e665b3e38')]),
}

ROOT_RIPS = [
    (0x605962,0x3326468),(0x60597B,0x3483C20),(0x6059DB,0x3483C34),
    (0x6059F3,0x347CE60),(0x605A70,0x3326340),(0x605AB6,0x3326308),
    (0x605AE5,0x3483C20),(0x605AEB,0x3326D20),(0x605B64,0x3483C20),
    (0x605B6A,0x3326D20),(0x605BA8,0x347CE18),(0x605BBF,0x22473B8),
    (0x605D4F,0x346D500),(0x605DBF,0x346BF98),(0x605DCB,0x3326D20),
    (0x605E10,0x346BF98),(0x605E1C,0x3326D20),(0x605E2A,0x3326E68),
    (0x605E4C,0x23C6D70),(0x605E77,0x3326340),(0x605E87,0x3326468),
    (0x605E9B,0x33266A0),(0x605EFF,0x3326308),(0x605F06,0x22473C8),
]
ROOT_CALLS = [
    (0x6059EE,0x606820),(0x6059FC,0x139C360),
    (0x605A2E,0xB0B020),(0x605A42,0xB11C20),(0x605A56,0xB0F820),
    (0x605A68,0xFD9C80),(0x605ADD,0x838680),(0x605B5C,0xA747D0),
    (0x605BC9,0x13462C0),(0x605C63,0xA74700),(0x605D05,0xA77800),
    (0x605D20,0x135A4A0),(0x605D2C,0xBE21A0),(0x605D34,0xFD9D40),
    (0x605D7D,0x13BFB40),(0x605D9A,0x135AB10),(0x605DAA,0xBE16F0),
    (0x605DC6,0xFDC310),(0x605E17,0xFDC310),(0x605EDE,0x94C9C0),
    (0x605EFA,0x60C2A0),
]
EXPECTED_RELOCS = {
    DEPARTURE: set(('rip_address' if rva in (0x605BBF,0x605F06) else 'rip_memory',rva,target)
                   for rva,target in ROOT_RIPS) | set(('call_rel32',rva,target) for rva,target in ROOT_CALLS),
    EXPLICIT_READER: {('rip_memory',0x606824,INVALID_ID_GLOBAL)},
}
EXPECTED_INDIRECT = {
    DEPARTURE: {('call_indirect',0x605AC8),('tail_jump_indirect',0x605F28)},
    EXPLICIT_READER: set(),
}
ARRAY_SITES = {
    DEPARTURE: {'pointer': {0x605A0D,0x605B96},
                'primary_first_dword': {0x605A26,0x605A3A,0x605A4E},
                'property_first_dword': {0x605A5B}},
    EXPLICIT_READER: {'property_network_dword': {0x60683A,0x6068CE}},
}
NOTIFICATION_STRINGS = {0x22473B8: b'disconnected\0',
                        0x22473C8: b'player_count\0'}
CRITICAL = {
    DEPARTURE: {
        'entry_entity':0x605975,'entry_id':0x605978,'initial_map_miss':0x6059D4,
        'explicit_reader_call':0x6059EE,'network_association_call':0x6059FC,
        'ordinal_scale_property':0x605A03,'target_pointer_first':0x605A0D,
        'flag_test':0x605A15,'primary_index_scale':0x605A22,
        'first_primary_notification':0x605A2E,'second_primary_notification':0x605A42,
        'third_primary_notification':0x605A56,'property_first_read':0x605A5B,
        'related_object_lookup':0x605A68,'target_pointer_second':0x605B96,
        'relationship_id_read':0x605AE2,'dense_count_first':0x605EF1,
        'final_direct_call':0x605EFA,'dense_count_second':0x605F0D,
        'indirect_tail':0x605F28},
    EXPLICIT_READER: {
        'entry_s':0x60682A,'invalid_id_branch':0x60682D,
        'invalid_path_ordinal':0x60682F,'invalid_path_property_read':0x60683A,
        'map_miss_ordinal':0x6068B0,'miss_path_property_read':0x6068CE,
        'found_ordinal_read':0x6068DF,'early_return':0x606846,'normal_return':0x6068DA},
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def detail(ins):
    out = row(ins)
    out['encoding'] = dict(rex=ins.rex, modrm=ins.modrm, sib=ins.sib,
                           displacement_offset=ins.disp_offset,
                           displacement_size=ins.disp_size,
                           immediate_offset=ins.imm_offset,
                           immediate_size=ins.imm_size)
    return out


def pin_fragments(im, entry, spec):
    found = [f for f in im.functions if im.root(f[0])[0] == entry]
    expected = [(a,b,u) for a,b,u,_ in spec['fragments']]
    require(found == expected, 'chained unwind fragments changed at ' + hex(entry))
    require(found[0][0] == entry and found[-1][1] == spec['end'] and
            all(x[1] == y[0] for x,y in zip(found,found[1:])),
            'noncontiguous body fragments')
    out = []
    for a,b,u,digest in spec['fragments']:
        raw = im.read(a,b-a)
        require(sha(raw) == digest, 'fragment bytes changed at ' + hex(a))
        out.append(dict(start=hex(a),end_exclusive=hex(b),unwind=hex(u),
                        size_bytes=b-a,sha256=digest))
    return out


def pin_flow(instructions, entry):
    by_addr = {x.address:x for x in instructions}
    cfg, branches, relocations, indirect = {}, [], [], []
    for x in instructions:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocations.append(dict(kind='rip_address' if x.mnemonic == 'lea' else 'rip_memory',
                                        rva=hex(x.address),target_rva=hex(x.address+x.size+op.mem.disp),
                                        displacement_offset=x.disp_offset,
                                        displacement_size=x.disp_size,instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            require(len(x.operands)==1,'unmodeled call operands')
            if x.operands[0].type == X86_OP_IMM:
                relocations.append(dict(kind='call_rel32',rva=hex(x.address),
                                        target_rva=hex(x.operands[0].imm),
                                        displacement_offset=x.imm_offset,
                                        displacement_size=x.imm_size,instruction=detail(x)))
            else:
                indirect.append(dict(kind='call_indirect',rva=hex(x.address),instruction=detail(x)))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands)==1,'unmodeled jump operands')
            if x.operands[0].type == X86_OP_IMM:
                target=x.operands[0].imm
                require(target in by_addr,'branch escapes complete body at '+hex(x.address))
                successors=[target]
                if x.mnemonic!='jmp':successors.append(x.address+x.size)
                branches.append(detail(x))
            else:
                require(x.mnemonic=='jmp','indirect conditional branch')
                successors=[]
                indirect.append(dict(kind='tail_jump_indirect',rva=hex(x.address),instruction=detail(x)))
        else:
            successors=[x.address+x.size]
        require(all(t in by_addr for t in successors),'bad CFG edge at '+hex(x.address))
        cfg[hex(x.address)]=[hex(t) for t in successors]
    require({(x['kind'],int(x['rva'],16),int(x['target_rva'],16)) for x in relocations}
            == EXPECTED_RELOCS[entry], 'external relocation set changed at '+hex(entry))
    require({(x['kind'],int(x['rva'],16)) for x in indirect} == EXPECTED_INDIRECT[entry],
            'indirect control set changed at '+hex(entry))
    require(all(x['displacement_size']==4 for x in relocations),
            'non-disp32 external relocation')
    seen, todo=set(),[entry]
    while todo:
        at=todo.pop()
        if at in seen:continue
        seen.add(at);todo.extend(int(t,16) for t in cfg[hex(at)])
    require(seen==set(by_addr),'unreachable instruction in complete body')
    return cfg,branches,relocations,indirect


def pin_arrays(instructions,entry):
    found=[]
    for x in instructions:
        for i,op in enumerate(x.operands):
            if op.type != X86_OP_MEM:continue
            if entry == DEPARTURE and X86_REG_R13 in (op.mem.base,op.mem.index):
                group=next((name for name,addresses in ARRAY_SITES[entry].items()
                            if x.address in addresses),None)
            elif entry == EXPLICIT_READER and X86_REG_R10 in (op.mem.base,op.mem.index):
                group=next((name for name,addresses in ARRAY_SITES[entry].items()
                            if x.address in addresses),None)
            else:continue
            if group is None:continue
            found.append(dict(rva=hex(x.address),group=group,operand_index=i,
                              access='address_only' if x.mnemonic=='lea' else 'write' if i==0 else 'read',
                              width_bytes=op.size,base_register=x.reg_name(op.mem.base),
                              index_register=x.reg_name(op.mem.index),index_scale=op.mem.scale,
                              original_displacement=op.mem.disp,
                              displacement_offset=x.disp_offset,
                              displacement_size=x.disp_size,instruction=detail(x)))
    actual={name:{int(x['rva'],16) for x in found if x['group']==name}
            for name in ARRAY_SITES[entry]}
    require(actual==ARRAY_SITES[entry], 'direct array-site set changed at '+hex(entry))
    require(all(x['access']=='read' and x['displacement_size']==4 for x in found),
            'non-read or unexpected array encoding')
    return found


def pin_body(im,entry,spec):
    fs=pin_fragments(im,entry,spec)
    raw=im.read(entry,spec['end']-entry)
    require(sha(raw)==spec['sha256'],'complete body changed at '+hex(entry))
    ins=list(im.md.disasm(raw,entry))
    require(len(ins)==spec['instructions'] and sum(x.size for x in ins)==len(raw),
            'incomplete decode at '+hex(entry))
    require(len({x.address for x in ins})==len(ins),'duplicate instruction boundary')
    cfg,branches,relocations,indirect=pin_flow(ins,entry)
    arrays=pin_arrays(ins,entry)
    by_addr={x.address:x for x in ins}
    require(all(a in by_addr for a in CRITICAL[entry].values()),'critical site boundary changed')
    exits=[detail(x) for x in ins if x.group(cs.CS_GRP_RET) or
           (x.group(cs.CS_GRP_JUMP) and x.operands[0].type!=X86_OP_IMM)]
    if entry==DEPARTURE:
        require([(x['kind'],int(x['rva'],16)) for x in indirect if x['kind']=='tail_jump_indirect']
                == [('tail_jump_indirect',0x605F28)] and not any(x['asm'].startswith('ret') for x in exits),
                'departure exit changed')
        abi='Windows x64; RDX=entity pointer, ID at +8, R14=entity, R13=[global 3326468]=S. Entry RCX is saved to home space but not used as roster source. Restores nonvolatiles/XMM6/stack then indirect tail-jumps; no local RET.'
    else:
        require([int(x['rva'],16) for x in exits]==[0x606846,0x6068DA],
                'explicit reader returns changed')
        abi='Windows x64; RCX=explicit S, EDX=entity ID, R10=RCX. Both invalid and miss ordinal FFFFFFFF paths still read S+3B4h+ordinal*20h. EAX is that property network-index DWORD; two RET paths.'
    return dict(entry=hex(entry),end_exclusive=hex(spec['end']),
                size_bytes=len(raw),sha256=sha(raw),bytes_hex=raw.hex(),fragments=fs,
                abi=abi,instructions=[detail(x) for x in ins],cfg=cfg,branches=branches,
                external_relocations=relocations,indirect_controls=indirect,
                array_sites=arrays,array_site_counts={name:sum(x['group']==name for x in arrays)
                                                for name in ARRAY_SITES[entry]},
                critical_sites={name:detail(by_addr[at]) for name,at in CRITICAL[entry].items()},
                exit_sites=exits)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    require(not args.output.exists(),'refusing to overwrite output')
    im=Image(args.evidence)
    bodies={hex(entry):pin_body(im,entry,spec) for entry,spec in BODIES.items()}
    strings={}
    for address,expected in NOTIFICATION_STRINGS.items():
        raw=im.read(address,len(expected))
        require(raw==expected,'notification literal changed at '+hex(address))
        strings[hex(address)]=dict(bytes_hex=raw.hex(),sha256=sha(raw),
                                   text=raw[:-1].decode('ascii'))
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
                replay_sha256=sha(Path(__file__).read_bytes()),bodies=bodies,
                notification_literals=strings,
                dependency='605950 directly calls 606820 with RCX=S and EDX=target ID; its two property network-index reads must be handled with the departure root.',
                direct_roster_storage='605950 has two pointer reads, three primary-first-DWORD reads and one property-first-DWORD read; 606820 has two property-network-DWORD reads. Neither body directly reads or writes aux records.',
                finite_scope='Complete 605950 chained root plus one directly necessary 606820 reader; all other direct/indirect callees remain explicit boundaries.',
                limits=['605950 is not a direct call to 60CEA0/540A40 and does not itself decrement roster T/D/P or mutate four storage arrays.',
                        'Map miss can propagate ordinal FFFFFFFF to direct property access and to 606820; valid map/ordinal is not proved by these bodies.',
                        'External notifications, object lifetime, indirect dispatch target, caller reachability and failure recovery remain unproved.',
                        'No live process, code emission, hook or multiplayer execution.'])
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),bodies={k:dict(size_bytes=v['size_bytes'],
          instructions=len(v['instructions']),sha256=v['sha256'],
          relocations=len(v['external_relocations']),array_site_counts=v['array_site_counts'])
          for k,v in bodies.items()})))


if __name__=='__main__':main()
