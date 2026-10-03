import json
from pathlib import Path
LOG=Path(__file__).with_name('live_capacity_patch_runtime_20261003.jsonl')
rows=[json.loads(x) for x in LOG.read_text(encoding='utf-8').splitlines() if x.strip()]
applied=[x for x in rows if x.get('event')=='applied']
refused=[x for x in rows if x.get('event')=='refused']
result={
 'schema':'hd2_capacity_patch_runtime_verification_v1',
 'build':25480438,
 'log':str(LOG.as_posix()),
 'events':len(rows),
 'loaded':any(x.get('event')=='loaded' for x in rows),
 'applied':len(applied)==1 and applied[0].get('patched')==35,
 'patched_count': applied[0].get('patched') if applied else 0,
 'refused':len(refused)>0,
 'session_observations':sum(x.get('event')=='session_observe' for x in rows),
 'rollback_event':any(x.get('event')=='unloaded' for x in rows),
 'read_only':False,
 'process_mutated':True,
 'capacity_layer_only':True,
 'player_admission_proven':False,
 'player_creation_proven':False,
 'installable':False,
 'multiplayer_verified':False
}
result['verification_passed']=result['loaded'] and result['applied'] and not result['refused'] and result['session_observations']>=1
Path(__file__).with_name('live_capacity_patch_runtime_verification_20261003.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
assert result['verification_passed']
