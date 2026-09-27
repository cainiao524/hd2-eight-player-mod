"""Offline rank-ID purpose/lookup evidence from fixed code and local dictionaries.

No process access, new capture, game patch, network or package installation.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image,EXPECTED,require,row

FUNCTIONS={
 0x142D870:(0x142EE66,'af2fe66540aa39708e295346aaf1b7d32bddbb3fe8612666011f4955a766d533'),
 0x12556E0:(0x125576A,'6673f0100c9f49e7c45aede2810d4e9605560c7bce608593916decc2aae1ad30'),
 0x1255800:(0x1255882,'50beb89aef84e227597d4018021c44dc6f97f463d9aa2b7e417d0e774999b5da'),
 0x1327F50:(0x1327FBB,'bbfd22df1596db8d92c262b0a4a063266e73ccb323b204905e7bc7cb86d791f3'),
 0x1327FE0:(0x1328046,'cabf99657bb29115e1c77e4e887f22248a1b96b056868f0ac587e7358ee6c298'),
 0x4EDA90:(0x4EDD85,'a0da94ec3550578975fcd14e9065d91f8d695432bd736e473d279bf32152b5bd'),
 0xFC5550:(0xFC56B6,'695eb13263114cec43d2d432e2553dbcf6e340169cc4fa0d7329a83b5e1d16d3'),
 0xFC4C50:(0xFC51C8,'75126d1def67e5e32ce93402ebec2c67556995cdd75fc9709d20590e8ad6c050'),
 0xAAFF30:(0xAB0048,'dd8fc0a2804bddb59871343b89cf4bbee983049964ae274eb18ed73a14080325'),
}
FILES={
 'FileDiver/stingray/hash.go':'3206b6f98f75401266f6ce374a5b41c1fa8e491d36e6b8c606df48d7b369cbd5',
 'FileDiver/stingray/hash_test.go':'4c0b4b7b619b579264880880aaee0caca90769fef61e6697a48032d3f2cde9b1',
 'FileDiver/hashes/thinhashes.txt':'a0bdca1e94555551c825f067f718dba98454a14a7752318d5a26a34be44f5fb5',
 'FileDiver/hashes/hashes.txt':'a9ee27bff4766c07d92a713667e467fc6c6449b49ad5cad66896d2bc4a5cb63b',
 'FileDiver/hashes/material_textures.txt':'95ef723c7a398a67399e8bafed12f13783eaafc859fe0ae9662cc930f812d4df',
 'FileDiver/hashes/cracked.txt':'66b15ea115e1088ee9a72c5a6246560a19aa813a38651dd9cdf296efea22b7ca',
}
ASSET_SHA='3b34c46a17f0aa1003a30cf23a6010c5f08fddcfc5ab9a9020ffd2ef06091557'
MANIFEST_SHA='2f172470d8c13495536e3844b8a51b46821e5f393185cd51f2f363721a03ef01'
TABLES={
 'movement_on_event':dict(base='rbp-0x70',init=[0x142EB1E,0x142EB25,0x142EB2C],
                         values=[0x2E1387C5,0xED9E2BBD,0x30E087B2],read=0x142ED37,local=0x07A65DB2),
 'movement_off_event':dict(base='rbp-0x50',init=[0x142EB33,0x142EB3A,0x142EB41],
                          values=[0x56D7E815,0xCE12B5A6,0xD2D33C0C],read=0x142ED3B,local=0x11D0ACB1),
 'movement_float_parameter':dict(base='rbp-0x80',init=[0x142EB48,0x142EB4F,0x142EB56],
                               values=[0x25065DD3,0x6E61441F,0x833E051C],read=0x142ED3F,local=0x18752516),
}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def murmur64a(data):
    mask,mix=(1<<64)-1,0xC6A4A7935BD1E995
    h,at=len(data)*mix&mask,0
    while at+8<=len(data):
        k=int.from_bytes(data[at:at+8],'little');at+=8
        k=k*mix&mask;k^=k>>47;k=k*mix&mask
        h^=k;h=h*mix&mask
    if at<len(data):
        h^=int.from_bytes(data[at:],'little');h=h*mix&mask
    h^=h>>47;h=h*mix&mask
    return h^(h>>47)

def lookup_model(buckets,key,multiplier=2):
    """12556E0 under initializer-proven invalid=0, power-of-two capacity."""
    cap=len(buckets)
    hashed=key*multiplier&0xffffffff
    for probe in range(cap):
        k,v=buckets[((hashed+probe)&0xffffffff)&(cap-1)]
        if k==0 or k==key:
            return v if k else 0
    return 0

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args();out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    im=Image(args.evidence)
    prior=HERE/'indexed_float_consumers_evidence.json'
    prior_raw=prior.read_bytes()
    require(sha(prior_raw)=='503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578','consumer evidence changed')
    decoded={};functions=[];tails=[]
    for root,(end,digest) in FUNCTIONS.items():
        fs=[f for f in im.functions if im.root(f[0])[0]==root]
        require(fs and fs[0][0]==root and fs[-1][1]==end,'root boundary changed')
        require(all(a[1]==b[0] for a,b in zip(fs,fs[1:])),'root gap')
        raw=b''.join(im.read(a,b-a) for a,b,_ in fs)
        require(sha(raw)==digest,'root bytes changed')
        ins=[];fragments=[]
        for a,b,u in fs:
            code_end=0xAB0029 if root==0xAAFF30 else b
            ds=list(im.md.disasm(im.read(a,code_end-a),a))
            require(sum(i.size for i in ds)==code_end-a,'incomplete code decode')
            ins+=ds
            fragments.append(dict(start=hex(a),end_exclusive=hex(b),unwind=hex(u),
                                  code_end_exclusive=hex(code_end),sha256=sha(im.read(a,b-a))))
        decoded.update((i.address,i) for i in ins)
        boundaries={i.address for i in ins};edges={};external=[]
        for i in ins:
            if i.group(cs.CS_GRP_RET):ss=[]
            elif i.group(cs.CS_GRP_JUMP):
                if i.operands[0].type==X86_OP_IMM:
                    ss=[i.operands[0].imm]
                elif i.address==0xAAFFB6:
                    ss=list(struct.unpack('<7I',im.read(0xAB002C,28)))
                else:
                    require(i.mnemonic=='jmp','unexpected conditional indirect jump')
                    external.append(row(i));ss=[]
                if i.mnemonic!='jmp':ss.append(i.address+i.size)
            else:ss=[i.address+i.size]
            require(all(t in boundaries for t in ss),'branch outside pinned code')
            edges[hex(i.address)]=[hex(x) for x in ss]
        functions.append(dict(entry=hex(root),end_exclusive=hex(end),raw_bytes=len(raw),sha256=digest,
            fragments=fragments,instructions=[row(i) for i in ins],normal_cfg=edges,external_tail_jumps=external))
    tail=im.read(0xAB0029,31)
    require(tail[:3]==bytes.fromhex('0f1f00'),'hash padding changed')
    require(list(struct.unpack('<7I',tail[3:]))==[0xAB0000,0xAAFFF4,0xAAFFE8,0xAAFFDC,0xAAFFD0,0xAAFFC4,0xAAFFB8],'hash switch changed')
    tails.append(dict(start='0xab0029',end_exclusive='0xab0048',bytes=tail.hex(),sha256=sha(tail),
                      interpretation='3-byte post-RET NOP followed by seven DWORD RVAs, dispatched at AAFFB6.'))
    pins={}
    groups={
      'rank_and_motion_dataflow':[0x142EB0B,0x142EB61,0x142EB70,0x142EB72,0x142EB77,0x142EB7A,0x142EB7D,
        0x142EB94,0x142EBA1,0x142EBC3,0x142EBD0,0x142EC6D,0x142EC9D,0x142ECC1,0x142ECCF,
        0x142ECD7,0x142ECDB,0x142ED0B,0x142ED10,0x142ED15,0x142ED1A,0x142ED1F,0x142ED24,
        0x142ED29,0x142ED2C,0x142ED2E,0x142ED32,0x142ED35,0x142ED37,0x142ED3B,0x142ED3F,
        0x142ED43,0x142ED46,0x142ED48,0x142ED4B,0x142ED4D,0x142ED52,0x142ED54,0x142ED59,
        0x142ED5B,0x142ED5E,0x142ED65,0x142ED68,0x142ED78,0x142ED86,0x142ED8D,0x142ED8F,
        0x142ED94,0x142EDA0,0x142EDA3,0x142EDA6,0x142EDAF,0x142EDB5,0x142EDBE,0x142EDC6],
      'plugin_identity_and_callback_binding':[0x4EDB27,0x4EDB2F,0x4EDB33,0x4EDB36,0x4EDB40,
        0x4EDB42,0x4EDB47,0xFC558C,0xFC5596,0xFC55B8,0xFC55C8,0xFC4D8C,0xFC4D8F,
        0xFC4D92,0xFC4D97,0xFC4D9B,0xFC4D9D,0xFC4DA2,0xFC4DA4,0xFC4DA6,
        0xFC4E7B,0xFC4E80,0xFC4E87,0xFC502D,0xFC5032,0xFC5039],
      'lookup_and_initializer':[0x125580B,0x1255820,0x125582A,0x125582C,0x125582F,0x125583B,
        0x1255846,0x125584F,0x125585B,0x1255862,0x12556EF,0x12556F8,0x1255702,0x1255706,
        0x125570F,0x1255715,0x1255730,0x1255732,0x1255734,0x1255737,0x125573B,0x125573E,
        0x1255740,0x1255752,0x1255754,0x1255756],
      'wrappers':[0x1327F5F,0x1327F66,0x1327F6F,0x1327F76,0x1327F7D,0x1327F84,0x1327F86,
        0x1327F8B,0x1327F97,0x1327F9A,0x1327F9D,0x1327FA6,0x1327FB8,
        0x1327FEA,0x1327FF1,0x1327FFF,0x1328002,0x1328010,0x1328017,0x1328021,
        0x1328024,0x1328027,0x1328031,0x1328043],
    }
    for name,ats in groups.items():pins[name]=[row(decoded[a]) for a in ats]
    caller=im.instruction(0xAB1535)
    require(caller.mnemonic=='call' and caller.op_str=='0x1255800','initializer caller changed')
    pins['initializer_caller']=[dict(**row(caller),root=hex(im.root(caller.address)[0]))]
    def rip_target(at):
        i=decoded[at]
        refs=[i.address+i.size+o.mem.disp for o in i.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(len(refs)==1,'unexpected RIP address')
        return refs[0]
    for at,target in {0x4EDB36:0x3326318,0x4EDB47:0x3326318,0x1327F5F:0x3326318,
                      0x1327FEA:0x3326318,0x125583B:0x346C9F8,0x125584F:0x346CA04,
                      0x125585B:0x346CA00,0x1255862:0x346CA08,0xFC558C:0x225CF00,
                      0xFC55B8:0xFC4C50}.items():require(rip_target(at)==target,'RIP target changed')
    require(im.read(0x225CF00,20)==b'wwise_trigger_event\0','event string changed')
    for t in TABLES.values():
        for at,value in zip(t['init'],t['values']):
            i=decoded[at];require(i.mnemonic=='mov' and i.operands[-1].imm==value,'ID initializer changed')
        t['initializers']=[row(decoded[a]) for a in t['init']]
        t['reader']=row(decoded[t['read']])
    for at,mn,op in [(0x4EDB27,'mov','ecx, 0x4b264f2e'),(0xFC4D92,'call','0xaaff30'),
        (0xFC4D97,'shr','rax, 0x20'),(0xFC4D9D,'call','0x12556e0'),
        (0x142ED0B,'mov','edx, 0x7a65db2'),(0x142ED10,'mov','edi, 0x11d0acb1'),
        (0x142ED15,'mov','ebx, 0x18752516')]:
        require((decoded[at].mnemonic,decoded[at].op_str)==(mn,op),'critical semantic changed')
    for name,digest in FILES.items():require(sha((ROOT/name).read_bytes())==digest,'dictionary/hash source changed')
    require(murmur64a(b'hello, world!')==0xD18ABE154A2A9637,'hash vector1')
    require(murmur64a(b'hello, world!!!!')==0x2F9DEA7BD39B9F7D,'hash vector2')
    targets={x for t in TABLES.values() for x in t['values']+[t['local']]}
    counts={};matches=[];identity=[]
    for name in FILES:
        if not name.endswith('.txt'):continue
        count=0
        for line_no,s in enumerate((ROOT/name).read_text(encoding='utf-8-sig').splitlines(),1):
            if not s or s.startswith(('#','//')):continue
            count+=1;h=murmur64a(s.encode())
            if h>>32 in targets or h==0xB9EE36888EF19818:
                matches.append(dict(file=name,line=line_no,text=s,hash64=hex(h),thin32=hex(h>>32)))
            if s in ('wwise_plugin','hash_lookup'):
                identity.append(dict(file=name,line=line_no,text=s,hash64=hex(h),thin32=hex(h>>32)))
        counts[name]=count
    require(murmur64a(b'wwise_plugin')>>32==0x4B264F2E,'plugin identity hash')
    require(murmur64a(b'hash_lookup')==0xE3F2851035957AF5,'resource type hash')
    require(any(x['text']=='wwise_plugin' for x in identity) and any(x['text']=='hash_lookup' for x in identity),'identity names absent')
    captured_strings=0;captured_matches=[]
    for area in im.report['ranges']:
        if not area['label'].startswith('readonly'):continue
        raw=im.read(area['rva'],area['size'])
        for m in re.finditer(rb'[\x20-\x7e]{1,}\x00',raw):
            captured_strings+=1;s=m.group()[:-1];h=murmur64a(s)
            if h>>32 in targets or h==0xB9EE36888EF19818:
                captured_matches.append(dict(rva=hex(area['rva']+m.start()),text=s.decode(),hash64=hex(h)))
    require(not matches and not captured_matches,'new ID name match requires interpretation')
    # Limited examples support the explicit missing behavior; actual map data is absent.
    examples=[dict(kind='capacity_zero',result=lookup_model([],123)),
              dict(kind='empty_bucket',result=lookup_model([(0,0)]*8,123)),
              dict(kind='full_missing_key',result=lookup_model([(1+i,100+i) for i in range(8)],123)),
              dict(kind='known_present_key',result=lookup_model([(0,0),(0,0),(1,77)]+[(0,0)]*5,1))]
    require([x['result'] for x in examples]==[0,0,0,77],'lookup model examples')
    # A separately extracted fixed boot resource, not a runtime global capture.
    asset=(HERE/'indexed_float_wwise_hash_lookup_current.bin').read_bytes()
    manifest_raw=(HERE/'indexed_float_rank_asset_manifest.json').read_bytes()
    require(sha(asset)==ASSET_SHA and sha(manifest_raw)==MANIFEST_SHA,'asset or extraction manifest changed')
    manifest=json.loads(manifest_raw)
    first_capacity=struct.unpack_from('<I',asset)[0]
    second_header=4+first_capacity*8
    second_capacity=struct.unpack_from('<I',asset,second_header)[0]
    require(len(asset)==second_header+4+second_capacity*8,'lookup resource extent')
    first=list(struct.iter_unpack('<II',asset[4:second_header]))
    second=list(struct.iter_unpack('<II',asset[second_header+4:]))
    forward={k:v for k,v in first if k};reverse={k:v for k,v in second if k}
    require(len(forward)==sum(k!=0 for k,v in first),'duplicate real key in first map')
    require(len(reverse)==sum(k!=0 for k,v in second),'duplicate real key in second map')
    require(set(forward.items())=={(v,k) for k,v in reverse.items()},'maps not exact reverse pairs')
    for key,value in forward.items():require(lookup_model(first,key)==value,'first-map key not reachable via helper algorithm')
    asset_queries=[]
    for key in sorted(targets):
        trace=[];return_value=0
        for probe in range(first_capacity):
            index=((key*2+probe)&0xffffffff)&(first_capacity-1)
            k,v=first[index]
            trace.append(dict(probe=probe,index=index,file_offset=hex(4+index*8),key=hex(k),value=hex(v),
                              bytes=asset[4+index*8:12+index*8].hex()))
            if k==0 or k==key:
                return_value=v if k else 0
                break
        asset_queries.append(dict(key=hex(key),present=key in forward,lookup_return=hex(return_value),
                                  complete_key_scan_occurrences=sum(k==key for k,v in first),trace=trace))
    require({int(q['key'],16) for q in asset_queries if not q['present']}=={0x6E61441F,0x833E051C},'missing-key set changed')
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        replay_sha256=sha(Path(__file__).read_bytes()),prior_consumer_evidence_sha256=sha(prior_raw),
        functions=functions,post_ret_data=tails,selected_instruction_groups=pins,tables=TABLES,
        hash_algorithm=dict(name='MurmurHash64A seed0; Thin is upper32',local_source_sha256=FILES,
            captured_implementation='0xaaff30',actual_string_lookup_call_chain=['0xfc4d8c','0xfc4d92','0xfc4d97','0xfc4d9d'],
            identity_matches=identity,test_vectors={'hello, world!':'0xd18abe154a2a9637','hello, world!!!!':'0x2f9dea7bd39b9f7d'},
            collision_uniqueness_proven=False),
        lookup_resource=dict(name_hash='0xb9ee36888ef19818',type_hash='0xe3f2851035957af5',type_name='hash_lookup',
            loader='0x1255800',first_map_header_global='0x346c9f8',capacity_global='0x346ca00',
            invalid_global='0x346ca04',multiplier_global='0x346ca08',invalid=0,multiplier=2,
            file_format_prefix='u32 capacity; capacity*(u32 key,u32 value); second u32 capacity; second map buckets',
            runtime_resource_bytes_captured=False,resource_name_matched=False,
            saved_disk_resource_parsed=True),
        saved_asset=dict(path='indexed_float_wwise_hash_lookup_current.bin',sha256=ASSET_SHA,size=len(asset),
            extraction_manifest='indexed_float_rank_asset_manifest.json',manifest_sha256=MANIFEST_SHA,
            runtime_verified=False,first_capacity=first_capacity,second_capacity=second_capacity,
            first_nonzero_keys=len(forward),second_nonzero_keys=len(reverse),all_first_keys_lookup_verified=len(forward),
            second_map_exact_inverse=True,queries=asset_queries,
            missing_parameter_keys=['0x6e61441f','0x833e051c'],
            selection_limits=manifest['limits'],
            interpretation='Selected installed-build boot resource plus separately audited loose override scope; does not prove actual runtime selection.'),
        dataflow=dict(plugin_global='0x3326318',plugin_name_hash='0x4b264f2e',plugin_name='wwise_plugin',
            event_api_offset='0x338',object_api_offset='0x288',float_parameter_api_offset='0x380',
            event_api_name_proof='wwise_trigger_event callback FC4C50 uses identical plugin+338 after the same string hash and ID lookup.',
            float_parameter_exact_export_name_proven=False,
            onset='new movement predicate true and old predicate false: first ID ->1327F50->lookup->plugin+338',
            ongoing='new predicate true: third ID ->lookup->1327FE0->plugin+380 with computed float',
            cessation='new predicate false and old predicate true: second ID ->lookup->plugin+338',
            local_triplet='07A65DB2 / 11D0ACB1 / 18752516 is used only when current slot equals selected local index.',
            source_isolation_per_rank_proven=False),
        missing_behavior=dict(lookup_return=0,initializer_invalid_zero_proven=True,lookup_examples=examples,
            rank_path_checks_zero=False,rank_path_forwards_zero_to_plugin=True,
            named_flow_callback_checks_zero=True,plugin_zero_id_runtime_behavior_proven=False),
        finite_name_search=dict(dictionary_counts=counts,dictionary_matches=matches,
            captured_ascii_nul_runs=captured_strings,captured_matches=captured_matches,
            limits='Only whole exact-case dictionary lines and printable ASCII NUL-terminated runs in saved readonly ranges; no universal absence claim.'),
        expansion=dict(existing_remote_triplets=3,additional_local_triplets=1,
            additional_remote_rank_definitions_proven=0,
            valid_new_id_rule='Need an actual resource definition, mapping, API semantics and compatible per-rank behavior. Hashing a guessed name is not registration; missing lookup returning 0 does not supply a new definition.',
            local_triplet_reuse_authorized_by_evidence=False,
            required_remote_count='7 if exactly one valid selected local is present among 8; otherwise rank enumeration may produce 8 entries.',
            resolved='These tables configure Wwise movement events/continuous float parameters; they are not player entity membership records.',
            unresolved='The selected boot hash_lookup is now pinned and parsed, but Wwise event/parameter definitions and additional remote-rank identities are not established. No validated extra triplets supplied.',
            baseline_detail='The saved first map contains all six remote event hashes and the first remote float hash; the other two original remote float hashes are absent and lookup returns 0. No runtime fault/safety conclusion follows.'),
        limits=['Static captured-code and local-dictionary analysis, not runtime audio behavior or multiplayer verification.',
            'No new capture, process query/read, injection, installation or asset mutation.',
            'Plugin table pointers and targets are runtime data absent from this capture; export offsets are established call boundaries.',
            'Hash matches do not prove uniqueness; event classification additionally uses explicit named callback registration.',
            'The selected disk resource is not evidence of every bundled duplicate or runtime-selected resource.',
            'The two absent baseline parameter hashes do not prove an original-game fault or that ID 0 is either valid, invalid or safe in plugin+380.',
            'No replacement IDs are invented, and no claim is made that missing ID 0 is a safe fallback.'])
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),replay_sha256=result['replay_sha256'],
        roots=len(functions),instruction_rows=sum(len(x['instructions']) for x in functions),
        dictionary_lines=sum(counts.values()),captured_ascii_runs=captured_strings),ensure_ascii=False))

if __name__=='__main__':main()
