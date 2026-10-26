"""Real owned executable entry bridges. No game access or receipt files."""
import argparse,json,subprocess,sys
from pathlib import Path
import validate_component33_resource_native as native

SCENARIOS=('acquire','defer_by_object','release_low_ordinal_and_flag','release_nonzero_flag',
    'wrong_receiver','bad_ordinal','no_entity','missing_service_pointer','service_seh','resolver_seh',
    'changed_defer_source','throwing_reject_policy','closed_owner','cancel_before_exposure',
    'copied_sdk_callbacks','read_budget_abort','nested_success','nested_abort_stops_caller',
    'entry_excludes_roster_reader','revision_exhausted','defer_without_services','duplicate_prepare',
    'partial_allocation_cleanup','wrong_storage','missing_reject_policy','truncated_sdk','wrong_build',
    'service_mutation','swallowed_reentry')

def main():
    ap=argparse.ArgumentParser()
    for name in ('zig','upstream','library'):ap.add_argument('--'+name,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',choices=('entries','native','provider','drain'),default='entries');a=ap.parse_args()
    project=native.source.n.PROJECT;library=(a.library or project/'build/component33_resource_entries_test.dll').resolve()
    if a.worker is not None:print(json.dumps({'checks':native.worker(library,a.group,a.worker)}));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required with --zig')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',project/'mod/src','-shared',*(project/s for s in native.admission.SOURCES),
            project/'mod/src/ep_component33_resource_provider.cpp',project/'mod/src/ep_component33_resource_entries.cpp',
            project/'tests/component33_resource_entries_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);native.source.n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0;groups=(('entries',len(SCENARIOS)),('native',len(native.SCENARIOS)),('provider',len(native.legacy.SCENARIOS)),('drain',24))
    for group,count in groups:
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            native.source.n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,entry_scenarios=len(SCENARIOS),related_regression_scenarios=sum(count for group,count in groups[1:]),
        checks=checks,saved_call_runs=native.saved_calls(),game_access=False)))
if __name__=='__main__':main()
