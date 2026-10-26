"""Pinned component33 core and classification with four relocated arrays.

Only numeric image generation. No live memory access, installation or hooks.
"""
import functools
import hashlib
import json
import struct
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'hellforge_multiplayer'
sys.path[:0] = [str(ROOT / 'eight_player_candidate_20260927/.native-test-deps'), str(ROOT / 'research_handoff_20260927/indirect')]
import capstone
from capstone.x86_const import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
from inspect_capture import Image
LOCK = PROJECT / 'native-component33.lock.json'
LOCK_SHA = '68523ebac989e9a0d6d83b296478d157b9043a64a65cd93c188270adf3589fdf'
KINDS = ('mover', 'append', 'dense', 'remove')
CLASSIFY_KINDS = ('enter','leave')
ALL_KINDS = KINDS + CLASSIFY_KINDS
sha = lambda b: hashlib.sha256(b).hexdigest()

def need(ok, message):
    if not ok: raise ValueError(message)

@functools.lru_cache()
def profile():
    need(sha(LOCK.read_bytes()) == LOCK_SHA, 'component33 lock changed')
    data = json.loads(LOCK.read_bytes())
    need(sha((ROOT / data['evidence_path']).read_bytes()) == data['evidence_sha256'], 'component33 evidence changed')
    im = Image(ROOT / data['capture_directory'])
    for name, f in data['functions'].items():
        code = bytes.fromhex(f['body_hex'])
        need(sha(code) == f['sha256'] and im.read(f['start'], len(code)) == code, 'source code changed: ' + name)
        for fragment in f.get('fragments', []):
            need(im.containing(fragment['start']) == (fragment['start'], fragment['end'], fragment['unwind_rva']), 'fragment changed')
            raw = bytes.fromhex(fragment['unwind_hex'])
            need(raw[0] in (1, 33) and raw[3] == 0 and im.read(fragment['unwind_rva'], len(raw)) == raw, 'unwind changed')
    for callback in data['classification_callbacks'].values():
        need(im.read(callback['entry'],8)==bytes.fromhex(callback['body_hex']),'classification wrapper changed')
        for i in callback['assignment']['instructions']:
            raw=bytes.fromhex(i['bytes']);need(im.read(int(i['rva'],16),len(raw))==raw and sha(raw)==i['sha256'],'classification registration changed')
    return data

def decode(blob, address):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    rows = list(md.disasm(blob, address))
    need(sum(i.size for i in rows) == len(blob), 'partial decode')
    return rows

def pointer(p, n, alignment):
    need(type(p) is int and 0 < p < (1 << 47) and not p % alignment and n <= (1 << 47) - p, 'invalid pointer')

