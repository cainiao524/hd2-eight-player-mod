"""C++ property/reset bytes, original callbacks and original GS handlers offline."""
import argparse,ctypes as c,json,struct
from collections import Counter
from pathlib import Path
from component33_initialization_fixture import *
from native_component33_library import Library,Addresses,Image
from generate_component33_templates import REFERENCE

def gs_cases(lib):
    cases=[]
    for game in (core.G,core.G+0x80000000):
        for corrupt in (False,True):
            f=Fixture(lib,'property',8,7,game=game);art=f.artifact
            for part in n.profile()['gs_handler'].values():
                if isinstance(part,dict):f.put(game+int(part['rva'],16),bytes.fromhex(part['bytes_hex']))
            dispatcher=core.STACK+0x200;frame=core.RSP-120;call_rsp=core.STACK+0x4008
            uw=struct.unpack_from('<I',art['image'],art['table_offset']+20)[0]
            f.put(dispatcher+8,core.u64(f.start));f.put(dispatcher+16,core.u64(f.start+art['table_offset']+12));f.put(dispatcher+56,core.u64(f.start+uw+32))
            f.put(frame+64,core.u64(COOKIE^frame^int(corrupt)));f.put(call_rsp,core.u64(f.stop))
            uc=core.unicorn.Uc(core.unicorn.UC_ARCH_X86,core.unicorn.UC_MODE_64)
            for page in f.pages:uc.mem_map(page,4096);uc.mem_write(page,f.read(page,4096))
            for key,value in {**core.SEEDS,'rcx':0,'rdx':frame,'r8':0,'r9':dispatcher,'rsp':call_rsp}.items():uc.reg_write(core.reg(key),value)
            trace=[];events=[]
            def hook(uc,pc,size,data):
                trace.append(pc)
                if pc==game+0x2088770:
                    n.need(uc.reg_read(core.reg('rcx'))==COOKIE^int(corrupt),'GS cookie argument')
                    events.append('corrupt' if corrupt else 'valid')
                    if corrupt:uc.emu_stop()
                    else:
                        sp=uc.reg_read(core.reg('rsp'));uc.reg_write(core.reg('rip'),int.from_bytes(uc.mem_read(sp,8),'little'));uc.reg_write(core.reg('rsp'),sp+8)
                elif pc==f.stop:events.append('return');uc.emu_stop()
            uc.hook_add(core.unicorn.UC_HOOK_CODE,hook);uc.emu_start(f.start+art['handler_offset'],0,count=500)
            n.need(events==(['corrupt'] if corrupt else ['valid','return']),'GS control flow')
            n.need(all(game+x in trace for x in (0x21044A0,0x21044C0,0x2088770)),'GS saved code not reached')
            if not corrupt:n.need(uc.reg_read(core.reg('rax'))==1 and uc.reg_read(core.reg('rsp'))==call_rsp+8 and all(uc.reg_read(core.reg(k))==v for k,v in core.SEEDS.items()),'GS return ABI')
            cases.append(dict(game_base=hex(game),corrupt=corrupt,events=events,instructions=len(trace)))
    return cases

