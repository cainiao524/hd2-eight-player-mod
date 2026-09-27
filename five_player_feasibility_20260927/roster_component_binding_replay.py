"""Offline component-239 ABI, creation flags, and network-index property bridge.

The callback registration table is independently documented by the callback
writer investigation. This replay verifies the dispatch ABI, its adjacent
roster wrapper, and the exact caller-proven leaf producing the index property.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from spawn_resource_identity_replay import FILES, murmur64a

GROUPS = [
    ('creation_flag_producer_and_shared_parameter',
     'Entry R9 params becomes RBP. record+14 is initialized to 0, then 1 iff params byte0 is nonzero. The same pointer is forwarded to both callback stages.',
     [0xFDC172, 0xFDC1B8, 0xFDC1BB, 0xFDC1C3, 0xFDC1C6, 0xFDC1C9,
      0xFDC1CD, 0xFDC1D1, 0xFDC1D5, 0xFDC1D7, 0xFDC250, 0xFDC254,
      0xFDC257, 0xFDC25A, 0xFDC2A0, 0xFDC2AA, 0xFDC2AD, 0xFDC2B1]),
    ('local_player_creation_sets_flag',
     'Known local-peer/index-gated caller sets word at rsp+48 to 1, copies its first 16 bytes to creation params rbp+2B0, then passes that pointer as R9 to FDC140 with player resource hash.',
     [0x1086212, 0x1086228, 0x1086238, 0x1086460, 0x1086469,
      0x1086830, 0x1086837, 0x1086846, 0x108684E, 0x1086861,
      0x10868BF, 0x10868C2, 0x10868C9, 0x10868CC, 0x10868D7]),
    ('first_stage_roster_add_abi',
     'First callback stage passes RCX=entity record and RDX=creation params. The 540920 inline roster add takes exactly these parameters; registration slot identity is supplied by the separate callback writer evidence.',
     [0x581348, 0x581353, 0x581366, 0x58140A, 0x58140E, 0x58141B, 0x58141E,
      0x581421, 0x54092A, 0x540931, 0x540934, 0x54093C, 0x54094C, 0x540957,
      0x540968, 0x54097B, 0x540A01, 0x540A0D, 0x540A24, 0x540A2C]),
    ('property_stage_wrapper_and_abi',
     '58152F calls with entity record, params, output array, count pointer, allocator pointer. Wrapper540AE0 shifts output to R9, count to stack arg5, allocator to stack arg6, and directly calls60C640; its R8 value is not consumed by this callee before overwrite.',
     [0x58142D, 0x581430, 0x581436, 0x581500, 0x581505, 0x581509, 0x581516, 0x58151B, 0x58151E,
      0x581523, 0x581528, 0x58152B, 0x58152F,
      0x540AE0, 0x540AE4, 0x540AE9, 0x540AEC, 0x540AF1, 0x540AF6, 0x540AF9,
      0x60C658, 0x60C664, 0x60C667, 0x60C66E, 0x60C670, 0x60C68E,
      0x60C6A9, 0x60C6AD, 0x60C6B5, 0x60C878,
      0x60C6C9, 0x60C6CE, 0x60C6D3, 0x60C6D6, 0x60C6DA, 0x60C6DF,
      0x60C6E4, 0x60C6E7, 0x60C6EB, 0x60C6EE]),
    ('roster_parallel_record_property_build',
     'The callee allocates32 bytes and writes eight values both to roster ordinal*32+3A8 and the buffer, then appends eight16-byte descriptors. Descriptor type codes are preserved numerically; their external SDK meanings are not assumed.',
     [0x60C6F2, 0x60C6FD, 0x60C703, 0x60C705, 0x60C708, 0x60C710, 0x60C719, 0x60C71E,
      0x60C720, 0x60C728, 0x60C730, 0x60C738, 0x60C741, 0x60C74A,
      0x60C74C, 0x60C754, 0x60C75C, 0x60C764, 0x60C76D, 0x60C776,
      0x60C778, 0x60C77D, 0x60C784, 0x60C78B, 0x60C793, 0x60C79C, 0x60C7A5,
      0x60C7A7, 0x60C7AF, 0x60C7B7, 0x60C7BF, 0x60C7C8, 0x60C7D1,
      0x60C7D3, 0x60C7DB, 0x60C7E3, 0x60C7EB, 0x60C7F4, 0x60C7FD,
      0x60C7FF, 0x60C803, 0x60C807, 0x60C80B, 0x60C813, 0x60C81B, 0x60C824, 0x60C82D,
      0x60C82F, 0x60C837, 0x60C83F, 0x60C847, 0x60C850, 0x60C855]),
    ('index_color_candidate_with_safe_fallback_and_separate_player_count',
     '6054F0 resolves entityID to roster ordinal. It reads record+3B4 network index; <4 selects three color-like components from a readonly four-row palette; >=4 supplies1.0 for all three. Components are scaled by255. Only mode==1 invokes an unresolved indirect endpoint. Control then continues. A later independent call passes literal player_count and roster+84 count to another API slot.',
     [0x605521, 0x605530, 0x605539, 0x605556, 0x605579, 0x605585, 0x60567A,
      0x6056B2, 0x6056B4, 0x60574C, 0x605754, 0x605758, 0x605760, 0x605767,
      0x60576A, 0x60576C, 0x60576F, 0x605776, 0x60577A, 0x60577F, 0x605785,
      0x605788, 0x60578E, 0x605792, 0x605794, 0x605797, 0x60579A, 0x60579D,
      0x6057A4, 0x6057AC, 0x6057B0, 0x6057B4, 0x6057B8, 0x6057BE, 0x6057C4,
      0x6057CA, 0x6057CC, 0x6057D3, 0x6057D8, 0x6057DB, 0x6057DF, 0x6057E6,
      0x6057E8, 0x6058ED, 0x6058F3, 0x6058F8, 0x6058FF, 0x605906, 0x60590C,
      0x605910]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(out)
    im = Image(args.evidence)
    groups = []
    for name, provenance, sites in GROUPS:
        pins = []
        for site in sites:
            ins = im.instruction(site)
            if ins is None:
                raise ValueError('Not a captured unwind instruction boundary: '+hex(site))
            pin = row(ins)
            pin['root'] = hex(im.root(site)[0])
            pin['rip_memory_targets'] = [hex(ins.address+ins.size+op.mem.disp)
                                         for op in ins.operands
                                         if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
            pins.append(pin)
        groups.append({'name':name, 'base_provenance':provenance, 'anchors':pins})
    # A real E8 call at a proven boundary establishes this leaf's entry. Decode
    # through both RET paths, rather than truncating at the first return.
    call = im.instruction(0x60C778)
    if call.mnemonic != 'call' or call.operands[0].type != X86_OP_IMM or call.operands[0].imm != 0x134F190:
        raise ValueError('Leaf entry proof changed')
    start, end = 0x134F190, 0x134F1EC
    raw = im.read(start, end-start)
    leaf = list(im.md.disasm(raw,start))
    starts = {ins.address for ins in leaf}
    if sum(ins.size for ins in leaf) != len(raw) or sum(ins.mnemonic=='ret' for ins in leaf) != 2:
        raise ValueError('Incomplete two-path leaf decode')
    for ins in leaf:
        if ins.mnemonic.startswith('j') and ins.operands[0].type == X86_OP_IMM:
            if ins.operands[0].imm not in starts:
                raise ValueError('Leaf branch escapes proven boundaries')
    # Follow FileDiver's Thin() definition: upper32 of Murmur64A.
    for relative,digest in FILES.items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != digest:
            raise ValueError('Pinned hash/name source changed: '+relative)
    if murmur64a(b'hello, world!') != 0xD18ABE154A2A9637 or murmur64a(b'hello, world!!!!') != 0x2F9DEA7BD39B9F7D:
        raise ValueError('Hash vectors failed')
    if im.read(0x2260E34,6) != b'index\0' or murmur64a(b'index') >> 32 != 0xB03B8BCE:
        raise ValueError('Property name hash mismatch')
    descriptors = []
    for n, key in enumerate([0xF27C68E,0xCD889DBC,0x86C3722,0xB03B8BCE,0x7ED6949C,0xEBEE098F,0xBD74FB92,0x83C8F804]):
        descriptors.append({'ordinal':n,'hash':hex(key),'type_code':1 if n<4 else 2,
                            'roster_field_offset':hex(0x3A8+n*4),'temporary_buffer_offset':n*4,
                            'initial_value':'local network index from 0x134f190' if n==3 else ('0x7fff' if n==0 else 0),
                            'name_hash_match':'index' if n==3 else None})
    palette_raw = im.read(0x213F4E0,64)
    palette_values = struct.unpack('<16f',palette_raw)
    fallback_raw = im.read(0x23C6D70,4)
    scale_raw = im.read(0x23C79AC,4)
    fallback,scale = struct.unpack('<f',fallback_raw)[0],struct.unpack('<f',scale_raw)[0]
    if fallback != 1.0 or scale != 255.0 or im.read(0x22473C8,13) != b'player_count\0':
        raise ValueError('Palette scalar / literal changed')
    def f32(value):
        return struct.unpack('<f',struct.pack('<f',value))[0]
    palette_rows = []
    for index in range(4):
        values = list(palette_values[index*4:index*4+4])
        palette_rows.append({'network_index':index,'raw_floats':values,
                             'three_output_components_float32':[f32(v*scale) for v in values[1:]]})
    readonly = [
        {'name':'four_palette_rows','rva':'0x213f4e0','bytes':palette_raw.hex(),'sha256':hashlib.sha256(palette_raw).hexdigest()},
        {'name':'fallback_scalar','rva':'0x23c6d70','bytes':fallback_raw.hex(),'value':fallback},
        {'name':'scale_scalar','rva':'0x23c79ac','bytes':scale_raw.hex(),'value':scale},
        {'name':'player_count_literal','rva':'0x22473c8','bytes':im.read(0x22473C8,13).hex(),'text':'player_count'},
    ]
    result = {'source_sha256':EXPECTED, 'capture_identity_sha256':im.report['capture_sha256'],
              'groups':groups,
              'proven_leaf':{'entry':hex(start),'end_exclusive':hex(end),'entry_proof_call':'0x60c778',
                             'sha256':hashlib.sha256(raw).hexdigest(),'instructions':[row(ins) for ins in leaf],
                             'behavior':'global347CEF0 confirmed-peer lookup by owner backpointer local peer ID -> stored network index; FFFFFFFF if absent'},
              'descriptors':descriptors,
              'bounded_index_palette_consumer':{
                  'readonly':readonly,'rows':palette_rows,'index_ge_four_output':[f32(fallback*scale)]*3,
                  'output_buffer_order':['table_float1_or_fallback','table_float2_or_fallback','table_float3_or_fallback'],
                  'color_classification':'Strong RGB-palette correspondence; exact destination surface / peripheral is not identified.',
                  'indirect_color_call':{'site':'0x6057e6','pointer_steps':['api=qword[global3326308]','first_table=qword[api]','nested_table=qword[first_table+0x10]','target=qword[nested_table]'],'rcx':'qword[global347D6A0]','rdx':'address of three float32 components','guard':'dword[global347D620]==1'},
                  'separate_named_count_call':{'site':'0x605910','pointer_steps':['api=qword[global3326308]','table=qword[api+0x10]','target=qword[table+0x480]'],'rcx':'player_count literal','edx':'roster+0x84 count'},
                  'index_ge_four_branch_rejects_join':False,'scope':'No out-of-range palette access at index4..7, no early return from this branch; other parts of function and global mod requirements remain separate.'},
              'name_match':{'name':'index','thin_hash':'0xb03b8bce','readonly_rva':'0x2260e34',
                            'algorithm':'upper32(Murmur64A(name))','source_sha256':FILES,'uniqueness_proven':False},
              'runtime_verified':False,
              'limits':[
                  'Static callback slot registration and resource component lists are maintained in separate evidence; this script does not inspect live table values.',
                  'This proves network index stored in roster parallel record+0xC and property output, not network-index equality with roster ordinal.',
                  'For the inspected local-player creation path the flag is1; global semantic names such as local/authority are not inferred for every caller.',
                  'The eight property descriptors are fields of one entity, not eight players or a capacity.',
                  'The color-like output destination, platform mode meaning, and player_count API semantics are unresolved indirect interfaces; no UI/controller naming is asserted.',
                  '60CA80/60CBA0 have ABI-shifted equivalent inline bodies, but their own dispatch remains unproven.',
                  'No process read, game function execution, patch, install, or multiplayer verification.']}
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'anchors':sum(len(g['anchors']) for g in groups),'leaf_instructions':len(leaf),'leaf_bytes':len(raw)}))


if __name__ == '__main__':
    main()