def build(kind, *, game_base, code_address, component_address, storage_address, move_code_address, reject_address):
    need(kind in ALL_KINDS, 'invalid kind')
    data = profile(); f = data['functions'][kind]; classification=kind in CLASSIFY_KINDS
    for p,n,a in ((game_base,0x3483C38,4096),(code_address,4096,16),(component_address,0x2B8,8),
                  (storage_address,0x490,16),(move_code_address,4096,16),(reject_address,1,1)):
        pointer(p,n,a)
    need(storage_address >= 0x70, 'storage bias underflow')
    regions = [(code_address,4096),(component_address,0x2B8),(storage_address,0x490),(reject_address,1),(game_base+0x33267B8,8),(game_base+0x3483C34,4)]
    if kind != 'mover': regions.append((move_code_address,4096))
    regions += [(game_base+x['start'],x['end']-x['start']) for x in data['functions'].values()]
    need(all(a+n <= b or b+m <= a for k,(a,n) in enumerate(regions) for b,m in regions[k+1:]), 'overlapping image/data/source')
    out = bytearray(); labels = {}; fixes = []
    def emit(h): out.extend(bytes.fromhex(h) if isinstance(h,str) else h)
    def mov(reg,value): emit(bytes([0x48 | (reg >> 3), 0xB8 + (reg & 7)]) + struct.pack('<Q',value))
    def branch(target,condition=None):
        emit(b'\xe9' if condition is None else bytes([0x0F,condition])); fixes.append((len(out),target)); emit(bytes(4))
    def label(name): labels[name] = len(out)
    # All refusal paths precede any stack/data write. Original arguments survive.
    if classification: emit('4889d1')  # helper ABI: entity RDX, RCX unused by original body
    mov(0,game_base+0x33267B8); emit('488b00'); mov(10,component_address); emit('4c39d0'); branch('reject1',0x85)
    if kind == 'mover': emit('4c39d1'); branch('reject1',0x85)
    emit('458b5a08 4183fb08'); branch('reject2',0x83 if kind in ('append','dense') else 0x87)
    emit('418b420c 4439d8'); branch('reject3',0x87)
    emit('41394210'); branch('reject3',0x87)
    if kind == 'dense': emit('4439d8'); branch('reject4',0x85)
    mov(0,component_address+0x14); emit('49394258'); branch('reject5',0x85)
    emit('41837a6008'); branch('reject5',0x85)
    emit('41837a6400'); branch('reject5',0x85)
    if kind == 'mover':
        emit('83fa08'); branch('reject8',0x83); emit('4183f808'); branch('reject8',0x83)
        emit('4439c2'); branch('body',0x84)
        mov(0,storage_address); emit('4a8b04c0 4885c0'); branch('reject6',0x84)
        emit('448b5008 4585d2'); branch('reject6',0x84)
        mov(9,component_address+0x14); emit('4531db 31c9'); label('scan')
        emit('438b04d9 4439d0'); branch('next',0x85)
        emit('473944d904'); branch('reject8',0x85); emit('ffc1')
        label('next'); emit('41ffc3 4183fb08'); branch('scan',0x82)
        emit('83f901'); branch('reject7',0x85); mov(1,component_address)
    else:
        emit('4885c9'); branch('reject6',0x84)
        if kind == 'dense': emit('4885d2'); branch('reject6',0x84)
        emit('448b4108 4585c0'); branch('reject6',0x84)
        mov(9,component_address+0x14); emit('4531d2 4531db')
        if kind == 'remove' or classification: emit('baffffffff')
        label('scan'); emit('438b04d9 4439c0')
        if kind == 'remove' or classification:
            branch('nonmatch',0x85); emit('83faff'); branch('reject7',0x85)
            emit('43837cd90408'); branch('reject8',0x83)
            emit('438b54d904'); label('nonmatch')
        else: branch('reject7',0x84)
        emit('85c0'); branch('next',0x85); emit('41ffc2')
        label('next'); emit('41ffc3 4183fb08'); branch('scan',0x82)
        mov(0,component_address); emit('8b4008 4101c2 4183fa08'); branch('reject9',0x85)
        if kind == 'remove' or classification:
            emit('39c2'); branch('reject8',0x83)
            if not classification:
                mov(11,component_address); emit('413b530c'); branch('remove_ready',0x83)
                emit('413b430c'); branch('reject4',0x85); label('remove_ready')
            mov(0,storage_address); emit('48390cd0'); branch('reject6',0x85)
            if classification:
                mov(11,game_base+0x3483C34);emit('453b03');branch('reject6',0x84)
                mov(11,component_address);emit('413b530c');branch('reject8',0x83)
                emit('458b4310 4439c2');branch('reject4',0x82 if kind=='enter' else 0x83)
                if kind=='leave':emit('41ffc8')
                mov(0,storage_address);emit('4a8b04c0 4885c0');branch('reject6',0x84)
                emit('448b5008 4585d2');branch('reject6',0x84)
                mov(11,game_base+0x3483C34);emit('453b13');branch('reject6',0x84)
                mov(9,component_address+0x14);emit('4531db 31d2');label('boundary_scan')
                emit('438b04d9 4439d0');branch('boundary_next',0x85)
                emit('473944d904');branch('reject8',0x85);emit('ffc2')
                label('boundary_next');emit('41ffc3 4183fb08');branch('boundary_scan',0x82)
                emit('83fa01');branch('reject7',0x85);emit('4889ca')
    branch('body')
    for reason in range(1,10):
        label('reject'+str(reason)); emit(b'\x41\xba'+struct.pack('<I',reason)); branch('external')
    while len(out) % 16: emit('90')
    label('body'); body_offset = len(out)
    source = bytes.fromhex(f['body_hex']); mapping = {}; patches = []
    register_id = {'rax':0,'rcx':1,'rdx':2,'rbx':3,'rsp':4,'rbp':5,'rsi':6,'rdi':7,
                   **{'r'+str(i):i for i in range(8,16)}}
    for i in decode(source,f['start']):
        mapping[i.address] = len(out); raw = bytearray(i.bytes)
        array = None
        for operand in i.operands:
            if operand.type != X86_OP_MEM: continue
            m = operand.mem; base,index = i.reg_name(m.base),i.reg_name(m.index)
            bound = 'rbp' if classification else ('rcx' if i.address < 0x666076 else 'r11') if kind == 'mover' else 'rbx'
            if bound not in (base,index) or not (m.index or (classification and i.mnemonic=='lea' and m.disp==0x1D8)): continue
            if m.disp == 0x70: array=(bound,storage_address-0x70,'pointer')
            elif classification and m.disp == 0x90: array=(bound,storage_address+0x40-0x90,'byte')
            elif 0x98 <= m.disp <= 0xD8: array=(bound,storage_address+0x50-0x98,'primary')
            elif 0x1D8 <= m.disp <= 0x208: array=(bound,storage_address+0x2D0-0x1D8,'secondary')
        if array:
            name,value,field = array
            need(i.reg_name(i.operands[0].reg) != name if i.operands[0].type != X86_OP_MEM else True, 'array overwrites its own base')
            mov(register_id[name],value); emit(raw); mov(register_id[name],component_address)
            patches.append({'rva':hex(i.address),'array':field,'base':name}); continue
        if i.address in (0x51AC08,0x51AC89):
            need(raw[-1] == 4 and i.mnemonic == 'cmp', 'capacity pin changed'); raw[-1] = 8
        if i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL):
            need(i.operands[0].type == X86_OP_IMM, 'unexpected indirect transfer')
            target = i.operands[0].imm
            if i.mnemonic == 'call': emit('e8'); fixes.append((len(out),target)); emit(bytes(4))
            else: branch(target, None if i.mnemonic=='jmp' else raw[1] if raw[0]==0x0F else raw[0]+0x10)
        else:
            for operand in i.operands:
                if operand.type==X86_OP_MEM and operand.mem.base==X86_REG_RIP:
                    target=game_base+i.address+i.size+operand.mem.disp
                    struct.pack_into('<i',raw,i.disp_offset,target-(code_address+len(out)+i.size))
            emit(raw)
    mapping[f['end']] = len(out)
    need(len(patches)=={'mover':21,'append':6,'dense':6,'remove':1,'enter':35,'leave':37}[kind], 'array coverage changed')
    for at,target in fixes:
        dest = reject_address if target=='external' else code_address+labels[target] if isinstance(target,str) else (
            code_address+mapping[target] if target in mapping else move_code_address if target==0x665FE0 else game_base+target)
        struct.pack_into('<i',out,at,dest-(code_address+at+4))
    code_bytes = len(out)
    while len(out)%4: emit('00')
    leaf = len(out); emit('01000000'); unwind_map = {}; unwind_offsets = []
    for fragment in f['fragments']:
        unwind_map[fragment['unwind_rva']] = len(out); unwind_offsets.append(len(out)); emit(bytes.fromhex(fragment['unwind_hex']))
    for fragment,offset in zip(f['fragments'],unwind_offsets):
        original=bytes.fromhex(fragment['unwind_hex']); start=fragment['start']; prolog=original[1]
        # Classification inserts array rebinding inside a conditional prologue;
        # relocate its instruction-end offsets as well as its fragment ranges.
        if classification:
            def offset_for(old):
                need(start+old in mapping,'unwind offset is not an instruction boundary')
                value=mapping[start+old]-mapping[start];need(0<=value<=255,'unwind offset overflow');return value
            out[offset+1]=offset_for(prolog);at=4
            while at<4+original[2]*2:
                operation=original[at+1]&15;need(operation in (0,2,4),'unexpected classification unwind operation')
                out[offset+at]=offset_for(original[at]);at+=4 if operation==4 else 2
        else:
            need(out[mapping[start]:mapping[start]+prolog] == source[start-f['start']:start-f['start']+prolog], 'prologue changed')
        if original[0] >> 3 & 4:
            chain=4+((original[2]+1)&~1)*2; begin,end,uw=struct.unpack_from('<III',original,chain)
            struct.pack_into('<III',out,offset+chain,mapping[begin],mapping[end],unwind_map[uw])
    table_offset=len(out); rows=[(0,body_offset,leaf)]+[(mapping[x['start']],mapping[x['end']],uw) for x,uw in zip(f['fragments'],unwind_offsets)]
    for row in rows: emit(struct.pack('<III',*row))
    need(len(out)<=4096, 'component image overflow')
    return {'image':bytes(out),'code_bytes':code_bytes,'body_offset':body_offset,'table_offset':table_offset,
            'unwind_offset':leaf,'function_count':len(rows),'array_patches':patches,'instruction_map':mapping}
