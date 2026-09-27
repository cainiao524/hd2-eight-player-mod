"""Replay client network-index consumers from the pinned offline capture only.

--rescan-fields repeats the whole captured-code disp32 search. The default
revalidates selected instruction boundaries and concrete owner provenance.
No process APIs, installed game access, memory writes, or runtime assertions.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'tools'), str(HERE.parent / 'research_handoff_20260927' / 'indirect')]
from inspect_capture import EXPECTED, Image, row
from field_refs import scan_fields
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

GROUPS = [
    ('owner_identity', 'Constructor loads owner from global 0x347CEF0, forms embedded client +0x162C8, and installs owner backpointer.',
     [0x134D754, 0x134DD07, 0x134DD28, 0x134DD41, 0x134DD65]),
    ('peer_to_index_and_secondary_storage',
     '0x631182 loads same owner global. count +16390, peer IDs +16398 and stride 32 select index +163AC. The resulting index addresses a different subsystem at global 0x3326AE0 +0xC4A0 + index*24; its capacity is not proven here.',
     [0x631149, 0x631182, 0x63118B, 0x63119B, 0x6311A2, 0x6311A9, 0x6311AD, 0x6311BD, 0x6311C4, 0x6311C8, 0x6311D0, 0x6311D4,
      0x63127D, 0x631296, 0x63129E, 0x6312A2, 0x6312AE, 0x6312B2, 0x6312C4, 0x6312C8, 0x6312D1, 0x631305]),
    ('index_to_separate_slot_mapping',
     'Tag 0xE5 object in R10 is independent from client. Global owner lookup supplies network index; that index selects a dword at object+0x27D8 + index*4. The selected value must be <4 before object+0x620E8 + selected*0x1EE18 goes to 0x1893D40. This does NOT prove network index equals gameplay roster ordinal.',
     [0xB90054, 0xB9005D, 0xB90060, 0xB9007B, 0xB90089, 0xB900C6, 0xB900CF, 0xB900DF, 0xB900F0, 0xB900F7, 0xB900FB, 0xB90104, 0xB90108,
      0xB90120, 0xB90127, 0xB9012B, 0xB90137, 0xB9013B, 0xB90143, 0xB9014B, 0xB9014E, 0xB90150, 0xB90157, 0xB90160, 0xB90163]),
    ('local_network_index_less_than_four_gate',
     'Same owner global in R8; compares confirmed peer ID with owner+0xB398 (local ID), then directly rejects index>=4 from a special path. This is an unsigned network-index bound, distinct from occupancy or roster count.',
     [0x1086212, 0x1086219, 0x108621C, 0x1086223, 0x1086228, 0x1086230, 0x1086232, 0x1086236, 0x1086238, 0x1086240, 0x1086246, 0x1086248,
      0x108645C, 0x1086460, 0x1086469, 0x108646F, 0x1086799, 0x1086806, 0x108681C, 0x1086823, 0x1086837, 0x10868AA, 0x10868B1, 0x10868B4, 0x10868BB,
      0x10868BF, 0x10868C2, 0x10868C9, 0x10868CC, 0x10868CE, 0x10868D5, 0x10868D7, 0x10868DC, 0x10868E3, 0x10868E8, 0x10868EF, 0x10868F1, 0x1086918]),
    ('inline_reverse_lookup',
     'Same global owner; EBP<4 path searches index +163AC, and returns low 32 bits of peer-ID field +16398 through ECX/EDX. For EBP>=4 this lookup is skipped. Meaning of EBP and consuming subsystem are not established here.',
     [0x139519B, 0x13951A2, 0x13951A9, 0x13951AC, 0x13951AE, 0x13951BB, 0x13951C2, 0x13951C8, 0x13951CC, 0x13951D0, 0x13951D2, 0x1395228, 0x139522A, 0x139522E, 0x1395236]),
    ('record_pointer_escape_uses_flag',
     '0x1083150 receives embedded client via owner update. Direct calls establish leaf 0x1084FD0 entry; both returned record-pointer consumers use byte +0x18, not index +0x14.',
     [0x134E437, 0x134E43E, 0x1083179, 0x10834AF, 0x10834B5, 0x10834B8, 0x10834BD, 0x10834C2, 0x108396B, 0x1083972, 0x1083975, 0x108397A, 0x108397F]),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--rescan-fields', action='store_true')
    a = p.parse_args()
    im = Image(a.evidence)
    out = Path(a.output)
    if out.exists():
        raise FileExistsError(out)
    if a.rescan_fields:
        result = scan_fields(im, [0xE4, 0x104, 0x124, 0x144], [(0x162C8, 0x16458)])
    else:
        groups = []
        for name, provenance, rvas in GROUPS:
            pins = []
            for rva in rvas:
                ins = im.instruction(rva)
                if ins is None:
                    raise ValueError('not a captured unwind instruction boundary: '+hex(rva))
                pin = row(ins)
                pin.update(root=hex(im.root(rva)[0]), fragment=[hex(v) for v in im.containing(rva)])
                pin['rip_memory_targets'] = [hex(ins.address+ins.size+op.mem.disp) for op in ins.operands
                                             if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
                pins.append(pin)
            groups.append({'name':name, 'base_provenance':provenance, 'anchors':pins})
        # Real E8 call in unwind-covered code proves the leaf entry. Sequential
        # decoding through all branches up to the exact final return is sufficient
        # here; the complete 54-byte body contains no uncovered direct targets.
        leaf_start, leaf_end = 0x1084FD0, 0x1085006
        leaf_raw = im.read(leaf_start, leaf_end-leaf_start)
        leaf = list(im.md.disasm(leaf_raw, leaf_start))
        if sum(x.size for x in leaf) != len(leaf_raw) or leaf[-1].mnemonic != 'ret':
            raise ValueError('leaf decode did not cover pinned range')
        result = {
            'capture_sha256': im.report['capture_sha256'], 'source_sha256': EXPECTED,
            'owner_global_rva':'0x347cef0', 'embedded_client_offset':'0x162c8',
            'confirmed_peer_count_owner_offset':'0x16390',
            'confirmed_peer_id_owner_offset':'0x16398',
            'confirmed_peer_index_owner_offset':'0x163ac', 'record_stride':32,
            'groups':groups,
            'proven_leaf':{'entry':hex(leaf_start),'end_exclusive':hex(leaf_end),
                          'entry_proof_calls':['0x10834b8','0x1083975'],
                          'sha256':hashlib.sha256(leaf_raw).hexdigest(),
                          'instructions':[row(x) for x in leaf]},
            'unreferenced_leaf_candidates':[
                {'entry':'0x10869b0','candidate_behavior':'local peer ID -> network index'},
                {'entry':'0x1086a00','candidate_behavior':'specified peer ID -> network index'},
                {'entry':'0x1086a40','candidate_behavior':'network index -> low32(peer ID)'}],
            'limits':[
                'The three unreferenced routines are structural candidates, not proven called entries.',
                'Whole-code field scan supplies candidates; matching displacements alone do not prove object identity.',
                'Network index is not equated to roster ordinal; a separate map is observed in one consumer.',
                'No live execution, object creation success, new participant, or playable mod verified.']}
    out.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
