"""Owned-process caller scopes and related entry regressions; no receipts."""
import argparse,ctypes as c,json,subprocess,sys
from pathlib import Path
import validate_component33_core_entry as core
n=core.n;PROJECT=core.PROJECT

def worker(library,mode):
    dll=c.CDLL(str(library));fn=dll.c33_caller_entries_test
    fn.argtypes=[c.c_uint,c.c_void_p,c.c_uint,c.c_uint,c.c_uint];fn.restype=c.c_uint
    raw,table,rows=core.saved_maps();buffer=c.create_string_buffer(raw)
    return fn(mode,buffer,len(raw),table,rows)

def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='callers');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_caller_entry_test.dll').resolve()
    if a.worker is not None:
        checks=worker(library,a.worker) if a.group=='callers' else core.worker(library,a.worker) if a.group=='core' else core.leave.refresh.reset.update.entries.native.worker(library,a.group,a.worker)
        print(json.dumps(dict(checks=checks)));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
             '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in core.leave.refresh.reset.update.entries.native.admission.SOURCES),
             PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_caller_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('callers',27),('core',19),('whole_leave',30),('whole_refresh',25),('whole_reset',24),('whole_update',18),('update_entry',10),('entries',29)):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,caller_scenarios=27,caller_entries=3,related_entry_regressions=155,checks=checks,game_access=False)))
if __name__=='__main__':main()
