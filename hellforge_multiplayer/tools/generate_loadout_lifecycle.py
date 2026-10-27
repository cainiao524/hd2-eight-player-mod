"""Relocate four saved lifecycle bodies and an isolated bank initializer.

The constructor's player records/widgets move together. Nested widget fields,
including the four choices at 189D050, retain their original layout. No hashes,
receipts, runtime discovery or hook publication are produced.
"""
import argparse
import json
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PROJECT = Path(__file__).resolve().parents[1]
CAPTURE = PROJECT.parent / 'evidence/existing-code-evidence-25480438'
HEADER = PROJECT / 'mod/src/ep_loadout_lifecycle_template.h'
STARTS = (0x14A17E0, 0x1467330, 0x1467720, 0x1470A40)
TRANSITION_UNWIND = bytes.fromhex('192f0d00208806001b780700176808001364150013341400130112000c700000')
GS_HANDLER = 0x21044A0
# RVA: (expected instruction, replacement bytes, parameter, addend, operand offset)
PATCHES = {
    0x14A17F4: ('mov edi, 4', b'\xbf'+bytes(4), 5, 0, 1),
    0x14A17F9: ('lea rdx, [rcx + 0x10]', b'\x48\xba'+bytes(8), 3, 0, 2),
    0x14A1943: ('lea rsi, [rbx + 0x53a78]', b'\x48\xbe'+bytes(8), 4, 0, 2),
    0x14674B4: ('lea rbx, [r14 + 0x57fc0]', b'\x48\xbb'+bytes(8), 4, 0x4548, 2),
    0x14674BB: ('mov edi, 4', b'\xbf'+bytes(4), 5, 0, 1),
    0x1467743: ('add rbx, 0x55a20', b'\x48\xbb'+bytes(8), 4, 0x1FA8, 2),
    0x146774A: ('mov edi, 4', b'\xbf'+bytes(4), 5, 0, 1),
    0x1470B48: ('lea rbx, [rsi + 0x53a78]', b'\x48\xbb'+bytes(8), 4, 0, 2),
    0x1470B4F: ('mov edi, 4', b'\xbf'+bytes(4), 5, 0, 1),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Capture:
    """Read only explicitly selected bytes from the existing offline capture."""
    def __init__(self):
        self.report = json.loads((CAPTURE/'capture-report.json').read_text())
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True
        u = next(x for x in self.report['ranges'] if x['label'] == 'unwind')
        self.functions = list(struct.iter_unpack('<III', self.read(u['rva'], u['size'])))

    def read(self, address, size):
        data = bytearray()
        with (CAPTURE/'captured-data.bin').open('rb') as stream:
            while size:
                chunk = next(x for x in self.report['chunks'] if x['kind'] == 'DATA'
                             and x['rva'] <= address < x['rva']+x['size'])
                n = min(size, chunk['rva']+chunk['size']-address)
                stream.seek(chunk['file_offset']+address-chunk['rva'])
                part = stream.read(n)
                need(len(part) == n, 'Truncated saved capture')
                data += part
                address += n
                size -= n
        return bytes(data)


def build():
    capture = Capture()
    blob, fixes, functions, metadata = bytearray(), [], [], []
    mapping, entries, seen, sources = {}, [], set(), []
    branches = []
    for start in STARTS:
        begin, end, unwind = next(f for f in capture.functions if f[0] == start)
        source = capture.read(begin, end-begin)
        head = capture.read(unwind, 4)
        need(head[0] == (25 if start == 0x1470A40 else 1) and head[3] == 0,
             'Unsupported lifecycle exception contract')
        uw = capture.read(unwind, 4+((head[2]+1)&~1)*2)
        if start == 0x1470A40:
            need(uw == TRANSITION_UNWIND and capture.read(unwind+len(uw),8) == struct.pack('<II',GS_HANDLER,80),
                 'Unsupported transition GS contract')
            uw += bytes(4)+struct.pack('<I',80)
        blob += b'\xcc' * (-len(blob) % 16)
        entry = len(blob)
        entries.append(entry)
        # RCX is the original screen; reject foreign objects before any save,
        # screen read, or storage write. The external rejection target must not return.
        blob += b'\x49\xba'+bytes(8)+b'\x4c\x39\xd1\x0f\x85'+bytes(4)
        fixes += [(entry+2, 0, 2, 1, 0), (entry+15, entry+19, 6, 0, 0)]
        body = len(blob)
        functions.append((entry, body, b'\x01\x00\x00\x00'))
        insns = list(capture.md.disasm(source, begin))
        need(insns and insns[-1].address+insns[-1].size == end, 'Incomplete lifecycle decode')
        for ins in insns:
            at = len(blob)
            mapping[ins.address] = at
            if ins.address in PATCHES:
                expected, code, key, add, operand = PATCHES[ins.address]
                need(ins.mnemonic+' '+ins.op_str == expected, 'Unexpected lifecycle operand')
                seen.add(ins.address)
                blob += code
                fixes.append((at+operand, 0, key, 2 if key == 5 else 1, add))
            elif ins.address==0x1470ab7:
                need(ins.mnemonic+' '+ins.op_str=='call 0x146ac60','Changed lifecycle state link')
                blob+=b'\xe8'+bytes(4);fixes.append((at+1,len(blob),7,0,0))
            elif (ins.mnemonic == 'call' or ins.mnemonic.startswith('j')) and ins.operands[0].type == X86_OP_IMM:
                target = ins.operands[0].imm
                raw = bytes(ins.bytes)
                if raw[0] in (0xe8, 0xe9):
                    code = raw[:1]+bytes(4)
                elif raw[0] == 0xeb:
                    code = b'\xe9'+bytes(4)
                elif 0x70 <= raw[0] <= 0x7f:
                    code = bytes((0x0f, raw[0]+0x10))+bytes(4)
                else:
                    need(raw[:1] == b'\x0f' and 0x80 <= raw[1] <= 0x8f, 'Unsupported branch')
                    code = raw[:2]+bytes(4)
                blob += code
                if begin <= target < end:
                    branches.append((at+len(code)-4, len(blob), target))
                else:
                    fixes.append((at+len(code)-4, len(blob), 0, 0, target))
            else:
                blob += ins.bytes
                if any(o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP for o in ins.operands):
                    # RIP addressing always encodes disp32; Capstone 5 reports
                    # disp_size=2 for these 66-prefixed MOVDQA instructions.
                    need(ins.disp_offset+4 <= ins.size and
                         struct.unpack_from('<i', ins.bytes, ins.disp_offset)[0] == ins.disp,
                         'Unsupported RIP operand')
                    fixes.append((at+ins.disp_offset, len(blob), 0, 0, ins.address+ins.size+ins.disp))
            if ins.address < begin+head[1]:
                need(blob[at:] == ins.bytes and at-body == ins.address-begin, 'Prologue moved')
        functions.append((body, len(blob), uw))
        sources.append(dict(start=begin, end=end, data=source, unwind=uw, entry=entry, body=body))
    need(seen == set(PATCHES), 'Missing lifecycle replacement')
    for offset, nxt, target in branches:
        need(target in mapping, 'Branch is not an instruction boundary')
        fixes.append((offset, nxt, 1, 0, mapping[target]))
    # A retained screen must NOT go through the full constructor again. Reuse
    # only its bound-screen guard, original prologue + record initialization,
    # native per-widget construction loop, and epilogue. In particular, omit
    # ALL unrelated inline-screen member initialization and helper calls.
    # Clone relocated bytes, rebasing both operand locations and local branches;
    # original entry offsets/branches remain unchanged for existing callers.
    pieces=((entries[0],mapping[0x14a1912]),
            (mapping[0x14a1943],mapping[0x14a1965]),
            (mapping[0x14a1b29],functions[1][1]))
    blob += b'\xcc' * (-len(blob)%16)
    bank_entry=len(blob);clones=[]
    for lo,hi in pieces:
        need(lo<hi,'Empty bank-constructor segment')
        dest=len(blob);clones.append((lo,hi,dest));blob.extend(blob[lo:hi])
    def cloned_offset(old):
        selected=[dest+old-lo for lo,hi,dest in clones if lo<=old<hi]
        need(len(selected)==1,'Bank constructor branches into omitted screen initialization')
        return selected[0]
    for offset,nxt,key,kind,add in list(fixes):
        for lo,hi,dest in clones:
            if not lo<=offset<hi:continue
            need(offset+(8 if kind==1 else 4)<=hi,'Split constructor relocation')
            if nxt:need(lo<=nxt<=hi,'Split constructor instruction')
            fixes.append((dest+offset-lo,dest+nxt-lo if nxt else 0,key,kind,
                          cloned_offset(add) if key==1 else add))
    bank_body=bank_entry+sources[0]['body']-sources[0]['entry']
    functions.extend(((bank_entry,bank_body,b'\x01\0\0\0'),(bank_body,len(blob),functions[1][2])))
    bank_mapping={rva:cloned_offset(off) for rva,off in mapping.items()
                  if any(lo<=off<hi for lo,hi,dest in clones)}
    # Preserve EH/UH flags, the RSP+80 cookie, and an owned GS-handler thunk.
    blob += b'\xcc' * (-len(blob) % 16)
    handler_offset = len(blob)
    blob += b'\xe9'+bytes(4)
    fixes.append((handler_offset+1,handler_offset+5,0,0,GS_HANDLER))
    functions.append((handler_offset,len(blob),b'\x01\x00\x00\x00'))
    code_bytes = len(blob)
    blob += bytes(-len(blob) % 4)
    unwind_offset = len(blob)
    for begin, end, uw in functions:
        if uw[0] == 25:
            uw = uw[:-8]+struct.pack('<II',handler_offset,80)
        metadata.append((begin, end, len(blob)))
        blob += uw
    table_offset = len(blob)
    for row in metadata:
        blob += struct.pack('<III', *row)
    need(len(blob) <= 4096, 'Lifecycle image exceeds bounded storage')
    return dict(blob=bytes(blob), fixes=fixes, code_bytes=code_bytes, unwind_offset=unwind_offset,
                table_offset=table_offset, entries=entries, functions=metadata, sources=sources, mapping=mapping,
                handler_offset=handler_offset,bank_initializer=dict(entry=bank_entry,body=bank_body,mapping=bank_mapping))


def render(artifact):
    blob = artifact['blob']
    lines = ['// Generated from saved build 25480438 by generate_loadout_lifecycle.py.',
             '// Player loops only; all per-widget choice/resource loops remain unchanged.',
             'static const uint8_t ep_loadout_lifecycle_template[] = {']
    for off in range(0, len(blob), 16):
        lines.append('    '+','.join(f'0x{x:02x}' for x in blob[off:off+16])+',')
    lines += ['};', 'static const EpLoadoutFixup ep_loadout_lifecycle_fixups[] = {']
    lines += ['    {'+','.join(str(x) for x in f)+'},' for f in artifact['fixes']]
    lines += ['};']
    for name in ('code_bytes', 'unwind_offset', 'table_offset','handler_offset'):
        lines.append(f'static const uint32_t ep_loadout_{name} = {artifact[name]};')
    lines.append(f'static const uint32_t ep_loadout_construct_banks = {artifact["bank_initializer"]["entry"]};')
    lines.append(f'static const uint32_t ep_loadout_function_count = {len(artifact["functions"])};')
    lines += ['static const uint32_t ep_loadout_entries[] = {'+','.join(map(str, artifact['entries']))+'};', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    artifact = build()
    if args.write:
        HEADER.write_text(render(artifact), encoding='utf-8', newline='\n')
    print(json.dumps(dict(image_bytes=len(artifact['blob']),lifecycle_entries=4,bank_initializer=True,game_access=False)))
