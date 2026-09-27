"""Emit an offline ID-to-network-index reader for shared eight-slot storage.

Preserve original missing returns and the complete property DWORD. Guard a
foreign roster before map access, and invalid active ordinals before property
access. No process access, allocation, hooks or host-native code execution.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

_spec=importlib.util.spec_from_file_location('roster_classify',Path(__file__).with_name('roster_classify.py'))
classify=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(classify)
remove=classify.remove;move=remove.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
_Code=remove._Code
TARGET_PROFILE=dict(move.TARGET_PROFILE)
EVIDENCE_SHA256='1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd'
ENTRY,END=0x606AD0,0x606B75
SOURCE_SHA256='96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb'
GLOBAL_RVA,SENTINEL_RVA=0x3326468,0x3483C20
EARLY_GUARD,LATE_GUARD,PROPERTY_READ=0x606AF3,0x606B67,0x606B6B
LENGTHS=(5, 5, 5, 5, 6, 7, 2, 7, 2, 7, 3, 4, 3, 2, 7, 7, 3, 2, 4, 3, 4, 4, 2, 2, 2, 2, 2, 3, 2, 5, 5, 5, 5, 5, 1, 2, 2, 4, 3, 2, 4, 8, 2)
REASONS={1:'global_roster_binding_mismatch',2:'map_ordinal_not_below_8',
         3:'tracked_count_above_8',4:'map_ordinal_not_below_tracked_count',
         5:'requested_id_equals_empty_bucket_key'}
sha=lambda b:hashlib.sha256(b).hexdigest()


def load_source(evidence_path:Path)->bytes:
    raw=Path(evidence_path).read_bytes();require(sha(raw)==EVIDENCE_SHA256,'getter evidence fingerprint mismatch')
    blob=bytes.fromhex(json.loads(raw)['bodies'][hex(ENTRY)]['bytes_hex'])
    require(len(blob)==END-ENTRY and sha(blob)==SOURCE_SHA256,'getter body fingerprint mismatch')
    return blob


def build(source:bytes,*,game_base:int,code_address:int,roster_address:int,
          storage_address:int,reject_address:int)->dict:
    require(type(source)is bytes and len(source)==END-ENTRY and sha(source)==SOURCE_SHA256,
            'getter source fingerprint mismatch')
    pointer(game_base,SENTINEL_RVA+4,0x1000,'game_base');pointer(code_address,1,16,'code_address')
    pointer(roster_address,0x428,8,'roster_address');pointer(storage_address,0x680,16,'storage_address')
    pointer(reject_address,1,1,'reject_address')
    c=_Code(code_address);mapping={};relocations=[];offset=0;array_patch=None;guards={}
    for size in LENGTHS:
        old=ENTRY+offset;raw=source[offset:offset+size];offset+=size
        c.label(hex(old));mapping[old]=c.base+len(c.data)
        if old==EARLY_GUARD:
            # Original invalid-ID branch already ran. Its missing path never
            # dereferences S, even if the loaded global pointer is unmapped.
            guards['binding']=c.base+len(c.data)
            c.emit(b'\x49\xbb'+struct.pack('<Q',roster_address))
            c.emit(bytes.fromhex('4d3bd3'));c.branch(b'\x0f\x85','reject1')
        elif old==LATE_GUARD:
            # Original lookup already excluded value FFFFFFFF. Pending records
            # are readable too: use tracked T, not dense D or prefix P.
            guards['successful_lookup']=c.base+len(c.data)
            c.emit(bytes.fromhex('83f808'));c.branch(b'\x0f\x83','reject2')
            c.emit(bytes.fromhex('4183ba8000000008'));c.branch(b'\x0f\x87','reject3')
            c.emit(bytes.fromhex('413b8280000000'));c.branch(b'\x0f\x83','reject4')
            c.emit(bytes.fromhex('413b92dc000000'));c.branch(b'\x0f\x84','reject5')
        address=c.base+len(c.data)
        if old==PROPERTY_READ:
            require(raw==bytes.fromhex('428b8410b4030000'),'getter property operand changed')
            patched=bytearray(raw);patched[3]=0x18 # SIB index R10 -> R11, retain RAX offset
            blob=b'\x49\xbb'+struct.pack('<Q',storage_address+0x1D8)+bytes(patched)
            c.emit(blob);array_patch={'original_rva':old,'emitted_address':address,
                                    'original_hex':raw.hex(),'replacement_hex':blob.hex()}
        elif len(raw)==2 and 0x70<=raw[0]<=0x7F:
            target=old+2+struct.unpack('<b',raw[1:])[0]
            require(ENTRY<=target<END,'unexpected external getter branch')
            c.branch(bytes([0x0F,raw[0]+0x10]),hex(target))
            relocations.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif len(raw)==2 and raw[0]==0xEB:
            target=old+2+struct.unpack('<b',raw[1:])[0]
            require(ENTRY<=target<END,'unexpected external getter jump')
            c.branch(b'\xe9',hex(target))
            relocations.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif old in (0x606AE4,0x606AEA):
            at=2 if old==0x606AE4 else 3;target=old+size+struct.unpack_from('<i',raw,at)[0]
            require(target==(SENTINEL_RVA if old==0x606AE4 else GLOBAL_RVA),'getter RIP target changed')
            blob=bytearray(raw);blob[at:at+4]=rel32(address+size,game_base+target);c.emit(bytes(blob))
            relocations.append({'original_rva':old,'emitted_address':address,'kind':'global_read',
                                'original_target_rva':target,'target_address':game_base+target})
        else:c.emit(raw)
    require(offset==len(source) and array_patch is not None,'incomplete getter relocation')
    for item in relocations:
        if item['kind']=='local_branch':
            require(item['original_target_rva']in mapping,'getter branch is not an instruction boundary')
            item['target_address']=mapping[item['original_target_rva']]
    for reason in REASONS:
        c.label('reject'+str(reason));c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9','reject_restore')
    c.label('reject_restore')
    c.emit(bytes.fromhex('488b5c2408488b6c2410488b742418488b7c2420'))
    c.branch(b'\xe9',reject_address)
    code=c.finish();pointer(code_address,len(code),16,'complete getter code')
    regions=[{'name':'getter code','address':code_address,'size_bytes':len(code)},
             {'name':'getter reject','address':reject_address,'size_bytes':1},
             {'name':'original getter','address':game_base+ENTRY,'size_bytes':END-ENTRY},
             {'name':'original roster','address':roster_address,'size_bytes':0x428},
             {'name':'four-array sidecar','address':storage_address,'size_bytes':0x680},
             {'name':'roster global','address':game_base+GLOBAL_RVA,'size_bytes':8},
             {'name':'entity sentinel','address':game_base+SENTINEL_RVA,'size_bytes':4}]
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'known getter region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_getter_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'size_bytes':len(code),
            'code_hex':code.hex(),'code_sha256':sha(code),'roster_address':roster_address,
            'storage_address':storage_address,'storage_size_bytes':0x680,'property_address':storage_address+0x580,
            'reject_address':reject_address,'known_regions':regions,'guard_addresses':guards,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},'array_patch':array_patch,'relocations':relocations,
            'reject_reasons':{str(k):v for k,v in REASONS.items()},
            'reject_state':{'rsp':'entry RSP; original four saved nonvolatile registers restored from caller shadow space',
                            'preserved':'EDX entity ID and all nonvolatile GPR/XMM',
                            'clobbered':'RAX, RCX, R8, R9, R10(reason), R11, flags may differ',
                            'writes':'32 bytes of original caller shadow saves; no non-stack data writes'},
            'return_contract':'EAX is the complete property DWORD; RAX upper 32 bits zero. Original invalid-ID/map-miss/zero-capacity/FFFFFFFF-value paths return 00000000FFFFFFFF',
            'entry_or_callsite_patch':None,
            'limits':['Valid synchronized S/map/storage lifetime and a valid map header/backing/probe chain remain required',
                      'Global invalid-ID return bypasses binding check; otherwise binding mismatch rejects before S/map dereference',
                      'Successful lookup requires ordinal<8, T<=8 and ordinal<T; pending members are allowed and network index is not clamped',
                      'Empty-bucket key with non-sentinel value is rejected after lookup instead of permitting the original phantom hit',
                      'Map capacity is not forced to eight here; preserve original zero-capacity return and valid power-of-two lookup semantics',
                      'No complete map bijection or pointer-array identity validation is performed by this scalar reader',
                      'No allocation/publication/cleanup, rejection handler, Windows unwind, hook, caller redirection or multiplayer validation']}


def build_bundle(getter_source:bytes,classify_sources:dict[str,bytes],remove_sources:dict[str,bytes],insert_sources:dict[str,bytes],
                 move_source:bytes,producer_source:bytes,receiver_source:bytes,*,getter_code_address:int,getter_reject_address:int,
                 **classify_params)->dict:
    base=classify.build_bundle(classify_sources,remove_sources,insert_sources,move_source,producer_source,receiver_source,**classify_params)
    shared=base['shared_binding'];getter=build(getter_source,**shared,code_address=getter_code_address,reject_address=getter_reject_address)
    regions=list(base['known_regions'])
    regions.extend([{'name':'getter code','address':getter_code_address,'size_bytes':getter['size_bytes']},
                    {'name':'getter reject','address':getter_reject_address,'size_bytes':1},
                    {'name':'original getter','address':shared['game_base']+ENTRY,'size_bytes':END-ENTRY}])
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'getter bundle region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_getter_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'getter':getter,'known_regions':regions,
            'limits':base['limits']+['One complete ID-to-network-index getter is relocated; other readers and actual caller/hook integration remain incomplete']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('evidence','classify-evidence','remove-evidence','insert-evidence','move-evidence','producer-evidence','receiver-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    result=build_bundle(load_source(args.evidence),classify.load_sources(args.classify_evidence),remove.load_sources(args.remove_evidence),
                        remove.insert.load_sources(args.insert_evidence),move.load_source(args.move_evidence),
                        remove.insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        remove.insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),**json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'getter_size_bytes':result['getter']['size_bytes']}))


if __name__=='__main__':main()
