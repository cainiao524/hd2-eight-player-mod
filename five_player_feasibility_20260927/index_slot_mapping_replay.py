"""Replay loadout-screen network-index mapping evidence from the pinned capture.

Only saved capture files are read. No installed game or process access.
All selected instruction boundaries are validated against captured unwind data.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

GROUPS = [
    ('screen_identity_and_registration',
     'on_enter preserves incoming screen pointer in RDI, logs MenuScreenLoadout, calls initializer with same pointer, and registers that exact pointer with tag E5 in global 3326E68. Includes list count +62E8 used by B90040.',
     [0x1465879, 0x1465894, 0x146589B, 0x14658A2, 0x1465AE1, 0x1465AE4,
      0x1465FCD, 0x1465FD4, 0x1465FD9, 0x1465FE1,
      0x1466040, 0x146604C, 0x1466052, 0x1466055, 0x146605F,
      0xB90054, 0xB90063, 0xB90072, 0xB90078, 0xB9007B, 0xB90089]),
    ('allocation_and_four_element_construction',
     'Allocator-like call receives size 2739D0; returned memory is zeroed for that size, constructed by 14A17E0, stored at screen-manager +B0. Constructor loops four times at +53A78 stride 1EE18. Exact name of allocator is unproven.',
     [0x14984E8, 0x1498AE1, 0x1498AE8, 0x1498AED, 0x1498AF4, 0x1498AFA, 0x1498AFE,
      0x1498B01, 0x1498B03, 0x1498B09, 0x1498B0C, 0x1498B0F, 0x1498B14, 0x1498B17, 0x1498B1C,
      0x1495A47, 0x1495A4E, 0x1495A51, 0x1495A54,
      0x14A17F4, 0x14A17FD, 0x14A1943, 0x14A1950, 0x14A1953, 0x14A1958, 0x14A195F, 0x14A1963,
      0x14A1B2E, 0x14664AF, 0x14664DE]),
    ('mapping_reset_and_local_slot_zero',
     'Initializer has same screen in RDI. Two adjacent 4-DWORD maps reset to FFFFFFFF. Finds local peer ID in owner client records, reads network index, sets forward[index]=0 and inverse[0]=index; no local index<4 check in this sequence.',
     [0x14661C3, 0x1466F12, 0x1466F19,
      0x1466F26, 0x1466F31, 0x1466F3C, 0x1466F47, 0x1466F52,
      0x1466F5D, 0x1466F69, 0x1466F70, 0x1466F80, 0x1466F82, 0x1466F88,
      0x14670AC, 0x14670B0, 0x14670B8, 0x14670BB, 0x14670C1, 0x14670C7, 0x14670CF,
      0x146693E, 0x1466AE2, 0x1466AF0, 0x1466AF5, 0x1466AF8, 0x1466C3B, 0x1466C4D, 0x1466C51]),
    ('network_index_to_loadout_slot_consumer',
     'Tag-E5 registered pointer, peer ID lookup in client owner, then forward map value<4 gates UI subobject at +620E8 + slot*1EE18. Slot is not roster ordinal.',
     [0xB900C6, 0xB900CF, 0xB900DF, 0xB900F0, 0xB900F7, 0xB90108,
      0xB90137, 0xB9013B, 0xB90143, 0xB9014B, 0xB9014E, 0xB90150, 0xB90157, 0xB90160, 0xB90163,
      0x14719F9, 0x1471A3C, 0x1471AB8, 0x1471AC3, 0x1471ACA, 0x1471ACD, 0x1471ACF, 0x1471AD9, 0x1471AE0, 0x1471AE3]),
    ('mapping_assignment_during_roster_update',
     'Screen in RSI. Reads separate roster pointer-list ordinal, explicitly checks ordinal<4, derives peer identity and then network index through owner client. Reserves UI slot zero; searches inverse slots 1..3 for FFFFFFFF, then writes both maps.',
     [0x146C306, 0x146C35C, 0x146C363, 0x146C381, 0x146C3A4, 0x146C3B1, 0x146C3B9, 0x146C3D1, 0x146C3D5, 0x146D30B,
      0x146C41B, 0x146C424, 0x146C433, 0x146C440, 0x146C447, 0x146C45A,
      0x146C474, 0x146C49B, 0x146C4A0, 0x146C4A3, 0x146C4B0, 0x146C4B5, 0x146C4B7, 0x146C4BB, 0x146C4BE,
      0x146C4C9, 0x146C4D1, 0x146C4F7, 0x146C509, 0x146C62B,
      0x146CC3D, 0x146CC49, 0x146CC51]),
    ('mapping_assignment_registered_event',
     'Another tag-E5 subscriber reads screen+27D4, bounds that network index<4, and fills inverse slot1..3 before using whole per-slot widget at +53A78.',
     [0xB9019F, 0xB901C5, 0xB901D2, 0xB901DA, 0xB901E1, 0xB901E5, 0xB901EB, 0xB901F2,
      0xB901F7, 0xB901FC, 0xB90203, 0xB9020E, 0xB90211, 0xB90217, 0xB9021F, 0xB90228, 0xB9022F, 0xB9023C]),
    ('four_slot_release_and_transition',
     'Screen update scans inverse map and paired widgets exactly four times, clears forward[networkIndex] and inverse[slot]. Separate transition hides/updates four widgets. Does not prove destructor coverage.',
     [0x146CFD0, 0x146CFD7, 0x146CFE3, 0x146D22B, 0x146D237, 0x146D245,
      0x146D28E, 0x146D296, 0x146D29B, 0x146D2A6, 0x146D2AD, 0x146D2B2, 0x146D2B9, 0x146D2C0, 0x146D2C3,
      0x1470A76, 0x1470B48, 0x1470B4F, 0x1470B69, 0x1470B99, 0x1470B9E, 0x1470BA5, 0x1470BA9]),
    ('subobject_ui_behavior',
     '1893D40 writes selected value to widget+3C4, searches a 21-entry table, and uses UI functions at 1448690 / 144F800 on widget+110. Exact user-facing selection name is unresolved.',
     [0x1893D59, 0x1893D5C, 0x1893D62, 0x1893D70, 0x1893D76, 0x1893D7A, 0x1893D7F,
      0x1893DAF, 0x1893DDE, 0x1893DE2, 0x1893DEC]),
    ('separate_network_index_records_in_same_screen',
     'The screen also has four records at +10 with stride 9F0 ending at +27D0. Constructor initializes four. 146FC40 resolves a roster peer to its network index, gates index<4, then copies 9F0 bytes to the indexed record. This index is deliberately distinct from the forward-map display slot.',
     [0x14A17F4, 0x14A17F9, 0x14A1800, 0x14A1818, 0x14A181F, 0x14A1821, 0x14A1908, 0x14A190C,
      0x146FC79, 0x146FD37, 0x146FD47, 0x146FD92, 0x146FD9B, 0x146FD9F, 0x146FDA6,
      0x146FDB6, 0x146FDC0, 0x146FDC7, 0x146FDD6, 0x146FDDA, 0x146FDE6, 0x146FDE9,
      0x146FDF6, 0x146FDF9, 0x146FE31, 0x146FE3D, 0x146FE43, 0x146FE46, 0x146FE4A,
      0x146FF65, 0x146FF8A, 0x146FF8E, 0x146FF94, 0x146FF9F, 0x1470009, 0x1470010, 0x1470013]),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    dest = Path(args.output)
    if dest.exists():
        raise FileExistsError(dest)
    im = Image(args.evidence)
    groups = []
    for name, provenance, rvas in GROUPS:
        pins = []
        for rva in rvas:
            ins = im.instruction(rva)
            if ins is None:
                raise ValueError('not an unwind instruction boundary: '+hex(rva))
            pin = row(ins)
            pin.update(root=hex(im.root(rva)[0]), fragment=[hex(x) for x in im.containing(rva)])
            pin['rip_memory_targets'] = [hex(ins.address+ins.size+op.mem.disp) for op in ins.operands
                                         if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
            pins.append(pin)
        groups.append(dict(name=name, base_provenance=provenance, anchors=pins))
    strings = []
    for rva, text in [(0x22CAC20, 'MenuScreenLoadout'), (0x22CABF8, 'on_enter (hotjoin=%s, rejoin=%s)')]:
        data = im.read(rva, len(text)+1)
        if data != text.encode()+b'\0':
            raise ValueError('string mismatch')
        strings.append(dict(rva=hex(rva), text=text, bytes=data.hex(), sha256=hashlib.sha256(data).hexdigest()))
    forward, inverse, flags, start, stride, count = 0x27D8, 0x27E8, 0x27F8, 0x53A78, 0x1EE18, 4
    assert forward + count*4 == inverse and inverse + count*4 == flags
    result = dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        groups=groups, captured_strings=strings,
        layout=dict(forward_map=hex(forward), inverse_map=hex(inverse), entries_per_map=count,
                    next_flags=hex(flags), allocation_size_argument='0x2739d0',
                    indexed_record_base='0x10', indexed_record_stride='0x9f0', indexed_record_count=4,
                    indexed_records_end_exclusive=hex(0x10+4*0x9f0),
                    slot_widget_base=hex(start), slot_widget_stride=hex(stride), constructed_slots=count,
                    slots_end_exclusive=hex(start+stride*count), next_widget_base='0xcf2d8',
                    observed_subwidget_base='0x620e8', observed_subwidget_offset=hex(0x620e8-start),
                    index_4_forward_address=hex(forward+4*4), index_4_reverse_address=hex(inverse+4*4)),
        limits=[
            'Screen display/loadout slots are distinct from network indices and gameplay roster ordinals.',
            'These are code/data layout facts, not an observed execution or successful eight-player mod.',
            'Selected anchors and field scans are not a complete relocation inventory or destructor audit.',
            'The allocator-like indirect target and exact selection represented by 1893D40 are unnamed.',
            'Only captured code/read-only/unwind are read; writable objects and live process are not queried.'])
    dest.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(dest), anchors=sum(len(g['anchors']) for g in groups),
                          unique_instructions=len({p['rva'] for g in groups for p in g['anchors']}))))


if __name__ == '__main__':
    main()
