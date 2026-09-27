"""Execute roster removals against independent partition/identity invariants.

All x64 runs use synthetic Unicorn RAM. Original comparisons use the actual
four-slot layout. The real saved map deletion and four-array mover execute;
neither helper is stubbed. No process or installed game is accessed.
"""
from __future__ import annotations
import hashlib, importlib.util, json, struct, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent / 'five_player_feasibility_20260927'
sys.path.insert(0, str(ROOT / '.native-test-deps'))
import capstone, unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

sha = lambda b: hashlib.sha256(b).hexdigest()
u32 = lambda n: struct.pack('<I', n)
u64 = lambda n: struct.pack('<Q', n)
reg = lambda n: getattr(xr, 'UC_X86_REG_' + n.upper())
GAME = 0x7FF600000000
S, B, MAP, ENTITY = 0x18200100400, 0x18200800100, 0x18200200100, 0x18200300000
STACK, RSP = 0x182F0000000, 0x182F0008008
WIRE, CURSOR = 0x18200400000, 0x18200500000
LAYOUT = [('pointer', 0, 0xE8, 8), ('primary', 0x40, 0x108, 0x70),
          ('aux', 0x3C0, 0x2C8, 0x38), ('property', 0x580, 0x3A8, 0x20)]
SEEDS = {n: 0xABCDEF0100000000 + i for i, n in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
KINDS = {'legacy': (0x60CEA0, 0x60CF4C), 'registered': (0x540A40, 0x540AE0)}
EVIDENCE = RESEARCH / 'roster_remove_native_evidence.json'
EVIDENCE_SHA = '67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af'
RUNS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load('remove_under_test', ROOT / 'Native/roster_remove.py')
insert = load('insert_dependency', ROOT / 'Native/roster_insert.py')
move = load('move_dependency', ROOT / 'Native/roster_move.py')
receiver = load('receiver_dependency', ROOT / 'Native/roster_receiver.py')
raw = EVIDENCE.read_bytes()
assert sha(raw) == EVIDENCE_SHA
ev = json.loads(raw)


def reconstruct(body, entry, end):
    chunks = []
    cursor = entry
    for row in body['instructions']:
        blob = bytes.fromhex(row['bytes'])
        assert int(row['rva'], 16) == cursor and sha(blob) == row['sha256']
        chunks.append(blob)
        cursor += len(blob)
    result = b''.join(chunks)
    assert cursor == end and sha(result) == body['sha256'] and result.hex() == body['bytes_hex']
    return result


SOURCES = {kind: reconstruct(ev['bodies'][hex(a)], a, z) for kind, (a, z) in KINDS.items()}
DELETE_BODY = reconstruct(ev['bodies']['0x172f8a0'], 0x172F8A0, 0x172F9A3)
assert sha(DELETE_BODY) == 'd58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f'
MOVE_BODY = move.load_source(RESEARCH / 'roster_move_native_evidence.json')
INSERT_SOURCES = insert.load_sources(RESEARCH / 'roster_insert_native_evidence.json')
MAP_INSERT_BODY = bytes.fromhex(json.loads((RESEARCH / 'roster_insert_native_evidence.json').read_bytes())['map_helper']['bytes_hex'])
assert sha(MAP_INSERT_BODY) == '57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375'


def params(kind, game=GAME):
    index = list(KINDS).index(kind)
    return dict(kind=kind, game_base=game, code_address=game + 0x100B0000 + index * 0x10000,
                reject_address=game + 0x100B8000 + index * 0x10000,
                roster_address=S, storage_address=B, move_code_address=game + 0x10040000)


def decode(blob, address):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    rows = list(decoder.disasm(blob, address))
    assert sum(i.size for i in rows) == len(blob)
    return rows


def changed_pages(before, changes):
    result = {p: bytearray(b) for p, b in before.items()}
    for address, blob in changes:
        for i, value in enumerate(blob):
            result[(address + i) & ~0xFFF][(address + i) & 0xFFF] = value
    return {p: bytes(b) for p, b in result.items()}


class Fixture:
    def __init__(self, kind, t=8, d=5, p=2, ordinal=0, *, original=False, game=GAME,
                 actual_s=S, roster_mapped=True, keys=None, multiplier=1, changes=None):
        self.kind, self.t, self.d, self.p, self.ordinal = kind, t, d, p, ordinal
        self.original, self.game, self.multiplier = original, game, multiplier
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages, self.calls, self.trace, self.writes, self.reads = set(), [], [], [], []
        arguments = params(kind, game)
        arguments.update(changes or {})
        self.artifact = native.build(SOURCES[kind], **arguments)
        self.start = game + KINDS[kind][0] if original else self.artifact['entry_address']
        self.reject = self.artifact['reject_address']
        self.move_reject, self.stop = game + 0x10048000, game + 0x100F0000
        blob = SOURCES[kind] if original else bytes.fromhex(self.artifact['code_hex'])
        self.map(self.start, len(blob)); self.write(self.start, blob)
        for a in (self.reject, self.move_reject, self.stop):
            self.map(a, 1); self.write(a, b'\xcc')
        self.map(game + 0x172F8A0, len(DELETE_BODY)); self.write(game + 0x172F8A0, DELETE_BODY)
        mover = move.build(MOVE_BODY, game_base=game, code_address=game + 0x10040000,
                           roster_address=S, storage_address=B, reject_address=self.move_reject)
        self.move_entry = game + 0x60C410 if original else mover['entry_address']
        mover_blob = MOVE_BODY if original else bytes.fromhex(mover['code_hex'])
        self.map(self.move_entry, len(mover_blob)); self.write(self.move_entry, mover_blob)
        self.map(game + 0x3326468, 8); self.write(game + 0x3326468, u64(actual_s))
        self.map(STACK, 0x10000); self.write(RSP, u64(self.stop))
        self.records, self.table = {}, [(0, 0xFFFFFFFF)] * 8
        self.keys = list(keys) if keys else [11 + 8 * i for i in range(8)]
        self.target = ENTITY + ordinal * 0x40
        if roster_mapped:
            for a, n in ((S - 0x80, 0x600), (B - 0x80, 0x780), (MAP - 0x80, 0x100), (ENTITY, 0x1000)):
                self.map(a, n)
            for off, value in ((0x80, t), (0x84, d), (0x88, p), (0x7C, 17),
                               (0xD8, 8), (0xDC, 0), (0xE0, multiplier)):
                self.write(S + off, u32(value))
            self.write(S + 0xD0, u64(MAP))
            for i in range(4 if original else 8):
                entity = ENTITY + i * 0x40
                self.write(entity + 8, u32(self.keys[i]))
                self.write(entity + 0x10, u32(0xCC000000 + i))
                self.write(entity + 0x14, bytes([int(i < p)]))
                if i < t:
                    for offset in range(8):
                        bucket = ((self.keys[i] * multiplier) + offset) & 7
                        if self.table[bucket][0] == 0:
                            self.table[bucket] = (self.keys[i], i)
                            break
                for group, (name, off, old, stride) in enumerate(LAYOUT):
                    value = u64(entity) if name == 'pointer' else bytes((i * 31 + j * 7 + group * 67) & 255 for j in range(stride))
                    self.records[name, i] = value
                    self.write(self.slot(name, i), value)
            for i, (key, index) in enumerate(self.table):
                self.write(MAP + i * 8, u32(key) + u32(index))
        self.seed()
        self.outcome = None
        self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, a, ad, n, v, data: self.reads.append((ad, n)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, ad, n, v, data: self.writes.append((ad, n)))

    def slot(self, name, ordinal):
        _, offset, old, stride = next(row for row in LAYOUT if row[0] == name)
        return (S + old if self.original else B + offset) + ordinal * stride

    def map(self, address, size):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000); self.uc.mem_write(page, b'\xa5' * 0x1000); self.pages.add(page)

    def write(self, address, blob): self.uc.mem_write(address, blob)
    def read(self, address, size): return bytes(self.uc.mem_read(address, size))
    def int32(self, address): return struct.unpack('<I', self.read(address, 4))[0]
    def snapshot(self): return {page: self.read(page, 0x1000) for page in self.pages if not STACK <= page < STACK + 0x10000}

    def seed(self):
        for name, value in SEEDS.items(): self.uc.reg_write(reg(name), value)
        for i in range(6, 16): self.uc.reg_write(reg('xmm' + str(i)), (0x0102030405060708 + i) * (1 + (1 << 64)))
        values = dict(rsp=RSP, rax=0xABABABABABABABAB, r8=0x8181818181818181, r9=0x9191919191919191,
                      rcx=0xDEAD1234 if self.kind == 'legacy' else self.target,
                      rdx=self.target if self.kind == 'legacy' else 0xBEEF5678)
        for name, value in values.items(): self.uc.reg_write(reg(name), value)
        self.arguments = {name: self.uc.reg_read(reg(name)) for name in ('rcx', 'rdx', 'r8', 'r9')}

    def reset_call(self):
        self.seed(); self.write(RSP, u64(self.stop))
        self.outcome = None
        self.calls, self.trace, self.writes, self.reads = [], [], [], []
        self.before = self.snapshot()

    def on_code(self, uc, address, size, data):
        self.trace.append(address)
        if address in (self.stop, self.reject, self.move_reject):
            self.outcome = 'return' if address == self.stop else 'reject'
            uc.emu_stop()
        if address in (self.move_entry, self.game + 0x172F8A0, self.game + 0x172F790):
            self.calls.append({'helper': 'move' if address == self.move_entry else 'delete' if address == self.game + 0x172F8A0 else 'insert',
                               'dst': uc.reg_read(reg('edx')), 'src': uc.reg_read(reg('r8d'))})

    def run(self, name, entry=None):
        self.uc.emu_start(self.start if entry is None else entry, 0, count=15000)
        assert self.outcome is not None, 'no bounded outcome'
        self.after = self.snapshot()
        RUNS.append(dict(name=name, kind=self.kind, original=self.original, t=self.t, d=self.d, p=self.p,
                         ordinal=self.ordinal, outcome=self.outcome, instructions=len(self.trace), helper_calls=self.calls,
                         return_rax=self.uc.reg_read(reg('rax'))))
        return self


