from __future__ import annotations
import hashlib, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / 'five_player_feasibility_20260927' / 'PUBLIC_RUNTIME_BRIDGE_CCHUSKY_RECEIPT_20261002.json'


def main() -> int:
    rec = json.loads(RECEIPT.read_text(encoding='utf-8'))
    source_root = ROOT / rec['repository']['source_root']
    assert subprocess.check_output(['git','-C',str(source_root),'rev-parse','HEAD'], text=True).strip() == rec['repository']['commit']
    for f in rec['files']:
        p = source_root / f['path']
        b = p.read_bytes()
        assert len(b) == f['bytes'], f['path']
        assert hashlib.sha256(b).hexdigest() == f['sha256'], f['path']
    hook = (source_root / 'hook' / 'hd2_raycast_hook.c').read_text(encoding='utf-8', errors='replace')
    watcher = (source_root / 'hook' / 'watcher.c').read_text(encoding='utf-8', errors='replace')
    injector = (source_root / 'hook' / 'dll_injector.c').read_text(encoding='utf-8', errors='replace')
    assert 'install_hook(&tramp, hk_lua_pcall' in hook
    assert 'World.units' in hook and 'World.entities' in hook
    for token in ['confirmed-peer','confirmed_peer','spawn_entity','player_manager','remove_player','package unload']:
        assert token.lower() not in hook.lower(), token
    for token in ['OpenProcess','VirtualAllocEx','WriteProcessMemory','CreateRemoteThread']:
        assert token in watcher or token in injector, token
    d = rec['decision']
    assert d['confirmed_peer_bridge_found'] is False
    assert d['player_creation_bridge_found'] is False
    assert d['cleanup_bridge_found'] is False
    assert d['installable'] is False and d['multiplayer_verified'] is False
    print('cchusky_runtime_bridge_audit_passed')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
