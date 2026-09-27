"""Emit four fixed native roster insertion candidates as offline byte artifacts.

No process access, executable allocation, hook, unwind or host-native execution.
R11 is locally dead in all four original bodies and redefined by map insertion.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import struct
from pathlib import Path


def _module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


base_bundle=_module('roster_bundle')
move=base_bundle.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
TARGET_PROFILE=dict(move.TARGET_PROFILE)
EVIDENCE_SHA256='794c357a56b2aa28cfd1061374afe27c1a3a2c06d31ce4ca736e4b783e41b497'
GLOBAL_RVA=0x3326468
MAP_RVA,MAP_SIZE=0x172F790,110
sha=lambda b:hashlib.sha256(b).hexdigest()
SPECS={'dense_legacy': {'entry': 6343296,
                  'end': 6343583,
                  'sha256': '974935cec813b3ce3f8d62cff1c7f46b17bb306f5bce020e8dde6fdccfc01e4f',
                  'lengths': (5,
                              1,
                              4,
                              7,
                              3,
                              6,
                              2,
                              3,
                              2,
                              11,
                              4,
                              6,
                              2,
                              7,
                              3,
                              2,
                              2,
                              3,
                              5,
                              7,
                              3,
                              4,
                              6,
                              3,
                              4,
                              8,
                              8,
                              8,
                              8,
                              8,
                              8,
                              8,
                              2,
                              3,
                              2,
                              3,
                              4,
                              3,
                              8,
                              8,
                              8,
                              8,
                              8,
                              8,
                              6,
                              6,
                              6,
                              3,
                              4,
                              3,
                              7,
                              8,
                              3,
                              5,
                              4,
                              1,
                              5),
                  'arrays': ((105, 'primary', 4),
                             (113, 'primary', 4),
                             (121, 'primary', 4),
                             (129, 'primary', 4),
                             (137, 'primary', 4),
                             (145, 'primary', 4),
                             (153, 'primary', 4),
                             (178, 'auxiliary', 4),
                             (186, 'auxiliary', 4),
                             (194, 'auxiliary', 4),
                             (202, 'auxiliary', 4),
                             (210, 'auxiliary', 4),
                             (218, 'auxiliary', 3),
                             (261, 'pointer', 4)),
                  'capacity_cmp': 28,
                  'dense': True},
 'append_legacy': {'entry': 6343584,
                   'end': 6343787,
                   'sha256': '57a8d7f5d1dbb83f3a9a80918f740ce2065dfc1ac09b10952189b3693a7132c8',
                   'lengths': (2,
                               4,
                               7,
                               3,
                               7,
                               4,
                               3,
                               2,
                               8,
                               7,
                               3,
                               3,
                               4,
                               3,
                               8,
                               8,
                               8,
                               8,
                               8,
                               8,
                               8,
                               4,
                               8,
                               8,
                               8,
                               8,
                               8,
                               8,
                               8,
                               7,
                               3,
                               5,
                               6,
                               4,
                               1,
                               1),
                   'arrays': ((60, 'primary', 4),
                              (68, 'primary', 4),
                              (76, 'primary', 4),
                              (84, 'primary', 4),
                              (92, 'primary', 4),
                              (100, 'primary', 4),
                              (108, 'primary', 4),
                              (120, 'auxiliary', 4),
                              (128, 'auxiliary', 4),
                              (136, 'auxiliary', 4),
                              (144, 'auxiliary', 4),
                              (152, 'auxiliary', 3),
                              (160, 'auxiliary', 4),
                              (168, 'pointer', 4)),
                   'capacity_cmp': 27,
                   'dense': False},
 'append_registered': {'entry': 5507152,
                       'end': 5507358,
                       'sha256': '1264c1c0bf558d390f7dd2bdf075e3f6b3b2465fbfbac5575d6eea8a6ea6d6c0',
                       'lengths': (2,
                                   4,
                                   7,
                                   3,
                                   3,
                                   7,
                                   4,
                                   3,
                                   2,
                                   8,
                                   7,
                                   3,
                                   3,
                                   4,
                                   3,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   4,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   8,
                                   7,
                                   3,
                                   5,
                                   6,
                                   4,
                                   1,
                                   1),
                       'arrays': ((63, 'primary', 4),
                                  (71, 'primary', 4),
                                  (79, 'primary', 4),
                                  (87, 'primary', 4),
                                  (95, 'primary', 4),
                                  (103, 'primary', 4),
                                  (111, 'primary', 4),
                                  (123, 'auxiliary', 4),
                                  (131, 'auxiliary', 4),
                                  (139, 'auxiliary', 4),
                                  (147, 'auxiliary', 4),
                                  (155, 'auxiliary', 3),
                                  (163, 'auxiliary', 4),
                                  (171, 'pointer', 4)),
                       'capacity_cmp': 30,
                       'dense': False},
 'dense_registered': {'entry': 5507360,
                      'end': 5507646,
                      'sha256': '197e6d093ec081d304e0642ffee3e7fc3a71b2eadb36f3a0805d4927af7a5196',
                      'lengths': (5,
                                  1,
                                  4,
                                  7,
                                  3,
                                  6,
                                  2,
                                  3,
                                  2,
                                  11,
                                  3,
                                  6,
                                  2,
                                  7,
                                  3,
                                  2,
                                  2,
                                  3,
                                  5,
                                  7,
                                  3,
                                  4,
                                  6,
                                  3,
                                  4,
                                  8,
                                  8,
                                  8,
                                  8,
                                  8,
                                  8,
                                  8,
                                  2,
                                  3,
                                  2,
                                  3,
                                  4,
                                  3,
                                  8,
                                  8,
                                  8,
                                  8,
                                  8,
                                  8,
                                  6,
                                  6,
                                  6,
                                  3,
                                  4,
                                  3,
                                  7,
                                  8,
                                  3,
                                  5,
                                  4,
                                  1,
                                  5),
                      'arrays': ((104, 'primary', 4),
                                 (112, 'primary', 4),
                                 (120, 'primary', 4),
                                 (128, 'primary', 4),
                                 (136, 'primary', 4),
                                 (144, 'primary', 4),
                                 (152, 'primary', 4),
                                 (177, 'auxiliary', 4),
                                 (185, 'auxiliary', 4),
                                 (193, 'auxiliary', 4),
                                 (201, 'auxiliary', 4),
                                 (209, 'auxiliary', 4),
                                 (217, 'auxiliary', 3),
                                 (260, 'pointer', 4)),
                      'capacity_cmp': 28,
                       'dense': True}}


def load_sources(evidence_path: Path) -> dict[str, bytes]:
    raw=Path(evidence_path).read_bytes()
    require(sha(raw)==EVIDENCE_SHA256,'insertion evidence fingerprint mismatch')
    evidence=json.loads(raw)
    result={}
    for name,spec in SPECS.items():
        rows=evidence['inserts'][hex(spec['entry'])]['instructions']
        cursor=spec['entry'];parts=[]
        for row in rows:
            blob=bytes.fromhex(row['bytes'])
            require(int(row['rva'],16)==cursor and sha(blob)==row['sha256'],'insertion instruction mismatch')
            parts.append(blob);cursor+=len(blob)
        body=b''.join(parts)
        require(cursor==spec['end'] and sha(body)==spec['sha256'],'insertion body fingerprint mismatch')
        result[name]=body
    return result


def _array_instruction(raw: bytes, group: str, disp_offset: int) -> bytes:
    """Replace RBX by R11 in the single fixed SIB memory operand."""
    blob=bytearray(raw);sib=blob[disp_offset-1]
    bit=1 if group=='pointer' else 2
    require((sib&7 if bit==1 else (sib>>3)&7)==3,'array SIB no longer uses RBX')
    value=struct.unpack_from('<i',blob,disp_offset)[0]
    value+={'pointer':0,'primary':0x20,'auxiliary':0x1E0}[group]
    blob[disp_offset:disp_offset+4]=struct.pack('<i',value)
    if 0x40<=blob[0]<=0x4F:
        require(not blob[0]&bit,'array REX extension already present');blob[0]|=bit
    else:blob[:0]=bytes([0x40|bit])
    return bytes(blob)


def build(source: bytes, *, kind: str, game_base: int, code_address: int,
          roster_address: int, storage_address: int, move_code_address: int,
          reject_address: int) -> dict:
    require(kind in SPECS,'unknown insertion kind');spec=SPECS[kind]
    require(type(source)is bytes and len(source)==spec['end']-spec['entry'] and sha(source)==spec['sha256'],
            'insertion source fingerprint mismatch')
    pointer(game_base,GLOBAL_RVA+8,0x1000,'game_base')
    pointer(code_address,1,16,'code_address');pointer(roster_address,0x428,8,'roster_address')
    pointer(storage_address,0x680,16,'storage_address')
    require(storage_address>=0xE8,'storage cannot encode bias')
    pointer(move_code_address,545,16,'move_code_address');pointer(reject_address,1,1,'reject_address')
    # Guard precedes the original prologue. Only RAX/R10/R11/flags change.
    prefix=bytearray();labels={};fixups=[]
    def emit(b):prefix.extend(b)
    def jump(op,label):
        emit(op);fixups.append((len(prefix),label));emit(b'\0'*4)
    emit(b'\x49\xbb'+struct.pack('<Q',game_base+GLOBAL_RVA))
    emit(b'\x4d\x8b\x1b')                         # R11=actual global S
    emit(b'\x48\xb8'+struct.pack('<Q',roster_address))
    emit(b'\x49\x3b\xc3');jump(b'\x0f\x85','binding')
    emit(b'\x41\x8b\x83\x80\0\0\0')            # EAX=T
    emit(b'\x83\xf8\x08');jump(b'\x0f\x83','capacity')
    emit(b'\x45\x8b\x93\x84\0\0\0')            # R10D=D
    emit(b'\x44\x3b\xd0');jump(b'\x0f\x87','counts') # D>T
    if spec['dense']:jump(b'\x0f\x85','pending')      # D!=T
    emit(b'\x41\x8b\x83\x88\0\0\0')            # EAX=P
    emit(b'\x41\x3b\xc2');jump(b'\x0f\x87','counts') # P>D
    jump(b'\xe9','body')
    for label,reason in (('binding',1),('capacity',2),('counts',3),('pending',4)):
        labels[label]=code_address+len(prefix)
        emit(b'\x41\xba'+struct.pack('<I',reason));jump(b'\xe9',reject_address)
    prefix.extend(b'\xcc'*((-len(prefix))%16));labels['body']=code_address+len(prefix)
    for off,target in fixups:
        target=labels[target]if isinstance(target,str)else target
        prefix[off:off+4]=rel32(code_address+off+4,target)

    # Relocate whole instructions. Local branches land before injected loads.
    patches={off:(group,disp)for off,group,disp in spec['arrays']}
    offset=0;pieces=[];mapping={};relocations=[];array_rows=[]
    for size in spec['lengths']:
        old=spec['entry']+offset;raw=source[offset:offset+size]
        address=code_address+len(prefix)+sum(len(p['blob'])for p in pieces)
        mapping[old]=address;blob=raw;target=None;disp_at=None;reason=None
        if offset in patches:
            group,disp=patches[offset]
            blob=b'\x49\xbb'+struct.pack('<Q',storage_address-0xE8)+_array_instruction(raw,group,disp)
            array_rows.append({'original_rva':old,'group':group,'emitted_address':address,'original_hex':raw.hex(),'replacement_hex':blob.hex()})
        elif offset==spec['capacity_cmp']:
            require(raw==b'\x83\xf8\x04','capacity comparison changed');blob=b'\x83\xf8\x08'
        elif len(raw)==2 and 0x70<=raw[0]<=0x7F:
            target=old+2+struct.unpack('<b',raw[1:])[0]
            blob=bytes([0x0F,raw[0]+0x10])+b'\0'*4;disp_at=2;reason='local_conditional'
        elif len(raw)==2 and raw[0]==0xEB:
            target=old+2+struct.unpack('<b',raw[1:])[0];blob=b'\xe9'+b'\0'*4;disp_at=1;reason='local_jump'
        elif len(raw)==5 and raw[0]in (0xE8,0xE9):
            target=old+5+struct.unpack('<i',raw[1:])[0];disp_at=1;reason='external_branch'
            require(target in (0x60C410,MAP_RVA),'unexpected direct target')
        elif raw[:3]==b'\x48\x8b\x1d':
            target=old+7+struct.unpack('<i',raw[3:])[0];disp_at=3;reason='global_read'
            require(target==GLOBAL_RVA,'global target changed')
        pieces.append({'rva':old,'address':address,'blob':blob,'target':target,'disp':disp_at,'reason':reason})
        offset+=size
    require(offset==len(source) and len(array_rows)==14,'incomplete insertion rewrite')
    for piece in pieces:
        if piece['target']is None:continue
        t=piece['target'];reason=piece['reason']
        if reason.startswith('local'):
            require(t in mapping,'branch not an original instruction boundary');destination=mapping[t]
        else:destination=move_code_address if t==0x60C410 else game_base+t
        b=bytearray(piece['blob']);at=piece['disp']
        b[at:at+4]=rel32(piece['address']+len(b),destination);piece['blob']=bytes(b)
        relocations.append({'original_rva':piece['rva'],'emitted_address':piece['address'],'kind':reason,
                            'original_target_rva':t,'target_address':destination})
    code=bytes(prefix)+b''.join(p['blob']for p in pieces)
    pointer(code_address,len(code),16,'complete code')
    regions=[{'name':'insertion code','address':code_address,'size_bytes':len(code)},
             {'name':'original roster','address':roster_address,'size_bytes':0x428},
             {'name':'four-array sidecar','address':storage_address,'size_bytes':0x680},
             {'name':'insertion rejection entry','address':reject_address,'size_bytes':1},
             {'name':'mover code','address':move_code_address,'size_bytes':545},
             {'name':'roster global','address':game_base+GLOBAL_RVA,'size_bytes':8},
             {'name':'map insertion helper','address':game_base+MAP_RVA,'size_bytes':MAP_SIZE}]
    regions.extend({'name':'original '+n,'address':game_base+s['entry'],'size_bytes':s['end']-s['entry']}for n,s in SPECS.items())
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                    'known region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_insert_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'kind':kind,'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'size_bytes':len(code),
            'code_hex':code.hex(),'code_sha256':sha(code),'body_address':labels['body'],
            'roster_address':roster_address,'storage_address':storage_address,'storage_size_bytes':0x680,
            'move_code_address':move_code_address,'reject_address':reject_address,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},'array_patches':array_rows,'relocations':relocations,
            'known_regions':regions,'reject_reasons':{'1':'global_roster_binding_mismatch','2':'tracked_count_not_below_8',
                                                      '3':'prefix_dense_tracked_order_invalid','4':'dense_insert_with_pending_tail'},
            'reject_state':{'rsp':'unchanged entry RSP, no prologue or memory writes',
                            'preserved':'RCX/RDX/R8/R9, all nonvolatile GPR/XMM',
                            'clobbered':'RAX, R10(reason), R11(actual global S), flags'},
            'entry_or_callsite_patch':None,
            'limits':['Valid writable sidecar, entity/flag pointers and synchronized global/count/map state required',
                      'Map must have a valid new key and empty slot; original helper does not reject duplicates or full maps safely',
                      'Dense insertion requires D==T here; actual caller guarantee or pending-hole protocol remains unproven',
                      'Property initialization remains a subsequent producer/receiver operation; false dense flag preserves primary bytes',
                      'Mover binding/sidecar must match and its valid source/map preconditions must hold',
                      'No initialization/publication/lifetime, rejection handler, Windows unwind, hook or multiplayer validation']}


def build_bundle(insert_sources: dict[str, bytes], move_source: bytes, producer_source: bytes, receiver_source: bytes,
                 *, insert_code_addresses: dict[str,int], insert_reject_addresses: dict[str,int], **base_params) -> dict:
    require(set(insert_sources)==set(insert_code_addresses)==set(insert_reject_addresses)==set(SPECS),'incomplete insertion bundle')
    base=base_bundle.build(move_source,producer_source,receiver_source,**base_params)
    shared=base['shared_binding'];inserts={}
    for name in SPECS:
        inserts[name]=build(insert_sources[name],kind=name,**shared,code_address=insert_code_addresses[name],
                            reject_address=insert_reject_addresses[name],move_code_address=base['move']['code_address'])
    regions=list(base['known_regions'])
    regions.append({'name':'map insertion helper','address':shared['game_base']+MAP_RVA,'size_bytes':MAP_SIZE})
    for name,a in inserts.items():
        for label,address,size in [('code',a['code_address'],a['size_bytes']),('reject',a['reject_address'],1),
                                   ('original',shared['game_base']+SPECS[name]['entry'],SPECS[name]['end']-SPECS[name]['entry'])]:
            regions.append({'name':name+' '+label,'address':address,'size_bytes':size})
    for i,a in enumerate(regions):
        for b in regions[i+1:]:
            require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                    'insert bundle region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_insert_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'inserts':inserts,
            'known_regions':regions,'limits':base['limits']+['Insertion caller contracts, pending-tail handling, full lifecycle and real mission tests remain incomplete']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('evidence','move-evidence','producer-evidence','receiver-evidence','addresses','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    params=json.loads(args.addresses.read_bytes())
    result=build_bundle(load_sources(args.evidence),move.load_source(args.move_evidence),
                         base_bundle.pair.producer.load_source(args.producer_evidence),
                         base_bundle.pair.receiver.load_source(args.receiver_evidence),**params)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],
                      'insert_sizes':{k:v['size_bytes']for k,v in result['inserts'].items()}}))


if __name__=='__main__':main()
