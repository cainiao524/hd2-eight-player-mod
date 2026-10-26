"""Reserve/seal/retain real C++ images in our DLL; never execute their code.

All game/S/B/reject addresses are synthetic numbers. Only memory allocated by
our test DLL is inspected. Original bytes come from the pinned saved capture.
"""
import argparse,ctypes as c,json,struct,subprocess
from pathlib import Path
import native_component33_image as n
import native_component33_readers as readers
import native_component33_owner as owner
import native_component33_consumers as consumers

U=c.c_uint64;D=c.c_uint32;P=c.c_void_p
class Code(c.Structure):
    _fields_=[('handle',U),('base',U),('next_pointer',U)]+[(x,D) for x in ('bytes','state','registered','pinned')]
class Window(c.Structure):
    _fields_=[('target',U),('bytes',D),('call_offset',D),('expected',c.c_ubyte*16),('replacement',c.c_ubyte*16)]
class OwnerWindow(c.Structure):
    _fields_=[('target',U),('bytes',D),('call_offset',D),('expected',c.c_ubyte*75),('replacement',c.c_ubyte*75)]
class Info(c.Structure):
    _fields_=[('handle',U),('state',D),('reserved_images',D),('code',Code*19),('owner_window',OwnerWindow),('reader_windows',Window*2)]
class Bindings(c.Structure):
    _fields_=[(x,U) for x in ('game_base','component_address','storage_address','reject_address')]+[('desired_code',U*19)]
class Gs(c.Structure):
    _fields_=[('function_index',D),('handler_offset',D),('handler_target',U)]
class Memory(c.Structure):
    _fields_=[('base',P),('allocation',P),('allocation_protect',D),('partition',c.c_uint16),('region',c.c_size_t),('state',D),('protect',D),('type',D)]