class RemoveTests(unittest.TestCase):
    def abi(self, f, *, rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')), RSP if rejected else RSP + 8)
        for name, value in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(name)), value, name)
        for i in range(6, 16): self.assertEqual(f.uc.reg_read(reg('xmm' + str(i))), (0x0102030405060708 + i) * (1 + (1 << 64)))
        if rejected:
            for name, value in f.arguments.items(): self.assertEqual(f.uc.reg_read(reg(name)), value, name)

    def map_is_bijection(self, f, live):
        buckets = [struct.unpack('<II', f.read(MAP + i * 8, 8)) for i in range(8)]
        actual = [(key, ordinal) for key, ordinal in buckets if key != 0]
        self.assertEqual(len(actual), len(live))
        self.assertEqual(dict(actual), {key: ordinal for ordinal, key in enumerate(live)})
        for ordinal, key in enumerate(live):
            # A conventional lookup may stop at an empty bucket. Surviving
            # entries must remain reachable even after a collision-chain delete.
            reached = None
            for offset in range(8):
                bucket_key, value = buckets[((key * f.multiplier) + offset) & 7]
                if bucket_key == 0: break
                if bucket_key == key:
                    reached = value
                    break
            self.assertEqual(reached, ordinal)
        return buckets

    def success(self, f):
        self.assertEqual(f.outcome, 'return')
        self.abi(f)
        q, t, d, p = f.ordinal, f.t, f.d, f.p
        # Partition-level unordered erasure, independent of machine control
        # flow: replace the removed member with its partition's last member,
        # then close each following partition's first gap with its last member.
        partitions = [list(range(p)), list(range(p, d)), list(range(d, t))]
        group = 0 if q < p else 1 if q < d else 2
        within = partitions[group].index(q)
        partitions[group][within] = partitions[group][-1]
        partitions[group].pop()
        wanted = []
        for index, part in enumerate(partitions):
            if index > group and part:
                part = [part[-1]] + part[:-1]
            wanted.extend(part)
        pn, dn, tn = p - int(q < p), d - int(q < d), t - 1
        self.assertEqual([f.int32(S + x) for x in (0x80, 0x84, 0x88)], [tn, dn, pn])
        live_ids = [f.keys[i] for i in wanted]
        self.map_is_bijection(f, live_ids)
        for i, source_index in enumerate(wanted):
            for name, off, old, stride in LAYOUT:
                self.assertEqual(f.read(f.slot(name, i), stride), f.records[name, source_index], (name, i, source_index))
        # Unordered erasure must preserve every complete survivor exactly once.
        self.assertEqual(set(live_ids), set(f.keys[:t]) - {f.keys[q]})
        self.assertEqual(len(live_ids), len(set(live_ids)))
        # Byte-level boundary oracle: only the actual changed active slots,
        # counts, and eight map buckets may differ. Tail data stays untouched.
        changes = [(S + 0x80, u32(tn)), (S + 0x84, u32(dn)), (S + 0x88, u32(pn)),
                   (MAP, f.read(MAP, 64))]
        for i, source_index in enumerate(wanted):
            for name, off, old, stride in LAYOUT:
                changes.append((f.slot(name, i), f.records[name, source_index]))
        self.assertEqual(f.after, changed_pages(f.before, changes))
        self.assertEqual(sum(c['helper'] == 'delete' for c in f.calls), 1)
        if f.kind == 'legacy': self.assertEqual(f.uc.reg_read(reg('eax')), 0xCC000000 + q)
        return wanted

    def rejected(self, f, reason):
        self.assertEqual(f.outcome, 'reject')
        self.assertEqual(f.uc.reg_read(reg('r10d')), reason)
        self.assertEqual(f.before, f.after)
        self.assertEqual(f.calls, [])
        self.assertTrue(all(STACK <= address < STACK + 0x10000 and address + size <= STACK + 0x10000
                            for address, size in f.writes))
        self.abi(f, rejected=True)

    def test_01_fixed_source_and_emitted_branch_boundaries(self):
        self.assertEqual(native.load_sources(EVIDENCE), SOURCES)
        for kind, source in SOURCES.items():
            artifact = native.build(source, **params(kind))
            blob = bytes.fromhex(artifact['code_hex'])
            self.assertEqual(artifact['code_sha256'], sha(blob))
            instructions = decode(blob, artifact['entry_address'])
            boundaries = {i.address for i in instructions}
            calls = []
            for ins in instructions:
                if ins.group(capstone.CS_GRP_JUMP) or ins.group(capstone.CS_GRP_CALL):
                    self.assertEqual(ins.operands[0].type, capstone.x86_const.X86_OP_IMM)
                    target = ins.operands[0].imm
                    self.assertIn(target, boundaries | {artifact['reject_address'], GAME + 0x172F8A0, GAME + 0x10040000})
                    if ins.group(capstone.CS_GRP_CALL): calls.append(target)
            self.assertEqual(calls.count(GAME + 0x172F8A0), 1)
            self.assertIn(GAME + 0x10040000, calls)
            with self.assertRaises(ValueError): native.build(bytes([source[0] ^ 1]) + source[1:], **params(kind))

    def test_02_every_eight_slot_partition_and_removal_ordinal(self):
        for kind in KINDS:
            for t in range(1, 9):
                for d in range(t + 1):
                    for p in range(d + 1):
                        for ordinal in range(t):
                            with self.subTest(kind=kind, t=t, d=d, p=p, ordinal=ordinal):
                                self.success(Fixture(kind, t, d, p, ordinal).run('every_partition'))

    def test_03_original_four_slot_valid_scope(self):
        for kind in KINDS:
            for t in range(1, 5):
                for d in range(t + 1):
                    for p in range(d + 1):
                        for ordinal in range(t):
                            if d != t and ordinal < d: continue
                            with self.subTest(kind=kind, t=t, d=d, p=p, ordinal=ordinal):
                                original = Fixture(kind, t, d, p, ordinal, original=True).run('original_preserving_scope')
                                self.success(original)
                                if kind == 'registered':
                                    candidate = Fixture(kind, t, d, p, ordinal).run('registered_return_baseline_pair')
                                    self.success(candidate)
                                    self.assertEqual(original.uc.reg_read(reg('rax')), candidate.uc.reg_read(reg('rax')))

    def test_04_original_dense_pending_counterexample_and_repair(self):
        for kind in KINDS:
            original = Fixture(kind, 2, 1, 0, 0, original=True).run('original_dense_pending_counterexample')
            self.assertEqual(original.outcome, 'return')
            self.assertEqual(original.int32(S + 0x80), 1)
            self.assertEqual(original.read(original.slot('pointer', 0), 8), original.records['pointer', 0])
            active_id = original.int32(struct.unpack('<Q', original.read(original.slot('pointer', 0), 8))[0] + 8)
            self.assertEqual(active_id, original.keys[0])
            self.assertNotEqual(active_id, original.keys[1])
            candidate = Fixture(kind, 2, 1, 0, 0).run('candidate_dense_pending_repair')
            self.success(candidate)
            self.assertEqual(original.uc.reg_read(reg('rax')), candidate.uc.reg_read(reg('rax')))

    def test_05_mixed_hash_homes_and_second_aslr(self):
        for kind in KINDS:
            for ordinal in range(8):
                self.success(Fixture(kind, 8, 5, 3, ordinal, game=0x7FF800000000,
                                     keys=[2, 10, 17, 25, 8, 16, 31, 39], multiplier=3).run('mixed_hash_full_map'))

    def test_06_guard_rejects_before_nonstack_mutation(self):
        for kind in KINDS:
            for t, d, p, reason in [(0, 0, 0, 2), (9, 5, 2, 2), (0xFFFFFFFF, 0, 0, 2),
                                    (7, 8, 1, 3), (7, 5, 6, 3)]:
                self.rejected(Fixture(kind, t, d, p).run('invalid_counts'), reason)
            f = Fixture(kind, actual_s=0x40000000, roster_mapped=False).run('unmapped_wrong_binding')
            self.rejected(f, 1)
            self.assertTrue(all(address == GAME + 0x3326468 or STACK <= address < STACK + 0x10000 for address, size in f.reads))
            for capacity in (0, 4, 16):
                f = Fixture(kind); f.write(S + 0xD8, u32(capacity)); f.before = f.snapshot()
                self.rejected(f.run('wrong_map_capacity'), 4)
            for mutation, reason in [('missing', 5), ('sentinel', 5), ('ordinal', 6), ('prefix', 7), ('pointer', 8)]:
                f = Fixture(kind)
                if mutation == 'missing': f.write(f.target + 8, u32(999))
                elif mutation == 'sentinel': f.write(f.target + 8, u32(0))
                elif mutation == 'ordinal': f.write(MAP + 3 * 8 + 4, u32(8))
                elif mutation == 'prefix': f.write(f.target + 0x14, b'\0')
                elif mutation == 'pointer': f.write(f.slot('pointer', 0), u64(ENTITY + 7 * 0x40))
                f.before = f.snapshot()
                self.rejected(f.run('invalid_' + mutation), reason)
            f = Fixture(kind, 4, 3, 1)
            f.write(f.target + 8, u32(999)); f.before = f.snapshot()
            self.rejected(f.run('missing_id_with_empty_buckets'), 5)
            f = Fixture(kind, ordinal=3)
            f.write(f.target + 0x14, b'\1'); f.before = f.snapshot()
            self.rejected(f.run('invalid_nonprefix_dense_flag'), 7)
            f = Fixture(kind, ordinal=6)
            f.write(f.target + 0x14, b'\xff'); f.before = f.snapshot()
            self.success(f.run('pending_flag_not_used_as_prefix'))

    def test_07_address_and_bundle_region_validation(self):
        for kind in KINDS:
            for changes in [dict(storage_address=B + 1), dict(code_address=GAME + KINDS[kind][0]),
                            dict(reject_address=B + 0x500), dict(storage_address=S + 0x100),
                            dict(move_code_address=params(kind)['code_address']), dict(game_base=GAME + 1)]:
                values = params(kind); values.update(changes)
                with self.subTest(kind=kind, changes=changes), self.assertRaises(ValueError):
                    native.build(SOURCES[kind], **values)
        producer_source = insert.base_bundle.pair.producer.load_source(RESEARCH / 'roster_property_producer_native_evidence.json')
        receiver_source = receiver.load_source(RESEARCH / 'roster_property_receive_evidence.json')
        values = bundle_params()
        result = native.build_bundle(SOURCES, INSERT_SOURCES, MOVE_BODY, producer_source, receiver_source, **values)
        self.assertEqual(set(result['removes']), set(KINDS))
        for artifact in result['removes'].values():
            self.assertEqual(artifact['storage_address'], B)
            self.assertEqual(artifact['roster_address'], S)
            self.assertEqual(artifact['move_code_address'], values['move_code_address'])
        for field, key, address in [('remove_code_addresses', 'legacy', values['producer_code_address']),
                                    ('remove_reject_addresses', 'registered', values['receiver_reject_address']),
                                    ('remove_code_addresses', 'registered', values['remove_code_addresses']['legacy'])]:
            bad = json.loads(json.dumps(values)); bad[field][key] = address
            with self.assertRaises(ValueError):
                native.build_bundle(SOURCES, INSERT_SOURCES, MOVE_BODY, producer_source, receiver_source, **bad)

    def test_08_reject_rel32_endpoints(self):
        for kind in KINDS:
            values = params(kind); artifact = native.build(SOURCES[kind], **values)
            rows = decode(bytes.fromhex(artifact['code_hex']), artifact['code_address'])
            jumps = [i for i in rows if i.mnemonic == 'jmp' and i.operands[0].imm == artifact['reject_address']]
            self.assertTrue(jumps)
            low = max(i.address + i.size - (1 << 31) for i in jumps)
            high = min(i.address + i.size + (1 << 31) - 1 for i in jumps)
            for address in (low, high):
                self.rejected(Fixture(kind, 0, 0, 0, changes={'reject_address': address}).run('reject_rel32_boundary'), 2)
            for address in (low - 1, high + 1):
                values['reject_address'] = address
                with self.assertRaises(ValueError): native.build(SOURCES[kind], **values)

    def test_09_append_remove_reinsert_receiver_sequence(self):
        for kind in KINDS:
            f = Fixture(kind, 0, 0, 0)
            ik = 'append_' + kind
            ia = insert.build(INSERT_SOURCES[ik], kind=ik, game_base=GAME, code_address=GAME + 0x10060000,
                              roster_address=S, storage_address=B, move_code_address=GAME + 0x10040000,
                              reject_address=GAME + 0x10068000)
            f.map(ia['code_address'], ia['size_bytes']); f.write(ia['code_address'], bytes.fromhex(ia['code_hex']))
            f.map(ia['reject_address'], 1); f.write(ia['reject_address'], b'\xcc')
            f.map(GAME + 0x172F790, len(MAP_INSERT_BODY)); f.write(GAME + 0x172F790, MAP_INSERT_BODY)
            remove_reject = f.reject
            active = []
            def append(entity, key):
                f.write(entity + 8, u32(key)); f.write(entity + 0x14, b'\0')
                f.target = entity; f.reset_call(); f.reject = ia['reject_address']
                f.t, f.d, f.p = len(active), 0, 0
                f.run('sequence_append', ia['entry_address'])
                self.assertEqual(f.outcome, 'return'); self.abi(f)
                active.append(key)
                self.map_is_bijection(f, active)
                self.assertEqual([f.int32(S + x) for x in (0x80, 0x84, 0x88)], [len(active), 0, 0])
            for i in range(8): append(ENTITY + i * 0x40, 11 + 8 * i)
            for ordinal in (2, 0, 4):
                f.t, f.d, f.p, f.ordinal = len(active), 0, 0, ordinal
                f.target = struct.unpack('<Q', f.read(f.slot('pointer', ordinal), 8))[0]
                f.keys = active + [0] * (8 - len(active))
                f.records = {(name, i): f.read(f.slot(name, i), stride) for name, off, old, stride in LAYOUT for i in range(8)}
                f.reset_call(); f.reject = remove_reject
                # Legacy result belongs to the actual input record, not its
                # current slot; check separately from the fixed-case oracle.
                expected_return = f.int32(f.target + 0x10)
                f.run('sequence_remove')
                actual_kind = f.kind
                f.kind = 'registered'
                wanted = self.success(f)
                f.kind = actual_kind
                if kind == 'legacy': self.assertEqual(f.uc.reg_read(reg('eax')), expected_return)
                active = [active[i] for i in wanted]
            for i in range(3): append(ENTITY + 0x400 + i * 0x40, 91 + i * 8)
            # Receive properties for an entity moved by removal. Its new map
            # ordinal, not its old ordinal or network-index word, selects slot.
            received_ordinal = 2
            key = active[received_ordinal]
            self.assertEqual(key, 67)  # Moved from original ordinal 7 to 2.
            rs = receiver.load_source(RESEARCH / 'roster_property_receive_evidence.json')
            ra = receiver.build(rs, game_base=GAME, code_address=GAME + 0x10020000,
                                roster_address=S, property_address=B + 0x580, reject_address=GAME + 0x10024000)
            for address, size in ((ra['code_address'], ra['size_bytes']), (ra['reject_address'], 1),
                                  (GAME + 0x3483C20, 4), (WIRE, 0x100), (CURSOR, 4)):
                f.map(address, size)
            f.write(ra['code_address'], bytes.fromhex(ra['code_hex'])); f.write(ra['reject_address'], b'\xcc')
            f.write(GAME + 0x3483C20, u32(0xFFFFFFFF))
            wire = struct.pack('<8I', 0x12345678, 0xAABBCCDD, 0xFFFFFFFF, 7, 5, 6, 9, 10)
            f.write(WIRE + 12, wire); f.write(CURSOR, u32(12))
            f.reset_call(); f.reject = ra['reject_address']
            for name, value in dict(rcx=S, rdx=key, r8=WIRE, r9=CURSOR).items(): f.uc.reg_write(reg(name), value)
            f.run('sequence_receiver', ra['entry_address'])
            self.assertEqual(f.outcome, 'return'); self.abi(f)
            self.assertEqual(f.after, changed_pages(f.before, [(B + 0x580 + received_ordinal * 0x20, wire), (CURSOR, u32(44))]))
            self.assertEqual(f.calls, [])
            self.assertIn((S + 0xD0, 8), f.reads)
            self.assertTrue(any(MAP <= address < MAP + 64 for address, size in f.reads))
            self.map_is_bijection(f, active)


