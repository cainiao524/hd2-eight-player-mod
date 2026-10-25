"""Pinned classification images with stable stack depth and unconditional saves."""
import json,struct,capstone
import native_remove_image as common
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_GRP_JUMP,CS_GRP_CALL
from capstone.x86_const import X86_OP_MEM,X86_REG_RIP,X86_REG_RSP,X86_REG_RBP
ROOT,PROJECT=common.ROOT,common.PROJECT
load,require,sha,source=common.load,common.require,common.sha,common.source
KINDS=('enter','leave')
LOCK=PROJECT/'native-classify.lock.json'
LOCK_SHA256='41843b622018655e4d286036256ba8463ce6f638a15fd33f6cd1bf5ff87c8b03'
LEGACY_SHA256='bc4508fadf17726b773ed9c4237f7693405856ccc0b57ddcac4d06e073f46153'
SAVES={'enter':((0x60d044,12,8),),'leave':((0x60d39a,12,8),(0x60d3b1,14,16))}
SCRATCH_SAVE=bytes.fromhex('48896c2418')
SCRATCH_RESTORE=bytes.fromhex('488b6c2418')

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Classification source lock changed');data=json.loads(raw)
    source.audit(data,schema='hellforge_captured_classify_unwind_v1',names=KINDS);return data

def legacy():
    common.legacy()
    path=ROOT/'eight_player_candidate_20260927/Native/roster_classify.py'
    require(sha(path.read_bytes())==LEGACY_SHA256,'Classification source changed')
    return load('pinned_classify',path)

def decode(code,base):
    md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True;rows=list(md.disasm(code,base))
    require(sum(i.size for i in rows)==len(code),'Incomplete classification decode');return rows

