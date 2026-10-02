"""Verify the frozen v0.14 offline delivery, without accessing game processes.

Checks file pins, report counts, local document links and a fresh CLI bundle.
Old suites and historical research replays are not rerun. --write refreshes
only delivery_checks.json after all checks succeed; default compares it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESEARCH = ROOT / 'five_player_feasibility_20260927'
VERIFY = HERE / 'verification'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_bytes())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def pin(path, expected):
    require(sha(path) == expected, f'Fingerprint mismatch: {path}')


def check():
    prior_path = VERIFY / 'delivery_checks_v0.13.json'
    pin(prior_path, '49543cb5ed13a64421baee652b133fbf8850101a953a7a08b93e484861216d9a')
    receipt = read(prior_path)
    manifest = read(HERE / 'candidate-manifest.json')
    require(manifest['version'] == '0.14.0-offline', 'Wrong release')
    for field in ('installable_mod', 'game_integration', 'multiplayer_verified'):
        require(manifest[field] is False, field)
    for name, digest in manifest['source_sha256'].items():
        pin(HERE / name, digest)
    for name, digest in receipt['source_sha256'].items():
        pin(HERE / name, digest)
    counters = dict(report_source_references=0, report_evidence_references=0,
                    pinned_test_sources=0, test_dependency_references=0)
    groups = executions = 0
    for name in manifest['validation_reports']:
        path = HERE / name
        report = read(path)
        require(report['status'] == 'passed', name)
        for field in ('failure_count', 'error_count', 'failures', 'errors'):
            require(not report.get(field), f'{name}: {field}')
        if name in receipt['validation_reports']:
            pin(path, receipt['validation_reports'][name]['sha256'])
        elif path.name == 'native_roster_arrival_tests.json':
            pin(path, '3c9d4921951bc6ae2777c0b02f682b36df44853d89c6d58c79fcd2d3e94530ad')
        sources = report['source_sha256']
        evidence = report['evidence_sha256']
        if isinstance(sources, str):
            sources = {'Source/pool_preflight.lua': sources}
            evidence = {'indexed_float_pool_triple_members_evidence_v3.json': evidence}
        for source, digest in sources.items():
            pin(HERE / source.replace('\\', '/'), digest)
            counters['report_source_references'] += 1
        for source, digest in evidence.items():
            pin(RESEARCH / Path(source.replace('\\', '/')).name, digest)
            counters['report_evidence_references'] += 1
        digest = report.get('test_sha256', report.get('test_source_sha256'))
        if digest:
            test = HERE / 'tests' / ('test_' + path.stem.removesuffix('_tests') + '.py')
            pin(test, digest)
            counters['pinned_test_sources'] += 1
        for source, digest in report.get('test_dependency_sha256', {}).items():
            pin(HERE / source.replace('\\', '/'), digest)
            counters['test_dependency_references'] += 1
        count = report.get('test_methods_run', report.get('tests'))
        runs = len(report.get('emulator_runs', []))
        groups += count
        executions += runs
        if name not in receipt['validation_reports']:
            receipt['validation_reports'][name] = dict(
                sha256=sha(path), tests=count, source_hashes_match=True,
                evidence_hashes_match=True, test_source_hash_matches=True,
                test_dependency_hashes_match=True, emulator_executions=runs,
                execution_counts=report['execution_counts'],
                nested_saved_fd9af0_entries_not_added_to_total=25,
                contract_stubs=report['contract_stubs'])
    require((groups, executions) == (149, 4314), 'Unexpected totals')
    args = {'evidence': 'roster_arrival_native_evidence.json',
            'registry-evidence': 'roster_registry_update_native_evidence.json',
            'departure-evidence': 'roster_departure_native_evidence.json',
            'getter-evidence': 'roster_getter_native_evidence.json',
            'classify-evidence': 'roster_classify_native_evidence.json',
            'remove-evidence': 'roster_remove_native_evidence.json',
            'insert-evidence': 'roster_insert_native_evidence.json',
            'move-evidence': 'roster_move_native_evidence.json',
            'producer-evidence': 'roster_property_producer_native_evidence.json',
            'receiver-evidence': 'roster_property_receive_evidence.json',
            'player-count-evidence': 'roster_player_count_native_evidence.json',
            'context-evidence': 'roster_departure_callee_evidence.json'}
    address = VERIFY / 'native_roster_arrival_addresses_synthetic.json'
    sample = VERIFY / 'native_roster_arrival_bundle_synthetic.json'
    command = [sys.executable, '-B', str(HERE / 'Native/roster_arrival.py')]
    for key, value in args.items():
        command += ['--' + key, str(RESEARCH / value)]
    with tempfile.TemporaryDirectory(prefix='hd2-v014-offline-') as temp:
        output = Path(temp) / 'bundle.json'
        subprocess.run(command + ['--addresses', str(address), '--output', str(output)],
                       check=True, capture_output=True, text=True)
        require(output.read_bytes() == sample.read_bytes(), 'CLI bundle differs')
    bundle = read(sample)
    require(bundle['base_bundle'] == read(VERIFY / 'native_roster_registry_update_bundle_synthetic.json'),
            'Embedded v0.13 bundle differs')
    evidence_path = RESEARCH / args['evidence']
    require(evidence_path.read_bytes() == (RESEARCH / 'roster_arrival_native_recheck.json').read_bytes(),
            'Arrival evidence/recheck differ')
    program = RESEARCH / 'roster_arrival_native_replay.py'
    compile(program.read_bytes(), str(program), 'exec')
    receipt['research_artifacts'][args['evidence']] = dict(
        sha256=sha(evidence_path), recheck_identical=True,
        program_sha256=sha(program), syntax='passed',
        scope='Frozen complete 6054F0 and test-only FD9AF0; existing evidence checked, capture replay not rerun')
    documents = set(receipt['documents_sha256'])
    documents.update(str(p.relative_to(ROOT)).replace('\\', '/') for p in (
        HERE / 'NATIVE_ROSTER_ARRIVAL.zh-TW.md',
        VERIFY / 'native_roster_arrival_review.zh-TW.md',
        VERIFY / 'native_roster_arrival_test_review.zh-TW.md',
        RESEARCH / 'roster_arrival_native_findings.zh-TW.md',
        RESEARCH / 'roster_arrival_native_prerequisites.zh-TW.md',
        RESEARCH / 'roster_mask_reader_findings.zh-TW.md',
        RESEARCH / 'PEER_ADMISSION_PRIORITY.zh-TW.md'))
    link_count = 0
    for name in sorted(documents):
        path = ROOT / name
        for target in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', path.read_text(encoding='utf-8')):
            target = target.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z]+:', target):
                continue
            require((path.parent / unquote(target)).exists(), f'Broken link: {name}: {target}')
            link_count += 1
    receipt['documents_sha256'] = {name: sha(ROOT / name) for name in sorted(documents)}
    receipt['local_document_links'] = link_count
    pin(HERE / 'requirements-native-tests.txt', receipt['native_test_requirements_sha256'])
    pin(ROOT / 'github_handoff_20260927/GOAL_OBJECTIVE.zh-TW.md', receipt['objective_sha256'])
    receipt.update(candidate_version=manifest['version'], manifest_sha256=sha(HERE / 'candidate-manifest.json'),
                   source_sha256=manifest['source_sha256'], test_groups=groups,
                   native_emulator_executions=executions, prior_delivery_receipt_sha256=sha(prior_path))
    receipt['current_delivery_pin_checks'] = dict(
        candidate_sources=16, validation_reports=15, unchanged_prior_candidate_sources=15,
        unchanged_prior_validation_reports=14, **counters, prior_suites_rerun=False,
        arrival_suite_rechecked_during_oracle_review=True, new_bundle_cli_regenerated=True,
        embedded_registry_artifact_match=True)
    receipt['synthetic_native_roster_arrival_bundle_example'] = dict(
        sha256=sha(sample), addresses_sha256=sha(address), cli_regeneration_byte_identical=True,
        root_size_bytes=bundle['arrival']['size_bytes'], roster_function_count=16,
        known_regions=len(bundle['known_regions']), embedded_registry_artifact_identical=True,
        host_native_code_executed=False)
    receipt['native_execution_count_note'] = (
        '4314 is total suite executions/observations, not candidate successes. '
        'Arrival adds 4 complete original baselines, 21 candidate complete returns and 17 rejections. '
        'Its 25 nested FD9AF0 entries and review rerun are not added. Historical prefix observations, '
        'original expected counterexamples and rejection cases remain included as documented in v0.13.')
    receipt['scope'] = (
        'v0.14 offline 6054F0 state-update delivery. Frozen reports and all their source/evidence/test pins '
        'checked; CLI rebuilt byte-identically with unchanged embedded v0.13. Arrival oracle review reran '
        'only its five methods and matched all42 frozen execution records. Old suites and historical '
        'research replays were not rerun; inherited regeneration statements are historical. '
        'No process access, new capture, host native execution, installation or multiplayer validation. '
        'This tool checks release files and links, not semantic correctness or eight-account acceptance.')
    receipt['delivery_verifier_sha256'] = sha(Path(__file__))
    followup = read(RESEARCH / 'roster_mask_reader_probe.json')
    require(followup['status'] == 'passed' and followup['prefix_observations'] == 24,
            'Mask prefix investigation incomplete')
    pin(RESEARCH / 'roster_mask_reader_probe.py', followup['program_sha256'])
    pin(RESEARCH / 'roster_mask_reader_evidence.json', followup['evidence_sha256'])
    pin(RESEARCH / 'roster_mask_reader_replay.py',
        read(RESEARCH / 'roster_mask_reader_evidence.json')['replay_sha256'])
    receipt['followup_mask_reader_investigation'] = dict(
        files_sha256={name: sha(RESEARCH / name) for name in (
            'roster_mask_reader_replay.py', 'roster_mask_reader_evidence.json',
            'roster_mask_reader_probe.py', 'roster_mask_reader_probe.json',
            'roster_mask_reader_findings.zh-TW.md')},
        prefix_observations=24, nested_leaf_calls=48, full_function_executed=False,
        candidate_emitted=False, included_in_delivery_suite_totals=False)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    receipt = check()
    path = VERIFY / 'delivery_checks.json'
    if args.write:
        path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    else:
        require(read(path) == receipt, 'Receipt differs; inspect changes before using --write')
    print(json.dumps({key: receipt[key] for key in
                      ('status', 'candidate_version', 'test_groups', 'native_emulator_executions', 'local_document_links')}))
