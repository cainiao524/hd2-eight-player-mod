"""Offline replay of all nine reference-player first-stage component callbacks.

No process access. The reference resource list is not a live metadata claim.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

PRIOR = {
    'spawn_resource_metadata_evidence.json': '400bd47c3d75928695f76b64591d56c699ab725581b4d068071c5f293b07cd2a',
    'spawn_callback_registration_evidence_v2.json': '142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109',
}
# index: entry, end, instruction count, complete fragment SHA-256, global RVA
FUNCTIONS = {
    3: (0x516540, 0x5165BA, 34, '83d03ce0a4f93f84374e0149dedef38735021b2892ec4ba781a2c8529f040a96', 0x3326430),
    33: (0x51AC70, 0x51AD27, 46, '2738a498cd3220e8099e71bdd7f44ad0e7dcd1d6cbde3f2ba9e6e59e59640fca', 0x33267B8),
    41: (0x51BB50, 0x51BC35, 58, '682e095018c853ad4a05254b8942fa894feb2a6b421719d321ab40e60f385e2a', 0x3326998),
    43: (0x51C110, 0x51C19C, 35, 'af18bad0fc8315e822a296464ef38c34f6df3dac6647d78c7578a7329fdabb39', 0x3326AF0),
    226: (0x53E1B0, 0x53E27B, 45, 'a3d2c1cbafa8145c62f49e2a4a19a51d298f35ec38ce880057470c23025772d3', 0x3326AE0),
    238: (0x540660, 0x54073A, 47, '11dbd9a2456faca7b6d3533700695326b406d9529e360b9761d287f643c21da0', 0x33264F8),
    239: (0x540920, 0x540A3E, 57, '197e6d093ec081d304e0642ffee3e7fc3a71b2eadb36f3a0805d4927af7a5196', 0x3326468),
    250: (0x5432B0, 0x543360, 46, 'b14a6bbab2b47ed986dd7af2f30ea4798e691d893d711da888c0f7cc6c7b9af2', 0x33266D0),
    260: (0x544FD0, 0x54509E, 60, 'b30ddc2d089220d946b46fb52483f043d12a0c119091219b7beeb8f9bab411da', 0x3326A50),
}
# count-load RVA, count field, base register, cmp RVA
GUARDS = {
    33: (0x51AC84, 0x8, 'rbx', 0x51AC89),
    41: (0x51BB69, 0x4, 'rbx', 0x51BB6E),
    43: (0x51C12E, 0x4, 'rsi', 0x51C133),
    226: (0x53E1C4, 0x37D08, 'rbx', 0x53E1CC),
    238: (0x540674, 0x8E4, 'rbx', 0x54067C),
    239: (0x540934, 0x80, 'rbx', 0x54093C),
    250: (0x5432C4, 0xC, 'rbx', 0x5432C9),
}
# Manually derived address expressions; the complete pinned assembly is emitted.
LAYOUTS = {
    33: dict(pointer_base=0x70, pointer_store=0x51AD10, record_base=0x98, record_stride=0x50,
             record_writes=[0x51ACD1, 0x51ACD9, 0x51ACE1, 0x51ACE9, 0x51ACF1],
             record_initialization='all append paths', movement_helper=0x665FE0),
    41: dict(pointer_base=0x68, pointer_store=0x51BC19, record_base=0x88, record_stride=0x9928,
             record_writes=[0x51BBA5, 0x51BBAD, 0x51BBB4, 0x51BBBB, 0x51BBBE],
             record_initialization='creation params byte 0 nonzero only', movement_helper=0x7AF210,
             second_record_base=0x26528, second_record_stride=0x58,
             second_record_initialization='all append paths'),
    43: dict(pointer_base=0x68, pointer_store=0x51C17B, record_base=0x88, record_stride=0x108,
             record_writes=[0x51C146, 0x51C14D, 0x51C156, 0x51C15C, 0x51C15F],
             record_initialization='all append paths', movement_helper=None),
    238: dict(pointer_base=0x948, pointer_store=0x540720, record_base=0x96C, record_stride=0x44,
              record_writes=[0x5406C8, 0x5406CF, 0x5406D7, 0x5406DF, 0x5406E7, 0x5406EF],
              record_initialization='all append paths', movement_helper=0x87B5D0),
    250: dict(pointer_base=0x70, pointer_store=0x543349, record_base=0x90, record_stride=0x34,
              record_writes=[0x543305, 0x54330B, 0x543313, 0x54331B, 0x543323],
              record_initialization='creation params byte 0 nonzero only', movement_helper=0x671610),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior = {}
    for name, fingerprint in PRIOR.items():
        raw = (HERE / name).read_bytes()
        require(sha(raw) == fingerprint, 'prior evidence mismatch: ' + name)
        prior[name] = json.loads(raw)
    metadata = prior['spawn_resource_metadata_evidence.json']
    player = next(x for x in metadata['reference_metadata']['resources']
                  if x['reference_name'] == 'content/entities/player')
    require(player['indices'] == list(FUNCTIONS), 'reference player list changed')
    reference_path = HERE.parent / 'FileDiver/datalibrary/generated_entities.dl_bin'
    reference = reference_path.read_bytes()
    require(sha(reference) == '21377252b81fdbc670eba1e59a8ab64b170323df208f175e708992e4c1fb515e',
            'reference metadata file changed')
    for offset, encoded in [(player['record_file_offset'], player['record_bytes']),
                            (player['component_list_file_offset'], player['component_list_bytes'])]:
        value = bytes.fromhex(encoded)
        require(reference[int(offset, 16):int(offset, 16)+len(value)] == value, 'reference bytes changed')
    require(list(struct.unpack('<9H', bytes.fromhex(player['component_list_bytes']))) == list(FUNCTIONS),
            'component list bytes mismatch')

    im = Image(args.evidence)
    start, end = 0x556D90, 0x55E1E3
    init = im.read(start, end-start)
    require(sha(init) == '22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2',
            'initializer bytes changed')
    require(im.instruction(0x568239).op_str == '0x556d90', 'initializer entry proof changed')
    require(len(init) == 2127*14+1 and init[-1] == 0xC3, 'initializer size/end changed')
    assignments = {}
    for at in range(0, len(init)-1, 14):
        pair = init[at:at+14]
        require(pair[:3] == b'\x48\x8d\x05' and pair[7:10] == b'\x48\x89\x81', 'unexpected initializer pair')
        target = start+at+7+struct.unpack_from('<i', pair, 3)[0]
        offset = struct.unpack_from('<i', pair, 10)[0]
        require(offset not in assignments, 'duplicate destination')
        assignments[offset] = dict(target=target, write_rva=start+at+7,
                                   instructions=[row(i) for i in im.md.disasm(pair, start+at)])
    entries = []
    for index, (entry, end, count, fingerprint, global_rva) in FUNCTIONS.items():
        registration = assignments[0xF0C110+index*8]
        require(registration['target'] == entry, 'registered callback mismatch')
        fragment = im.containing(entry)
        require(fragment[:2] == (entry, end), 'fragment bounds mismatch')
        raw = im.read(entry, end-entry)
        require(sha(raw) == fingerprint, 'callback bytes changed')
        instructions = list(im.md.disasm(raw, entry))
        require(len(instructions) == count and sum(i.size for i in instructions) == len(raw), 'decode mismatch')
        global_loads = [i for i in instructions if any(o.type == X86_OP_MEM and o.mem.base == X86_REG_RIP
                        and i.address+i.size+o.mem.disp == global_rva for o in i.operands)]
        require(len(global_loads) == 1, 'global load not unique')
        item = dict(component_index=index, reference_data_type=next(x['data_type_name'] for x in player['data_type_names'] if x['index'] == index),
                    entry=hex(entry), unwind_fragment=[hex(x) for x in fragment], sha256=fingerprint,
                    callback_table_base='0xf0c110', callback_slot=hex(0xF0C110+index*8), registration=registration,
                    global_rva=hex(global_rva), global_load=row(global_loads[0]), instructions=[row(i) for i in instructions])
        by_address = {i.address:i for i in instructions}
        if index in GUARDS:
            load, field, base, compare = GUARDS[index]
            k = next(k for k, i in enumerate(instructions) if i.address == load)
            block = instructions[k:k+5]
            require(block[0].mnemonic == 'mov' and block[0].operands[1].mem.disp == field
                    and im.md.reg_name(block[0].operands[1].mem.base) == base, 'count load mismatch')
            require([(i.mnemonic, i.op_str) for i in block[1:3]] == [('inc', 'eax'), ('cmp', 'eax, 4')]
                    and block[2].address == compare, 'guard arithmetic mismatch')
            require(block[3].mnemonic == 'jbe' and block[3].operands[0].imm == block[4].address+block[4].size
                    and block[4].mnemonic == 'mov' and block[4].op_str == 'dword ptr [0], 0', 'guard branch mismatch')
            item['count_guard'] = dict(count_field=hex(field), expression='uint32(count + 1) <= 4',
                                       compare_rva=hex(compare), instructions=[row(i) for i in block],
                                       note='For the normal bounded count domain; this does not model overflow or exceptions.')
        else:
            require(not any(i.mnemonic == 'cmp' and i.op_str == 'eax, 4' for i in instructions), 'unexpected four comparison')
            item['capacity_classification'] = 'Count is compared with object fields and calls helpers; eight-player safety is not established.'
        if index in LAYOUTS:
            layout = dict(LAYOUTS[index])
            pointer = by_address[layout['pointer_store']].operands[0]
            require(pointer.type == X86_OP_MEM and pointer.size == 8 and pointer.mem.disp == layout['pointer_base']
                    and pointer.mem.scale == 8, 'pointer expression mismatch')
            require(all(x in by_address for x in layout['record_writes']), 'record site missing')
            collisions = []
            for ordinal in range(4, 8):
                lo, hi = layout['pointer_base']+ordinal*8, layout['pointer_base']+(ordinal+1)*8
                first_lo, first_hi = layout['record_base'], layout['record_base']+layout['record_stride']
                overlap = max(0, min(hi, first_hi)-max(lo, first_lo))
                collisions.append(dict(ordinal=ordinal, pointer_span=[hex(lo), hex(hi)],
                                       overlap_with_record_zero_bytes=overlap))
            layout['hypothetical_expanded_pointer_writes'] = collisions
            layout['record_four_start'] = hex(layout['record_base']+4*layout['record_stride'])
            if index == 41:
                require(layout['record_base']+4*layout['record_stride'] == layout['second_record_base'], 'parallel array adjacency changed')
                layout['record_four_collides_with_second_array'] = True
            item['manually_derived_storage'] = layout
        entries.append(item)
    result = dict(source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
                  prior_evidence_sha256=PRIOR, reference_file_sha256=sha(reference), reference_player=player,
                  initializer_sha256=sha(init), initializer_assignments=len(assignments),
                  entries=entries, first_stage_callbacks=9, fixed_four_guard_components=list(GUARDS),
                  new_guard_components=[33, 41, 43, 238, 250], decoded_instructions=sum(len(x['instructions']) for x in entries),
                  limits=['Reference-file equality with current installed/decrypted or live metadata is unproven.',
                          'Static initialization and callback bodies are verified; live callback selection and execution are not.',
                          'Record formulas are manual dataflow deductions from the complete pinned instruction bodies.',
                          'Ordinal is a component storage index; it is not assumed equal to network index.',
                          'Conditional initialization, helper calls, removal, relocation, and other consumers require coordinated treatment.',
                          'Two callbacks with field-based capacity checks are not proven unlimited or safe for eight.',
                          'No live process access, modification, installation, or five/eight-player test.'])
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), callbacks=9, instructions=result['decoded_instructions'], fixed_four_components=list(GUARDS))))


if __name__ == '__main__':
    main()
