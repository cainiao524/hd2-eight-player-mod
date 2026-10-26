"""Whole UPDATE native ABI/scope in owned fixture memory. No game access."""
import argparse,json,subprocess,sys
from pathlib import Path
import validate_component33_update_drain as update
entries=update.entries;n=update.n;PROJECT=n.PROJECT

def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='whole_update');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_update_entry_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':entries.native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_update_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('whole_update',18),('update_entry',10),('entries',len(entries.SCENARIOS))):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,whole_update_scenarios=18,related_entry_regressions=39,checks=checks,game_access=False)))
if __name__=='__main__':main()
