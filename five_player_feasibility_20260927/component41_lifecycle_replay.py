"""Offline lifecycle/layout replay for component index 41, fixed capture only.

Does not access a process, install a mod, or patch any game files.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import EXPECTED, Image, require, row, scan

PRIOR_SHA = '4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147'
INIT_SHA = '22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2'
TABLES = [0xF0B6F0,0xF0C110,0xF0CB30,0xF0D550,0xF0DF70,
          0xF0E990,0xF0F3B0,0xF0FDD0,0xF107F0,0xF11210]
TARGETS = {0xF0B6F0:0x51BA90,0xF0C110:0x51BB50,0xF0CB30:0x51BCC0,
           0xF0D550:0x51BEB0,0xF0E990:0x51BC40,0xF0F3B0:0x51BEF0,
           0xF107F0:0x51BF00}
ROOTS = [0x51BA90,0x51BB50,0x51BC40,0x51BCC0,0x51BEB0,
         0x7AEDF0,0x7AF210,0x7AF610,0x7AF7A0,0x7AFB50,0x7AFBE0,0x7AFFD0,
         0x172F790,0x172F8A0]
SPANS = {
    'owner_context_and_alias_globals': [(0xFDA352,0xFDA37A),(0x551B60,0x551B82),
                                      (0x568230,0x568249),(0xBC2D7C,0xBC2D93)],
    'component_and_adjacent_member_publication': [(0x568448,0x568464)],
    'constructor_hash_map_and_tag80': [(0x551D3C,0x551D3F),(0x552703,0x55285D)],
    'owner_registry_cleanup': [(0x55E1F0,0x55E206),(0x55F3A8,0x55F3B4)],
    'direct_owner_update': [(0x571250,0x571295),(0x571427,0x5715C5)],
    'direct_owner_pending_integration': [(0x576CF0,0x576D10),(0x577DDE,0x577E2D)],
    'owner_update_and_integration_callers': [(0xFDAEE0,0xFDAF54),(0xFDC780,0xFDC7AC)],
    'direct_owner_property_apply': [(0xBD13E4,0xBD13FF)],
    'first_record_global_consumer_example': [(0xFDFF33,0xFDFF94)],
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = Path(args.output)
    require(not out.exists(), 'refusing overwrite')
    im = Image(args.evidence)
    prior_raw = (HERE/'player_component_capacity_evidence.json').read_bytes()
    require(sha(prior_raw)==PRIOR_SHA, 'capacity artifact changed')
    prior = json.loads(prior_raw)
    c41 = next(e for e in prior['entries'] if e['component_index']==41)
    for p in c41['instructions']:
        i = im.instruction(int(p['rva'],16))
        require(i is not None and i.bytes.hex()==p['bytes'], 'capacity source mismatch')

    init = im.read(0x556D90,0x55E1E3-0x556D90)
    require(sha(init)==INIT_SHA, 'initializer changed')
    require(im.instruction(0x568239).op_str=='0x556d90', 'initializer call proof changed')
    assignments = {}
    for at in range(0,len(init)-1,14):
        pair=init[at:at+14]
        require(pair[:3]==b'\x48\x8d\x05' and pair[7:10]==b'\x48\x89\x81', 'bad assignment')
        target=0x556D90+at+7+struct.unpack_from('<i',pair,3)[0]
        offset=struct.unpack_from('<i',pair,10)[0]
        assignments[offset]=dict(target=target, instructions=[row(i) for i in im.md.disasm(pair,0x556D90+at)])
    registrations=[]
    for base in TABLES:
        slot=base+41*8
        value=assignments.get(slot)
        require((value and value['target'])==TARGETS.get(base), 'index41 registration mismatch')
        registrations.append(dict(table_base=hex(base),slot=hex(slot),
            callback=hex(value['target']) if value else None,
            initializer_assignment=value,
            status='registered' if value else 'No assignment in this fixed initializer; runtime value is unproven.'))

    functions=[]
    decoded={}
    for root in ROOTS:
        fs=[f for f in im.functions if im.root(f[0])[0]==root]
        require(fs and fs[0][0]==root, 'missing root')
        instructions=[]
        fragments=[]
        for a,b,u in fs:
            data=im.read(a,b-a)
            ds=list(im.md.disasm(data,a))
            require(sum(i.size for i in ds)==len(data), 'incomplete fragment decode')
            fragments.append(dict(start=hex(a),end_exclusive=hex(b),unwind=hex(u),sha256=sha(data)))
            instructions.extend(ds)
        decoded[root]=instructions
        functions.append(dict(entry=hex(root),fragments=fragments,instructions=[row(i) for i in instructions]))

    leaves=[]
    for entry,target in [(0x51BEF0,0x7AFBE0),(0x51BF00,0x7AFFD0)]:
        data=im.read(entry,8)
        ds=list(im.md.disasm(data,entry))
        require(len(ds)==2 and sum(i.size for i in ds)==8 and ds[-1].op_str==hex(target), 'leaf changed')
        proof=next(r for r in registrations if r['callback']==hex(entry))
        leaves.append(dict(entry=hex(entry),sha256=sha(data),entry_proof=proof,instructions=[row(i) for i in ds]))
    # This leaf has two RETs. Decode through the final branch target, not merely
    # through the first RET, and validate every normal branch target.
    entry,end=0xB389B0,0xB38B4E
    data=im.read(entry,end-entry)
    ds=list(im.md.disasm(data,entry))
    require(sha(data)=='c739c1e6b44c31040950e32edc75faccd111e98069b53e0cc93907ad9767ed64','cleanup changed')
    require(sum(i.size for i in ds)==len(data),'cleanup decode incomplete')
    boundaries={i.address for i in ds}
    for i in ds:
        if i.group(cs.CS_GRP_JUMP):
            require(i.operands[0].type==X86_OP_IMM and i.operands[0].imm in boundaries, 'cleanup branch leaves body')
    caller=im.instruction(0x55F3AF)
    require(caller is not None and caller.mnemonic=='call' and caller.op_str==hex(entry), 'cleanup entry proof changed')
    leaves.append(dict(entry=hex(entry),end_exclusive=hex(end),sha256=sha(data),
                       entry_proof=row(caller),instructions=[row(i) for i in ds]))

    pins={}
    for name,ranges in SPANS.items():
        pins[name]=[]
        for lo,hi in ranges:
            require(im.instruction(lo) is not None, 'span start unproven '+hex(lo))
            require(im.instruction(hi) is not None or any(f[1]==hi for f in im.functions),'span end unproven '+hex(hi))
            for a,b,u in im.functions:
                if a>=hi or b<=lo:continue
                for i in im.md.disasm(im.read(a,b-a),a):
                    if lo<=i.address<hi:
                        pins[name].append(dict(**row(i),root=hex(im.root(i.address)[0]),
                                              fragment=[hex(a),hex(b),hex(u)]))

    # The inventory deliberately retains aliases and distinguishes full owner
    # references from same-displacement matches belonging to unrelated types.
    inventory={}
    for root,instructions in decoded.items():
        inventory[hex(root)]=[dict(**row(i),operands=[dict(displacement=hex(o.mem.disp),size=o.size,
            base=i.reg_name(o.mem.base),index=i.reg_name(o.mem.index),scale=o.mem.scale,access=o.access)
            for o in i.operands if o.type==X86_OP_MEM and (0x26528<=o.mem.disp<0x267E8 or o.mem.disp in [0x68,0x88])])
            for i in instructions if any(o.type==X86_OP_MEM and
            (0x26528<=o.mem.disp<0x267E8 or o.mem.disp in [0x68,0x88]) for o in i.operands)]
    xrefs=scan(im,{0x3326998,0x7AF210})
    require(0x88+4*0x9928==0x26528 and 0x26528+4*0x58==0x26688 and
            0x26688+4*0x58==0x2A930-0x4148,'layout equality changed')
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        prior_capacity_artifact_sha256=PRIOR_SHA,prior_component_41=c41,
        registration_initializer_sha256=INIT_SHA,registrations=registrations,
        functions=functions,leaf_functions=leaves,selected_instruction_groups=pins,
        storage_reference_inventory=inventory,bounded_reference_scan=xrefs,
        layout=dict(owner_offset='0x4148',published_global='0x3326998',tag='0x80',
            next_member_owner_offset='0x2a930',span_to_next_member='0x267e8',
            hash_map=dict(header='0x50',embedded_entries='0x10',buckets=8,bucket_size=8,multiplier=2),
            arrays=[dict(base=hex(a),stride=hex(s),count=4,end_exclusive=hex(a+4*s))
                    for a,s in [(0x68,8),(0x88,0x9928),(0x26528,0x58),(0x26688,0x58)]],
            eight_slot_payload_growth=4*(8+0x9928+0x58+0x58)),
        semantic_findings=[
            '7AF210 performs a one-way source-R8D to destination-EDX copy, not a swap; it updates the copied entity ID->ordinal value.',
            '51BC40 removes the ID from the map, compacts classified/active/total regions as applicable, and calls the one-way move helper.',
            '7AFBE0 promotes into +C prefix: clears destination 0x9928 record, swaps pointer and both 0x58 records, repairs both map values.',
            '7AFFD0 demotes from +C prefix: swaps all four arrays and repairs both map values.',
            '51BCC0 initializes and emits two 0x2C records from the third array; 7AF610 applies two 0x2C records into it.',
            '7AEDF0 post-setup uses slot zero of the third array and pointer array after a +C>0 condition, and dispatches two property hashes.',
            'Direct owner update/integration/property paths and tag registry copies bypass the component global pointer.',
        ],
        limits=[
            'Component41 belongs to the reference player metadata; equality with installed/live metadata remains unproven.',
            'Three table slots lack an initializer assignment; this is not proof that their live values are null.',
            'Storage index is an entity-ID map ordinal, not established as a network index.',
            'The span ends at a separately published/initialized next member; it is not an independently allocated heap block size.',
            'The exact-displacement inventory omits derived-address accesses; aliases and downstream callees must be retained in any redesign.',
            'Eight hash buckets can represent eight keys in principle, but full-table runtime operation has not been tested.',
            'No runtime invocation, capture, patch, installation, or multiplayer validation.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),functions=len(functions),
        instructions=sum(len(f['instructions']) for f in functions),
        leaf_instructions=sum(len(f['instructions']) for f in leaves),
        selected_records=sum(map(len,pins.values())),registered_callbacks=len(TARGETS),
        sha256=sha(out.read_bytes()))))


if __name__=='__main__':
    main()
