"""Compile bounded client-layout anchors from the pinned, offline game.dll capture."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, row

GROUPS = [
    ('owner_constructor', 'r8 = owner+0x162C8 at 0x134DD07; client object',
     [0x134DD07,0x134DD41,0x134DD65,0x134DD73,0x134DD7A,0x134DD81]),
    ('client_constructor_alternate', 'r8 = incoming client pointer at 0x1082F34',
     [0x1082F34,0x1082F69,0x1082F86,0x1082F8D,0x1082F94,0x1082F9B]),
    ('confirmed_peer_append_registry', 'rbx = tag-0xEB registered ClientSynchronizer pointer',
     [0xB90B6C,0xB90B7B,0xB90B98,0xB90BB2,0xB90BB6,0xB90BE3,0xB90BF2,
      0xB90C03,0xB90C0B,0xB90C12,0xB90C23]),
    ('confirmed_peer_append_direct', 'rdi = rcx client pointer at 0x10872D8',
     [0x10872D8,0x10872F1,0x1087302,0x1087306,0x1087333,0x1087342,
      0x108734C,0x108736A]),
    ('confirmed_peer_remove_and_neighbor_arrays', 'rbx = rcx client pointer at 0x1087559',
     [0x1087559,0x10875D0,0x10875F2,0x10875F8,0x1087612,0x1087618,
      0x1087626,0x108762E,0x1087636,0x108763E,0x1087660,0x1087669,
      0x108767C,0x108768F,0x1087696,0x10876A4,0x10876B2,0x10876C4,
      0x10876CC,0x10876D1,0x10876E2,0x10876E7,0x10876FA,0x108770C,
      0x1087714,0x108771C,0x108772C,0x1087730]),
    ('client_reset_primary', 'rdi = rcx client pointer at 0x10845D3',
     [0x10845D3,0x10849BD,0x10849D2,0x10849D6,0x10849E5,0x10849ED,
      0x10849F7,0x1084A28]),
    ('client_reset_secondary', 'r15 = rcx client pointer at 0x1087037',
     [0x1087037,0x1087066,0x10870A0,0x10870A4,0x1087219,0x1087251,
      0x1087260,0x1087298]),
    ('kicked_path_and_host_migration_handoff',
     'rbx = tag-0xEB client pointer; 0x1089720 is separate host migration root',
     [0xB91365,0xB91376,0xB9140A,0xB91422,0xB91426,0xB91446,
      0xB9144F,0xB9159D,0x1089E9F]),
    ('client_adjacent_peer_keyed_array', 'rcx is client pointer; +0x150 is separate from +0xD0 records',
     [0x1084F59,0x1084F7F,0x1084F83,0x1084F8E,0x1084F91,0x1084F95]),
    ('excluded_plus14_read_examples',
     'other objects: event-payload list count or host member slot, not client +0xD0 record',
     [0x1087945,0xB919C4,0x108BB76,0x108DDCB]),
]

LAYOUT = [
    {'count_offset':'0x10','base_offset':'0x18','stride':8,'next_field_offset':'0x38','in_object_capacity':4,
     'provenance':'client remove root 0x1087540: 0x10876A4–0x10876CC'},
    {'count_offset':'0x38','base_offset':'0x40','stride':16,'next_field_offset':'0x80','in_object_capacity':4,
     'provenance':'client remove root 0x1087540: 0x1087660–0x1087696'},
    {'count_offset':'0x80','base_offset':'0x88','stride':16,'next_field_offset':'0xC8','in_object_capacity':4,
     'provenance':'client remove root 0x1087540: 0x10876D1–0x1087733'},
    {'count_offset':'0xC8','base_offset':'0xD0','stride':32,'next_field_offset':'0x150','in_object_capacity':4,
     'record_player_index_offset':'0x14',
     'provenance':'append roots 0xB90B20/0x10872C0; remove 0x1087540; ctor +0x150'},
    {'count_offset':None,'base_offset':'0x150','stride':16,'next_field_offset':None,
     'observed_loop_end_exclusive':'0x190','in_object_capacity':4,
     'provenance':'separate client peer-keyed search root 0x1084F50, cmp index,4 at 0x1084F83',
     'caveat':'one-to-one relationship with confirmed peer records not established'},
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True)
    p.add_argument('--client-layout-scan', required=True)
    p.add_argument('--index-scan', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    im = Image(a.evidence)
    groups = []
    for name, provenance, rvas in GROUPS:
        anchors = []
        for rva in rvas:
            ins = im.instruction(rva)
            if ins is None:
                raise ValueError('RVA is not a captured instruction boundary: '+hex(rva))
            item = row(ins)
            item.update(root=hex(im.root(rva)[0]),
                        fragment=[hex(x) for x in im.containing(rva)])
            anchors.append(item)
        groups.append({'name':name,'base_provenance':provenance,'anchors':anchors})
    source_scans = []
    for path in (Path(a.client_layout_scan),Path(a.index_scan)):
        raw = path.read_bytes()
        data = json.loads(raw)
        if data['capture_sha256'] != im.report['capture_sha256']:
            raise ValueError('capture mismatch in '+str(path))
        source_scans.append({'path':str(path),'sha256':sha(raw)})
    layout_scan = json.loads(Path(a.client_layout_scan).read_text(encoding='utf-8'))
    index_scan = json.loads(Path(a.index_scan).read_text(encoding='utf-8'))
    client_plus14 = [x for x in layout_scan['hits'] if x['displacement']=='0x14']
    possible_fixed = [x for x in index_scan['hits'] if x['displacement'] in ('0xe4','0x104','0x124','0x144')]
    result = {
        'schema_version':1, 'capture_sha256':im.report['capture_sha256'],
        'source_sha256':EXPECTED, 'source_scans':source_scans,
        'method':'known RVA instruction-boundary revalidation plus previously bounded client layout/index scans',
        'client_layout':LAYOUT, 'operation_groups':groups,
        'index_reader_audit':{
            'record_offset':'0x14',
            'client_string_candidate_root_count':len(layout_scan['candidate_roots']),
            'client_string_candidate_plus14_hits':[{'root':x['root'],'rva':x['rva'],'asm':x['asm']}
                                                   for x in client_plus14],
            'nearby_code_ranges':index_scan['ranges'],
            'fixed_client_record_index_displacement_candidates':[
                {'root':x['root'],'rva':x['rva'],'asm':x['asm']} for x in possible_fixed],
            'confirmed_client_record_index_scalar_readers':[],
            'limits':['No proven scalar reader in inspected roots/ranges is not a global absence proof.',
                      'Whole-record copies and pointer escape could convey the field without a +0x14 scalar read.',
                      'Displacement equality alone cannot establish base provenance.']},
        'mod_relevance':{
            'count_driven_paths':['two append variants after storage exists',
                                  'remove/swap entire 0x20-byte record',
                                  'reset pre-clear traversal',
                                  'kicked path traversal'],
            'fixed_four_or_128_byte_paths':['in-object adjacent array boundaries',
                                            'primary reset 8x16-byte clear at +0xD0',
                                            'secondary reset 8x16-byte clear at +0xD0',
                                            'separate +0x150 four-entry search',
                                            'host migration separate four-slot layout'],
            'unknowns':['full client object allocation size and all downstream offsets',
                        'runtime peer-index readers outside inspected bounds',
                        'fifth participant service/gameplay acceptance']}}
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2)+'\n',encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
