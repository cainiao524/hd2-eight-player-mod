"""Exercise saved/candidate network-index getters and changed-roster integration.

Getter and removal helpers execute captured/emitted x64 in synthetic Unicorn
RAM. Only the classification integration uses the separately pinned fixture's
explicit temporary-resource contract stubs. No game process is accessed.
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
S, B, MAP = 0x18200100400, 0x18200800100, 0x18200200100
STACK, RSP = 0x182F0000000, 0x182F0008008
ENTRY, END = 0x606AD0, 0x606B75
NETWORKS = [0x80000007, 0xFFFFFFFE, 0x7FFFFFFF, 0x12345678, 0xABCDEF04, 0x00010000, 0xFFFFFFFF, 0xFEDCBA98]
SEEDS = {name: 0xABCDEF0100000000 + i for i, name in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
EVIDENCE = RESEARCH / 'roster_getter_native_evidence.json'
EVIDENCE_SHA = '1360863bfe1f1f6ce640ef049776d3b31703a1cbfe2bea3f90bf20555f69e0fd'
CLASSIFY_FIXTURE_SHA = '50ac149e11274994f4f8fa6e766e5937ff1317130eb1a16718882da7859a8593'
RUNS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


native = load('getter_under_test', ROOT / 'Native/roster_getter.py')
classifier = load('getter_classify_dependency', ROOT / 'Native/roster_classify.py')
remove = load('getter_remove_dependency', ROOT / 'Native/roster_remove.py')
insert = load('getter_insert_dependency', ROOT / 'Native/roster_insert.py')
move = load('getter_move_dependency', ROOT / 'Native/roster_move.py')
receiver = load('getter_receiver_dependency', ROOT / 'Native/roster_receiver.py')
fixture_path = ROOT / 'tests/test_native_roster_classify.py'
assert sha(fixture_path.read_bytes()) == CLASSIFY_FIXTURE_SHA
chain = load('getter_pinned_classify_fixture', fixture_path)
raw = EVIDENCE.read_bytes(); assert sha(raw) == EVIDENCE_SHA
body = json.loads(raw)['bodies'][hex(ENTRY)]
cursor, chunks = ENTRY, []
for row in body['instructions']:
    blob = bytes.fromhex(row['bytes'])
    assert int(row['rva'], 16) == cursor and sha(blob) == row['sha256']
    chunks.append(blob); cursor += len(blob)
BODY = b''.join(chunks)
assert cursor == END and len(body['instructions']) == 43 and BODY.hex() == body['bytes_hex']
assert sha(BODY) == '96ce6884140adb9ae93688e042a2b5db7ffc1e59ffb45eb03188e6bab79abcfb'


def params(game=GAME):
    return dict(game_base=game, code_address=game + 0x100F0000, reject_address=game + 0x100F8000,
                roster_address=S, storage_address=B)


def decode(blob, address):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); decoder.detail = True
    rows = list(decoder.disasm(blob, address)); assert sum(row.size for row in rows) == len(blob)
    return rows


class Fixture:
    def __init__(self, ordinal=7, *, t=8, d=3, capacity=8, keys=None, multiplier=1, original=False,
                 game=GAME, query=None, invalid=0xFFFFFFFF, empty=0, actual_s=S,
                 roster_mapped=True, storage_mapped=True, changes=None):
        self.ordinal, self.t, self.d, self.capacity = ordinal, t, d, capacity
        self.original, self.game, self.multiplier = original, game, multiplier
        self.empty = empty
        self.keys = list(keys) if keys else [11 + 8 * i for i in range(8)]
        self.query = self.keys[ordinal] if query is None else query
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages, self.trace, self.reads, self.writes = set(), [], [], []
        arguments = params(game); arguments.update(changes or {})
        self.artifact = native.build(BODY, **arguments)
        self.start = game + ENTRY if original else self.artifact['entry_address']
        self.reject, self.stop = self.artifact['reject_address'], game + 0x10100000
        blob = BODY if original else bytes.fromhex(self.artifact['code_hex'])
        self.map(self.start, len(blob)); self.write(self.start, blob)
        for address in (self.reject, self.stop): self.map(address, 1); self.write(address, b'\xcc')
        self.map(game + 0x3326468, 8); self.write(game + 0x3326468, u64(actual_s))
        self.map(game + 0x3483C20, 4); self.write(game + 0x3483C20, u32(invalid))
        self.map(STACK, 0x10000); self.write(RSP, u64(self.stop))
        self.table = [(empty, 0xFFFFFFFF)] * capacity
        if roster_mapped:
            self.map(S - 0x80, 0x600); self.map(MAP - 0x80, 0x200)
            for off, value in ((0x80, t), (0x84, d), (0x88, min(d, 2)), (0xD8, capacity), (0xDC, empty), (0xE0, multiplier)):
                self.write(S + off, u32(value))
            self.write(S + 0xD0, u64(MAP))
            for i in range(min(t, capacity, 4 if original else 8)):
                bucket = next((self.keys[i] * multiplier + j) & (capacity - 1) for j in range(capacity)
                              if self.table[(self.keys[i] * multiplier + j) & (capacity - 1)][0] == empty)
                self.table[bucket] = (self.keys[i], i)
            for bucket, (key, index) in enumerate(self.table): self.write(MAP + bucket * 8, u32(key) + u32(index))
        if storage_mapped:
            self.map(B - 0x80, 0x780)
            for i in range(4 if original else 8):
                self.write(self.property(i), bytes((i * 31 + j * 7 + 17) & 255 for j in range(0x20)))
                self.write(self.property(i) + 0xC, u32(NETWORKS[i]))
        for name, value in SEEDS.items(): self.uc.reg_write(reg(name), value)
        for i in range(6, 16): self.uc.reg_write(reg('xmm' + str(i)), (0x0102030405060708 + i) * (1 + (1 << 64)))
        for name, value in dict(rsp=RSP, rax=0xA5A50000DEADBEEF, rcx=0xDEAD0000,
                               rdx=0xBEEF000000000000 | self.query, r8=0x8181818181818181, r9=0x9191919191919191).items():
            self.uc.reg_write(reg(name), value)
        self.outcome = None; self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, access, address, size, value, data: self.reads.append((address, size)))
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data: self.writes.append((address, size)))

    def property(self, ordinal): return (S + 0x3A8 if self.original else B + 0x580) + ordinal * 0x20
    def map(self, address, size):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000); self.uc.mem_write(page, b'\xa5' * 0x1000); self.pages.add(page)
    def read(self, address, size): return bytes(self.uc.mem_read(address, size))
    def write(self, address, blob): self.uc.mem_write(address, blob)
    def snapshot(self): return {page: self.read(page, 0x1000) for page in self.pages if not STACK <= page < STACK + 0x10000}
    def on_code(self, uc, address, size, data):
        self.trace.append(address)
        if address in (self.stop, self.reject): self.outcome = 'return' if address == self.stop else 'reject'; uc.emu_stop()
    def run(self, name):
        self.uc.emu_start(self.start, 0, count=10000)
        assert self.outcome is not None, 'no bounded outcome'
        self.after = self.snapshot()
        RUNS.append(dict(name=name, component='getter', original=self.original, ordinal=self.ordinal,
                         t=self.t, d=self.d, capacity=self.capacity, query=self.query, outcome=self.outcome,
                         return_rax=self.uc.reg_read(reg('rax')), instructions=len(self.trace)))
        return self


class GetterTests(unittest.TestCase):
    def abi(self, f, rejected=False):
        self.assertEqual(f.uc.reg_read(reg('rsp')), RSP if rejected else RSP + 8)
        for name, value in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(name)), value, name)
        for i in range(6, 16): self.assertEqual(f.uc.reg_read(reg('xmm' + str(i))), (0x0102030405060708 + i) * (1 + (1 << 64)))
        self.assertEqual(f.uc.reg_read(reg('edx')), f.query)
        self.assertEqual(f.before, f.after)
        self.assertTrue(all(STACK <= address and address + size <= STACK + 0x10000 for address, size in f.writes))

    def success(self, f, expected=None, hit=True):
        self.assertEqual(f.outcome, 'return'); self.abi(f)
        self.assertEqual(f.uc.reg_read(reg('rax')), NETWORKS[f.ordinal] if expected is None else expected)
        if hit: self.assertIn((f.property(f.ordinal) + 0xC, 4), f.reads)
        else: self.assertFalse(any((S + 0x3A8 <= address < S + 0x428) or (B <= address < B + 0x680) for address, size in f.reads))

    def rejected(self, f, reason):
        self.assertEqual(f.outcome, 'reject'); self.assertEqual(f.uc.reg_read(reg('r10d')), reason)
        self.abi(f, True)
        self.assertFalse(any((S + 0x3A8 <= address < S + 0x428) or (B <= address < B + 0x680) for address, size in f.reads))

    def test_01_source_control_flow_and_fixed_fingerprint(self):
        self.assertEqual(native.load_source(EVIDENCE), BODY)
        artifact = native.build(BODY, **params()); blob = bytes.fromhex(artifact['code_hex'])
        self.assertEqual(sha(blob), artifact['code_sha256'])
        instructions = decode(blob, artifact['entry_address']); boundaries = {row.address for row in instructions}
        for row in instructions:
            self.assertFalse(row.group(capstone.CS_GRP_CALL))
            if row.group(capstone.CS_GRP_JUMP): self.assertIn(row.operands[0].imm, boundaries | {artifact['reject_address']})
        with self.assertRaises(ValueError): native.build(bytes([BODY[0] ^ 1]) + BODY[1:], **params())

    def test_02_collision_ordinals_full_network_dwords_and_pending(self):
        for ordinal in range(8):
            self.success(Fixture(ordinal, d=0).run('all_ordinals_pending'))
        # Zero and maximum DWORD are values, and must not be clamped to slot.
        for network in (0, 7, 8, 0x100, 0x80000000, 0xFFFFFFFF):
            f = Fixture(5); f.write(f.property(5) + 0xC, u32(network)); f.before = f.snapshot()
            self.success(f.run('network_dword_domain'), network)
        for capacity in (1, 2, 4, 8, 16):
            t = min(capacity, 8)
            for ordinal in range(t):
                self.success(Fixture(ordinal, t=t, d=t, capacity=capacity).run('valid_power_two_map_capacity'))
        for ordinal in range(8):
            self.success(Fixture(ordinal, keys=[2, 10, 17, 25, 8, 16, 31, 39], multiplier=3,
                                 game=0x7FF800000000).run('mixed_hash_second_aslr'))

    def test_03_original_four_slot_paired_baseline(self):
        for ordinal in range(4):
            original = Fixture(ordinal, t=4, d=1, original=True).run('original_baseline')
            candidate = Fixture(ordinal, t=4, d=1).run('candidate_baseline_pair')
            self.success(original); self.success(candidate)
            self.assertEqual(original.uc.reg_read(reg('rax')), candidate.uc.reg_read(reg('rax')))

    def test_04_all_ordinary_missing_paths(self):
        for original in (False, True):
            cases = [dict(t=0, d=0, capacity=0, query=75),
                     dict(t=4 if original else 8, d=1, capacity=4 if original else 8, query=75),
                     dict(t=3, d=1, query=75),
                     dict(t=4, d=1, query=0, invalid=0, actual_s=0x40000000, roster_mapped=False),
                     dict(t=4, d=1, query=0xFFFFFFFF, actual_s=0x40000000, roster_mapped=False)]
            for case in cases:
                f = Fixture(0, original=original, storage_mapped=False, **case).run('ordinary_missing')
                self.success(f, 0xFFFFFFFF, False)
                if not case.get('roster_mapped', True):
                    self.assertTrue(all(address in (GAME + 0x3326468, GAME + 0x3483C20) or STACK <= address < STACK + 0x10000
                                        for address, size in f.reads))
            f = Fixture(0, t=4, d=1, original=original, storage_mapped=False)
            bucket = next(i for i, pair in enumerate(f.table) if pair[0] == f.query)
            f.write(MAP + bucket * 8 + 4, u32(0xFFFFFFFF)); f.before = f.snapshot()
            self.success(f.run('map_value_invalid'), 0xFFFFFFFF, False)
        # Empty key differs from global invalid, but a -1 bucket value keeps
        # the original ordinary-missing path before the new stale-value guard.
        f = Fixture(0, t=4, query=0, storage_mapped=False).run('empty_key_invalid_value')
        self.success(f, 0xFFFFFFFF, False)

    def test_05_hit_guards_and_empty_key_stale_value(self):
        f = Fixture(0, actual_s=0x40000000, roster_mapped=False, storage_mapped=False).run('wrong_binding')
        self.rejected(f, 1)
        self.assertTrue(all(address in (GAME + 0x3326468, GAME + 0x3483C20) or STACK <= address < STACK + 0x10000 for address, size in f.reads))
        for ordinal, tracked, reason in [(8, 8, 2), (0xFFFFFFFE, 8, 2), (0, 9, 3), (0, 0xFFFFFFFF, 3),
                                          (0, 0, 4), (7, 7, 4), (3, 2, 4)]:
            f = Fixture(0, storage_mapped=False)
            bucket = next(i for i, pair in enumerate(f.table) if pair[0] == f.query)
            f.write(MAP + bucket * 8 + 4, u32(ordinal)); f.write(S + 0x80, u32(tracked)); f.before = f.snapshot()
            self.rejected(f.run('invalid_hit_domain'), reason)
        # Original treats the map's empty key with stale ordinal 2 as a hit.
        # Candidate intentionally rejects this case before reading property.
        for original in (True, False):
            f = Fixture(2, t=4, query=0, original=original)
            f.write(MAP + 4, u32(2)); f.before = f.snapshot(); f.run('empty_key_stale_value')
            if original: self.success(f)
            else: self.rejected(f, 5)

    def test_06_address_rel32_and_twelve_function_bundle(self):
        for changes in [dict(storage_address=B + 1), dict(storage_address=S + 0x100),
                        dict(code_address=GAME + ENTRY), dict(reject_address=B + 0x500), dict(game_base=GAME + 1)]:
            arguments = params(); arguments.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): native.build(BODY, **arguments)
        artifact = native.build(BODY, **params())
        jumps = [row for row in decode(bytes.fromhex(artifact['code_hex']), artifact['code_address'])
                 if row.mnemonic == 'jmp' and row.operands[0].imm == artifact['reject_address']]
        self.assertTrue(jumps)
        low = max(row.address + row.size - (1 << 31) for row in jumps)
        high = min(row.address + row.size + (1 << 31) - 1 for row in jumps)
        for address in (low, high):
            self.rejected(Fixture(0, actual_s=0x40000000, roster_mapped=False, storage_mapped=False,
                                  changes={'reject_address': address}).run('reject_rel32_boundary'), 1)
        for address in (low - 1, high + 1):
            arguments = params(); arguments['reject_address'] = address
            with self.assertRaises(ValueError): native.build(BODY, **arguments)
        values = chain.bundle_params(); values.update(getter_code_address=params()['code_address'], getter_reject_address=params()['reject_address'])
        sources = [BODY, classifier.load_sources(RESEARCH / 'roster_classify_native_evidence.json'),
                   remove.load_sources(RESEARCH / 'roster_remove_native_evidence.json'), insert.load_sources(RESEARCH / 'roster_insert_native_evidence.json'),
                   move.load_source(RESEARCH / 'roster_move_native_evidence.json'),
                   insert.base_bundle.pair.producer.load_source(RESEARCH / 'roster_property_producer_native_evidence.json'),
                   receiver.load_source(RESEARCH / 'roster_property_receive_evidence.json')]
        result = native.build_bundle(*sources, **values)
        self.assertEqual(result['getter']['storage_address'], B); self.assertEqual(result['getter']['roster_address'], S)
        for field, value in [('getter_code_address', values['classify_code_addresses']['enter']),
                              ('getter_code_address', values['remove_code_addresses']['legacy']),
                              ('getter_reject_address', values['receiver_reject_address'])]:
            bad = json.loads(json.dumps(values)); bad[field] = value
            with self.assertRaises(ValueError): native.build_bundle(*sources, **bad)

    def test_07_classifier_remove_then_getter_uses_updated_map(self):
        f = chain.Fixture('enter', 8, 8, 2, 7)
        for i, network in enumerate(NETWORKS): f.write(f.slot('property', i) + 0xC, u32(network))
        f.capture_records(); f.reset_call(); f.run('getter_chain_classify')
        chain.ClassifyTests().success(f)
        RUNS.append(dict(chain.RUNS[-1], component='classifier', temporary_helpers='pinned_contract_stubs'))
        getter = native.build(BODY, **params())
        for address, blob in [(getter['code_address'], bytes.fromhex(getter['code_hex'])), (getter['reject_address'], b'\xcc')]:
            f.map(address, len(blob)); f.write(address, blob)
        def query(key, ordinal, expected):
            f.t, f.d, f.p = [f.int32(S + off) for off in (0x80, 0x84, 0x88)]
            f.ordinal = ordinal if ordinal is not None else -1
            f.reset_call(); f.reject = getter['reject_address']; f.uc.reg_write(reg('edx'), key)
            f.run('getter_chain_query', getter['entry_address'])
            self.assertEqual(f.outcome, 'return'); chain.ClassifyTests().abi(f)
            self.assertEqual(f.uc.reg_read(reg('rax')), expected); self.assertEqual(f.before, f.after)
            self.assertEqual(f.uc.reg_read(reg('edx')), key); self.assertEqual(f.calls, [])
            if ordinal is not None: self.assertIn((B + 0x580 + ordinal * 0x20 + 0xC, 4), f.reads)
            else: self.assertFalse(any(B <= address < B + 0x680 for address, size in f.reads))
            self.assertIn((S + 0xD0, 8), f.reads)
            RUNS.append(dict(chain.RUNS[-1], component='getter', kind='getter', query=key, expected_ordinal=ordinal))
        query(67, 2, NETWORKS[7])
        # Actual captured map deletion and emitted mover run without stubs.
        rs = remove.load_sources(RESEARCH / 'roster_remove_native_evidence.json')
        artifact = remove.build(rs['registered'], kind='registered', game_base=GAME, code_address=GAME + 0x100C0000,
                                roster_address=S, storage_address=B, move_code_address=GAME + 0x10040000, reject_address=GAME + 0x100C8000)
        ms = move.load_source(RESEARCH / 'roster_move_native_evidence.json')
        mover = move.build(ms, game_base=GAME, code_address=GAME + 0x10040000, roster_address=S,
                           storage_address=B, reject_address=GAME + 0x10048000)
        deletion = bytes.fromhex(json.loads((RESEARCH / 'roster_remove_native_evidence.json').read_bytes())['bodies']['0x172f8a0']['bytes_hex'])
        self.assertEqual(sha(deletion), 'd58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f')
        for address, blob in [(artifact['code_address'], bytes.fromhex(artifact['code_hex'])), (artifact['reject_address'], b'\xcc'),
                              (mover['code_address'], bytes.fromhex(mover['code_hex'])), (mover['reject_address'], b'\xcc'),
                              (GAME + 0x172F8A0, deletion)]:
            f.map(address, len(blob)); f.write(address, blob)
        observed = []
        f.uc.hook_add(UC_HOOK_CODE, lambda uc, address, size, data: observed.append(address)
                      if address in (GAME + 0x172F8A0, mover['entry_address']) else None)
        f.capture_records(); before_records = dict(f.records)
        f.t, f.d, f.p = [f.int32(S + off) for off in (0x80, 0x84, 0x88)]
        f.ordinal = 1; f.target = f.int64(f.slot('pointer', 1))
        f.reset_call(); f.reject = artifact['reject_address']; f.uc.reg_write(reg('rcx'), f.target)
        f.run('getter_chain_remove', artifact['entry_address'])
        self.assertEqual(f.outcome, 'return'); chain.ClassifyTests().abi(f)
        self.assertEqual(observed, [GAME + 0x172F8A0, mover['entry_address'], mover['entry_address']])
        expected_keys = [11, 67, 27, 35, 43, 51, 59]
        chain.ClassifyTests().map_is_bijection(f, expected_keys)
        changes = [(S + 0x80, u32(7)), (S + 0x84, u32(7)), (S + 0x88, u32(2)), (MAP, f.read(MAP, 64))]
        for dst, src in enumerate([0, 2, 7, 3, 4, 5, 6]):
            for name, off, old, stride in chain.LAYOUT: changes.append((f.slot(name, dst), before_records[name, src]))
        self.assertEqual(f.after, chain.changed_pages(f.before, changes))
        RUNS.append(dict(chain.RUNS[-1], component='remove', kind='registered', actual_map_delete_and_mover=True))
        query(67, 1, NETWORKS[7])
        query(27, 2, NETWORKS[2])
        query(19, None, 0xFFFFFFFF)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GetterTests))
    sources = ['roster_getter', 'roster_classify', 'roster_remove', 'roster_insert', 'roster_bundle', 'roster_property_pair', 'roster_producer', 'roster_receiver', 'roster_move']
    evidences = ['roster_getter_native_evidence.json', 'roster_classify_native_evidence.json', 'roster_remove_native_evidence.json',
                 'roster_insert_native_evidence.json', 'roster_move_native_evidence.json', 'roster_property_producer_native_evidence.json', 'roster_property_receive_evidence.json']
    report = dict(status='passed' if result.wasSuccessful() else 'failed', test_methods_run=result.testsRun,
                  failure_count=len(result.failures), error_count=len(result.errors),
                  failures=[{'test': str(test), 'traceback': tb} for test, tb in result.failures],
                  errors=[{'test': str(test), 'traceback': tb} for test, tb in result.errors],
                  source_sha256={f'Native/{name}.py': sha((ROOT / f'Native/{name}.py').read_bytes()) for name in sources},
                  test_sha256=sha(Path(__file__).read_bytes()),
                  test_dependency_sha256={'tests/test_native_roster_classify.py': CLASSIFY_FIXTURE_SHA},
                  evidence_sha256={str((RESEARCH / name).relative_to(ROOT.parent)): sha((RESEARCH / name).read_bytes()) for name in evidences},
                  python_version=sys.version, unicorn_version=unicorn.__version__, capstone_version=capstone.__version__,
                  fixture_synthetic=True, game_process_accessed=False, host_native_code_executed=False, installable=False,
                  emulator_runs=RUNS,
                  execution_counts={'candidate': sum(not run['original'] for run in RUNS),
                                    'original_baseline': sum(run['original'] and run['name'] != 'empty_key_stale_value' for run in RUNS),
                                    'original_expected_phantom_hit': sum(run['original'] and run['name'] == 'empty_key_stale_value' for run in RUNS),
                                    'total': len(RUNS)},
                  limits=['Synthetic valid readable map with zero or power-of-two capacity and valid probe chain; malformed map allocation is not guarded',
                          'Getter preserves complete network DWORD without imposing a gameplay index range; ordinal is a separate lookup value',
                          'Ordinary misses preserve original semantics; tracked-range and stale empty-key rejection are new candidate guards',
                          'Classifier integration uses pinned fixture temporary contract stubs and caller-staged flags; removal helpers execute actual saved/emitted bytes',
                          'No actual caller, storage lifetime, synchronization, rejection handler, hook, Windows unwind, installation or multiplayer validation'])
    out = ROOT / 'verification/native_roster_getter_tests.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], methods=result.testsRun, executions=len(RUNS), failures=len(result.failures), errors=len(result.errors))))
    raise SystemExit(0 if result.wasSuccessful() else 1)
