"""Four-array writer: a leaf preflight followed by a uniformly saved body."""
import importlib.util,json,struct
import native_getter_image as common
from capstone.x86_const import X86_OP_IMM
ROOT,PROJECT=common.ROOT,common.PROJECT
sha,require=common.sha,common.require
LOCK=PROJECT/'native-mover.lock.json'
LOCK_SHA256='d871e37dfa31605cec611c4e4d2757ef7d1421862a004a9019ff40f6ac8f4a30'
PROLOGUE=bytes.fromhex('48895c2420415648896c2410488974241848897c2420')
# As in the captured primary unwind, RBX becomes recoverable at the push's
# completion; restore it before undoing PUSH R14, using the final RSP + 0x28.
UNWIND=bytes.fromhex('0116090016740400116403000c5402000734050007e00000')

def profile():
    raw=LOCK.read_bytes();require(sha(raw)==LOCK_SHA256,'Mover source lock changed')
    data=json.loads(raw);common.source.audit(data,schema='hellforge_captured_mover_unwind_v1',names=('mover',));return data

def legacy():
    data=profile();path=ROOT/'eight_player_candidate_20260927/Native/roster_move.py'
    lock=json.loads((PROJECT/'native-storage.lock.json').read_bytes())
    require(sha(path.read_bytes())==lock['legacy_source_sha256'][path.relative_to(ROOT).as_posix()],'Mover source changed')
    spec=importlib.util.spec_from_file_location('pinned_mover',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,module.load_source(ROOT/data['functions']['mover']['evidence_path'])

def build(*,game_base,code_address,roster_address,storage_address,reject_address):
    old,source=legacy()
    for value,size,align,name in ((game_base,old.END_RVA,4096,'game'),(code_address,1,16,'code'),(roster_address,0x428,8,'roster'),(storage_address,0x680,16,'storage'),(reject_address,1,1,'reject')):
        old.pointer(value,size,align,name)
    require(storage_address>=0xE8,'Storage bias underflow')
    # Preserve all original instructions after PUSH R14, apart from the three
    # late saves moved to the common prologue, displacement patches and map base.
    patched=bytearray(source)
    for _,sites,delta in old.PATCH_GROUPS:
        for rva,offset,expected in sites:
            at=rva-old.ENTRY_RVA+offset;require(struct.unpack_from('<i',source,at)[0]==expected,'Changed array displacement')
            struct.pack_into('<i',patched,at,expected+delta)
    md=common.common.capstone.Cs(common.common.capstone.CS_ARCH_X86,common.common.capstone.CS_MODE_64);md.detail=True
    ins=list(md.disasm(source,old.ENTRY_RVA));require(sum(i.size for i in ins)==len(source),'Partial mover decode')
    out=bytearray();labels={};fixups=[]
    def emit(blob):out.extend(blob)
    def branch(op,target):emit(op);fixups.append((len(out),target));emit(bytes(4))
    emit(bytes.fromhex('443bc2'));branch(b'\x0f\x84','equal')
    emit(bytes.fromhex('83fa08'));branch(b'\x0f\x83','reject1')
    emit(bytes.fromhex('4183f808'));branch(b'\x0f\x83','reject2')
    emit(b'\x48\xb8'+struct.pack('<Q',roster_address));emit(bytes.fromhex('4839c1'));branch(b'\x0f\x85','reject3')
    emit(b'\x48\xb9'+struct.pack('<Q',storage_address-0xE8));branch(b'\xe9','body')
    for reason in (1,2,3):
        labels['reject'+str(reason)]=len(out);emit(b'\x41\xba'+struct.pack('<I',reason));branch(b'\xe9','external')
    labels['equal']=len(out);emit(b'\xc3')
    require(len(out)==96,'Changed leaf prefix');labels['body']=len(out);emit(PROLOGUE)
    mapping={}
    for i in ins:
        offset=i.address-old.ENTRY_RVA
        if offset<16:continue
        mapping[i.address]=len(out);raw=bytes(patched[offset:offset+i.size])
        if i.address in (0x60C454,0x60C459,0x60C45E):
            expected={0x60C454:'48896c2410',0x60C459:'4889742418',0x60C45E:'48897c2420'}[i.address]
            require(raw.hex()==expected,'Changed late save');emit(b'\x90'*i.size)
        elif i.address==0x60C54A:
            require(raw==old.MAP_BYTES,'Changed map splice');emit(b'\x48\xbb'+struct.pack('<Q',roster_address)+raw)
        elif i.group(common.common.capstone.CS_GRP_JUMP):
            target=next(o.imm for o in i.operands if o.type==X86_OP_IMM)
            require(old.ENTRY_RVA+16<=target<old.END_RVA,'Unexpected body branch')
            op=b'\xe9' if i.mnemonic=='jmp' else bytes((0x0F,raw[0]+0x10)) if len(raw)==2 else raw[:2]
            branch(op,target)
        else:
            require(not i.group(common.common.capstone.CS_GRP_CALL),'Unexpected mover call');emit(raw)
    for at,target in fixups:
        dest=reject_address if target=='external' else code_address+(mapping[target] if isinstance(target,int) else labels[target])
        out[at:at+4]=old.rel32(code_address+at+4,dest)
    code=bytes(out);leaf=(len(code)+3)&~3;unwind=leaf+4;table=unwind+len(UNWIND)
    image=code+bytes(leaf-len(code))+b'\x01\0\0\0'+UNWIND+struct.pack('<6I',0,96,leaf,96,len(code),unwind)
    old.pointer(code_address,len(image),16,'whole image')
    regions=((code_address,len(image)),(roster_address,0x428),(storage_address,0x680),(game_base+old.ENTRY_RVA,len(source)),(reject_address,1))
    require(all(not old.overlaps(a,n,b,m) for k,(a,n) in enumerate(regions) for b,m in regions[k+1:]),'Known region overlap')
    candidate=dict(status='offline_native_mover_with_unwind',installable=False,game_execution=False,multiplayer_verified=False,
        target_profile=old.TARGET_PROFILE,source_sha256=old.SOURCE_SHA256,evidence_sha256=old.EVIDENCE_SHA256,
        game_base=game_base,code_address=code_address,entry_address=code_address,roster_address=roster_address,
        storage_address=storage_address,property_address=storage_address+0x580,reject_address=reject_address,
        code_hex=code.hex(),code_sha256=sha(code),size_bytes=len(code),body_offset=96,
        instruction_address_map={hex(k):code_address+v for k,v in mapping.items()},runtime_verified=False)
    return dict(candidate=candidate,image=image,unwind_offset=unwind,table_offset=table,function_count=2)

def load_fixture():
    data=profile();path=ROOT/data['fixture_path'];require(sha(path.read_bytes())==data['fixture_sha256'],'Changed mover fixture')
    spec=importlib.util.spec_from_file_location('hellforge_mover_fixture',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    require(m.unicorn.__version__=='2.1.4' and m.capstone.__version__=='5.0.7','Wrong emulator/decoder');return m

def emitter(library):
    def emit(source,**addresses):
        require(type(source) is bytes and sha(source)==profile()['functions']['mover']['code_sha256'],'Changed mover input')
        return library.mover_candidate(addresses,build(**addresses))
    return emit

def bind_insertion_fixture(module,library):
    """Override only the pinned fixture; validate the larger image explicitly."""
    module.native.move.build=emitter(library)
    original=module.Fixture.__init__
    def initialize(f,*args,**kwargs):
        original(f,*args,**kwargs)
        if f.original:return
        image=build(game_base=f.game,code_address=f.move_entry,roster_address=module.S,
                    storage_address=module.B,reject_address=f.move_reject)['image']
        # The legacy insert/remove emitters know only the old 545-byte mover.
        # This fixture additionally checks the entire new 612-byte image.
        for address,size in ((f.start,f.a['size_bytes']),(f.reject,1),(f.stop,1),
                             (f.game+0x172F790,len(module.MAP_BODY)),(f.game+0x10110000,0x10000)):
            require(f.move_entry+len(image)<=address or address+size<=f.move_entry,'Mover fixture overlap')
        f.native_mover_image_bytes=len(image)
    module.Fixture.__init__=initialize
