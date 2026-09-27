"""Execute the pinned original and emitted x64 receiver in synthetic Unicorn RAM.

No game process, host-native code, loader, hooks, executable host allocation or
live addresses are used. A rejection is observed at its supplied continuation;
the test deliberately does not pretend that the interior frame can just RET.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.native-test-deps'))
import capstone
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

MODULE_PATH = ROOT / 'Native' / 'roster_receiver.py'
MODULE_BYTES = MODULE_PATH.read_bytes()
spec = importlib.util.spec_from_file_location('native_roster_receiver_under_test', MODULE_PATH)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
EVIDENCE_PATH = ROOT.parent / 'five_player_feasibility_20260927' / 'roster_property_receive_evidence.json'
EVIDENCE_SHA = 'bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10'
BODY_SHA = '23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411'
ENTRY, END, SENTINEL = 0x60C890, 0x60C9BF, 0x3483C20
SPLICE, RESUME = 0xA2, 0xA8
DEFAULT_GAME = 0x00007FF600000000
ROSTER = 0x0000018200100400
WRONG_ROSTER = ROSTER + 0x20000
BUCKETS = 0x0000018200200100
PAYLOAD = 0x0000018200300200
CURSOR = 0x0000018200400100
PROPERTY = 0x0000018200800100
STACK = 0x00000182F0000000
ENTRY_RSP = STACK + 0x8008
REGISTER_SEEDS = {
    'rbx': 0x1122334455667788, 'rbp': 0x2233445566778899,
    'rsi': 0x33445566778899AA, 'rdi': 0x445566778899AABB,
    'r12': 0x5566778899AABBCC, 'r13': 0x66778899AABBCCDD,
    'r14': 0x778899AABBCCDDEE, 'r15': 0x8899AABBCCDDEEFF,
}
RUNS = []


def sha(value):
    return hashlib.sha256(value).hexdigest()


def u32(value):
    return struct.pack('<I', value)


def u64(value):
    return struct.pack('<Q', value)


def register(name):
    return getattr(xr, 'UC_X86_REG_' + name.upper())


def independently_read_body():
    raw = EVIDENCE_PATH.read_bytes()
    if sha(raw) != EVIDENCE_SHA:
        raise AssertionError('pinned evidence changed')
    rows = json.loads(raw)['receiver']['instructions']
    if len(rows) != 72:
        raise AssertionError('expected complete 72-instruction source')
    position, chunks = ENTRY, []
    for row in rows:
        blob = bytes.fromhex(row['bytes'])
        if int(row['rva'], 16) != position or sha(blob) != row['sha256']:
            raise AssertionError('source row gap or incorrect byte hash')
        chunks.append(blob)
        position += len(blob)
    body = b''.join(chunks)
    if position != END or len(body) != 303 or sha(body) != BODY_SHA:
        raise AssertionError('independent original body fingerprint mismatch')
    return body


BODY = independently_read_body()


def parameters(game=DEFAULT_GAME):
    return dict(game_base=game, code_address=game + 0x10000000,
                roster_address=ROSTER, property_address=PROPERTY,
                reject_address=game + 0x10004000)


def emit(**changes):
    args = parameters()
    args.update(changes)
    return native.build(BODY, **args)


def instructions(blob, base):
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    decoder.detail = True
    return list(decoder.disasm(blob, base))


def immediate_target(ins):
    return next(op.imm for op in ins.operands if op.type == X86_OP_IMM)


def emulate(*, name, ordinal=0, network_index=7, cursor=12, original=False,
            game=DEFAULT_GAME, entity=17, capacity=8, multiplier=1,
            buckets=None, input_roster=ROSTER, payload_mapped=True,
            global_invalid=0xFFFFFFFF, address_overrides=None):
    """Create valid synthetic headers; only intended invalidity is parameterized.

    Ordinals 4..7 in the original comparison use deliberately oversized synthetic
    roster storage; this is NOT evidence that the game's inline array has room.
    A wrong binding still has a readable map/header: the new guard runs after
    native lookup and cannot guard an invalid input roster pointer beforehand.
    """
    args = parameters(game)
    args.update(address_overrides or {})
    artifact = native.build(BODY, **args)
    blob = BODY if original else bytes.fromhex(artifact['code_hex'])
    start = game + ENTRY if original else artifact['entry_address']
    stop = game + 0x10006000
    reject = artifact['reject_address']
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    pages = set()

    def map_region(address, size, fill=0xA5):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in pages:
                uc.mem_map(page, 0x1000)
                uc.mem_write(page, bytes([fill]) * 0x1000)
                pages.add(page)

    for addr, size in ((ROSTER - 0x80, 0x700), (WRONG_ROSTER - 0x80, 0x700),
                       (PROPERTY - 0x80, 0x200), (BUCKETS - 0x80, 0x200),
                       (CURSOR - 0x80, 0x100), (STACK, 0x10000),
                       (game + SENTINEL, 4), (start, len(blob)),
                       (stop, 1), (reject, 1)):
        map_region(addr, size)
    if payload_mapped:
        map_region(PAYLOAD - 0x80, 0x900)
    uc.mem_write(start, blob)
    uc.mem_write(stop, b'\xcc')
    uc.mem_write(reject, b'\xcc')
    uc.mem_write(game + SENTINEL, u32(global_invalid))
    uc.mem_write(ENTRY_RSP, u64(stop))
    uc.mem_write(CURSOR, u32(cursor))
    if buckets is None:
        buckets = [(0, 0xFFFFFFFF)] * capacity
        if capacity:
            buckets[(entity * multiplier) & (capacity - 1)] = (entity, ordinal)
    if len(buckets) != capacity:
        raise AssertionError('fixture bucket count must equal header capacity')
    for roster in (ROSTER, WRONG_ROSTER):
        uc.mem_write(roster + 0xD0, u64(BUCKETS))
        uc.mem_write(roster + 0xD8, u32(capacity))
        uc.mem_write(roster + 0xDC, u32(0))
        uc.mem_write(roster + 0xE0, u32(multiplier))
    for index, (key, mapped_ordinal) in enumerate(buckets):
        uc.mem_write(BUCKETS + index * 8, u32(key) + u32(mapped_ordinal))
    words = [0x01234567, 0x89ABCDEF, 0xFFFFFFFF, network_index,
             0x80000000, 0x13579BDF, 0x2468ACE0, 0xDEADBEEF]
    payload = struct.pack('<8I', *words)
    if payload_mapped:
        uc.mem_write(PAYLOAD + cursor, payload)
    for name_reg, value in REGISTER_SEEDS.items():
        uc.reg_write(register(name_reg), value)
    for name_reg, value in dict(rsp=ENTRY_RSP, rcx=input_roster, rdx=entity,
                               r8=PAYLOAD, r9=CURSOR, r10=0xABCDEF0012345678).items():
        uc.reg_write(register(name_reg), value)
    # Every non-stack mapped page is checked, not just the intended record.
    before = {p: bytes(uc.mem_read(p, 0x1000)) for p in pages if not STACK <= p < STACK + 0x10000}
    reads, writes, trace, outcome = [], [], [], []

    def on_code(machine, address, size, data):
        trace.append(address)
        if address in (stop, reject):
            outcome.append('return' if address == stop else 'reject')
            machine.emu_stop()

    def on_read(machine, access, address, size, value, data):
        reads.append((address, size))

    def on_write(machine, access, address, size, value, data):
        writes.append((address, size, value))

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.hook_add(UC_HOOK_MEM_READ, on_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    uc.emu_start(start, 0, count=4000)
    if len(outcome) != 1:
        raise AssertionError('receiver neither returned nor reached explicit rejection')
    after = {p: bytes(uc.mem_read(p, 0x1000)) for p in before}
    RUNS.append(dict(name=name, original=original, outcome=outcome[0],
                    game_base=hex(game), ordinal=ordinal, network_index=network_index,
                    cursor=cursor, instructions_executed=len(trace),
                    input_roster=hex(input_roster), payload_mapped=payload_mapped))
    return dict(uc=uc, artifact=artifact, before=before, after=after,
                reads=reads, writes=writes, trace=trace, outcome=outcome[0],
                payload=payload, cursor=cursor, ordinal=ordinal, original=original,
                input_roster=input_roster, start=start)


class NativeRosterReceiverTests(unittest.TestCase):
    def assert_registers_returned(self, result):
        uc = result['uc']
        self.assertEqual(result['outcome'], 'return')
        for name, expected in REGISTER_SEEDS.items():
            self.assertEqual(uc.reg_read(register(name)), expected, name)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RSP), ENTRY_RSP + 8)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RAX), result['cursor'] + 32)

    def assert_memory_success(self, result):
        ordinal, cursor = result['ordinal'], result['cursor']
        target = (result['input_roster'] + 0x3A8 if result['original'] else PROPERTY) + ordinal * 32
        expected = {p: bytearray(blob) for p, blob in result['before'].items()}

        def change(address, value):
            for offset, byte in enumerate(value):
                addr = address + offset
                expected[addr & ~0xFFF][addr & 0xFFF] = byte

        change(target, result['payload'])
        change(CURSOR, u32(cursor + 32))
        self.assertEqual(result['after'], {p: bytes(b) for p, b in expected.items()})
        nonstack = [(a, s) for a, s, v in result['writes'] if not STACK <= a < STACK + 0x10000]
        self.assertEqual(nonstack, [(target + i * 4, 4) for i in range(7)] +
                         [(CURSOR, 4), (target + 28, 4)])
        payload_reads = [(a, s) for a, s in result['reads'] if PAYLOAD <= a < PAYLOAD + 0x900]
        self.assertEqual(payload_reads, [(PAYLOAD + cursor + i * 4, 4) for i in range(8)])

    def assert_rejected(self, result, reason):
        uc = result['uc']
        self.assertEqual(result['outcome'], 'reject')
        self.assertEqual(result['before'], result['after'])
        self.assertEqual([(a, s) for a, s, v in result['writes']
                          if not STACK <= a < STACK + 0x10000], [])
        self.assertFalse(any(PAYLOAD <= a < PAYLOAD + 0x900 for a, s in result['reads']))
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_R10) & 0xFFFFFFFF, reason)
        expected_rax = ROSTER if reason == 2 else uc.reg_read(xr.UC_X86_REG_R8) // 32
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RAX), expected_rax)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RSP), ENTRY_RSP - 8)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RBP), PAYLOAD)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_R14), CURSOR)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_R11), result['input_roster'])
        self.assertEqual(bytes(uc.mem_read(ENTRY_RSP - 8, 8)), u64(REGISTER_SEEDS['r14']))
        self.assertEqual(bytes(uc.mem_read(ENTRY_RSP + 0x20, 8)), u64(REGISTER_SEEDS['rbp']))
        for name in ('rbx', 'rsi', 'rdi', 'r12', 'r13', 'r15'):
            self.assertEqual(uc.reg_read(register(name)), REGISTER_SEEDS[name], name)
        self.assertEqual(uc.reg_read(xr.UC_X86_REG_RCX), result['cursor'])
        self.assertIn(result['artifact']['trampoline_address'], result['trace'])
        self.assertNotIn(result['artifact']['resume_address'], result['trace'])

    def test_01_pinned_source_and_explicit_offline_contract(self):
        self.assertEqual(native.load_source(EVIDENCE_PATH), BODY)
        self.assertEqual(len(instructions(BODY, ENTRY)), 72)
        artifact = emit()
        self.assertEqual(artifact['source_sha256'], BODY_SHA)
        self.assertEqual(artifact['evidence_sha256'], EVIDENCE_SHA)
        self.assertEqual(artifact['status'], 'offline_native_candidate')
        for key in ('installable', 'game_execution', 'multiplayer_verified'):
            self.assertIs(artifact[key], False)
        self.assertIsNone(artifact['entry_or_callsite_patch'])
        self.assertEqual(artifact['size_bytes'], len(bytes.fromhex(artifact['code_hex'])))
        self.assertEqual(sha(bytes.fromhex(artifact['code_hex'])), artifact['code_sha256'])

    def test_02_all_eight_ordinals_against_original_at_high_aslr(self):
        permutation = [7, 0, 6, 1, 5, 2, 4, 3]
        for game in (DEFAULT_GAME, 0x0000700000000000):
            for ordinal, network in enumerate(permutation):
                with self.subTest(game=hex(game), ordinal=ordinal, network=network):
                    options = dict(ordinal=ordinal, network_index=network,
                                   cursor=4 + ordinal * 4, game=game)
                    old = emulate(name=f'original_{game:x}_{ordinal}', original=True, **options)
                    new = emulate(name=f'candidate_{game:x}_{ordinal}', **options)
                    for item in (old, new):
                        self.assert_registers_returned(item)
                        self.assert_memory_success(item)
                    old_record = bytes(old['uc'].mem_read(ROSTER + 0x3A8 + ordinal * 32, 32))
                    self.assertEqual(bytes(new['uc'].mem_read(PROPERTY + ordinal * 32, 32)), old_record)
                    self.assertEqual(struct.unpack_from('<I', old_record, 12)[0], network)
                    self.assertEqual(new['uc'].reg_read(xr.UC_X86_REG_R10),
                                     old['uc'].reg_read(xr.UC_X86_REG_R10))
                    self.assertIn(new['artifact']['code_address'] + SPLICE, new['trace'])
                    self.assertIn(new['artifact']['trampoline_address'], new['trace'])
                    self.assertIn(new['artifact']['resume_address'], new['trace'])

    def test_03_hash_collisions_full_probe_wrap_and_verbatim_network_dword(self):
        # Eight different keys share hash bucket 1. The last key needs all eight
        # probes including wrap from bucket 7 to bucket 0; ordinal is independent.
        buckets = [(0, 0xFFFFFFFF)] * 8
        for i in range(8):
            buckets[(1 + i) & 7] = (1 + i * 8, 7 - i)
        for original in (False, True):
            result = emulate(name=f'collision_full_wrap_{original}', original=original,
                             entity=57, ordinal=0, network_index=0xFEDCBA98,
                             cursor=0x120, buckets=buckets)
            self.assert_registers_returned(result)
            self.assert_memory_success(result)
            key_reads = [(a, s) for a, s in result['reads'] if BUCKETS <= a < BUCKETS + 64]
            self.assertEqual(key_reads, [(BUCKETS + ((1 + i) & 7) * 8, 4) for i in range(8)] +
                             [(BUCKETS + 4, 4)])

    def test_04_ordinal_guard_rejects_unsigned_values_without_payload_access(self):
        for ordinal in (8, 9, 255, 0x80000000, 0xFFFFFFFF):
            with self.subTest(ordinal=hex(ordinal)):
                result = emulate(name=f'bad_ordinal_{ordinal:x}', ordinal=ordinal,
                                 payload_mapped=False)
                self.assert_rejected(result, 1)
                self.assertEqual(result['uc'].reg_read(xr.UC_X86_REG_R8), ordinal * 32)

    def test_05_invalid_sentinel_empty_map_and_full_map_misses(self):
        scenarios = [
            dict(name='global_sentinel', entity=0xFFFFFFFF),
            dict(name='zero_capacity', capacity=0, buckets=[]),
            dict(name='empty_bucket_miss', buckets=[(0, 0xFFFFFFFF)] * 8),
            dict(name='full_map_miss', entity=65,
                 buckets=[(57, 3)] + [(1 + (i - 1) * 8, 2) for i in range(1, 8)]),
            dict(name='mapped_missing_sentinel', ordinal=0xFFFFFFFF),
        ]
        for options in scenarios:
            with self.subTest(name=options['name']):
                result = emulate(payload_mapped=False, **options)
                self.assert_rejected(result, 1)
                key_reads = [(a, s) for a, s in result['reads'] if BUCKETS <= a < BUCKETS + 64]
                if options['name'] == 'global_sentinel':
                    self.assertEqual(key_reads, [])
                if options['name'] == 'full_map_miss':
                    self.assertEqual(len(key_reads), 8)

    def test_06_wrong_readable_roster_binding_rejects_and_priority_is_ordinal(self):
        for ordinal, reason in ((3, 2), (0xFFFFFFFF, 1)):
            result = emulate(name=f'wrong_binding_{ordinal:x}', input_roster=WRONG_ROSTER,
                             ordinal=ordinal, payload_mapped=False)
            self.assert_rejected(result, reason)
            self.assertEqual(result['uc'].reg_read(xr.UC_X86_REG_R8), ordinal * 32)

    def test_07_native_branch_targets_and_only_intended_body_edits(self):
        artifact = emit()
        base = artifact['code_address']
        code = bytes.fromhex(artifact['code_hex'])
        expected = bytearray(BODY)
        expected[9:13] = struct.pack('<i', DEFAULT_GAME + SENTINEL - (base + 13))
        expected[SPLICE:RESUME] = b'\xe9' + struct.pack('<i', artifact['trampoline_address'] - (base + SPLICE + 5)) + b'\x90'
        self.assertEqual(code[:303], expected)
        self.assertEqual(code[303:artifact['trampoline_address'] - base], b'\xcc')
        source_ins = instructions(BODY, DEFAULT_GAME + ENTRY)
        rip = [(i, op) for i in source_ins for op in i.operands
               if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
        self.assertEqual(len(rip), 1)
        self.assertEqual(rip[0][0].address + rip[0][0].size + rip[0][1].mem.disp,
                         DEFAULT_GAME + SENTINEL)
        clone = {i.address - base: i for i in instructions(code[:303], base)}
        for old in source_ins:
            if old.group(capstone.CS_GRP_JUMP):
                offset = old.address - (DEFAULT_GAME + ENTRY)
                self.assertEqual(immediate_target(clone[offset]) - base,
                                 immediate_target(old) - (DEFAULT_GAME + ENTRY))
        patched_rip = next(op for op in clone[7].operands if op.type == X86_OP_MEM)
        self.assertEqual(base + 13 + patched_rip.mem.disp, DEFAULT_GAME + SENTINEL)
        self.assertEqual(immediate_target(clone[SPLICE]), artifact['trampoline_address'])
        tail = instructions(code[304:], base + 304)
        self.assertEqual([i.mnemonic for i in tail],
                         ['cmp', 'jae', 'movabs', 'cmp', 'jne', 'movabs', 'mov', 'lea',
                          'jmp', 'mov', 'jmp', 'mov', 'jmp'])
        self.assertEqual(immediate_target(tail[0]), 8)
        self.assertEqual(immediate_target(tail[1]), tail[9].address)
        self.assertEqual(immediate_target(tail[2]), ROSTER)
        self.assertEqual(immediate_target(tail[4]), tail[11].address)
        self.assertEqual(immediate_target(tail[5]), PROPERTY - 0x3A8)
        self.assertEqual(bytes(tail[6].bytes + tail[7].bytes), BODY[SPLICE:RESUME])
        self.assertEqual(immediate_target(tail[8]), base + RESUME)
        for branch in (tail[10], tail[12]):
            self.assertEqual(immediate_target(branch), artifact['reject_address'])
        self.assertEqual(immediate_target(tail[9]), 1)
        self.assertEqual(immediate_target(tail[11]), 2)

    def test_08_signed_rel32_exact_bounds_and_aligned_rip_build_bounds(self):
        next_ip = 0x0000400000000000
        for delta in (-(1 << 31), (1 << 31) - 1):
            self.assertEqual(native.rel32(next_ip, next_ip + delta), struct.pack('<i', delta))
        for delta in (-(1 << 31) - 1, 1 << 31):
            with self.assertRaises(ValueError):
                native.rel32(next_ip, next_ip + delta)
        target = DEFAULT_GAME + SENTINEL
        # 16-aligned clone bases make target-(code+13) congruent to 3 mod 16.
        for delta in (-(1 << 31) + 3, (1 << 31) - 13):
            code_address = target - 13 - delta
            artifact = emit(code_address=code_address, reject_address=code_address + 0x4000)
            self.assertEqual(struct.unpack('<i', bytes.fromhex(artifact['code_hex'])[9:13])[0], delta)
            # Execute the extreme accepted RIP relocation, not just its bytes.
            run = emulate(name=f'rip_boundary_{delta}', ordinal=7,
                          address_overrides=dict(code_address=code_address,
                                                 reject_address=code_address + 0x4000))
            self.assert_registers_returned(run)
            self.assert_memory_success(run)
        for delta in (-(1 << 31) - 13, (1 << 31) + 3):
            code_address = target - 13 - delta
            with self.assertRaises(ValueError):
                emit(code_address=code_address, reject_address=code_address + 0x4000)

    def test_09_both_actual_reject_branches_must_fit_rel32(self):
        initial = emit()
        base = initial['code_address']
        tail = instructions(bytes.fromhex(initial['code_hex'])[304:], base + 304)
        next_ips = [i.address + i.size for i in tail
                    if i.mnemonic == 'jmp' and immediate_target(i) == initial['reject_address']]
        self.assertEqual(len(next_ips), 2)
        lower = max(ip - (1 << 31) for ip in next_ips)
        upper = min(ip + (1 << 31) - 1 for ip in next_ips)
        for target in (lower, upper):
            with self.subTest(target=hex(target)):
                artifact = emit(reject_address=target)
                out = instructions(bytes.fromhex(artifact['code_hex'])[304:], base + 304)
                self.assertEqual([immediate_target(i) for i in out if i.address + i.size in next_ips], [target, target])
                for ordinal, roster, reason in ((8, ROSTER, 1), (3, WRONG_ROSTER, 2)):
                    run = emulate(name=f'reject_boundary_{target:x}_reason{reason}',
                                  ordinal=ordinal, input_roster=roster, payload_mapped=False,
                                  address_overrides=dict(reject_address=target))
                    self.assert_rejected(run, reason)
        for target in (lower - 1, upper + 1):
            with self.assertRaises(ValueError):
                emit(reject_address=target)

    def test_10_reject_changed_source_invalid_addresses_and_known_overlaps(self):
        for source in (BODY[:-1], BODY + b'\0', bytes([BODY[0] ^ 1]) + BODY[1:], bytearray(BODY)):
            with self.subTest(source_type=type(source).__name__, length=len(source)):
                with self.assertRaises(ValueError):
                    native.build(source, **parameters())
        invalid = [dict(game_base=DEFAULT_GAME + 1), dict(code_address=DEFAULT_GAME + 0x10000001),
                   dict(roster_address=ROSTER + 1), dict(property_address=PROPERTY + 1),
                   dict(property_address=0x3A0), dict(reject_address=0), dict(reject_address=True),
                   dict(roster_address=(1 << 47) - 8), dict(property_address=(1 << 47) - 8),
                   dict(code_address=(1 << 47) - 16), dict(game_base=1 << 47),
                   dict(property_address=ROSTER + 0x400), dict(property_address=DEFAULT_GAME + SENTINEL),
                   dict(code_address=DEFAULT_GAME + ENTRY), dict(reject_address=PROPERTY + 255),
                   dict(reject_address=DEFAULT_GAME + 0x10000001)]
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    emit(**changes)
        # The first byte immediately beyond either storage extent is not an
        # overlap, provided all other range/rel32 constraints also hold.
        self.assertEqual(emit(property_address=ROSTER + 0x428)['property_address'], ROSTER + 0x428)

    def test_11_candidate_and_evidence_did_not_change_during_run(self):
        self.assertEqual(MODULE_PATH.read_bytes(), MODULE_BYTES)
        self.assertEqual(sha(EVIDENCE_PATH.read_bytes()), EVIDENCE_SHA)


def write_report(result):
    report = {
        'status': 'passed' if result.wasSuccessful() else 'failed',
        'test_methods_run': result.testsRun,
        'failure_count': len(result.failures), 'error_count': len(result.errors),
        'failures': [{'test': str(test), 'traceback': trace} for test, trace in result.failures],
        'errors': [{'test': str(test), 'traceback': trace} for test, trace in result.errors],
        'source_sha256': {str(MODULE_PATH.relative_to(ROOT)): sha(MODULE_BYTES)},
        'test_sha256': sha(Path(__file__).read_bytes()),
        'evidence_sha256': {str(EVIDENCE_PATH.relative_to(ROOT.parent)): EVIDENCE_SHA},
        'original_body_sha256': BODY_SHA, 'original_size_bytes': len(BODY),
        'original_instruction_count': 72,
        'python_version': sys.version, 'unicorn_version': unicorn.__version__,
        'capstone_version': capstone.__version__,
        'fixture_synthetic': True, 'game_process_accessed': False,
        'host_native_code_executed': False, 'game_or_multiplayer_verified': False,
        'installable': False,
        'emulator_runs': RUNS,
        'verified_scope': [
            'Actual original and emitted x64 execution: eight ordinals and permuted network indexes at two high ASLR bases',
            'Nonzero cursor; exact eight DWORD stores; cursor increment; all mapped non-stack pages checked for unintended modifications',
            'Hash collisions, full probe wrap, empty/full map misses, global invalid sentinel and mapped invalid ordinal',
            'Unsigned ordinal and readable wrong-binding rejection before payload read or cursor/record write, with interior frame retained',
            'Success restores nonvolatile registers and caller RSP; original and clone outputs agree in oversized synthetic storage',
            'Native branch/RIP targets decoded independently, preserved source bytes and original internal branch destinations',
            'Exact signed rel32 edges, closest aligned RIP build edges, both rejection-jump range intersection and invalid inputs',
        ],
        'limits': [
            'All maps, roster objects, payloads, addresses and memory permissions are synthetic; no game or host-native execution',
            'Original ordinals 4..7 are comparison fixtures with oversized RAM, not evidence that original inline storage supports eight records',
            'Binding check occurs after native lookup; a wrong but readable roster is tested, not arbitrary invalid roster pointers',
            'Native lookup is preserved, including its existing header/key/sentinel semantics; map validity remains an integration precondition',
            'No payload length, source/destination alias, pointer lifetime, reentrancy, synchronization or allocation proof',
            'Reject hook stops at the explicit interior-frame continuation; no safe caller abort or cursor-recovery implementation is claimed',
            'No Windows unwind metadata, exception unwinding, hook installation, actual native callers or gameplay verification',
            'Other inline-array producers/consumers remain outside this receiver candidate and must migrate before integration',
        ],
    }
    destination = ROOT / 'verification' / 'native_roster_receiver_tests.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(destination), 'status': report['status'],
                      'test_methods_run': result.testsRun, 'emulator_runs': len(RUNS)}))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeRosterReceiverTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_report(result)
    raise SystemExit(0 if result.wasSuccessful() else 1)
