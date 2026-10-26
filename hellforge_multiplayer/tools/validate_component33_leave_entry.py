"""Owned native leave/related entries, independent switch and unwind execution.

No game access, fingerprint or receipt workflow.
"""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_leave as source
import validate_component33_refresh_entry as refresh
import validate_component33_consumers as v
from native_component33_library import Image
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from validate_component33_images import reg
n=source.n;PROJECT=n.PROJECT


class Addresses(c.Structure):_fields_=[('game',c.c_uint64),('code',c.c_uint64),('defer',c.c_uint64)]


def image_cases(library,zig):
    dll=c.CDLL(str(library));fn=dll.c33_leave_build;fn.argtypes=[c.POINTER(Addresses),c.POINTER(Image)];fn.restype=c.c_int
    reference=source.build();contexts=set();runs=0;dispatches=0;sample=None
    saved=json.loads(source.LOCK.read_bytes())['callers']['release'];original=bytes.fromhex(saved['body_hex']);root=source.ROOT
    table=[x[0] for x in struct.iter_unpack('<I',original[0xb524b8-root:0xb524ec-root])]
    index=original[0xb524ec-root:];arms=set(table)|{0xb522ad,0xb523b4,0xb5239f,0xb52484}
    for variant in range(2):
        game=0x180000000+variant*0x100000000;code=game+0x10000000;defer=code+0x10000
        out=Image();n.need(fn(Addresses(game,code,defer),out)==0,'leave image refused')
        raw=bytes(out.data[:out.bytes]);expected=bytearray(reference['image'])
        for off,nxt,key,add in reference['fixups']:struct.pack_into('<i',expected,off,(game if key==0 else defer)+add-code-nxt)
        n.need(raw==expected and all(getattr(out,key)==reference[key] for key in ('code_bytes','unwind_offset','table_offset','function_count')),'leave source relocation')
        # Check every external native target independently of the generator's
        # fixup list; preserve bytes outside rewritten operands/effect block.
        relocated=n.decode(raw[:saved['code_end']-root],code);by_offset={i.address-code:i for i in relocated}
        for old in n.decode(original[:saved['code_end']-root],root):
            if source.START<=old.address<source.END:continue
            new=by_offset[old.address-root]
            for operand in old.operands:
                if operand.type==n.X86_OP_MEM and operand.mem.base==n.X86_REG_RIP:
                    target=old.address+old.size+operand.mem.disp
                    n.need(new.address+new.size+new.disp==(game+target if target else code-root),'leave external RIP/switch base')
            if old.group(n.capstone.CS_GRP_CALL) and old.operands[0].type==n.X86_OP_IMM:
                n.need(new.operands[0].imm==game+old.operands[0].imm,'leave external call')
        for case in range(6):
            uc=Uc(UC_ARCH_X86,UC_MODE_64);pages=set();registry=0x400000000;component=0x410000000;object_=0x420000000;other=component+0x200;stop=v.G+0x10500000
            def put(address,data):
                for page in range(address&~4095,(address+len(data)+4095)&~4095,4096):
                    if page not in pages:uc.mem_map(page,4096);pages.add(page)
                uc.mem_write(address,bytes(data))
            def q(address,value):put(address,struct.pack('<Q',value))
            def d(address,value):put(address,struct.pack('<I',value))
            put(code,raw);put(defer,b'\xc3');put(stop,b'\xcc');put(v.STACK,bytes(0x10000));q(v.RSP,stop)
            q(game+0x3326e68,registry);put(registry,bytes(0x1000));put(component,bytes(4096))
            d(registry+0xd10,0 if case==0 else 4);d(component+12,0 if case==2 else 8)
            for i in range(4):q(registry+0xd18+16*i,component if i%2 else 0xbad);d(registry+0xd20+16*i,0x7c if i%2 and case!=1 else 0)
            if case==5:q(registry+0xd18,other);d(registry+0xd20,0x119);q(other+0x20,object_);put(other+0x28,b'\xa5'*24)
            for name,value in v.SEEDS.items():uc.reg_write(reg(name),value)
            uc.reg_write(reg('rsp'),v.RSP);uc.reg_write(reg('rcx'),object_);uc.reg_write(reg('rdx'),0xdeadbeeffedcba91)
            calls=[];trace=[]
            def normalize(value):
                if v.RSP-512<=value<v.RSP+128:return 0x200000000+value-v.RSP
                if code<=value<code+len(raw):return 0x100000000+value-code
                return value
            def hook(emu,pc,size,unused):
                if pc==defer:
                    calls.append((emu.reg_read(reg('rcx')),emu.reg_read(reg('rdx'))))
                    n.need(emu.reg_read(reg('rsp'))%16==8,'leave DEFER stack alignment')
                    if case==4:d(component+12,0)
                    for name in ('rax','rcx','rdx','r8','r9','r10','r11'):emu.reg_write(reg(name),0xfedcba)
                if code<=pc<code+out.code_bytes:
                    trace.append(pc-code);stack=bytearray(emu.mem_read(v.RSP-512,640))
                    for at in range(0,640,8):struct.pack_into('<Q',stack,at,normalize(struct.unpack_from('<Q',stack,at)[0]))
                    contexts.add(struct.pack('<IiII8Q',pc-code,emu.reg_read(reg('rsp'))-v.RSP,0,1,*(normalize(emu.reg_read(reg(name))) for name in v.NAMES))+stack)
            hook_id=uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(code,stop,count=10000)
            expected_calls=0 if case<3 else 1 if case==4 else 2
            n.need(uc.reg_read(reg('rip'))==stop and uc.reg_read(reg('rsp'))==v.RSP+8 and calls==[(component,object_)]*expected_calls,'leave traversal arguments/skip')
            n.need(all(uc.reg_read(reg(name))==value for name,value in v.SEEDS.items()),'leave nonvolatile changed')
            n.need(not any(source.START-root+16<=pc<source.END-root for pc in trace),'removed fixed scan executed')
            if case==5:n.need(not any(uc.mem_read(other+0x20,32)),'non-component33 arm lost')
            sample=out;runs+=1
            if case!=0:continue
            uc.hook_del(hook_id)
            # Drive the actual copied dispatch for every byte-table input,
            # gaps around it, special arms and unsigned extremes. Stop before
            # each arm's unknown native effects; validate destination + flags.
            for tag in (*range(0x131),0x7fffffff,0x80000000,0xffffffff):
                d(registry+0xd10,1);d(registry+0xd20,tag)
                expected_target=0xb522ad if tag==0x119 else 0xb523b4 if tag==0x11f else 0xb5239f if tag==0x124 else table[index[tag-0x18]] if 0x18<=tag<=0x115 else 0xb52484
                for flags in (0,0x91,0xfedcba91):
                    for name,value in v.SEEDS.items():uc.reg_write(reg(name),value)
                    uc.reg_write(reg('rsp'),v.RSP);uc.reg_write(reg('rcx'),object_);uc.reg_write(reg('rdx'),0xdeadbeef00000000|flags)
                    reached=[]
                    def arm_hook(emu,pc,size,unused):
                        if pc-code+root in arms:
                            reached.append(pc-code+root)
                            n.need(emu.reg_read(reg('rbx'))==flags and emu.reg_read(reg('rdi'))==object_,'leave flags/object ABI')
                            emu.emu_stop()
                    arm_id=uc.hook_add(UC_HOOK_CODE,arm_hook);uc.emu_start(code,stop,count=1000);uc.hook_del(arm_id)
                    n.need(reached==[expected_target],'leave switch destination');dispatches+=1
    rejected=0
    for args in ((0,0x190000000,0x190010000),(v.G,0,0x190010000),(v.G,v.G+0xb51de0,0x190010000),
                 (v.G,0x190000000,0x190000000),(v.G,0x290000000,0x190010000),(v.G,0x190000000,0x290010000)):
        out=Image();c.memset(c.byref(out),0xa5,c.sizeof(out));n.need(fn(Addresses(*args),out)!=0 and not any(bytes(out)),'invalid leave placement');rejected+=1
    raw=bytes(sample.data[:sample.bytes]);bad=bytearray(raw);uw=sample.unwind_offset
    n.need(bad[uw+5]&15==2,'leave root allocation unwind');bad[uw+5]^=0x10
    rows=sorted(contexts);negative=bytearray(next(row for row in rows if struct.unpack_from('<I',row)[0]==source.START-root+11));struct.pack_into('<I',negative,8,1)
    packed=bytearray(b'EPCCNW1\0'+struct.pack('<I',2))
    for image,items in ((bad,[negative]),(raw,rows)):
        packed.extend(struct.pack('<4I',len(image),sample.table_offset,sample.function_count,len(items)));packed.extend(image)
        packed.extend(struct.pack('<9Q',*(v.SEEDS[name] for name in v.NAMES),v.G+0x10500000));packed.extend(b''.join(items))
    fixture=PROJECT/'build/component33-leave-unwind.bin';fixture.write_bytes(packed);exe=PROJECT/'build/component33_leave_unwind_test.exe'
    if zig:v.run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_component33_consumers_unwind_test.c','-o',exe])
    result=json.loads(v.run([exe,fixture]))
    return dict(registry_executions=runs,switch_dispatches=dispatches,rejected_placements=rejected,windows_unwind_contexts=result['windows_unwind_contexts'])


def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='whole_leave');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_leave_entry_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':refresh.reset.update.entries.native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in refresh.reset.update.entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_leave_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('whole_leave',30),('whole_refresh',25),('whole_reset',24),('whole_update',18),('update_entry',10),('entries',29)):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    result=image_cases(library,a.zig.resolve() if a.zig else None)
    print(json.dumps(dict(passed=True,whole_leave_scenarios=30,related_entry_regressions=106,checks=checks,**result,game_access=False)))
if __name__=='__main__':main()
