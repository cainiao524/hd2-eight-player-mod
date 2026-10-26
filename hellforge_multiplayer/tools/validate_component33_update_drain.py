"""UPDATE tail routing, real owned entry scope, and Windows unwind; no game.

Uses saved instructions directly. Old fixture loaders are supplied their JSON
metadata without running their unrelated file-digest/receipt workflows.
"""
import argparse,ctypes as c,json,struct,subprocess,sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import validate_component33_resource_entries as entries
import validate_component33_resource_drain as drain
import validate_component33_resources as r
import validate_component33_consumers as v
import validate_component33_resource_services as services
from native_component33_library import Library,Image
n=v.n;PROJECT=n.PROJECT;DRAIN=v.G+0x10d00000

class RoutedImages(r.Images):
    def build(self,kind,**a):
        legacy=super().build(kind,**a)
        if kind!='update':return legacy
        out=Image();n.need(self.resources.dll.c33_update_drain_build(v.Addresses(**a),DRAIN,out)==0,'UPDATE route emission')
        base=v.consumer.build(kind,**a);raw=bytes(out.data[:out.bytes]);start=base['instruction_map'][0x664b2f];end=base['instruction_map'][0x664ba9]
        n.need(raw[:start]==base['image'][:start] and raw[end:]==base['image'][end:],'route changed non-tail code/unwind')
        n.need(raw[start+7:start+12]==base['image'][start+7:start+12],'R13 restore moved')
        return {**base,'image':raw}

class RoutedFixture(r.Fixture):
    def on_code(self,uc,pc,size,data):
        if pc==DRAIN:
            self.drain_calls+=1;n.need(uc.reg_read(v.reg('rcx'))==v.S,'drain receiver')
            if not self.int32(v.HEAP+0x190c):
                raw=self.read(self.arena,r.resource.size(self.capacity));buffer=c.create_string_buffer(raw,len(raw));scratch=c.create_string_buffer(len(raw))
                @services.SERVICE
                def dispose(context,op,key):
                    n.need(op==1,'UPDATE used load');self.calls.append(('dispose',(key,0,0,0)));return 1
                n.need(self.resources.dll.c33_resource_drain(r.Binding(self.arena,self.capacity,0),buffer,len(raw),scratch,len(raw),dispose,None)==0,'routed arena drain')
                self.put(self.arena,buffer.raw)
            sp=uc.reg_read(v.reg('rsp'));uc.reg_write(v.reg('rip'),struct.unpack('<Q',self.read(sp,8))[0]);uc.reg_write(v.reg('rsp'),sp+8);return
        # Collect actual relocated UPDATE contexts, including both sides of
        # the restored-R13 unwind boundary and the new helper call.
        v.Fixture.on_code(self,uc,pc,size,data)

