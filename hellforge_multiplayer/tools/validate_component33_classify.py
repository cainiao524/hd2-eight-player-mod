"""Execute emitted classification helpers and saved callback shims in Unicorn."""
import argparse,ctypes as c,json,struct
from collections import Counter
from pathlib import Path
import native_component33_image as n
from native_component33_library import Library,Addresses,Image
import validate_component33_images as core
from generate_component33_templates import REFERENCE
TEMP=0x18500500000
def addresses(kind,game=core.G):
    return {**core.addresses('mover',game), 'code_address':game+0x10600000+n.CLASSIFY_KINDS.index(kind)*0x10000}

class Fixture(core.Fixture):
    def __init__(self,lib,kind,t,d,p,ordinal,*,original=False,game=core.G,callback=True,fail_allocation=False):
        super().__init__(lib,'mover',t,d,p,ordinal=ordinal,original=original,game=game)
        self.kind=kind;self.artifact=lib.candidate(kind,**addresses(kind,game))
        f=n.profile()['functions'][kind]
        self.start=game+f['start'] if original else addresses(kind,game)['code_address']
        self.put(self.start,bytes.fromhex(f['body_hex']) if original else self.artifact['image'])
        self.put(game+0x3483C34,core.u32(0xFFFFFFFF));self.put(TEMP,b'\xa5'*0x1000)
        self.helpers={game+0x173B6F0:'init',game+0x173B8D0:'allocate',game+0x173BC20:'release'}
        for address in self.helpers:self.put(address,b'\xc3')
        self.helper_events=[];self.extra_writable=[];self.allocations=[];self.fail_allocation=fail_allocation
        self.uc.reg_write(core.reg('rdx'),core.E+ordinal*0x40)
        if callback:
            wrapper=n.profile()['classification_callbacks'][kind];blob=bytearray.fromhex(wrapper['body_hex'])
            n.need(blob[:4]==bytes.fromhex('488bd1e9'),'wrapper ABI changed')
            struct.pack_into('<i',blob,4,self.start-(game+wrapper['entry']+8))
            self.entry=game+wrapper['entry'];self.put(self.entry,bytes(blob));self.uc.reg_write(core.reg('rcx'),core.E+ordinal*0x40)
        else:self.entry=self.start
    def on_code(self,uc,pc,size,data):
        if pc in self.helpers:
            role=self.helpers[pc];rsp=uc.reg_read(core.reg('rsp'));rcx=uc.reg_read(core.reg('rcx'))
            n.need(rsp%16==8,'helper stack alignment');answer=0
            if role=='init':
                n.need(rcx==core.RSP-0x38,'temporary object location');self.put(rcx,core.u64(TEMP+0xF00))
            elif role=='allocate':
                size=uc.reg_read(core.reg('rdx'));alignment=uc.reg_read(core.reg('r8'))
                expected=(0x50,0x38) if self.kind=='enter' else (1,0x50,0x38)
                n.need(rcx==TEMP+0xF00 and alignment==4 and size==expected[len(self.allocations)],'allocation arguments')
                answer=0 if self.fail_allocation else TEMP+0x100*len(self.allocations)
                self.allocations.append((answer,size))
                if answer:self.extra_writable.append((answer,size))
            else:n.need(rcx==core.RSP-0x38,'temporary cleanup object')
            self.helper_events.append(role)
            self.put(rsp+8,b'\xc7'*32)
            for i,key in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):uc.reg_write(core.reg(key),0xCDCD000000000000+i)
            for i in range(6):uc.reg_write(core.reg('xmm'+str(i)),(0x123456789ABC0000+i)*(1+(1<<64)))
            uc.reg_write(core.reg('rax'),answer);uc.reg_write(core.reg('eflags'),0x246)
        super().on_code(uc,pc,size,data)
    def check_model(self):
        target=self.ordinal;boundary=self.p if self.kind=='enter' else self.p-1
        records=dict(self.records);mapping={key:value for key,value in self.table if key}
        if target!=boundary:
            for name in ('pointer','primary','secondary'):
                records[name,target],records[name,boundary]=records[name,boundary],records[name,target]
            if self.kind=='leave':records['byte',target]=records['byte',boundary]
            for index in (target,boundary):
                pointer=struct.unpack('<Q',records['pointer',index])[0];mapping[self.int32(pointer+8)]=index
        n.need([self.int32(core.S+off) for off in (8,12,16)]==[self.t,self.d,self.p+(1 if self.kind=='enter' else -1)],'classification counts')
        n.need(self.int32(core.S+4)==2,'classification changed high-water field')
        for (name,i),expected in records.items():n.need(self.read(self.slot(name,i),len(expected))==expected,'classification row mismatch '+str((self.kind,self.t,self.d,self.p,self.ordinal,name,i)))
        actual={self.int32(core.S+0x14+8*i):self.int32(core.S+0x18+8*i) for i in range(8) if self.int32(core.S+0x14+8*i)}
        n.need(actual==mapping,'classification map mismatch')
        if not self.original:n.need(self.read(core.S+0x70,0x248)==b'\xa5'*0x248,'classification changed old arrays')
        n.need(self.read(core.B-0x80,0x80)==b'\xb6'*0x80 and self.read(core.B+0x490,0x80)==b'\xb6'*0x80,'classification sidecar overrun')
        groups=(2 if self.kind=='enter' else 3) if target!=boundary else 0
        n.need(self.helper_events==['init','allocate','release','release']*groups,'temporary helper order')

