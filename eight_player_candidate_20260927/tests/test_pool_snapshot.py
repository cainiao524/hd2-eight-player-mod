"""Validate synthetic P/S/N/template bytes using the actual LuaJIT modules.

This is not a heap capture or execution of native HD2 code. The fixture's
addresses, context values and payloads are synthetic; layout and selected
template counts/types/events come from hash-pinned, previously reviewed files.
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

SOURCES = [ROOT / 'Source' / name for name in ('pool_preflight.lua', 'pool_snapshot.lua')]
EVIDENCE_DIR = ROOT.parent / 'five_player_feasibility_20260927'
EVIDENCE_SHAS = {
    'indexed_float_subobjects_evidence.json': '5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
    'indexed_float_pool_triple_members_evidence_v3.json': '7a5b7ef002c671d698edd6c663b791a7306eda2b09a238b5d8f187393c04bd60',
    'indexed_float_template_budget_evidence.json': '575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
}
D = 0x0000010000000000
GAME = 0x00007FF814A30000
P = D + 0x36F8
TEMPLATES = GAME + 0x3492F20
NODE_SIZE, S_SIZE, TEMPLATE_SIZE, ELEMENT_SIZE = 0x208, 0x78, 0xA0E8, 0xD68


def qword(value):
    return struct.pack('<Q', value)


def put(buffer, offset, value, fmt='<I'):
    """Return a changed byte string; never edit Lua or original fixture storage."""
    data = bytearray(buffer)
    struct.pack_into(fmt, data, offset, value)
    return bytes(data)


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence = {}
        for name, expected in EVIDENCE_SHAS.items():
            raw = (EVIDENCE_DIR / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise AssertionError(f'evidence mismatch: {name}')
            evidence[name] = json.loads(raw)
        cls.layout = evidence['indexed_float_subobjects_evidence.json']['storage']
        cls.templates = {}
        triple = evidence['indexed_float_pool_triple_members_evidence_v3.json']
        for key, value in triple['template_emissions'].items():
            cls.templates[int(key, 16)] = list(zip(value['types'], value['events']))
        budget = evidence['indexed_float_template_budget_evidence.json']
        cls.templates[0x1B] = [(n['type'], n['events']) for n in budget['emission_blocks']['0x1b']['nodes']]

    def setUp(self):
        # Binary strings must not be implicitly decoded as UTF-8 by Python.
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

    def fixture(self, capacity=6, reverse=False, partial=False, unlisted=0):
        ids = [0x28, 0x1C, 0x2E] if reverse else [0x24, 0x1B, 0x2D]
        template_blobs = []
        for identifier, elements in sorted(self.templates.items()):
            blob = bytearray(TEMPLATE_SIZE)
            struct.pack_into('<I', blob, 0xA0E0, len(elements))
            for ordinal, (typ, events) in enumerate(elements):
                struct.pack_into('<I', blob, ordinal * ELEMENT_SIZE, typ)
                struct.pack_into('<I', blob, ordinal * ELEMENT_SIZE + 0xD64, events)
            template_blobs.append(dict(id=identifier, bytes=bytes(blob)))
        nodes, bitmap, owners = bytearray(capacity * NODE_SIZE), bytearray(capacity), []
        used = 0
        for owner_index, identifier in enumerate(ids):
            count = len(self.templates[identifier]) - int(partial and owner_index == 0)
            owner = bytearray(S_SIZE)
            struct.pack_into('<QQQIIQ', owner, 0, D + 0x300000, D, D + 0x400000,
                             0x12345678 + owner_index, identifier, P)
            struct.pack_into('<I', owner, 0x58, count)
            owner[0x5C] = owner[0x74] = owner[0x75] = 1
            for ordinal in range(count):
                struct.pack_into('<I', owner, 0x28 + ordinal * 4, used)
                start = used * NODE_SIZE
                nodes[start:start + 0x1C] = owner[:0x1C]
                struct.pack_into('<QI', nodes, start + 0x20,
                                 TEMPLATES + identifier * TEMPLATE_SIZE + ordinal * ELEMENT_SIZE,
                                 self.templates[identifier][ordinal][0])
                bitmap[used] = 1
                used += 1
            owners.append(dict(address=qword(D + 0x80DA0 + owner_index * 0x80), bytes=bytes(owner)))
        for _ in range(unlisted):
            start = used * NODE_SIZE
            struct.pack_into('<QQQI', nodes, start, D + 0x500000, D, D + 0x600000, 0xFACE)
            struct.pack_into('<QI', nodes, start + 0x20, TEMPLATES + 0x29 * TEMPLATE_SIZE, 2)
            bitmap[used] = 1
            used += 1
        descriptor = bytearray(0x20)
        struct.pack_into('<QQIII', descriptor, 0, D + 0x3718,
                         D + 0x3718 + capacity * NODE_SIZE, used, capacity, 0)
        return dict(version=dict(self.preflight.target().items()), d_address=qword(D), game_base=qword(GAME),
                    descriptor=bytes(descriptor), nodes=bytes(nodes), occupancy=bytes(bitmap),
                    owners=owners, templates=template_blobs)

    def ops(self, packet, reverse=False):
        keys = [f'{struct.unpack("<Q", s["address"])[0]:016x}' for s in packet['owners']]
        changes = [(0, 0x24), (2, 0x2D), (1, 0x1B), (2, 0x2D), (0, 0x24)] if reverse else [
            (1, 0x1C), (2, 0x2E), (0, 0x28)]
        return [dict(owner=keys[i], template_id=t) for i, t in changes]

    def validate(self, packet):
        return self.module.validate(self.lua(packet))

    def expect_status(self, packet, status):
        result = self.validate(packet)
        self.assertEqual(result[b'status'], status.encode())
        self.assertFalse(result[b'executable'])
        return result

    def change_owner(self, packet, index, offset, value, fmt='<I'):
        packet['owners'][index]['bytes'] = put(packet['owners'][index]['bytes'], offset, value, fmt)

    def change_template(self, packet, identifier, offset, value):
        t = next(t for t in packet['templates'] if t['id'] == identifier)
        t['bytes'] = put(t['bytes'], offset, value)

    def test_01_binary_to_plan_preserves_both_transition_peaks(self):
        for reverse, shortage_step in ((False, 2), (True, 1)):
            for capacity in (5, 6):
                with self.subTest(reverse=reverse, capacity=capacity):
                    p = self.fixture(capacity, reverse)
                    checked = self.expect_status(p, 'consistent_supplied_bytes')
                    audit = checked[b'audit']
                    self.assertEqual((audit[b'occupied_nodes'], audit[b'claimed_nodes']), (5, 5))
                    self.assertTrue(audit[b'all_occupied_nodes_accounted'])
                    r = self.module.validate_and_plan(self.lua(p), self.lua(self.ops(p, reverse)))
                    self.assertEqual(r[b'status'], b'fits' if capacity == 6 else b'insufficient_capacity')
                    self.assertEqual((r[b'peak_required'], r[b'final_used']), (6, 5))
                    self.assertFalse(r[b'executable'])
                    self.assertEqual(r[b'state_semantics'], b'full_allocation_plan_not_native_post_state')
                    if capacity == 5:
                        self.assertEqual(r[b'first_shortage_step'], shortage_step)

    def test_02_unlisted_occupied_nodes_are_validated_and_remain_in_budget(self):
        p = self.fixture(unlisted=1)
        r = self.module.validate_and_plan(self.lua(p), self.lua(self.ops(p)))
        self.assertEqual((r[b'status'], r[b'peak_required'], r[b'unlisted_owner_nodes']),
                         (b'insufficient_capacity', 7, 1))
        self.assertEqual(r[b'snapshot_audit'][b'unclaimed_occupied_nodes'], 1)
        self.assertFalse(r[b'snapshot_audit'][b'all_occupied_nodes_accounted'])
        p['templates'] = [t for t in p['templates'] if t['id'] != 0x29]
        self.expect_status(p, 'missing_template')

    def test_03_partial_same_id_requires_recovery_but_different_id_releases_actual_count(self):
        p = self.fixture(partial=True)
        c = self.expect_status(p, 'consistent_supplied_bytes')
        key = c[b'snapshot'][b'owners'][1][b'key']
        self.assertEqual(c[b'audit'][b'partial_owners'][1], key)
        for identifier, expected in ((0x24, b'partial_same_id_requires_recovery'), (0x28, b'fits')):
            r = self.module.validate_and_plan(self.lua(p), self.lua([dict(owner=key, template_id=identifier)]))
            self.assertEqual(r[b'status'], expected)
            if identifier == 0x28:
                self.assertEqual((r[b'steps'][1][b'released'], r[b'final_used']), (2, 4))

    def test_04_used_must_match_whole_bitmap(self):
        p = self.fixture()
        p['descriptor'] = put(p['descriptor'], 0x10, 4)
        self.expect_status(p, 'occupancy_used_mismatch')
        p['descriptor'] = put(p['descriptor'], 0x10, 7)
        self.expect_status(p, 'invalid_used')

    def test_05_duplicate_indices_within_and_between_owners_are_rejected(self):
        for owner, offset, slot in ((0, 0x2C, 0), (1, 0x28, 0)):
            with self.subTest(owner=owner):
                p = self.fixture()
                self.change_owner(p, owner, offset, slot)
                self.expect_status(p, 'duplicate_node_index')

    def test_06_index_must_point_to_an_occupied_in_range_node(self):
        for slot, status in ((6, 'index_out_of_range'), (0xFFFFFFFF, 'index_out_of_range'),
                             (5, 'index_points_to_free_node')):
            p = self.fixture()
            self.change_owner(p, 0, 0x28, slot)
            self.expect_status(p, status)

    def test_07_owner_pool_d_and_node_context_relationships(self):
        for offset, value, status in ((8, D + 8, 'owner_context_mismatch'),
                                     (0x20, P + 8, 'owner_pool_mismatch')):
            p = self.fixture()
            self.change_owner(p, 0, offset, value, '<Q')
            self.expect_status(p, status)
        p = self.fixture()
        p['nodes'] = put(p['nodes'], 8, D + 8, '<Q')
        self.expect_status(p, 'node_owner_context_mismatch')
        for offset, fmt in ((0, '<Q'), (0x10, '<Q'), (0x18, '<I')):
            p = self.fixture()
            p['nodes'] = put(p['nodes'], offset, 123, fmt)
            self.expect_status(p, 'node_context_mismatch')

    def test_08_template_pointer_type_and_element_identity(self):
        for pointer in (0, TEMPLATES - 1, TEMPLATES + 73 * TEMPLATE_SIZE,
                        TEMPLATES + 0x24 * TEMPLATE_SIZE + 1,
                        TEMPLATES + 0x24 * TEMPLATE_SIZE + 3 * ELEMENT_SIZE,
                        TEMPLATES + 0x24 * TEMPLATE_SIZE + 0xA0E0):
            p = self.fixture()
            p['nodes'] = put(p['nodes'], 0x20, pointer, '<Q')
            self.expect_status(p, 'invalid_template_pointer')
        p = self.fixture()
        p['nodes'] = put(p['nodes'], 0x28, 1)
        self.expect_status(p, 'node_type_mismatch')
        for pointer in (TEMPLATES + 0x25 * TEMPLATE_SIZE,
                        TEMPLATES + 0x24 * TEMPLATE_SIZE + ELEMENT_SIZE):
            p = self.fixture()
            p['nodes'] = put(p['nodes'], 0x20, pointer, '<Q')
            self.expect_status(p, 'owner_template_mismatch')

    def test_09_truncation_never_reaches_unchecked_decode(self):
        for field in ('descriptor', 'nodes', 'occupancy'):
            p = self.fixture()
            p[field] = p[field][:-1]
            self.expect_status(p, 'invalid_length')
        for array in ('owners', 'templates'):
            p = self.fixture()
            p[array][0]['bytes'] = p[array][0]['bytes'][:-1]
            self.expect_status(p, 'invalid_length')
        p = self.fixture()
        p['d_address'] = p['d_address'][:-1]
        self.expect_status(p, 'invalid_input')

    def test_10_capacity_cursor_and_pointer_bounds(self):
        for capacity in (0, 4097, 0xFFFFFFFF):
            p = self.fixture()
            p['descriptor'] = put(p['descriptor'], 0x14, capacity)
            self.expect_status(p, 'unsupported_capacity')
        p = self.fixture()
        p['descriptor'] = put(p['descriptor'], 0x18, 6)
        self.expect_status(p, 'invalid_cursor')
        for field, value in (('d_address', 0), ('d_address', D + 1),
                             ('game_base', 1 << 47), ('game_base', (1 << 47) - 8)):
            p = self.fixture()
            p[field] = qword(value)
            self.expect_status(p, 'unsupported_address')
        for offset, value in ((0, 0), (0, D + 1), (0, (1 << 47) - 8), (8, 0)):
            p = self.fixture()
            p['descriptor'] = put(p['descriptor'], offset, value, '<Q')
            self.expect_status(p, 'unsupported_address')

    def test_11_duplicate_and_overlapping_memory_ranges(self):
        p = self.fixture()
        p['owners'][1]['address'] = p['owners'][0]['address']
        self.expect_status(p, 'duplicate_owner')
        for address in (D + 0x80DA8, P, D + 0x3718, TEMPLATES):
            p = self.fixture()
            p['owners'][1]['address'] = qword(address)
            self.expect_status(p, 'region_overlap')
        p = self.fixture()
        p['descriptor'] = put(p['descriptor'], 8, D + 0x3718, '<Q')
        self.expect_status(p, 'region_overlap')
        p = self.fixture()
        p['owners'][1]['address'] = qword(1 << 47)
        self.expect_status(p, 'unsupported_address')

    def test_12_missing_template_for_requested_zero_active_owner_is_not_zero_cost(self):
        p = self.fixture()
        self.change_owner(p, 0, 0x1C, 0x30)
        self.change_owner(p, 0, 0x58, 0)
        self.expect_status(p, 'missing_template')

    def test_13_inactive_index_bytes_are_ignored_and_cursor_can_be_nonzero(self):
        p = self.fixture()
        for owner in p['owners']:
            count = struct.unpack_from('<I', owner['bytes'], 0x58)[0]
            for i in range(count, 12):
                owner['bytes'] = put(owner['bytes'], 0x28 + i * 4, 0xFFFFFFFF)
        p['descriptor'] = put(p['descriptor'], 0x18, 4)
        self.expect_status(p, 'consistent_supplied_bytes')

    def test_14_stale_free_node_and_unrecognized_occupancy_are_not_ordinary_free_space(self):
        p = self.fixture()
        p['nodes'] = put(p['nodes'], 5 * NODE_SIZE + 0x20, TEMPLATES, '<Q')
        self.expect_status(p, 'stale_free_node')
        p = self.fixture()
        p['occupancy'] = bytes([2]) + p['occupancy'][1:]
        self.expect_status(p, 'unsupported_occupancy_byte')

    def test_15_template_counts_events_types_and_zero_id_policy(self):
        for offset, value, status in ((0xA0E0, 13, 'unsupported_template_count'),
                                     (0xD64, 11, 'invalid_event_count'),
                                     (0, 0, 'unsupported_node_type'), (0, 5, 'unsupported_node_type')):
            p = self.fixture()
            self.change_template(p, 0x24, offset, value)
            self.expect_status(p, status)
        p = self.fixture()
        zero = dict(id=0, bytes=bytes(TEMPLATE_SIZE))
        p['templates'].append(zero)
        self.expect_status(p, 'consistent_supplied_bytes')
        zero['bytes'] = put(zero['bytes'], 0xA0E0, 1)
        self.expect_status(p, 'unsupported_template_count')
        for offset, value, status in ((0x58, 13, 'invalid_owner_state'),
                                     (0x1C, 73, 'invalid_owner_state'),
                                     (0x1C, 0, 'invalid_owner_state'),
                                     (0x58, 4, 'owner_allocation_exceeds_template')):
            p = self.fixture()
            self.change_owner(p, 0, offset, value)
            self.expect_status(p, status)

    def test_16_version_table_shape_and_template_identity(self):
        for field in (b'build', b'exe_sha256', b'game_dll_sha256'):
            p = self.fixture()
            p['version'][field] = b'wrong'
            self.expect_status(p, 'version_mismatch')
        p = self.fixture()
        p['templates'].append(copy.deepcopy(p['templates'][0]))
        self.expect_status(p, 'duplicate_template')
        p = self.lua(self.fixture())
        p[b'owners'][2] = None
        self.assertEqual(self.module.validate(p)[b'status'], b'invalid_input')
        p = self.lua(self.fixture())
        self.rt.eval(b'setmetatable')(p, self.rt.table())
        self.assertEqual(self.module.validate(p)[b'status'], b'invalid_input')

    def test_17_results_do_not_alias_input_and_no_snapshot_can_be_executable(self):
        fixture = self.fixture()
        before = copy.deepcopy(fixture)
        p = self.lua(fixture)
        r = self.module.validate(p)
        r[b'snapshot'][b'version'][b'build'] = -1
        r[b'snapshot'][b'owners'][1][b'allocated'] = 99
        r[b'template_counts'][0x24] = 99
        self.assertEqual(self.module.validate(p)[b'status'], b'consistent_supplied_bytes')
        plan = self.module.validate_and_plan(p, self.lua(self.ops(fixture)))
        self.assertEqual((plan[b'status'], plan[b'executable']), (b'fits', False))
        self.assertEqual(fixture, before)

    def test_18_profile_layout_and_original_256_slot_backing(self):
        self.assertEqual(int(self.layout['subobject_size'], 16), S_SIZE)
        self.assertEqual(int(self.layout['pool']['node_stride'], 16), NODE_SIZE)
        self.assertEqual(int(self.layout['template_stride'], 16), TEMPLATE_SIZE)
        self.assertEqual(int(self.layout['template_element_stride'], 16), ELEMENT_SIZE)
        p = self.fixture(capacity=256, unlisted=251)
        self.assertEqual(struct.unpack_from('<Q', p['descriptor'], 8)[0], D + 0x23F18)
        r = self.module.validate_and_plan(self.lua(p), self.lua(self.ops(p)))
        self.assertEqual((r[b'status'], r[b'peak_required']), (b'insufficient_capacity', 257))
        self.assertEqual(r[b'snapshot_audit'][b'unclaimed_occupied_nodes'], 251)

    def test_19_free_node_payload_must_match_constructor_or_cleanup_pattern(self):
        # Constructor clears then calls 1408FE0, which sets A8 and AC to 1.0f.
        # Cleanup 1408F00 instead clears all 0x208 bytes. Accept both, not a
        # made-up invariant that every free node must always be entirely zero.
        p = self.fixture()
        for offset in (0xA8, 0xAC):
            p['nodes'] = put(p['nodes'], 5 * NODE_SIZE + offset, 0x3F800000)
        self.expect_status(p, 'consistent_supplied_bytes')
        for offset in (0, 0x28, 0x30, 0x68, 0xA8, 0xB0, 0x204):
            with self.subTest(offset=hex(offset)):
                p = self.fixture()
                p['nodes'] = put(p['nodes'], 5 * NODE_SIZE + offset, 1)
                self.expect_status(p, 'unsupported_free_node_state')

    def test_20_fresh_unallocated_owners_do_not_require_unknown_template_zero(self):
        p = self.fixture()
        p['nodes'] = bytes(6 * NODE_SIZE)
        p['occupancy'] = bytes(6)
        p['descriptor'] = put(p['descriptor'], 0x10, 0)
        for i in range(3):
            self.change_owner(p, i, 0x1C, 0)
            self.change_owner(p, i, 0x58, 0)
        c = self.expect_status(p, 'consistent_supplied_bytes')
        self.assertEqual(c[b'audit'][b'occupied_nodes'], 0)
        key = c[b'snapshot'][b'owners'][1][b'key']
        r = self.module.validate_and_plan(self.lua(p), self.lua([dict(owner=key, template_id=0x24)]))
        self.assertEqual((r[b'status'], r[b'final_used']), (b'fits', 3))
        # ID 0 as current empty state is recognized; requesting ID 0 still
        # requires its explicitly supplied zero-count template contract.
        r = self.module.validate_and_plan(self.lua(p), self.lua([dict(owner=key, template_id=0)]))
        self.assertEqual(r[b'status'], b'unknown_template')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), python=sys.version,
        python_executable=sys.executable, lupa_version=lupa.__version__,
        lua_runtime=LuaRuntime().lua_implementation,
        source_sha256={str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES},
        test_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        evidence_sha256=EVIDENCE_SHAS, fixture_origin='synthetic binary bytes, not captured heap',
        game_process_access=False, game_execution=False, mod_installed=False,
        limitations=['Supplied-byte structure only; no live origin, atomicity or synchronization proof.',
                     'No proof of unprovided owner aliases or external resource validity.',
                     'No native executor, game integration or multiplayer acceptance.'])
    folder = ROOT / 'verification'
    folder.mkdir(exist_ok=True)
    (folder / 'pool_snapshot_tests.json').write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
