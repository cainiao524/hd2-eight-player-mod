"""Component260 capacity/lifecycle closure from a pinned saved capture only."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP, X86_REG_RBX, X86_REG_EBX, X86_REG_XMM6

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image, EXPECTED, require, row

PRIOR = {
    'player_component_capacity_evidence.json':'4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147',
    'spawn_callback_registration_evidence_v2.json':'142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109',
    'property_dispatch_evidence.json':'9cabca2fa61fd59e9c776230da80ad68716f947c46f56c6b9c203ba011d0d55d',
    'component238_lifecycle_evidence_v2.json':'ac68b8cc938dc56288c9db7fa9a41d8a64f84fdd353fee6ff3414f6c35e0424b',
}
TABLES = {0xF0B6F0:0x544F30, 0xF0C110:0x544FD0, 0xF0CB30:0x545130,
          0xF0D550:0x545160, 0xF0DF70:None, 0xF0E990:0x5450A0,
          0xF0F3B0:0x5452A0, 0xF0FDD0:None, 0xF107F0:0x5452B0, 0xF11210:None}
ROOTS = {
    0x544F30:'simple_append', 0x544FD0:'classified_append', 0x5450A0:'remove_and_compact',
    0x545130:'property_builder_wrapper', 0x545160:'post_property_callback',
    0x7992D0:'copy_four_rows_and_repair_map', 0x7994E0:'nine_property_slots_builder',
    0x799790:'receive_36_byte_property_record', 0x7998B0:'initialize_64_rows_128_map_buckets',
    0x799CA0:'grow_map_and_rehash', 0x799EA0:'grow_all_four_row_arrays',
    0x79A420:'prefix_promotion_and_record_swap', 0x79A970:'prefix_demotion_and_record_swap',
    0xB29410:'register_tag_B1_alias', 0x172F790:'map_insert', 0x172F8A0:'map_remove',
}
SPANS = {
    'component_initialize_register_neighbor':(0x5567C0,0x5567EA),
    'global_publish_and_next_member':(0x568FEE,0x56900A),
    'destroy_five_backings_and_unregister':(0x565E77,0x565F10),
    'property_dispatch_owner_alias':(0xBD1DE1,0xBD1DF7),
    'owner_batch_capacity_and_partition':(0x57EB2B,0x57EBCF),
}
PINS = [0xFDA352,0xFDA360,0xFDA375,0x551B7A,0x551B7D,0x568236,0x568239,0x568242,
        0xBC2D85,0x576D0D,0x576D15]
ASSERT_ASM = {
    0x7998CA:'mov dword ptr [rcx + 4], 0x40',
    0x7998F5:'mov qword ptr [rbx + 0x38], rax',
    0x79990C:'lea eax, [rax*2 - 1]',
    0x7999AA:'mov qword ptr [rbx + 0x18], rax',
    0x799AB1:'mov qword ptr [rbx + 0x40], rax',
    0x799AD3:'imul rdx, rax, 0x178',
    0x799AEC:'mov qword ptr [rbx + 0x48], rax',
    0x799B0E:'lea rdx, [rax + rax*8]',
    0x799B12:'shl rdx, 2',
    0x799B1E:'mov qword ptr [rbx + 0x50], rax',
    0x799B93:'mov dword ptr [rbx + 0x30], 2',
    0x799BD4:'mov qword ptr [rbx + 0x20], rax',
    0x799BD8:'mov dword ptr [rbx + 0x28], ecx',
    0x799BDB:'mov dword ptr [rbx + 0x2c], edx',
    0x544FF4:'cmp eax, dword ptr [rdi + 0x28]',
    0x545004:'cmp eax, dword ptr [rdi + 4]',
    0x799EDF:'mov r8d, eax',
    0x799EE2:'mov dword ptr [rbp + 4], eax',
    0x799F1D:'mov qword ptr [rbp + 0x38], rax',
    0x799F86:'mov qword ptr [rbp + 0x40], rax',
    0x799FEA:'mov qword ptr [rbp + 0x48], rax',
    0x79A049:'mov qword ptr [rbp + 0x50], rax',
    0x799E81:'movups xmmword ptr [rbp + 0x20], xmm0',
    0x799E85:'mov qword ptr [rbp + 0x18], r14',
    0x799E89:'movsd qword ptr [rbp + 0x30], xmm1',
    0x7992FB:'mov qword ptr [r8 + r14*8], rax',
    0x79930C:'mov qword ptr [r8 + r14*8], rax',
    0x799310:'imul r8, r14, 0x178',
    0x799317:'imul rax, r10, 0x178',
    0x799326:'mov ecx, 2',
    0x7993CC:'lea rax, [r14 + r14*8]',
    0x7993D8:'mov rdx, qword ptr [r9 + 0x50]',
    0x7993F8:'mov dword ptr [r8 + 0x20], eax',
    0x799466:'mov dword ptr [r8 + 4], r14d',
    0x799813:'mov r8, qword ptr [rbx + 0x50]',
    0x79981E:'lea r9, [rcx + rcx*8]',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    priors={}
    for name,digest in PRIOR.items():
        data=(HERE/name).read_bytes()
        require(sha(data)==digest,'prior changed: '+name)
        priors[name]=json.loads(data)
    im=Image(args.evidence)
    e=next(e for e in priors['player_component_capacity_evidence.json']['entries'] if e['component_index']==260)
    require(e['entry']=='0x544fd0' and e['global_rva']=='0x3326a50','prior component identity changed')
    require(sha(im.read(0x544FD0,0xCE))==e['sha256'],'append bytes differ from prior')
    cache={}
    def instruction(addr):
        f=im.containing(addr)
        require(f is not None,'no unwind '+hex(addr))
        if f[0] not in cache:
            raw=im.read(f[0],f[1]-f[0]);ds=list(im.md.disasm(raw,f[0]))
            require(sum(i.size for i in ds)==len(raw),'incomplete decode')
            cache[f[0]]={i.address:i for i in ds}
        require(addr in cache[f[0]],'not instruction boundary '+hex(addr))
        return cache[f[0]][addr]
    def ann(i):
        return dict(**row(i),rip_targets=[hex(i.address+i.size+o.mem.disp) for o in i.operands
                    if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP])
    def span(a,b):
        raw=im.read(a,b-a);ds=list(im.md.disasm(raw,a))
        require(sum(i.size for i in ds)==len(raw),'incomplete span')
        for i in ds:require(instruction(i.address).bytes==i.bytes,'invalid span boundary')
        return dict(start=hex(a),end_exclusive=hex(b),sha256=sha(raw),instructions=[ann(i) for i in ds])

    start,end=0x556D90,0x55E1E3
    raw=im.read(start,end-start)
    init_sha='22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2'
    require(sha(raw)==init_sha and len(raw)==2127*14+1 and raw[-1]==0xC3,'registration initializer changed')
    require(instruction(0x568239).op_str=='0x556d90','registration entry call changed')
    assignments={}
    for n in range(0,len(raw)-1,14):
        pair=raw[n:n+14]
        require(pair[:3]==b'\x48\x8d\x05' and pair[7:10]==b'\x48\x89\x81','unexpected registration encoding')
        slot=struct.unpack_from('<i',pair,10)[0]
        require(slot not in assignments,'duplicate slot')
        assignments[slot]=(start+n+7+struct.unpack_from('<i',pair,3)[0],start+n,pair)
    callbacks=[]
    for base,target in TABLES.items():
        v=assignments.get(base+260*8)
        if target is None:
            require(v is None,'unassigned registration slot changed')
            callbacks.append(dict(table=hex(base),slot=hex(base+260*8),target=None,
                caveat='No assignment in this initializer; zero or runtime value not established.'))
        else:
            require(v and v[0]==target,'callback target changed')
            callbacks.append(dict(table=hex(base),slot=hex(base+260*8),target=hex(target),
                instructions=[ann(i) for i in im.md.disasm(v[2],v[1])]))

    roots={root:[] for root in ROOTS};batch_writes=[]
    for f in im.functions:
        root=im.root(f[0])[0]
        if root in roots:
            roots[root].append(span(f[0],f[1]))
        if root==0x576CF0 and f[0]<0x57EBCF and f[1]>0x576D0D:
            for i in im.md.disasm(im.read(f[0],f[1]-f[0]),f[0]):
                if 0x576D0D<=i.address<0x57EBCF and set(i.regs_access()[1])&{X86_REG_RBX,X86_REG_EBX,X86_REG_XMM6}:
                    batch_writes.append(ann(i))
    require(all(roots.values()),'missing full root')
    require([r['rva'] for r in batch_writes]==['0x576d0d','0x576d15'],'owner or threshold register changed in batch span')
    spans={label:span(a,b) for label,(a,b) in SPANS.items()}
    pins=[ann(instruction(a)) for a in PINS]
    for addr,expected in ASSERT_ASM.items():
        i=instruction(addr)
        require(i.mnemonic+' '+i.op_str==expected,'semantic pin changed '+hex(addr))
        pins.append(ann(i))
    # Source chains explicitly connect callback global, published member and receiver.
    require(ann(instruction(0x568FF5))['rip_targets']==['0x3326a50'],'published global changed')
    require(instruction(0x568FEE).op_str=='rax, [rbx + 0xeb5e10]','owner base changed')
    require(ann(instruction(0x544FE4))['rip_targets']==['0x3326a50'],'callback global changed')
    require(instruction(0xBD1DE4).op_str=='rcx, [rbx + 0xeb5e10]' and instruction(0xBD1DF2).op_str=='0x799790','receiver alias changed')

    leaves=[]
    for entry,end,callsite,tail in [(0x5452A0,0x5452A8,None,0x79A420),
                                   (0x5452B0,0x5452B8,None,0x79A970),
                                   (0x21012E4,0x21013A6,0x799EC2,0x2103E50)]:
        if callsite:
            require(instruction(callsite).op_str==hex(entry),'leaf direct call changed')
        else:require(entry in TABLES.values(),'leaf lacks registered entry')
        raw=im.read(entry,end-entry);ds=list(im.md.disasm(raw,entry))
        require(sum(i.size for i in ds)==len(raw),'incomplete leaf')
        addresses={i.address for i in ds}
        for i in ds:
            if i.mnemonic.startswith('j') and i.operands[0].type==X86_OP_IMM:
                require(i.operands[0].imm in addresses or i.operands[0].imm==tail,'unclosed leaf branch')
        leaves.append(dict(entry=hex(entry),end_exclusive=hex(end),sha256=sha(raw),
            direct_call=hex(callsite) if callsite else None,registered=callsite is None,external_tail=hex(tail),
            instructions=[ann(i) for i in ds]))

    literals=[]
    for addr,size,expected in [(0x799EB4,8,32.0),(0x799CC6,4,0.5),(0x576D15,4,struct.unpack('<f',bytes.fromhex('cdcc4c3f'))[0])]:
        i=instruction(addr);o=i.operands[1]
        require(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP,'not RIP scalar')
        rva=i.address+i.size+o.mem.disp;b=im.read(rva,size)
        value=struct.unpack('<d' if size==8 else '<f',b)[0]
        require(value==expected,'capacity scalar changed')
        literals.append(dict(instruction=ann(i),rva=hex(rva),bytes=b.hex(),value=value))

    arrays=[dict(pointer_offset=hex(off),stride=stride,capacity=64,allocated_bytes=stride*64,
                 slot7_end=stride*8,slots_0_to_7_fit=stride*8<=stride*64)
            for off,stride in [(0x38,8),(0x40,8),(0x48,0x178),(0x50,0x24)]]
    # Small-integer map sizes derived from the decoded initialization/growth pattern.
    def p2(x):return 1<<(x-1).bit_length()
    scenarios=[]
    for initial_total in [0,4,7,63,64,127,128]:
        rowcap=64
        while rowcap<initial_total:rowcap+=32
        mapcap=128
        while mapcap<initial_total:mapcap=p2(mapcap+(mapcap+1)//2)
        before=(rowcap,mapcap)
        if initial_total>=mapcap:mapcap=p2(mapcap+(mapcap+1)//2)
        if initial_total>=rowcap:rowcap+=32
        scenarios.append(dict(existing_count=initial_total,before_row_capacity=before[0],before_map_capacity=before[1],
            after_row_capacity=rowcap,after_map_capacity=mapcap,new_ordinal=initial_total,
            fits=initial_total<rowcap and initial_total<mapcap))
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],prior_sha256=PRIOR,
        component_index=260,reference_type='WeatheringComponentData',runtime_membership_verified=False,
        identity=dict(global_rva='0x3326a50',owner_global='0x346bfc8',owner_offset='0xeb5e10',
            next_owner_member='0xeb5e68',descriptor_bytes='0x58',property_receiver='0x799790',
            closes_prior_property_dispatch_null_component=True,
            chain=['callback260 F0C110 ->544FD0 -> global3326A50','568FEE/568FF5 publish owner+EB5E10 to same global',
                   'BC2D85 loads same owner;BD1DE4/BD1DF2 pass owner+EB5E10 to799790']),
        registration_initializer=dict(sha256=init_sha,validated_pairs=len(assignments),callbacks=callbacks),
        functions=[dict(root=hex(root),purpose=ROOTS[root],fragments=roots[root]) for root in ROOTS],
        proven_leaves=leaves,spans=spans,pins=pins,literals=literals,
        batch_register_writes=dict(range=['0x576d0d','0x57ebcf'],registers=['RBX/EBX','XMM6'],writes=batch_writes),
        layout=dict(row_capacity='0x4',high_water='0x8',total_count='0xc',active_count='0x10',prefix_count='0x14',
            owning_map_pointer='0x18',map_pointer='0x20',map_bucket_count='0x28',map_sentinel='0x2c',map_multiplier='0x30',
            initial_row_capacity=64,initial_map_buckets=128,map_pair_stride=8,map_multiplier_value=2,
            row_arrays=arrays,initial_data_backing_bytes=sum(a['allocated_bytes'] for a in arrays),initial_map_backing_bytes=128*8,
            tag='0xb1',tag_registry_global='0x3326e68',tag_registry_list_count='0x6c0',tag_registry_entries='0x6c8'),
        growth=dict(join_checks='Before write: compare total with map bucket capacity then row capacity; call grow helpers when >=.',
            row_helper='0x799ea0',row_increment=32,row_formula='old_capacity + positive-integral result of21012E4(32.0) = old+32',
            row_actions='Allocate/clear/copy/free each of +38,+40,+48,+50; copy old capacity rows, update pointers; allocation failure not checked locally.',
            map_helper='0x799ca0',map_formula='power_of_two_ceiling(old + ceil(float32(old)*0.5)) for the small positive capacities considered',
            map_actions='Allocate new pairs, sentinel-initialize all buckets, reinsert every non-sentinel old pair, free old backing, publish descriptor and owning pointer.',
            batch='576CF0 additionally checks counts against ceil(float32(capacity)*float32(0.8)) then calls same growers before prefix moves.',
            scenarios=scenarios,scenarios_are_static_arithmetic_not_runtime_tests=True),
        lifecycle=dict(initialization='7998B0 initializes total/active/prefix, allocates64 rows and128 map buckets; no claim that this function initializes high_water+8.',
            move='7992D0(self,destination,source) copies both qword rows, all0x178 primary bytes, all0x24 property bytes, then writes the moved entity map value to destination. Source bytes are not cleared.',
            removal='5450A0 removes entity map entry, updates total/active/prefix partitions, calls/tails7992D0 to fill holes.',
            prefix='79A420 increments prefix and swaps entity/primary/property rows while clearing destination +40 row;79A970 decrements prefix and swaps +40 as well. Both repair entity map ordinals.',
            destruction='565E77..565EEF frees backing pointers+38,+18,+40,+48,+50;565EF6..565F0B unregisters alias from list6C0.',
            property='799790 maps entity ID to ordinal and writes36 bytes through dynamic pointer+50, without a four-player limit or safe missing-ID guard.'),
        eight_slot_decision=dict(capacity_patch_required_for_slots_0_to_7=False,
            scope='Existing constructor/backing sizing, append, grow, copy and property-receive paths; not a blanket proof of every consumer.',
            reason='Default capacity64 and map128 already exceed8, with all four rows dynamically grown together; no four-slot inline overflow to repair here.',
            conditions=['Successful normal allocation and initialized object.','Valid entity membership and ordinal within total/capacity.',
                        'Total is component entity count, not a proven player-only counter; other instances can invoke growth.',
                        'No runtime fifth-player path or engine/platform allowance has been established.']),
        limits=['Only fixed capture/workspace read; no live query/read, probe, capture or game patch.',
                'Reference type name is from prior offline metadata; installed/runtime metadata match is not asserted.',
                'Unassigned initializer table slots are not asserted null.',
                'Rounding leaf external NaN tail2103E50 is recorded but not analyzed; small positive integral capacity cases do not use it.',
                'Allocator implementation and OOM recovery not proved; this code calls allocator slots58/60 with no local null-check.',
                'Memory helper calls208AAA0/20988F0 are interpreted as existing zero/copy operations; this report does not re-audit full CRT implementations.',
                'No exhaustive audit of all global consumers or schema variants; no claim of overall eight-player compatibility.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),roots=len(roots),
        root_instructions=sum(len(f['instructions']) for fs in roots.values() for f in fs),
        leaf_instructions=sum(len(l['instructions']) for l in leaves),pins=len(pins))))


if __name__=='__main__':main()
