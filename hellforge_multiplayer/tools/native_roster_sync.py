"""Native property records through the real backend, using only synthetic RAM.

The eight descriptor values are assembled explicitly: this is NOT the game's
complete serializer or entity dispatch. Entity routing, peer state and tickets
remain fixture inputs. Original producer, index leaf and receiver execute.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import native_producer_unwind
import native_receiver_unwind
import native_getter_image
import native_mover_image
from native_property_library import GetterAddresses,GateImage,Library

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'hellforge_multiplayer'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def modules(property_library):
    lock = json.loads((PROJECT / 'native-storage.lock.json').read_text())
    for name, digest in lock['legacy_source_sha256'].items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, 'Changed source: ' + name)
    insert = load('sync_insert', ROOT / 'eight_player_candidate_20260927/tests/test_native_roster_insert.py')
    producer = load('sync_producer', ROOT / 'eight_player_candidate_20260927/tests/test_native_roster_producer.py')
    require(insert.unicorn.__version__ == lock['unicorn'] and insert.capstone.__version__ == lock['capstone'], 'Dependency version mismatch')
    native=Library(property_library)
    native_mover_image.bind_insertion_fixture(insert,native)
    original = producer.native.build
    def with_windows_unwind(source, **addresses):
        reference=native_producer_unwind.with_unwind(original(source, **addresses))
        return native.candidate(1,addresses,reference)
    producer.native.build = with_windows_unwind
    old_receiver = producer.receiver.build
    def receiver_with_windows_unwind(source, **addresses):
        reference=native_receiver_unwind.with_unwind(old_receiver(source, **addresses))
        return native.candidate(2,addresses,reference)
    producer.receiver.build = receiver_with_windows_unwind
    return insert, producer


def entity(node, peer):
    return (node + 1) * 256 + 1 + 8 * peer


def order_for(node):
    # Each node's local member occupies a different ordinal (0..7), while
    # two remote members exchange places to give eight distinct layouts.
    order = list(range(8))
    a, b = (node + 1) % 8, (node + 2) % 8
    order[a], order[b] = order[b], order[a]
    return order


def export(path, m, f, node):
    regions = [(m.S, f.read(m.S, 0xE8)), (m.B, f.read(m.B, 0x680)), (m.MAP, f.read(m.MAP, 64))]
    regions += [(m.ENTITY + i * 0x40, f.read(m.ENTITY + i * 0x40, 12)) for i in range(8)]
    # This local-user view is a fixture input, separate from the producer's
    # original confirmed-peer index lookup (which actually executed).
    user = 0x18201000000
    regions += [(m.GAME + 0x3326468, m.u64(m.S)), (m.GAME + 0x347CEF0, m.u64(user)), (user + 0xB398, m.u64(100 + node))]
    blob = b'EPNATV1\0' + struct.pack('<QQQI', m.GAME, m.S, m.B, len(regions))
    for address, data in regions:
        blob += struct.pack('<QI', address, len(data)) + data
    path.write_bytes(blob)
    return {'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}


def image(path):
    blob = path.read_bytes()
    require(blob[:8] == b'EPNATV1\0', 'Invalid image magic')
    game, roster, storage, count = struct.unpack_from('<QQQI', blob, 8)
    pos, regions = 36, []
    require(count <= 32, 'Invalid region count')
    for _ in range(count):
        address, size = struct.unpack_from('<QI', blob, pos)
        pos += 12
        require(size <= 2048 and pos + size <= len(blob), 'Invalid image extent')
        regions.append((address, blob[pos:pos + size]))
        pos += size
    require(pos == len(blob), 'Trailing image data')
    return game, roster, storage, regions


def produce(output, property_library):
    m, p = modules(property_library)
    packets, artifacts, runs = [], {}, []
    for node in range(8):
        order = order_for(node)
        f = m.Fixture('dense_legacy', t=0, d=0, p=0, flag=1)
        f.write(m.B, bytes(0x680))
        for ordinal, peer in enumerate(order):
            descriptor = m.ENTITY + peer * 0x40
            f.write(descriptor + 8, m.u32(entity(node, peer)))
            f.write(descriptor + 0x14, b'\x01')
            f.seed(); f.uc.reg_write(m.reg('rdx'), descriptor)
            f.outcome = None; f.trace.clear(); f.run('sync_insert')
            require(f.outcome == 'return' and struct.unpack('<III', f.read(m.S + 0x80, 12)) == (ordinal + 1,) * 3, 'Native insertion failed')
            # Admission and lifecycle are NOT recovered by this test.
            f.write(m.B + 0x3C0 + ordinal * 0x38, m.u64(100 + peer))
            f.write(m.B + 0x3C0 + ordinal * 0x38 + 0x18, m.u32(3))
            f.write(m.B + 0x580 + ordinal * 0x20, bytes([0xFF]) * 32)
        own = order.index(node)
        send = p.Fixture(ordinal=own, network=(3 * node + 2) % 8, count=0, entity=entity(node, node),
                         changes={'property_address': m.B + 0x580})
        for address, size in [(m.S, 0xE8), (m.B, 0x680), (m.MAP, 64), (m.ENTITY, 8 * 0x40)]:
            send.map(address, size); send.write(address, f.read(address, size))
        send.write(p.LOCAL_PEER + 0xB398, p.u64(100 + node))
        send.write(p.INDEX_OWNER + 0x16398 + 5 * 32, p.u64(100 + node))
        descriptors = 0x18209100100  # disjoint from the eight player descriptors
        send.map(descriptors, 128); send.uc.reg_write(p.reg('r9'), descriptors)
        send.uc.reg_write(p.reg('rdx'), m.ENTITY + node * 0x40)
        send.run('sync_producer')
        require(send.outcome == 'return' and len(send.alloc_calls) == 1 and len(send.index_calls) == 1, 'Producer path incomplete')
        values = []
        for field, expected_hash in enumerate(p.HASHES):
            field_hash, field_type, pointer = struct.unpack('<IIQ', send.read(descriptors + field * 16, 16))
            require(field_hash == expected_hash and field_type == (1 if field < 4 else 2) and pointer == p.PAYLOAD + field * 4, 'Descriptor contract changed')
            values.append(send.read(pointer, 4))
        wire = b''.join(values)
        require(wire == struct.pack('<8I', 0x7FFF, 0, 0, (3 * node + 2) % 8, 0, 0, 0, 0), 'Native property/index output mismatch')
        packets.append({'sender': node + 1, 'payload': base64.b64encode(wire).decode('ascii')})
        path = output.parent / f'native-sync-{node + 1}-before.bin'
        artifacts[path.name] = export(path, m, send, node)
        runs.append({'node': node + 1, 'local_ordinal': own, 'local_entity': entity(node, node),
                     'network_index': (3 * node + 2) % 8, 'instructions': len(send.trace),
                     'allocator_contract_calls': len(send.alloc_calls), 'actual_index_leaf_calls': len(send.index_calls)})
    result = {'schema': 'native_roster_property_fixture_v1', 'packets': packets, 'artifacts': artifacts,
              'native_producers': runs, 'mover_image_emitted_by_native_mod_code':True, 'game_serializer_executed': False, 'game_access': False}
    output.write_text(json.dumps(result, indent=2) + '\n')
    return {'native_producers': len(runs), 'native_insertions': 64, 'game_access': False}


def consume(input_path, routed_path, output, property_library):
    m, p = modules(property_library)
    source = json.loads(input_path.read_text()); routed = json.loads(routed_path.read_text())
    require(routed['input_sha256'] == hashlib.sha256(input_path.read_bytes()).hexdigest(), 'Stale routed input')
    expected = {item['sender']: base64.b64decode(item['payload'], validate=True) for item in source['packets']}
    deliveries = routed['deliveries']
    require(len(deliveries) == 56 and {(d['sender'], d['recipient']) for d in deliveries} ==
            {(s, r) for s in range(1, 9) for r in range(1, 9) if s != r}, 'Missing/duplicate delivery')
    runs, artifacts, queries = [], {}, []
    native=Library(property_library)
    for node in range(8):
        before_path = input_path.parent / f'native-sync-{node + 1}-before.bin'
        require(hashlib.sha256(before_path.read_bytes()).hexdigest() == source['artifacts'][before_path.name]['sha256'], 'Changed sender image')
        game, roster, storage, regions = image(before_path)
        require((game, roster, storage) == (m.GAME, m.S, m.B), 'Unexpected image layout')
        f = p.Fixture(count=0)
        for address, data in regions:
            f.map(address, len(data)); f.write(address, data)
        a = p.receiver.build(p.RECEIVER_BODY, game_base=game, code_address=game + 0x10020000,
                             roster_address=roster, property_address=storage + 0x580, reject_address=game + 0x10024000)
        code = bytes.fromhex(a['code_hex'])
        f.map(a['entry_address'], len(code)); f.write(a['entry_address'], code)
        f.reject = a['reject_address']; f.map(f.reject, 1); f.write(f.reject, b'\xcc')
        f.map(p.WIRE, 128); f.map(p.CURSOR, 4)
        for delivery in (d for d in deliveries if d['recipient'] == node + 1):
            sender = delivery['sender']
            wire = base64.b64decode(delivery['payload'], validate=True)
            require(wire == expected[sender] and len(wire) == 32, 'Corrupt routed property data')
            cursor = 20
            f.write(p.WIRE + cursor, wire); f.write(p.CURSOR, p.u32(cursor))
            f.seed(); f.write(p.RSP, p.u64(f.stop))
            # Explicit format/entity-dispatch bridge, not a recovered game envelope.
            for reg, value in dict(rsp=p.RSP, rcx=roster, rdx=entity(node, sender - 1), r8=p.WIRE, r9=p.CURSOR).items():
                f.uc.reg_write(p.reg(reg), value)
            f.outcome = None; f.trace.clear(); f.writes.clear(); f.alloc_calls.clear(); f.index_calls.clear()
            before = f.read(storage, 0x680)
            f.run('sync_receiver', a['entry_address'])
            require(f.outcome == 'return' and f.read(p.CURSOR, 4) == p.u32(cursor + 32), 'Receiver failed')
            order = order_for(node)
            ordinal = order.index(sender - 1)
            changed = bytearray(before); changed[0x580 + ordinal * 32:0x580 + (ordinal + 1) * 32] = wire
            require(f.read(storage, 0x680) == bytes(changed), 'Receiver changed another member')
            require(not f.alloc_calls and not f.index_calls, 'Unexpected receive helper')
            runs.append({'sender': sender, 'recipient': node + 1, 'local_ordinal': ordinal,
                         'network_index': struct.unpack_from('<I', wire, 12)[0], 'instructions': len(f.trace)})
        bindings=dict(game_base=game,code_address=game+0x10030000,roster_address=roster,
                      storage_address=storage,reject_address=game+0x10034000)
        control=game+0x10038000;out=GateImage()
        require(native.getter_gate(GetterAddresses(**bindings),control,control+8,out)==0,'Getter gate failed')
        reference=native_getter_image.build(**{**bindings,'code_address':bindings['code_address']+32})
        data=bytes(out.data[:out.bytes]);require(data[32:32+reference['table_offset']]==reference['image'][:reference['table_offset']],'Gated getter differs')
        getter={**reference['candidate'],'entry_address':bindings['code_address']}
        f.map(getter['entry_address'],len(data));f.write(getter['entry_address'],data)
        f.map(control,16);f.write(control,p.u32(1));f.write(control+8,p.u64(f.stop))
        f.reject=getter['reject_address'];f.map(f.reject,1);f.write(f.reject,b'\xCC')
        for peer in range(8):
            f.seed();f.write(p.RSP,p.u64(f.stop));f.uc.reg_write(p.reg('rsp'),p.RSP);f.uc.reg_write(p.reg('edx'),entity(node,peer))
            f.outcome=None;f.trace.clear();f.writes.clear();f.alloc_calls.clear();f.index_calls.clear()
            before=f.read(storage,0x680);f.run('sync_network_index_getter',getter['entry_address'])
            expected_index=(3*peer+2)%8
            require(f.outcome=='return' and f.uc.reg_read(p.reg('rax'))==expected_index,'Getter returned another member index')
            require(f.uc.reg_read(p.reg('rsp'))==p.RSP+8 and f.uc.reg_read(p.reg('edx'))==entity(node,peer),'Getter argument/stack changed')
            require(f.read(storage,0x680)==before and not f.alloc_calls and not f.index_calls,'Getter changed storage/called helper')
            require(all(p.STACK<=address and address+size<=p.STACK+0x10000 for address,size,_ in f.writes),'Getter wrote outside stack')
            require(all(f.uc.reg_read(p.reg(name))==value for name,value in p.SEEDS.items()),'Getter clobbered preserved register')
            queries.append(dict(node=node+1,member=peer+1,entity=entity(node,peer),ordinal=order_for(node).index(peer),network_index=expected_index))
        path = output.parent / f'native-sync-{node + 1}-after.bin'
        artifacts[path.name] = export(path, m, f, node)
    result = {'native_receivers': runs, 'native_getter_queries':queries,'native_getter_gate_executed':True,'artifacts': artifacts, 'passed': True,
              'source_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
              'routed_sha256': hashlib.sha256(routed_path.read_bytes()).hexdigest(),
              'game_serializer_executed': False, 'game_entity_dispatch_executed': False,
              'real_admission_executed': False, 'game_access': False}
    output.write_text(json.dumps(result, indent=2) + '\n')
    return {'native_receivers': len(runs), 'native_getter_queries':len(queries),'game_access': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['produce', 'consume'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--routed', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--property-library',type=Path,required=True)
    args = parser.parse_args()
    if args.mode == 'consume' and (args.input is None or args.routed is None):
        parser.error('consume requires --input and --routed')
    print(json.dumps(produce(args.output,args.property_library) if args.mode == 'produce' else consume(args.input,args.routed,args.output,args.property_library)))
