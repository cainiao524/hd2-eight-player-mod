"""Fresh joint roster migration in test-owned RAM; no receipts or packages."""
import argparse,ctypes as c,json,subprocess,sys
from pathlib import Path
import validate_multiplayer_commit as joint
MODES=[*range(30),*range(100,135),*range(1001,1037)]
def main():
    ap=argparse.ArgumentParser()
    for name in ('zig','upstream','library'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--only',nargs='+',type=int);a=ap.parse_args()
    pub=joint.migration.publication;project=pub.PROJECT;library=(a.library or project/'build/roster_migration_commit_test.dll').resolve()
    if a.worker is not None:
        dll=c.CDLL(str(library));fn=dll.roster_migration_commit_test;fn.argtypes=[c.c_uint];fn.restype=c.c_uint
        print(json.dumps(dict(checks=fn(a.worker))));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        library.parent.mkdir(parents=True,exist_ok=True)
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
             '-I',a.upstream.resolve()/'native/mod-sdk','-I',project/'mod/src','-shared',
             *(project/s for s in pub.callers.core.leave.refresh.reset.update.entries.native.admission.SOURCES),
             *(project/'mod/src'/f'{s}.cpp' for s in joint.EMITTERS),project/'mod/src/ep_component33_resource_provider.cpp',
             project/'mod/src/ep_multiplayer_commit.cpp',project/'mod/src/ep_roster_migration.cpp',project/'tests/roster_migration_commit_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);pub.n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for mode in a.only or MODES:
        p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode)],capture_output=True,text=True,timeout=30)
        pub.n.need(p.returncode==0,f'roster-migration/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,roster_migration_scenarios=len(a.only or MODES),checks=checks,game_access=False)))
if __name__=='__main__':main()