def execute_tests(library,zig):
    res=r.Resources(library);lib=Library(library);f=res.dll.c33_update_drain_build
    f.argtypes=[c.POINTER(v.Addresses),c.c_uint64,c.POINTER(Image)];f.restype=c.c_int
    res.dll.c33_resource_drain.argtypes=[c.POINTER(r.Binding),r.P,r.D,r.P,r.D,services.SERVICE,r.P];res.dll.c33_resource_drain.restype=c.c_int
    rejected=0;a=v.params('update')
    for address in (0,1,1<<47,(1<<47)-16,a['code_address'],a['component_address'],a['storage_address'],a['reject_address'],a['game_base']+0x664520,a['code_address']+0x100000000):
        out=Image();c.memset(c.byref(out),0xa5,c.sizeof(out));n.need(f(v.Addresses(**a),address,out)!=0 and not any(bytes(out)),'invalid drain destination');rejected+=1
    n.need(f(None,DRAIN,Image())!=0 and f(v.Addresses(**a),DRAIN,None)!=0,'null routing arguments')
    contexts=set();runs=0;saved_runs=0;sample=None
    shapes=[(capacity,t,d,p,1,active,count,blocked) for capacity in (128,512)
        for t,d,p,active in ((0,0,0,0),(4,4,2,1),(5,5,2,1),(8,8,4,1),(8,5,2,1)) for count in (0,3) for blocked in (0,1)]
    shapes += [(512,8,8,4,1,1,count,blocked) for count in (129,512) for blocked in (0,1)]
    shapes += [(capacity,8,8,4,control,active,3,0) for capacity in (128,512) for control,active in ((0,1),(1,0))]
    for capacity,t,d,p,control,active,count,blocked in shapes:
        raw=drain.arena(res,capacity,count,1)
        before=r.Fixture(lib,r.Images(res,capacity),'update',t,d,p,control=control,active=active);before.install(raw,res,capacity);before.put(v.HEAP+0x190c,v.u32(blocked))
        # The original has a 128-entry clear. Scale only that immediate for
        # expanded arenas, just as SavedDrain does; retain all original calls,
        # gates and ordering. The managed path must clear the entire capacity.
        clear=v.params('update')['code_address']+before.artifact['instruction_map'][0x664b94]
        n.need(before.read(clear,2)==b'\x41\xb8','saved clear immediate');before.put(clear+2,v.u32(capacity*8))
        after=RoutedFixture(lib,RoutedImages(res,capacity),'update',t,d,p,control=control,active=active);after.install(raw,res,capacity);after.put(v.HEAP+0x190c,v.u32(blocked));after.put(DRAIN,b'\xc3');after.drain_calls=0
        expected=before.execute_resource();actual=after.execute_resource()
        n.need(expected==actual and after.drain_calls==1,'UPDATE arena/scheduling differs '+str((capacity,t,d,p,control,active,count,blocked,after.drain_calls,expected==actual)))
        n.need([call for call in before.calls if call[0]!='clear_queue']==after.calls,'UPDATE effects/order differs')
        n.need(before.read(v.B,0x490)==after.read(v.B,0x490) and before.read(v.S,2)==after.read(v.S,2),'UPDATE component state differs')
        n.need(not any(a<=pc<b for pc in after.trace for a,b in ((v.params('update')['code_address']+after.artifact['instruction_map'][0x664b70],v.params('update')['code_address']+after.artifact['instruction_map'][0x664ba9]),)),'raw drain loop still executed')
        contexts.update(after.rows);sample=after;runs+=1
        if t==0:
            source=drain.SavedDrain(lib,res,raw,capacity,blocked);n.need(source.execute_resource()==actual,'saved full UPDATE differs');saved_runs+=1
    # Windows consumes contexts from the instructions that actually ran. A
    # deliberately broken root unwind operation must fail the same comparison.
    blob=sample.blob;rows=sorted(contexts);bad=bytearray(blob)
    root=v.consumer.profile()['functions']['update']['fragments'][0];uw=struct.unpack_from('<I',blob,sample.table+12+8)[0]
    raw=bytes.fromhex(root['unwind_hex']);pos=next(i for i in range(4,4+raw[2]*2,2) if raw[i+1]&15==2);bad[uw+pos+1]^=0x10
    off=sample.images['update']['instruction_map'][0x664539];negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]==off));struct.pack_into('<I',negative,8,1)
    packed=bytearray(b'EPCCNW1\0'+v.u32(2))
    for image,items in ((bad,[negative]),(blob,rows)):
        packed.extend(struct.pack('<4I',len(image),sample.table,sample.count,len(items)));packed.extend(image)
        packed.extend(struct.pack('<9Q',*(v.SEEDS[k] for k in v.NAMES),v.G+0x10500000));packed.extend(b''.join(items))
    fixture=PROJECT/'build/component33-update-drain-unwind.bin';fixture.write_bytes(packed);exe=PROJECT/'build/component33_update_drain_unwind_test.exe'
    if zig:v.run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_component33_consumers_unwind_test.c','-o',exe])
    windows=json.loads(v.run([exe,fixture]));return dict(update_comparisons=runs,saved_full_update_comparisons=saved_runs,rejected_placements=rejected,windows_unwind_contexts=windows['windows_unwind_contexts'])

def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='update_entry');ap.add_argument('--images-only',action='store_true');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_update_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':entries.native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'mod/src/ep_component33_resource_entries.cpp',PROJECT/'tests/component33_update_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    for group,count in (() if a.images_only else (('update_entry',10),('entries',len(entries.SCENARIOS)))):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr)
    with ExitStack() as stack:
        for module in (n,v.consumer,r.resource):stack.enter_context(patch.object(module,'profile',return_value=json.loads(module.LOCK.read_bytes())))
        result=execute_tests(library,a.zig.resolve() if a.zig else None)
    print(json.dumps(dict(passed=True,native_entry_scenarios=0 if a.images_only else 39,**result,game_access=False)))
if __name__=='__main__':main()
