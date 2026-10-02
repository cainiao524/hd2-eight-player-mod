"""Pin 1277920 and its necessary 585B80 leaf from the saved capture only.

No process APIs, capture, candidate emission or installation. The leaf's
jump table is data and is deliberately not decoded as instructions.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'eight_player_candidate_20260927/.native-test-deps'))
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927/indirect'))
import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from inspect_capture import Image, EXPECTED, require, row

ENTRY, END = 0x1277920, 0x1277F7B
BODY_SHA = 'aecf466c012f2e9ba64787a5108b1807753f55166b484d7a0c21c71a21e5d1ca'
LEAF_SHA = '70255ca6064c9b9e4e10f1ec404aad246a72878ae03a3f11a0a10423bed6598e'
TABLE_SHA = '3e9800c014db395115c5e8a102b75e944a39dd4cc9cd4d2b035725f16ab8a87d'
INVENTORY_SHA = '0b664e0f65601221399bfd01ad92f248d373b30376c5e2fdac6b7a702dc93dc2'
sha = lambda blob: hashlib.sha256(blob).hexdigest()


def analyze(im):
    require(sha((HERE / 'roster_property_consumers_native_inventory.json').read_bytes()) == INVENTORY_SHA,
            'Consumer inventory changed')
    blob = im.read(ENTRY, END - ENTRY)
    require(sha(blob) == BODY_SHA, 'Complete root changed')
    instructions = list(im.md.disasm(blob, ENTRY))
    require(sum(x.size for x in instructions) == len(blob), 'Incomplete root decode')
    addresses = {x.address for x in instructions}
    fragments = [f for f in im.functions if ENTRY <= f[0] < END]
    require([(a, b, u) for a, b, u in fragments] == [
        (ENTRY, 0x12779DE, 0x24F9CA0), (0x12779DE, 0x1277F54, 0x24F9CC0),
        (0x1277F54, END, 0x24F9CD8)], 'Unwind fragments changed')
    require(all(im.root(a) == fragments[0] for a, _, _ in fragments), 'Unwind chain changed')
    cfg, calls, rips, indirect = [], [], [], []
    for ins in instructions:
        item = row(ins)
        is_jump, is_call = ins.group(cs.CS_GRP_JUMP), ins.group(cs.CS_GRP_CALL)
        if is_jump or is_call:
            if ins.operands[0].type == X86_OP_IMM:
                target = ins.operands[0].imm
                item['target_rva'] = hex(target)
                if is_jump:
                    require(target in addresses, 'Nonlocal or unaligned root jump')
                    cfg.append(item)
                else:
                    calls.append(item)
            else:
                indirect.append(item)
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                item = row(ins)
                item.update(target_rva=hex(ins.address + ins.size + op.mem.disp),
                            displacement_offset=ins.disp_offset, displacement_size=ins.disp_size)
                rips.append(item)
    by_address = {x.address: x for x in instructions}
    arrays = []
    for at, encoding, group, field in [
        (0x12779F5, '420f2fac182c010000', 'primary', 0x24),
        (0x1277A06, '468b8419b4030000', 'property', 0xC)]:
        require(by_address[at].bytes.hex() == encoding, 'Roster operand changed')
        arrays.append(dict(**row(by_address[at]), group=group, field_offset=field,
                           binding='R11 from global3326468; ordinal from S map',
                           new_offset=0x40 + field if group == 'primary' else 0x580 + field))
    leaf = im.read(0x585B80, 0x28)
    table = im.read(0x585BA8, 52)
    require(sha(leaf) == LEAF_SHA and sha(table) == TABLE_SHA, 'Leaf/table changed')
    targets = list(struct.unpack('<13I', table))
    require(targets == [0x585B9B] * 13, 'Leaf table targets changed')
    return dict(
        source_sha256=EXPECTED, capture_identity_sha256=im.report['capture_sha256'],
        inventory_sha256=INVENTORY_SHA, replay_sha256=sha(Path(__file__).read_bytes()),
        body=dict(entry=hex(ENTRY), end_exclusive=hex(END), size_bytes=len(blob),
                  sha256=sha(blob), bytes_hex=blob.hex(), instructions=[row(x) for x in instructions],
                  fragments=[dict(start=hex(a), end=hex(b), unwind=hex(u), sha256=sha(im.read(a, b-a)))
                             for a, b, u in fragments],
                  local_branches=cfg, direct_calls=calls, rip_relocations=rips,
                  indirect_controls=indirect, roster_array_reads=arrays),
        necessary_leaf=dict(entry='0x585b80', end_exclusive='0x585ba8', sha256=sha(leaf),
                            bytes_hex=leaf.hex(), instructions=[row(x) for x in im.md.disasm(leaf, 0x585B80)],
                            jump_table=dict(rva='0x585ba8', size_bytes=52, sha256=sha(table),
                                            bytes_hex=table.hex(), targets=[hex(x) for x in targets]),
                            scope='Actual calls use lowDWORD3, highDWORD13/14; leaf returns13/14, overwrites EDX/R8, preserves R9 and all XMM'),
        decision=dict(
            reads='Both primary+24h and property+Ch must use common B; keeping only the inventoried property patch is incomplete',
            index='Network DWORD and map ordinal remain distinct; BT register bit position wraps modulo32, FFFFFFFF is explicitly skipped',
            mask='All exits of the mask loop converge at1277A3C; EDX loop count is overwritten by585B80 before later use. Preserve loop and side effects; no mask-based admission result established',
            early_effect='Input record+10 float is updated at127795A before roster lookup or validation; late rejection would not be side-effect-free',
            other_owner='Global3326D20, +6C count/+110 pointers and +F8 map are a different source; do not redirect to roster B or rename its ordinal as network index'),
        limits=[
            'Bounded saved-code analysis; no game process, multiplayer or full function execution',
            'Only585B80 is expanded; other root callees, callback effects and ring32 record ownership remain boundaries',
            'Complete root bytes/CFG are fixed, but global alias closure and live storage/caller lifetimes are not proved',
            'No candidate source, hook, rejection policy or Windows unwind emitted by this replay'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=HERE.parent / 'evidence/existing-code-evidence-25480438')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refusing to overwrite output')
    result = analyze(Image(args.evidence))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    body = result['body']
    print(json.dumps(dict(bytes=body['size_bytes'], instructions=len(body['instructions']),
                          local_branches=len(body['local_branches']), calls=len(body['direct_calls']),
                          rips=len(body['rip_relocations']), indirect=len(body['indirect_controls']))))
