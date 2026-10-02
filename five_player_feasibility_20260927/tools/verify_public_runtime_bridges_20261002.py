from __future__ import annotations
import hashlib, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_RECEIPT = ROOT / 'five_player_feasibility_20260927' / 'PUBLIC_RUNTIME_BRIDGE_RECEIPT_20261002.json'
CCHUSKY_RECEIPT = ROOT / 'five_player_feasibility_20260927' / 'PUBLIC_RUNTIME_BRIDGE_CCHUSKY_RECEIPT_20261002.json'

def verify_receipt(path: Path):
    rec=json.loads(path.read_text(encoding='utf-8'))
    if 'repository' in rec:
        repos=[rec['repository']]
        file_groups=[(rec.get('files',[]), repos[0])]
    else:
        repos=rec.get('repositories',[])
        file_groups=[]
        for entry in repos:
            file_groups.append((entry.get('key_files',[]),entry))
    for files,entry in file_groups:
        source_root=entry.get('source_root')
        if not source_root:
            name=entry.get('name','').split('/')[-1]
            source_root='public_research_20261002/_clones/'+name
        repo=ROOT/source_root
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        assert commit == entry['commit'], f'{path.name}: commit drift {entry.get("name",entry.get("source_root"))}'
        for item in files:
            rel=item.get('path'); p=repo/rel; b=p.read_bytes()
            assert len(b)==item['bytes'], f'{path.name}: bytes {rel}'
            assert hashlib.sha256(b).hexdigest()==item['sha256'], f'{path.name}: hash {rel}'
    return rec

def main():
    a=verify_receipt(BRIDGE_RECEIPT)
    c=verify_receipt(CCHUSKY_RECEIPT)
    # The public bridge report must remain a negative result until native contracts exist.
    assert a['decision']['executable_bridge_found'] is False
    assert a['decision']['native_plan_remains'].startswith('executable=false')
    assert c['decision']['confirmed_peer_bridge_found'] is False
    assert c['decision']['player_creation_bridge_found'] is False
    assert c['decision']['cleanup_bridge_found'] is False
    assert c['build_check']['source_build_script'] == 'hook/build_clean.bat'
    assert c['build_check']['compiled_in_this_audit'] is False
    # Re-check exact current-build claims in source rather than trusting prose alone.
    hd2=ROOT/'public_research_20261002/_clones/HD2Runtime'
    natives=(hd2/'domains/event_natives.lua').read_text(encoding='utf-8',errors='replace')
    world=(hd2/'runtime/event_world.lua').read_text(encoding='utf-8',errors='replace')
    api=(hd2/'api/hd2.lua').read_text(encoding='utf-8',errors='replace')
    assert 'maxPlayers"]=4' in natives and 'gameDllSha256' in natives
    assert 'count>P.maxPlayers' in world
    assert 'READ_ONLY_MILESTONE' in api
    lobby=ROOT/'public_research_20261002/_clones/BetterLobbyManagement/src/game.lua'
    lobby_text=lobby.read_text(encoding='utf-8',errors='replace')
    assert 'G.MAX_PEERS = 4' in lobby_text and '0x347ced8' in lobby_text and '0x16390' in lobby_text
    print('public_runtime_bridge_audit_passed: hd2runtime=4-slot-read-only-boundary; betterlobby=4-slot-reader; cchusky=observer-only; bridge=false')

if __name__ == '__main__':
    main()
