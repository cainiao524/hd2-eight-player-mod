"""Replay only saved HD2 capture: proven roster network-index downstream uses.

All addresses are game.dll RVAs. This program has no process or network API.
It validates the saved capture hashes with inspect_capture.Image and resolves
instruction starts from the captured unwind table before producing evidence.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP


# End-exclusive ranges must begin and end on proven instruction boundaries.
# Keeping whole short blocks preserves guards, arithmetic and stores together.
GROUPS = [
    ('state_game_parent_identity',
     'AC5D40 saves entry RCX as parent P, associates StateGame / On Enter literals, registers (P, B5) with registry3326E68+24F8. B61E60 dispatches that exact table/tag to AD4520, which saves entry RCX as R13 and passes P+50 to FFD8C0.',
     [(0xAC5D68, 0xAC5DAF), (0xAC5E42, 0xAC5E65),
      (0xB61E6A, 0xB61EB5), (0xAD455E, 0xAD4579), (0xAD488A, 0xAD488F), (0xAD4C16, 0xAD4C2A),
      (0xAB3123, 0xAB3147)]),
    ('tag_da_embedded_four_records_and_parallel_array',
     'FFD8C0 saves entry S=P+50 and registers tag DA. Its initialization loop uses S+80 with stride90 and counter<4; a parallel dword pointer begins at S+70 and advances4 once per iteration.',
     [(0xFFD936, 0xFFD97B), (0xFFD9E7, 0xFFDA50),
      (0xFFE231, 0xFFE2EA), (0xFFE359, 0xFFE3D6)]),
    ('tag_da_unchecked_network_index_writes',
     'R9=global3326468; ordinal ranges over roster+84. Each record at ordinal*20+3B4 supplies network index n. Four stores target S+n*90+88/8C/90/89 with no index<4 or sentinel guard in this block.',
     [(0xFFE3D6, 0xFFE443)]),
    ('same_parent_used_fields_hit_at_index_four',
     'Within AC5D40, R12 is the registered parent P. P+318 receives qword owner+10E8. P+320 receives a 16-byte bitset assembled by BTS and POR. The unchecked DA stores for n=4 hit these precise bytes.',
     [(0xAC67EB, 0xAC685F)]),
    ('bounded_normalized_vector_caller',
     'ACA400 preserves entry RCX in rsp+70, then passes first roster record network index as R8D to ACF1F0. The index is sourced directly from global3326468+3B4, not a same-offset guess.',
     [(0xACA422, 0xACA430), (0xACA57B, 0xACA597)]),
    ('bounded_normalized_vector_with_default',
     'ACF1F0 takes unsigned R8D<4 before using n*90 storage. Valid fields form a normalized three-float vector. Otherwise it copies a 12-byte default from uncaptured global32A8E60/68 and returns the output pointer.',
     [(0xACF1F0, 0xACF21E), (0xACF223, 0xACF244),
      (0xACF244, 0xACF262), (0xACF280, 0xACF289),
      (0xACF29E, 0xACF2C9), (0xACF2E5, 0xACF303)]),
    ('bounded_state_operation_roster_map_caller',
     '12A98D0 obtains roster R10 from global3326468, resolves a peer-associated entity ID through roster+D0/D8/DC/E0 map to ordinal, reads ordinal*20+3B4, and calls ACF420 with that index and outer3326340+1FA08. The outer+1FA08 parent constructor call is pinned above.',
     [(0x12A9BD9, 0x12A9C7A), (0x12A9C7A, 0x12A9CCB),
      (0x12A9E93, 0x12A9EB5)]),
    ('bounded_state_operation_false_at_four',
     'ACF420 maps parent to S=P+50. Index>=4 returns AL=0 before accessing slot storage; valid index computes slot S+80+n*90, updates vector/state fields and invokes downstream functions. The caller proceeds without testing AL, so this is operation denial, not proof of join rejection.',
     [(0xACF436, 0xACF475), (0xACF4DF, 0xACF558),
      (0xACF558, 0xACF570)]),
    ('roster_map_to_32bit_mask_consumer',
     '1277920 looks up entity ID through the same roster map, obtains ordinal, reads record+3B4 network index, then tests that bit in dword masks from another system global33269C0. It excludes FFFFFFFF but has no four bound. Bits4..7 fit this consumer width; producer behavior remains unknown.',
     [(0x1277945, 0x12779BD), (0x12779CE, 0x1277A3C)]),
    ('roster_map_direct_index_getter',
     '606AD0 explicitly loads global3326468 and its map, obtains ordinal, returns dword[roster+ordinal*20+3B4]. Missing map result returns FFFFFFFF; no four-index clamp appears in this getter.',
     [(0x606AE4, 0x606B75)]),
    ('additional_unbounded_array_writer_capacity_not_proven',
     '7275D6 reads the index from global3326468 roster loop and passes it as EDX to14335F0; the callee writes two float fields to destination+index*298+80E24 before any range test. Destination is caller RSI+4C8260. Its capacity and UI semantics are not proven, so this is retained as one concrete unresolved array consumer, not a confirmed four-slot collision.',
     [(0x72757E, 0x727610), (0x14335F0, 0x143363D)]),
]


def rip_targets(ins):
    return [ins.address + ins.size + op.mem.disp for op in ins.operands
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]


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
    pins = {}
    for name, proof, ranges in GROUPS:
        blocks = []
        for start, end in ranges:
            if im.instruction(start) is None:
                raise ValueError('Unproven start boundary '+hex(start))
            raw = im.read(start, end-start)
            decoded = list(im.md.disasm(raw, start))
            if sum(i.size for i in decoded) != len(raw):
                raise ValueError('Partial instruction at end '+hex(end))
            entries = []
            for ins in decoded:
                checked = im.instruction(ins.address)
                if checked is None or checked.bytes != ins.bytes:
                    raise ValueError('Not an unwind-established boundary '+hex(ins.address))
                p = row(ins)
                p['root'] = hex(im.root(ins.address)[0])
                p['rip_memory_targets'] = [hex(t) for t in rip_targets(ins)]
                entries.append(p)
                pins[ins.address] = ins
            blocks.append({'start':hex(start), 'end_exclusive':hex(end),
                           'sha256':hashlib.sha256(raw).hexdigest(), 'instructions':entries})
        groups.append({'name':name, 'base_provenance':proof, 'blocks':blocks})

    # Checks on claims that combine separate blocks.
    for site, target in [(0xAC5D96,0x3326E68),(0xB61E6A,0x3326E68),
                         (0xFFD936,0x3326E68),(0xFFE3D6,0x3326468),
                         (0xACA57B,0x3326468),(0x12A9BE0,0x3326468),
                         (0x127796B,0x3326468),(0x606AEA,0x3326468),
                         (0x72757E,0x3326468),(0x7275B1,0x3326468),
                         (0x7275FF,0x3326468),(0x1277A0E,0x33269C0),
                         (0xACF2E5,0x32A8E68),(0xACF2EB,0x32A8E60)]:
        if target not in rip_targets(pins[site]):
            raise ValueError('RIP provenance changed '+hex(site))
    for site,target in [(0xAD4C25,0xFFD8C0),(0xB61EB0,0xAD4520),
                        (0xACA592,0xACF1F0),(0x12A9CAC,0xACF420),
                        (0x7275FA,0x14335F0),(0xAB3142,0xAC5D40)]:
        ins = pins[site]
        if ins.mnemonic != 'call' or ins.operands[0].type != X86_OP_IMM or ins.operands[0].imm != target:
            raise ValueError('Call edge changed '+hex(site))
    for site,asm in {
        0xAD4C1A:'lea rcx, [r13 + 0x50]',
        0xFFDA04:'lea r15, [r12 + 0x80]',
        0xFFDA3E:'lea rax, [r12 + 0x70]',
        0xFFE3B6:'add r15, 0x90',
        0xFFE3CC:'cmp r12d, 4',
        0xFFE3FF:'mov ecx, dword ptr [rax + r9 + 0x3b4]',
        0xFFE415:'mov byte ptr [r12 + rdx*8 + 0x88], 0',
        0xFFE41E:'mov dword ptr [r12 + rax*8 + 0x8c], 0x40a00000',
        0xFFE42A:'mov dword ptr [r12 + rdx*8 + 0x90], r14d',
        0xFFE432:'mov byte ptr [r12 + rdx*8 + 0x89], r10b',
        0xAC67F2:'mov qword ptr [r12 + 0x318], rax',
        0xAC6856:'movups xmmword ptr [r12 + 0x320], xmm0',
        0xACF1F9:'cmp r8d, 4',
        0xACF43F:'cmp edx, 4',
        0xACF444:'xor al, al',
        0x1277A2F:'bt eax, r8d',
    }.items():
        if pins[site].mnemonic+' '+pins[site].op_str != asm:
            raise ValueError('Critical instruction changed '+hex(site))

    strings = []
    for addr,expected in [(0x22549C0,b'StateGame\0'),(0x22549D0,b'On Enter\0'),
                          (0x2254EC0,b'on_synchronized_tasks_done\0')]:
        raw = im.read(addr,len(expected))
        if raw != expected:
            raise ValueError('Debug literal changed '+hex(addr))
        strings.append({'rva':hex(addr),'text':raw[:-1].decode(),
                        'bytes':raw.hex(),'sha256':hashlib.sha256(raw).hexdigest()})
    collisions = []
    for site,off,width,value in [(0xFFE415,0x88,1,0),(0xFFE41E,0x8C,4,'5.0f'),
                                (0xFFE42A,0x90,4,0),(0xFFE432,0x89,1,'saved boolean')]:
        parent_offset = 0x50+4*0x90+off
        collisions.append({'store_rva':hex(site),'index':4,'write_width':width,
                           'parent_offset':hex(parent_offset),'value':value,
                           'overlaps':'parent+318..31F qword' if parent_offset<0x320 else 'parent+320..32F bitset'})
    result = {
        'source_sha256':EXPECTED,'capture_identity_sha256':im.report['capture_sha256'],
        'scope':'Offline fixed code/readonly/unwind capture only. No process query/read or execution.',
        'groups':groups,'debug_literals':strings,
        'tag_da_capacity':{
            'parent_tag':'0xb5','parent_debug_name':'StateGame','child_tag':'0xda',
            'child_base':'parent+0x50','records':'child+0x80+index*0x90',
            'initialized_record_count':4,'record_size':0x90,
            'four_records_parent_range':['0xd0','0x310'],
            'eight_records_same_base_parent_range':['0xd0','0x550'],
            'parallel_dword_array_child_range':['0x70','0x80'],
            'parallel_dword_array_eight_same_base_child_range':['0x70','0x90'],
            'index_four_collisions':collisions,
            'additional_logical_record_payload_for_eight':4*0x90+4*4,
            'payload_calculation_excludes':'alignment, other four-slot consumers, relocation metadata and unrelated subsystem allocations; this is not a proven minimal allocation size',
            'required_design':'relocate or re-layout both arrays and update their consumers; changing cmp4 to8 in place corrupts parent fields and overlaps the parallel array with slot0',
            'runtime_invocation_with_index_ge_four_observed':False},
        'classification':[
            {'site':'0xffe3ff ->0xffe415/41e/42a/432','kind':'confirmed static overlapping writes for index4','required_for_equivalent_eight_player_state':True},
            {'site':'0x12a9c80 ->0xacf420','kind':'operation returns false for index>=4','join_rejection_proven':False,'action':'extend only with storage and dependent operation audit'},
            {'site':'0xaca58b ->0xacf1f0','kind':'safe bounded default vector','join_rejection_proven':False,'action':'may temporarily retain fallback; per-player equivalent vector behavior needs extension','default_value_known':False},
            {'site':'0x1277a06 ->0x1277a2f','kind':'32-bit register mask test','bits4_to7_representable':True,'action':'no consumer-width change proven necessary; producer still unverified'},
            {'site':'0x606b6b','kind':'returns network index scalar','four_limit_present':False,'action':'preserve scalar behavior, update record address if roster layout moves'},
            {'site':'0x7275d6 ->0x143362f','kind':'unchecked indexed two-float write','destination_capacity_proven':False,'ui_semantics_proven':False,'action':'one concrete remaining capacity audit; do not assert another four-slot collision'}],
        'runtime_verified':False,
        'limitations':[
            'The captured program was not invoked by this replay. A fifth-player execution and exact visible symptom were not observed.',
            'StateGame is a captured debug literal associated with parent operations. No specific class name is assigned to tagDA.',
            'The vector default at32A8E60/68 is outside the capture; its numeric value is unknown.',
            'The mask producer and the destination capacity/semantics of14335F0 are not established here.',
            'This is a selected proof of concrete index uses, not an exhaustive field-xref audit. Same displacements on other objects were excluded.',
            'No join-success inference, no new probe, no game patch; callback239 wrappers and previous6054F0 palette investigation remain separate.']}
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(out),'groups':len(groups),'unique_instructions':len(pins),
                      'evidence_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
