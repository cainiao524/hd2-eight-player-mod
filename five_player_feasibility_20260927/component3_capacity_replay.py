"""Offline component3 initial capacity, growth and pointer-based layout.

Only reads the fixed saved image and workspace evidence. Does not execute game code.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

ROOTS = [0x5164C0, 0x516540, 0x5165C0, 0x516620, 0x6B5620,
         0x6B5750, 0x6B5A40, 0x6B5A90, 0x6B5C90, 0x6B5E30, 0x6B5EB0]
TABLES = [0xF0B6F0,0xF0C110,0xF0CB30,0xF0D550,0xF0DF70,
          0xF0E990,0xF0F3B0,0xF0FDD0,0xF107F0,0xF11210]
REGISTERED = {0xF0B6F0:0x5164C0,0xF0C110:0x516540,
              0xF0D550:0x516620,0xF0E990:0x5165C0}
SPANS = {'owner_identity':[(0x551B7A,0x551B82),(0x568236,0x568249)],
         'owner_publish_and_next_member':[(0x56825E,0x56827A)],
         'owner_constructor_and_registry':[(0x551BB9,0x551C3A)]}
CRITICAL = {
    0x56825E:'lea rax, [rbx + 0xe8]',
    0x56826C:'lea rax, [rbx + 0x128]',
    0x551BE5:'call 0x6b5750',
    0x6B5763:'mov qword ptr [rcx + 8], rdi',
    0x6B576A:'mov dword ptr [rcx], 0x200',
    0x6B5770:'mov edx, 0x1000',
    0x6B5793:'mov qword ptr [rbx + 0x30], rax',
    0x6B5846:'mov qword ptr [rbx + 0x10], rax',
    0x6B5948:'mov qword ptr [rbx + 0x38], rax',
    0x6B59E5:'mov qword ptr [rbx + 0x18], rax',
    0x6B59E9:'mov dword ptr [rbx + 0x20], ecx',
    0x6B59EF:'mov dword ptr [rbx + 0x28], 2',
    0x516557:'cmp eax, dword ptr [rbx + 0x20]',
    0x51655F:'call 0x6b5a90',
    0x516567:'cmp eax, dword ptr [rbx]',
    0x51656E:'call 0x6b5c90',
    0x5165B5:'jmp 0x172f790',
    0x6B5C75:'mov qword ptr [rbp + 0x10], r14',
    0x6B5CCC:'mov dword ptr [rsi], eax',
    0x6B5D04:'mov qword ptr [rsi + 0x30], rax',
    0x6B5D65:'mov qword ptr [rsi + 0x38], rax',
    0x6B565A:'mov qword ptr [rcx + r8], rax',
    0x6B5666:'mov qword ptr [rcx + r8], rax',
    0x6B56D2:'mov dword ptr [r8 + 4], esi',
    0x516719:'cmp edi, 0x40',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def spread_then_increment(value):
    """The repeated SHR/OR sequence for small positive uint32 capacity inputs."""
    x = (value-1) & 0xFFFFFFFF
    out = x
    for _ in range(31):
        out = (out >> 1) | x
    return (out+1) & 0xFFFFFFFF


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args();out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    prior=HERE/'player_component_capacity_evidence.json'
    require(sha(prior.read_bytes())=='4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147','prior changed')
    im=Image(args.evidence);cache={}
    def decode(f):
        if f not in cache:
            ds=list(im.md.disasm(im.read(f[0],f[1]-f[0]),f[0]))
            require(sum(i.size for i in ds)==f[1]-f[0],'incomplete decode')
            cache[f]={i.address:i for i in ds}
        return cache[f]
    def instruction(a):
        f=im.containing(a)
        require(f is not None and a in decode(f),'unproven instruction boundary')
        return decode(f)[a]
    functions=[]
    for r in ROOTS:
        fs=[f for f in im.functions if im.root(f[0])[0]==r]
        require(fs and fs[0][0]==r,'missing root')
        functions.append(dict(root=hex(r),fragments=[dict(bounds=[hex(v) for v in f],
            sha256=sha(im.read(f[0],f[1]-f[0])),instructions=[row(i) for i in decode(f).values()]) for f in fs]))
    pins={}
    for name,spans in SPANS.items():
        pins[name]=[]
        for a,b in spans:
            f=im.containing(a);require(f is not None and b<=f[1],'span crosses boundary')
            ds=[i for addr,i in decode(f).items() if a<=addr<b]
            require(sum(i.size for i in ds)==b-a,'unaligned span')
            pins[name].extend(dict(**row(i),root=hex(im.root(i.address)[0])) for i in ds)
    for a,asm in CRITICAL.items():
        i=instruction(a);require(i.mnemonic+' '+i.op_str==asm,'critical pin changed '+hex(a))
    global_pins=[]
    for a,dst in [(0x568265,0x3326430),(0x51654A,0x3326430),(0x551BEA,0x3326E68)]:
        i=instruction(a)
        found=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(found==[dst],'global target mismatch')
        global_pins.append(dict(instruction=row(i),target=hex(dst)))

    init=im.read(0x556D90,0x55E1E3-0x556D90)
    require(sha(init)=='22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2','initializer changed')
    assignments={}
    for at in range(0,len(init)-1,14):
        b=init[at:at+14];require(b[:3]==b'\x48\x8d\x05' and b[7:10]==b'\x48\x89\x81','initializer shape')
        slot=struct.unpack_from('<i',b,10)[0]
        assignments[slot]=dict(target=0x556D90+at+7+struct.unpack_from('<i',b,3)[0],
                              instructions=[row(i) for i in im.md.disasm(b,0x556D90+at)])
    registrations=[]
    for t in TABLES:
        item=assignments.get(t+3*8)
        require((item is not None)==(t in REGISTERED),'registration set changed')
        if item:require(item['target']==REGISTERED[t],'callback changed')
        registrations.append(dict(table=hex(t),slot=hex(t+3*8),assignment=item))
    constants=[]
    for a,r,fmt,value in [(0x6B5AB6,0x23C6AD0,'f',0.5),(0x6B5C9F,0x23C73D8,'d',256.0)]:
        i=instruction(a)
        target=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(target==[r],'constant address changed');raw=im.read(r,struct.calcsize(fmt))
        require(struct.unpack('<'+fmt,raw)[0]==value,'constant changed')
        constants.append(dict(instruction=row(i),rva=hex(r),bytes=raw.hex(),sha256=sha(raw),value=value))
    # Leaf start is established by two calls in complete captured roots.
    require(instruction(0x6B5AC1).op_str==instruction(0x6B5CAC).op_str=='0x21012e4','rounding entry changed')
    math_raw=im.read(0x21012E4,0x21013A6-0x21012E4)
    math_ds=list(im.md.disasm(math_raw,0x21012E4))
    require(sum(i.size for i in math_ds)==len(math_raw) and math_ds[-1].mnemonic=='ret','leaf body changed')
    # For 256.0 and the small positive integer half-capacities below, the
    # captured leaf's fractional-bit clearing leaves the bit pattern unchanged.
    integer_inputs=[]
    for value in [256,512,1024,2048]:
        bits=struct.unpack('<Q',struct.pack('<d',value))[0]
        shift=(0x33-((bits>>52)&0xFF))&0x3F
        mask=(~((1<<shift)-1))&0xFFFFFFFFFFFFFFFF
        require((bits&mask)==bits,'expected integral rounding domain changed')
        integer_inputs.append(dict(input=value,bits=hex(bits),shift=shift,result=value))
    require(spread_then_increment(512*2)==1024,'constructor bucket arithmetic')
    growth=[dict(old=n,increment=n//2,pre_round=n+n//2,new=spread_then_increment(n+n//2)) for n in [1024,2048,4096]]
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],runtime_verified=False,
        component_index=3,reference_name='TagComponentData',global_rva='0x3326430',
        functions=functions,owner_pins=pins,global_pins=global_pins,registrations=registrations,constants=constants,
        rounding_leaf=dict(start='0x21012e4',end_exclusive='0x21013a6',sha256=sha(math_raw),
            instructions=[row(i) for i in math_ds],entry_callers=[row(instruction(a)) for a in [0x6B5AC1,0x6B5CAC]],
            outside_branch='0x2103e50 for the NaN-related path; not decoded or needed by the selected finite integer cases',
            selected_integral_input_model=integer_inputs),
        layout=dict(owner_offset=0xE8,next_owner_member=0x128,object_span=0x40,
            array_capacity_field=0,initial_array_capacity=512,total_count_field=8,classified_count_field=12,
            initial_count_fields_zeroed=[8,12],highwater_field=4,highwater_initialization='Not established in this constructor.',
            bucket_backing_pointer=0x10,map_header=0x18,map_capacity_field=0x20,initial_buckets=1024,
            sentinel_field=0x24,multiplier_field=0x28,multiplier=2,
            entity_pointer_array=dict(pointer_field=0x30,stride=8,initial_bytes=4096),
            tag_value_array=dict(pointer_field=0x38,stride=8,initial_bytes=4096),
            initial_bucket_bytes=8192,all_arrays='Separate allocations, not four-slot arrays embedded after the header.'),
        growth=dict(arrays=dict(helper='0x6b5c90',increment=256,pointer_fields=[0x30,0x38],
            old_data_transfer_helper='0x20988f0',clear_helper='0x208aaa0',allocation_slot='api+58',release_slot='api+60'),
            hash=dict(helper='0x6b5a90',examples=growth,rehashes='all non-sentinel old buckets with multiplier2 and old ordinal values')),
        move=dict(helper='0x6b5620',copies=['entity pointer qword','tag value qword'],updates='moved entity ID map value to destination ordinal'),
        decision='The captured initialization and selected append paths are not fixed to four: they start with512 data rows and1024 hash buckets and include growth. No player4-to8 capacity replacement is indicated in this scoped component path.',
        limits=['Capacity covers component entities, not an exclusive player quota; current occupancy is unknown.',
                'Indirect allocation/release methods were not resolved or executed; allocation success, generic copy helper internals and live growth are not proven.',
                'No exhaustive audit of all global consumers, malformed input, lifetime, concurrency or current metadata equivalence.',
                'The tag-value loop limit0x40 is per-entity tag input, not a player count.',
                'No process access, capture, code execution, patch or multiplayer validation.'])
    result['full_root_instruction_count']=sum(len(f['instructions']) for x in functions for f in x['fragments'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),roots=len(functions),
                         full_root_instructions=result['full_root_instruction_count'])))


if __name__=='__main__':
    main()
