import json
from pathlib import Path
base=Path(__file__).parent
m=json.loads((base/'capacity_patch_manifest_20261003.json').read_text(encoding='utf-8'))
assert m['build']==25480438
assert len(m['sites'])==32
for site in m['sites']:
    old=bytes.fromhex(site['old']); new=bytes.fromhex(site['new'])
    assert len(old)==len(new)
    assert old!=new and new.count(8)>=1
assert m['transaction']['preflight_all_sites']
assert m['transaction']['rollback_on_failure']
assert m['installable'] is False and m['multiplayer_verified'] is False
r=json.loads((base.parents[2]/'five_player_feasibility_20260927/live_capacity_patch_runtime_verification_20261003.json').read_text(encoding='utf-8'))
assert r['verification_passed'] and r['patched_count']==32 and r['session_observations']>=1
assert r['player_admission_proven'] is False and r['player_creation_proven'] is False
print('capacity_patch_manifest_and_runtime_receipt_passed')
