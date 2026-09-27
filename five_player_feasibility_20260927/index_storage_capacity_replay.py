"""Replay tag-0x73 network-index storage findings from the pinned offline capture.

This reads only capture-report.json and captured-data.bin. It neither accesses
the running process nor produces a patch. Layouts below are interpretations of
the pinned anchors, not an eight-player implementation.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

GROUPS = [
    ('owner_identity_and_registry',
     'The same owner-relative object is initialized, registered as tag 0x73, published to global 0x3326AE0, updated, and passed to teardown. Adjacent owner object begins at +0x7FF1A0.',
     [0x5563CB, 0x5563D5, 0x5563DC, 0x5563E9, 0x5563F0, 0x5563FB, 0x556402,
      0x556410, 0x55641D, 0x556421, 0x556428, 0x55642F, 0x556432,
      0x55648B, 0x5564AF, 0x5564B6, 0x5564BB, 0xB279D4, 0xB279D8, 0xB279DF,
      0xB279E7, 0xB279EB, 0xB279F4, 0xB27B01,
      0x568E12, 0x568E19, 0x568E20, 0x564D15, 0x564D1C, 0x57D953, 0x57D97F, 0x57D990, 0x57D9B0]),
    ('network_index_write',
     'Global object in R14; lookup by peer ID in known network owner supplies network index. Index is multiplied by 24 with no local <4 bound, then writes peer ID, integer accumulators, and a flag.',
     [0x631149, 0x631182, 0x63118B, 0x63119B, 0x6311A2, 0x6311A9, 0x6311AD,
      0x6311C4, 0x6311C8, 0x6311D0, 0x6311D4, 0x6311DC, 0x6311DF, 0x6311EB,
      0x63127D, 0x631296, 0x63129E, 0x6312A2, 0x6312AE, 0x6312B2, 0x6312C4,
      0x6312C8, 0x6312CC, 0x6312D1, 0x6312D7, 0x6312E4, 0x6312F4, 0x631300, 0x631305,
      0x1191536, 0x119153B, 0x119153E, 0x11915A2, 0x11915A5]),
    ('consume_then_clear_snapshot',
     'Input object becomes R14. Rebuild final records by active object ordinal, resolve corresponding peer ID and network index, copy 24 bytes from index cache after checking peer ID, then clear exactly 0x60 bytes of the cache.',
     [0xACB137, 0xACB13E, 0x631328, 0x63132D, 0x631334, 0x63133B, 0x631342,
      0x631349, 0x631350, 0x631357, 0x63135E, 0x631390, 0x631422, 0x63142A,
      0x631430, 0x631434, 0x6314E1, 0x6314EA, 0x6314F5, 0x631500, 0x631507,
      0x63150F, 0x631514, 0x631516, 0x63151A, 0x631522, 0x631524, 0x63152D,
      0x631535, 0x63153F, 0x63154D, 0x631551, 0x631559, 0x63161D, 0x631686,
      0x63168D, 0x631693, 0x63169A, 0x6316BE, 0x6316C1, 0x6316C9, 0x6316D1,
      0x6316D9, 0x6316E1, 0x6316E9]),
    ('adjacent_live_typed_storage',
     'RIP global provenance at reset; the region at +C500 is cleared independently, then has its own entry keys, integer/float/bool values, and type discriminator consumed by the direct serializer 0x62DF40.',
     [0x62D21A, 0x62D221, 0x62D223, 0x62D22A, 0x62D231,
      0x62D236, 0x62D23D, 0x62D23F, 0x62D245, 0x62D24A, 0x62D24F,
      0x62D259, 0x62D260, 0x62D267, 0x62D26E, 0x62D275,
      0x62D29D, 0x62D2A1, 0x62D2A5, 0x62D2B0, 0x62D2C4, 0x62D2C8, 0x62D2CF,
      0x62D2D3, 0x62D2E8, 0x62D2F0, 0x62D2F8, 0x62D2FD, 0x62D302, 0x62D30A,
      0x1460C63, 0x1460C6A, 0x1460C71, 0x1464893, 0x146489A, 0x14648A1,
      0xB856BF, 0xB856CB, 0xB856D3, 0xB856D5, 0xB856DC, 0xB856DF, 0xB856E4,
      0xB856E6, 0xB856EA, 0xB856ED,
      0x62DF69, 0x62E040, 0x62E044, 0x62E04F, 0x62E055, 0x62E06E, 0x62E0AE,
      0x62E0D6, 0x62E122]),
    ('object_append_four_bounds',
     'Three independent code entries append corresponding objects into this global subsystem. Each checks total count+1 <=4 and explicitly writes to address zero on failure. Direct execution dispatch for these entries is not yet identified.',
     [0x53E136, 0x53E140, 0x53E147, 0x53E14B, 0x53E14E, 0x53E150,
      0x53E16A, 0x53E16E, 0x53E176, 0x53E17E, 0x53E18D, 0x53E19E,
      0x53E1BA, 0x53E1C4, 0x53E1CA, 0x53E1CC, 0x53E1CF, 0x53E1D1, 0x53E237,
      0x53E249, 0x53E261, 0x631B9A, 0x631BA4, 0x631BAA, 0x631BAC, 0x631BAF,
      0x631BB1, 0x631BFC, 0x631C00, 0x631C08, 0x631C10, 0x631C18, 0x631C2A,
      0x631C42, 0x631C4A]),
    ('move_and_compact_parallel_records',
     '0x631930 and inlined 0x631CE0 move both pointer records and complete 40-byte records, update the embedded lookup map, and use three lifecycle counts. Owner update also calls 0x631930.',
     [0x63193D, 0x63194F, 0x631957, 0x63195B, 0x631963, 0x631967, 0x631970,
      0x631978, 0x631981, 0x631989, 0x631993, 0x63199E, 0x6319BB, 0x631A02,
      0x631CEA, 0x631CF0, 0x631CF3, 0x631D01, 0x631D22, 0x631D2E, 0x631D3A,
      0x631D42, 0x631D4A, 0x631D52, 0x631D5A, 0x631D63, 0x631DD4, 0x631DD9,
      0x631DE1, 0x631E04]),
    ('final_snapshot_fixed_four_consumers',
     'The same global object feeds a four-record peer-ID search at +C440 and a fully unrolled four-term sum of record+0xC fields. Exact high-level system / resource names are not proven by these instructions.',
     [0x126EB75, 0x126EBE7, 0x126EBF1, 0x126EBF8, 0x126EBFC, 0x126EBFF,
      0x126EC03, 0x126EC07, 0x126EC1B, 0x126EC54, 0x126EC60, 0x126EC66,
      0x126EC6C, 0x126EC72, 0x126EC78]),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    path = Path(a.output)
    if path.exists():
        raise FileExistsError(path)
    im = Image(a.evidence)
    groups = []
    for name, provenance, sites in GROUPS:
        anchors = []
        for site in sites:
            ins = im.instruction(site)
            if ins is None:
                raise ValueError('Not a captured instruction boundary: '+hex(site))
            item = row(ins)
            item.update(root=hex(im.root(site)[0]), fragment=[hex(v) for v in im.containing(site)])
            item['rip_memory_targets'] = [hex(ins.address+ins.size+op.mem.disp)
                                          for op in ins.operands
                                          if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
            anchors.append(item)
        groups.append({'name':name, 'base_provenance':provenance, 'anchors':anchors})
    boundaries = {
        'final_snapshot': {'base':0xC440, 'stride':24, 'count':4, 'end':0xC4A0},
        'network_index_snapshot': {'base':0xC4A0, 'stride':24, 'count':4, 'end':0xC500},
        'registered_object_pointers': {'base':0x37D70, 'stride':8, 'count':4, 'end':0x37D90},
        'registered_object_records': {'base':0x37D98, 'stride':40, 'count':4, 'end':0x37E38},
    }
    for description in boundaries.values():
        assert description['base'] + description['stride']*description['count'] == description['end']
    assert 0x7C7368 + 0x37E38 == 0x7FF1A0
    collisions = []
    for index in range(4,8):
        base = 0xC4A0 + 24*index
        collisions.append({'network_index':index, 'record_start':hex(base),
                           'peer_id_write':[hex(base),hex(base+8)],
                           'flag_write':hex(base+20),
                           'overlaps_adjacent_live_typed_storage':base >= 0xC500})
    result = {
        'source_sha256':EXPECTED, 'capture_identity_sha256':im.report['capture_sha256'],
        'global_rva':'0x3326ae0', 'owner_relative_object':'0x7c7368', 'registry_tag':'0x73',
        'official_system_name_proven':False,
        'groups':groups, 'layouts':boundaries, 'out_of_array_writes':collisions,
        'limits':[
            'No live process access; no fifth player, object insertion, eight-player match, or playable mod verified.',
            'Index>=4 crosses the proven four-record member-array boundary, not necessarily the heap allocation boundary.',
            'The constructor embeds its own map storage and registers the object pointer; changing only the published global cannot relocate all references.',
            'Scalar integer accumulator count is data-driven; this evidence does not identify its resource names or bound it to three.',
            'Final snapshot ordinal, subsystem registered-object ordinal, and network index are distinct addressing paths; equality is not asserted.',
            'The three add functions are identified implementations; their actual runtime dispatch remains unresolved.',
            'Field scans identify encoded displacement candidates and do not exhaust computed or uncaptured references.',
        ],
    }
    path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output':str(path), 'groups':len(groups), 'anchor_records':sum(len(g['anchors']) for g in groups),
                      'unique_instruction_sites':len({r['rva'] for g in groups for r in g['anchors']})}))


if __name__ == '__main__':
    main()
