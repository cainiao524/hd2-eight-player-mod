"""Emit offline source-faithful roster classification into shared eight-slot storage.

Enter clears primary[old P] and leaves primary[target] in place; it is NOT a
four-record swap. Temporary arena helpers must succeed without interleaving.
No process access, hooks, installation or host-native execution.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

_spec=importlib.util.spec_from_file_location('roster_remove',Path(__file__).with_name('roster_remove.py'))
remove=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(remove)
move=remove.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
_Code=remove._Code
TARGET_PROFILE=dict(move.TARGET_PROFILE)
GLOBAL_RVA,SENTINEL_RVA=0x3326468,0x3483C20
EVIDENCE_SHA256='f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33'
sha=lambda b:hashlib.sha256(b).hexdigest()
# Fixed, capture-derived instruction boundaries and array displacement sites.
SPECS={'enter': {'entry': 6344528,
           'end': 6345462,
           'sha256': '09e5e20c35955b4f563f1e971646a8c32c67ff6afdc76e4c1aa796270a6ff33c',
           'lengths': (5, 5, 5, 1, 2, 2, 4, 3, 6, 7, 2, 7, 2, 7, 4, 4, 3, 2, 7, 6, 4, 8, 2, 4, 3, 4, 4, 2, 2,
                       2, 2, 2, 3, 2, 5, 7, 3, 3, 3, 2, 4, 6, 4, 8, 8, 8, 8, 8, 8, 8, 5, 2, 2, 4, 2, 8, 5, 8,
                       8, 8, 3, 8, 8, 5, 4, 8, 8, 8, 8, 8, 8, 8, 5, 5, 5, 4, 5, 4, 7, 3, 4, 3, 3, 4, 4, 4, 4,
                       5, 5, 8, 3, 8, 4, 8, 4, 9, 5, 3, 8, 4, 8, 4, 8, 5, 9, 5, 5, 5, 5, 5, 5, 5, 5, 4, 5, 4,
                       5, 4, 8, 3, 8, 4, 9, 8, 9, 8, 3, 9, 4, 9, 5, 5, 5, 8, 6, 3, 7, 2, 3, 4, 3, 2, 7, 7, 4,
                       8, 3, 3, 3, 4, 4, 3, 2, 2, 2, 2, 3, 2, 3, 4, 2, 8, 7, 7, 5, 4, 4, 4, 3, 2, 7, 6, 4, 9,
                       2, 4, 3, 3, 4, 2, 2, 3, 2, 2, 3, 2, 3, 4, 6, 5, 5, 5, 4, 2, 2, 1, 1),
           'array_sites': {6344693: (4, 32),
                           6344701: (4, 32),
                           6344709: (4, 32),
                           6344717: (4, 32),
                           6344725: (4, 32),
                           6344733: (4, 32),
                           6344741: (4, 32),
                           6344777: (4, 0),
                           6344793: (4, 0),
                           6344804: (4, 0),
                           6344812: (4, 0),
                           6344829: (4, 32),
                           6344837: (4, 32),
                           6344845: (4, 32),
                           6344853: (4, 32),
                           6344861: (4, 32),
                           6344869: (4, 32),
                           6344877: (4, 32),
                           6344913: (3, 480),
                           6344959: (4, 480),
                           6344970: (4, 480),
                           6344982: (4, 480),
                           6344994: (5, 480),
                           6345011: (4, 480),
                           6345023: (4, 480),
                           6345035: (4, 480),
                           6345048: (5, 480),
                           6345119: (4, 704),
                           6345130: (4, 704),
                           6345142: (5, 704),
                           6345151: (4, 704),
                           6345159: (5, 704),
                           6345168: (4, 704),
                           6345179: (5, 704),
                           6345192: (5, 704),
                           6345216: (4, 0),
                           6345322: (4, 0)},
           'rip_sites': {6344555: (2, 55065632), 6344561: (3, 53634152)}},
 'leave': {'entry': 6345472,
           'end': 6346592,
           'sha256': '973e04a016a90f53ba131da1590d9e647b7c9ad8ebec35018ae173d72a22cf6a',
           'lengths': (5, 5, 1, 1, 2, 4, 3, 6, 7, 2, 7, 2, 7, 4, 4, 3, 2, 7, 6, 2, 2, 4, 3, 4, 4, 2, 2, 2, 2,
                       2, 3, 2, 5, 7, 3, 3, 2, 7, 5, 2, 2, 4, 2, 5, 8, 8, 2, 5, 3, 8, 8, 8, 8, 5, 5, 5, 5, 4,
                       5, 4, 3, 8, 3, 8, 4, 8, 4, 8, 4, 8, 4, 8, 4, 8, 4, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
                       8, 8, 8, 5, 3, 8, 4, 8, 4, 8, 4, 8, 4, 8, 4, 8, 4, 8, 5, 5, 5, 5, 5, 5, 5, 4, 5, 4, 7,
                       3, 3, 3, 4, 4, 4, 4, 5, 5, 4, 8, 3, 8, 4, 8, 4, 9, 5, 3, 8, 4, 8, 4, 8, 5, 9, 5, 5, 5,
                       5, 5, 5, 5, 5, 4, 5, 4, 5, 4, 8, 3, 8, 4, 8, 8, 8, 8, 3, 8, 4, 8, 5, 5, 5, 8, 2, 7, 6,
                       3, 3, 4, 3, 2, 7, 7, 5, 3, 3, 3, 4, 4, 3, 2, 2, 2, 2, 3, 2, 3, 5, 2, 4, 8, 7, 7, 5, 4,
                       4, 4, 3, 2, 7, 6, 8, 2, 4, 3, 3, 4, 2, 2, 3, 2, 2, 3, 2, 3, 4, 6, 5, 5, 4, 2, 1, 1,
                       1),
           'array_sites': {6345639: (4, 0),
                           6345665: (4, 0),
                           6345673: (4, 0),
                           6345681: (4, 0),
                           6345725: (4, 32),
                           6345736: (4, 32),
                           6345748: (4, 32),
                           6345760: (4, 32),
                           6345772: (4, 32),
                           6345784: (4, 32),
                           6345796: (4, 32),
                           6345812: (4, 32),
                           6345820: (4, 32),
                           6345828: (4, 32),
                           6345836: (4, 32),
                           6345844: (4, 32),
                           6345852: (4, 32),
                           6345860: (4, 32),
                           6345868: (4, 32),
                           6345876: (4, 32),
                           6345884: (4, 32),
                           6345892: (4, 32),
                           6345900: (4, 32),
                           6345908: (4, 32),
                           6345916: (4, 32),
                           6345932: (4, 32),
                           6345944: (4, 32),
                           6345956: (4, 32),
                           6345968: (4, 32),
                           6345980: (4, 32),
                           6345992: (4, 32),
                           6346004: (4, 32),
                           6346060: (3, 480),
                           6346106: (4, 480),
                           6346117: (4, 480),
                           6346129: (4, 480),
                           6346141: (5, 480),
                           6346158: (4, 480),
                           6346170: (4, 480),
                           6346182: (4, 480),
                           6346195: (5, 480),
                           6346266: (4, 704),
                           6346277: (4, 704),
                           6346289: (4, 704),
                           6346297: (4, 704),
                           6346305: (4, 704),
                           6346313: (4, 704),
                           6346324: (4, 704),
                           6346336: (4, 704),
                           6346359: (4, 0),
                           6346463: (4, 0)},
           'rip_sites': {6345493: (2, 55065632), 6345499: (3, 53634152)}}}
HELPERS={0x173B6F0:0x104,0x173B8D0:0x182,0x173BC20:0x77}
REASONS={1:'global_roster_binding_mismatch',2:'tracked_count_zero_or_above_8',
         3:'prefix_dense_tracked_order_invalid',4:'map_capacity_not_8',
         5:'requested_id_missing_or_sentinel',6:'map_ordinal_outside_dense_range',
         7:'classification_direction_invalid',8:'target_record_id_disagrees_with_map',
         9:'target_entity_prefix_flag_not_set'}


def load_sources(evidence_path:Path)->dict[str,bytes]:
    raw=Path(evidence_path).read_bytes();require(sha(raw)==EVIDENCE_SHA256,'classification evidence fingerprint mismatch')
    evidence=json.loads(raw);result={}
    for kind,spec in SPECS.items():
        blob=bytes.fromhex(evidence['bodies'][hex(spec['entry'])]['bytes_hex'])
        require(len(blob)==spec['end']-spec['entry'] and sha(blob)==spec['sha256'],'classification body fingerprint mismatch')
        result[kind]=blob
    return result


def _preflight(kind,game_base,code_address,roster_address,storage_address,reject_address):
    c=_Code(code_address)
    c.emit(bytes.fromhex('515241504151535657')) # args and RBX/RSI/RDI, 56 stack bytes
    c.emit(bytes.fromhex('488bf2')) # RSI=entity
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+GLOBAL_RVA));c.emit(bytes.fromhex('488b38'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',roster_address));c.emit(bytes.fromhex('483bf8'))
    c.branch(b'\x0f\x85','reject1')
    c.emit(bytes.fromhex('8b9f8000000085db'));c.branch(b'\x0f\x84','reject2')
    c.emit(bytes.fromhex('83fb08'));c.branch(b'\x0f\x87','reject2')
    c.emit(bytes.fromhex('8b87840000003bc3'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('8b8f880000003bc8'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('448b8fd80000004183f908'));c.branch(b'\x0f\x85','reject4')
    c.emit(bytes.fromhex('4c8b87d00000008b56083b97dc000000'));c.branch(b'\x0f\x84','reject5')
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+SENTINEL_RVA));c.emit(bytes.fromhex('3b10'))
    c.branch(b'\x0f\x84','reject5')
    c.emit(bytes.fromhex('8bc20faf87e000000083e00733c9'))
    c.label('lookup')
    c.emit(bytes.fromhex('413b14c0'));c.branch(b'\x0f\x84','found')
    c.emit(bytes.fromhex('458b1cc0443b9fdc000000'));c.branch(b'\x0f\x84','reject5')
    c.emit(bytes.fromhex('ffc083e007ffc183f908'));c.branch(b'\x0f\x82','lookup')
    c.branch(b'\xe9','reject5')
    c.label('found')
    c.emit(bytes.fromhex('418b5cc0043b9f84000000'));c.branch(b'\x0f\x83','reject6')
    c.emit(bytes.fromhex('3b9f88000000'))
    c.branch(b'\x0f\x82' if kind=='enter' else b'\x0f\x83','reject7')
    c.emit(b'\x49\xbb'+struct.pack('<Q',storage_address))
    c.emit(bytes.fromhex('4d8b1cdb413b5308'));c.branch(b'\x0f\x85','reject8')
    c.emit(bytes.fromhex('41f6431401'));c.branch(b'\x0f\x84','reject9')
    restore=bytes.fromhex('5f5e5b415941585a59')
    c.label('accepted');c.emit(restore);c.branch(b'\xe9','body')
    for reason in REASONS:
        c.label('reject'+str(reason));c.emit(restore)
        c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9',reject_address)
    c.emit(b'\xcc'*((-len(c.data))%16));c.label('body')
    return c.finish(),c.labels


def build(source:bytes,*,kind:str,game_base:int,code_address:int,roster_address:int,
          storage_address:int,reject_address:int)->dict:
    require(kind in SPECS,'unknown classification kind');spec=SPECS[kind]
    require(type(source)is bytes and len(source)==spec['end']-spec['entry'] and sha(source)==spec['sha256'],
            'classification source fingerprint mismatch')
    pointer(game_base,SENTINEL_RVA+4,0x1000,'game_base');pointer(code_address,1,16,'code_address')
    pointer(roster_address,0x428,8,'roster_address');pointer(storage_address,0x680,16,'storage_address')
    require(storage_address>=0xE8,'storage cannot encode bias');pointer(reject_address,1,1,'reject_address')
    prefix,labels=_preflight(kind,game_base,code_address,roster_address,storage_address,reject_address)
    pieces=[];mapping={};patches=[];offset=0;cursor=code_address+len(prefix)
    for size in spec['lengths']:
        old=spec['entry']+offset;raw=source[offset:offset+size];mapping[old]=cursor
        blob=raw;target=None;disp=None;reason=None
        if old in spec['array_sites']:
            at,delta=spec['array_sites'][old];patched=bytearray(raw)
            original_disp=struct.unpack_from('<i',raw,at)[0]
            struct.pack_into('<i',patched,at,original_disp+delta)
            # Every selected operand uses RBP=S; no selected instruction writes
            # RBP or uses RSP. Restore RBP immediately, before any call or branch.
            blob=b'\x55\x48\xbd'+struct.pack('<Q',storage_address-0xE8)+bytes(patched)+b'\x5d'
            patches.append({'original_rva':old,'emitted_address':cursor,'original_hex':raw.hex(),
                            'replacement_hex':blob.hex(),'displacement_delta':delta})
        elif len(raw)==2 and 0x70<=raw[0]<=0x7F:
            target=old+2+struct.unpack('<b',raw[1:])[0];blob=bytes([0x0F,raw[0]+0x10])+b'\0'*4;disp=2;reason='local_branch'
        elif len(raw)==2 and raw[0]==0xEB:
            target=old+2+struct.unpack('<b',raw[1:])[0];blob=b'\xe9'+b'\0'*4;disp=1;reason='local_branch'
        elif len(raw)==5 and raw[0]in(0xE8,0xE9):
            target=old+5+struct.unpack('<i',raw[1:])[0];disp=1
            reason='local_branch' if spec['entry']<=target<spec['end'] else 'helper_call'
            require(reason=='local_branch' or (raw[0]==0xE8 and target in HELPERS),'unexpected classification direct target')
        elif old in spec['rip_sites']:
            at,expected=spec['rip_sites'][old];target=old+size+struct.unpack_from('<i',raw,at)[0]
            require(target==expected,'classification RIP target changed');disp=at;reason='global_read'
        pieces.append({'rva':old,'address':cursor,'blob':blob,'target':target,'disp':disp,'reason':reason})
        cursor+=len(blob);offset+=size
    require(offset==len(source) and len(patches)==len(spec['array_sites']),'incomplete classification relocation')
    relocations=[]
    for p in pieces:
        if p['target']is None:continue
        t=p['target']
        if p['reason']=='local_branch':
            require(t in mapping,'branch is not an original instruction boundary');dest=mapping[t]
        else:dest=game_base+t
        blob=bytearray(p['blob']);at=p['disp'];blob[at:at+4]=rel32(p['address']+len(blob),dest);p['blob']=bytes(blob)
        relocations.append({'original_rva':p['rva'],'emitted_address':p['address'],'kind':p['reason'],
                            'original_target_rva':t,'target_address':dest})
    code=prefix+b''.join(p['blob']for p in pieces)
    pointer(code_address,len(code),16,'complete classification code')
    regions=[{'name':'classification code','address':code_address,'size_bytes':len(code)},
             {'name':'classification reject','address':reject_address,'size_bytes':1},
             {'name':'original roster','address':roster_address,'size_bytes':0x428},
             {'name':'four-array sidecar','address':storage_address,'size_bytes':0x680},
             {'name':'roster global','address':game_base+GLOBAL_RVA,'size_bytes':8},
             {'name':'entity sentinel','address':game_base+SENTINEL_RVA,'size_bytes':4}]
    regions.extend({'name':'temporary helper '+hex(rva),'address':game_base+rva,'size_bytes':size}for rva,size in HELPERS.items())
    regions.extend({'name':'original '+k,'address':game_base+s['entry'],'size_bytes':s['end']-s['entry']}for k,s in SPECS.items())
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'known classification region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_classify_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'kind':kind,'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'body_address':labels['body'],
            'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),
            'roster_address':roster_address,'storage_address':storage_address,'storage_size_bytes':0x680,
            'reject_address':reject_address,'known_regions':regions,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},'array_patches':patches,'relocations':relocations,
            'reject_reasons':{str(k):v for k,v in REASONS.items()},
            'reject_state':{'rsp':'entry RSP after restoring seven saved registers',
                            'preserved':'RCX/RDX/R8/R9 and all nonvolatile GPR/XMM',
                            'clobbered':'RAX, R10(reason), R11, flags',
                            'writes':'56 bytes scratch stack; no roster/sidecar/map/entity mutation'},
            'entry_or_callsite_patch':None,
            'limits':['Valid mapped entity/record/map pointers and synchronized global/count/record/map state are required',
                      'Eight-bucket map must have unique keys, valid probe chains and a bijection with tracked records',
                      'Target is dense; enter target is outside prefix, leave target is inside prefix; its bit0 must already be set',
                      'Caller flag updates and notifications remain external; candidate does not change any entity flags',
                      'Rejection preserves entry state only; it cannot roll back a caller flag/notification already performed before entry',
                      'Enter clears primary[old P], leaves primary[target] in place; primary is not preserved per entity',
                      'Temporary helpers must return successfully without reentry/interleaving; original mutates before allocation, so allocation failure is not atomic',
                      'No allocation/publication/cleanup, rejection handler, Windows unwind, hook or multiplayer validation']}


def build_bundle(classify_sources:dict[str,bytes],remove_sources:dict[str,bytes],insert_sources:dict[str,bytes],
                 move_source:bytes,producer_source:bytes,receiver_source:bytes,*,classify_code_addresses:dict[str,int],
                 classify_reject_addresses:dict[str,int],**remove_params)->dict:
    require(set(classify_sources)==set(classify_code_addresses)==set(classify_reject_addresses)==set(SPECS),'incomplete classification bundle')
    base=remove.build_bundle(remove_sources,insert_sources,move_source,producer_source,receiver_source,**remove_params)
    shared=base['shared_binding'];classifiers={}
    for kind in SPECS:
        classifiers[kind]=build(classify_sources[kind],kind=kind,**shared,code_address=classify_code_addresses[kind],
                                reject_address=classify_reject_addresses[kind])
    # Replace the earlier one-byte allocator-entry reservation with the full
    # now-captured helper. Do not merge arbitrary overlapping regions.
    regions=list(base['known_regions'])
    for rva,size in HELPERS.items():
        address=shared['game_base']+rva
        if rva==0x173B8D0:
            regions=[r for r in regions if not(r['name']=='allocator entry' and r['address']==address and r['size_bytes']==1)]
        if not any(r['address']==address and r['size_bytes']==size for r in regions):
            regions.append({'name':'temporary helper '+hex(rva),'address':address,'size_bytes':size})
    for kind,a in classifiers.items():
        for label,address,size in [('code',a['code_address'],a['size_bytes']),('reject',a['reject_address'],1),
                                   ('original',shared['game_base']+SPECS[kind]['entry'],SPECS[kind]['end']-SPECS[kind]['entry'])]:
            regions.append({'name':'classify '+kind+' '+label,'address':address,'size_bytes':size})
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'classification bundle region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_classify_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'classifiers':classifiers,'known_regions':regions,
            'limits':base['limits']+['Source-faithful classification uses successful temporary helpers; caller flags/notifications, primary ownership and full lifecycle integration remain unverified']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('evidence','remove-evidence','insert-evidence','move-evidence','producer-evidence','receiver-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    result=build_bundle(load_sources(args.evidence),remove.load_sources(args.remove_evidence),remove.insert.load_sources(args.insert_evidence),
                        move.load_source(args.move_evidence),remove.insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        remove.insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),**json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'classify_sizes':{k:v['size_bytes']for k,v in result['classifiers'].items()}}))


if __name__=='__main__':main()