def bundle_params():
    return dict(game_base=GAME, roster_address=S, storage_address=B,
                move_code_address=GAME + 0x10040000, move_reject_address=GAME + 0x10048000,
                producer_code_address=GAME + 0x10000000, producer_reject_address=GAME + 0x10004000,
                receiver_code_address=GAME + 0x10020000, receiver_reject_address=GAME + 0x10024000,
                insert_code_addresses={k: GAME + 0x10060000 + i * 0x10000 for i, k in enumerate(insert.SPECS)},
                insert_reject_addresses={k: GAME + 0x10068000 + i * 0x10000 for i, k in enumerate(insert.SPECS)},
                remove_code_addresses={k: params(k)['code_address'] for k in KINDS},
                remove_reject_addresses={k: params(k)['reject_address'] for k in KINDS})


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RemoveTests))
    source_names = ['roster_remove', 'roster_insert', 'roster_bundle', 'roster_property_pair', 'roster_producer', 'roster_receiver', 'roster_move']
    evidence_names = ['roster_remove_native_evidence.json', 'roster_insert_native_evidence.json',
                      'roster_move_native_evidence.json', 'roster_property_producer_native_evidence.json', 'roster_property_receive_evidence.json']
    report = dict(status='passed' if result.wasSuccessful() else 'failed', test_methods_run=result.testsRun,
                  failure_count=len(result.failures), error_count=len(result.errors),
                  failures=[{'test': str(t), 'traceback': s} for t, s in result.failures],
                  errors=[{'test': str(t), 'traceback': s} for t, s in result.errors],
                  source_sha256={f'Native/{name}.py': sha((ROOT / f'Native/{name}.py').read_bytes()) for name in source_names},
                  test_sha256=sha(Path(__file__).read_bytes()), test_dependency_sha256={},
                  evidence_sha256={str((RESEARCH / name).relative_to(ROOT.parent)): sha((RESEARCH / name).read_bytes()) for name in evidence_names},
                  python_version=sys.version, unicorn_version=unicorn.__version__, capstone_version=capstone.__version__,
                  fixture_synthetic=True, game_process_accessed=False, host_native_code_executed=False, installable=False,
                  emulator_runs=RUNS,
                  execution_counts={'candidate': sum(not run['original'] for run in RUNS),
                                    'original_baseline': sum(run['original'] and run['name'] != 'original_dense_pending_counterexample' for run in RUNS),
                                    'original_expected_counterexample': sum(run['name'] == 'original_dense_pending_counterexample' for run in RUNS),
                                    'total': len(RUNS)},
                  original_comparison_scope='Original actual four-slot arrays, D==T or removal ordinal>=D; separate dense/pending counterexample is expected failure of original identity preservation',
                  limits=['Synthetic valid unique-ID entity/map/partition state; actual caller lifetime and concurrency remain unproven',
                          'All active survivor IDs, complete four-array records, partition counts, collision lookup, ABI and nonstack boundaries checked',
                          'Removal intentionally fills dense/pending boundary gap beyond original behavior; caller ownership of pending records still needs integration review',
                          'Map and pointer validity outside explicit entry guards is a precondition',
                          'Receiver sequence uses synthetic incoming bytes; no serializer, network transport, Windows unwind, installation or multiplayer execution'])
    out = ROOT / 'verification/native_roster_remove_tests.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], methods=result.testsRun, executions=len(RUNS), failures=len(result.failures), errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