def body_unwind(raw,saves):
    require(raw[0]==1 and raw[3]==0,'Unsupported primary classification unwind')
    shift=5*len(saves);codes=bytearray(raw[4:4+raw[2]*2]);at=0
    while at<len(codes):
        op=codes[at+1]&15;require(op in (0,2,4),'Unexpected primary unwind operation')
        codes[at]+=shift;at+=4 if op==4 else 2
    # SAVE_NONVOL offsets use the frame base, not the progressively unwound RSP.
    # Until the full frame exists these registers still hold the caller values.
    early=bytearray()
    for n,(_,reg,offset) in reversed(list(enumerate(saves,1))):
        early+=bytes((raw[1]+shift,(reg<<4)|4))+struct.pack('<H',(0x58+offset)//8)
    codes=early+codes
    count=len(codes)//2
    return bytes((1,raw[1]+shift,count,0))+codes+bytes(2*(count%2))

def with_unwind(candidate):
    data=profile();kind=candidate['kind'];fn=data['functions'][kind];old=legacy();base=candidate['code_address']
    require(candidate['source_sha256']==fn['code_sha256'] and candidate['evidence_sha256']==fn['evidence_sha256'],'Changed classification identity')
    code=bytearray.fromhex(candidate['code_hex']);require(sha(code)==candidate['code_sha256'],'Changed classification code')
    body=candidate['body_address'];saves=SAVES[kind];original=old.load_sources(ROOT/fn['evidence_path'])[kind]
    primary=bytes.fromhex(fn['fragments'][0]['unwind_hex'])
    require(code[body-base:body-base+primary[1]]==original[:primary[1]],'Changed classification prologue')
    # Check the scratch slot against all direct stack references. Helpers receive
    # RSP+0x20, while the transient save uses the fourth shadow slot at RSP+0x18.
    for i in decode(original,int(fn['entry'],16)):
        if i.address>=int(fn['entry'],16)+primary[1]:
            for op in i.operands:
                if op.type==X86_OP_MEM and op.mem.base==X86_REG_RSP:
                    require(op.mem.disp>=0x20,'Original body uses scratch shadow slot')
    restore=bytes.fromhex('5f5e5b415941585a59');rejections=[]
    for reason in range(1,10):
        mov=b'\x41\xba'+struct.pack('<I',reason);pattern=restore+mov+b'\xe9'
        require(code.count(pattern)==1,'Changed classification rejection layout');at=code.index(pattern)
        code[at:at+len(restore)+len(mov)]=mov+restore;rejections.append(at)
    changes={};starts=[]
    for patch in candidate['array_patches']:
        at=patch['emitted_address'];blob=bytes.fromhex(patch['replacement_hex'])
        require(blob[0]==0x55 and blob[1:3]==b'\x48\xbd' and blob[-1]==0x5d,'Changed array wrapper')
        original_op=decode(bytes.fromhex(patch['original_hex']),patch['original_rva'])
        require(len(original_op)==1,'Array patch covers multiple instructions')
        reads,writes=original_op[0].regs_access()
        require(X86_REG_RSP not in reads and X86_REG_RSP not in writes and X86_REG_RBP not in writes,'Array patch changes frame register')
        changes[at]=SCRATCH_SAVE;changes[at+len(blob)-1]=SCRATCH_RESTORE;starts.append(at)
    hoisted=b''
    for rva,reg,offset in saves:
        at=candidate['instruction_address_map'][hex(rva)]
        require(bytes(code[at-base:at-base+5])==bytes((0x4c,0x89,0x64 if reg==12 else 0x74,0x24,0x58+offset)),'Changed conditional save')
        changes[at]=b'\x90'*5
        hoisted+=bytes((0x4c,0x89,0x64 if reg==12 else 0x74,0x24,offset))
    rows=decode(code,base);mapping={};pieces=[];cursor=base
    for i in rows:
        mapping[i.address]=cursor;blob=changes.get(i.address,bytes(i.bytes))
        if i.address==body:blob=hoisted+blob
        pieces.append([i,cursor,bytearray(blob)]);cursor+=len(blob)
    for i,at,blob in pieces:
        if i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL):
            target=i.operands[0].imm
            if base<=target<base+len(code):require(target in mapping,'Invalid local target');target=mapping[target]
            require(i.imm_size==4,'Unexpected short classification branch')
            blob[i.imm_offset:i.imm_offset+4]=old.rel32(at+len(blob),target)
        for op in i.operands:
            if op.type==X86_OP_MEM and op.mem.base==X86_REG_RIP:
                require(i.address!=body,'Unexpected RIP access in first prologue operation')
                target=i.address+i.size+op.mem.disp
                blob[i.disp_offset:i.disp_offset+4]=old.rel32(at+len(blob),target)
    code=b''.join(bytes(p[2]) for p in pieces);prefix=(len(code)+3)&~3
    unwind=body_unwind(primary,saves);uw=prefix+len(common.PREFLIGHT_UNWIND);table=uw+len(unwind)
    body_offset=mapping[body]-base
    image=code+bytes(prefix-len(code))+common.PREFLIGHT_UNWIND+unwind+struct.pack('<6I',0,body_offset,prefix,body_offset,len(code),uw)
    regions=[dict(r) for r in candidate['known_regions']];regions[0]['size_bytes']=len(image)
    for n,a in enumerate(regions):
        old.pointer(a['address'],a['size_bytes'],1,a['name'])
        for b in regions[n+1:]:require(not old.overlaps(a['address'],a['size_bytes'],b['address'],b['size_bytes']),'Complete classification image overlap')
    patches=[]
    for patch in candidate['array_patches']:
        begin=patch['emitted_address'];end=begin+len(bytes.fromhex(patch['replacement_hex']))
        stop=mapping[end] if end in mapping else base+len(code)
        patches.append({**patch,'emitted_address':mapping[begin],'replacement_hex':code[mapping[begin]-base:stop-base].hex()})
    result={**candidate,'status':'offline_native_classify_with_unwind','known_regions':regions,
            'body_address':mapping[body],'size_bytes':len(code),'code_hex':code.hex(),'code_sha256':sha(code),
            'array_patches':patches,'instruction_address_map':{k:mapping[v] for k,v in candidate['instruction_address_map'].items()},
            'relocations':[{**r,'emitted_address':mapping[r['emitted_address']],
                           'target_address':mapping.get(r['target_address'],r['target_address'])} for r in candidate['relocations']],
            'unwind_registered':False,'runtime_verified':False}
    return dict(candidate=result,image=image,unwind_offset=uw,table_offset=table,function_count=2,
                prefix_unwind_offset=prefix,rejection_offsets=[mapping[base+x]-base for x in rejections],
                scratch_offsets=[mapping[x]-base for x in starts],hoisted_nonvolatile_registers=[r for _,r,_ in saves])

def build(**addresses):
    old=legacy();fn=profile()['functions'][addresses['kind']]
    return with_unwind(old.build(old.load_sources(ROOT/fn['evidence_path'])[addresses['kind']],**addresses))

def load_fixture():
    d=profile();p=ROOT/d['fixture_path'];require(sha(p.read_bytes())==d['fixture_sha256'],'Classification fixture changed')
    m=load('hellforge_classify_fixture',p)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def emitter(library):
    def emit(body,**addresses):
        require(type(body)is bytes and sha(body)==profile()['functions'][addresses['kind']]['code_sha256'],'Changed classification input')
        ref=build(**addresses)
        return library.classify_candidate(addresses,ref) if library else ref['candidate']
    return emit

def bind_fixture(module,library):
    module.native.build=emitter(library)
