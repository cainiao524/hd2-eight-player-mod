"""Produce an offline storage fixture with the existing native x64 insert emitter.

Eight insertions and their original map helper execute in Unicorn. Peer/lifecycle
and property values are explicit fixture inputs, not native admission evidence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import native_insert_image
from native_property_library import Library

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'hellforge_multiplayer'


def generate(output,property_library):
    lock = json.loads((PROJECT / 'native-storage.lock.json').read_text(encoding='utf-8'))
    for name, digest in lock['legacy_source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Legacy source changed: ' + name)
    path = ROOT / 'eight_player_candidate_20260927/tests/test_native_roster_insert.py'
    spec = importlib.util.spec_from_file_location('ep_storage_fixture', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if m.unicorn.__version__ != lock['unicorn'] or m.capstone.__version__ != lock['capstone']:
        raise RuntimeError('Emulator/disassembler version changed')
    native_insert_image.bind_fixture(m,Library(property_library))
    f = m.Fixture('dense_legacy', t=0, d=0, p=0, flag=1)
    f.write(m.B, bytes(0x680))
    runs = []
    for i in range(8):
        descriptor = m.ENTITY + 0x40 * i
        f.write(descriptor + 0x14, b"\x01")
        f.seed(); f.uc.reg_write(m.reg('rdx'), descriptor)
        f.outcome = None; f.trace.clear(); f.calls.clear()
        f.run('hellforge_storage_insert_' + str(i))
        if f.outcome != 'return' or struct.unpack('<III', f.read(m.S + 0x80, 12)) != (i + 1,) * 3:
            raise RuntimeError('Native insertion failed')
        if struct.unpack('<Q', f.read(m.B + i * 8, 8))[0] != descriptor:
            raise RuntimeError('Native pointer write differs')
        runs.append({'ordinal': i, 'instructions': len(f.trace), 'map_calls': sum(x['kind']=='map' for x in f.calls), 'mover_calls': sum(x['kind']=='move' for x in f.calls)})
    before = f.read(m.S, 0xE8) + f.read(m.B, 0x680) + f.read(m.MAP, 64)
    f.seed(); f.outcome = None; f.writes.clear(); f.run('hellforge_storage_ninth_refused')
    if f.outcome != 'reject' or f.writes or before != f.read(m.S, 0xE8) + f.read(m.B, 0x680) + f.read(m.MAP, 64):
        raise RuntimeError('Ninth insert did not refuse before mutation')
    # These values model the separate later admission/property callbacks.
    # Do not label them as outputs of the insertion routines above.
    for i in range(8):
        f.write(m.B + 0x3C0 + i * 0x38, m.u64(100 + i))
        f.write(m.B + 0x3C0 + i * 0x38 + 0x18, m.u32(3))
        f.write(m.B + 0x580 + i * 0x20, m.u32(0x1000 + i))
        f.write(m.B + 0x580 + i * 0x20 + 0xC, m.u32((3 * i + 2) % 8))
    user = 0x18201000000
    def export(path):
        regions = [(m.S, f.read(m.S, 0xE8)), (m.B, f.read(m.B, 0x680)), (m.MAP, f.read(m.MAP, 64))]
        regions += [(m.ENTITY + i * 0x40, f.read(m.ENTITY + i * 0x40, 12)) for i in range(8)]
        regions += [(m.GAME + 0x3326468, m.u64(m.S)), (m.GAME + 0x347CEF0, m.u64(user)), (user + 0xB398, m.u64(107))]
        blob = b'EPNATV1\0' + struct.pack('<QQQI', m.GAME, m.S, m.B, len(regions))
        for address, data in regions:
            blob += struct.pack('<QI', address, len(data)) + data
        path.write_bytes(blob)
        return {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
    exported = {output.name: export(output)}
    # Remove ordinal 4 through the actual candidate and saved deletion/move code.
    remove = m.load('ep_storage_remove', ROOT / 'eight_player_candidate_20260927/Native/roster_remove.py')
    evidence_path = ROOT / 'five_player_feasibility_20260927/roster_remove_native_evidence.json'
    bodies = remove.load_sources(evidence_path)
    evidence = json.loads(evidence_path.read_bytes())
    delete = bytes.fromhex(evidence['bodies'][hex(remove.DELETE_RVA)]['bytes_hex'])
    artifact = remove.build(bodies['legacy'], kind='legacy', game_base=m.GAME,
        code_address=m.GAME+0x10110000, roster_address=m.S, storage_address=m.B,
        move_code_address=f.move_entry, reject_address=f.reject)
    code = bytes.fromhex(artifact['code_hex'])
    f.map(artifact['entry_address'],len(code)); f.write(artifact['entry_address'],code)
    f.map(m.GAME+remove.DELETE_RVA,len(delete)); f.write(m.GAME+remove.DELETE_RVA,delete)
    insertion = f.start; f.start = artifact['entry_address']
    f.seed(); f.uc.reg_write(m.reg('rdx'),m.ENTITY+4*0x40)
    f.outcome=None; f.trace.clear(); f.calls.clear(); f.run('hellforge_storage_remove_ordinal_4')
    if f.outcome!='return' or struct.unpack('<III',f.read(m.S+0x80,12))!=(7,7,7):
        raise RuntimeError('Native removal failed')
    if struct.unpack('<Q',f.read(m.B+4*8,8))[0] != m.ENTITY+7*0x40:
        raise RuntimeError('Native removal did not move the last member into the hole')
    removal_instructions=len(f.trace)
    removed=output.with_suffix('.removed.bin'); exported[removed.name]=export(removed)
    f.start=insertion; f.seed(); f.uc.reg_write(m.reg('rdx'),m.ENTITY+4*0x40)
    f.outcome=None; f.trace.clear(); f.run('hellforge_storage_rejoin')
    if f.outcome!='return' or struct.unpack('<III',f.read(m.S+0x80,12))!=(8,8,8):
        raise RuntimeError('Native reinsert failed')
    # Separate admission/property callbacks remain explicit synthetic inputs.
    f.write(m.B+0x3C0+7*0x38,m.u64(104)); f.write(m.B+0x3C0+7*0x38+0x18,m.u32(3))
    f.write(m.B+0x580+7*0x20,m.u32(0x1004)); f.write(m.B+0x580+7*0x20+0xC,m.u32(6))
    rejoined=output.with_suffix('.rejoined.bin'); exported[rejoined.name]=export(rejoined)
    return {'insert_images_emitted_by_native_mod_code':True,'mover_image_emitted_by_native_mod_code':True,'mover_image_bytes':f.native_mover_image_bytes,'native_insertions': runs, 'ninth_refused_before_write': True,
            'fixtures': exported, 'native_removal_instructions': removal_instructions,
            'native_reinsert_instructions': len(f.trace),
            'native_outputs': ['descriptor pointers', 'tracked/dense/prefix counts', 'entity-to-ordinal map', 'primary/auxiliary initialization'],
            'synthetic_inputs': ['descriptors/entity IDs', 'peer IDs', 'lifecycles', 'avatar network IDs', 'player network indexes', 'local peer', 'generation tickets'],
            'game_access': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--property-library',required=True,type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.output.resolve(),args.property_library)))
