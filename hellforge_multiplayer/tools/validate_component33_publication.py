"""Transactional component33 entry tests, own process only; no receipts/hashes."""
import argparse,ctypes as c,json,subprocess,sys
from pathlib import Path
import validate_component33_caller_entry as callers
n=callers.n;PROJECT=callers.PROJECT
MODES=[*range(53),*range(60,83),90,91]

def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='publication')
    ap.add_argument('--only',nargs='+',type=int);a=ap.parse_args();library=(a.library or PROJECT/'build/component33_publication_test.dll').resolve()
    if a.worker is not None:
        if a.group=='publication':
            dll=c.CDLL(str(library));fn=dll.c33_publication_test;fn.argtypes=[c.c_uint];fn.restype=c.c_uint;checks=fn(a.worker)
        elif a.group=='callers':checks=callers.worker(library,a.worker)
        elif a.group=='core':checks=callers.core.worker(library,a.worker)
        else:checks=callers.core.leave.refresh.reset.update.entries.native.worker(library,a.group,a.worker)
        print(json.dumps(dict(checks=checks)));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
             '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in callers.core.leave.refresh.reset.update.entries.native.admission.SOURCES),
             PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_publication_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    groups=[('publication',a.only or MODES)]
    if not a.only:groups += [(key,range(count)) for key,count in (('callers',27),('core',19),('whole_leave',30),('whole_refresh',25),('whole_reset',24),('whole_update',18),('update_entry',10),('entries',29))]
    checks=0
    for group,modes in groups:
        for mode in modes:
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,publication_scenarios=len(a.only or MODES),sdk_entry_targets=25,related_regressions=0 if a.only else 182,checks=checks,game_access=False)))
if __name__=='__main__':main()
