"""Exercise the actual LuaJIT owner-layout module using synthetic addresses.

Expected visit order comes from the hash-pinned native constructor/cleanup
projection, independently of the candidate Lua's lists. No game is accessed.
"""
import copy
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.test-deps'))
from lupa.luajit21 import LuaRuntime
import lupa

SOURCES = [ROOT / 'Source' / n for n in ('pool_preflight.lua', 'pool_owner_layout.lua', 'pool_snapshot.lua')]
EVIDENCE_DIR = ROOT.parent / 'five_player_feasibility_20260927'
EVIDENCE_SHAS = {
    'indexed_float_pool_lifecycle_inventory_evidence.json': '7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6',
    'indexed_float_subobjects_evidence.json': '5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
}
D, SIDECAR, PTR_END = 0x10000000000, 0x20000000000, 1 << 47


def qword(value):
    return struct.pack('<Q', value)


class OwnerLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = {}
        for name, digest in EVIDENCE_SHAS.items():
            raw = (EVIDENCE_DIR / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise AssertionError('evidence mismatch: ' + name)
            cls.evidence[name] = json.loads(raw)
        cls.inventory = cls.evidence['indexed_float_pool_lifecycle_inventory_evidence.json']
        cls.storage = cls.evidence['indexed_float_subobjects_evidence.json']['storage']

    def setUp(self):
        self.rt = LuaRuntime(encoding=None, unpack_returned_tuples=True)
        self.preflight = self.rt.execute(SOURCES[0].read_bytes())
        self.module = self.rt.execute(SOURCES[1].read_bytes())(self.preflight)

    def lua(self, value):
        if isinstance(value, dict):
            return self.rt.table_from({self.lua(k): self.lua(v) for k, v in value.items()})
        if isinstance(value, list):
            return self.rt.table_from([self.lua(v) for v in value])
        if isinstance(value, str):
            return value.encode()
        return value

    def config(self, count=4, relocated=False, d=D):
        return dict(version=dict(self.preflight.target().items()), d_address=qword(d),
                    player_records=dict(count=count, base=qword(SIDECAR if relocated else d + 0x80E18)))

    def expected(self, count=4, relocated=False, d=D, sidecar=SIDECAR):
        # These are addresses produced by actual pinned constructor/cleanup
        # instruction projections; no duplicate candidate offset list here.
        name = 'eight_sidecar_hypothetical' if count == 8 else 'original'
        scenario = self.inventory['scenarios'][name]
        constructor = [int(r['S'], 16) for r in scenario['constructor_visits']]
        cleanup = [int(r['S'], 16) for r in scenario['cleanup_visits']]
        self.assertEqual(constructor, cleanup)
        original = 0x10080E18
        translated = []
        for value in constructor:
            if count == 8 and 0x40000000 <= value < 0x40000000 + 8 * 0x298:
                translated.append(sidecar + value - 0x40000000)
            elif relocated and original <= value < original + 4 * 0x298:
                translated.append(sidecar + value - original)
            else:
                translated.append(d + value - 0x10000000)
        return translated

    def packet(self, count=4, relocated=False, d=D):
        return dict(version=dict(self.preflight.target().items()), d_address=qword(d),
                    owners=[dict(address=qword(a), bytes=bytes(0x78))
                            for a in self.expected(count, relocated, d)])

    def plan(self, config, status='known_owner_layout'):
        result = self.module.plan(self.lua(config))
        self.assertEqual(result[b'status'], status.encode())
        self.assertFalse(result[b'executable'])
        return result

    def coverage(self, config, packet, status='known_owner_addresses_complete'):
        result = self.module.check_coverage(self.lua(config), self.lua(packet))
        self.assertEqual(result[b'status'], status.encode())
        self.assertFalse(result[b'executable'])
        return result

    @staticmethod
    def addresses(result):
        owners = result[b'owners']
        return [struct.unpack('<Q', owners[i][b'address'])[0] for i in range(1, len(owners) + 1)]

    def test_01_original_305_order_matches_constructor_and_cleanup(self):
        result = self.plan(self.config())
        self.assertEqual(self.addresses(result), self.expected())
        self.assertEqual((result[b'known_owner_count'], result[b'fixed_owner_count'], result[b'player_owner_count']),
                         (305, 285, 20))
        self.assertEqual(len(result[b'retired_player_owners']), 0)
        for i, value in enumerate(self.expected(), 1):
            self.assertEqual(result[b'owners'][i][b'key'], f'{value:016x}'.encode())

    def test_02_eight_sidecar_325_order_matches_pinned_projection(self):
        result = self.plan(self.config(8, True))
        self.assertEqual(self.addresses(result), self.expected(8, True))
        self.assertEqual((result[b'known_owner_count'], result[b'fixed_owner_count'], result[b'player_owner_count']),
                         (325, 285, 40))
        self.assertEqual(result[b'player_records'][b'size'], 8 * int(self.storage['record_stride'], 16))
        self.assertEqual(len(result[b'retired_player_owners']), 20)
        self.assertTrue(result[b'player_records'][b'relocated'])

    def test_03_eight_adds_only_twenty_player_S_and_preserves_fixed_order(self):
        four, eight = self.plan(self.config(4, True)), self.plan(self.config(8, True))
        def by_kind(result, kind):
            return [result[b'owners'][i][b'address'] for i in range(1, len(result[b'owners']) + 1)
                    if result[b'owners'][i][b'kind'] == kind]
        self.assertEqual(by_kind(four, b'fixed'), by_kind(eight, b'fixed'))
        self.assertEqual(by_kind(four, b'player'), by_kind(eight, b'player')[:20])
        self.assertEqual(len(set(by_kind(eight, b'player')) - set(by_kind(four, b'player'))), 20)

    def test_04_double_group_all_forty_ignores_active_counter_hints(self):
        config = self.config(8, True)
        config['active_counts'] = {'array_8b748': 0}
        result = self.plan(config)
        actual = [struct.unpack('<Q', result[b'owners'][i][b'address'])[0]
                  for i in range(1, len(result[b'owners']) + 1)
                  if result[b'owners'][i][b'group'] == b'array_8b748']
        evidence_group = next(f for f in self.inventory['scenarios']['original']['families']
                              if f['name'] == 'array_8b748')
        self.assertEqual(len(actual), 40)
        # The full order is already checked against evidence in tests 1/2;
        # here confirm count-zero caller hints cannot remove the group.
        self.assertEqual(set(actual), {a for a in self.expected() if D + 0x8B748 <= a < D + 0x8D538})
        self.assertEqual(evidence_group['records'], 20)
        self.assertEqual(actual, [D + int(a, 16) - 0x10000000 for a in evidence_group['members']])
        packet = self.packet(8, True)
        packet['owners'] = [o for o in packet['owners'] if struct.unpack('<Q', o['address'])[0] not in set(actual)]
        missing = self.coverage(config, packet, 'missing_known_owner')
        self.assertEqual(missing[b'missing_owner_count'], 40)

    def test_05_original_eight_and_partial_original_span_rejected(self):
        self.plan(self.config(8), 'original_storage_requires_four_records')
        config = self.config(4, True)
        config['player_records']['base'] = qword(D + 0x80E18 + 8)
        self.plan(config, 'region_overlap')

    def test_06_whole_record_tail_gap_cannot_overlap_fixed_S(self):
        # Last player S ends eight bytes before the whole record span ends.
        # All player S could fit before this singleton while the last 8 bytes
        # of the record would overwrite it; validate the WHOLE record span.
        config = self.config(4, True)
        config['player_records']['base'] = qword(D + 0x80DA0 + 8 - 4 * 0x298)
        result = self.plan(config, 'region_overlap')
        self.assertEqual(result[b'field'], b'singleton_80da0:0:0')

    def test_07_descriptor_nodes_bitmap_and_metadata_are_protected(self):
        for offset, label in ((0x36F8, b'pool_descriptor'), (0x3718, b'original_pool_nodes'),
                              (0x23F18, b'original_pool_occupancy'),
                              (0x8D6C8, b'original_player_metadata_a'),
                              (0x8D6D8, b'original_player_metadata_b')):
            with self.subTest(offset=hex(offset)):
                config = self.config(8, True)
                config['player_records']['base'] = qword(D + offset)
                result = self.plan(config, 'region_overlap')
                self.assertEqual(result[b'field'], label)

    def test_08_address_type_alignment_and_canonical_end(self):
        for value in (b'', b'0' * 7, D, qword(0), qword(D + 1), qword(PTR_END), qword((1 << 64) - 8)):
            with self.subTest(value=value):
                config = self.config()
                config['d_address'] = value
                self.plan(config, 'unsupported_address')
                config = self.config(8, True)
                config['player_records']['base'] = value
                self.plan(config, 'unsupported_address')
        config = self.config(4, True)
        config['player_records']['base'] = qword(PTR_END - 4 * 0x298)
        self.plan(config)
        config['player_records']['base'] = qword(PTR_END - 4 * 0x298 + 8)
        self.plan(config, 'unsupported_address')
        config = self.config(d=PTR_END - 0x1000)
        self.plan(config, 'unsupported_address')

    def test_09_version_gate_for_config_and_packet(self):
        for field in (b'build', b'exe_sha256', b'game_dll_sha256'):
            config = self.config()
            config['version'][field] = 0
            self.plan(config, 'version_mismatch')
            packet = self.packet()
            packet['version'][field] = 0
            self.coverage(self.config(), packet, 'version_mismatch')

    def test_10_record_count_is_four_or_eight_only(self):
        for count in (0, 1, 5, 7, 9, 4.1, '4', True, float('nan')):
            config = self.config()
            config['player_records']['count'] = count
            self.plan(config, 'unsupported_record_count')

    def test_11_complete_addresses_accept_packet_order_independently(self):
        for count, relocated in ((4, False), (4, True), (8, True)):
            packet = self.packet(count, relocated)
            packet['owners'].reverse()
            result = self.coverage(self.config(count, relocated), packet)
            self.assertEqual((result[b'expected_owner_count'], result[b'extra_owner_count']),
                             (285 + count * 5, 0))
            self.assertFalse(result[b'bytes_validated'])
            self.assertTrue(result[b'requires_snapshot_validation'])

    def test_12_missing_known_owner_reports_exact_identity(self):
        packet = self.packet(8, True)
        missing = packet['owners'].pop(23)
        result = self.coverage(self.config(8, True), packet, 'missing_known_owner')
        self.assertEqual(result[b'missing_owner_count'], 1)
        self.assertEqual(result[b'missing_owner_keys'][1], f'{struct.unpack("<Q", missing["address"])[0]:016x}'.encode())

    def test_13_duplicates_rejected_for_known_and_extra_owners(self):
        for extra in (False, True):
            packet = self.packet()
            if extra:
                packet['owners'].append(dict(address=qword(SIDECAR)))
            packet['owners'].append(copy.deepcopy(packet['owners'][-1]))
            self.coverage(self.config(), packet, 'duplicate_owner')

    def test_14_relocated_layout_rejects_each_old_player_S_copy(self):
        old_players = self.expected()[1:21]
        for old in old_players:
            with self.subTest(address=hex(old)):
                packet = self.packet(8, True)
                packet['owners'].append(dict(address=qword(old), bytes=bytes(0x78)))
                self.coverage(self.config(8, True), packet, 'retired_player_owner')
        packet = self.packet(8, True)
        packet['owners'].append(dict(address=qword(D + 0x80E18 + 8)))
        self.coverage(self.config(8, True), packet, 'retired_player_storage_overlap')

    def test_15_extras_are_listed_but_their_payloads_are_not_validated(self):
        packet = self.packet(8, True)
        extra = SIDECAR + 0x100000
        packet['owners'].append(dict(address=qword(extra), bytes=b'invalid S bytes'))
        packet['owners'][0]['bytes'] = False
        result = self.coverage(self.config(8, True), packet)
        self.assertEqual((result[b'supplied_owner_count'], result[b'extra_owner_count']), (326, 1))
        self.assertEqual(result[b'extra_owner_keys'][1], f'{extra:016x}'.encode())
        self.assertFalse(result[b'bytes_validated'])
        self.assertTrue(result[b'requires_snapshot_validation'])

    def test_16_packet_D_mismatch_and_bad_owner_addresses(self):
        packet = self.packet()
        packet['d_address'] = qword(D + 8)
        self.coverage(self.config(), packet, 'd_address_mismatch')
        for address in (qword(PTR_END), qword(D + 1), qword(0), b'bad', qword(PTR_END - 8)):
            packet = self.packet()
            packet['owners'][0]['address'] = address
            self.coverage(self.config(), packet, 'unsupported_address')

    def test_17_inputs_and_results_do_not_share_mutable_layout_state(self):
        config = self.config(8, True)
        packet = self.packet(8, True)
        before = copy.deepcopy((config, packet))
        r = self.plan(config)
        r[b'owners'][1][b'address'] = qword(8)
        r[b'version'][b'build'] = 0
        r[b'retired_player_owners'][1][b'key'] = b'changed'
        r2 = self.plan(config)
        self.assertEqual(self.addresses(r2), self.expected(8, True))
        self.coverage(config, packet)
        self.assertEqual((config, packet), before)

    def test_18_plain_tables_dense_arrays_and_owner_budget(self):
        config = self.lua(self.config())
        self.rt.eval(b'function(t) return setmetatable(t,{}) end')(config)
        self.assertEqual(self.module.plan(config)[b'status'], b'invalid_input')
        for owners in ({2: {'address': qword(D)}}, {1: {'address': qword(D)}, 'extra': {}},
                       [dict(address=qword(SIDECAR + i * 0x78)) for i in range(4097)]):
            packet = self.packet()
            packet['owners'] = owners
            self.coverage(self.config(), packet, 'invalid_input')
        packet = self.lua(self.packet())
        self.rt.eval(b'function(t) return setmetatable(t,{}) end')(packet[b'owners'][1])
        self.assertEqual(self.module.check_coverage(self.lua(self.config()), packet)[b'status'], b'invalid_input')

    def test_19_unknown_D_fields_are_not_claimed_to_be_protected(self):
        config = self.config(4, True)
        # This unused test address falls between known pinned regions. Its
        # acceptance is address arithmetic only, not an allocation guarantee.
        config['player_records']['base'] = qword(D + 0x40000)
        result = self.plan(config)
        self.assertIn(b'finite protected ranges only', result[b'scope'])
        self.assertIn(b'no mapped storage', result[b'scope'])
        self.assertFalse(result[b'executable'])

    def test_20_full_inventory_connects_to_snapshot_and_detects_bad_pool_pointer(self):
        snapshot = self.rt.execute(SOURCES[2].read_bytes())(self.preflight)
        for count, relocated in ((4, False), (8, True)):
            with self.subTest(count=count):
                config = self.config(count, relocated)
                planned = self.plan(config)
                descriptor = bytearray(0x20)
                struct.pack_into('<QQIII', descriptor, 0, D + 0x3718, D + 0x23F18, 0, 256, 0)
                packet = dict(version=copy.deepcopy(config['version']), d_address=qword(D),
                              game_base=qword(0x7FF814A30000), descriptor=bytes(descriptor),
                              nodes=bytes(256 * 0x208), occupancy=bytes(256), templates=[], owners=[])
                for i in range(1, len(planned[b'owners']) + 1):
                    blob = bytearray(0x78)
                    struct.pack_into('<QQQIIQ', blob, 0, D + 0x300000, D, D + 0x400000, 0, 0, D + 0x36F8)
                    blob[0x5C] = blob[0x74] = blob[0x75] = 1
                    packet['owners'].append(dict(address=planned[b'owners'][i][b'address'], bytes=bytes(blob)))
                coverage = self.coverage(config, packet)
                self.assertFalse(coverage[b'bytes_validated'])
                checked = snapshot.validate(self.lua(packet))
                self.assertEqual(checked[b'status'], b'consistent_supplied_bytes')
                self.assertEqual(len(checked[b'snapshot'][b'owners']), 285 + count * 5)
                self.assertFalse(checked[b'executable'])
                # Address identities are still complete after this corruption.
                # The separate S-byte validator must reject the wrong P value.
                bad = bytearray(packet['owners'][20]['bytes'])
                struct.pack_into('<Q', bad, 0x20, D + 0x36F8 + 8)
                packet['owners'][20]['bytes'] = bytes(bad)
                self.assertFalse(self.coverage(config, packet)[b'bytes_validated'])
                checked = snapshot.validate(self.lua(packet))
                self.assertEqual(checked[b'status'], b'owner_pool_mismatch')
                self.assertFalse(checked[b'executable'])

    def test_21_extra_owner_cannot_cross_selected_player_storage_edges(self):
        # The front extra ends exactly at the first known S, covering the
        # record header without overlapping that S. The tail extra starts
        # exactly where the last known S ends and covers the final 8 bytes.
        # Check the whole selected storage for original four and sidecars.
        for count, relocated in ((4, False), (4, True), (8, True)):
            config = self.config(count, relocated)
            base = struct.unpack('<Q', config['player_records']['base'])[0]
            for extra in (base - 0x50, base + count * 0x298 - 8):
                with self.subTest(count=count, relocated=relocated, extra=hex(extra)):
                    packet = self.packet(count, relocated)
                    self.coverage(config, packet)
                    packet['owners'].append(dict(address=qword(extra), bytes=bytes(0x78)))
                    result = self.coverage(config, packet, 'player_storage_overlap')
                    self.assertEqual(result[b'field'], f'{extra:016x}'.encode())

    def test_22_extra_owner_exactly_outside_sidecar_edges_remains_allowed(self):
        for count in (4, 8):
            for extra in (SIDECAR - 0x78, SIDECAR + count * 0x298):
                with self.subTest(count=count, extra=hex(extra)):
                    packet = self.packet(count, True)
                    packet['owners'].append(dict(address=qword(extra)))
                    result = self.coverage(self.config(count, True), packet)
                    self.assertEqual(result[b'extra_owner_count'], 1)

    def test_23_storage_gap_overlap_requires_layout_check_beyond_snapshot(self):
        # pool_snapshot knows supplied S/P/N ranges, not the surrounding player
        # record header/tail. Demonstrate that these two validators complement
        # each other: valid S bytes can still overlap non-S player storage.
        snapshot = self.rt.execute(SOURCES[2].read_bytes())(self.preflight)
        for extra in (SIDECAR - 0x50, SIDECAR + 8 * 0x298 - 8):
            with self.subTest(extra=hex(extra)):
                config = self.config(8, True)
                packet = self.packet(8, True)
                descriptor = bytearray(0x20)
                struct.pack_into('<QQIII', descriptor, 0, D + 0x3718, D + 0x23F18, 0, 256, 0)
                packet.update(game_base=qword(0x7FF814A30000), descriptor=bytes(descriptor),
                              nodes=bytes(256 * 0x208), occupancy=bytes(256), templates=[])
                packet['owners'].append(dict(address=qword(extra)))
                for owner in packet['owners']:
                    blob = bytearray(0x78)
                    struct.pack_into('<QQQIIQ', blob, 0, D + 0x300000, D, D + 0x400000, 0, 0, D + 0x36F8)
                    owner['bytes'] = bytes(blob)
                checked = snapshot.validate(self.lua(packet))
                self.assertEqual(checked[b'status'], b'consistent_supplied_bytes')
                self.assertFalse(checked[b'executable'])
                self.coverage(config, packet, 'player_storage_overlap')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OwnerLayoutTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), python=sys.version,
        python_executable=sys.executable, lupa_version=lupa.__version__, lua_runtime=LuaRuntime().lua_implementation,
        source_sha256={str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES},
        test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), evidence_sha256=EVIDENCE_SHAS,
        expected_address_origin='Pinned constructor and cleanup instruction projections, translated to synthetic D/sidecar addresses.',
        game_process_access=False, game_execution=False, mod_installed=False,
        limitations=['Finite known layout and address coverage only; no mapped storage or full D allocation proof.',
                     'Coverage does not validate S bytes, unique node ownership, all external aliases, synchronization or live origin.',
                     'No memory collector, allocator, native executor, game integration or multiplayer acceptance.'])
    folder = ROOT / 'verification'
    folder.mkdir(exist_ok=True)
    (folder / 'pool_owner_layout_tests.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
