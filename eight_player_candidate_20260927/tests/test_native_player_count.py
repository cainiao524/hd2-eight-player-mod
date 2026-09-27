"""Execute fixed count/filter instructions against synthetic scalar contracts.

Context execution stops at 94CA3A and is explicitly a prefix observation.
Filter execution reaches its real return and uses real 177E3C0 predicates.
Eligibility/modifier/allocator/security-cookie dependencies are declared stubs.
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
f32 = lambda value: struct.pack('<f', value)
reg = lambda name: getattr(xr, 'UC_X86_REG_' + name.upper())
GAME = 0x7FF600000000
DB, TEMPLATE, SOURCES, OUTPUT, COUNT, TAGS, TEMP, CONFIG = [0x18200100000 + i * 0x100000 for i in range(8)]
STACK, RSP = 0x182F0000000, 0x182F0008008
COOKIE = 0x12345678ABCDEF00
SEEDS = {name: 0xABCDEF0100000000 + i for i, name in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
EVIDENCE = RESEARCH / 'roster_player_count_native_evidence.json'
CONTEXT_EVIDENCE = RESEARCH / 'roster_departure_callee_evidence.json'
EVIDENCE_SHA = '8f0fad49d9f5bc7e95ffe8735007b59c302034704707602c8d8093ad795676e3'
CONTEXT_EVIDENCE_SHA = '04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0'
RUNS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


native = load('player_count_under_test', ROOT / 'Native/player_count.py')
raw = EVIDENCE.read_bytes(); assert sha(raw) == EVIDENCE_SHA
cr = CONTEXT_EVIDENCE.read_bytes(); assert sha(cr) == CONTEXT_EVIDENCE_SHA
ev, ce = json.loads(raw), json.loads(cr)
FILTER = bytes.fromhex(ev['bodies']['0x94be10']['bytes_hex'])
CONTEXT = bytes.fromhex(ce['bodies']['0x94c9c0']['bytes_hex'])
PREDICATE = bytes.fromhex(ev['bodies']['0x177e3c0']['bytes_hex'])
assert sha(FILTER) == '0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e'
assert sha(CONTEXT) == '7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2'
assert sha(PREDICATE) == '6f2946133c59eff112dee7cd648bef3126d78e4f9b4dde1fc07f32af4db54a38'


def params(game=GAME): return dict(game_base=game, trampoline_address=game + 0x10200000)


def decode(blob, address):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); decoder.detail = True
    rows = list(decoder.disasm(blob, address)); assert sum(row.size for row in rows) == len(blob)
    return rows


def changed_pages(before, changes):
    result = {page: bytearray(blob) for page, blob in before.items()}
    for address, blob in changes:
        for i, value in enumerate(blob): result[(address + i) & ~0xFFF][(address + i) & 0xFFF] = value
    return {page: bytes(blob) for page, blob in result.items()}


class Fixture:
    def __init__(self, players, *, tech=3, minimum=1, maximum=4, override=False, aggregate=False,
                 candidate=True, prefix=False, game=GAME, trampoline=None):
        self.players, self.tech, self.minimum, self.maximum = players, tech, minimum, maximum
        self.override, self.aggregate, self.candidate, self.prefix, self.game = override, aggregate, candidate, prefix, game
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages, self.trace, self.reads, self.writes, self.calls = set(), [], [], [], []
        self.predicate_calls, self.weight_reads, self.trampoline_states = [], [], []
        self.allocated = False
        arguments = params(game)
        if trampoline is not None: arguments['trampoline_address'] = trampoline
        self.artifact = native.build(CONTEXT, FILTER, **arguments)
        self.start, self.stop = game + (0x94C9C0 if prefix else 0x94BE10), game + 0x10300000
        for entry, blob in ((0x94C9C0, CONTEXT), (0x94BE10, FILTER), (0x177E3C0, PREDICATE)):
            self.map(game + entry, len(blob)); self.write(game + entry, blob)
        if candidate:
            address = self.artifact['code_address']; blob = bytes.fromhex(self.artifact['code_hex'])
            self.map(address, len(blob)); self.write(address, blob)
            for patch in self.artifact['patches']:
                self.assert_bytes(game + patch['rva'], bytes.fromhex(patch['expected_hex']))
                self.write(game + patch['rva'], bytes.fromhex(patch['replacement_hex']))
        self.stub_roles = {game + 0x94A0A0: 'eligibility', game + 0x949E10: 'modifier',
                           game + 0x173B8D0: 'allocator', game + 0x2088770: 'security_cookie'}
        for address in self.stub_roles: self.map(address, 1); self.write(address, b'\xc3')
        self.map(self.stop, 1); self.write(self.stop, b'\xcc')
        for address, size in ((DB, 0xB0), (TEMPLATE, 0x118), (SOURCES, 0x100), (OUTPUT - 0x40, 0x158),
                              (COUNT, 4), (TAGS, 0x44), (TEMP - 0x40, 0x88), (CONFIG, 0x48), (STACK, 0x10000),
                              (game + 0x263C010, 8), (game + 0x33266A0, 8),
                              (game + 0x23C675C, 4), (game + 0x23C7A74, 4)):
            self.map(address, size)
        self.write(game + 0x263C010, u64(COOKIE)); self.write(game + 0x33266A0, u64(CONFIG))
        self.write(CONFIG + 8, u32(0))
        self.write(game + 0x23C675C, bytes.fromhex('cdcccc3d'))
        self.write(game + 0x23C7A74, bytes.fromhex('0000af43'))
        self.write(DB, bytes(0xB0)); self.write(DB, u64(SOURCES)); self.write(DB + 8, u32(2))
        self.write(TEMPLATE, bytes(0x118)); self.write(TEMPLATE, u32(0x1234) + u32(2) + u32(0xC0DE1234))
        self.write(TEMPLATE + 0xE0, f32(1.0)); self.write(TEMPLATE + 0xE4, f32(2.0))
        for offset, value in ((0xE8, 0x05060708), (0xEC, 1), (0xF0, 10), (0xF4, minimum),
                              (0xF8, maximum), (0xFC, 0x01020304), (0x110, 0xAABBCCDD)):
            self.write(TEMPLATE + offset, u32(value))
        self.write(TEMPLATE + 0x100, u64(0x1111222233334444))
        self.write(TEMPLATE + 0x108, f32(5.5)); self.write(TEMPLATE + 0x10C, f32(6.5))
        self.write(TAGS, bytes(0x44)); self.write(COUNT, u32(0x11111111))
        for i in range(2):
            base = SOURCES + i * 0x80
            self.write(base, bytes(0x80)); self.write(base, u32(0x1234)); self.write(base + 0x20, f32(1.0 if i == 0 else 3.0))
            for level in range(1, 11): self.write(base + 0x30 + (level - 1) * 4, f32(level * (2 if i == 0 else 6)))
        self.write(RSP, u64(self.stop))
        for name, value in SEEDS.items(): self.uc.reg_write(reg(name), value)
        for i in range(6, 16): self.uc.reg_write(reg('xmm' + str(i)), (0x0102030405060708 + i) * (1 + (1 << 64)))
        self.uc.reg_write(reg('rsp'), RSP)
        if prefix:
            self.uc.reg_write(reg('rcx'), 0xDEAD0000); self.uc.reg_write(reg('rdx'), 0xBEEF0000)
            self.write(RSP + 0x28, u32(tech)); self.write(RSP + 0x30, u32(players))
        else:
            for name, value in dict(rcx=0xDEAD0000, rdx=DB, r8=TEMPLATE, r9=1).items(): self.uc.reg_write(reg(name), value)
            for offset, blob in [(0x28, u64(OUTPUT)), (0x30, u64(COUNT)), (0x38, u32(tech)), (0x40, u32(players)),
                                  (0x48, u64(TAGS)), (0x50, bytes([override])), (0x58, bytes([aggregate]))]:
                self.write(RSP + offset, blob)
        self.outcome = None; self.before = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_READ, self.on_read)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, self.on_write)

    def map(self, address, size):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000); self.uc.mem_write(page, b'\xa5' * 0x1000); self.pages.add(page)
    def write(self, address, blob): self.uc.mem_write(address, blob)
    def read(self, address, size): return bytes(self.uc.mem_read(address, size))
    def int32(self, address): return struct.unpack('<I', self.read(address, 4))[0]
    def assert_bytes(self, address, blob): assert self.read(address, len(blob)) == blob
    def snapshot(self): return {page: self.read(page, 0x1000) for page in self.pages if not STACK <= page < STACK + 0x10000}
    def gprs(self): return {name: self.uc.reg_read(reg(name)) for name in ('rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp', 'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15')}
    def on_read(self, uc, access, address, size, value, data):
        self.reads.append((address, size))
        for base in (SOURCES, SOURCES + 0x80):
            if base + 0x30 <= address < base + 0x58: self.weight_reads.append((address, size))
        if TEMP <= address < TEMP + 8: assert self.allocated and address + size <= TEMP + 8
    def on_write(self, uc, access, address, size, value, data):
        pc = uc.reg_read(reg('rip')); self.writes.append((address, size, pc))
        assert not self.artifact['code_address'] <= pc < self.artifact['code_address'] + self.artifact['size_bytes'], 'trampoline wrote memory'
        if TEMP <= address < TEMP + 8: assert self.allocated and address + size <= TEMP + 8
    def on_code(self, uc, address, size, data):
        self.trace.append(address)
        if self.prefix and address == self.game + 0x94CA3A:
            self.outcome = 'prefix_observation'; uc.emu_stop(); return
        if address == self.stop: self.outcome = 'return'; uc.emu_stop(); return
        if address == self.artifact['code_address']:
            self.trampoline_states.append({'before': self.gprs()})
        if self.trampoline_states and 'after' not in self.trampoline_states[-1] and address in (self.game + 0x94C081, self.game + 0x94C085):
            state = self.trampoline_states[-1]; state['after'] = self.gprs(); state['continuation'] = address
            assert state['before'] == state['after'], 'trampoline changed GPR/RSP'
        if address == self.game + 0x177E3C0:
            self.predicate_calls.append({'rcx': uc.reg_read(reg('rcx')), 'rdx': uc.reg_read(reg('rdx'))})
        role = self.stub_roles.get(address)
        if role is None: return
        rsp = uc.reg_read(reg('rsp')); assert rsp % 16 == 8
        event = {'role': role, 'rsp_mod16': rsp % 16}; result = 0; scalar = None
        if role == 'eligibility':
            assert uc.reg_read(reg('rcx')) == TEMPLATE and uc.reg_read(reg('edx')) == self.tech
            event['tech'] = self.tech; scalar = 1.0
        elif role == 'modifier':
            assert uc.reg_read(reg('rcx')) == DB
            source = uc.reg_read(reg('rdx')); assert source in (SOURCES, SOURCES + 0x80)
            scalar = struct.unpack('<f', self.read(source + 0x20, 4))[0]; event['source'] = source
        elif role == 'allocator':
            assert uc.reg_read(reg('rcx')) == self.game + 0x33262F0
            assert uc.reg_read(reg('rdx')) == 8 and uc.reg_read(reg('r8d')) == 8 and not self.allocated
            event.update(size=8, alignment=8); self.allocated = True; result = TEMP
        else:
            assert uc.reg_read(reg('rcx')) == COOKIE; event['cookie_matched'] = True
        self.calls.append(event)
        self.write(rsp + 8, b'\xc7' * 32)
        for i, name in enumerate(('rax', 'rcx', 'rdx', 'r8', 'r9', 'r10', 'r11')): uc.reg_write(reg(name), 0xCDCD000000000000 + i)
        for i in range(6): uc.reg_write(reg('xmm' + str(i)), (0xAABBCCDDEEFF0000 + i) * (1 + (1 << 64)))
        uc.reg_write(reg('rax'), result)
        if scalar is not None: uc.reg_write(reg('xmm0'), struct.unpack('<I', f32(scalar))[0])

    def run(self, name):
        self.uc.emu_start(self.start, 0, count=30000)
        assert self.outcome is not None, 'no bounded outcome'
        self.after = self.snapshot()
        RUNS.append(dict(name=name, candidate=self.candidate, execution_scope='context_prefix' if self.prefix else 'full_filter',
                         players=self.players, tech=self.tech, minimum=self.minimum, maximum=self.maximum,
                         override=self.override, aggregate=self.aggregate, outcome=self.outcome,
                         effective_context_players=self.uc.reg_read(reg('ebp')) if self.prefix else None,
                         effective_context_tech=self.uc.reg_read(reg('esi')) if self.prefix else None,
                         output_count=None if self.prefix else self.int32(COUNT), instructions=len(self.trace),
                         contract_stub_calls=self.calls, actual_predicate_calls=self.predicate_calls,
                         weight_reads=[{'address': address, 'size': size} for address, size in self.weight_reads],
                         trampoline_executions=len(self.trampoline_states)))
        return self


class PlayerCountTests(unittest.TestCase):
    def success(self, f, expected_admitted):
        self.assertEqual(f.outcome, 'return'); self.assertEqual(f.uc.reg_read(reg('rsp')), RSP + 8)
        for name, value in SEEDS.items(): self.assertEqual(f.uc.reg_read(reg(name)), value)
        for i in range(6, 16): self.assertEqual(f.uc.reg_read(reg('xmm' + str(i))), (0x0102030405060708 + i) * (1 + (1 << 64)))
        changes = [(COUNT, u32(int(expected_admitted)))]
        roles = ['eligibility']
        if expected_admitted:
            contribution = 5.0 if f.aggregate else 10.0
            fields = [(0, u32(0x1234) + u32(2) + u32(0xC0DE1234)), (0x60, u32(1)),
                      (0x64, f32(contribution)), (0x84, f32(8.0 * f.tech)), (0xA8, u64(TEMPLATE)),
                      (0xB0, u64(0x1111222233334444)), (0xB8, u32(0x01020304)), (0xBC, u32(0x05060708)),
                      (0xC0, f32(1.0)), (0xC4, f32(5.5)), (0xC8, f32(6.5)), (0xCC, u32(0xAABBCCDD)),
                      (0xD0, b'\0'), (0xD4, f32(contribution))]
            changes.extend((OUTPUT + off, blob) for off, blob in fields)
            changes.append((TEMP, u32(0) + u32(1)))
            self.assertEqual(f.predicate_calls, [{'rcx': TAGS, 'rdx': SOURCES + 0x58}, {'rcx': TAGS, 'rdx': SOURCES + 0xD8}])
            expected_addresses = {SOURCES + 0x30 + (f.tech - 1) * 4, SOURCES + 0xB0 + (f.tech - 1) * 4}
            self.assertEqual({address for address, size in f.weight_reads}, expected_addresses)
            self.assertEqual(len(f.weight_reads), 4); self.assertTrue(all(size == 4 for address, size in f.weight_reads))
            roles += ['allocator', 'modifier', 'modifier']
        else:
            self.assertEqual(f.predicate_calls, []); self.assertEqual(f.weight_reads, []); self.assertFalse(f.allocated)
        roles += ['security_cookie']
        self.assertEqual([event['role'] for event in f.calls], roles)
        self.assertEqual(f.after, changed_pages(f.before, changes))
        for state in f.trampoline_states: self.assertEqual(state['before'], state['after'])
        return f.read(OUTPUT, 0xD8), f.read(COUNT, 4), f.read(TEMP, 8)

    def test_01_source_patch_and_trampoline_contract(self):
        self.assertEqual(native.load_sources(EVIDENCE, CONTEXT_EVIDENCE), {'context': CONTEXT, 'filter': FILTER})
        artifact = native.build(CONTEXT, FILTER, **params())
        self.assertEqual([(p['rva'], p['expected_hex'], p['replacement_hex'][:2]) for p in artifact['patches']],
                         [(0x94CA30, 'b804000000', 'b8'), (0x94C07B, '413b47087704', 'e9')])
        self.assertEqual(artifact['patches'][0]['replacement_hex'], 'b808000000')
        self.assertEqual(artifact['size_bytes'], 51)
        blob = bytes.fromhex(artifact['code_hex']); self.assertEqual(sha(blob), artifact['code_sha256'])
        rows = decode(blob, artifact['code_address']); boundaries = {row.address for row in rows}
        for row in rows:
            self.assertIn(row.mnemonic, ('cmp', 'jne', 'ja', 'jmp'))
            if row.group(capstone.CS_GRP_JUMP):
                self.assertIn(row.operands[0].imm, boundaries | {GAME + 0x94C081, GAME + 0x94C085})
        for cs, fs in ((bytes([CONTEXT[0] ^ 1]) + CONTEXT[1:], FILTER), (CONTEXT, bytes([FILTER[0] ^ 1]) + FILTER[1:])):
            with self.assertRaises(ValueError): native.build(cs, fs, **params())

    def test_02_context_prefix_clamps_are_distinct(self):
        for candidate in (False, True):
            for players, tech in [(players, 3) for players in list(range(10)) + [0xFFFFFFFF]] + [(5, 1), (5, 10)]:
                f = Fixture(players, tech=tech, candidate=candidate, prefix=True).run('context_prefix_only')
                self.assertEqual(f.outcome, 'prefix_observation')
                self.assertEqual(f.uc.reg_read(reg('ebp')), min(max(players, 1), 8 if candidate else 4))
                self.assertEqual(f.uc.reg_read(reg('esi')), tech)
                self.assertEqual(f.before, f.after); self.assertEqual(f.calls, [])
                self.assertTrue(all(STACK <= address < STACK + 0x10000 for address, size, pc in f.writes))

    def test_03_one_through_four_full_output_compatibility(self):
        for minimum in range(1, 5):
            for maximum in range(minimum, 5):
                for players in range(1, 5):
                    expected = minimum <= players <= maximum
                    original = Fixture(players, minimum=minimum, maximum=maximum, candidate=False).run('original_legacy_domain')
                    candidate = Fixture(players, minimum=minimum, maximum=maximum).run('candidate_legacy_domain')
                    self.assertEqual(self.success(original, expected), self.success(candidate, expected))

    def test_04_five_through_eight_reuse_original_four_eligible_profiles(self):
        for minimum in range(1, 5):
            for maximum in range(minimum, 5):
                expected = maximum == 4
                original = Fixture(4, minimum=minimum, maximum=maximum, candidate=False).run('original_four_profile')
                baseline = self.success(original, expected)
                for players in range(5, 9):
                    f = Fixture(players, minimum=minimum, maximum=maximum).run('extended_legacy_profile')
                    self.assertEqual(self.success(f, expected), baseline)

    def test_05_other_ranges_malformed_range_and_override_preserved(self):
        cases = [(0, 0, 0), (0, 0, 1), (2, 5, 5), (2, 5, 6), (2, 8, 8), (2, 8, 9),
                 (5, 4, 4), (5, 4, 5), (5, 4, 8), (0xFFFFFFFF, 4, 0xFFFFFFFF)]
        for minimum, maximum, players in cases:
            expected = minimum <= players <= maximum
            original = Fixture(players, minimum=minimum, maximum=maximum, candidate=False).run('original_other_range')
            candidate = Fixture(players, minimum=minimum, maximum=maximum).run('candidate_other_range')
            self.assertEqual(self.success(original, expected), self.success(candidate, expected))
        for aggregate in (False, True):
            original = Fixture(7, minimum=5, maximum=3, override=True, aggregate=aggregate, candidate=False).run('original_override')
            candidate = Fixture(7, minimum=5, maximum=3, override=True, aggregate=aggregate).run('candidate_override')
            self.assertEqual(self.success(original, True), self.success(candidate, True))
            # The range is evaluated first; the later original override accepts
            # the record despite its false range result.
            self.assertEqual(len(candidate.trampoline_states), 1)
            self.assertEqual(candidate.trampoline_states[0]['continuation'], GAME + 0x94C085)

    def test_06_tech_index_and_second_aslr(self):
        for tech in (1, 3, 10):
            original = Fixture(4, tech=tech, minimum=2, maximum=4, candidate=False, game=0x7FF800000000).run('original_tech')
            candidate = Fixture(8, tech=tech, minimum=2, maximum=4, game=0x7FF800000000).run('candidate_tech')
            self.assertEqual(self.success(original, True), self.success(candidate, True))

    def test_07_region_alignment_and_rel32_boundaries(self):
        for changes in [dict(game_base=GAME + 1), dict(trampoline_address=GAME + 0x10000),
                        dict(trampoline_address=GAME - 16), dict(trampoline_address=GAME + native.IMAGE_SIZE - 16),
                        dict(trampoline_address=GAME + 0x10200001)]:
            arguments = params(); arguments.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): native.build(CONTEXT, FILTER, **arguments)
        artifact = native.build(CONTEXT, FILTER, **params())
        lo, hi = GAME + 0x94C07B + 5 - (1 << 31), GAME + 0x94C07B + 5 + (1 << 31) - 1
        for branch in artifact['branches']:
            target = branch['target_address']
            if artifact['code_address'] <= target < artifact['code_address'] + artifact['size_bytes']: continue
            after_offset = branch['address'] - artifact['code_address'] + len(bytes.fromhex(branch['opcode_hex'])) + 4
            lo = max(lo, target - ((1 << 31) - 1) - after_offset)
            hi = min(hi, target + (1 << 31) - after_offset)
        aligned_lo, aligned_hi = (lo + 15) & ~15, hi & ~15
        for address in (aligned_lo, aligned_hi): self.success(Fixture(8, trampoline=address).run('rel32_boundary'), True)
        for address in (aligned_lo - 16, aligned_hi + 16):
            with self.assertRaises(ValueError): native.build(CONTEXT, FILTER, game_base=GAME, trampoline_address=address)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlayerCountTests))
    counts = {'context_prefix_observations': sum(run['execution_scope'] == 'context_prefix' for run in RUNS),
              'full_filter_executions': sum(run['execution_scope'] == 'full_filter' for run in RUNS),
              'original_full_filter': sum(run['execution_scope'] == 'full_filter' and not run['candidate'] for run in RUNS),
              'candidate_full_filter': sum(run['execution_scope'] == 'full_filter' and run['candidate'] for run in RUNS), 'total': len(RUNS)}
    report = dict(status='passed' if result.wasSuccessful() else 'failed', test_methods_run=result.testsRun,
                  failure_count=len(result.failures), error_count=len(result.errors),
                  failures=[{'test': str(test), 'traceback': tb} for test, tb in result.failures],
                  errors=[{'test': str(test), 'traceback': tb} for test, tb in result.errors],
                  source_sha256={'Native/player_count.py': sha((ROOT / 'Native/player_count.py').read_bytes())},
                  test_sha256=sha(Path(__file__).read_bytes()), test_dependency_sha256={},
                  evidence_sha256={str(EVIDENCE.relative_to(ROOT.parent)): EVIDENCE_SHA, str(CONTEXT_EVIDENCE.relative_to(ROOT.parent)): CONTEXT_EVIDENCE_SHA},
                  python_version=sys.version, unicorn_version=unicorn.__version__, capstone_version=capstone.__version__,
                  fixture_synthetic=True, game_process_accessed=False, host_native_code_executed=False, installable=False,
                  emulator_runs=RUNS, execution_counts=counts,
                  captured_literals={'0x23c675c': 'cdcccc3d', '0x23c7a74': '0000af43'},
                  contracts={'0x94a0a0': 'eligibility scalar 1.0; assert template and unchanged tech parameter',
                             '0x949e10': 'source modifier scalar from synthetic source+20h, values 1.0 and 3.0',
                             '0x173b8d0': 'one successful 8-byte allocation, align8, fixed arena address; no engine allocator execution',
                             '0x2088770': 'validate synthetic security cookie then return',
                             '0x177e3c0': 'actual fixed 156-byte predicate, no stub'},
                  limits=['94C9C0 observations stop at 94CA3A; they are not complete context executions or notification/resource validation',
                          'Synthetic valid legacy profiles and scalar contracts prove local filtering/bytes only, not actual eight-player asset availability or balancing',
                          'The max==4 and min<=4 extension is a new candidate policy; non-four maxima and override behavior retain original semantics',
                          'Tech-level weights remain indexed by the separate 1..10 parameter; player count controls template range eligibility',
                          'FFFFFFFF input still becomes eight in the candidate context; departure pending-count underflow and caller lifecycle remain unresolved',
                          'Output capacity is provisioned for one input template; runtime template counts, storage, concurrency and allocation failure remain unverified',
                          'No full context integration, coordinated live patching, Windows unwind, installation or multiplayer validation'])
    out = ROOT / 'verification/native_player_count_tests.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=report['status'], methods=result.testsRun, executions=len(RUNS), **counts)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
