"""Offline replay for the single roster-indexed float writer 7275FA -> 14335F0.

Reads only the previously fixed saved capture. No process/network/game APIs.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

PRIOR_SHA = 'd7098a7d698aa7daaf53e89c08b19cb01e243860f70fbba518690837baf121ee'
ROOTS = {
    0x142B990: 0x142BEB3,  # Destination initializer and adjacent member initialization.
    0x14335F0: 0x143372C,  # Complete selected writer.
    0x140C160: 0x140C1FC, # Adjacent 0x78-byte subobject initializer.
    0x140C200: 0x140C28D, # Adjacent subobject indexed-dword consumer/cleanup.
    0x142C9B0: 0x142CB57, # Destination cleanup, including adjacent 64-entry array.
    0x208AA80: 0x208AA90, # REP STOSB path of the fixed byte-fill helper.
}
WINDOWS = {
    'owner_publish_manager': (0x5687E4, 0x5687F2),
    'owner_call_manager_update': (0x571FF7, 0x572006),
    'update_manager_saved': (0x725193, 0x7251B4),
    'update_destination_and_roster_loop': (0x727500, 0x727610),
    'constructor_global_and_map_ordinal': (0x724292, 0x724344),
    'constructor_restore_indexed_offset': (0x724370, 0x724388),
    'constructor_destination_and_call': (0x7244E2, 0x724547),
    'cleanup_global_and_map_ordinal': (0x7248EE, 0x724981),
    'cleanup_destination_and_call': (0x724DEC, 0x724DFB),
    'fill_helper_large_count_path': (0x208AAA0, 0x208AAB4),
    'fill_helper_large_count_dispatch': (0x208AAB4, 0x208AAD5),
    'fill_helper_large_count_body': (0x208AAE0, 0x208ABA4),
    'parent_context_map_strings': (0x72480E, 0x72482F),
}
PINS = [0x568236, 0x57128D, 0x571290, 0x571F4A, 0x724340, 0x72435D,
        0x724361, 0x72437C, 0x7245DC, 0x7245E4, 0x7245E9,
        0x724B5F, 0x724B67, 0x724B6C]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior_raw = (HERE / 'roster_index_usage_evidence_v2.json').read_bytes()
    require(sha(prior_raw) == PRIOR_SHA, 'prior roster-index evidence changed')
    im = Image(args.evidence)
    spans, decoded = {}, {}

    def span(label, a, b, proof):
        raw = im.read(a, b-a)
        ins = list(im.md.disasm(raw, a))
        require(ins and sum(i.size for i in ins) == len(raw), 'span decode incomplete: '+label)
        for i in ins:
            independently_bounded = im.instruction(i.address)
            require(independently_bounded is not None and independently_bounded.bytes == i.bytes,
                    'instruction not on captured unwind boundary '+hex(i.address))
        decoded.update({i.address:i for i in ins})
        spans[label] = dict(start=hex(a), end_exclusive=hex(b), sha256=sha(raw), proof=proof,
                            instructions=[row(i) for i in ins])

    for entry, end in ROOTS.items():
        fs = [f for f in im.functions if entry <= f[0] < end and im.root(f[0])[0] == entry]
        require(fs and fs[0][0] == entry and fs[-1][1] == end, 'root bounds changed')
        require(all(a[1] == b[0] for a,b in zip(fs, fs[1:])), 'root fragments not contiguous')
        for f in fs:
            span(hex(f[0]), f[0], f[1], dict(kind='complete_unwind_fragment', root=hex(entry),
                                            fragment=[hex(v) for v in f]))
    for label, (a,b) in WINDOWS.items():
        require(im.instruction(a) is not None and im.instruction(b) is not None,
                'window endpoints not proven '+label)
        span(label, a,b,dict(kind='unwind_bounded_window', root=hex(im.root(a)[0])))
    pins = []
    for at in PINS:
        i = im.instruction(at)
        require(i is not None, 'pin not on boundary '+hex(at))
        decoded[at] = i
        pins.append(dict(**row(i), root=hex(im.root(at)[0])))

    semantic = [
        (0x5687E4,'lea','rax, [rbx + 0x1f7ae8]'),
        (0x571FF7,'lea','rcx, [rdi + 0x1f7ae8]'),
        (0x572001,'call','0x725160'),
        (0x7251A4,'mov','r14, rcx'),
        (0x727516,'lea','rsi, [r14 + 0x4f90]'),
        (0x72752C,'imul','rax, rax, 0x55a698'),
        (0x727537,'add','rsi, rax'),
        (0x7275D6,'mov','edx, dword ptr [rax + rcx + 0x3b4]'),
        (0x7275F3,'lea','rcx, [rsi + 0x4c8260]'),
        (0x7275FA,'call','0x14335f0'),
        (0x143360F,'mov','esi, edx'),
        (0x1433614,'imul','r12, rsi, 0x298'),
        (0x143362F,'mov','qword ptr [r12 + rcx + 0x80e24], rax'),
        (0x724332,'imul','rax, rax, 0x55a698'),
        (0x724340,'mov','qword ptr [rbp - 0x49], rax'),
        (0x72437C,'mov','rsi, qword ptr [rbp - 0x49]'),
        (0x7244E2,'lea','rcx, [r13 + 0x4cd1f0]'),
        (0x7244FD,'add','rcx, rsi'),
        (0x724542,'call','0x142b990'),
        (0x142B9BE,'mov','rbx, rcx'),
        (0x142BB8D,'lea','r14, [rbx + 0x80eb8]'),
        (0x142BB94,'mov','r12d, 4'),
        (0x142BBA0,'lea','rcx, [r14 - 0xa0]'),
        (0x142BBA7,'xor','edx, edx'),
        (0x142BBA9,'mov','r8d, 0x298'),
        (0x142BBAF,'call','0x208aaa0'),
        (0x142BC2C,'add','r14, 0x298'),
        (0x142BC33,'sub','r12, 1'),
        (0x142BC37,'jne','0x142bba0'),
        (0x142BC3D,'lea','rcx, [rbx + 0x81888]'),
        (0x142BC52,'call','0x140c160'),
        (0x140C19C,'mov','qword ptr [rcx], rdx'),
        (0x142BD5E,'lea','r14, [rbx + 0x81d10]'),
        (0x142BA7E,'mov','r15d, 0x40'),
        (0x142BD95,'mov','rcx, r14'),
        (0x142BD98,'call','0x140c160'),
        (0x142BD9D,'add','r14, 0x180'),
        (0x142BDA4,'sub','r15, 1'),
        (0x142BDA8,'jne','0x142bd70'),
        (0x724DEC,'lea','rbx, [r13 + 0x4c8260]'),
        (0x724DF6,'call','0x142c9b0'),
        (0x142CAA9,'lea','rbx, [rdi + 0x81d10]'),
        (0x142CAB0,'mov','esi, 0x40'),
        (0x142CABE,'mov','rcx, rbx'),
        (0x142CAC1,'call','0x140c200'),
        (0x142CAC6,'add','rbx, 0x180'),
        (0x140C226,'mov','eax, dword ptr [rbx + rax*4 + 0x28]'),
        (0x140C22A,'imul','rcx, rax, 0x208'),
        (0x140C231,'mov','rax, qword ptr [rbx + 0x20]'),
        (0x140C235,'add','rcx, qword ptr [rax]'),
        (0x140C238,'call','0x1408f00'),
    ]
    for at,mnemonic,operands in semantic:
        i = decoded.get(at)
        require(i is not None and (i.mnemonic,i.op_str)==(mnemonic,operands), 'semantic pin '+hex(at))

    global_proofs = []
    for at,expected in [(0x5687EB,0x3326AA0),(0x724292,0x3326AA0),(0x7248EE,0x3326AA0),
                        (0x72757E,0x3326468),(0x7275B1,0x3326468),(0x7275FF,0x3326468),
                        (0x1433606,0x3326468)]:
        i = decoded[at]
        targets = [i.address+i.size+o.mem.disp for o in i.operands
                   if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP]
        require(targets==[expected], 'global target changed')
        global_proofs.append(dict(instruction=row(i), target=hex(expected)))

    # Full prefixes, not disconnected matching displacements, establish the base.
    audits = []
    for a,b,aliases,expected in [
        (0x568230,0x5687F2,('rbx','ebx','bx','bl','bh'),[0x568236]),
        (0x725160,0x727610,('r14','r14d','r14w','r14b'),[0x7251A4]),
        (0x724260,0x724547,('r13','r13d','r13w','r13b'),[0x724292]),
        (0x724260,0x724547,('rsi','esi','si','sil'),[0x72429F,0x72435D,0x724361,0x72437C]),
        (0x7248D0,0x724981,('rsi','esi','si','sil'),[0x7248EE]),
        (0x7248D0,0x724DFB,('r13','r13d','r13w','r13b'),[0x72496B,0x72497E]),
        (0x142B990,0x142BE88,('rbx','ebx','bx','bl','bh'),[0x142B9BE]),
    ]:
        raw = im.read(a,b-a)
        ins = list(im.md.disasm(raw,a))
        require(sum(i.size for i in ins)==len(raw), 'base audit decode incomplete')
        writes = [i for i in ins if any(im.md.reg_name(r) in aliases for r in i.regs_access()[1])]
        require([i.address for i in writes]==expected, 'base audit changed')
        audits.append(dict(start=hex(a),end_exclusive=hex(b),sha256=sha(raw),aliases=aliases,
                           explicit_writes=[row(i) for i in writes]))

    strings = []
    for at,expected in [(0x2249800,b'Galaxy_map_3d\0'),(0x2249858,b'Galaxy_map_2d_3d\0')]:
        raw = im.read(at,len(expected)); require(raw==expected,'parent-context string changed')
        strings.append(dict(rva=hex(at),bytes=raw.hex(),sha256=sha(raw),text=raw[:-1].decode(),
                            interpretation='Referenced in the same parent callback, not a proven class/name of destination D.'))
    base,stride = 0x80E18,0x298
    end4 = base+4*stride
    require(end4==0x81878 and 0x4F90+0x4C8260==0x4CD1F0,'layout arithmetic changed')
    writes = [dict(network_index=n,start=hex(0x80E24+n*stride),
                   end_exclusive=hex(0x80E2C+n*stride)) for n in range(8)]
    n7_subobject = 0x81D10+2*0x180
    require(n7_subobject==0x82010 and 0x80E24+7*stride-n7_subobject==0x3C,'n7 neighbor arithmetic')
    result = dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        prior_evidence_sha256=PRIOR_SHA,runtime_verified=False,scope='Only 7275FA -> 14335F0 roster-indexed float storage',
        code_spans=spans,pins=pins,base_prefix_audits=audits,global_proofs=global_proofs,parent_context_strings=strings,
        selected_instruction_count=sum(len(x['instructions']) for x in spans.values())+len(pins),
        base_identity=dict(manager_global='0x3326aa0',manager_owner_offset='0x1f7ae8',
            instance_expression='U=M+0x4F90+k*0x55A698',destination_expression='D=U+0x4C8260=M+k*0x55A698+0x4CD1F0',
            initializer='724542 -> 142B990',writer='7275FA -> 14335F0',cleanup='724DF6 -> 142C9B0',
            ordinal_note='k selects a manager instance; n is the independent roster network index. They are not equated.'),
        initialized_record_layout=dict(base=hex(base),stride=hex(stride),count=4,end_exclusive=hex(end4),
            qword_float_field_offset='0xc',next_proven_subobject='0x81888',gap_to_next_subobject=16,
            eight_record_end_if_unmoved=hex(base+8*stride),extra_four_record_bytes=4*stride,
            meaning='A four-record initialized region, not the full enclosing object allocation boundary.'),
        hypothetical_qword_writes=writes,
        proven_collisions=[
            dict(network_index=4,write_span=['0x81884','0x8188c'],neighbor_base='0x81888',
                 overwritten_span=['0x81888','0x8188c'],neighbor_field='First qword, initialized from RDX at140C19C; low four bytes overwritten.',
                 unclassified_first_four_bytes=['0x81884','0x81888']),
            dict(network_index=7,write_span=['0x8204c','0x82054'],neighbor_base='0x82010',
                 neighbor_source='81D10 + 2*180, one of64 initialized and cleaned subobjects',
                 neighbor_fields=['+0x3c','+0x40'],neighbor_array='dword array at+0x28; entries5 and6',
                 consumer='140C200 reads entries below count+58, multiplies each by208 and accesses pool through+20; cleanup path142CAC1 reaches this helper.',
                 condition='The write overlaps existing initialized storage regardless of count; later entry consumption requires count to include entries5/6.'),
        ],
        limits=[
            'No live query/read/capture/probe, game execution, modification or eight-player test.',
            'All collisions are conditional on this writer being reached with that network index; caller has other state gates and skips its selected local index.',
            'No invocation frequency, current data values, actual corruption symptom or crash is established.',
            'The enclosing destination allocation is much larger; spatial inclusion in it is not free capacity for this four-record region.',
            'Same-parent Galaxy_map strings do not name the exact destination child; its formal class/UI role remains unknown.',
            'The unrelated 14A67D7 same-stride occurrence was not used as object-identity evidence.',
            'Base audits rely on normal Windows x64 nonvolatile-register preservation across calls; unrelated consumers are not exhaustively audited.',
        ])
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),instructions=result['selected_instruction_count'],sha256=sha(output.read_bytes()))))


if __name__=='__main__':
    main()