def validate(lib,zig):
    contexts={k:set() for k in n.CLASSIFY_KINDS};runs=[]
    def execute(f,expected='return'):
        f.execute(expected);contexts[f.kind].update(f.contexts)
        runs.append(dict(kind=f.kind,total=f.t,dense=f.d,prefix=f.p,ordinal=f.ordinal,original=f.original,
                         outcome=f.outcome,callback=f.entry!=f.start,game_base=hex(f.game),helpers=len(f.helper_events)))
        return f
    for original in (True,False):
        for t in range(1,5 if original else 9):
            for d in range(1,t+1):
                for p in range(d+1):
                    for ordinal in range(d):
                        execute(Fixture(lib,'enter' if ordinal>=p else 'leave',t,d,p,ordinal,original=original))
    # A direct helper call retains its original entity-in-RDX ABI as well.
    for kind,p,index in (('enter',2,7),('leave',6,1)):
        execute(Fixture(lib,kind,8,8,p,index,callback=False))
        execute(Fixture(lib,kind,8,8,p,index,game=core.G+0x80000000))
        for address,blob in ((core.G+0x33267B8,core.u64(core.S+8)),(core.S+8,core.u32(9)),
                             (core.S+12,core.u32(9)),(core.S+16,core.u32(9)),(core.S+0x58,core.u64(core.S+0x18)),
                             (core.S+0x60,core.u32(16)),(core.S+0x64,core.u32(1)),
                             (core.E+index*0x40+8,core.u32(999)),(core.G+0x3483C34,core.u32(1+8*index)),
                             (core.B+index*8,core.u64(core.E+0x200)),(core.S+0x14+8,core.u32(0))):
            f=Fixture(lib,kind,8,8,p,index);f.put(address,blob);execute(f,'reject')
        boundary=p if kind=='enter' else p-1
        f=Fixture(lib,kind,8,8,p,index);f.put(core.B+boundary*8,core.u64(0));execute(f,'reject')
        f=Fixture(lib,kind,8,8,p,index);f.put(core.S+0x18+8*((1+boundary)&7),core.u32(index));execute(f,'reject')
    for kind,p,index in (('enter',8,7),('enter',3,2),('leave',0,0),('leave',3,3),('enter',3,6),('leave',3,6)):
        execute(Fixture(lib,kind,8,4 if index==6 else 8,p,index),'reject')
    # Carry a real classified arrangement into the other helper, preserving the
    # original asymmetric byte behavior rather than assuming inverse swaps.
    for index in range(3,8):
        before=execute(Fixture(lib,'enter',8,8,3,index))
        after=Fixture(lib,'leave',8,8,4,index)
        after.put(core.S,before.read(core.S,0x400));after.put(core.B,before.read(core.B,0x490))
        after.uc.reg_write(core.reg('rcx'),core.E+index*0x40);after.ordinal=3
        after.records={(name,i):after.read(after.slot(name,i),stride) for name,(_,_,stride) in core.LAYOUT.items() for i in range(8)}
        after.table=[(after.int32(core.S+0x14+8*i),after.int32(core.S+0x18+8*i)) for i in range(8)]
        execute(after)
    allocation_controls=[]
    for original in (True,False):
        for kind,p,index in (('enter',1,3),('leave',3,0)):
            f=Fixture(lib,kind,4,4,p,index,original=original,fail_allocation=True);faults=[]
            def invalid(uc,access,address,size,value,data):faults.append(dict(access=access,address=address,size=size));return False
            f.uc.hook_add(core.unicorn.UC_HOOK_MEM_INVALID,invalid)
            try:f.uc.emu_start(f.entry,0,count=100000)
            except core.unicorn.UcError:pass
            else:raise ValueError('null allocation control did not fault')
            boundary=p if kind=='enter' else p-1
            n.need(faults and faults[-1]['address']==0 and f.helper_events==['init','allocate'],'allocation failure path changed')
            n.need(f.read(f.slot('pointer',index),8)==f.records['pointer',boundary] and f.read(f.slot('pointer',boundary),8)==f.records['pointer',index],'partial pointer swap not reproduced')
            n.need([f.int32(core.S+off) for off in (8,12,16)]==[4,4,p],'failed classification updated counts')
            allocation_controls.append(dict(kind=kind,original=original,null_allocation_fault=True,prior_pointer_swap=True,cleanup_called=False))
    accepted=rejected=0
    for kind in n.CLASSIFY_KINDS:
        placements=[REFERENCE]
        for key in REFERENCE:
            for value in (0,1,15,16,(1<<47)-16,1<<47,(1<<64)-1):placements.append({**REFERENCE,key:value})
        for key in ('component_address','storage_address'):placements.append({**REFERENCE,key:REFERENCE[key]+0x100000000})
        for a in placements:
            try:expected=n.build(kind,**a)['image']
            except (ValueError,struct.error,OverflowError):expected=None
            out=Image();c.memset(c.byref(out),0xA5,c.sizeof(out));rc=lib.build(n.ALL_KINDS.index(kind)+1,Addresses(**a),out)
            if expected is None:n.need(rc!=0 and not any(bytes(out)),'invalid placement accepted');rejected+=1
            else:n.need(rc==0 and bytes(out.data[:out.bytes])==expected,'C++ classification mismatch');accepted+=1
    exe=n.PROJECT/'build/native_component33_classify_unwind_test.exe'
    core.run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',n.PROJECT/'tests/native_component33_unwind_test.c','-o',exe])
    windows={};conditional_controls={};artifacts=[lib.path,exe];metadata={}
    for kind in n.CLASSIFY_KINDS:
        a=lib.candidate(kind,**addresses(kind));rows=sorted(contexts[kind]);bad=bytearray(a['image']);bad[a['unwind_offset']+4+6]^=1
        row=bytearray(next(x for x in rows if struct.unpack_from('<i',x,4)[0]==-88 and struct.unpack_from('<Q',x,20)[0]!=core.SEEDS['rbp']))
        struct.pack_into('<I',row,8,1);expected=struct.pack('<9Q',*(core.SEEDS[k] for k in core.NAMES),core.G+0x10500000)
        def variant(blob,items):return struct.pack('<4I',len(blob),a['code_bytes'],a['table_offset'],len(items))+blob+expected+b''.join(items)
        fixture=n.PROJECT/'build'/('component33-'+kind+'-unwind.bin');fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(bad,[row])+variant(a['image'],rows))
        windows[kind]=json.loads(core.run([exe,fixture]));artifacts.append(fixture)
        child_begin,child_end,child_unwind=struct.unpack_from('<III',a['image'],a['table_offset']+24)
        saved=bytes.fromhex(n.profile()['functions'][kind]['fragments'][1]['unwind_hex'])
        n.need(saved[1]==23 and a['image'][child_unwind+1]==43,'conditional prologue size changed')
        row=next(x for x in rows if child_begin+23<=struct.unpack_from('<I',x)[0]<child_begin+43)
        broken=bytearray(a['image']);broken[child_unwind:child_unwind+12]=saved[:12]
        negative=bytearray(row);struct.pack_into('<I',negative,8,1)
        fixture=n.PROJECT/'build'/('component33-'+kind+'-conditional-unwind.bin')
        fixture.write_bytes(b'EPUWDV1\0'+struct.pack('<I',2)+variant(broken,[negative])+variant(a['image'],[row]))
        conditional_controls[kind]=json.loads(core.run([exe,fixture]));artifacts.append(fixture)
        metadata[kind]={key:a[key] for key in ('code_bytes','body_offset','table_offset','function_count')};metadata[kind]['array_patches']=len(a['array_patches'])
    paths=['tools/validate_component33_classify.py','tools/validate_component33_images.py','tools/native_component33_image.py',
           'tools/native_component33_library.py','tools/generate_component33_templates.py','native-component33.lock.json',
           'mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h',
           'tests/component33_image_dll.cpp','tests/native_component33_unwind_test.c','tests/native_producer_unwind_test.c']
    return dict(schema='hellforge_component33_classification_validation_v1',passed=True,functional_runs=len(runs),runs=runs,
                run_types=dict(Counter(('original_' if r['original'] else 'candidate_')+r['kind']+'_'+r['outcome'] for r in runs)),
                accepted_placements=accepted,rejected_placements=rejected,windows=windows,variants=metadata,
                conditional_prologue_controls=conditional_controls,allocation_failure_controls=allocation_controls,
                windows_unwind_contexts=sum(v['windows_unwind_contexts'] for v in windows.values()),
                chained_enter_leave_sequences=5,temporary_helpers_are_contract_stubs=True,entity_flags_owned_by_caller=True,
                full_component33_lifecycle=False,production_owner_bound=False,allocation_failure_rollback=False,
                source_sha256={p:n.sha((n.PROJECT/p).read_bytes()) for p in paths},
                artifacts={p.name:dict(bytes=p.stat().st_size,sha256=n.sha(p.read_bytes())) for p in artifacts},
                game_access=False,runtime_verified=False,multiplayer_verified=False,native_execution_of_game_bodies=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=validate(Library(a.library),a.zig);a.out.write_bytes((json.dumps(r,indent=2)+'\n').encode());print(json.dumps({k:r[k] for k in ('passed','functional_runs','run_types','windows_unwind_contexts','accepted_placements','rejected_placements','game_access')}))
