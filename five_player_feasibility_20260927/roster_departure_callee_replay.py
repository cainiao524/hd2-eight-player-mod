"""Pin seven already-reviewed departure callees and three strings, offline only.

Fixed manifest: no code scan, recursive callee expansion, process API or emitter.
94C9C0's final unwind fragment contains code, padding and three RVA tables;
only the declared code prefix is disassembled as instructions.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'eight_player_candidate_20260927' / '.native-test-deps'),
               str(HERE.parent / 'research_handoff_20260927' / 'indirect')]
import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from inspect_capture import EXPECTED, Image, require, row


# end, code end, decoded code instruction count, full-range SHA, unwind fragments
BODIES = {
    0xB0B020: (0xB0B1C4, 0xB0B1C4, 104,
               '5e4eb6a1ec43b034743f67d84cf8af24a83bcbf8c4851211e2074ccb6600d1d4',
               [(0xB0B020,0xB0B03E,0x24A9D54),(0xB0B03E,0xB0B07C,0x24A9D60),
                (0xB0B07C,0xB0B0C7,0x24A9D7C),(0xB0B0C7,0xB0B1A6,0x24A9D90),
                (0xB0B1A6,0xB0B1AB,0x24A9DA4),(0xB0B1AB,0xB0B1BA,0x24A9DB4),
                (0xB0B1BA,0xB0B1C4,0x24A9DC4)]),
    0xB11C20: (0xB11DC4, 0xB11DC4, 104,
               '2cfbab65bc09dab531e0d6d40068a47e7e13a95f1f039ffff5795fb813768b25',
               [(0xB11C20,0xB11C3E,0x24AA5C4),(0xB11C3E,0xB11C7C,0x24AA5D0),
                (0xB11C7C,0xB11CC7,0x24AA5EC),(0xB11CC7,0xB11DA6,0x24AA600),
                (0xB11DA6,0xB11DAB,0x24AA614),(0xB11DAB,0xB11DBA,0x24AA624),
                (0xB11DBA,0xB11DC4,0x24AA634)]),
    0xB0F820: (0xB0F9C4, 0xB0F9C4, 104,
               '533fada65b0fe0477682f7fa97a9c346c0bc3d503065d6e4d211f793b3a4afaa',
               [(0xB0F820,0xB0F83E,0x24AA2F4),(0xB0F83E,0xB0F87C,0x24AA300),
                (0xB0F87C,0xB0F8C7,0x24AA31C),(0xB0F8C7,0xB0F9A6,0x24AA330),
                (0xB0F9A6,0xB0F9AB,0x24AA344),(0xB0F9AB,0xB0F9BA,0x24AA354),
                (0xB0F9BA,0xB0F9C4,0x24AA364)]),
    0xFDC310: (0xFDC40A, 0xFDC40A, 63,
               '774652c9ef50dde18f79f969fc77f54a07f8b5fac561b9fead11eec1d9730b64',
               [(0xFDC310,0xFDC40A,0x24CDE64)]),
    0xFD9C80: (0xFD9D33, 0xFD9D33, 46,
               '0533fa336a0f696021412e722716c7de8ee2096439a98f7e8671a9ea44487eae',
               [(0xFD9C80,0xFD9C9C,0x24CD94C),(0xFD9C9C,0xFD9D15,0x24CD954),
                (0xFD9D15,0xFD9D33,0x24CD970)]),
    0x60C2A0: (0x60C33F, 0x60C33F, 40,
               '66ce04f430d2fc2d46c023d5d7cff18bb19cca43a0f43eaf72fa842b01f066d6',
               [(0x60C2A0,0x60C33F,0x2425674)]),
    0x94C9C0: (0x94D308, 0x94D299, 467,
               '7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2',
               [(0x94C9C0,0x94C9EE,0x247E990),(0x94C9EE,0x94CC27,0x247E9B0),
                (0x94CC27,0x94CC84,0x247E9C8),(0x94CC84,0x94D277,0x247E9D8),
                (0x94D277,0x94D308,0x247E9EC)]),
}

PRIMARY_KEYS = {
    'retain_entity_id':0x10, 'retain_owner_s':0x13, 'compare_tuple_owner_s':0xD9,
    'compare_tuple_entity_id':0xE3, 'clear_tuple_pointer':0xF2,
    'decrement_registration_count':0xFD, 'indirect_free':0x144,
    'clear_backing_pointer':0x147, 'mark_subsystem_index':0x170,
    'decrement_subsystem_count':0x176, 'map_cleanup_call':0x17C,
}
CRITICAL = {entry: {name:entry+offset for name,offset in PRIMARY_KEYS.items()}
            for entry in (0xB0B020,0xB11C20,0xB0F820)}
CRITICAL.update({
    0xFDC310: {'invalid_id_compare':0xFDC31A,'type_lookup':0xFDC32D,
               'event_call':0xFDC389,'queue_write':0xFDC3F6,'queue_count_increment':0xFDC3F9},
    0xFD9C80: {'associated_type_7fff_compare':0xFD9C87,'associated_type_7fff_branch':0xFD9C8D,
               'ordinary_lookup_pointer_dereference':0xFD9D10,'7fff_null_return_value':0xFD9D2C},
    0x60C2A0: {'retain_unsigned_count':0x60C2B8,'first_count_compare':0x60C2D0,
               'fourth_count_compare':0x60C2DF,'hash_lookup':0x60C2FE,
               'named_resource_callback':0x60C312,'numeric_string':0x60C31F,
               'unsigned_count_to_float':0x60C329,'numeric_tail':0x60C338},
    0x94C9C0: {'read_caller_stack28_count':0x94CA1D,'lower_count_compare':0x94CA24,
               'lower_count_clamp':0x94CA29,'upper_count_constant':0x94CA30,
               'upper_unsigned_clamp':0x94CA37,'count_notification_string':0x94CBDE,
               'count_notification_argument':0x94CBE5,'count_notification_call':0x94CBEB,
               'first_clamped_count_stack_argument':0x94CC60,'first_downstream_call':0x94CC7A},
})
STRINGS = {
    0x22473C8: (b'player_count\0', '2d1f7bb5ed667b71641e114124b84958b97b41db1140c1f721dba595fff5edc4', 0x605F06),
    0x2247550: (b'Multiplayer_NumberOfActiveTeammates\0', 'ca1551c41277abc4e1516ed4e83f8971fcb366a795669445578e519ac993f0c7', 0x60C31F),
    0x224CF30: (b'num_players\0', '7f484e7a6d7f43a40309406e406b8584d9417c37d6d3ff2ea23d6b75294082f5', 0x94CBDE),
}
TABLES = [(0x94D29C,0x94D2C0,0x94CA92,0x94CA99,0x94CAA0,0x94CAA3),
          (0x94D2C0,0x94D2E4,0x94CAB7,0x94CABE,0x94CAC5,0x94CAC8),
          (0x94D2E4,0x94D308,0x94CADC,0x94CAE3,0x94CAEA,0x94CAED)]
TABLE_TARGETS = [0x94CAEF,0x94CAA5,0x94CAF9,0x94CB03,0x94CACA]+[0x94CB0D]*4


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def detail(ins):
    return dict(row(ins), encoding=dict(rex=ins.rex,modrm=ins.modrm,sib=ins.sib,
                displacement_offset=ins.disp_offset,displacement_size=ins.disp_size,
                immediate_offset=ins.imm_offset,immediate_size=ins.imm_size))


def region(im, start, end, kind):
    raw=im.read(start,end-start)
    return dict(start=hex(start),end_exclusive=hex(end),kind=kind,
                size_bytes=len(raw),sha256=sha(raw),bytes_hex=raw.hex())


def pin_body(im, entry, spec):
    end,code_end,count,digest,fragments=spec
    require(sha(im.read(entry,end-entry))==digest,'body SHA mismatch '+hex(entry))
    out=region(im,entry,end,'complete_saved_unwind_range')
    fragment_rows=[]
    current=entry
    for expected in fragments:
        require(expected[0]==current and im.containing(current)==expected,
                'fixed unwind fragment mismatch '+hex(current))
        require(im.root(current)==fragments[0],'unwind root mismatch')
        a,b,u=expected
        fragment_rows.append(dict(region(im,a,b,'unwind_fragment'),unwind_rva=hex(u)))
        current=b
    require(current==end,'incomplete fixed unwind range')
    instructions=list(im.md.disasm(im.read(entry,code_end-entry),entry))
    require(len(instructions)==count and sum(i.size for i in instructions)==code_end-entry,
            'code decode count/extent mismatch '+hex(entry))
    by_addr={i.address:i for i in instructions}
    relocations=[]
    indirect=[]
    for i in instructions:
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                relocations.append(dict(kind='rip_address' if i.mnemonic=='lea' else 'rip_memory',
                    rva=hex(i.address),target_rva=hex(i.address+i.size+op.mem.disp),
                    encoded_field_offset=i.disp_offset,encoded_field_size=i.disp_size))
        if i.group(cs.CS_GRP_CALL) or i.group(cs.CS_GRP_JUMP):
            require(len(i.operands)==1,'unexpected control operand count')
            is_call=i.group(cs.CS_GRP_CALL)
            op=i.operands[0]
            if op.type==X86_OP_IMM:
                target=op.imm
                local=target in by_addr
                require(is_call or local,'unexpected escaping direct jump')
                relocations.append(dict(kind='call_relative' if is_call else 'local_branch_relative',
                    rva=hex(i.address),target_rva=hex(target),target_is_local=local,
                    encoded_field_offset=i.imm_offset,encoded_field_size=i.imm_size))
            else:
                indirect.append(dict(rva=hex(i.address),kind='call_indirect' if is_call else 'jump_indirect',
                                     instruction=detail(i)))
    out.update(fragments=fragment_rows,code=region(im,entry,code_end,'code'),
               code_instruction_count=count,instructions=[detail(i) for i in instructions],
               relocations=relocations,indirect_control=indirect,
               critical_instructions={name:detail(by_addr[at]) for name,at in CRITICAL[entry].items()})
    if entry==0x94C9C0:
        require(im.read(0x94D299,3)==b'\x0f\x1f\x00','padding mismatch')
        out['padding']=region(im,0x94D299,0x94D29C,'alignment_padding_not_executed_by_return')
        tables=[]
        for a,b,base,load,add,jump in TABLES:
            values=list(struct.unpack('<9I',im.read(a,b-a)))
            require(values==TABLE_TARGETS and all(v in by_addr for v in values),'RVA table target mismatch')
            require(by_addr[base].mnemonic=='lea' and
                    by_addr[base].address+by_addr[base].size+by_addr[base].disp==0,
                    'table image-base materialization mismatch')
            require(by_addr[load].disp==a,'table load displacement mismatch')
            tables.append(dict(region(im,a,b,'nine_little_endian_u32_image_relative_targets'),
                entries_rva=[hex(v) for v in values],dispatch_instructions=[detail(by_addr[v]) for v in (base,load,add,jump)],
                relocation_note='RIP LEA materializes original image base; indexed load contains table RVA as disp32; '
                                'table entries are image-relative code targets. These are data relocations, not direct branches.'))
        out['jump_tables']=tables
    return out


def pin(im):
    strings={}
    for at,(expected,digest,site) in STRINGS.items():
        require(im.read(at,len(expected))==expected and sha(expected)==digest,'string mismatch')
        ins=im.instruction(site)
        require(ins is not None and ins.mnemonic=='lea' and
                ins.address+ins.size+ins.disp==at,'string use-site mismatch')
        strings[hex(at)]=dict(region(im,at,at+len(expected),'nul_terminated_ascii'),
                             text=expected[:-1].decode('ascii'),fixed_use_site=detail(ins))
    return dict(schema='hd2.departure.fixed-callees.v1',source_sha256=EXPECTED,
        capture_identity_sha256=im.report['capture_sha256'],replay_sha256=sha(Path(__file__).read_bytes()),
        decoder_version=cs.__version__,
        scope='Seven declared saved function ranges and three declared strings; no call-target expansion or whole-code scan.',
        bodies={hex(entry):pin_body(im,entry,spec) for entry,spec in BODIES.items()},strings=strings,
        limits=['Only captured code/unwind/string bytes are verified; runtime writable state and pointer targets are unavailable.',
                'Instruction/relocation inventories are evidence for later implementation, not native relocation output.',
                '94C9C0 jump tables and alignment padding are excluded from executable instruction count.',
                '94BE10 and all other unlisted callees remain boundaries. Their correctness, allocation, resource ownership and callback reentry are not proved.',
                'No claim of pending-target runtime reachability, unchanged roster across callbacks, or successful eight-account gameplay.'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--compare',type=Path,help='Require exact equality with an already-generated evidence file.')
    args=p.parse_args()
    require(not args.output.exists(),'refusing to overwrite output')
    result=pin(Image(args.capture))
    payload=(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode('utf-8')
    if args.compare:
        require(args.compare.read_bytes()==payload,'recheck differs from evidence')
    args.output.write_bytes(payload)
    print(json.dumps(dict(output=str(args.output),sha256=sha(payload),bodies=len(BODIES),
                          code_instructions=sum(v[2] for v in BODIES.values()),strings=len(STRINGS),
                          exact_compare_passed=bool(args.compare))))


if __name__=='__main__':
    main()
