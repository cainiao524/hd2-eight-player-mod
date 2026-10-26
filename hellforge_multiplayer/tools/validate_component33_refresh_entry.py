"""Owned native refresh integration plus executed registry/unwind contexts.

Only related entry regressions. No game, fingerprint, or receipt workflow.
"""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_refresh as source
import validate_component33_reset_entry as reset
import validate_component33_consumers as v
from native_component33_library import Image
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from validate_component33_images import reg
n=source.n;PROJECT=n.PROJECT


class Addresses(c.Structure):_fields_=[('game',c.c_uint64),('code',c.c_uint64),('acquire',c.c_uint64)]


def image_cases(library,zig):
    dll=c.CDLL(str(library));fn=dll.c33_refresh_build;fn.argtypes=[c.POINTER(Addresses),c.POINTER(Image)];fn.restype=c.c_int
    reference=source.build();contexts=set();runs=0;sample=None
    for variant in range(2):
        game=0x180000000+variant*0x100000000;code=game+0x10000000;acquire=code+0x10000
        out=Image();n.need(fn(Addresses(game,code,acquire),out)==0,'refresh image refused')
        raw=bytes(out.data[:out.bytes]);expected=bytearray(reference['image'])
        for off,nxt,key,add in reference['fixups']:struct.pack_into('<i',expected,off,(game if key==0 else acquire)+add-code-nxt)
        n.need(raw==expected and all(getattr(out,key)==reference[key] for key in ('code_bytes','unwind_offset','table_offset','function_count')),'refresh source relocation')
        for case in range(5):
            uc=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();registry=0x400000000;component=0x410000000;object_=0x420000000;stop=v.G+0x10500000
            def put(address,data):
                for page in range(address&~4095,(address+len(data)+4095)&~4095,4096):
                    if page not in pages:uc.mem_map(page,4096);pages.add(page)
                uc.mem_write(address,bytes(data))
            def q(address,value):put(address,struct.pack('<Q',value))
            def d(address,value):put(address,struct.pack('<I',value))
            put(code,raw);put(acquire,b'\xc3');put(stop,b'\xcc');put(v.STACK,bytes(0x10000));q(v.RSP,stop)
            q(game+0x3326e68,registry);put(registry,bytes(0x2100));put(component,bytes(4096))
            count=0 if case==0 else 4;d(registry+0x1f78,count);d(component+12,0 if case==2 else 8)
            for i in range(4):q(registry+0x1f80+16*i,component if i%2 else 0xbad);d(registry+0x1f88+16*i,0x7c if i%2 and case!=1 else 0x11)
            for name,value in v.SEEDS.items():uc.reg_write(reg(name),value)
            uc.reg_write(reg('rsp'),v.RSP);uc.reg_write(reg('rcx'),object_)
            calls=[];trace=[]
            def normalize(value):
                if v.RSP-512<=value<v.RSP+128:return 0x200000000+value-v.RSP
                if code<=value<code+len(raw):return 0x100000000+value-code
                return value
            def hook(emu,pc,size,unused):
                if pc==acquire:
                    calls.append((emu.reg_read(reg('rcx')),emu.reg_read(reg('rdx'))))
                    n.need(emu.reg_read(reg('rsp'))%16==8,'refresh call stack alignment')
                    if case==4:d(component+12,0)  # A later row must reload its dense count.
                    for name in ('rax','rcx','rdx','r8','r9','r10','r11'):emu.reg_write(reg(name),0xfedcba)
                if code<=pc<code+out.code_bytes:
                    trace.append(pc-code);stack=bytearray(emu.mem_read(v.RSP-512,640))
                    for at in range(0,640,8):struct.pack_into('<Q',stack,at,normalize(struct.unpack_from('<Q',stack,at)[0]))
                    contexts.add(struct.pack('<IiII8Q',pc-code,emu.reg_read(reg('rsp'))-v.RSP,0,1,*(normalize(emu.reg_read(reg(name))) for name in v.NAMES))+stack)
            uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(code,stop,count=10000)
            expected_calls=0 if case<3 else 2 if case==3 else 1
            n.need(uc.reg_read(reg('rip'))==stop and uc.reg_read(reg('rsp'))==v.RSP+8 and calls==[(component,object_)]*expected_calls,'refresh traversal arguments/skip')
            n.need(all(uc.reg_read(reg(name))==value for name,value in v.SEEDS.items()),'refresh nonvolatile changed')
            n.need(not any(source.START-source.ROOT+16<=pc<source.TAIL-source.ROOT for pc in trace),'removed raw effect loop executed')
            sample=out;runs+=1
    rejected=0
    for args in ((0,0x190000000,0x190010000),(v.G,0,0x190010000),(v.G,v.G+0xb5e710,0x190010000),
                 (v.G,0x190000000,0x190000000),(v.G,0x290000000,0x190010000),(v.G,0x190000000,0x290010000)):
        out=Image();c.memset(c.byref(out),0xa5,c.sizeof(out));n.need(fn(Addresses(*args),out)!=0 and not any(bytes(out)),'invalid refresh placement');rejected+=1
    # Exercise real Windows unwinding at every executed instruction, including
    # conditional saves, the routed call and both epilogues. One deliberately
    # wrong stack-allocation rule must fail this same comparison.
    raw=bytes(sample.data[:sample.bytes]);bad=bytearray(raw);uw=sample.unwind_offset
    n.need(bad[uw+5]&15==2,'root allocation unwind rule');bad[uw+5]^=0x10
    rows=sorted(contexts);negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]==source.START-source.ROOT+11));struct.pack_into('<I',negative,8,1)
    packed=bytearray(b'EPCCNW1\0'+struct.pack('<I',2))
    for image,items in ((bad,[negative]),(raw,rows)):
        packed.extend(struct.pack('<4I',len(image),sample.table_offset,sample.function_count,len(items)));packed.extend(image)
        packed.extend(struct.pack('<9Q',*(v.SEEDS[name] for name in v.NAMES),v.G+0x10500000));packed.extend(b''.join(items))
    fixture=PROJECT/'build/component33-refresh-unwind.bin';fixture.write_bytes(packed);exe=PROJECT/'build/component33_refresh_unwind_test.exe'
    if zig:v.run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_component33_consumers_unwind_test.c','-o',exe])
    result=json.loads(v.run([exe,fixture]))
    return dict(registry_executions=runs,rejected_placements=rejected,windows_unwind_contexts=result['windows_unwind_contexts'])


def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='whole_refresh');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_refresh_entry_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':reset.update.entries.native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in reset.update.entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_refresh_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('whole_refresh',25),('whole_reset',24),('whole_update',18),('update_entry',10),('entries',29)):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    result=image_cases(library,a.zig.resolve() if a.zig else None)
    print(json.dumps(dict(passed=True,whole_refresh_scenarios=25,related_entry_regressions=81,checks=checks,**result,game_access=False)))
if __name__=='__main__':main()