def validate(path):
    lib=c.CDLL(str(path.resolve()));checks=0;scenarios=[];m=0x10001
    def check(v,label):
        nonlocal checks
        checks+=1;n.need(v,label)
    def fn(name,args,rest=c.c_int):
        f=getattr(lib,'c33_test_'+name);f.argtypes=args;f.restype=rest;return f
    prepare=fn('prepare',[P,c.POINTER(Bindings),c.POINTER(Info)])
    info=fn('info',[P,U,c.POINTER(Info)]);cancel=fn('cancel',[P,U]);retain=fn('retain',[P,U])
    ci=fn('code_info',[P,U,c.POINTER(Code)]);reserve=fn('reserve',[P,U,D,c.POINTER(Code)])
    discard=fn('discard',[P,U]);publish=fn('publish',[P,U]);retain_set=fn('retain_set',[P,c.POINTER(U),D])
    seal=fn('seal',[P,U,P,D,D,D,c.POINTER(Gs),D])
    faults=fn('faults',[c.POINTER(D)],None);counts=fn('counts',[c.POINTER(D)])
    kernel=c.WinDLL('kernel32');nt=c.WinDLL('ntdll')
    query=kernel.VirtualQuery;query.argtypes=[P,c.POINTER(Memory),c.c_size_t];query.restype=c.c_size_t
    lookup=nt.RtlLookupFunctionEntry;lookup.argtypes=[U,c.POINTER(U),P];lookup.restype=P
    def reset(**kw):
        f=(D*7)()
        for key,value in kw.items():f[int(key)]=value
        faults(f)
    def stats():
        a=(D*7)();check(counts(a)==0,'unexpected SDK hook');return list(a)
    def b(shift=0):
        return Bindings(0x180000000+shift,0x200000000,0x210000000,0x1a0000000+shift,(U*19)(*(0x190000000+shift+i*0x10000 for i in range(19))))
    def view(h):
        out=Info();check(info(m,h,out)==1,'family missing');return out
    def free_pages(a):
        for p in a.desired_code:
            mbi=Memory();check(query(p,mbi,c.sizeof(mbi)) and mbi.state==0x10000,'allocation leaked')
    def windows(w,ref):
        check(w.target==ref['target'] and w.bytes==len(ref['replacement']),'window location')
        check(bytes(w.expected[:w.bytes])==ref['expected'] and bytes(w.replacement[:w.bytes])==ref['replacement'],'window bytes')
    def ready(out,a,retained=False):
        check(out.state==(4 if retained else 2) and out.reserved_images==19,'family state')
        for i,code in enumerate(out.code):
            check(code.base==a.desired_code[i] and code.registered==1 and code.pinned==int(retained) and code.state==(7 if retained else 2),'code lifetime')
            mbi=Memory();check(query(code.base,mbi,c.sizeof(mbi)) and mbi.protect==0x20,'not RX')
            base=U();check(lookup(code.base,base,None) and base.value==code.base,'unregistered table')
            if i<14:
                ref=n.build(n.ALL_KINDS[i],game_base=a.game_base,code_address=code.base,component_address=a.component_address,
                    storage_address=a.storage_address,move_code_address=out.code[0].base,reject_address=a.reject_address)
            elif i==14:ref=readers.build(game_base=a.game_base,code_address=code.base,component_address=a.component_address,
                    storage_address=a.storage_address,reset_address=out.code[7].base,reject_address=a.reject_address)
            else:ref=consumers.build(consumers.KINDS[i-15],game_base=a.game_base,code_address=code.base,component_address=a.component_address,
                    storage_address=a.storage_address,release_address=out.code[18].base,reject_address=a.reject_address)
            check(c.string_at(code.base,code.bytes)==ref['image'],'prepared bytes differ from independent relocation')
        op=owner.build(a.game_base,out.code[13].base);windows(out.owner_window,op)
        rp=readers.build(game_base=a.game_base,code_address=out.code[14].base,component_address=a.component_address,
            storage_address=a.storage_address,reset_address=out.code[7].base,reject_address=a.reject_address)
        for w,r in zip(out.reader_windows,rp['windows']):windows(w,r)

    reset();out=Info();check(prepare(m,None,out)!=0 and not any(bytes(out)),'null input')
    check(prepare(m,b(),None)!=0 and prepare(None,b(),out)!=0,'null owner/output')
    check(not cancel(m,0) and not retain(m,0),'invalid handles')
    for shift in (0,0x40000000):
        a=b(shift);reset();check(prepare(m,a,out)==0,'prepare');ready(out,a)
        check(stats()[:4]==[19]*4,'all images prepared')
        check(not info(m+1,out.handle,Info()) and not cancel(m+1,out.handle),'wrong owner')
        old=Info.from_buffer_copy(out);check(cancel(m,out.handle),'cancel')
        check(not info(m,old.handle,out),'stale handle');free_pages(a)
        for code in old.code:check(not lookup(code.base,U(),None),'unwind table leaked')
        scenarios.append('prepare_cancel_'+hex(shift))
    # Every reservation and registration can fail. Prior allocations/tables
    # must be released and no partly bound family may become PREPARED.
    for kind,steps in ((0,range(1,20)),(3,range(1,20)),(1,(1,8,19)),(2,(1,8,19))):
        for step in steps:
            a=b();reset(**{str(kind):step});out=Info();check(prepare(m,a,out) in (5,6),'fault not propagated')
            check(not out.handle and not any(bytes(out)),'failed prepare exposed family');free_pages(a);stats()
            scenarios.append(f'fault_{kind}_{step}')
    for fault in (4,5):
        a=b();reset(**{'3':8,str(fault):1});out=Info();check(prepare(m,a,out)==7,'cleanup failure not reported')
        check(out.state==3 and out.reserved_images==1,'cleanup ownership lost')
        check(not retain(m,out.handle),'partial family retained')
        check(not any(bytes(out.owner_window)) and not any(bytes(out.reader_windows)),'failed plans exposed')
        reset();check(cancel(m,out.handle),'cleanup retry');free_pages(a);scenarios.append(f'cleanup_retry_{fault}')
    reset();a=b();a.reject_address=a.desired_code[4]+0xfff
    check(prepare(m,a,out)==3 and not out.handle,'page padding overlap');check(stats()[1:4]==[0,0,0],'sealed invalid graph');free_pages(a)
    a=b();a.desired_code[14]=a.desired_code[0];reset();check(prepare(m,a,out)==5,'duplicate reservation');free_pages(b())
    a=b();a.desired_code[14]+=0x100000000;reset();check(prepare(m,a,out)==4,'far reader accepted');free_pages(a)
    scenarios.extend(['padding_overlap','duplicate_reservation','far_reader'])

    # Exercise the exact PROPERTY GS contract without executing any byte.
    a=b();base=a.desired_code[6]
    ref=n.build('property',game_base=a.game_base,code_address=base,component_address=a.component_address,
        storage_address=a.storage_address,move_code_address=a.desired_code[0],reject_address=a.reject_address)
    original=ref['image'];gs=Gs(1,ref['handler_offset'],a.game_base+0x21044a0)
    uw=struct.unpack_from('<I',original,ref['table_offset']+20)[0]
    for mutation in ('ordinary','arrival','cookie','prologue','handler','thunk','shared_leaf','target','valid'):
        reset();code=Code();check(reserve(m,base,len(original),code),'GS reserve');blob=bytearray(original);profile=Gs.from_buffer_copy(gs);mode=2
        if mutation=='ordinary':mode=0
        elif mutation=='arrival':mode=1
        elif mutation=='cookie':blob[uw+32]^=1
        elif mutation=='prologue':blob[uw+1]^=1
        elif mutation=='handler':blob[uw+28]^=1
        elif mutation=='thunk':blob[ref['handler_offset']]=0xc3
        elif mutation=='shared_leaf':blob[ref['unwind_offset']+1]=1
        elif mutation=='target':profile.handler_target+=16
        buf=c.create_string_buffer(bytes(blob));rc=seal(m,code.handle,buf,len(blob),ref['table_offset'],ref['function_count'],profile,mode)
        check(bool(rc)==(mutation=='valid'),'GS acceptance '+mutation)
        check(discard(m,code.handle),'GS cleanup');scenarios.append('gs_'+mutation)

    # Bad sets and a pin failure may not retain an arbitrary subset. The final
    # two groups are intentionally retained for process lifetime, never called.
    for shift in (0,0x40000000):
        reset();a=b(shift);out=Info();check(prepare(m,a,out)==0,'retain prepare');ids=(U*19)(*(x.handle for x in out.code))
        for bad in ((U*19)(*ids[:-1],0),(U*19)(*ids[:-1],ids[0])):
            check(not retain_set(m,bad,19),'bad set accepted');ready(view(out.handle),a)
        check(not retain_set(m+1,ids,19) and not retain_set(m,None,19) and not retain_set(m,ids,0),'invalid set')
        reset(**{'6':1});check(not retain(m,out.handle),'failed pin accepted');ready(view(out.handle),a)
        reset();check(retain(m,out.handle),'retain');ready(view(out.handle),a,True)
        check(not cancel(m,out.handle) and not retain(m,out.handle),'retained transition reversed')
        for code in out.code:check(not discard(m,code.handle),'dependency freed after retention')
        stats();scenarios.append('retain_'+hex(shift))
        if not shift:first_retained=out.handle
    free=kernel.FreeLibrary;free.argtypes=[P];free.restype=c.c_int
    check(free(lib._handle),'FreeLibrary');ready(view(out.handle),a,True)
    scenarios.append('module_and_graph_survive_FreeLibrary')
    retained=view(first_retained);check(not publish(m,retained.code[0].handle),'mock publish should fail')
    check(counts((D*7)())==1,'retained image did not reach mock publication')
    retained=view(first_retained)
    for i,code in enumerate(retained.code):
        check(code.pinned==1 and code.registered==1 and code.state==(6 if i==0 else 7),'dependency lifetime after publication failure')
        check(not discard(m,code.handle),'published dependency released')
    check(not cancel(m,first_retained),'failed publication released family')
    scenarios.append('retained_sdk_publication_failure_keeps_all_dependencies')
    return dict(passed=True,checks=checks,scenarios=scenarios,images_per_family=19,window_plans=3,
        source_game_access=False,native_game_code_executed=False,targets_modified=False,sdk_hook_calls=0,mock_hook_calls=1,
        registered_real_unwind_tables=True,retention_is_not_publication=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--zig',type=Path,required=True);p.add_argument('--upstream',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    sources=['mod/src/ep_component33_consumers.h','mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_consumers_template.h','tools/native_component33_consumers.py','native-component33-consumers.lock.json','mod/src/ep_component33_family.h','mod/src/ep_component33_family.cpp','mod/src/ep_session_code.h','mod/src/ep_session_code.cpp',
        'mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h','mod/src/ep_component33_owner_template.h',
        'mod/src/ep_component33_readers.h','mod/src/ep_component33_readers.cpp','mod/src/ep_component33_readers_template.h','tests/component33_family_dll.cpp',
        'tools/validate_component33_family.py','tools/native_component33_image.py','tools/native_component33_owner.py','tools/native_component33_readers.py',
        'native-component33.lock.json','native-component33-owner.lock.json','native-component33-readers.lock.json']
    dll=n.PROJECT/'build/component33_family_test.dll'
    command=[a.zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror','-I',a.upstream/'native/mod-sdk',
        *(n.PROJECT/s for s in ('mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_family.cpp','mod/src/ep_component33_image.cpp','mod/src/ep_component33_readers.cpp','tests/component33_family_dll.cpp')),'-o',dll]
    r=subprocess.run(list(map(str,command)),capture_output=True);n.need(r.returncode==0,r.stderr.decode(errors='replace'))
    result=validate(dll);result.update(schema='hellforge_component33_family_validation_v1',source_sha256={s:n.sha((n.PROJECT/s).read_bytes()) for s in sources},
        artifacts={dll.name:dict(bytes=dll.stat().st_size,sha256=n.sha(dll.read_bytes()))},production_owner_bound=False,installed=False,runtime_verified=False,multiplayer_verified=False,game_access=False)
    a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:result[k] for k in ('passed','checks','images_per_family','window_plans','game_access')}))
if __name__=='__main__':main()
