"""Emit fixed-build offline registry update and associated-ID roster reader.

The complete B54E00 and 606520 bodies share the existing eight-slot sidecar.
Only the roster branches acquire new guards; other registry tags retain their
original code and calls. This generator neither installs nor executes code.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

_spec=importlib.util.spec_from_file_location('roster_departure',Path(__file__).with_name('roster_departure.py'))
departure=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(departure)
remove=departure.remove;move=departure.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
_Code=remove._Code
TARGET_PROFILE=dict(move.TARGET_PROFILE)
IMAGE_SIZE=74727424
GLOBAL_RVA=0x3326468
sha=lambda b:hashlib.sha256(b).hexdigest()
EVIDENCE_SHA256='7a8f289ea8ddf85d1b2010a39d9cedc4599e9846db8936b9e215cbd4a96740e1'
SPECS={'0x606520': {'end': 6317615,
              'entry': 6317344,
              'lengths': (5,
                          5,
                          5,
                          5,
                          1,
                          2,
                          2,
                          2,
                          2,
                          7,
                          2,
                          3,
                          3,
                          6,
                          7,
                          7,
                          3,
                          7,
                          6,
                          7,
                          2,
                          7,
                          4,
                          4,
                          3,
                          2,
                          7,
                          6,
                          6,
                          3,
                          4,
                          3,
                          4,
                          3,
                          2,
                          2,
                          3,
                          2,
                          2,
                          3,
                          2,
                          2,
                          3,
                          2,
                          3,
                          4,
                          7,
                          4,
                          2,
                          7,
                          3,
                          2,
                          2,
                          4,
                          3,
                          6,
                          6,
                          5,
                          5,
                          5,
                          4,
                          3,
                          2,
                          2,
                          2,
                          2,
                          1,
                          1,
                          5,
                          8,
                          3,
                          2),
              'relocations': {6317394: (3, 54968216, 'rip_memory'),
                              6317532: (3, 55068012, 'rip_address'),
                              6317559: (2, 55065652, 'rip_memory')},
              'sha256': 'ca355caa6f6c7309202c504fadbfaae2c93fff84f5c846bf8be60d839631c39e'},
 '0xb54e00': {'end': 11882857,
              'entry': 11881984,
              'lengths': (2,
                          2,
                          2,
                          4,
                          7,
                          3,
                          2,
                          5,
                          7,
                          6,
                          5,
                          5,
                          5,
                          5,
                          5,
                          3,
                          3,
                          8,
                          3,
                          6,
                          3,
                          6,
                          3,
                          6,
                          5,
                          6,
                          8,
                          2,
                          5,
                          2,
                          5,
                          2,
                          2,
                          2,
                          7,
                          4,
                          7,
                          4,
                          3,
                          3,
                          2,
                          2,
                          7,
                          2,
                          3,
                          2,
                          1,
                          3,
                          7,
                          4,
                          2,
                          2,
                          3,
                          2,
                          6,
                          5,
                          7,
                          7,
                          4,
                          5,
                          5,
                          6,
                          5,
                          8,
                          8,
                          7,
                          3,
                          5,
                          8,
                          7,
                          6,
                          7,
                          2,
                          7,
                          4,
                          4,
                          3,
                          6,
                          7,
                          6,
                          5,
                          2,
                          4,
                          3,
                          4,
                          2,
                          2,
                          3,
                          2,
                          2,
                          3,
                          2,
                          5,
                          3,
                          6,
                          5,
                          3,
                          6,
                          6,
                          5,
                          4,
                          4,
                          3,
                          5,
                          3,
                          2,
                          6,
                          2,
                          5,
                          5,
                          3,
                          8,
                          5,
                          5,
                          6,
                          4,
                          4,
                          5,
                          8,
                          2,
                          7,
                          2,
                          6,
                          7,
                          4,
                          9,
                          2,
                          8,
                          5,
                          7,
                          2,
                          2,
                          4,
                          2,
                          2,
                          5,
                          8,
                          7,
                          3,
                          3,
                          6,
                          2,
                          7,
                          2,
                          7,
                          3,
                          4,
                          3,
                          2,
                          7,
                          7,
                          2,
                          3,
                          4,
                          3,
                          4,
                          2,
                          2,
                          2,
                          2,
                          2,
                          3,
                          2,
                          5,
                          5,
                          2,
                          4,
                          9,
                          2,
                          12,
                          3,
                          2,
                          8,
                          4,
                          2,
                          4,
                          9,
                          2,
                          2,
                          2,
                          5,
                          5,
                          2,
                          5,
                          5,
                          2,
                          8,
                          2,
                          5,
                          3,
                          5,
                          7,
                          6,
                          5,
                          5,
                          5,
                          5,
                          5,
                          4,
                          2,
                          2,
                          1,
                          1),
              'relocations': {11881994: (3, 53636712, 'rip_memory'),
                              11882111: (1, 16620272, 'call_rel32'),
                              11882129: (3, 53633800, 'rip_memory'),
                              11882210: (3, 53633864, 'rip_memory'),
                              11882265: (3, 53634152, 'rip_memory'),
                              11882275: (1, 6317344, 'call_rel32'),
                              11882288: (3, 55065652, 'rip_memory'),
                              11882431: (1, 24320608, 'call_rel32'),
                              11882470: (1, 24320608, 'call_rel32'),
                              11882554: (1, 16620448, 'call_rel32'),
                              11882591: (3, 53634152, 'rip_memory'),
                              11882604: (2, 55065632, 'rip_memory'),
                              11882796: (1, 8083296, 'call_rel32')},
              'sha256': '8f679d31841a3cce6ee1f4d66ec47bc89aa9a347b68939bc4264ec25bf8bd783'}}
REASONS={1:'roster_argument_or_registry_binding_mismatch',2:'global_roster_binding_mismatch',
         3:'tracked_count_above_8',4:'prefix_dense_tracked_order_invalid',
         5:'null_matched_entity_pointer',6:'entity_id_is_empty_map_key',
         7:'map_ordinal_outside_tracked_range',8:'map_capacity_not_8',
         9:'map_ordinal_disagrees_with_property_ordinal'}
ARRAYS={0xB5501C:('rdi',0x580),0xB55057:('base',-0xE8),
        0xB550E9:('base',-0xE8),0xB550CD:('index',0xF8),
        0xB550D8:('index',0xF8),0xB550FB:('index',0x1D8),
        0x606559:('r14',0x580),0x606622:('base',-0xE8)}
LIMITS=[
 'Offline candidate only: no allocation, initialization/migration, publication, hook, reject handler, unwind registration, game execution or multiplayer proof',
 'Bound S, sidecar, entity pointers, registry and maps require valid storage and serialized lifetime throughout each call; guards neither provide nor prove synchronization',
 'Tag69 checks registry/global S identity before its search; tag73 checks its loaded global S before calling the relocated helper; other tags have no roster guard',
 'Tag69 requires an eight-bucket map only after a property match and rejects an empty entity key, missing/out-of-range ordinal or ordinal inconsistent with the matched property record',
 'The registry can have processed earlier entries before a later rejection; prior callbacks and external effects are not rolled back',
 '606520 and FD9BA0 retain the original context-map algorithm; zero capacity or a full-table missing lookup can dereference null, and a key equal to its empty sentinel can produce a false hit. Valid context/backing, key domain, found ordinal and resource lifetimes remain external contracts',
 '606520 returns an entity ID and scans D records; it is not the network-index getter and pending records above D remain unsearched',
 'FD9BA0 treats associated ID 7FFF via the context default while 606520 skips that record; these different original semantics are preserved',
 'Tag115 and tag73 external callbacks, map/resource results and tag73 opaque stack bytes retain their original contracts; synthetic stubs cannot establish real resource behavior',
 'Standalone helper rejects at its original entry stack. Root prechecks the same binding/counts immediately before calling it; a root caller must keep that state stable, and no general nested-call unwinder is implemented',
]


def load_sources(path:Path)->dict[str,bytes]:
    raw=Path(path).read_bytes();require(sha(raw)==EVIDENCE_SHA256,'registry evidence fingerprint mismatch')
    evidence=json.loads(raw);result={}
    for key,spec in SPECS.items():
        blob=bytes.fromhex(evidence['bodies'][key]['bytes_hex'])
        require(len(blob)==spec['end']-spec['entry'] and sha(blob)==spec['sha256'],'registry body fingerprint mismatch')
        result[key]=blob
    return result


def _binding_guard(c,*,source_register,global_check,game_base,roster_address):
    # R10/R11 are dead scratch at each insertion; arguments and nonvolatiles stay intact.
    c.emit(b'\x49\xba'+struct.pack('<Q',roster_address))
    c.emit(bytes.fromhex('4d3bf2' if source_register=='r14' else '493bca'))
    c.branch(b'\x0f\x85','reject1')
    if global_check:
        c.emit(b'\x49\xbb'+struct.pack('<Q',game_base+GLOBAL_RVA))
        c.emit(bytes.fromhex('4d3913'));c.branch(b'\x0f\x85','reject2')
    c.emit(bytes.fromhex('458b9a800000004183fb08'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('45399a84000000'));c.branch(b'\x0f\x87','reject4')
    c.emit(bytes.fromhex('458b9a8400000045399a88000000'));c.branch(b'\x0f\x87','reject4')


def _emit(source,key,*,game_base,code_address,helper_code_address,roster_address,storage_address,reject_address):
    spec=SPECS[key];start=spec['entry'];root=key=='0xb54e00'
    require(type(source)is bytes and len(source)==spec['end']-start and sha(source)==spec['sha256'],
            'registry source fingerprint mismatch: '+key)
    c=_Code(code_address);mapping={};relocs=[];patches=[];guards=[]
    if not root:
        guards.append({'at':'entry','address':c.base,'kind':'argument_binding_and_counts'})
        _binding_guard(c,source_register='rcx',global_check=False,game_base=game_base,roster_address=roster_address)
    body_address=c.base+len(c.data);offset=0
    for size in spec['lengths']:
        old=start+offset;raw=source[offset:offset+size];offset+=size
        c.label(hex(old));mapping[old]=c.base+len(c.data)
        if old in (0xB5500B,0xB54F23):
            guards.append({'at':hex(old),'address':c.base+len(c.data),'kind':'binding_and_counts'})
            _binding_guard(c,source_register='r14' if old==0xB5500B else 'rcx',global_check=True,
                           game_base=game_base,roster_address=roster_address)
        elif old==0xB55069:
            guards.append({'at':hex(old),'address':c.base+len(c.data),'kind':'matched_pointer_nonnull'})
            c.emit(bytes.fromhex('4885c0'));c.branch(b'\x0f\x84','reject5')
        elif old==0xB5506C:
            guards.append({'at':hex(old),'address':c.base+len(c.data),'kind':'map_capacity_and_key'})
            c.emit(bytes.fromhex('4183bbd800000008'));c.branch(b'\x0f\x85','reject8')
            c.emit(bytes.fromhex('413b83dc000000'));c.branch(b'\x0f\x84','reject6')
        elif old==0xB550C7:
            guards.append({'at':hex(old),'address':c.base+len(c.data),'kind':'map_ordinal_valid_and_matches_property'})
            c.emit(bytes.fromhex('83f808'));c.branch(b'\x0f\x83','reject7')
            c.emit(bytes.fromhex('413b8680000000'));c.branch(b'\x0f\x83','reject7')
            c.emit(bytes.fromhex('3bc6'));c.branch(b'\x0f\x85','reject9')
        address=c.base+len(c.data)
        if old in ARRAYS:
            mode,bias=ARRAYS[old]
            if mode in ('rdi','r14'):
                blob=(b'\x48\xbf' if mode=='rdi' else b'\x49\xbe')+struct.pack('<Q',storage_address+bias)
            else:
                out=bytearray(raw)
                # Replace only the S operand in the SIB with R10, retaining index/stride/displacement.
                if mode=='base':out[0]|=1;out[3]=(out[3]&0xf8)|2
                else:out[0]|=2;out[3]=(out[3]&0xc7)|0x10
                blob=b'\x49\xba'+struct.pack('<Q',storage_address+bias)+bytes(out)
            c.emit(blob);patches.append({'original_rva':old,'emitted_address':address,
                                        'original_hex':raw.hex(),'replacement_hex':blob.hex(),'storage_bias':bias})
        elif old in spec['relocations']:
            at,target,kind=spec['relocations'][old]
            require(old+size+struct.unpack_from('<i',raw,at)[0]==target,'source relocation mismatch')
            dest=helper_code_address if old==0xB54F23 else game_base+target
            blob=bytearray(raw);blob[at:at+4]=rel32(address+size,dest);c.emit(blob)
            relocs.append({'original_rva':old,'emitted_address':address,'kind':kind,
                           'original_target_rva':target,'target_address':dest,'helper_callsite_replaced':old==0xB54F23})
        elif len(raw)==2 and 0x70<=raw[0]<=0x7f:
            target=old+2+int.from_bytes(raw[1:],'little',signed=True)
            c.branch(bytes([0x0f,raw[0]+0x10]),hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif len(raw)==6 and raw[0]==0x0f and 0x80<=raw[1]<=0x8f:
            target=old+6+int.from_bytes(raw[2:],'little',signed=True);c.branch(raw[:2],hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif (len(raw)==2 and raw[0]==0xeb) or (len(raw)==5 and raw[0]==0xe9):
            target=old+size+int.from_bytes(raw[1:],'little',signed=True);c.branch(b'\xe9',hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        else:c.emit(raw)
    require(offset==len(source) and len(patches)==(6 if root else 2),'incomplete registry emission')
    # All root rejection points are inside the nonempty-registry frame after every NV save.
    restore=source[0xB55146-start:0xB55168-start] if root else b''
    for reason in (REASONS if root else (1,3,4)):
        c.label('reject'+str(reason))
        if root:c.emit(bytes.fromhex('8bcb')+restore) # original ECX input ID, then original epilogue without RET
        c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9',reject_address)
    for row in relocs:
        if row['kind']=='local_branch':
            require(row['original_target_rva'] in mapping,'branch not on instruction boundary')
            row['target_address']=mapping[row['original_target_rva']]
    code=c.finish();pointer(code_address,len(code),16,'complete '+key+' code')
    return {'original_entry_rva':start,'code_address':code_address,'entry_address':code_address,'body_address':body_address,
            'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),'source_sha256':sha(source),
            'array_patches':patches,'patches':patches,'relocations':relocs,'guards':guards,
            'mapping':{hex(k):v for k,v in mapping.items()},'instruction_address_map':{hex(k):v for k,v in mapping.items()},
            'reject_address':reject_address,'reject_reasons':{str(k):REASONS[k] for k in (REASONS if root else (1,3,4))},
            'reject_state':{'rsp':'original function entry RSP; all nonvolatile registers preserved',
                            'arguments':'ECX=original input ID; other volatile registers unspecified' if root else 'RCX/RDX/R8 preserved; no stack or output writes',
                            'reason':'R10D; flags/R11 unspecified',
                            'effects':'earlier registry entries may already have external effects; current tag69 has no roster writes before its guards pass' if root else 'no nonstack writes or calls before rejection'},
            'entry_or_callsite_patch':None}


def build(sources:dict[str,bytes],*,game_base:int,code_address:int,helper_code_address:int,
          roster_address:int,storage_address:int,reject_address:int,helper_reject_address:int)->dict:
    pointer(game_base,IMAGE_SIZE,0x1000,'game_base');pointer(roster_address,0x428,8,'roster_address')
    pointer(storage_address,0x680,16,'storage_address');require(storage_address>=0x100E8,'invalid biased storage')
    for name,value in [('code',code_address),('helper',helper_code_address)]:pointer(value,1,16,name)
    for name,value in [('reject',reject_address),('helper reject',helper_reject_address)]:pointer(value,1,1,name)
    functions={}
    for key,address,reject in [('0xb54e00',code_address,reject_address),('0x606520',helper_code_address,helper_reject_address)]:
        functions[key]=_emit(sources[key],key,game_base=game_base,code_address=address,helper_code_address=helper_code_address,
                             roster_address=roster_address,storage_address=storage_address,reject_address=reject)
    regions=[{'name':'registry '+key,'address':f['code_address'],'size_bytes':f['size_bytes']} for key,f in functions.items()]
    regions.extend([{'name':name,'address':address,'size_bytes':size} for name,address,size in [
        ('registry reject',reject_address,1),('association reader reject',helper_reject_address,1),
        ('original roster',roster_address,0x428),('four-array sidecar',storage_address,0x680),('game image',game_base,IMAGE_SIZE)]])
    _check_regions(regions)
    return {'status':'offline_native_roster_registry_update_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'evidence_sha256':EVIDENCE_SHA256,
            'shared_binding':{'game_base':game_base,'roster_address':roster_address,'storage_address':storage_address},
            'functions':functions,'known_regions':regions,'limits':list(LIMITS)}


def _check_regions(regions):
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                    'registry known-region overlap: '+a['name']+' / '+b['name'])


def build_bundle(sources:dict[str,bytes],*departure_sources,registry_code_address:int,
                 registry_helper_code_address:int,registry_reject_address:int,
                 registry_helper_reject_address:int,**departure_params)->dict:
    base=departure.build_bundle(*departure_sources,**departure_params);shared=base['shared_binding']
    registry=build(sources,**shared,code_address=registry_code_address,helper_code_address=registry_helper_code_address,
                   reject_address=registry_reject_address,helper_reject_address=registry_helper_reject_address)
    regions=list(base['known_regions'])
    for key,f in registry['functions'].items():
        regions.extend([{'name':'registry '+key,'address':f['code_address'],'size_bytes':f['size_bytes']},
                        {'name':'registry reject '+key,'address':f['reject_address'],'size_bytes':1},
                        {'name':'original registry '+key,'address':shared['game_base']+SPECS[key]['entry'],
                         'size_bytes':SPECS[key]['end']-SPECS[key]['entry']}])
    _check_regions(regions)
    return {'status':'offline_native_roster_registry_update_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'registry_update':registry,
            'known_regions':regions,'limits':base['limits']+registry['limits']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','departure-evidence','getter-evidence','classify-evidence','remove-evidence','insert-evidence','move-evidence',
                 'producer-evidence','receiver-evidence','player-count-evidence','context-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    g=departure.getter;counts=departure.player_count.load_sources(args.player_count_evidence,args.context_evidence)
    result=build_bundle(load_sources(args.evidence),departure.load_source(args.departure_evidence),g.load_source(args.getter_evidence),
                        g.classify.load_sources(args.classify_evidence),remove.load_sources(args.remove_evidence),
                        remove.insert.load_sources(args.insert_evidence),move.load_source(args.move_evidence),
                        remove.insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        remove.insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),
                        player_count_context_source=counts['context'],player_count_filter_source=counts['filter'],
                        **json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'functions':15,'known_regions':len(result['known_regions'])}))


if __name__=='__main__':main()
