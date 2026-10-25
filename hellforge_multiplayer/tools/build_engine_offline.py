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
    fixture = build / 'native-roster-fixture.bin'
    fixture_receipt = json.loads(run([sys.executable, '-B', PROJECT / 'tools/native_roster_fixture.py', '--output', fixture]))
    native_test = build / 'native_roster_test.exe'
    run([*common, '-O1', PROJECT / 'tests/native_roster_test.c', *deps, '-o', native_test])
    native_output = run([native_test, fixture, fixture.with_suffix('.removed.bin'), fixture.with_suffix('.rejoined.bin')]).decode('utf-8').strip()
    native_match = re.fullmatch(r'native roster source: (\d+) checks passed; emitted native insert storage to real loader consumers', native_output)
    if not native_match:
        raise RuntimeError('Missing native storage result: ' + native_output)
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
         '-I',source/'native/mod-sdk',PROJECT/'mod/src/ep_property_image.cpp',PROJECT/'mod/src/ep_property_code.cpp',
         PROJECT/'tests/property_image_dll.cpp','-o',property_dll])
    property_output=json.loads(run([sys.executable,'-B',PROJECT/'tools/validate_property_images.py','--library',property_dll]))
    property_receipt=PROJECT/'evidence/property-image-validation.json'
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
                    'relay_checks': json.loads(sync_routed.read_bytes())['relay_checks'],
                    'game_serializer_executed': False, 'game_entity_dispatch_executed': False,
                    'real_admission_executed': False, 'passed': True}
    sync_receipt['producer_has_windows_unwind_variant'] = True
    sync_receipt['receiver_has_windows_unwind_variant'] = True
    sync_receipt['property_images_emitted_by_native_mod_code'] = True
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
            'tests/backend/Program.cs', 'tests/backend/Backend.csproj',
            'mod/src/ep_native_roster.cpp', 'mod/src/ep_native_roster.h', 'mod/src/ep_roster_api.h',
            'native-storage.lock.json', 'tools/build_engine_offline.py', 'engine/patch.lock.json', 'upstream.lock.json')},
        'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)} for p in (dll, test, native_test, code_test, code_dll, property_dll, fixture, fixture.with_suffix('.removed.bin'), fixture.with_suffix('.rejoined.bin'), sync_test, sync_input, sync_routed, sync_received, *sync_images)},
        'game_started': False, 'game_checked': False, 'game_read': False, 'installed': False,
        'native_game_storage_expanded': False, 'production_provider_bound': False,
        'runtime_verified': False, 'multiplayer_verified': False, 'public_release_allowed': False,
    }
    (PROJECT / 'evidence/engine-roster-validation.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': receipt['checks'], 'native_storage_checks': receipt['native_storage_checks'], 'session_code_checks': int(code_match[1]), 'property_images':property_output, 'sync_consumer_checks': sync_receipt['consumer_checks'], 'native_receivers': sync_receipt['native_receivers'], 'patch_replayed': True, 'game_access': False}))


if __name__ == '__main__':
    main()
