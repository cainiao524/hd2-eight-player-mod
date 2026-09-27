"""Emit offline roster removals with membership guards and pending-tail repair.

The repair is new candidate behavior: after a dense erase it fills the new
pending boundary from the old tracked tail. It is not present in the original.
No process access, executable allocation, hooks or host-native execution.
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
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


insert=_module('roster_insert');move=insert.move
require,pointer,rel32,overlaps=move.require,move.pointer,move.rel32,move.overlaps
TARGET_PROFILE=dict(move.TARGET_PROFILE)
EVIDENCE_SHA256='67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af'
GLOBAL_RVA=0x3326468
DELETE_RVA,DELETE_SIZE=0x172F8A0,259
DELETE_SHA256='d58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f'
sha=lambda b:hashlib.sha256(b).hexdigest()
SPECS={
 'legacy':{'entry':0x60CEA0,'end':0x60CF4C,
  'sha256':'0c6e7607bf93a1e9fba1b8eeba998053b316670295e7d8db432352b3ce49cc7d',
  'lengths':(5,1,4,7,3,3,7,5,7,3,2,3,2,6,7,3,2,3,2,8,4,2,7,6,2,3,3,5,7,6,2,6,3,7,3,2,3,5,2,5,4,1,1),
  'array_read':0x60CEEB,'dense_test':0x60CF32,'finish':0x60CF3F,'s_register':'rdi'},
 'registered':{'entry':0x540A40,'end':0x540AE0,
  'sha256':'35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8',
  'lengths':(2,4,3,7,7,5,7,2,3,2,6,7,3,2,3,2,8,4,2,7,6,2,3,3,5,7,6,2,6,3,7,3,2,3,4,1,5,4,1,1),
  'array_read':0x540A81,'dense_test':0x540AC8,'finish':0x540ADA,'s_register':'rbx'},
}
REASONS={1:'global_roster_binding_mismatch',2:'tracked_count_zero_or_above_8',
         3:'prefix_dense_tracked_order_invalid',4:'map_capacity_not_8',
         5:'requested_id_missing_or_sentinel',6:'map_ordinal_outside_tracked_range',
         7:'target_prefix_flag_disagrees_with_partition',8:'target_record_id_disagrees_with_map'}


class _Code:
    def __init__(self,base):self.base=base;self.data=bytearray();self.labels={};self.fixups=[]
    def emit(self,blob):self.data.extend(blob)
    def label(self,name):self.labels[name]=self.base+len(self.data)
    def branch(self,opcode,target):
        self.emit(opcode);self.fixups.append((len(self.data),target));self.emit(b'\0'*4)
    def finish(self):
        for off,target in self.fixups:
            dest=self.labels[target]if isinstance(target,str)else target
            self.data[off:off+4]=rel32(self.base+off+4,dest)
        return bytes(self.data)


def load_sources(evidence_path:Path)->dict[str,bytes]:
    raw=Path(evidence_path).read_bytes();require(sha(raw)==EVIDENCE_SHA256,'removal evidence fingerprint mismatch')
    evidence=json.loads(raw);result={}
    for kind,spec in SPECS.items():
        body=evidence['bodies'][hex(spec['entry'])];blob=bytes.fromhex(body['bytes_hex'])
        require(len(blob)==spec['end']-spec['entry'] and sha(blob)==spec['sha256'],'removal body fingerprint mismatch')
        result[kind]=blob
    helper=bytes.fromhex(evidence['bodies'][hex(DELETE_RVA)]['bytes_hex'])
    require(len(helper)==DELETE_SIZE and sha(helper)==DELETE_SHA256,'map deletion body fingerprint mismatch')
    return result


def _preflight(kind,game_base,code_address,roster_address,storage_address,reject_address):
    c=_Code(code_address)
    # Save every argument and the three nonvolatiles used by the bounded lookup.
    # There are no calls here. Scratch stack writes are not claimed absent.
    c.emit(bytes.fromhex('515241504151535657'))
    c.emit(bytes.fromhex('488bf2'if kind=='legacy'else'488bf1')) # RSI=input entity
    c.emit(b'\x48\xb8'+struct.pack('<Q',game_base+GLOBAL_RVA));c.emit(bytes.fromhex('488b38'))
    c.emit(b'\x48\xb8'+struct.pack('<Q',roster_address));c.emit(bytes.fromhex('483bf8'))
    c.branch(b'\x0f\x85','reject1')
    c.emit(bytes.fromhex('8b9f8000000085db'));c.branch(b'\x0f\x84','reject2')
    c.emit(bytes.fromhex('83fb08'));c.branch(b'\x0f\x87','reject2')
    c.emit(bytes.fromhex('8b87840000003bc3'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('8b8f880000003bc8'));c.branch(b'\x0f\x87','reject3')
    c.emit(bytes.fromhex('448b8fd80000004183f908'));c.branch(b'\x0f\x85','reject4')
    c.emit(bytes.fromhex('4c8b87d00000008b56083b97dc000000'));c.branch(b'\x0f\x84','reject5')
    c.emit(bytes.fromhex('8bc20faf87e000000083e00733c9'))
    c.label('lookup')
    c.emit(bytes.fromhex('413b14c0'));c.branch(b'\x0f\x84','found')
    c.emit(bytes.fromhex('458b1cc0443b9fdc000000'));c.branch(b'\x0f\x84','reject5')
    c.emit(bytes.fromhex('ffc083e007ffc183f908'));c.branch(b'\x0f\x82','lookup')
    c.branch(b'\xe9','reject5')
    c.label('found')
    c.emit(bytes.fromhex('418b5cc0043b9f80000000'));c.branch(b'\x0f\x83','reject6')
    c.emit(b'\x49\xbb'+struct.pack('<Q',storage_address))
    c.emit(bytes.fromhex('4d8b1cdb413b5308'));c.branch(b'\x0f\x85','reject8')
    c.emit(bytes.fromhex('3b9f84000000'));c.branch(b'\x0f\x83','accepted')
    c.emit(bytes.fromhex('3b9f880000000f92c0410fb64b1483e1013ac1'))
    c.branch(b'\x0f\x85','reject7')
    restore=bytes.fromhex('5f5e5b415941585a59')
    c.label('accepted');c.emit(restore);c.branch(b'\xe9','body')
    for reason in REASONS:
        c.label('reject'+str(reason));c.emit(restore)
        c.emit(b'\x41\xba'+struct.pack('<I',reason));c.branch(b'\xe9',reject_address)
    c.emit(b'\xcc'*((-len(c.data))%16));c.label('body')
    return c.finish(),c.labels


def build(source:bytes,*,kind:str,game_base:int,code_address:int,roster_address:int,
          storage_address:int,move_code_address:int,reject_address:int)->dict:
    require(kind in SPECS,'unknown removal kind');spec=SPECS[kind]
    require(type(source)is bytes and len(source)==spec['end']-spec['entry'] and sha(source)==spec['sha256'],
            'removal source fingerprint mismatch')
    pointer(game_base,GLOBAL_RVA+8,0x1000,'game_base');pointer(code_address,1,16,'code_address')
    pointer(roster_address,0x428,8,'roster_address');pointer(storage_address,0x680,16,'storage_address')
    require(storage_address>=0xE8,'storage cannot encode bias')
    pointer(move_code_address,545,16,'move_code_address');pointer(reject_address,1,1,'reject_address')
    prefix,labels=_preflight(kind,game_base,code_address,roster_address,storage_address,reject_address)
    pieces=[];mapping={};offset=0;cursor=code_address+len(prefix);array_patch=None
    for size in spec['lengths']:
        old=spec['entry']+offset;raw=source[offset:offset+size];mapping[old]=cursor
        blob=raw;target=None;disp=None;reason=None
        if old==spec['dense_test']:
            require(raw==bytes.fromhex('4585c0'),'dense completion test changed')
            blob=b'\xe9'+b'\0'*4;target='dense_completion';disp=1;reason='new_dense_completion'
        elif old==spec['array_read']:
            require(raw[:3]==bytes.fromhex('488b8c')and raw[4:]==bytes.fromhex('e8000000'),'target pointer read changed')
            patched=bytearray(raw);patched[0]|=1;patched[3]=(patched[3]&0xF8)|3
            blob=b'\x49\xbb'+struct.pack('<Q',storage_address-0xE8)+bytes(patched)
            array_patch={'original_rva':old,'emitted_address':cursor,'original_hex':raw.hex(),'replacement_hex':blob.hex()}
        elif len(raw)==2 and 0x70<=raw[0]<=0x7F:
            target=old+2+struct.unpack('<b',raw[1:])[0];blob=bytes([0x0F,raw[0]+0x10])+b'\0'*4;disp=2;reason='local_branch'
        elif len(raw)==2 and raw[0]==0xEB:
            target=old+2+struct.unpack('<b',raw[1:])[0];blob=b'\xe9'+b'\0'*4;disp=1;reason='local_branch'
        elif len(raw)==5 and raw[0]in(0xE8,0xE9):
            target=old+5+struct.unpack('<i',raw[1:])[0];disp=1;reason='external_branch'
            require(target in(DELETE_RVA,0x60C410),'unexpected removal direct target')
        elif len(raw)==7 and raw[:3]in(bytes.fromhex('488b3d'),bytes.fromhex('488b1d')):
            target=old+7+struct.unpack('<i',raw[3:])[0];disp=3;reason='global_read'
            require(target==GLOBAL_RVA,'removal global changed')
        pieces.append({'rva':old,'address':cursor,'blob':blob,'target':target,'disp':disp,'reason':reason})
        cursor+=len(blob);offset+=size
    require(offset==len(source)and array_patch is not None,'incomplete removal relocation')
    # Dense erasure preserves the original prefix/dense moves, then restores
    # the pending partition. The original pending branch still uses its own
    # call/tail path. Keep the original dense return RAX across the extra move.
    dense=_Code(cursor);dense.label('dense_completion')
    dense.emit(bytes.fromhex('4585c0'));dense.branch(b'\x0f\x84','repair')
    set_rcx=bytes.fromhex('488bcf'if kind=='legacy'else'488bcb')
    dense.emit(set_rcx);dense.branch(b'\xe8',move_code_address)
    dense.label('repair')
    dense.emit(bytes.fromhex('8b9784000000448b8780000000'if kind=='legacy'else'8b9384000000448b8380000000'))
    dense.emit(bytes.fromhex('413bd0'));dense.branch(b'\x0f\x83',mapping[spec['finish']])
    dense.emit(bytes.fromhex('504883ec28'));dense.emit(set_rcx)
    dense.branch(b'\xe8',move_code_address)
    dense.emit(bytes.fromhex('4883c42858'));dense.branch(b'\xe9',mapping[spec['finish']])
    dense_code=dense.finish();relocations=[]
    for p in pieces:
        if p['target']is None:continue
        t=p['target']
        if t=='dense_completion':dest=dense.labels[t]
        elif p['reason']=='local_branch':
            require(t in mapping,'branch is not an original instruction boundary');dest=mapping[t]
        else:dest=move_code_address if t==0x60C410 else game_base+t
        blob=bytearray(p['blob']);at=p['disp'];blob[at:at+4]=rel32(p['address']+len(blob),dest);p['blob']=bytes(blob)
        relocations.append({'original_rva':p['rva'],'emitted_address':p['address'],'kind':p['reason'],
                            'original_target_rva':t,'target_address':dest})
    code=prefix+b''.join(p['blob']for p in pieces)+dense_code
    pointer(code_address,len(code),16,'complete removal code')
    regions=[{'name':'removal code','address':code_address,'size_bytes':len(code)},
             {'name':'removal reject','address':reject_address,'size_bytes':1},
             {'name':'original roster','address':roster_address,'size_bytes':0x428},
             {'name':'four-array sidecar','address':storage_address,'size_bytes':0x680},
             {'name':'mover code','address':move_code_address,'size_bytes':545},
             {'name':'roster global','address':game_base+GLOBAL_RVA,'size_bytes':8},
             {'name':'map deletion helper','address':game_base+DELETE_RVA,'size_bytes':DELETE_SIZE}]
    regions.extend({'name':'original '+k,'address':game_base+s['entry'],'size_bytes':s['end']-s['entry']}for k,s in SPECS.items())
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'known removal region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_remove_candidate','installable':False,'game_execution':False,'multiplayer_verified':False,
            'kind':kind,'target_profile':dict(TARGET_PROFILE),'source_sha256':sha(source),'evidence_sha256':EVIDENCE_SHA256,
            'game_base':game_base,'code_address':code_address,'entry_address':code_address,'body_address':labels['body'],
            'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),
            'roster_address':roster_address,'storage_address':storage_address,'storage_size_bytes':0x680,
            'move_code_address':move_code_address,'reject_address':reject_address,'known_regions':regions,
            'instruction_address_map':{hex(k):v for k,v in mapping.items()},'array_patch':array_patch,'relocations':relocations,
            'dense_completion_address':dense.labels['dense_completion'],'dense_repair_check_address':dense.labels['repair'],
            'new_behavior':'After dense removal, if newD<newT, copy old tracked tail at newT to new pending start newD and update its map entry',
            'reject_reasons':{str(k):v for k,v in REASONS.items()},
            'reject_state':{'rsp':'entry RSP after restoring seven saved registers',
                            'preserved':'RCX/RDX/R8/R9 and all nonvolatile GPR/XMM',
                            'clobbered':'RAX, R10(reason), R11, flags',
                            'writes':'56 bytes of scratch stack; no roster/sidecar/map/entity mutation'},
            'entry_or_callsite_patch':None,
            'limits':['Valid mapped entity/record/map pointers and synchronized global/count/record/map state are required',
                      'Eight-bucket map must have unique valid keys, correct probe chains, and a bijection with tracked records',
                      'All dense record prefix flags must agree with the P partition; preflight checks the removal target only',
                      'Additional dense-pending repair is candidate semantics; complete external ownership/aliases/caller contracts remain unproven',
                      'Physical bytes beyond new tracked count remain as in the original copy-based lifecycle; this is not resource release',
                      'No allocation/publication/cleanup, rejection handler, Windows unwind, hook or multiplayer validation']}


def build_bundle(remove_sources:dict[str,bytes],insert_sources:dict[str,bytes],move_source:bytes,
                 producer_source:bytes,receiver_source:bytes,*,remove_code_addresses:dict[str,int],
                 remove_reject_addresses:dict[str,int],**insert_params)->dict:
    require(set(remove_sources)==set(remove_code_addresses)==set(remove_reject_addresses)==set(SPECS),'incomplete removal bundle')
    base=insert.build_bundle(insert_sources,move_source,producer_source,receiver_source,**insert_params)
    shared=base['shared_binding'];removes={}
    for kind in SPECS:
        removes[kind]=build(remove_sources[kind],kind=kind,**shared,code_address=remove_code_addresses[kind],
                            reject_address=remove_reject_addresses[kind],move_code_address=base['base_bundle']['move']['code_address'])
    regions=list(base['known_regions'])
    regions.append({'name':'map deletion helper','address':shared['game_base']+DELETE_RVA,'size_bytes':DELETE_SIZE})
    for kind,a in removes.items():
        for label,address,size in [('code',a['code_address'],a['size_bytes']),('reject',a['reject_address'],1),
                                   ('original',shared['game_base']+SPECS[kind]['entry'],SPECS[kind]['end']-SPECS[kind]['entry'])]:
            regions.append({'name':'remove '+kind+' '+label,'address':address,'size_bytes':size})
    for i,a in enumerate(regions):
        for b in regions[i+1:]:require(not overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),
                                      'removal bundle region overlap: '+a['name']+' / '+b['name'])
    return {'status':'offline_native_roster_remove_bundle','installable':False,'game_execution':False,'multiplayer_verified':False,
            'target_profile':dict(TARGET_PROFILE),'shared_binding':shared,'base_bundle':base,'removes':removes,'known_regions':regions,
            'limits':base['limits']+['Full removal partitions are implemented with new pending-tail repair; real caller/ownership and full lifecycle integration remain unverified']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in('evidence','insert-evidence','move-evidence','producer-evidence','receiver-evidence','addresses','output'):
        p.add_argument('--'+name,required=True,type=Path)
    args=p.parse_args();require(not args.output.exists(),'refusing to overwrite output')
    result=build_bundle(load_sources(args.evidence),insert.load_sources(args.insert_evidence),move.load_source(args.move_evidence),
                        insert.base_bundle.pair.producer.load_source(args.producer_evidence),
                        insert.base_bundle.pair.receiver.load_source(args.receiver_evidence),**json.loads(args.addresses.read_bytes()))
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.output),'status':result['status'],'remove_sizes':{k:v['size_bytes']for k,v in result['removes'].items()}}))


if __name__=='__main__':main()
