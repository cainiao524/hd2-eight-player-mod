"""Classify saved x64 records in synthetic Unicorn RAM with explicit temp contracts.

The classifier bodies execute as original or emitted bytes. The three temporary
resource helpers are CONTRACT STUBS, not captured engine execution. They check
call order, sizes, alignment, shadow space and temporary-buffer lifetime, while
clobbering volatile registers. No process or installed game is accessed.
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

sha = lambda blob: hashlib.sha256(blob).hexdigest()
u32 = lambda value: struct.pack('<I', value)
u64 = lambda value: struct.pack('<Q', value)
reg = lambda name: getattr(xr, 'UC_X86_REG_' + name.upper())
GAME = 0x7FF600000000
S, B, MAP, ENTITY = 0x18200100400, 0x18200800100, 0x18200200100, 0x18200300000
STACK, RSP = 0x182F0000000, 0x182F0008008
WIRE, CURSOR, TEMP = 0x18200400000, 0x18200500000, 0x18200600000
LAYOUT = [('pointer', 0, 0xE8, 8), ('primary', 0x40, 0x108, 0x70),
          ('aux', 0x3C0, 0x2C8, 0x38), ('property', 0x580, 0x3A8, 0x20)]
SEEDS = {name: 0xABCDEF0100000000 + i for i, name in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
HELPERS = {0x173B6F0: 'create', 0x173B8D0: 'allocate', 0x173BC20: 'release'}
KINDS = {'enter': (0x60CF50, 0x60D2F6), 'leave': (0x60D300, 0x60D760)}
EVIDENCE = RESEARCH / 'roster_classify_native_evidence.json'
EVIDENCE_SHA = 'f20165dad6823edc40fbcdf0434123139f1c80d9222a2b20d3f4c067768e9e33'
RUNS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load('classify_under_test', ROOT / 'Native/roster_classify.py')
remove = load('classify_remove_dependency', ROOT / 'Native/roster_remove.py')
insert = load('classify_insert_dependency', ROOT / 'Native/roster_insert.py')
move = load('classify_move_dependency', ROOT / 'Native/roster_move.py')
receiver = load('classify_receiver_dependency', ROOT / 'Native/roster_receiver.py')
raw = EVIDENCE.read_bytes()
assert sha(raw) == EVIDENCE_SHA
ev = json.loads(raw)


def reconstruct(body, entry, end):
    cursor, chunks = entry, []
    for row in body['instructions']:
        blob = bytes.fromhex(row['bytes'])
        assert int(row['rva'], 16) == cursor and sha(blob) == row['sha256']
        cursor += len(blob); chunks.append(blob)
    result = b''.join(chunks)
    assert cursor == end and sha(result) == body['sha256'] and result.hex() == body['bytes_hex']
    return result


SOURCES = {kind: reconstruct(ev['bodies'][hex(entry)], entry, end) for kind, (entry, end) in KINDS.items()}


def params(kind, game=GAME):
    index = list(KINDS).index(kind)
    return dict(kind=kind, game_base=game, code_address=game + 0x100D0000 + index * 0x10000,
                reject_address=game + 0x100D8000 + index * 0x10000,
                roster_address=S, storage_address=B)


def decode(blob, base):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
    rows = list(md.disasm(blob, base))
    assert sum(row.size for row in rows) == len(blob)
    return rows


def changed_pages(before, changes):
    result = {page: bytearray(blob) for page, blob in before.items()}
    for address, blob in changes:
        for i, value in enumerate(blob): result[(address + i) & ~0xFFF][(address + i) & 0xFFF] = value
    return {page: bytes(blob) for page, blob in result.items()}


class Fixture:
    def __init__(self, kind, t=8, d=7, p=3, ordinal=None, *, original=False, game=GAME,
                 keys=None, multiplier=1, actual_s=S, roster_mapped=True, changes=None):
        self.kind, self.t, self.d, self.p = kind, t, d, p
        self.ordinal = (6 if kind == 'enter' else 0) if ordinal is None else ordinal
        self.original, self.game, self.multiplier = original, game, multiplier
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages = set()
        self.calls, self.trace, self.reads, self.writes, self.allocations = [], [], [], [], []
        self.phase, self.box, self.context, self.group_index = 'create', None, None, 0
        self.arena, self.arena_block, self.arena_used = 0x18200700100, 0x18200701000, 0x40
        self.stop = game + 0x10100000
        self.map(self.stop, 1); self.write(self.stop, b'\xcc')
        self.select(kind, changes)
        for rva in HELPERS:
            self.map(game + rva, 1); self.write(game + rva, b'\xc3')
        self.map(game + 0x3326468, 8); self.write(game + 0x3326468, u64(actual_s))
        self.map(game + 0x3483C20, 4); self.write(game + 0x3483C20, u32(0xFFFFFFFF))
        self.map(STACK, 0x10000); self.write(RSP, u64(self.stop))
        self.map(TEMP, 0x3000)
        self.keys = list(keys) if keys else [11 + 8 * i for i in range(8)]
        self.target = ENTITY + self.ordinal * 0x40
        self.table, self.records = [(0, 0xFFFFFFFF)] * 8, {}
        if roster_mapped:
            for address, size in ((S - 0x80, 0x600), (B - 0x80, 0x780), (MAP - 0x80, 0x100), (ENTITY, 0x1000)):
                self.map(address, size)
            for off, value in ((0x80, t), (0x84, d), (0x88, p), (0x7C, 17), (0xD8, 8), (0xDC, 0), (0xE0, multiplier)):
                self.write(S + off, u32(value))
            self.write(S + 0xD0, u64(MAP))
            for i in range(4 if original else 8):
                entity = ENTITY + i * 0x40
                self.write(entity + 8, u32(self.keys[i]))
                self.write(entity + 0x14, bytes([int(i < p or i == self.ordinal)]))
                if i < t:
                    bucket = next(((self.keys[i] * multiplier) + j) & 7 for j in range(8)
                                  if self.table[((self.keys[i] * multiplier) + j) & 7][0] == 0)
                    self.table[bucket] = (self.keys[i], i)
                for group, (name, off, old, stride) in enumerate(LAYOUT):
                    blob = u64(entity) if name == 'pointer' else bytes((i * 31 + j * 7 + group * 67) & 255 for j in range(stride))
                    self.records[name, i] = blob; self.write(self.slot(name, i), blob)
            for bucket, (key, ordinal) in enumerate(self.table): self.write(MAP + bucket * 8, u32(key) + u32(ordinal))
        self.seed(); self.outcome = None; self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ, self.on_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.on_write)

    def select(self, kind, changes=None):
        self.kind = kind
        arguments = params(kind, self.game); arguments.update(changes or {})
        self.artifact = native.build(SOURCES[kind], **arguments)
        self.start = self.game + KINDS[kind][0] if self.original else self.artifact['entry_address']
        self.reject = self.artifact['reject_address']
        blob = SOURCES[kind] if self.original else bytes.fromhex(self.artifact['code_hex'])
        self.map(self.start, len(blob)); self.write(self.start, blob)
        self.map(self.reject, 1); self.write(self.reject, b'\xcc')

    def slot(self, name, ordinal):
        _, off, old, stride = next(row for row in LAYOUT if row[0] == name)
        return (S + old if self.original else B + off) + ordinal * stride

    def map(self, address, size):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000); self.uc.mem_write(page, b'\xa5' * 0x1000); self.pages.add(page)

    def write(self, address, blob): self.uc.mem_write(address, blob)
    def read(self, address, size): return bytes(self.uc.mem_read(address, size))
    def int32(self, address): return struct.unpack('<I', self.read(address, 4))[0]
    def int64(self, address): return struct.unpack('<Q', self.read(address, 8))[0]
    def snapshot(self): return {page: self.read(page, 0x1000) for page in self.pages if not STACK <= page < STACK + 0x10000}

    def seed(self):
        for name, value in SEEDS.items(): self.uc.reg_write(reg(name), value)
        for i in range(6, 16): self.uc.reg_write(reg('xmm' + str(i)), (0x0102030405060708 + i) * (1 + (1 << 64)))
        for name, value in dict(rsp=RSP, rax=0xABABABABABABABAB, rcx=0xDEAD0000, rdx=self.target,
                               r8=0x8181818181818181, r9=0x9191919191919191).items(): self.uc.reg_write(reg(name), value)
        self.arguments = {name: self.uc.reg_read(reg(name)) for name in ('rcx', 'rdx', 'r8', 'r9')}

    def reset_call(self):
        self.seed(); self.write(RSP, u64(self.stop)); self.outcome = None
        self.calls, self.trace, self.reads, self.writes, self.allocations = [], [], [], [], []
        self.phase, self.box, self.context, self.group_index = 'create', None, None, 0
        self.before = self.snapshot()

    def capture_records(self):
        self.keys = [self.int32(self.int64(self.slot('pointer', i)) + 8) for i in range(8)]
        self.records = {(name, i): self.read(self.slot(name, i), stride)
                        for name, off, old, stride in LAYOUT for i in range(8)}
        self.table = [struct.unpack('<II', self.read(MAP + bucket * 8, 8)) for bucket in range(8)]

    def check_temporary_access(self, address, size):
        if not (TEMP <= address < TEMP + 0x3000): return
        matches = [item for item in self.allocations if item['address'] <= address and address + size <= item['address'] + item['size']]
        assert len(matches) == 1 and matches[0]['live'], ('invalid temporary access', hex(address), size, self.allocations)

    def on_read(self, uc, access, address, size, value, data):
        self.reads.append((address, size)); self.check_temporary_access(address, size)

    def on_write(self, uc, access, address, size, value, data):
        self.writes.append((address, size)); self.check_temporary_access(address, size)

    def on_code(self, uc, address, size, data):
        self.trace.append(address)
        if address in (self.stop, self.reject):
            self.outcome = 'return' if address == self.stop else 'reject'; uc.emu_stop(); return
        role = HELPERS.get(address - self.game)
        if role is None: return
        rsp = uc.reg_read(reg('rsp')); rcx = uc.reg_read(reg('rcx'))
        assert rsp % 16 == 8, 'temporary-helper Windows call alignment'
        assert STACK <= rsp and rsp + 40 <= STACK + 0x10000
        return_address = self.int64(rsp)
        event = dict(role=role, rsp_mod16=rsp % 16, return_address=return_address, rcx=rcx)
        result = 0
        if role == 'create':
            assert self.phase == 'create'
            assert STACK <= rcx < STACK + 0x10000 and not (rsp <= rcx < rsp + 40)
            self.box = rcx; self.context = self.arena
            self.scope_snapshot = (self.arena, self.arena_block, self.arena_used)
            self.write(self.box, struct.pack('<3Q', *self.scope_snapshot)); self.phase = 'allocate'
            event['snapshot'] = list(self.scope_snapshot)
        elif role == 'allocate':
            assert self.phase == 'allocate' and rcx == self.context
            size_arg, alignment = uc.reg_read(reg('edx')), uc.reg_read(reg('r8d'))
            groups = [('aux', 0x38), ('property', 0x20)] if self.kind == 'enter' else [('primary', 0x70), ('aux', 0x38), ('property', 0x20)]
            group, expected_size = groups[self.group_index]
            assert size_arg == expected_size and alignment == 4
            result = TEMP + self.group_index * 0x1000
            self.allocations.append(dict(group=group, address=result, size=size_arg, live=True))
            self.arena_used = ((self.arena_used + alignment - 1) & -alignment) + size_arg
            event.update(size=size_arg, alignment=alignment, buffer=result)
            self.phase = 'release_first'
        else:
            assert rcx == self.box
            assert struct.unpack('<3Q', self.read(self.box, 24)) == self.scope_snapshot
            if self.phase == 'release_first':
                self.allocations[-1]['live'] = False
                self.arena_block, self.arena_used = self.scope_snapshot[1:]
                self.phase = 'release_second'; event['release_index'] = 1
            else:
                assert self.phase == 'release_second' and (self.arena_block, self.arena_used) == self.scope_snapshot[1:]
                self.phase = 'create'; self.group_index += 1; event['release_index'] = 2
            event['restored_snapshot'] = list(self.scope_snapshot)
        self.calls.append(event)
        # Contract-only helpers may overwrite their four home slots and every
        # volatile register. The real one-byte RET returns using actual RSP.
        self.write(rsp + 8, bytes([0xC0 + len(self.calls)]) * 32)
        for i, name in enumerate(('rax', 'rcx', 'rdx', 'r8', 'r9', 'r10', 'r11')):
            uc.reg_write(reg(name), 0xCDCD000000000000 + i)
        for i in range(6): uc.reg_write(reg('xmm' + str(i)), (0xAABBCCDDEEFF0000 + i) * (1 + (1 << 64)))
        uc.reg_write(reg('rax'), result)

    def run(self, name, entry=None):
        self.uc.emu_start(self.start if entry is None else entry, 0, count=20000)
        assert self.outcome is not None, 'no bounded outcome'
        self.after = self.snapshot()
        RUNS.append(dict(name=name, kind=self.kind, original=self.original, t=self.t, d=self.d, p=self.p,
                         ordinal=self.ordinal, outcome=self.outcome, instructions=len(self.trace),
                         contract_stub_calls=self.calls, return_rax=self.uc.reg_read(reg('rax'))))
        return self


class ClassifyTests(unittest.TestCase):
    def abi(self, f, rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')), RSP if rejected else RSP + 8)
        for name, value in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(name)), value, name)
        for i in range(6, 16): self.assertEqual(f.uc.reg_read(reg('xmm' + str(i))), (0x0102030405060708 + i) * (1 + (1 << 64)))
        if rejected:
            for name, value in f.arguments.items(): self.assertEqual(f.uc.reg_read(reg(name)), value, name)

    def map_is_bijection(self, f, keys):
        buckets = [struct.unpack('<II', f.read(MAP + i * 8, 8)) for i in range(8)]
        active = [(key, ordinal) for key, ordinal in buckets if key != 0]
        self.assertEqual(len(active), len(keys))
        self.assertEqual(dict(active), {key: i for i, key in enumerate(keys)})
        for wanted, key in enumerate(keys):
            reached = None
            for offset in range(8):
                candidate, ordinal = buckets[(key * f.multiplier + offset) & 7]
                if candidate == 0: break
                if candidate == key: reached = ordinal; break
            self.assertEqual(reached, wanted)

    def success(self, f):
        self.assertEqual(f.outcome, 'return'); self.abi(f)
        n = f.ordinal; boundary = f.p if f.kind == 'enter' else f.p - 1
        pn = f.p + (1 if f.kind == 'enter' else -1)
        expected_records = dict(f.records)
        changed = [(S + 0x88, u32(pn))]
        if n != boundary:
            for name, off, old, stride in LAYOUT:
                if name == 'primary' and f.kind == 'enter': continue
                expected_records[name, n], expected_records[name, boundary] = f.records[name, boundary], f.records[name, n]
        if f.kind == 'enter': expected_records['primary', boundary] = bytes(0x70)
        for (name, ordinal), value in expected_records.items(): changed.append((f.slot(name, ordinal), value))
        keys = f.keys[:f.t]
        if n != boundary: keys[n], keys[boundary] = keys[boundary], keys[n]
        table = [(key, keys.index(key)) if key != 0 else (key, ordinal) for key, ordinal in f.table]
        for bucket, (key, ordinal) in enumerate(table): changed.append((MAP + bucket * 8, u32(key) + u32(ordinal)))
        groups = [] if n == boundary else [('aux', 0x38), ('property', 0x20)] if f.kind == 'enter' else [('primary', 0x70), ('aux', 0x38), ('property', 0x20)]
        self.assertEqual([event['role'] for event in f.calls], ['create', 'allocate', 'release', 'release'] * len(groups))
        self.assertEqual([(event['size'], event['alignment']) for event in f.calls if event['role'] == 'allocate'], [(size, 4) for group, size in groups])
        self.assertEqual([event['release_index'] for event in f.calls if event['role'] == 'release'], [1, 2] * len(groups))
        self.assertEqual(f.phase, 'create'); self.assertEqual(f.group_index, len(groups))
        self.assertEqual((f.arena_block, f.arena_used), (0x18200701000, 0x40))
        self.assertTrue(all(not block['live'] for block in f.allocations))
        for index, (group, size) in enumerate(groups): changed.append((TEMP + index * 0x1000, f.records[group, boundary]))
        self.assertEqual(f.after, changed_pages(f.before, changed))
        self.assertEqual([f.int32(S + off) for off in (0x80, 0x84, 0x88)], [f.t, f.d, pn])
        self.map_is_bijection(f, keys)
        self.assertEqual(set(keys), set(f.keys[:f.t])); self.assertEqual(len(keys), len(set(keys)))
        return keys

    def rejected(self, f, reason):
        self.assertEqual(f.outcome, 'reject'); self.assertEqual(f.uc.reg_read(reg('r10d')), reason)
        self.assertEqual(f.before, f.after); self.assertEqual(f.calls, [])
        self.assertTrue(all(STACK <= address and address + size <= STACK + 0x10000 for address, size in f.writes))
        self.abi(f, True)

    def test_01_fixed_body_and_control_flow_boundaries(self):
        self.assertEqual(native.load_sources(EVIDENCE), SOURCES)
        for kind, source in SOURCES.items():
            artifact = native.build(source, **params(kind)); blob = bytes.fromhex(artifact['code_hex'])
            self.assertEqual(sha(blob), artifact['code_sha256'])
            rows = decode(blob, artifact['entry_address']); boundaries = {row.address for row in rows}
            calls = []
            for row in rows:
                if row.group(capstone.CS_GRP_JUMP) or row.group(capstone.CS_GRP_CALL):
                    self.assertEqual(row.operands[0].type, capstone.x86_const.X86_OP_IMM)
                    target = row.operands[0].imm
                    self.assertIn(target, boundaries | {artifact['reject_address']} | {GAME + rva for rva in HELPERS})
                    if row.group(capstone.CS_GRP_CALL): calls.append(target - GAME)
            self.assertEqual(calls, [0x173B6F0, 0x173B8D0, 0x173BC20, 0x173BC20] * (2 if kind == 'enter' else 3))
            with self.assertRaises(ValueError): native.build(bytes([source[0] ^ 1]) + source[1:], **params(kind))

    def test_02_all_eight_slot_partitions_and_valid_ordinals(self):
        for kind in KINDS:
            for t in range(1, 9):
                for d in range(t + 1):
                    for p in range(d + 1):
                        for ordinal in range(p, d) if kind == 'enter' else range(p):
                            with self.subTest(kind=kind, t=t, d=d, p=p, ordinal=ordinal):
                                self.success(Fixture(kind, t, d, p, ordinal).run('every_partition'))

    def test_03_original_four_slot_paired_baseline(self):
        for kind in KINDS:
            for t in range(1, 5):
                for d in range(t + 1):
                    for p in range(d + 1):
                        for ordinal in range(p, d) if kind == 'enter' else range(p):
                            with self.subTest(kind=kind, t=t, d=d, p=p, ordinal=ordinal):
                                original = Fixture(kind, t, d, p, ordinal, original=True).run('original_baseline')
                                candidate = Fixture(kind, t, d, p, ordinal).run('candidate_baseline_pair')
                                self.success(original); self.success(candidate)
                                for name, off, old, stride in LAYOUT:
                                    self.assertEqual(original.read(original.slot(name, 0), 4 * stride), candidate.read(candidate.slot(name, 0), 4 * stride))
                                self.assertEqual(original.read(MAP, 64), candidate.read(MAP, 64))
                                self.assertEqual(original.uc.reg_read(reg('rax')), candidate.uc.reg_read(reg('rax')))

    def test_04_mixed_hash_aslr_and_asymmetric_primary(self):
        for kind in KINDS:
            for ordinal in (range(3, 8) if kind == 'enter' else range(3)):
                f = Fixture(kind, 8, 8, 3, ordinal, game=0x7FF800000000,
                            keys=[2, 10, 17, 25, 8, 16, 31, 39], multiplier=3).run('mixed_hash_second_aslr')
                self.success(f)
                if kind == 'enter' and ordinal != 3:
                    self.assertEqual(f.read(f.slot('primary', ordinal), 0x70), f.records['primary', ordinal])
                    self.assertEqual(f.read(f.slot('primary', 3), 0x70), bytes(0x70))
                    self.assertNotEqual(f.records['primary', ordinal], f.records['primary', 3])

    def test_05_preflight_guards_before_nonstack_mutation(self):
        for kind in KINDS:
            for t, d, p, reason in [(0, 0, 0, 2), (9, 7, 3, 2), (0xFFFFFFFF, 0, 0, 2), (7, 8, 3, 3), (7, 5, 6, 3)]:
                self.rejected(Fixture(kind, t, d, p, 0).run('invalid_counts'), reason)
            f = Fixture(kind, actual_s=0x40000000, roster_mapped=False).run('unmapped_wrong_binding')
            self.rejected(f, 1)
            self.assertTrue(all(address == GAME + 0x3326468 or STACK <= address < STACK + 0x10000 for address, size in f.reads))
            for capacity in (0, 4, 16):
                f = Fixture(kind); f.write(S + 0xD8, u32(capacity)); f.before = f.snapshot()
                self.rejected(f.run('wrong_map_capacity'), 4)
            for mutation, reason in [('missing', 5), ('sentinel', 5), ('global_invalid', 5),
                                     ('ordinal', 6), ('pointer', 8), ('flag', 9)]:
                f = Fixture(kind)
                if mutation == 'missing': f.write(f.target + 8, u32(999))
                elif mutation == 'sentinel': f.write(f.target + 8, u32(0))
                elif mutation == 'global_invalid': f.write(GAME + 0x3483C20, u32(f.keys[f.ordinal]))
                elif mutation == 'ordinal':
                    bucket = next(i for i, pair in enumerate(f.table) if pair[0] == f.keys[f.ordinal])
                    f.write(MAP + bucket * 8 + 4, u32(f.d))
                elif mutation == 'pointer': f.write(f.slot('pointer', f.ordinal), u64(ENTITY + 7 * 0x40))
                elif mutation == 'flag': f.write(f.target + 0x14, b'\0')
                f.before = f.snapshot(); self.rejected(f.run('invalid_' + mutation), reason)
            f = Fixture(kind, 4, 4, 2, 2 if kind == 'enter' else 0)
            f.write(f.target + 8, u32(999)); f.before = f.snapshot()
            self.rejected(f.run('missing_id_with_empty_bucket'), 5)
            f = Fixture(kind, ordinal=0 if kind == 'enter' else 4)
            self.rejected(f.run('wrong_direction'), 7)
            f = Fixture(kind, 8, 7, 7 if kind == 'enter' else 0, 6 if kind == 'enter' else 0)
            self.rejected(f.run('prefix_direction_boundary'), 7)

    def test_06_addresses_bundle_and_reject_rel32(self):
        for kind in KINDS:
            for changes in [dict(storage_address=B + 1), dict(storage_address=S + 0x100),
                            dict(code_address=GAME + KINDS[kind][0]), dict(reject_address=B + 0x500), dict(game_base=GAME + 1)]:
                values = params(kind); values.update(changes)
                with self.subTest(kind=kind, changes=changes), self.assertRaises(ValueError): native.build(SOURCES[kind], **values)
            artifact = native.build(SOURCES[kind], **params(kind))
            jumps = [row for row in decode(bytes.fromhex(artifact['code_hex']), artifact['code_address'])
                     if row.mnemonic == 'jmp' and row.operands[0].imm == artifact['reject_address']]
            self.assertTrue(jumps)
            low = max(row.address + row.size - (1 << 31) for row in jumps)
            high = min(row.address + row.size + (1 << 31) - 1 for row in jumps)
            for address in (low, high):
                self.rejected(Fixture(kind, 0, 0, 0, 0, changes={'reject_address': address}).run('reject_rel32_boundary'), 2)
            for address in (low - 1, high + 1):
                values = params(kind); values['reject_address'] = address
                with self.assertRaises(ValueError): native.build(SOURCES[kind], **values)
        values = bundle_params()
        rs = remove.load_sources(RESEARCH / 'roster_remove_native_evidence.json')
        ins = insert.load_sources(RESEARCH / 'roster_insert_native_evidence.json')
        ms = move.load_source(RESEARCH / 'roster_move_native_evidence.json')
        ps = insert.base_bundle.pair.producer.load_source(RESEARCH / 'roster_property_producer_native_evidence.json')
        recv = receiver.load_source(RESEARCH / 'roster_property_receive_evidence.json')
        artifact = native.build_bundle(SOURCES, rs, ins, ms, ps, recv, **values)
        self.assertEqual(set(artifact['classifiers']), set(KINDS))
        for item in artifact['classifiers'].values():
            self.assertEqual(item['roster_address'], S); self.assertEqual(item['storage_address'], B)
        for field, key, address in [('classify_code_addresses', 'enter', values['remove_code_addresses']['legacy']),
                                    ('classify_reject_addresses', 'leave', values['receiver_reject_address']),
                                    ('classify_code_addresses', 'leave', values['classify_code_addresses']['enter'])]:
            bad = json.loads(json.dumps(values)); bad[field][key] = address
            with self.assertRaises(ValueError): native.build_bundle(SOURCES, rs, ins, ms, ps, recv, **bad)

    def test_07_continuous_classify_and_receive_relocated_identity(self):
        f = Fixture('enter', 8, 8, 2, 7)
        for kind, key in [('enter', 67), ('enter', 59), ('leave', 67), ('leave', 11)]:
            f.select(kind); f.capture_records()
            f.t, f.d, f.p = [f.int32(S + off) for off in (0x80, 0x84, 0x88)]
            f.ordinal = f.keys.index(key); f.target = f.int64(f.slot('pointer', f.ordinal))
            # Explicit caller-side flag staging is outside classifier execution.
            # These writes model the known requirement, not an integrated caller.
            f.write(f.target + 0x14, b'\1'); f.reset_call()
            self.success(f.run('sequence_' + kind))
            if kind == 'leave': f.write(f.target + 0x14, b'\0')
        f.capture_records()
        self.assertEqual(f.keys[3], 67); self.assertEqual(f.int32(S + 0x88), 2)
        rs = receiver.load_source(RESEARCH / 'roster_property_receive_evidence.json')
        artifact = receiver.build(rs, game_base=GAME, code_address=GAME + 0x10020000,
                                  roster_address=S, property_address=B + 0x580, reject_address=GAME + 0x10024000)
        for address, size in ((artifact['code_address'], artifact['size_bytes']), (artifact['reject_address'], 1), (WIRE, 0x100), (CURSOR, 4)):
            f.map(address, size)
        f.write(artifact['code_address'], bytes.fromhex(artifact['code_hex'])); f.write(artifact['reject_address'], b'\xcc')
        wire = struct.pack('<8I', 0x12345678, 0xAABBCCDD, 0xFFFFFFFF, 7, 5, 6, 9, 10)
        f.write(WIRE + 12, wire); f.write(CURSOR, u32(12)); f.reset_call(); f.reject = artifact['reject_address']
        for name, value in dict(rcx=S, rdx=67, r8=WIRE, r9=CURSOR).items(): f.uc.reg_write(reg(name), value)
        f.run('sequence_receiver', artifact['entry_address'])
        self.assertEqual(f.outcome, 'return'); self.abi(f)
        self.assertEqual(f.after, changed_pages(f.before, [(B + 0x580 + 3 * 0x20, wire), (CURSOR, u32(44))]))
        self.assertEqual(f.calls, []); self.assertIn((S + 0xD0, 8), f.reads)
        self.assertTrue(any(MAP <= address < MAP + 64 for address, size in f.reads))
        self.map_is_bijection(f, f.keys)


def bundle_params():
    return dict(game_base=GAME, roster_address=S, storage_address=B,
                move_code_address=GAME + 0x10040000, move_reject_address=GAME + 0x10048000,
                producer_code_address=GAME + 0x10000000, producer_reject_address=GAME + 0x10004000,
                receiver_code_address=GAME + 0x10020000, receiver_reject_address=GAME + 0x10024000,
                insert_code_addresses={key: GAME + 0x10060000 + i * 0x10000 for i, key in enumerate(insert.SPECS)},
                insert_reject_addresses={key: GAME + 0x10068000 + i * 0x10000 for i, key in enumerate(insert.SPECS)},
                remove_code_addresses={'legacy': GAME + 0x100B0000, 'registered': GAME + 0x100C0000},
                remove_reject_addresses={'legacy': GAME + 0x100B8000, 'registered': GAME + 0x100C8000},
                classify_code_addresses={key: params(key)['code_address'] for key in KINDS},
                classify_reject_addresses={key: params(key)['reject_address'] for key in KINDS})


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ClassifyTests))
    sources = ['roster_classify', 'roster_remove', 'roster_insert', 'roster_bundle', 'roster_property_pair', 'roster_producer', 'roster_receiver', 'roster_move']
    evidences = ['roster_classify_native_evidence.json', 'roster_remove_native_evidence.json', 'roster_insert_native_evidence.json',
                 'roster_move_native_evidence.json', 'roster_property_producer_native_evidence.json', 'roster_property_receive_evidence.json']
    report = dict(status='passed' if result.wasSuccessful() else 'failed', test_methods_run=result.testsRun,
                  failure_count=len(result.failures), error_count=len(result.errors),
                  failures=[{'test': str(test), 'traceback': tb} for test, tb in result.failures],
                  errors=[{'test': str(test), 'traceback': tb} for test, tb in result.errors],
                  source_sha256={f'Native/{name}.py': sha((ROOT / f'Native/{name}.py').read_bytes()) for name in sources},
                  test_sha256=sha(Path(__file__).read_bytes()), test_dependency_sha256={},
                  evidence_sha256={str((RESEARCH / name).relative_to(ROOT.parent)): sha((RESEARCH / name).read_bytes()) for name in evidences},
                  python_version=sys.version, unicorn_version=unicorn.__version__, capstone_version=capstone.__version__,
                  fixture_synthetic=True, game_process_accessed=False, host_native_code_executed=False, installable=False,
                  emulator_runs=RUNS,
                  execution_counts={'candidate': sum(not run['original'] for run in RUNS),
                                    'original_baseline': sum(run['original'] for run in RUNS), 'total': len(RUNS)},
                  temporary_helpers={'mode': 'contract_stubs_only', 'rvas': {hex(rva): role for rva, role in HELPERS.items()},
                                     'checks': ['create/allocate/release/release order per block', 'exact allocation size and align=4',
                                                'Windows shadow space and call alignment', 'volatile GPR/XMM clobber tolerance',
                                                'no temporary-buffer read/write before allocation or after first snapshot restore',
                                                'both restores retain the same 24-byte scope snapshot and return arena offset to its prior value'],
                                     'assumptions': ['successful non-null allocation', 'release restores the saved arena block/offset without interleaving',
                                                     'helpers preserve nonvolatile registers and return normally']},
                  limits=['Synthetic valid dense/prefix partition, unique entity IDs and mapped storage; actual caller lifetime/concurrency unproven',
                          'Entry copies pointer/aux/property and clears boundary primary; primary at source ordinal is intentionally not swapped',
                          'Entity flag is staged by synthetic caller; no actual notification or external resource integration',
                          'Temporary helpers are explicit contract stubs, not executed engine allocation/release implementations',
                          'Successful helper return is assumed; originals mutate roster before allocation, and failure rollback is not validated',
                          'Receiver uses synthetic incoming bytes; no serializer, transport, hooks, Windows unwind, installation or multiplayer verification'])
    out = ROOT / 'verification/native_roster_classify_tests.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], methods=result.testsRun, executions=len(RUNS), failures=len(result.failures), errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
