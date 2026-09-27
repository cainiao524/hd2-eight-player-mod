"""Emit the complete offline 6054F0 roster state-update candidate.

The working filename does not establish arrival/append caller reachability.
Four parallel arrays share B; original bounded palette and current-D
notifications remain. No process access, installation or native execution.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

_spec=importlib.util.spec_from_file_location('roster_registry_update',Path(__file__).with_name('roster_registry_update.py'))
registry=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(registry)
departure=registry.departure;remove=registry.remove;move=registry.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
_Code=remove._Code
TARGET_PROFILE=dict(move.TARGET_PROFILE)
IMAGE_SIZE=74727424
ENTRY,END=0x6054F0,0x605947
SOURCE_SHA256='6ad21683150fa35285c490fb75b00d8f0af68ab36dad70cbced0bccfc745288a'
EVIDENCE_SHA256='c3073ba7658599bc662d980397f21bf7a003f56a2b821cdcf4c2341fe05a2e64'
GLOBAL_RVA,SENTINEL_RVA=0x3326468,0x3483C20
sha=lambda b:hashlib.sha256(b).hexdigest()
LENGTHS=(5,
 5,
 5,
 5,
 2,
 7,
 5,
 7,
 3,
 5,
 3,
 3,
 6,
 3,
 7,
 2,
 7,
 2,
 7,
 4,
 4,
 3,
 2,
 7,
 6,
 4,
 9,
 2,
 4,
 3,
 4,
 2,
 6,
 2,
 6,
 2,
 3,
 2,
 5,
 4,
 6,
 4,
 2,
 4,
 7,
 2,
 3,
 2,
 8,
 4,
 2,
 4,
 11,
 7,
 4,
 7,
 7,
 7,
 3,
 6,
 7,
 6,
 6,
 3,
 4,
 2,
 2,
 7,
 7,
 3,
 3,
 3,
 2,
 4,
 2,
 3,
 3,
 2,
 3,
 2,
 4,
 4,
 2,
 3,
 4,
 4,
 3,
 2,
 11,
 2,
 2,
 6,
 5,
 5,
 11,
 2,
 11,
 7,
 3,
 12,
 2,
 4,
 11,
 3,
 2,
 8,
 6,
 7,
 2,
 3,
 4,
 8,
 2,
 3,
 7,
 6,
 7,
 2,
 11,
 4,
 5,
 3,
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
 3,
 2,
 8,
 4,
 8,
 7,
 3,
 2,
 3,
 7,
 4,
 5,
 6,
 3,
 6,
 4,
 2,
 3,
 3,
 3,
 7,
 8,
 4,
 4,
 4,
 6,
 6,
 6,
 2,
 7,
 5,
 3,
 4,
 7,
 2,
 7,
 7,
 2,
 7,
 2,
 8,
 7,
 3,
 2,
 3,
 3,
 2,
 2,
 7,
 3,
 2,
 2,
 7,
 6,
 2,
 11,
 7,
 2,
 6,
 6,
 4,
 2,
 6,
 3,
 5,
 2,
 7,
 4,
 2,
 7,
 7,
 7,
 7,
 4,
 2,
 3,
 2,
 2,
 8,
 8,
 4,
 7,
 6,
 5,
 5,
 5,
 7,
 2,
 6,
 6,
 6,
 5,
 7,
 7,
 6,
 4,
 7,
 5,
 3,
 5,
 8,
 4,
 4,
 4,
 4,
 5,
 3,
 2,
 1)
RELOCATIONS={6313234: (3, 40091664, 'rip_memory'),
 6313255: (2, 55065632, 'rip_memory'),
 6313264: (3, 53634152, 'rip_memory'),
 6313432: (3, 54973752, 'rip_memory'),
 6313450: (3, 55037680, 'rip_memory'),
 6313628: (3, 55037544, 'rip_memory'),
 6313680: (2, 55065652, 'rip_memory'),
 6313722: (2, 55065652, 'rip_memory'),
 6313752: (1, 16620272, 'call_rel32'),
 6313771: (3, 53633800, 'rip_memory'),
 6313804: (4, 37514608, 'rip_memory'),
 6313839: (3, 34862304, 'rip_address'),
 6313885: (2, 55039520, 'rip_memory'),
 6313892: (4, 37517740, 'rip_memory'),
 6313932: (3, 53633800, 'rip_memory'),
 6313951: (3, 55039648, 'rip_memory'),
 6313960: (3, 53633856, 'rip_memory'),
 6313976: (3, 55037520, 'rip_memory'),
 6314055: (3, 53636712, 'rip_memory'),
 6314111: (3, 53634152, 'rip_memory'),
 6314132: (3, 53634720, 'rip_memory'),
 6314195: (1, 9750976, 'call_rel32'),
 6314200: (3, 53633856, 'rip_memory'),
 6314227: (1, 6341280, 'call_rel32'),
 6314232: (3, 53633800, 'rip_memory'),
 6314239: (3, 35943368, 'rip_address'),
 6314271: (1, 34113392, 'call_rel32')}
ARRAYS={6313403: ('base', -232, 3),
 6313421: ('index', 472, 2),
 6313503: ('r11', 1412, 0),
 6313510: ('r10', 0, 0),
 6313573: ('index', -200, 2),
 6313604: ('index', -200, 2),
 6313617: ('index', -200, 2),
 6313638: ('index', -200, 3),
 6313656: ('index', 248, 2),
 6313672: ('index', 248, 2),
 6313686: ('index', 248, 2),
 6313702: ('index', 472, 3),
 6313715: ('index', 248, 2),
 6313728: ('index', 248, 2),
 6313737: ('index', 248, 2),
 6313816: ('index', 248, 3),
 6313824: ('base', 472, 2),
 6313985: ('index', 248, 3),
 6314044: ('index', 248, 2)}
REASONS={1:'global_roster_binding_mismatch',2:'null_target',3:'null_caller_state',
         4:'tracked_count_zero_or_above_8',5:'prefix_dense_tracked_order_invalid',
         6:'map_capacity_not_8',7:'invalid_or_empty_entity_id',8:'requested_entity_id_missing',
         9:'map_ordinal_outside_tracked_range',10:'pointer_record_is_not_target'}
LIMITS=[
 'Only a fixed-build offline state-update candidate; the working arrival filename is not proof of append/arrival caller reachability',
 'Bound S/B, target, all dense pointer records, map/backing and caller-state resources must remain valid and serialized through callbacks; the guard does not supply lifetime, readable memory or synchronization',
 'Counts, map and binding are checked before any original effects, but callbacks can invalidate those assumptions; no reentrancy defense or resource rollback is provided',
 'Original FD9AF0 associated context, handle interfaces, palette callback, mode4 object records, registry notifications and cookie-checker contracts remain required',
 'Network index is distinct from ordinal. Original network indices below4 select four saved color records; all indices at least4 retain the bounded default, not new unique colors',
 'All original count notifications use current dense D. Global-S and held-S reads agree only under the stable binding/count contract. No predictive departure count is introduced',
 'The existing player-count patch plan is included in the shared build; actual configuration assets/full context execution and named resources beyond four remain unverified',
 'No storage allocation/initialization/migration/publication/cleanup, entry patch, reject handler, Windows unwind, runtime version check, installation, game execution or multiplayer validation',
]


def load_source(path:Path)->bytes:
    raw=Path(path).read_bytes();require(sha(raw)==EVIDENCE_SHA256,'state-update evidence fingerprint mismatch')
    blob=bytes.fromhex(json.loads(raw)['bodies'][hex(ENTRY)]['bytes_hex'])
    require(len(blob)==END-ENTRY and sha(blob)==SOURCE_SHA256,'state-update body fingerprint mismatch')
    return blob


def _preflight(c,game_base,roster_address,storage_address,reject_address):
    # Seven scratch saves preserve argument registers and every touched NV.
    c.emit(bytes.fromhex('515241504151535657488bf2'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+GLOBAL_RVA));c.emit(bytes.fromhex('488b38'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',roster_address));c.emit(bytes.fromhex('483bf8'))
    c.branch(b'\x0f\x85','reject1')
    c.emit(bytes.fromhex('4885f6'));c.branch(b'\x0f\x84','reject2')
    c.emit(bytes.fromhex('48837c242000'));c.branch(b'\x0f\x84','reject3')
    c.emit(bytes.fromhex('8b9f8000000085db'));c.branch(b'\x0f\x84','reject4')
    c.emit(bytes.fromhex('83fb08'));c.branch(b'\x0f\x87','reject4')
    c.emit(bytes.fromhex('8b87840000003bc3'));c.branch(b'\x0f\x87','reject5')
    c.emit(bytes.fromhex('8b8f880000003bc8'));c.branch(b'\x0f\x87','reject5')
    c.emit(bytes.fromhex('83bfd800000008'));c.branch(b'\x0f\x85','reject6')
    c.emit(bytes.fromhex('8b56083b97dc000000'));c.branch(b'\x0f\x84','reject7')
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+SENTINEL_RVA))
    c.emit(bytes.fromhex('3b10'));c.branch(b'\x0f\x84','reject7')
    c.emit(bytes.fromhex('4c8b87d00000008bc20faf87e000000083e00733c9'))
    c.label('lookup');c.emit(bytes.fromhex('413b14c0'));c.branch(b'\x0f\x84','found')
    c.emit(bytes.fromhex('458b1cc0443b9fdc000000'));c.branch(b'\x0f\x84','reject8')
    c.emit(bytes.fromhex('ffc083e007ffc183f908'));c.branch(b'\x0f\x82','lookup')
    c.branch(b'\xe9','reject8');c.label('found')
    c.emit(bytes.fromhex('418b5cc0043b9f80000000'));c.branch(b'\x0f\x83','reject9')
    c.emit(b'\x49\xbb'+struct.pack('<Q',storage_address))
    c.emit(bytes.fromhex('4d8b1cdb4c3bde'));c.branch(b'\x0f\x85','reject10')
    restore=bytes.fromhex('5f5e5b415941585a59')
    c.emit(restore);c.branch(b'\xe9','body')
    for reason in REASONS:
        c.label('reject'+str(reason));c.emit(restore)
        c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9',reject_address)
    c.emit(b'\xcc'*((-len(c.data))%16));c.label('body')


def build(source:bytes,*,game_base:int,code_address:int,roster_address:int,
          storage_address:int,reject_address:int)->dict:
    require(type(source)is bytes and len(source)==END-ENTRY and sha(source)==SOURCE_SHA256,
            'state-update source fingerprint mismatch')
    pointer(game_base,IMAGE_SIZE,0x1000,'game_base');pointer(code_address,1,16,'code_address')
    pointer(roster_address,0x428,8,'roster_address');pointer(storage_address,0x680,16,'storage_address')
    pointer(reject_address,1,1,'reject_address');require(storage_address>=0x100E8,'invalid biased storage')
    c=_Code(code_address);_preflight(c,game_base,roster_address,storage_address,reject_address)
    mapping={};patches=[];relocs=[];offset=0;body_address=c.labels['body']
    for size in LENGTHS:
        old=ENTRY+offset;raw=source[offset:offset+size];offset+=size
        c.label(hex(old));address=c.base+len(c.data);mapping[old]=address
        if old in ARRAYS:
            mode,bias,sib_at=ARRAYS[old]
            if mode in ('r10','r11'):
                blob=(b'\x49\xba' if mode=='r10' else b'\x49\xbb')+struct.pack('<Q',storage_address+bias)
            else:
                out=bytearray(raw)
                if mode=='base':
                    require(out[sib_at]&7==7,'array base is no longer RDI')
                    out[sib_at]=(out[sib_at]&0xf8)|3;rexbit=1
                else:
                    require(out[sib_at]&0x38==0x38,'array index is no longer RDI')
                    out[sib_at]=(out[sib_at]&0xc7)|0x18;rexbit=2
                if 0x40<=out[0]<=0x4f:out[0]|=rexbit
                else:out[:0]=bytes([0x40|rexbit])
                blob=b'\x49\xbb'+struct.pack('<Q',storage_address+bias)+bytes(out)
            c.emit(blob);patches.append({'original_rva':old,'emitted_address':address,
                                        'original_hex':raw.hex(),'replacement_hex':blob.hex(),'storage_bias':bias})
        elif old in RELOCATIONS:
            at,target,kind=RELOCATIONS[old]
            require(old+size+struct.unpack_from('<i',raw,at)[0]==target,'source relocation mismatch')
            blob=bytearray(raw);blob[at:at+4]=rel32(address+size,game_base+target);c.emit(blob)
            relocs.append({'original_rva':old,'emitted_address':address,'kind':kind,
                           'original_target_rva':target,'target_address':game_base+target})
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
    require(offset==len(source) and len(patches)==19,'incomplete state-update emission')
    for row in relocs:
        if row['kind']=='local_branch':
            require(row['original_target_rva'] in mapping,'branch not on source boundary')
            row['target_address']=mapping[row['original_target_rva']]
    code=c.finish();pointer(code_address,len(code),16,'complete state-update code')
    regions=[{'name':name,'address':address,'size_bytes':size} for name,address,size in [
        ('state update code',code_address,len(code)),('state update reject',reject_address,1),
        ('original roster',roster_address,0x428),('four-array sidecar',storage_address,0x680),('game image',game_base,IMAGE_SIZE)]]
    registry._check_regions(regions)
    return {'status':'offline_native_roster_state_update_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'body_address':body_address,
            'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),'roster_address':roster_address,
            'storage_address':storage_address,'storage_size_bytes':0x680,'reject_address':reject_address,
            'array_patches':patches,'relocations':relocs,'known_regions':regions,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},
            'guard_addresses':{k:v for k,v in c.labels.items() if not k.startswith('0x')},
            'reject_reasons':{str(k):v for k,v in REASONS.items()},
            'reject_state':{'rsp':'original entry RSP; RCX/RDX/R8/R9 and every nonvolatile GPR/XMM preserved',
                            'reason':'R10D, 1..10; RAX/R11/flags unspecified',
                            'writes':'56 bytes below entry RSP from scratch saves; no nonstack writes or calls'},
            'entry_or_callsite_patch':None,'limits':list(LIMITS)}


def build_bundle(source:bytes,registry_sources:dict[str,bytes],*departure_sources,
                 arrival_code_address:int,arrival_reject_address:int,**registry_params)->dict:
    base=registry.build_bundle(registry_sources,*departure_sources,**registry_params);shared=base['shared_binding']
    arrival=build(source,**shared,code_address=arrival_code_address,reject_address=arrival_reject_address)
    regions=list(base['known_regions'])+[
        {'name':'state update code','address':arrival_code_address,'size_bytes':arrival['size_bytes']},
        {'name':'state update reject','address':arrival_reject_address,'size_bytes':1},
        {'name':'original state update','address':shared['game_base']+ENTRY,'size_bytes':END-ENTRY}]
    registry._check_regions(regions)
    return {'status':'offline_native_roster_state_update_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'arrival':arrival,
            'known_regions':regions,'limits':base['limits']+arrival['limits']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','registry-evidence','departure-evidence','getter-evidence','classify-evidence','remove-evidence',
                 'insert-evidence','move-evidence','producer-evidence','receiver-evidence','player-count-evidence','context-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    g=departure.getter;counts=departure.player_count.load_sources(args.player_count_evidence,args.context_evidence)
    result=build_bundle(load_source(args.evidence),registry.load_sources(args.registry_evidence),departure.load_source(args.departure_evidence),
                        g.load_source(args.getter_evidence),g.classify.load_sources(args.classify_evidence),remove.load_sources(args.remove_evidence),
                        remove.insert.load_sources(args.insert_evidence),move.load_source(args.move_evidence),
                        remove.insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        remove.insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),
                        player_count_context_source=counts['context'],player_count_filter_source=counts['filter'],
                        **json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'functions':16,'known_regions':len(result['known_regions'])}))


if __name__=='__main__':main()
