"""Owned native ABI integration and saved call-site execution. No receipts."""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_resource_provider as source
import validate_component33_resource_call as admission
import validate_component33_resource_provider as legacy
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *

SCENARIOS=('acquire_fifth','release','deferred_release','drain','blocked_drain','empty_drain',
    'null_engine','null_load','overflow_table','unreadable_load','unreadable_call_site','changed_call_site',
    'context_seh','resolver_seh','load_seh','dispose_seh','context_reentry','resolver_reentry',
    'context_nested_fault','load_reentry','load_mutates_arena','shared_read_budget','wrong_build',
    'truncated_sdk','native_excludes_roster_reader','frozen_service_targets','zero_context','no_entity','revision_exhausted')

def worker(library,group,mode):
    if group=='provider': return legacy.worker(library,mode)['checks']
    dll=c.CDLL(str(library));fn=getattr(dll,'c33_resource_'+group+'_test');fn.argtypes=[c.c_uint];fn.restype=c.c_uint
    return fn(mode)

def saved_calls():
    """Execute the actual saved call instructions, with inert owned targets.

    Check observable RCX/RDX arguments separately from the C++ adapter test;
    no assumptions about unknown callee bodies, readiness or runtime safety.
    """
    n=source.n;p=json.loads(source.resources.LOCK.read_bytes());image=n.Image(n.ROOT/p['capture_directory'])
    expected=source.render_native_calls().encode()
    n.need(source.HEADER.read_bytes().endswith(expected),'native code guards not current')
    runs=0
    for variant in range(2):
        game=0x180000000+variant*0x10000000;engine=0x200000000;table=engine+0x1000
        contexts=engine+0x2000;objects=engine+0x3000;row=engine+0x4000;stack=0x300000000
        context=0 if variant else 0x230000000;key=(1<<64)-7 if variant else 101;handle=0xfedcba98 if variant else 14
        targets={'context':engine+0x5000,'resolve':engine+0x5100,'load':engine+0x5200,'dispose':engine+0x5300}
        for name,start,raw in source.native_call_sources():
            n.need(image.read(start,len(raw))==raw,'call instructions differ from saved capture')
            uc=Uc(UC_ARCH_X86,UC_MODE_64);pages=set()
            def put(address,data):
                for page in range(address&~4095,(address+len(data)+4095)&~4095,4096):
                    if page not in pages:uc.mem_map(page,4096);pages.add(page)
                uc.mem_write(address,data)
            def q(address,value):put(address,struct.pack('<Q',value))
            put(game+start,raw);q(game+0x3326308,engine)
            q(engine+0x10,table);q(engine+0x38,contexts);q(engine+0x40,objects)
            q(contexts+8,targets['context']);q(objects+0x160,targets['resolve']);q(table+0x2f0,targets['load']);q(table+0x300,targets['dispose'])
            q(row,key);put(stack,bytes(4096));uc.reg_write(UC_X86_REG_RSP,stack+2048)
            uc.reg_write(UC_X86_REG_R8,key);uc.reg_write(UC_X86_REG_RBX,row);uc.reg_write(UC_X86_REG_RBP,0x1234567800000000|handle)
            for address in targets.values():put(address,b'\xc3')
            calls=[]
            def hook(emu,pc,size,unused):
                for label,address in targets.items():
                    if pc==address:
                        calls.append((label,emu.reg_read(UC_X86_REG_RCX),emu.reg_read(UC_X86_REG_RDX)))
                        emu.reg_write(UC_X86_REG_RAX,context if label=='context' else 0)
            uc.hook_add(UC_HOOK_CODE,hook);uc.emu_start(game+start,game+start+len(raw),count=50)
            n.need(uc.reg_read(UC_X86_REG_RIP)==game+start+len(raw) and uc.reg_read(UC_X86_REG_RSP)==stack+2048,'call site did not return')
            if name in ('resolve','defer'):
                n.need(len(calls)==2 and calls[0][:2]==('context',engine) and calls[1]==('resolve',context,handle),'saved resolver arguments')
            else:n.need(calls==[(name,key,table)],'saved service arguments')
            runs+=1
    return runs

def main():
    ap=argparse.ArgumentParser()
    for name in ('zig','upstream','library'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',choices=('native','provider','drain'),default='native');a=ap.parse_args()
    library=(a.library or source.n.PROJECT/'build/component33_resource_native_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream is required with --zig')
        command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',source.n.PROJECT/'mod/src','-shared',*(source.n.PROJECT/s for s in admission.SOURCES),
            source.n.PROJECT/'mod/src/ep_component33_resource_provider.cpp',source.n.PROJECT/'tests/component33_resource_native_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in command],capture_output=True,text=True);source.n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('native',len(SCENARIOS)),('provider',len(legacy.SCENARIOS)),('drain',24)):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            source.n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,native_scenarios=len(SCENARIOS),related_regression_scenarios=len(legacy.SCENARIOS)+24,
        saved_call_runs=saved_calls(),checks=checks,game_access=False)))
if __name__=='__main__':main()
