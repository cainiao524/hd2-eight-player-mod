"""Whole RESET ABI/scope and live-resource preservation, using owned memory.

Reads saved instruction JSON directly; no game, receipt or fingerprint work.
"""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import validate_component33_update_entry as update
import validate_component33_resources as r
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_RSP,UC_X86_REG_RIP
n=update.n;PROJECT=n.PROJECT


def idle_cases(library):
    lib=r.Resources(library);fn=lib.dll.c33_resource_reset_idle;fn.argtypes=[c.POINTER(r.Binding),c.c_void_p,c.c_uint32];fn.restype=c.c_int
    checks=0
    def run(raw,cap):
        nonlocal checks
        buf=c.create_string_buffer(raw,len(raw));rc=fn(r.Binding(r.A,cap,0),buf,len(raw));checks+=1;return rc,buf.raw
    for cap in (128,256,512,1024,2048,4096,8192,16384,32768,65536):
        for seed in (0,1,2,0xffffffff):
            for rows,queue in (([(65,0),(66,0)],[]), ([(65,1),(66,0)],[]), ([(65,0),(66,0)],[65])):
                raw=lib.migrate_bytes(r.snapshot(rows,queue,seed),cap)
                # Leave stale unused queue cells to require clearing the full
                # capacity on idle reset, preservation when claims remain.
                raw=raw[:48+8*(cap-1)]+struct.pack('<Q',0xabcdef)+raw[48+8*cap:]
                rc,out=run(raw,cap);n.need(rc==0,'idle reset refused coherent arena')
                idle=not queue and not any(refs for _,refs in rows)
                expected=lib.migrate_bytes(r.snapshot(seed=2),cap) if idle else raw
                n.need(out==expected and lib.validate_bytes(out,cap)==0,'reset changed live claims or failed complete idle reset')
                rc,again=run(out,cap);n.need(rc==0 and again==out,'reset not stable on repeated entry')
            broken=bytearray(lib.migrate_bytes(r.snapshot([(65,1)],seed=seed),cap));struct.pack_into('<Q',broken,0,0)
            rc,out=run(bytes(broken),cap);n.need(rc!=0 and out==broken,'malformed arena was reset')
    # Independent original instruction execution: both wrappers initialize an
    # idle 128-slot cache with the same result as the new idle policy. Calls
    # to the per-entity helper and memset are intercepted in Unicorn only.
    profile=json.loads((PROJECT/'native-component33-resources.lock.json').read_bytes());originals=0
    for game in (0x180000000,0x190000000):
        for root in (0x51ade0,0x664210):
            uc=Uc(UC_ARCH_X86,UC_MODE_64);mapped=set()
            def put(address,data):
                for page in range(address&~4095,(address+len(data)+4095)&~4095,4096):
                    if page not in mapped:uc.mem_map(page,4096);mapped.add(page)
                uc.mem_write(address,bytes(data))
            def q(address,value):put(address,struct.pack('<Q',value))
            f=profile['functions'][hex(root)];put(game+root,bytes.fromhex(f['body_hex']))
            q(game+0x33267b8,0x200000000);put(game+0x3797550,bytes([0xa5])*1024)
            put(game+0x3797960,bytes([0xa5])*2048);put(game+0x3798180,bytes(32));q(game+0x348ba88,0)
            put(game+0x664430,b'\xc3');put(game+0x208aaa0,b'\xc3');put(0x300000000,bytes(4096))
            stop=0x300000f00;put(stop,b'\xcc');q(0x300000808,stop);uc.reg_write(UC_X86_REG_RSP,0x300000808)
            entity=0x200001000;uc.reg_write(UC_X86_REG_RCX,entity if root==0x51ade0 else 0xbad);uc.reg_write(UC_X86_REG_RDX,entity if root==0x664210 else 0xbad)
            calls=[]
            def hook(emu,pc,size,unused):
                if pc==game+0x664430:calls.append((emu.reg_read(UC_X86_REG_RCX),emu.reg_read(UC_X86_REG_RDX)))
                if pc==game+0x208aaa0:emu.mem_write(emu.reg_read(UC_X86_REG_RCX),bytes([emu.reg_read(UC_X86_REG_RDX)&255])*emu.reg_read(UC_X86_REG_R8))
            uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(game+root,stop,count=10000)
            n.need(uc.reg_read(UC_X86_REG_RIP)==stop and uc.reg_read(UC_X86_REG_RSP)==0x300000810 and calls==[(0x200000000,entity)],'saved RESET wrapper ABI')
            expected=bytearray(uc.mem_read(game+0x3798180,32))+bytearray(uc.mem_read(game+0x348ba88,8))+bytearray(8)
            expected+=uc.mem_read(game+0x3797550,1024)+uc.mem_read(game+0x3797960,2048)
            struct.pack_into('<Q',expected,0,r.A+48+128*8)
            raw=lib.migrate_bytes(r.snapshot([(65,0),(66,0)],seed=1),128);rc,out=run(raw,128)
            n.need(rc==0 and out==expected,'idle RESET diverges from saved original initialization');originals+=1
    return checks,originals


def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='whole_reset');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_reset_entry_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':update.entries.native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in update.entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_reset_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('whole_reset',24),('whole_update',18),('update_entry',10),('entries',len(update.entries.SCENARIOS))):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    cases,originals=idle_cases(library)
    print(json.dumps(dict(passed=True,whole_reset_scenarios=24,related_entry_regressions=57,reset_policy_calls=cases,
        original_idle_comparisons=originals,checks=checks,game_access=False)))
if __name__=='__main__':main()