def validate(lib,zig):
    contexts={k:set() for k in n.INITIALIZE_KINDS};runs=[]
    def execute(f,expected='return'):
        f.execute(expected);contexts[f.kind].update(f.contexts)
        runs.append(dict(kind=f.kind,total=f.t,ordinal=f.ordinal,original=f.original,callback=f.callback,outcome=f.outcome,descriptor_count=f.descriptor_count,game_base=hex(f.game)))
        return f
    for original in (True,False):
        for t in range(1,5 if original else 9):
            for ordinal in range(t):
                for mode in ('zero','known','unknown','mixed'):
                    execute(Fixture(lib,'property',t,ordinal,original=original,mode=mode,callback=True,descriptor_count=124 if mode=='known' else 0))
                execute(Fixture(lib,'reset',t,ordinal,original=original,callback=True))
    for kind in n.INITIALIZE_KINDS:
        execute(Fixture(lib,kind,8,7,callback=False));execute(Fixture(lib,kind,8,7,game=core.G+0x80000000,callback=True))
        for address,blob in ((core.G+0x33267B8,core.u64(core.S+8)),(core.S+8,core.u32(9)),(core.S+12,core.u32(9)),
                             (core.S+16,core.u32(9)),(core.S+0x58,core.u64(core.S+0x18)),(core.S+0x60,core.u32(16)),
                             (core.S+0x64,core.u32(1)),(core.E+7*0x40+8,core.u32(999)),(core.G+0x3483C34,core.u32(57)),
                             (core.B+56,core.u64(core.E)),(core.S+0x14+8,core.u32(0)),(core.S+0x14+16,core.u32(57))):
            f=Fixture(lib,kind,8,7);f.put(address,blob);execute(f,'reject')
        for total,ordinal in ((0,0),(4,5)):
            execute(Fixture(lib,kind,total,ordinal),'reject')
    for count in (125,128,0xFFFFFFFF):execute(Fixture(lib,'property',8,7,descriptor_count=count),'reject')
    for field in ('entity','descriptors','count','list','input'):
        f=Fixture(lib,'property',8,7)
        if field in ('entity','descriptors'):f.uc.reg_write(core.reg('rdx' if field=='entity' else 'r9'),0)
        else:f.put({'count':core.RSP+40,'list':core.RSP+48,'input':core.G+0x347CDD8}[field],core.u64(0))
        execute(f,'reject')
    wrapper_refusals=[]
    for kind in n.INITIALIZE_KINDS:
        f=Fixture(lib,kind,8,7,callback=True);f.put(core.B+56,core.u64(core.E));before=f.state()
        f.uc.emu_start(f.entry,0,count=10000)
        n.need(f.outcome=='reject' and f.state()==before and not f.events and f.uc.reg_read(core.reg('rsp'))==f.helper_rsp,'wrapper refusal state')
        n.need(all(core.STACK<=a and a+size<=core.STACK+0x10000 for a,size in f.writes),'wrapper refusal data write')
        wrapper_refusals.append(dict(kind=kind,frame_bytes=core.RSP-f.helper_rsp,data_unchanged=True))
    allocation=[]
    for original in (True,False):
        f=Fixture(lib,'property',4,3,original=original,null_allocate=True);faults=[]
        def invalid(uc,access,address,size,value,data):faults.append(address);return False
        f.uc.hook_add(core.unicorn.UC_HOOK_MEM_INVALID,invalid)
        try:f.uc.emu_start(f.entry,0,count=100000)
        except core.unicorn.UcError:pass
        n.need(faults==[0] and f.events==['allocate'],'property null allocation fault')
        row=f.read(f.slot('secondary',3),56)
        n.need(row[:24]==f.expected_secondary[:24] and row[24:]==f.records['secondary',3][24:] and f.int32(COUNT)==0,'property partial write control')
        allocation.append(dict(original=original,secondary_bytes_written_before_fault=24,descriptors_added=0))
    # Classify an entity into a new ordinal, then run property + reset on that
    # actual arrangement. Subsequent initialization must follow the map.
    from validate_component33_classify import Fixture as ClassifyFixture
    for target in range(3,8):
        previous=ClassifyFixture(lib,'enter',8,8,3,target).execute()
        for kind in n.INITIALIZE_KINDS:
            f=Fixture(lib,kind,8,3);f.d=8;f.p=4
            f.put(core.S,previous.read(core.S,0x400));f.put(core.B,previous.read(core.B,0x490));f.uc.reg_write(core.reg('rdx'),core.E+target*0x40)
            f.records={(name,i):f.read(f.slot(name,i),size) for name,(_,_,size) in core.LAYOUT.items() for i in range(8)}
            f.table=[(f.int32(core.S+0x14+8*i),f.int32(core.S+0x18+8*i)) for i in range(8)]
            previous=execute(f)
    accepted=rejected=0
    for kind in n.INITIALIZE_KINDS:
        placements=[REFERENCE]
        for key in REFERENCE:
            for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):placements.append({**REFERENCE,key:value})
        for key in ('component_address','storage_address'):placements.append({**REFERENCE,key:REFERENCE[key]+0x100000000})
        for rva,size in n.EXTRA_GLOBAL_REGIONS:placements.append({**REFERENCE,'component_address':REFERENCE['game_base']+rva})
        for a in placements:
            try:expected=n.build(kind,**a)['image']
            except (ValueError,struct.error,OverflowError):expected=None
            out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.build(n.ALL_KINDS.index(kind)+1,Addresses(**a),out)
            if expected is None:n.need(rc!=0 and not any(bytes(out)),'initializer accepted invalid placement');rejected+=1
            else:n.need(rc==0 and bytes(out.data[:out.bytes])==expected,'initializer C++ mismatch');accepted+=1
    exe=n.PROJECT/'build/native_component33_initialize_unwind_test.exe'
    core.run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_initialize_unwind_test.c','-o',exe])
    windows={};artifacts=[lib.path,exe];variants={}
    for kind in n.INITIALIZE_KINDS:
        art=lib.candidate(kind,**addresses(kind));rows=sorted(contexts[kind]);bad=bytearray(art['image'])
        table_row=1 if kind=='property' else 2;uw=struct.unpack_from('<I',bad,art['table_offset']+12*table_row+8)[0]
        bad[uw+(10 if kind=='property' else 14)]^=1
        start,end,_=struct.unpack_from('<III',art['image'],art['table_offset']+12*table_row)
        row=bytearray(next(r for r in rows if start+64<=struct.unpack_from('<I',r)[0]<end and struct.unpack_from('<Q',r,20)[0]!=core.SEEDS['rbp']))
        struct.pack_into('<I',row,8,1);expected=struct.pack('<9Q',*(core.SEEDS[k] for k in core.NAMES),core.G+0x10500000)
        def pack(blob,items):return struct.pack('<4I',len(blob),art['code_bytes'],art['table_offset'],len(items))+blob+expected+b''.join(items)
        fixture=n.PROJECT/'build'/('component33-'+kind+'-unwind.bin');fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+pack(bad,[row])+pack(art['image'],rows))
        windows[kind]=json.loads(core.run([exe,fixture]));artifacts.append(fixture)
        n.need((windows[kind]['gs_handler_dispatches']>0)==(kind=='property'),'missing property GS handler dispatch')
        variants[kind]={k:art[k] for k in ('code_bytes','body_offset','table_offset','function_count','handler_offset')}
    paths=['tools/validate_component33_initialize.py','tools/component33_initialization_fixture.py','tools/validate_component33_images.py','tools/validate_component33_classify.py',
           'tools/native_component33_image.py','tools/native_component33_library.py','tools/generate_component33_templates.py','native-component33.lock.json',
           'mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h',
           'tests/component33_image_dll.cpp','tests/native_component33_initialize_unwind_test.c']
    return dict(schema='hellforge_component33_initialization_validation_v1',passed=True,functional_runs=len(runs),runs=runs,
                run_types=dict(Counter(('original_' if r['original'] else 'candidate_')+r['kind']+'_'+r['outcome'] for r in runs)),
                windows=windows,windows_unwind_contexts=sum(v['windows_unwind_contexts'] for v in windows.values()),variants=variants,
                gs_execution=gs_cases(lib),accepted_placements=accepted,rejected_placements=rejected,
                wrapper_refusals=wrapper_refusals,null_allocation_controls=allocation,classify_property_reset_sequences=5,
                descriptor_capacity=128,maximum_initial_descriptor_count=124,descriptors_appended=4,
                source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in artifacts},
                external_helpers_are_contract_stubs=True,property_tables_are_synthetic=True,allocation_failure_rollback=False,
                full_component33_lifecycle=False,production_owner_bound=False,game_access=False,
                runtime_verified=False,multiplayer_verified=False,native_execution_of_game_bodies=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps({k:r[k] for k in ('passed','functional_runs','run_types','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
