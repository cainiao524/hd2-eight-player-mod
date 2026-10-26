"""Fresh OLD snapshot migration and commit, mapped fixture reads only."""
import argparse,ctypes as c,json,subprocess,sys
from pathlib import Path
import validate_component33_publication as publication
MODES=[*range(31),*range(100,145)]
def main():
    ap=argparse.ArgumentParser()
    for name in ('zig','upstream','library'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--only',nargs='+',type=int);a=ap.parse_args()
    project=publication.PROJECT;library=(a.library or project/'build/component33_migration_commit_test.dll').resolve()
    if a.worker is not None:
        dll=c.CDLL(str(library));fn=dll.c33_migration_commit_test;fn.argtypes=[c.c_uint];fn.restype=c.c_uint
        print(json.dumps(dict(checks=fn(a.worker))));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
             '-I',a.upstream.resolve()/'native/mod-sdk','-I',project/'mod/src','-shared',
             *(project/s for s in publication.callers.core.leave.refresh.reset.update.entries.native.admission.SOURCES),
             project/'mod/src/ep_component33_resource_provider.cpp',project/'tests/component33_migration_commit_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);publication.n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for mode in a.only or MODES:
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode)],capture_output=True,text=True,timeout=30)
        publication.n.need(p.returncode==0,f'migration/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    if not a.only:
        p=subprocess.run([sys.executable,'-B',str(project/'tools/validate_component33_publication.py'),'--library',str(library),'--only',*[str(x) for x in publication.MODES]],capture_output=True,text=True,timeout=120)
        publication.n.need(p.returncode==0,p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,migration_scenarios=len(a.only or MODES),related_publication_scenarios=0 if a.only else len(publication.MODES),checks=checks,game_access=False)))
if __name__=='__main__':main()
