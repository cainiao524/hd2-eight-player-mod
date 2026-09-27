"""Summarize completed runs, retaining failed attempts and their resolution."""
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parent
initial = json.loads((root / 'checks-v2/results.json').read_bytes())
test_runs = [r for r in initial['checks'] if r['name'] != 'replay']
if len(test_runs) != 10 or not all(r['passed'] for r in test_runs):
    raise ValueError('research tests or mutation outcome failed')
counts = {}
for mode in ('normal', 'optimized'):
    total = 0
    for log in sorted((root / 'checks-v2').glob(mode + '-test_*.log')):
        text = log.read_text(encoding='utf-8')
        match = re.search(r'Ran (\d+) tests? in ', text)
        if match is None or not text.rstrip().endswith('OK'):
            raise ValueError('test log not successful: ' + str(log))
        total += int(match.group(1))
    if total != 118:
        raise ValueError('unexpected test count')
    counts[mode] = total
analysis = json.loads((root / 'reference-replay/analysis.json').read_bytes())
evidence = json.loads((root / 'replay-final/generation-evidence.json').read_bytes())
comparison = json.loads((root / 'compare-final/generation-comparison.json').read_bytes())
if analysis['analysis_fingerprint'] != 'a1c7d72ba38d91f3526af7d8a58f2eee0ec235198d9a28d454abf2bc84eca1b3':
    raise ValueError('reference replay changed')
if evidence['evidence_fingerprint'] != '91a2468bb745b6f266ca7aa3f537e7dba35569fd937c0a8ee4a39a0b46d65ac2':
    raise ValueError('old evidence replay changed')
if comparison['status'] != 'unchanged_still_unverified':
    raise ValueError('unexpected comparison result')
settings = root / 'settings-findings-v2.json'
if settings.read_bytes() != (root / 'settings-findings-optimized-v2.json').read_bytes():
    raise ValueError('settings evidence differs under optimized Python')
entity = json.loads((root / 'entity/test-results.json').read_bytes())
indirect = json.loads((root / 'indirect/verification-results.json').read_bytes())
if any(entity[mode]['tests'] != 6 or entity[mode]['exit_code'] != 0 for mode in ('normal', 'optimized')):
    raise ValueError('entity tests failed')
if any(entity['verifier_fault_injection'][mode]['exit_code'] != 1 for mode in ('normal', 'optimized')):
    raise ValueError('entity mutation not detected')
if len(indirect) != 4 or not all(r['expected_status_observed'] for r in indirect):
    raise ValueError('indirect verification failed')
for row in indirect:
    expected = 1 if row['injected_instruction_fault'] else 0
    if row['exit_code'] != expected or 'Ran 7 tests' not in row['stderr']:
        raise ValueError('indirect test count or result changed')
result = {
    'status': 'completed_with_research_gaps', 'offline_test_counts': counts,
    'new_entity_tests_per_mode': 6, 'new_indirect_tests_per_mode': 7,
    'total_tests_per_mode': 131,
    'mutation_runs': {'normal': 'expected failure, exit 1', 'optimized': 'expected failure, exit 1'},
    'reference_analysis_fingerprint': analysis['analysis_fingerprint'],
    'prior_evidence_replay_fingerprint': evidence['evidence_fingerprint'],
    'prior_evidence_comparison': comparison['status'],
    'settings_pinned_instructions': 44,
    'settings_normal_optimized_equal': True,
    'settings_evidence_sha256': hashlib.sha256(settings.read_bytes()).hexdigest(),
    'entity_and_indirect_fault_injection': 'both normal and optimized runs failed as expected',
    'earlier_attempts': [
        {'path': 'checks/', 'result': 'harness output decoding failed on UTF-8 child output with Windows GBK parent default',
         'resolution': 'explicit UTF-8 decoding; rerun logs in checks-v2/'},
        {'path': 'checks-v2/replay.log', 'exit_code': 2, 'result': 'old analysis graph correctly rejected as missing or malformed',
         'resolution': 'used the spec-pinned analysis-final; replay-final/ and compare-final/ passed; freshly replayed original 16-source bundle into reference-replay/ with matching fingerprint'},
    ],
    'not_executed': [
        'new candidate ownership/write refusal, object-reuse and restore tests: no field binding or runtime exists',
        'gameplay comparison, FPS and frame time measurement: no qualified candidate exists',
    ],
    'new_candidate_acceptance_passed': False, 'field_binding': None,
    'gameplay_verified': False, 'fps_measured': False, 'frametime_measured': False,
}
(root / 'verification-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
