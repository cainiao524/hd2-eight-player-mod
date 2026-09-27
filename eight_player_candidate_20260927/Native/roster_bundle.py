"""Build offline producer, receiver and full-array mover against one sidecar.

Emits byte artifacts only. No allocation, initialization, memory migration,
process access, hooks or host-native execution are performed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load(name):
    path=Path(__file__).with_name(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


move=_load('roster_move')
pair=_load('roster_property_pair')


def build(move_source: bytes, producer_source: bytes, receiver_source: bytes, *,
          game_base: int, roster_address: int, storage_address: int,
          move_code_address: int, producer_code_address: int, receiver_code_address: int,
          move_reject_address: int, producer_reject_address: int, receiver_reject_address: int) -> dict:
    mover=move.build(move_source,game_base=game_base,roster_address=roster_address,
                     storage_address=storage_address,code_address=move_code_address,
                     reject_address=move_reject_address)
    properties=pair.build(producer_source,receiver_source,game_base=game_base,
                          roster_address=roster_address,property_address=storage_address+0x580,
                          producer_code_address=producer_code_address,receiver_code_address=receiver_code_address,
                          producer_reject_address=producer_reject_address,receiver_reject_address=receiver_reject_address)
    move.require(mover['target_profile']==properties['target_profile'],'bundle target profile mismatch')
    move.require(mover['property_address']==storage_address+0x580,'mover property layout mismatch')
    regions=[r for r in properties['known_regions'] if r['name']!='property storage']
    regions += [
        {'name':'all four sidecar arrays','address':storage_address,'size_bytes':0x680},
        {'name':'move code','address':move_code_address,'size_bytes':mover['size_bytes']},
        {'name':'move rejection entry','address':move_reject_address,'size_bytes':1},
        {'name':'original move','address':game_base+0x60C410,'size_bytes':430},
    ]
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            move.require(not move.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                         'bundle known region overlap: '+a['name']+' / '+b['name'])
    return {
        'status':'offline_native_roster_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
        'target_profile':properties['target_profile'],
        'shared_binding':{'game_base':game_base,'roster_address':roster_address,'storage_address':storage_address},
        'storage_size_bytes':0x680,'record_capacity':8,
        'layout':{'entity_pointers':{'offset':0,'stride':8,'size_bytes':0x40},
                  'primary':{'offset':0x40,'stride':0x70,'size_bytes':0x380},
                  'auxiliary':{'offset':0x3C0,'stride':0x38,'size_bytes':0x1C0},
                  'properties':{'offset':0x580,'stride':0x20,'size_bytes':0x100}},
        'move':mover,'property_pair':properties,'known_regions':regions,
        'required_integration':[
            'Redirect remaining insertion, compaction, classification, removal and readers to the same four arrays',
            'Establish sidecar allocation, opaque-record migration, native-equivalent initialization, publication and lifetime',
            'Validate original map, valid source entity and destination hole/caller state before nontrivial movement',
            'Maintain engine synchronization and original resource ownership; the mover is not a full remove/compact transaction',
            'Implement each rejection ABI, Windows unwind, runtime version checks and reversible installation',
            'Verify four-player baseline and fifth-through-eighth-player mission lifecycle',
        ],
        'limits':[
            'Whole680h sidecar checked against finite known regions only; not an actual allocation or full-image proof',
            'Original source records remain after move and enclosing counts are not updated by the mover',
            'Original map failure behavior is preserved; ordinal/binding guards do not establish valid map semantics',
            'No assumption that zero-filled new memory is a valid native roster',
            'No real game execution, native memory migration or multiplayer verification',
        ],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for role in ('move','producer','receiver'):
        parser.add_argument('--'+role+'-evidence',required=True,type=Path)
        parser.add_argument('--'+role+'-code-address',required=True,type=lambda s:int(s,0))
        parser.add_argument('--'+role+'-reject-address',required=True,type=lambda s:int(s,0))
    for name in ('game-base','roster-address','storage-address'):
        parser.add_argument('--'+name,required=True,type=lambda s:int(s,0))
    parser.add_argument('--output',required=True,type=Path)
    args=vars(parser.parse_args());out=args.pop('output')
    move.require(not out.exists(),'refusing to overwrite output')
    ms=move.load_source(args.pop('move_evidence'))
    ps=pair.producer.load_source(args.pop('producer_evidence'))
    rs=pair.receiver.load_source(args.pop('receiver_evidence'))
    result=build(ms,ps,rs,**args)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'status':result['status'],
                      'move_bytes':result['move']['size_bytes'],'storage_bytes':result['storage_size_bytes']}))


if __name__=='__main__':main()
