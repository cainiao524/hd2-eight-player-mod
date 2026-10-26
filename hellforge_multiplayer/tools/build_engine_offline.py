"""Replay the private engine patch and test real consumers in our synthetic process.

Never invoke upstream launch/setup/build scripts. Source, compiler and MinHook
paths are explicit; no installation or game process discovery takes place.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

PROJECT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd=PROJECT):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stdout.decode('utf-8', errors='replace') + r.stderr.decode('utf-8', errors='replace'))
    return r.stdout


def check(path, expected):
    if digest(path) != expected:
        raise RuntimeError(f'Source/tool pin mismatch: {path.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('upstream', 'zig', 'minhook'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    upstream, zig, minhook = args.upstream.resolve(), args.zig.resolve(), args.minhook.resolve()
    lock = json.loads((PROJECT / 'upstream.lock.json').read_text(encoding='utf-8'))
    patch_lock = json.loads((PROJECT / 'engine/patch.lock.json').read_text(encoding='utf-8'))
    if run(['git', 'rev-parse', 'HEAD'], upstream).decode().strip() != lock['commit'] or lock['commit'] != patch_lock['upstream_commit']:
        raise RuntimeError('Use the pinned upstream commit')
    if run(['git', 'status', '--porcelain', '--untracked-files=no'], upstream).strip():
        raise RuntimeError('The original upstream checkout must stay unmodified')
    for path, sha in lock['source_sha256'].items():
        check(upstream / path, sha)
    check(zig, lock['zig']['exe_sha256'])
    if run([zig, 'version']).decode().strip() != lock['zig']['version']:
        raise RuntimeError('Wrong compiler version')
    for path, sha in patch_lock['minhook']['source_sha256'].items():
        check(minhook / path, sha)
    patch = PROJECT / patch_lock['patch']
    check(patch, patch_lock['patch_sha256'])
    check(PROJECT / 'mod/src/ep_roster_api.h', patch_lock['patched_source_sha256']['native/mod-loader/ep_roster.h'])
    build = PROJECT / 'build'
    build.mkdir(exist_ok=True)
    source_tests = json.loads(run([sys.executable, '-B', PROJECT / 'tests/test_native_unwind_source.py']))
    source_replay = json.loads(run([sys.executable, '-B', PROJECT / 'tools/verify_native_unwind_source.py',
                                   '--capture', PROJECT.parent / 'evidence/existing-code-evidence-25480438']))
    source_receipt = PROJECT / 'evidence/native-unwind-source-validation.json'
    # A fresh preserved export avoids deleting or resetting any prior work.
    source = Path(tempfile.mkdtemp(prefix='engine-source-', dir=build)).resolve()
    if not source.is_relative_to(build.resolve()):
        raise RuntimeError('Export escaped build directory')
    archive = run(['git', 'archive', '--format=tar', lock['commit']], upstream)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source, filter='data')
    run(['git', 'init', '-q'], source)
    run(['git', 'config', 'core.autocrlf', 'false'], source)
    run(['git', 'apply', '--check', patch], source)
    run(['git', 'apply', patch], source)
    for path, sha in patch_lock['patched_source_sha256'].items():
        check(source / path, sha)
    common = [zig, 'cc', '-target', 'x86_64-windows-gnu', '-std=c11', '-Wall', '-Werror', '-Wno-unused-parameter',
              '-I', source / 'native/mod-sdk', '-I', source / 'native/mod-loader',
              '-I', minhook / 'include', '-I', minhook / 'src']
    deps = [minhook / p for p in ('src/buffer.c', 'src/hook.c', 'src/trampoline.c', 'src/hde/hde64.c')]
    dll, test = build / 'hellforge_modloader-research.dll', build / 'engine_roster_test.exe'
    run([*common, '-shared', '-O2', '-s', source / 'native/mod-loader/hellforge_modloader.c', *deps, '-o', dll])
    run([*common, '-O1', PROJECT / 'tests/engine_roster_test.c', *deps, '-o', test])
    output = run([test, dll]).decode('utf-8').strip()
    match = re.fullmatch(r'engine roster: (\d+) checks passed; real patched consumers, synthetic process only', output)
    if not match:
        raise RuntimeError('Missing successful native test result: ' + output)
    unwind_output = json.loads(run([sys.executable, '-B', PROJECT / 'tools/build_unwind_offline.py', '--zig', zig]))
    unwind_receipt = PROJECT / 'evidence/native-producer-unwind-validation.json'
    receiver_unwind_output = json.loads(run([sys.executable, '-B', PROJECT / 'tools/build_receiver_unwind_offline.py', '--zig', zig]))
    receiver_unwind_receipt = PROJECT / 'evidence/native-receiver-unwind-validation.json'
    code_test = build / 'session_code_test.exe'
    code_dll = build / 'session_code_owner_test.dll'
    run([*common, '-shared', '-O1', PROJECT / 'tests/session_code_dll.c', '-o', code_dll])
    run([*common, '-O1', PROJECT / 'tests/session_code_test.c', *deps, '-o', code_test])
    code_output = run([code_test, build / 'producer-unwind-image.bin', build / 'receiver-unwind-image.bin', code_dll]).decode('utf-8').strip()
    code_match = re.fullmatch(r'session code: (\d+) checks passed; real HellForge chain, synthetic code only', code_output)
    if not code_match:
        raise RuntimeError('Missing session code ownership result: ' + code_output)
    property_dll=build/'property_image_test.dll'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O1','-Wall','-Werror','-Wno-unused-parameter',
         '-I',source/'native/mod-sdk',PROJECT/'mod/src/ep_property_image.cpp',PROJECT/'mod/src/ep_property_code.cpp',PROJECT/'mod/src/ep_property_gate.cpp',PROJECT/'mod/src/ep_getter_image.cpp',PROJECT/'mod/src/ep_mover_image.cpp',PROJECT/'mod/src/ep_insert_image.cpp',
         PROJECT/'mod/src/ep_remove_image.cpp',PROJECT/'mod/src/ep_classify_image.cpp',PROJECT/'mod/src/ep_registry_image.cpp',PROJECT/'mod/src/ep_departure_image.cpp',PROJECT/'mod/src/ep_arrival_image.cpp',PROJECT/'mod/src/ep_roster_gate.cpp',PROJECT/'tests/arrival_image_dll.cpp','-o',property_dll])
    property_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_property_images.py','--library',property_dll]))
    property_receipt=PROJECT/'evidence/property-image-validation.json'
    getter_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_getter_image.py','--library',property_dll,'--zig',zig]))
    getter_receipt=PROJECT/'evidence/native-getter-validation.json'
    mover_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_mover_image.py','--library',property_dll,'--zig',zig]))
    mover_receipt=PROJECT/'evidence/native-mover-validation.json'
    insert_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_insert_images.py','--library',property_dll,'--zig',zig]))
    insert_receipt=PROJECT/'evidence/native-insert-validation.json'
    remove_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_remove_images.py','--library',property_dll,'--zig',zig]))
    remove_receipt=PROJECT/'evidence/native-remove-validation.json'
    classify_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_classify_images.py','--library',property_dll,'--zig',zig]))
    classify_receipt=PROJECT/'evidence/native-classify-validation.json'
    registry_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_registry_images.py','--library',property_dll,'--zig',zig]))
    registry_receipt=PROJECT/'evidence/native-registry-validation.json'
    departure_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_departure_images.py','--library',property_dll,'--zig',zig]))
    departure_receipt=PROJECT/'evidence/native-departure-validation.json'
    arrival_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_arrival_images.py','--library',property_dll,'--zig',zig]))
    arrival_receipt=PROJECT/'evidence/native-arrival-validation.json'
    entity_remove_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_entity_remove.py','--library',property_dll]))
    entity_remove_receipt=PROJECT/'evidence/entity-remove-dispatch-validation.json'
    component33_dll=build/'component33_image_test.dll'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',
         PROJECT/'mod/src/ep_component33_image.cpp',PROJECT/'tests/component33_image_dll.cpp','-o',component33_dll])
    component33_receipt=PROJECT/'evidence/native-component33-validation.json'
    component33_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_images.py','--library',component33_dll,'--zig',zig,'--out',component33_receipt]))
    component33_classify_receipt=PROJECT/'evidence/native-component33-classify-validation.json'
    component33_classify_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_classify.py','--library',component33_dll,'--zig',zig,'--out',component33_classify_receipt]))
    component33_initialize_receipt=PROJECT/'evidence/native-component33-initialize-validation.json'
    component33_initialize_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_initialize.py','--library',component33_dll,'--zig',zig,'--out',component33_initialize_receipt]))
    component33_direct_receipt=PROJECT/'evidence/native-component33-direct-validation.json'
    component33_direct_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_direct.py','--library',component33_dll,'--zig',zig,'--out',component33_direct_receipt]))
    component33_transition_receipt=PROJECT/'evidence/native-component33-transition-validation.json'
    component33_transition_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_transition.py','--library',component33_dll,'--zig',zig,'--out',component33_transition_receipt]))
    component33_owner_receipt=PROJECT/'evidence/native-component33-owner-validation.json'
    component33_owner_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_owner.py','--library',component33_dll,'--zig',zig,'--out',component33_owner_receipt]))
    component33_readers_dll=build/'component33_readers_test.dll'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',
         PROJECT/'mod/src/ep_component33_readers.cpp',PROJECT/'tests/component33_readers_dll.cpp','-o',component33_readers_dll])
    component33_readers_receipt=PROJECT/'evidence/native-component33-readers-validation.json'
    component33_readers_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_readers.py','--library',component33_dll,'--readers',component33_readers_dll,'--zig',zig,'--out',component33_readers_receipt]))
    component33_consumers_dll=build/'component33_consumers_test.dll'
    run([zig,'c++','-target','x86_64-windows-gnu','-std=c++17','-shared','-O2','-Wall','-Wextra','-Werror',
         PROJECT/'mod/src/ep_component33_consumers.cpp',PROJECT/'tests/component33_consumers_dll.cpp','-o',component33_consumers_dll])
    component33_consumers_receipt=PROJECT/'evidence/native-component33-consumers-validation.json'
    component33_consumers_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_consumers.py','--library',component33_dll,'--consumers',component33_consumers_dll,'--zig',zig,'--out',component33_consumers_receipt]))
    component33_outer_dll=build/'component33_outer_test.dll'
    run([zig,'c++','-target','x86_64-windows-gnu','-std=c++17','-shared','-O2','-Wall','-Wextra','-Werror',
         PROJECT/'mod/src/ep_component33_outer.cpp',PROJECT/'tests/component33_outer_dll.cpp','-o',component33_outer_dll])
    component33_outer_receipt=PROJECT/'evidence/native-component33-outer-validation.json'
    component33_outer_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_outer.py','--library',component33_dll,'--consumers',component33_consumers_dll,'--outer',component33_outer_dll,'--zig',zig,'--out',component33_outer_receipt]))
    component33_resources_dll=build/'component33_resources_test.dll'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Wextra','-Werror',
         PROJECT/'mod/src/ep_component33_resources.cpp',PROJECT/'mod/src/ep_component33_consumers.cpp',PROJECT/'tests/component33_resources_dll.cpp','-o',component33_resources_dll])
    component33_resources_receipt=PROJECT/'evidence/native-component33-resources-validation.json'
    component33_resources_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resources.py','--library',component33_dll,'--consumers',component33_consumers_dll,'--outer',component33_outer_dll,'--resources',component33_resources_dll,'--out',component33_resources_receipt]))
    component33_family_receipt=PROJECT/'evidence/native-component33-family-validation.json'
    component33_family_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_family.py','--zig',zig,'--upstream',upstream,'--out',component33_family_receipt]))
    component33_storage_receipt=PROJECT/'evidence/native-component33-storage-validation.json'
    component33_storage_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_storage.py','--zig',zig,'--upstream',upstream,'--core',component33_dll,'--out',component33_storage_receipt]))
    component33_resource_owner_receipt=PROJECT/'evidence/native-component33-resource-owner-validation.json'
    component33_resource_owner_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resource_owner.py','--library',build/'component33_storage_test.dll','--resources',component33_resources_dll,'--core',component33_dll,'--out',component33_resource_owner_receipt]))
    component33_resource_call_receipt=PROJECT/'evidence/native-component33-resource-call-validation.json'
    component33_resource_call_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resource_call.py','--zig',zig,'--upstream',upstream,'--resources',component33_resources_dll,'--core',component33_dll,'--out',component33_resource_call_receipt]))
    component33_resource_services_receipt=PROJECT/'evidence/native-component33-resource-services-validation.json'
    component33_resource_services_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resource_services.py','--library',build/'component33_resource_call_test.dll','--resources',component33_resources_dll,'--core',component33_dll,'--out',component33_resource_services_receipt]))
    component33_resource_provider_receipt=PROJECT/'evidence/native-component33-resource-provider-validation.json'
    component33_resource_provider_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resource_provider.py','--zig',zig,'--upstream',upstream,'--resources',component33_resources_dll,'--core',component33_dll,'--out',component33_resource_provider_receipt]))
    component33_resource_release_receipt=PROJECT/'evidence/native-component33-resource-release-validation.json'
    component33_resource_release_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_component33_resource_release.py','--zig',zig,'--upstream',upstream,'--resources',component33_resources_dll,'--core',component33_dll,'--out',component33_resource_release_receipt]))
    creation_receipt=PROJECT/'evidence/creation-dispatch-validation.json'
    creation_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_creation_dispatch.py','--library',property_dll,'--out',creation_receipt,'--component33-library',component33_dll]))
    classify_fixture=build/'native-classify-fixture.bin'
    classify_fixture_receipt=json.loads(run([sys.executable,'-B',PROJECT/'tools/native_classify_fixture.py','--output',classify_fixture,'--property-library',property_dll]))
    classify_test=build/'native_classify_roster_test.exe'
    run([*common,'-O1',PROJECT/'tests/native_classify_roster_test.c',*deps,'-o',classify_test])
    classify_consumer=run([classify_test,classify_fixture,classify_fixture.with_suffix('.enter.bin'),classify_fixture.with_suffix('.leave.bin')]).decode('utf-8').strip()
    classify_match=re.fullmatch(r'native classification source: (\d+) checks passed; emitted classification storage to real loader consumers',classify_consumer)
    if not classify_match:raise RuntimeError('Missing classification consumer result: '+classify_consumer)
    fixture = build / 'native-roster-fixture.bin'
    fixture_receipt = json.loads(run([sys.executable, '-B', PROJECT / 'tools/native_roster_fixture.py', '--output', fixture, '--property-library', property_dll]))
    native_test = build / 'native_roster_test.exe'
    run([*common, '-O1', PROJECT / 'tests/native_roster_test.c', *deps, '-o', native_test])
    native_output = run([native_test, fixture, fixture.with_suffix('.removed.bin'), fixture.with_suffix('.rejoined.bin')]).decode('utf-8').strip()
    native_match = re.fullmatch(r'native roster source: (\d+) checks passed; emitted native insert storage to real loader consumers', native_output)
    if not native_match:
        raise RuntimeError('Missing native storage result: ' + native_output)
    owner_dll,owner_test=build/'roster_owner_test.dll',build/'roster_owner_test.exe'
    # Same flags as upstream ModKit: the owner must not require an unshipped
    # launcher/compiler flag patch to compile its exception boundary.
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Werror','-Wno-unused-parameter',
         PROJECT/'tests/roster_owner_dll.cpp','-o',owner_dll])
    run([*common,'-O1',PROJECT/'tests/roster_owner_test.c',*deps,'-o',owner_test])
    owner_output=run([owner_test,owner_dll,fixture,fixture.with_suffix('.removed.bin'),fixture.with_suffix('.rejoined.bin')]).decode('utf-8').strip()
    owner_match=re.fullmatch(r'roster owner: (\d+) checks passed; production DLL and real loader, synthetic memory only',owner_output)
    if not owner_match:raise RuntimeError('Missing roster owner result: '+owner_output)
    owner_result=dict(checks=int(owner_match[1]),actual_owner_dll=True,actual_loader_consumers=True,
        source_compiles_with_upstream_flags=True,serialized_read_write=True,stale_revision_refused_before_mutation=True,
        slot_generation_tombstones=True,overlapping_owners_refused=True,close_drains_readers_and_queued_writers=True,
        stale_provider_context_unavailable=True,callback_seh_quarantines_and_releases=True,
        bound_to_roster_group=False,all_game_writers_covered=False,authoritative_identity_source_bound=False,
        underlying_memory_reader_is_fixture=True,partial_write_rollback_implemented=False,game_access=False)
    gate_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_property_gates.py','--library',property_dll]))
    gate_receipt=PROJECT/'evidence/property-gate-validation.json'
    group_dll,group_test=build/'property_group_test.dll',build/'property_group_test.exe'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O1','-Wall','-Werror','-Wno-unused-parameter',
         '-I',source/'native/mod-sdk',PROJECT/'mod/src/ep_property_image.cpp',PROJECT/'mod/src/ep_getter_image.cpp',PROJECT/'tests/property_group_dll.cpp','-o',group_dll])
    run([*common,'-O1',PROJECT/'tests/property_group_test.c',*deps,'-o',group_test])
    group_output=run([group_test,group_dll]).decode('utf-8').strip()
    group_match=re.fullmatch(r'property group: (\d+) checks passed; real HellForge chains, synthetic bodies only',group_output)
    if not group_match: raise RuntimeError('Missing property group result: '+group_output)
    roster_gate_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_roster_gates.py','--library',property_dll,'--zig',zig]))
    roster_gate_receipt=PROJECT/'evidence/roster-gate-validation.json'
    roster_group_dll,roster_group_test=build/'roster_group_test.dll',build/'roster_group_test.exe'
    roster_emitters=[PROJECT/'mod/src'/('ep_'+n+'.cpp') for n in ('property_image','property_gate','getter_image','mover_image','insert_image','remove_image','classify_image','registry_image','departure_image','arrival_image','roster_gate')]
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O1','-Wall','-Werror','-Wno-unused-parameter',
         '-I',source/'native/mod-sdk',*roster_emitters,PROJECT/'mod/src/ep_roster_call.cpp',PROJECT/'mod/src/ep_roster_owner.cpp',PROJECT/'mod/src/ep_native_roster.cpp',PROJECT/'tests/roster_group_dll.cpp','-o',roster_group_dll])
    run([*common,'-O1',PROJECT/'tests/roster_group_test.c',*deps,'-o',roster_group_test])
    roster_scenarios=[]
    for index,after in [(0,0)]+[(i,j) for i in range(1,18) for j in (0,1)]:
        arguments=[] if not index else [index,after]
        result=run([roster_group_test,roster_group_dll,*arguments]).decode('utf-8').strip()
        found=re.fullmatch(r'roster group: (\d+) checks passed; scenario (\d+) (\d+)',result)
        if not found or (int(found[2]),int(found[3]))!=(index,after):raise RuntimeError('Missing roster group result: '+result)
        roster_scenarios.append(dict(failure_position=index,after_sdk=bool(after),checks=int(found[1])))
    roster_group_result=dict(checks=sum(x['checks'] for x in roster_scenarios),scenarios=roster_scenarios,entries=17,
        shared_storage_and_latch=True,internal_mover_bound_to_group=True,internal_association_bound_to_group=True,internal_departure_getter_bound_to_group=True,actual_hellforge_chains=True,
        cooperative_quiescence_tested=True,production_quiescence_provider_bound=False,active_data_rollback_implemented=False,
        native_execution_of_game_bodies=False,game_access=False)
    call_abi=json.loads(run([sys.executable,'-B',PROJECT/'tools/verify_roster_call_abi.py']))
    call_abi_receipt=PROJECT/'evidence/roster-call-abi-validation.json'
    roster_call_dll,roster_call_test=build/'roster_call_test.dll',build/'roster_call_test.exe'
    run([zig,'c++','-std=c++17','-target','x86_64-windows-gnu','-shared','-O2','-Wall','-Werror','-Wno-unused-parameter',
         '-I',source/'native/mod-sdk',*roster_emitters,PROJECT/'tests/roster_call_dll.cpp','-o',roster_call_dll])
    run([*common,'-O1',PROJECT/'tests/roster_call_test.c',*deps,'-o',roster_call_test])
    roster_bridge_fixture=build/'roster_call_test.unwind.bin'
    roster_bridge_unwind=json.loads(run([sys.executable,'-B',PROJECT/'tools/roster_bridge_unwind.py','--library',roster_call_dll,'--output',roster_bridge_fixture]))
    call_scenarios=[]
    for arguments in [['normal'],['nestedfault'],['depth'],['close'],['validatefault'],['endfault'],['exhausted'],['unavailable'],['departurefault'],['departureclose'],['departurerace'],['scopecommit'],['scopeclose'],['scopesnapshot'],['scopefault'],['scopechain']]+[[i,j] for i in range(1,18) for j in (0,1)]:
        result=run([roster_call_test,roster_call_dll,*arguments]).decode('utf-8').strip()
        found=re.fullmatch(r'roster calls: (\d+) checks passed; (?:mode \w+|scenario \d+ \d+)',result)
        if not found:raise RuntimeError('Missing owned roster call result: '+result)
        call_scenarios.append(dict(arguments=arguments,checks=int(found[1])))
    roster_call_result=dict(checks=sum(x['checks'] for x in call_scenarios),scenarios=call_scenarios,entries=17,
        actual_owner_dll=True,actual_hellforge_chains=True,old_and_new_calls_owned=True,route_selected_under_owner=True,
        departure_synthetic_indirect_tail_owned=True,departure_nested_delete_fault_quarantines=True,departure_tail_close_and_commit_drain=True,
        departure_indirect_tail_target_abi_verified=False,departure_full_cleanup_transaction_owned=False,
        entity_remove_original_dispatcher_scoped=True,entity_remove_two_phase_gap_drain=True,entity_remove_nested_fault_quarantines=True,
        entity_remove_live_next_chain_preserved=True,entity_remove_original_rollback=False,full_original_dispatcher_emulated=False,
        producer_six_arguments_preserved=True,float_register_arguments_and_result_preserved=True,
        nonvolatile_gpr_and_xmm_preserved=True,volatile_return_registers_preserved=True,windows_bridge_unwind=roster_bridge_unwind,
        nested_native_calls_share_scope=True,commit_staging_and_cleanup_owned_after_scope_entry=True,close_drains_and_cancels_queued=True,
        callback_seh_quarantines_and_releases=True,abi=call_abi,abi_receipt_sha256=digest(call_abi_receipt),
        native_execution_of_game_bodies=False,production_quiescence_provider_bound=False,
        all_game_writers_covered=False,external_tail_abi_verified=False,authoritative_identity_source_bound=False,game_access=False)
    sync_input, sync_routed, sync_received = (build / n for n in ('native-sync-input.json', 'native-sync-routed.json', 'native-sync-received.json'))
    sync_script = PROJECT / 'tools/native_roster_sync.py'
    run([sys.executable, '-B', sync_script, 'produce', '--output', sync_input, '--property-library', property_dll])
    backend_output = run(['dotnet', 'run', '--project', PROJECT / 'tests/backend/Backend.csproj',
                          f'-p:HellForgeRoot={upstream.as_posix()}', '-p:PublishAot=false', '--configuration', 'Release',
                          '--', '--native-roster-input', sync_input, '--native-roster-output', sync_routed]).decode('utf-8')
    backend_rows = [json.loads(line) for line in backend_output.splitlines() if line.startswith('{')]
    backend_result = next((r for r in backend_rows if r.get('suite') == 'hellforge_backend_eight_nodes' and r.get('passed')), None)
    if backend_result is None:
        raise RuntimeError('Missing native property relay test result')
    run([sys.executable, '-B', sync_script, 'consume', '--input', sync_input, '--routed', sync_routed, '--output', sync_received, '--property-library', property_dll])
    sync_test = build / 'native_roster_sync_test.exe'
    sync_images = [build / f'native-sync-{node}-{phase}.bin' for node in range(1,9) for phase in ('before','after')]
    run([*common, '-O1', PROJECT / 'tests/native_roster_sync_test.c', *deps, '-o', sync_test])
    sync_output = run([sync_test, *sync_images]).decode('utf-8').strip()
    sync_match = re.fullmatch(r'native roster sync: (\d+) checks passed; eight synthetic recipients, real patched consumers', sync_output)
    if not sync_match:
        raise RuntimeError('Missing native property consumer result: ' + sync_output)
    synced = json.loads(sync_received.read_bytes())
    sync_receipt = {'consumer_checks': int(sync_match[1]), 'backend': backend_result,
                    'native_producers': 8, 'native_insertions': 64, 'native_receivers': len(synced['native_receivers']),
                    'native_getter_queries':len(synced['native_getter_queries']),
                    'native_getter_gate_executed':synced['native_getter_gate_executed'],
                    'relay_checks': json.loads(sync_routed.read_bytes())['relay_checks'],
                    'game_serializer_executed': False, 'game_entity_dispatch_executed': False,
                    'real_admission_executed': False, 'passed': True}
    sync_receipt['producer_has_windows_unwind_variant'] = True
    sync_receipt['receiver_has_windows_unwind_variant'] = True
    sync_receipt['property_images_emitted_by_native_mod_code'] = True
    sync_receipt['mover_image_emitted_by_native_mod_code'] = True
    sync_receipt['insert_images_emitted_by_native_mod_code'] = True
    receipt = {
        'schema': 'hellforge_engine_roster_validation_v1',
        'verified_at_utc': datetime.now(timezone.utc).isoformat(),
        'upstream_commit': lock['commit'], 'sdk': 13, 'game_build': '25480438',
        'private_extension_version': 1, 'checks': int(match[1]), 'passed': True,
        'native_storage_checks': int(native_match[1]), 'native_storage_fixture': fixture_receipt,
        'native_property_sync': sync_receipt,
        'native_producer_unwind': {**unwind_output, 'validation_sha256': digest(unwind_receipt)},
        'native_receiver_unwind': {**receiver_unwind_output, 'validation_sha256': digest(receiver_unwind_receipt)},
        'native_property_images': {**property_output,'validation_sha256':digest(property_receipt)},
        'native_getter':{**getter_output,'validation_sha256':digest(getter_receipt)},
        'native_mover':{**mover_output,'validation_sha256':digest(mover_receipt)},
        'native_insert':{**insert_output,'validation_sha256':digest(insert_receipt)},
        'native_remove':{**remove_output,'validation_sha256':digest(remove_receipt)},
        'roster_group':roster_group_result,
        'roster_owner':owner_result,
        'roster_calls':roster_call_result,
        'roster_gates':{**roster_gate_output,'validation_sha256':digest(roster_gate_receipt)},
        'native_classify':{**classify_output,'validation_sha256':digest(classify_receipt)},
        'native_registry':{**registry_output,'validation_sha256':digest(registry_receipt)},
        'native_arrival':{**arrival_output,'validation_sha256':digest(arrival_receipt)},
        'native_departure':{**departure_output,'validation_sha256':digest(departure_receipt)},
        'native_entity_remove_dispatch':{**entity_remove_output,'validation_sha256':digest(entity_remove_receipt)},
        'native_creation_dispatch':{**creation_output,'validation_sha256':digest(creation_receipt)},
        'native_component33':{**component33_output,'validation_sha256':digest(component33_receipt)},
        'native_component33_classify':{**component33_classify_output,'validation_sha256':digest(component33_classify_receipt)},
        'native_component33_initialize':{**component33_initialize_output,'validation_sha256':digest(component33_initialize_receipt)},
        'native_component33_direct':{**component33_direct_output,'validation_sha256':digest(component33_direct_receipt)},
        'native_component33_transition':{**component33_transition_output,'validation_sha256':digest(component33_transition_receipt)},
        'native_component33_owner':{**component33_owner_output,'validation_sha256':digest(component33_owner_receipt)},
        'native_component33_readers':{**component33_readers_output,'validation_sha256':digest(component33_readers_receipt)},
        'native_component33_consumers':{**component33_consumers_output,'validation_sha256':digest(component33_consumers_receipt)},
        'native_component33_outer':{**component33_outer_output,'validation_sha256':digest(component33_outer_receipt)},
        'native_component33_resources':{**component33_resources_output,'validation_sha256':digest(component33_resources_receipt)},
        'native_component33_family':{**component33_family_output,'validation_sha256':digest(component33_family_receipt)},
        'native_component33_storage':{**component33_storage_output,'validation_sha256':digest(component33_storage_receipt)},
        'native_component33_resource_owner':{**component33_resource_owner_output,'validation_sha256':digest(component33_resource_owner_receipt)},
        'native_component33_resource_call':{**component33_resource_call_output,'validation_sha256':digest(component33_resource_call_receipt)},
        'native_component33_resource_services':{**component33_resource_services_output,'validation_sha256':digest(component33_resource_services_receipt)},
        'native_component33_resource_provider':{**component33_resource_provider_output,'validation_sha256':digest(component33_resource_provider_receipt)},
        'native_component33_resource_release':{**component33_resource_release_output,'validation_sha256':digest(component33_resource_release_receipt)},
        'native_classify_storage':{'checks':int(classify_match[1]),**classify_fixture_receipt},
        'native_property_gates':{**gate_output,'validation_sha256':digest(gate_receipt)},
        'property_group':{'checks':int(group_match[1]),'entries':['producer','receiver','entity_network_getter'],'shared_storage_binding':True,'actual_hellforge_chains':True,
                         'partial_publication_failure_forwards':True,'cooperative_quiescence_tested':True,
                         'production_quiescence_provider_bound':False,'active_data_rollback_implemented':False,
                         'native_execution_of_game_bodies':False,'game_access':False},
        'session_code_owner': {'checks': int(code_match[1]), 'actual_hellforge_hook_chain': True,
                               'synthetic_chain_links': 5, 'module_pin_survived_free_library': True,
                               'game_candidate_executed_natively': False,
                               'automatic_mod_init_binding': False, 'game_access': False},
        'original_unwind_source': {**source_replay, 'source_gate_tests': source_tests,
                                   'validation_sha256': digest(source_receipt)},
        'replayed_patch': patch_lock['patch'], 'patch_sha256': digest(patch),
        'patched_source_sha256': patch_lock['patched_source_sha256'],
        'test_source_sha256': {p: digest(PROJECT / p) for p in (
            'tests/engine_roster_test.c', 'tests/native_roster_test.c', 'tools/native_roster_fixture.py',
            'tests/native_fixture.h', 'tests/native_roster_sync_test.c', 'tools/native_roster_sync.py',
            'tools/native_producer_unwind.py', 'tools/build_unwind_offline.py', 'tests/native_producer_unwind_test.c',
            'tools/native_receiver_unwind.py', 'tools/build_receiver_unwind_offline.py',
            'tools/native_unwind_source.py', 'tools/verify_native_unwind_source.py',
            'tests/test_native_unwind_source.py', 'native-unwind-source.lock.json',
            'tests/session_code_test.c', 'mod/src/ep_session_code.h', 'mod/src/ep_session_code.cpp',
            'tests/session_code_dll.c', 'tests/session_code_dll.h',
            'mod/src/ep_property_image.cpp','mod/src/ep_property_image.h','mod/src/ep_property_templates.h',
            'mod/src/ep_property_code.cpp','mod/src/ep_property_code.h','tests/property_image_dll.cpp',
            'tools/generate_property_templates.py','tools/native_property_library.py','tools/validate_property_images.py',
            'mod/src/ep_property_gate.h','mod/src/ep_property_gate.cpp','mod/src/ep_property_group.h','mod/src/ep_property_group.cpp',
            'tests/property_group_dll.h','tests/property_group_dll.cpp','tests/property_group_test.c','tools/validate_property_gates.py',
            'native-mover.lock.json','tools/native_mover_image.py','tools/generate_mover_template.py','tools/validate_mover_image.py',
            'mod/src/ep_mover_image.h','mod/src/ep_mover_image.cpp','mod/src/ep_mover_template.h',
            'native-insert.lock.json','tools/native_insert_image.py','tools/generate_insert_templates.py','tools/validate_insert_images.py',
            'mod/src/ep_insert_image.h','mod/src/ep_insert_image.cpp','mod/src/ep_insert_templates.h',
            'native-remove.lock.json','tools/native_remove_image.py','tools/generate_remove_templates.py','tools/validate_remove_images.py',
            'mod/src/ep_remove_image.h','mod/src/ep_remove_image.cpp','mod/src/ep_remove_templates.h',
            'native-arrival.lock.json','tools/native_arrival_image.py','tools/generate_arrival_template.py','tools/validate_arrival_images.py','tools/native_arrival_library.py',
            'mod/src/ep_arrival_image.h','mod/src/ep_arrival_image.cpp','mod/src/ep_arrival_templates.h','tests/arrival_image_dll.cpp','tests/native_arrival_unwind_test.c',
            'native-departure.lock.json','tools/native_departure_image.py','tools/generate_departure_template.py','tools/validate_departure_images.py','tools/native_departure_library.py',
            'mod/src/ep_departure_image.h','mod/src/ep_departure_image.cpp','mod/src/ep_departure_templates.h','tests/departure_image_dll.cpp','tests/native_departure_unwind_test.c',
            'native-registry.lock.json','tools/native_registry_image.py','tools/generate_registry_templates.py','tools/validate_registry_images.py',
            'mod/src/ep_registry_image.h','mod/src/ep_registry_image.cpp','mod/src/ep_registry_templates.h',
            'native-classify.lock.json','tools/native_classify_image.py','tools/generate_classify_templates.py','tools/validate_classify_images.py',
            'mod/src/ep_classify_image.h','mod/src/ep_classify_image.cpp','mod/src/ep_classify_templates.h',
            'tools/native_classify_fixture.py','tests/native_classify_roster_test.c',
            'mod/src/ep_roster_gate.h','mod/src/ep_roster_gate.cpp','mod/src/ep_roster_group.h','mod/src/ep_roster_group.cpp',
            'tests/roster_group_dll.h','tests/roster_group_dll.cpp','tests/roster_group_test.c','tools/validate_roster_gates.py',
            'mod/src/ep_roster_owner.h','mod/src/ep_roster_owner.cpp',
            'tests/roster_owner_dll.h','tests/roster_owner_dll.cpp','tests/roster_owner_test.c',
            'mod/src/ep_roster_call.h','mod/src/ep_roster_call.cpp','tools/verify_roster_call_abi.py','native-entity-remove.lock.json',
            'tools/validate_entity_remove.py','tools/validate_creation_dispatch.py','native-creation-dispatch.lock.json',
            'tools/native_component33_image.py','tools/native_component33_library.py','tools/generate_component33_templates.py','tools/validate_component33_images.py','tools/validate_component33_classify.py',
            'native-component33.lock.json','mod/src/ep_component33_image.h','mod/src/ep_component33_image.cpp','mod/src/ep_component33_templates.h',
            'tests/component33_image_dll.cpp','tests/native_component33_unwind_test.c',
            'tools/component33_initialization_fixture.py','tools/validate_component33_initialize.py','tests/native_component33_initialize_unwind_test.c',
            'tools/validate_component33_direct.py','tools/validate_component33_transition.py',
            'native-component33-readers.lock.json','tools/native_component33_readers.py','tools/validate_component33_readers.py',
            'mod/src/ep_component33_readers.h','mod/src/ep_component33_readers.cpp','mod/src/ep_component33_readers_template.h',
            'tests/component33_readers_dll.cpp','tests/native_component33_readers_unwind_test.c',
            'mod/src/ep_component33_consumers.h','mod/src/ep_component33_consumers.cpp','mod/src/ep_component33_consumers_template.h','tools/native_component33_consumers.py','native-component33-consumers.lock.json',
            'tools/validate_component33_consumers.py','tests/component33_consumers_dll.cpp','tests/native_component33_consumers_unwind_test.c',
            'mod/src/ep_component33_outer.h','mod/src/ep_component33_outer.cpp','mod/src/ep_component33_outer_template.h','tools/native_component33_outer.py','native-component33-outer.lock.json',
            'tools/validate_component33_outer.py','tests/component33_outer_dll.cpp','tests/native_component33_outer_unwind_test.c',
            'mod/src/ep_component33_resources.h','mod/src/ep_component33_resources.cpp','mod/src/ep_component33_resources_template.h','native-component33-resources.lock.json',
            'tools/native_component33_resources.py','tools/validate_component33_resources.py','tests/component33_resources_dll.cpp',
            'mod/src/ep_component33_family.h','mod/src/ep_component33_family.cpp','tests/component33_family_dll.cpp','tools/validate_component33_family.py',
            'mod/src/ep_component33_storage.h','mod/src/ep_component33_storage.cpp','tests/component33_storage_dll.cpp','tools/validate_component33_storage.py',
            'tools/validate_component33_resource_owner.py',
            'tools/validate_component33_resource_call.py','tests/component33_resource_call_dll.cpp','mod/src/ep_component33_resource_call.h','mod/src/ep_component33_resource_call.cpp',
            'tools/validate_component33_resource_services.py',
            'tools/validate_component33_resource_provider.py','tools/native_component33_resource_provider.py','native-component33-resource-provider.lock.json',
            'mod/src/ep_component33_resource_provider.cpp','mod/src/ep_component33_resource_provider.h','mod/src/ep_component33_resource_provider_template.h','tests/component33_resource_provider_dll.cpp',
            'tools/validate_component33_resource_release.py','tests/component33_resource_release_dll.cpp',
            'native-component33-owner.lock.json','tools/native_component33_owner.py','tools/validate_component33_owner.py',
            'mod/src/ep_component33_owner_template.h','tests/native_component33_owner_unwind_test.c',
            'tests/roster_call_dll.h','tests/roster_call_dll.cpp','tests/roster_call_test.c',
            'tests/roster_call_abi.h','tools/roster_bridge_unwind.py',
            'native-getter.lock.json','tools/native_getter_image.py','tools/generate_getter_template.py','tools/validate_getter_image.py',
            'mod/src/ep_getter_image.h','mod/src/ep_getter_image.cpp','mod/src/ep_getter_template.h',
            'tests/backend/Program.cs', 'tests/backend/Backend.csproj',
            'mod/src/ep_native_roster.cpp', 'mod/src/ep_native_roster.h', 'mod/src/ep_roster_api.h',
            'native-storage.lock.json', 'tools/build_engine_offline.py', 'engine/patch.lock.json', 'upstream.lock.json')},
        'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in (component33_readers_dll,component33_dll,roster_bridge_fixture,roster_call_dll,roster_call_test,owner_dll,owner_test,roster_group_dll,roster_group_test,dll, test, native_test, code_test, code_dll, property_dll, group_dll, group_test, classify_test, classify_fixture, classify_fixture.with_suffix('.enter.bin'), classify_fixture.with_suffix('.leave.bin'), fixture, fixture.with_suffix('.removed.bin'), fixture.with_suffix('.rejoined.bin'), sync_test, sync_input, sync_routed, sync_received, *sync_images)},
        'game_started': False, 'game_checked': False, 'game_read': False, 'installed': False,
        'native_game_storage_expanded': False, 'production_provider_bound': False,
        'runtime_verified': False, 'multiplayer_verified': False, 'public_release_allowed': False,
    }
    (PROJECT / 'evidence/engine-roster-validation.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': receipt['checks'], 'native_storage_checks': receipt['native_storage_checks'], 'session_code_checks': int(code_match[1]), 'property_images':property_output,'property_gates':gate_output,'property_group_checks':int(group_match[1]),'getter':getter_output,'mover':mover_output,'insert':insert_output,'remove':remove_output,'classify':classify_output,'registry':registry_output,'departure':departure_output,'arrival':arrival_output,'classify_storage_checks':int(classify_match[1]),'roster_gates':roster_gate_output,'roster_group_checks':roster_group_result['checks'],'roster_owner_checks':owner_result['checks'],'native_getter_queries':sync_receipt['native_getter_queries'], 'sync_consumer_checks': sync_receipt['consumer_checks'], 'native_receivers': sync_receipt['native_receivers'], 'patch_replayed': True, 'game_access': False}))


if __name__ == '__main__':
    main()
