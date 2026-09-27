"""Compose offline producer/receiver code for one shared roster property store.

This is a byte artifact builder, not a loader, allocator or game integration.
It adds cross-component known-range checks to the individual emitters.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def _load(name: str):
    path = Path(__file__).with_name(name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


producer = _load('roster_producer')
receiver = _load('roster_receiver')


def build(producer_source: bytes, receiver_source: bytes, *, game_base: int,
          roster_address: int, property_address: int,
          producer_code_address: int, receiver_code_address: int,
          producer_reject_address: int, receiver_reject_address: int) -> dict:
    """Emit both routines with exactly the same object and storage binding.

    Distinct rejection entrypoints are required because the two interior frames
    have different layouts, even though they use the same rejection reason IDs.
    A one-byte rejection region does not prove the whole handler is disjoint.
    """
    shared = dict(game_base=game_base, roster_address=roster_address,
                  property_address=property_address)
    p = producer.build(producer_source, **shared, code_address=producer_code_address,
                       reject_address=producer_reject_address)
    r = receiver.build(receiver_source, **shared, code_address=receiver_code_address,
                       reject_address=receiver_reject_address)
    producer.require(p['target_profile'] == r['target_profile'], 'producer/receiver profile mismatch')
    regions = [
        ('producer code',producer_code_address,p['size_bytes']),
        ('receiver code',receiver_code_address,r['size_bytes']),
        ('producer rejection entry',producer_reject_address,1),
        ('receiver rejection entry',receiver_reject_address,1),
        ('roster',roster_address,0x428),
        ('property storage',property_address,0x100),
        ('original producer',game_base+producer.ENTRY_RVA,len(producer_source)),
        ('original receiver',game_base+receiver.ENTRY_RVA,len(receiver_source)),
        ('sentinel',game_base+producer.SENTINEL_RVA,4),
        ('roster global',game_base+producer.ROSTER_GLOBAL_RVA,8),
        ('index helper global',game_base+0x347CEF0,8),
        ('allocator entry',game_base+producer.ALLOCATOR_RVA,1),
        ('index helper',game_base+producer.INDEX_HELPER_RVA,0x5C),
    ]
    for i,(name,a,n) in enumerate(regions):
        for other,b,m in regions[i+1:]:
            producer.require(not producer.overlaps(a,n,b,m),
                             'pair known region overlap: '+name+' / '+other)
    return {
        'status':'offline_native_pair_candidate', 'installable':False,
        'game_execution':False, 'multiplayer_verified':False,
        'target_profile':p['target_profile'], 'shared_binding':shared,
        'property_size_bytes':0x100, 'record_capacity':8, 'record_stride':0x20,
        'producer':p, 'receiver':r,
        'known_regions':[{'name':name,'address':a,'size_bytes':n} for name,a,n in regions],
        'required_integration':[
            'Both routines are only a subset; redirect remaining roster initialization, move/remove, classification and readers',
            'Provide distinct verified rejection continuations for the two different interior frames and abort the enclosing operation',
            'Establish allocation origin, full code/handler/storage extents, permissions, binding incarnation, lifetime and engine synchronization',
            'Validate runtime image and all helper contracts; implement Windows unwind and reversible hook installation',
            'Verify original four-player behavior and fifth-through-eighth-player mission lifecycle',
        ],
        'limits':[
            'Known finite ranges only, not a whole-process allocation or full-image non-overlap check',
            'Index-helper global range is protected but its live pointer, target owner and peer records are not inspected',
            'No allocation, copying of existing records, initialization, hooks, rejection handlers or executable memory operations',
            'No serialization, transport, real peer joining, game execution or multiplayer acceptance',
        ],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer-evidence',type=Path,required=True)
    parser.add_argument('--receiver-evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    for name in ('game-base','roster-address','property-address','producer-code-address',
                 'receiver-code-address','producer-reject-address','receiver-reject-address'):
        parser.add_argument('--'+name,type=lambda s:int(s,0),required=True)
    args=vars(parser.parse_args())
    out=args.pop('output')
    producer.require(not out.exists(),'refusing to overwrite output')
    ps=producer.load_source(args.pop('producer_evidence'))
    rs=receiver.load_source(args.pop('receiver_evidence'))
    result=build(ps,rs,**args)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'status':result['status'],
                      'producer_bytes':result['producer']['size_bytes'],
                      'receiver_bytes':result['receiver']['size_bytes']}))


if __name__=='__main__':
    main()
