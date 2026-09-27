"""Emit a fixed-build offline eight-slot pre-removal candidate.

All original resource calls and control-flow branches remain. The two predictive
count notifications use entry D - (ordinal < D); the final tail keeps its
original current-D read. Serialized roster/storage lifetime is an integration
requirement, not provided or established by the entry guard.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path

_spec=importlib.util.spec_from_file_location('roster_getter',Path(__file__).with_name('roster_getter.py'))
getter=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(getter)
remove=getter.remove;move=remove.move
player_count=remove._module('player_count')
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
_Code=remove._Code
TARGET_PROFILE=dict(move.TARGET_PROFILE)
EVIDENCE_SHA256='0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609'
ENTRY,END=0x605950,0x605F2F
SOURCE_SHA256='4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681'
GLOBAL_RVA,SENTINEL_RVA=0x3326468,0x3483C20
IMAGE_SIZE=74727424
sha=lambda b:hashlib.sha256(b).hexdigest()
REASONS={1:'global_roster_binding_mismatch',2:'null_target',3:'tracked_count_zero_or_above_8',
         4:'prefix_dense_tracked_order_invalid',5:'map_capacity_not_8',
         6:'invalid_or_empty_entity_id',7:'requested_id_missing',
         8:'map_ordinal_outside_tracked_range',9:'pointer_record_is_not_target',
         10:'target_prefix_flag_disagrees_with_dense_partition'}
ARRAYS={0x605A0D:('base',-0xE8),0x605B96:('base',-0xE8),
        0x605A26:('index',-0xC8),0x605A3A:('index',-0xC8),
        0x605A4E:('index',-0xC8),0x605A5B:('index',0x1D8)}
# Metadata decoded once from the fixed, fingerprinted complete body.
LENGTHS=(3, 4, 1, 1, 2, 7, 7, 4, 4, 4, 3, 3, 6, 2, 7, 2, 7, 4, 4, 3, 2, 7, 7, 2, 2, 4, 3, 4, 2, 6, 2, 6, 2, 3, 2, 5,
 2, 6, 4, 2, 4, 3, 5, 7, 2, 5, 2, 4, 2, 2, 2, 8, 4, 2, 4, 3, 4, 8, 5, 4, 3, 8, 5, 4, 3, 8, 5, 8, 5, 5, 3, 7,
 3, 6, 7, 6, 5, 6, 3, 6, 4, 6, 3, 2, 6, 7, 4, 7, 2, 2, 6, 3, 3, 5, 5, 3, 6, 7, 2, 7, 2, 7, 4, 4, 3, 2, 7, 6,
 2, 3, 4, 3, 4, 2, 6, 2, 6, 2, 3, 2, 2, 2, 2, 7, 7, 3, 5, 3, 6, 7, 2, 2, 2, 5, 2, 6, 5, 5, 2, 6, 8, 4, 6, 7,
 7, 6, 3, 7, 3, 5, 5, 2, 6, 5, 5, 7, 2, 7, 4, 8, 4, 3, 2, 7, 7, 8, 3, 4, 3, 4, 3, 6, 2, 6, 2, 3, 2, 2, 8, 2,
 7, 7, 3, 5, 3, 2, 6, 2, 2, 7, 2, 7, 4, 4, 3, 2, 7, 7, 4, 10, 2, 4, 3, 4, 3, 2, 2, 2, 2, 3, 2, 2, 2, 6, 5, 5,
 2, 2, 5, 2, 3, 7, 5, 7, 3, 5, 4, 5, 3, 2, 4, 2, 2, 5, 4, 3, 5, 3, 5, 5, 8, 6, 3, 7, 4, 8, 8, 5, 6, 8, 5, 7,
 2, 2, 4, 2, 2, 3, 2, 5, 7, 4, 5, 2, 3, 2, 4, 2, 3, 7, 5, 7, 2, 8, 3, 2, 4, 3, 4, 7, 2, 8, 3, 2, 3, 2, 4, 2,
 3, 7, 5, 7, 2, 3, 2, 7, 2, 5, 8, 6, 6, 8, 4, 8, 2, 3, 8, 2, 8, 7, 7, 2, 7, 7, 6, 7, 2, 4, 2, 4, 2, 3, 8, 8,
 5, 6, 4, 7, 5, 5, 2, 6, 6, 7, 2, 5, 7, 7, 7, 4, 5, 7, 2, 1, 1, 7)
RELOCATIONS={6314338: (3, 53634152, 'rip_memory'),
 6314363: (2, 55065632, 'rip_memory'),
 6314459: (2, 55065652, 'rip_memory'),
 6314478: (1, 6318112, 'call_rel32'),
 6314483: (3, 55037536, 'rip_memory'),
 6314492: (1, 20562784, 'call_rel32'),
 6314542: (1, 11579424, 'call_rel32'),
 6314562: (1, 11607072, 'call_rel32'),
 6314582: (1, 11597856, 'call_rel32'),
 6314600: (1, 16620672, 'call_rel32'),
 6314608: (3, 53633856, 'rip_memory'),
 6314678: (3, 53633800, 'rip_memory'),
 6314717: (1, 8619648, 'call_rel32'),
 6314725: (2, 55065632, 'rip_memory'),
 6314731: (3, 53636384, 'rip_memory'),
 6314844: (1, 10962896, 'call_rel32'),
 6314852: (2, 55065632, 'rip_memory'),
 6314858: (3, 53636384, 'rip_memory'),
 6314920: (3, 55037464, 'rip_memory'),
 6314943: (3, 35943352, 'rip_address'),
 6314953: (1, 20210368, 'call_rel32'),
 6315107: (1, 10962688, 'call_rel32'),
 6315269: (1, 10975232, 'call_rel32'),
 6315296: (1, 20292768, 'call_rel32'),
 6315308: (1, 12460448, 'call_rel32'),
 6315316: (1, 16620864, 'call_rel32'),
 6315343: (3, 54973696, 'rip_memory'),
 6315389: (1, 20708160, 'call_rel32'),
 6315418: (1, 20294416, 'call_rel32'),
 6315434: (1, 12457712, 'call_rel32'),
 6315455: (3, 54968216, 'rip_memory'),
 6315462: (1, 16630544, 'call_rel32'),
 6315467: (3, 53636384, 'rip_memory'),
 6315536: (3, 54968216, 'rip_memory'),
 6315543: (1, 16630544, 'call_rel32'),
 6315548: (3, 53636384, 'rip_memory'),
 6315562: (3, 53636712, 'rip_memory'),
 6315596: (4, 37514608, 'rip_memory'),
 6315639: (3, 53633856, 'rip_memory'),
 6315655: (3, 53634152, 'rip_memory'),
 6315675: (3, 53634720, 'rip_memory'),
 6315742: (1, 9750976, 'call_rel32'),
 6315770: (1, 6341280, 'call_rel32'),
 6315775: (3, 53633800, 'rip_memory'),
 6315782: (3, 35943368, 'rip_address')}
STACK_SITES={6314595: (2, 4, 1, 96),
 6314712: (2, 4, 1, 112),
 6315001: (2, 4, 4, 184),
 6315080: (2, 4, 4, 184),
 6315278: (2, 4, 1, 112),
 6315326: (2, 4, 4, 160),
 6315394: (1, 3, 4, 160),
 6315423: (1, 3, 4, 160),
 6315476: (2, 4, 4, 176),
 6315571: (2, 4, 1, 120),
 6315576: (2, 4, 4, 168),
 6315800: (2, 4, 1, 96)}



def load_source(evidence_path:Path)->bytes:
    raw=Path(evidence_path).read_bytes()
    require(sha(raw)==EVIDENCE_SHA256,'departure evidence fingerprint mismatch')
    blob=bytes.fromhex(json.loads(raw)['bodies'][hex(ENTRY)]['bytes_hex'])
    require(len(blob)==END-ENTRY and sha(blob)==SOURCE_SHA256,'departure body fingerprint mismatch')
    return blob


def _preflight(c,game_base,roster_address,storage_address,reject_address):
    # No calls. Restore all argument registers and the three scratch nonvolatiles.
    # R10D/R11D deliberately carry remaining D and ordinal into the new frame.
    c.emit(bytes.fromhex('515241504151535657488bf2'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+GLOBAL_RVA));c.emit(bytes.fromhex('488b38'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',roster_address));c.emit(bytes.fromhex('483bf8'))
    c.branch(b'\x0f\x85','reject1')
    c.emit(bytes.fromhex('4885f6'));c.branch(b'\x0f\x84','reject2')
    c.emit(bytes.fromhex('8b9f8000000085db'));c.branch(b'\x0f\x84','reject3')
    c.emit(bytes.fromhex('83fb08'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('8b87840000003bc3'));c.branch(b'\x0f\x87','reject4')
    c.emit(bytes.fromhex('8b8f880000003bc8'));c.branch(b'\x0f\x87','reject4')
    c.emit(bytes.fromhex('83bfd800000008'));c.branch(b'\x0f\x85','reject5')
    c.emit(bytes.fromhex('8b56083b97dc000000'));c.branch(b'\x0f\x84','reject6')
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+SENTINEL_RVA))
    c.emit(bytes.fromhex('3b10'));c.branch(b'\x0f\x84','reject6')
    c.emit(bytes.fromhex('4c8b87d00000008bc20faf87e000000083e00733c9'))
    c.label('lookup')
    c.emit(bytes.fromhex('413b14c0'));c.branch(b'\x0f\x84','found')
    c.emit(bytes.fromhex('458b1cc0443b9fdc000000'));c.branch(b'\x0f\x84','reject7')
    c.emit(bytes.fromhex('ffc083e007ffc183f908'));c.branch(b'\x0f\x82','lookup')
    c.branch(b'\xe9','reject7')
    c.label('found')
    c.emit(bytes.fromhex('418b5cc0043b9f80000000'));c.branch(b'\x0f\x83','reject8')
    c.emit(b'\x49\xbb'+struct.pack('<Q',storage_address))
    c.emit(bytes.fromhex('4d8b1cdb4c3bde'));c.branch(b'\x0f\x85','reject9')
    c.emit(bytes.fromhex('3b9f84000000'));c.branch(b'\x0f\x83','predict')
    c.emit(bytes.fromhex('3b9f880000000f92c0410fb64b1483e1013ac1'))
    c.branch(b'\x0f\x85','reject10')
    c.label('predict')
    c.emit(bytes.fromhex('448b9784000000')) # load D before the ordinal comparison
    c.emit(bytes.fromhex('3b9f840000004183da00448bdb')) # R10D=D-CF; R11D=ordinal
    restore=bytes.fromhex('5f5e5b415941585a59')
    c.emit(restore);c.branch(b'\xe9','body')
    for reason in REASONS:
        c.label('reject'+str(reason));c.emit(restore)
        c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9',reject_address)
    c.emit(b'\xcc'*((-len(c.data))%16));c.label('body')


def _stack_rewrite(raw,site):
    modrm,at,size,old=site
    require(int.from_bytes(raw[at:at+size],'little',signed=True)==old,'stack displacement mismatch')
    new=old+0x10;out=bytearray(raw)
    if size==1 and new>0x7f:
        require(raw[modrm]&0xc0==0x40,'expected disp8 stack ModRM')
        out[modrm]=(out[modrm]&0x3f)|0x80
        out[at:at+1]=struct.pack('<i',new)
    else:out[at:at+size]=new.to_bytes(size,'little',signed=True)
    return bytes(out)


def build(source:bytes,*,game_base:int,code_address:int,roster_address:int,
          storage_address:int,getter_code_address:int,reject_address:int)->dict:
    require(type(source)is bytes and len(source)==END-ENTRY and sha(source)==SOURCE_SHA256,
            'departure source fingerprint mismatch')
    pointer(game_base,IMAGE_SIZE,0x1000,'game_base');pointer(code_address,1,16,'code_address')
    pointer(roster_address,0x428,8,'roster_address');pointer(storage_address,0x680,16,'storage_address')
    pointer(getter_code_address,354,16,'getter_code_address');pointer(reject_address,1,1,'reject_address')
    require(storage_address>=0x10000+0xE8,'storage bias falls outside user space')
    c=_Code(code_address);_preflight(c,game_base,roster_address,storage_address,reject_address)
    body_address=c.labels['body'];mapping={};relocs=[];arrays=[];stack=[];offset=0;count_patches=[]
    for size in LENGTHS:
        old=ENTRY+offset;raw=source[offset:offset+size];offset+=size
        c.label(hex(old));mapping[old]=c.base+len(c.data)
        if old==0x605978:
            c.emit(bytes.fromhex('448954246044895c2464'))
        address=c.base+len(c.data)
        if old in ARRAYS:
            mode,bias=ARRAYS[old];out=bytearray(raw)
            if mode=='base':
                require(raw[0]==0x49 and raw[3]&7==5,'array R13 base changed')
                out[3]=(out[3]&0xf8)|3
            else:
                require(raw[0]==0x42 and raw[3]&0x38==0x28,'array R13 index changed')
                out[3]=(out[3]&0xc7)|0x18
            blob=b'\x49\xbb'+struct.pack('<Q',storage_address+bias)+bytes(out);c.emit(blob)
            arrays.append({'original_rva':old,'emitted_address':address,'original_hex':raw.hex(),
                           'replacement_hex':blob.hex(),'storage_bias':bias})
        elif old in (0x60595B,0x605F1D):
            require(raw[-4:]==struct.pack('<I',0x80),'frame allocation changed')
            blob=raw[:-4]+struct.pack('<I',0x90);c.emit(blob)
            stack.append({'original_rva':old,'original_hex':raw.hex(),'replacement_hex':blob.hex(),'kind':'frame_size'})
        elif old in STACK_SITES:
            blob=_stack_rewrite(raw,STACK_SITES[old]);c.emit(blob)
            stack.append({'original_rva':old,'original_hex':raw.hex(),'replacement_hex':blob.hex(),'kind':'frame_displacement'})
        elif old in (0x605E95,0x605EF1,0x605EA2,0x605EF8):
            blob=bytes.fromhex('8b542460' if old in (0x605E95,0x605EF1) else '6690')
            if old in (0x605EA2,0x605EF8):require(raw==bytes.fromhex('ffca'),'original count decrement changed')
            c.emit(blob);count_patches.append({'original_rva':old,'emitted_address':address,'original_hex':raw.hex(),'replacement_hex':blob.hex()})
        elif old in RELOCATIONS:
            at,target,kind=RELOCATIONS[old]
            require(old+size+struct.unpack_from('<i',raw,at)[0]==target,'source relocation changed')
            dest=getter_code_address if old==0x6059EE else game_base+target
            blob=bytearray(raw);blob[at:at+4]=rel32(address+size,dest);c.emit(bytes(blob))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':kind,
                           'original_target_rva':target,'target_address':dest,
                           'getter_callsite_replaced':old==0x6059EE})
        elif len(raw)==2 and 0x70<=raw[0]<=0x7f:
            target=old+2+struct.unpack('<b',raw[1:])[0]
            c.branch(bytes([0x0f,raw[0]+0x10]),hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif len(raw)==6 and raw[0]==0x0f and 0x80<=raw[1]<=0x8f:
            target=old+6+struct.unpack('<i',raw[2:])[0];c.branch(raw[:2],hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        elif raw[0]==0xeb and len(raw)==2 or raw[0]==0xe9 and len(raw)==5:
            target=old+size+int.from_bytes(raw[1:],'little',signed=True);c.branch(b'\xe9',hex(target))
            relocs.append({'original_rva':old,'emitted_address':address,'kind':'local_branch','original_target_rva':target})
        else:c.emit(raw)
    require(offset==len(source) and len(arrays)==6 and len(stack)==14,'incomplete departure emission')
    for row in relocs:
        if row['kind']=='local_branch':
            require(row['original_target_rva'] in mapping,'branch not on source boundary')
            row['target_address']=mapping[row['original_target_rva']]
    code=c.finish();pointer(code_address,len(code),16,'complete departure code')
    regions=[{'name':'departure code','address':code_address,'size_bytes':len(code)},
             {'name':'departure reject','address':reject_address,'size_bytes':1},
             {'name':'shared getter code','address':getter_code_address,'size_bytes':354},
             {'name':'original roster','address':roster_address,'size_bytes':0x428},
             {'name':'four-array sidecar','address':storage_address,'size_bytes':0x680},
             {'name':'game image','address':game_base,'size_bytes':IMAGE_SIZE}]
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'known departure region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_departure_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'body_address':body_address,
            'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),'roster_address':roster_address,
            'storage_address':storage_address,'storage_size_bytes':0x680,'getter_code_address':getter_code_address,
            'reject_address':reject_address,'known_regions':regions,'array_patches':arrays,'stack_patches':stack,
            'count_patches':count_patches,'relocations':relocs,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},
            'guard_addresses':{k:v for k,v in c.labels.items() if not k.startswith('0x')},
            'reject_reasons':{str(k):v for k,v in REASONS.items()},
            'reject_state':{'rsp':'original entry RSP; arguments and all nonvolatile GPR/XMM restored',
                            'reason':'R10D, 1..10; RAX/R11/flags unspecified',
                            'writes':'56 bytes below entry RSP from scratch saves; no nonstack writes or external calls'},
            'count_policy':{'predictive_notifications':'entry D - unsigned(entry ordinal < entry D)',
                            'tail_player_count':'original current [held S+84h] read; not replaced by prediction',
                            'new_behavior':'pending removal keeps D, including zero; original dense count preserved',
                            'frame_size_bytes':0x90,'remaining_dense_offset':0x60,'entry_ordinal_offset':0x64},
            'entry_or_callsite_patch':None,
            'limits':['Serialized binding S, target identity, map/partition/storage lifetime from entry through all callbacks and subsequent actual roster removal is required; entry guard does not supply or prove it',
                      'No callback rollback, state-change detection or reentrant safety is provided; late rejection cannot undo resource effects',
                      'The prediction is an explicit candidate policy matching later dense-count arithmetic under the stated state contract, not proof of the original notification design',
                      'Only callsite 6059EE uses the shared getter; 606820 is not globally replaced',
                      'All original associated-resource/manager/registration branches and direct/indirect calls are preserved; their runtime resource contracts remain required',
                      'The original tail rereads current D; it equals entry D only under the state-stability contract',
                      'Requires the separately generated v0.11 player-count policy for counts 5..8; zero still clamps to one in 94C9C0 and 60C2A0 has no verified named resources above four',
                      'No executable allocation, code publication, unwind registration, hooks, reject handler, runtime version verification, game execution or multiplayer validation']}


def build_bundle(departure_source:bytes,getter_source:bytes,classify_sources:dict[str,bytes],remove_sources:dict[str,bytes],
                 insert_sources:dict[str,bytes],move_source:bytes,producer_source:bytes,receiver_source:bytes,*,
                 departure_code_address:int,departure_reject_address:int,
                 player_count_context_source:bytes,player_count_filter_source:bytes,
                 player_count_trampoline_address:int,**getter_params)->dict:
    base=getter.build_bundle(getter_source,classify_sources,remove_sources,insert_sources,move_source,producer_source,receiver_source,**getter_params)
    shared=base['shared_binding']
    departure=build(departure_source,**shared,code_address=departure_code_address,
                    getter_code_address=base['getter']['entry_address'],reject_address=departure_reject_address)
    counts=player_count.build(player_count_context_source,player_count_filter_source,
                              game_base=shared['game_base'],trampoline_address=player_count_trampoline_address)
    regions=list(base['known_regions'])+[{'name':'departure code','address':departure_code_address,'size_bytes':departure['size_bytes']},
                                        {'name':'departure reject','address':departure_reject_address,'size_bytes':1},
                                        {'name':'original departure','address':shared['game_base']+ENTRY,'size_bytes':END-ENTRY},
                                        {'name':'player-count trampoline','address':counts['entry_address'],'size_bytes':counts['size_bytes']}]
    for name,(start,end,_) in player_count.SPECS.items():
        regions.append({'name':'original player-count '+name,'address':shared['game_base']+start,'size_bytes':end-start})
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'departure bundle region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_departure_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'departure':departure,
            'player_count':counts,'known_regions':regions,'limits':base['limits']+departure['limits']+counts['limits']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','getter-evidence','classify-evidence','remove-evidence','insert-evidence','move-evidence','producer-evidence','receiver-evidence','player-count-evidence','context-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    counts=player_count.load_sources(args.player_count_evidence,args.context_evidence)
    result=build_bundle(load_source(args.evidence),getter.load_source(args.getter_evidence),
                        getter.classify.load_sources(args.classify_evidence),remove.load_sources(args.remove_evidence),
                        remove.insert.load_sources(args.insert_evidence),move.load_source(args.move_evidence),
                        remove.insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        remove.insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),
                        player_count_context_source=counts['context'],player_count_filter_source=counts['filter'],
                        **json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'departure_size_bytes':result['departure']['size_bytes']}))


if __name__=='__main__':main()
