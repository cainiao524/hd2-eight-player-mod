"""Check local report links and protected originals, then fingerprint delivery."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parent
for target in re.findall(r'\]\(([^)]+)\)', (root / 'HANDOFF.zh-TW.md').read_text(encoding='utf-8')):
    if '://' not in target and not (root / target).is_file():
        raise ValueError('missing report target: ' + target)
preservation = subprocess.run([sys.executable, str(root / 'baseline/audit_baseline.py'), '--verify-preserved'],
                             capture_output=True, text=True, encoding='utf-8')
if preservation.returncode != 0:
    raise ValueError(preservation.stdout + preservation.stderr)
files = []
for p in sorted(root.rglob('*')):
    if not p.is_file() or '__pycache__' in p.parts or p.name in ('delivery-manifest.json', 'SHA256SUMS.txt'):
        continue
    raw = p.read_bytes()
    files.append({'path': p.relative_to(root).as_posix(), 'size': len(raw),
                  'sha256': hashlib.sha256(raw).hexdigest()})
manifest = {
    'schema_version': 1, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'UNBOUND', 'field_binding': None, 'common_solution_found': False,
    'mod_zip_built': False, 'deployed': False, 'published': False,
    'gameplay_verified': False, 'fps_measured': False, 'frametime_measured': False,
    'protected_assets': {'files_checked': 40, 'unchanged': True,
                         'verification_output': preservation.stdout.strip()},
    'entry_point': 'HANDOFF.zh-TW.md', 'local_only': True,
    'files': files,
}
(root / 'delivery-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with (root / 'SHA256SUMS.txt').open('w', encoding='utf-8', newline='\n') as f:
    for row in files:
        f.write(row['sha256'] + '  ' + row['path'] + '\n')
    f.write(hashlib.sha256((root / 'delivery-manifest.json').read_bytes()).hexdigest() + '  delivery-manifest.json\n')
print(json.dumps({'files': len(files), 'protected_assets_unchanged': True,
                  'report_sha256': hashlib.sha256((root / 'HANDOFF.zh-TW.md').read_bytes()).hexdigest(),
                  'status': 'UNBOUND', 'mod_zip_built': False}))
