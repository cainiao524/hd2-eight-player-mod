"""Replay existing research and tests without writing to the source repository."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--repo', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
results = []

def run(name, command, expected=0):
    started = time.monotonic()
    proc = subprocess.run(command, cwd=args.repo, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (args.output / (name + '.log')).write_text(proc.stdout + proc.stderr, encoding='utf-8')
    item = {'name': name, 'command': command, 'exit_code': proc.returncode,
            'expected_exit_code': expected, 'passed': proc.returncode == expected,
            'elapsed_seconds': round(time.monotonic() - started, 3)}
    results.append(item)
    print(json.dumps(item, ensure_ascii=False), flush=True)

for optimized in (False, True):
    prefix = [sys.executable] + (['-O'] if optimized else [])
    tag = 'optimized' if optimized else 'normal'
    for pattern in ('test_generation*.py', 'test_reference*.py', 'test_secondary_catalog.py', 'test_projectile_verifier.py'):
        run(tag + '-' + pattern.replace('*', 'all'), prefix + ['-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'])
    # Mutation is confined to this child process. Disabling the exact-source
    # check must make its existing regression test FAIL, including under -O.
    mutation = '''import sys, unittest
sys.path[:0] = ['tests', 'tools']
import test_generation_research as tests
original = tests.study.require
def broken_require(condition, message):
    if message == 'existing code evidence file fingerprint mismatch':
        return
    return original(condition, message)
tests.study.require = broken_require
suite = unittest.TestSuite([tests.GenerationResearchTests('test_modified_code_file_is_rejected_by_exact_source_pin')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
'''
    run(tag + '-disabled-source-guard-mutation', prefix + ['-c', mutation], expected=1)

run('replay', [sys.executable, 'tools/generation_research.py', 'analyze',
              '--analysis', 'build/generation-research-v1-analysis-final/analysis.json',
              '--code-evidence-dir', 'build/existing-code-evidence-25480438',
              '--output', str(args.output / 'replay')])
if results[-1]['passed']:
    run('compare', [sys.executable, 'tools/generation_research.py', 'compare',
                   '--baseline', 'build/generation-research-v1-findings-continuation-v3/generation-evidence.json',
                   '--candidate', str(args.output / 'replay/generation-evidence.json'),
                   '--output', str(args.output / 'compare')])
summary = {'schema_version': 1, 'checks': results,
           'all_expected_results': all(item['passed'] for item in results),
           'scope': 'Offline evidence and classification only; no new runtime or lifecycle binding exists.',
           'gameplay_verified': False, 'fps_measured': False, 'frametime_measured': False}
(args.output / 'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sys.exit(0 if summary['all_expected_results'] else 1)
