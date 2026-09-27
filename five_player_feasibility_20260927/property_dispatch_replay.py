"""Replay the selected per-entity property dispatch from saved HD2 capture only.

No process query, live read, network request, new capture, or patching.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

PRIOR = {
    'property_dispatch_entry_xrefs.json': 'fce7de5f35c6da32b4908f5c4db2b470f53722c5c25df0f96fec18077ceeae37',
    'component238_lifecycle_evidence_v2.json': 'ac68b8cc938dc56288c9db7fa9a41d8a64f84fdd353fee6ff3414f6c35e0424b',
    'component33_250_lifecycle_evidence_v2.json': 'dfb125ab3edd6b9672eb725981beecb91e1768da9d44b92522e28fd971155280',
    'component41_lifecycle_evidence_v2.json': '0f902df704cffb16992d483e099867f5e05708e6d32bdf1672128eca744721df',
    'roster_property_receive_evidence.json': 'bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10',
}
ROOTS = {
    0xFD9BA0: 'external_handle_to_entity_id',
    0x581C40: 'component_list_callbacks_before_and_after_property_apply',
    0xFDC140: 'creation_order_components_map_property_post_callback',
    0xFDDE30: 'pending_handle_list_apply_loop',
    0xFDDE90: 'single_handle_tail_apply',
    0x671860: 'component250_cursor_4_low_byte_only',
    0x60C890: 'roster239_cursor_32_all_eight_dwords',
    0x87BB30: 'component238_cursor_64',
    0x666590: 'component33_cursor_56',
    0x7AF610: 'component41_cursor_88',
    0x799790: 'final_component_cursor_36',
}
SPANS = {
    'entry_api_output_and_selector': (0xBC2D30, 0xBC2DBF),
    'api_false_or_selector_out_of_range_return': (0xBC6859, 0xBC6869),
    'selected_case': (0xBD138C, 0xBD13FF),
    'shared_final_component_and_return': (0xBD1DE1, 0xBD1E07),
    'classification_caller': (0xFDBDD0, 0xFDBE15),
}
# Expected disassembly fixes the hand-derived cursor arithmetic to exact code.
CURSOR_PINS = {
    0x6718E9: 'mov edx, dword ptr [r14]',
    0x6718EE: 'movzx eax, byte ptr [rdx + r15]',
    0x6718F3: 'mov byte ptr [rcx + r11 + 0x164], al',
    0x6718FB: 'lea eax, [rdx + 4]',
    0x6718FE: 'mov dword ptr [r14], eax',
    0x60C928: 'mov ecx, dword ptr [r14]',
    0x60C95C: 'mov ecx, dword ptr [rdx + rbp]',
    0x60C962: 'mov dword ptr [r8 + r11 + 0x3b4], ecx',
    0x60C997: 'lea eax, [rdx + 4]',
    0x60C99F: 'mov dword ptr [r14], eax',
    0x87BBCE: 'lea r8, [rbx + 0xa7c]',
    0x87BBDA: 'shl rcx, 6',
    0x87BBE1: 'mov ecx, dword ptr [r15]',
    0x87BBE8: 'lea edx, [rcx + 4]',
    0x87BC6B: 'lea eax, [rdx + 4]',
    0x87BC6E: 'mov dword ptr [r15], eax',
    0x87BC71: 'mov dword ptr [r8 + 0x3c], ecx',
    0x66661E: 'lea r8, [rbx + 0x1d8]',
    0x66662A: 'imul rax, rcx, 0x38',
    0x66662E: 'mov ecx, dword ptr [r15]',
    0x666638: 'lea edx, [rcx + 0x18]',
    0x66665F: 'add edx, 8',
    0x666674: 'add edx, 0x14',
    0x666680: 'lea eax, [rdx + 4]',
    0x666683: 'mov dword ptr [r15], eax',
    0x7AF69E: 'lea r8, [rbx + 0x26688]',
    0x7AF6AA: 'imul rax, rcx, 0x58',
    0x7AF6AE: 'mov ecx, dword ptr [r14]',
    0x7AF6B8: 'lea edx, [rcx + 0x2c]',
    0x7AF6EC: 'lea eax, [rdx + 0x2c]',
    0x7AF6F3: 'mov dword ptr [r14], eax',
    0x799813: 'mov r8, qword ptr [rbx + 0x50]',
    0x79981E: 'lea r9, [rcx + rcx*8]',
    0x799822: 'mov ecx, dword ptr [r14]',
    0x799871: 'movzx ecx, byte ptr [rdx + rbp]',
    0x799875: 'add edx, 4',
    0x799880: 'lea eax, [rdx + 4]',
    0x799888: 'mov dword ptr [r14], eax',
}
SELECTED = [
    # Ref component identity, owner offset, callsite, receiver, serialized bytes.
    (250, 0xEB5178, 0xBD139D, 0x671860, 4),
    (239, 0xEA0818, 0xBD13B3, 0x60C890, 0x20),
    (238, 0xE9FC98, 0xBD13C9, 0x87BB30, 0x40),
    (33, 0x3CA0, 0xBD13DF, 0x666590, 0x38),
    (41, 0x4148, 0xBD13F5, 0x7AF610, 0x58),
    (None, 0xEB5E10, 0xBD1DF2, 0x799790, 0x24),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    priors = {}
    for name, digest in PRIOR.items():
        data = (HERE / name).read_bytes()
        require(sha(data) == digest, 'prior changed: ' + name)
        priors[name] = json.loads(data)
    im = Image(args.evidence)
    boundary_cache = {}

    def ins(addr):
        f = im.containing(addr)
        require(f is not None, 'no unwind at ' + hex(addr))
        if f[0] not in boundary_cache:
            b = im.read(f[0], f[1] - f[0])
            ds = list(im.md.disasm(b, f[0]))
            require(sum(i.size for i in ds) == len(b), 'incomplete fragment')
            boundary_cache[f[0]] = {i.address: i for i in ds}
        require(addr in boundary_cache[f[0]], 'invalid boundary ' + hex(addr))
        return boundary_cache[f[0]][addr]

    def annotated(i):
        return dict(**row(i), rip_targets=[hex(i.address + i.size + o.mem.disp)
                    for o in i.operands if o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP])

    spans = {}
    for label, (start, end) in SPANS.items():
        ds = list(im.md.disasm(im.read(start, end - start), start))
        require(sum(i.size for i in ds) == end - start, 'span end not boundary')
        for i in ds:
            require(ins(i.address).bytes == i.bytes, 'span boundary differs')
            require(im.root(i.address)[0] == (0xFDBB40 if label == 'classification_caller' else 0xBC2D30), 'span wrong root')
        spans[label] = dict(start=hex(start), end_exclusive=hex(end), sha256=sha(im.read(start, end-start)),
                            instructions=[annotated(i) for i in ds])

    fragments = {root: [] for root in ROOTS}
    for f in im.functions:
        root = im.root(f[0])[0]
        if root in fragments:
            b = im.read(f[0], f[1] - f[0])
            ds = list(im.md.disasm(b, f[0]))
            require(sum(i.size for i in ds) == len(b), 'root fragment decode incomplete')
            fragments[root].append(dict(start=hex(f[0]), end_exclusive=hex(f[1]), unwind=hex(f[2]),
                sha256=sha(b), instructions=[annotated(i) for i in ds]))
    require(all(fragments.values()), 'root missing')
    # All six sizing helpers are self-contained and have no calls. Their complete
    # fragments preserve the map/error paths as well as the successful copy path.
    for receiver in [s[3] for s in SELECTED]:
        rows = [r for f in fragments[receiver] for r in f['instructions']]
        require(not any(r['asm'].startswith('call ') for r in rows), 'unexpected sizing callee')

    cursor_pins = []
    for addr, expected in CURSOR_PINS.items():
        i = ins(addr)
        require(i.mnemonic + ' ' + i.op_str == expected, 'cursor pin changed: ' + hex(addr) + ' ' + i.mnemonic + ' ' + i.op_str)
        cursor_pins.append(annotated(i))

    expected_targets = {0x581DA9: 0x581C40, 0xFDBE10: 0xFDBB40, 0xFDC29B: 0xFDC140,
                        0xFDDE6A: 0xFDDE30, 0xFDDEB3: 0xFDDE90}
    xrefs = priors['property_dispatch_entry_xrefs.json']['targets']['0xbc2d30']['branches']
    require({int(x['rva'], 16) for x in xrefs} == set(expected_targets), 'bounded incoming set changed')
    callers = []
    for addr, root in expected_targets.items():
        i = ins(addr)
        require(i.mnemonic in ('call', 'jmp') and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == 0xBC2D30, 'caller target changed')
        require(im.root(addr)[0] == root, 'caller root changed')
        prior = next(r for r in xrefs if int(r['rva'],16) == addr)
        require(prior['bytes'] == i.bytes.hex(), 'caller prior bytes differ')
        callers.append(dict(**annotated(i), root=hex(root)))

    # Verify API-result -> selector -> RVA table edge, without inventing a wire header.
    expected_selector = {
        0xBC2D4D: 'test r8b, r8b', 0xBC2D93: 'mov eax, dword ptr [rbp - 8]',
        0xBC2D96: 'mov rdi, qword ptr [rbp - 0x10]',
        0xBC2D9A: 'mov dword ptr [rbp + 0x20], 0',
        0xBC2DA1: 'cmp eax, 0x73e',
        0xBC2DB3: 'mov ecx, dword ptr [rdx + rax*4 + 0xbd9eb8]',
        0xBC2DBA: 'add rcx, rdx', 0xBC2DBD: 'jmp rcx',
    }
    for addr, expected in expected_selector.items():
        i = ins(addr)
        require(i.mnemonic + ' ' + i.op_str == expected, 'selector pin changed')
    table_rva, count = 0xBD9EB8, 0x73F
    table = im.read(table_rva, count * 4)
    entries = list(struct.unpack('<' + 'I' * count, table))
    matching = [(n,t) for n,t in enumerate(entries) if 0xBD138C <= t < 0xBD13FF]
    require(matching == [(0x3A7, 0xBD138C)], 'selected table edge changed')

    contracts, cursor = [], 0
    for component, owner_offset, callsite, receiver, length in SELECTED:
        i = ins(callsite)
        require(i.mnemonic == 'call' and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == receiver, 'receiver edge changed')
        start = callsite - 0x11
        setup = [ins(a) for a in (start, start + 3, start + 0xA, start + 0xE)]
        expected = ['mov edx, dword ptr [rbp + 0x28]', 'lea rcx, [rbx + ' + hex(owner_offset) + ']',
                    'lea r9, [rbp + 0x20]', 'mov r8, rdi']
        require([i.mnemonic + ' ' + i.op_str for i in setup] == expected, 'selected argument setup changed')
        contracts.append(dict(reference_component_index=component, owner_offset=hex(owner_offset), receiver=hex(receiver),
            callsite=hex(callsite), argument_setup=[annotated(i) for i in setup],
            cursor_at_entry=hex(cursor), cursor_at_return=hex(cursor + length), serialized_bytes=length,
            byte_range=[hex(cursor), hex(cursor + length)]))
        cursor += length
    require(cursor == 0x118, 'selected format size changed')

    result = dict(source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'], prior_sha256=PRIOR,
        entry='0xbc2d30', runtime_verified=False,
        api_result=dict(api_global='0x3326308', interface_offset='0x40', false_method='0xa8', true_method='0xb0',
            zero_initialized_output_bytes=16, output_base='rbp-0x10', payload_pointer_offset=0, selector_offset=8,
            true_method_false_return_skips_apply=True,
            caveat='This is local API result metadata. Wire framing, descriptor+12 meaning, selector producer and API method names are not established.'),
        selector=dict(maximum='0x73e', table_rva=hex(table_rva), table_entry_count=count, table_bytes=len(table),
            table_sha256=sha(table), selected_index='0x3a7', selected_index_decimal=0x3A7,
            selected_slot_rva=hex(table_rva+0x3A7*4), selected_slot_bytes=table[0x3A7*4:0x3A8*4].hex(), target='0xbd138c',
            entries_targeting_selected_case=[dict(index=hex(n),target=hex(t)) for n,t in matching],
            meaning='API-provided format selector; not a player ordinal or a proven reference component index.'),
        spans=spans, functions=[dict(root=hex(root), purpose=ROOTS[root], fragments=fragments[root]) for root in ROOTS],
        cursor_pins=cursor_pins, selected_format=contracts, total_serialized_bytes=cursor,
        roster_index_payload_offset=hex(4+0xC),
        cursor_arithmetic=dict(component250=[4], roster239=[4]*8, component238=[4]*16,
            component33=[0x18,8,0x14,4], component41=[0x2C,0x2C], final_component_at_owner_EB5E10=[4]*9,
            interpretation='Manual arithmetic verified against complete receiver instructions and exact pins, not runtime execution or a packet decoder.'),
        incoming_direct_calls_and_tail=callers,
        dispatch_order=dict(creation=['581320 component add', '172F790 external-handle map insertion when handle!=7FFF',
                'BC2D30 only when handle!=7FFF and creation parameter first byte==0', '581780 post callback'],
            component_list_caller='581C40 iterates uint16 component indices from F12EA0/F12EA8 around BC2D30 using callback tables F0F3B0/F0FDD0; BC2D30 instead uses its API result selector.',
            pending_list='FDDE30 uses count at self+18 and dword handles at self+1C; no immediate four-count restriction is present in this loop.'),
        id_resolution=dict(helper='0xfd9ba0', context_global='0x346bf98', map_offset='0xf22ec8', record_array_offset='0xf32f18',
            record_stride='0x18', id_field='0x8', sentinel_global='0x348456c', output='BC2D30 stack dword rbp+28',
            caution='No general membership guarantee: helper can return sentinel, and a no-entry path can dereference zero. BC2D30 does not validate output before selected receivers. Creation ordering alone does not prove all callers are safe.'),
        modification_implications=[
            'The selected format carries one entity, not an inline array of four players; no four-player count patch is identified in this dispatcher.',
            'Its component41/238/239 receivers index destination arrays by entity-map ordinal. Existing four-row native storage still requires independent expansion.',
            'Direct owner+4148, owner+E9FC98, owner+EA0818 aliases must move if the owning embedded systems relocate; changing global pointers alone is insufficient.',
            'Four-byte scalar strides and selector maximum73E are not player limits.',
            'Eight-player use of unchanged one-entity schema is a conditional design possibility, not a verified sender/API/transport capability.'
        ],
        limits=[
            'Fixed saved capture only; no process query/read, new capture, game patch, multiplayer run or runtime metadata verification.',
            'Six selected receivers and five direct incoming edges are scoped evidence; no exhaustive classification of BC2D30 other cases.',
            'Direct incoming set is inherited from bounded E8/E9 scan with unwind boundary validation; uncovered/indirect callers are not excluded.',
            'Reference component labels are prior static associations. Runtime selection of3A7 for a player has not been observed.',
            'The final owner+EB5E10 member is included to close the payload length; its reference component index is not proven in this scoped artifact and is left null.',
            'No selected-path input length or entity-ID validity guard was established. API production of payload and selector remains unresolved.',
            'Component250 reads only one byte but advances cursor by4; final component likewise includes a byte encoded in a four-byte slot.',
            '32-bit cursor arithmetic wraps modulo2^32 in code; ranges here describe cursor initialized to0 and one successful selected dispatch.'
        ])
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), sha256=sha(output.read_bytes()), roots=len(ROOTS),
        root_instructions=sum(len(f['instructions']) for fs in fragments.values() for f in fs),
        span_instructions=sum(len(s['instructions']) for s in spans.values()), cursor_pins=len(cursor_pins),
        serialized_bytes=cursor)))


if __name__ == '__main__':
    main()
