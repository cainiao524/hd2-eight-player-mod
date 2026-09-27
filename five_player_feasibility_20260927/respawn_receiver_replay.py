"""Replay the bounded respawn RPC -> roster state -> object-handle path.

Reads only the existing fingerprinted game.dll capture. No process access,
installation writes, or assumptions about uncaptured runtime API targets.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row, sha

PINS = {
    'local_and_remote_six_fields': [
        0xAC82A1, 0xAC82B9, 0xAC82CF, 0xAC82DA, 0xAC82DE,
        0xAC82E3, 0xAC82E8, 0xAC82EB, 0xAC82EF, 0xAC82F4,
        0xAC82F8, 0xAC82FE, 0xAC8303, 0xAC8323, 0xAC8328,
        0xAC832C, 0xAC8330, 0xAC8333, 0xAC8335, 0xAC833A,
        0xAC833F, 0xAC8343,
    ],
    'sender_hash_and_descriptors': [
        0xBE193F, 0xBE1941, 0xBE1944, 0xBE1947, 0xBE194C,
        0xBE194E, 0xBE1953, 0xBE195B, 0xBE1963, 0xBE196B,
        0xBE1973, 0xBE1978, 0xBE197D, 0xBE1984, 0xBE1986,
        0xBE198B, 0xBE1993, 0xBE1998, 0xBE19A0, 0xBE19A8,
        0xBE19AC, 0xBE19B4, 0xBE19B9, 0xBE19BE, 0xBE19C2,
        0xBE19CA, 0xBE19D2, 0xBE19D7, 0xBE19DC, 0xBE19E0,
        0xBE19E8, 0xBE19ED, 0xBE19F1, 0xBE19F9,
    ],
    'receiver_decode_and_native_handler': [
        0xBA73A5, 0xBA73B1, 0xBA73B3, 0xBA73B8, 0xBA73C1,
        0xBA73C3, 0xBA73C8, 0xBA73D1, 0xBA73D3, 0xBA73D8,
        0xBA73DC, 0xBA73E1, 0xBA73E5, 0xBA73EA, 0xBA73EE,
        0xBA73F2, 0xBA73F5, 0xBA73F9, 0xBA73FD, 0xBA7403,
        0xBA7406, 0xBA740A, 0xBA740E, 0xBA7412, 0xBA7415,
        0xBA7419, 0xB8E97E, 0xB8E987, 0xB8E98A, 0xB8E98D,
        0xB8E9A0, 0xB8E9AB, 0xB8E9B8, 0xB8E9CD, 0xB8E9E6,
        0xB8E9E9, 0xB8E9ED, 0xB8E9F2, 0xB8E9F6,
        0xB8E9FB, 0xB8EA09,
    ],
    'position_and_waiting_state_write': [
        0xAC8411, 0xAC841F, 0xAC842A, 0xAC844B, 0xAC8455,
        0xAC845C, 0xAC8469, 0xAC8489, 0xAC8499, 0xAC856F,
        0xAC84AD, 0xAC84B3, 0xAC84B9, 0xAC84BF, 0xAC84CB,
        0xAC84CD, 0xAC84D5, 0xAC84D8, 0xAC84E0, 0xAC84E6,
        0xAC84ED, 0xAC85E1, 0xAC85F0, 0xAC877C, 0xAC8782,
        0xAC8784, 0xAC8787, 0x608A98, 0x608A9B, 0x608B5A,
        0x608B2A, 0x608B2C, 0x608B30, 0x608B3B, 0x608B40,
        0x608B43, 0x608B45, 0x608B4C,
    ],
    'waiting_state_to_local_object_creation': [
        0xACC638, 0xACC640, 0xACC64E, 0xACC65B, 0xACC669,
        0xACC773, 0xACC780, 0xACC789, 0xACC78C, 0xACC792,
        0xACC795, 0xACC7F1, 0xACC850, 0xACC87A,
        0xACC8CC, 0xACC8D0, 0xACC8D6, 0xACC8DD, 0xACC8E1,
        0xACC8E7, 0xACC8EB, 0xACC926, 0xACC92C, 0xACC932,
        0xACC93E, 0xACC944, 0xACC94B, 0xACC957, 0xACC95E,
        0xACC966, 0xACC96E, 0xACC972, 0xACC974, 0xACC979,
        0xACC97C, 0xACC97F,
    ],
    'object_creation_boundary_and_handle_association': [
        0xAC8896, 0xAC889D, 0xAC88B0, 0xAC88B9, 0xAC88C0,
        0xAC88CD, 0xAC88E9, 0xAC88F5, 0xAC8996, 0xAC8909,
        0xAC890B, 0xAC8B4E, 0xAC8B6B, 0xAC8BA1, 0xAC9000,
        0xAC90B8, 0xAC9BE9, 0xAC9BF0, 0xAC9BF7, 0xAC9BFE,
        0xAC9C05, 0xAC9C08, 0xAC9C0B, 0xAC9C15, 0xAC9C19,
        0xAC9C23, 0xAC9C26, 0xAC9C28, 0xAC9C2B, 0xAC9C2D,
        0xAC9C42, 0xAC9C49, 0xAC9C4C, 0xAC9C4E,
        0x60782E, 0x607831, 0x607833, 0x6078AB, 0x6078BE,
        0x6078C1, 0x607982, 0x607988, 0x60798A, 0x60798D,
        0x6079B5,
    ],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--evidence', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    require(not a.output.exists(), 'refusing overwrite')
    im = Image(a.evidence)
    cache = {}
    pins = {}
    for group, addresses in PINS.items():
        pins[group] = []
        for address in addresses:
            fn = im.containing(address)
            require(fn is not None, f'no unwind fragment: {address:#x}')
            if fn[0] not in cache:
                cache[fn[0]] = {i.address: i for i in im.md.disasm(im.read(fn[0], fn[1] - fn[0]), fn[0])}
            i = cache[fn[0]].get(address)
            require(i is not None, f'not an instruction boundary: {address:#x}')
            pins[group].append({**row(i), 'root': hex(im.root(address)[0])})
    table_rva, table_count = 0x214C2E0, 592
    table = im.read(table_rva, table_count * 8)
    pointers = [x[0] - im.base for x in struct.iter_unpack('<Q', table)]
    require(pointers.count(0xBA7390) == 1, 'receive wrapper pointer absent/duplicated')
    callback_index = pointers.index(0xBA7390)
    occurrences = []
    for area in im.report['ranges']:
        data = im.read(area['rva'], area['size'])
        at = 0
        while (at := data.find(struct.pack('<I', 0x280728D6), at)) >= 0:
            occurrences.append({'rva': hex(area['rva'] + at), 'range': area['label']})
            at += 1
    strings = []
    for rva in (0x2254B30, 0x2254B90):
        raw = im.read(rva, 120).split(b'\0')[0]
        strings.append({'rva': hex(rva), 'bytes': raw.hex(), 'text': raw.decode('ascii')})
    result = {
        'source_sha256': EXPECTED,
        'capture_sha256': im.report['capture_sha256'],
        'game_sha256': im.report['game_sha256'],
        'build_id': im.report['build_id'],
        'runtime_verified': im.report['runtime_verified'],
        'pins': pins,
        'outgoing': {'sender': '0xbe1920', 'hash': '0x280728d6', 'descriptor_types': [1, 3, 1, 0, 1, 0], 'descriptor_sizes': [4, 12, 4, 4, 4, 4]},
        'receive_semantic_pair': {'wrapper': '0xba7390', 'handler': '0xb8e970', 'local_equivalent': '0xac83f0', 'runtime_hash_binding_verified': False},
        'callback_pointer': {'table_rva': hex(table_rva), 'table_count': table_count, 'table_sha256': sha(table), 'index_zero_based': callback_index, 'entry_rva': hex(table_rva + 8 * callback_index), 'bytes': table[8 * callback_index:8 * callback_index + 8].hex()},
        'hash_occurrences_in_captured_ranges': occurrences,
        'state_label_strings': strings,
        'engine_creation_boundary': {'call_rva': '0xac9c19', 'api_global': '0x3326308', 'pointer_path': ['api + 0xc0', 'dereference object + 0', 'vtable + 0x18'], 'resource_argument_rdx': '0xb04d927afb137b9b', 'return': 'EAX -> ESI -> R8D at 0xac9c49 -> 0x607820 -> roster + ordinal*0x70 + 0x108', 'target_pointer_captured': False},
        'limits': [
            'No live process access; no dynamic trace or multiplayer validation.',
            'Six-field matching and local-equivalent dispatch establish semantic pairing, not the runtime RPC registry edge.',
            'The state-2 consumer shown is ordinal zero with player-object +0x14 bit 0 set, inside the previously identified four-candidate update; the bit has not been independently named local.',
            'The engine call returns an object handle associated with the player roster and advances state to Spawned; its exact named API and allocation capacity remain unresolved.',
            'Spawn-position computations can alter the stored vector before the indirect call; no byte-for-byte identity of a final engine descriptor is claimed.',
            'The pointer path includes dereferencing api+C0 to an object, then its first pointer to a vtable; it is not a direct api+C0+18 slot.',
        ],
    }
    a.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{a.output}: {sum(map(len, pins.values()))} instruction pins; wrapper pointer index {callback_index}')


if __name__ == '__main__':
    main()
