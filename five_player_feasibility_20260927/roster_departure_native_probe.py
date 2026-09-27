"""Bounded original-x64 departure/count observation, never a candidate test.

Three original-four-slot cases run 605950 with its real 606820 lookup, then
540A40 with its real map-delete helper. The outer dispatch is a synthetic
harness. External notifications are explicitly noninterfering contract stubs.
"""
from __future__ import annotations
import argparse, hashlib, json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'eight_player_candidate_20260927/.native-test-deps'))
import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr

sha = lambda data: hashlib.sha256(data).hexdigest()
u32 = lambda value: struct.pack('<I', value)
u64 = lambda value: struct.pack('<Q', value)
reg = lambda name: getattr(xr, 'UC_X86_REG_' + name.upper())
GAME = 0x7FF600000000
S, MAP, ENTITIES = 0x18200100400, 0x18200200100, 0x18200300000
CONTEXT, VTABLE = 0x18200400000, 0x18200401000
MODE, ASSOC_MANAGER, UI_MANAGER, UI, AUX_CONFIG = [0x18200500000 + i * 0x100000 for i in range(5)]
STACK, RSP = 0x182F0000000, 0x182F0008008
TAIL, STOP = GAME + 0x100F0000, GAME + 0x10100000
SEEDS = {name: 0xABCDEF0100000000 + i for i, name in enumerate(('rbx', 'rbp', 'rsi', 'rdi', 'r12', 'r13', 'r14', 'r15'))}
DEPARTURE_EVIDENCE_SHA = '0280267b6f32d4a24f15c69da317d1c2c7a93adb136d4252ff93e09a8d67e609'
REMOVE_EVIDENCE_SHA = '67563b2d12860c814096b1d45338dd271ad13975c3ba4f96169a92473ab061af'
DEPARTURE = HERE / 'roster_departure_native_evidence.json'
REMOVE = HERE / 'roster_remove_native_evidence.json'
NOTIFICATION_ROLES = {0x139C360: 'network_notification', 0xFD9C80: 'associated_entity_lookup_returns_null',
                      0x94C9C0: 'ui_notification', 0x60C2A0: 'count_notification'}
NETWORKS = [0, 1, 2, 3]
LAYOUT = [('pointer', 0xE8, 8), ('primary', 0x108, 0x70), ('aux', 0x2C8, 0x38), ('property', 0x3A8, 0x20)]


def read_evidence(path, expected):
    raw = path.read_bytes()
    assert sha(raw) == expected, 'fixed evidence fingerprint changed'
    return json.loads(raw)


def reconstruct(evidence, entry, end, expected):
    body = evidence['bodies'][hex(entry)]
    cursor, pieces = entry, []
    for row in body['instructions']:
        blob = bytes.fromhex(row['bytes'])
        assert int(row['rva'], 16) == cursor and sha(blob) == row['sha256']
        pieces.append(blob); cursor += len(blob)
    result = b''.join(pieces)
    assert cursor == end and result.hex() == body['bytes_hex'] and sha(result) == expected
    return result


departure_ev = read_evidence(DEPARTURE, DEPARTURE_EVIDENCE_SHA)
remove_ev = read_evidence(REMOVE, REMOVE_EVIDENCE_SHA)
BODIES = {
    0x605950: reconstruct(departure_ev, 0x605950, 0x605F2F, '4f0de56eb062df3180f58fcf4fd9a4e462eceba75a3077ac2bc22728500f5681'),
    0x606820: reconstruct(departure_ev, 0x606820, 0x6068E5, '0ee6495101f1fbd8c4a95731144aa5dbd43289f107264c12c4d2d9aab9ffd2ce'),
    0x540A40: reconstruct(remove_ev, 0x540A40, 0x540AE0, '35e4c996bb1466c41df455f8e5f9df1174c8c2bb958ee127a3b7ecc59f6abcf8'),
    0x172F8A0: reconstruct(remove_ev, 0x172F8A0, 0x172F9A3, 'd58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f'),
}


class Probe:
    def __init__(self, name, t, d, ordinal):
        self.name, self.t, self.d, self.ordinal = name, t, d, ordinal
        self.entity = ENTITIES + ordinal * 0x40
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages, self.events, self.writes, self.trace = set(), [], [], []
        self.phase, self.outcome = None, None
        for entry, blob in BODIES.items(): self.map(GAME + entry, len(blob)); self.write(GAME + entry, blob)
        for rva in NOTIFICATION_ROLES: self.map(GAME + rva, 1); self.write(GAME + rva, b'\xc3')
        self.map(TAIL, 1); self.write(TAIL, b'\xc3')
        self.map(STOP, 1); self.write(STOP, b'\xcc')
        for address, size in ((S - 0x80, 0x600), (MAP - 0x80, 0x100), (ENTITIES, 0x1000), (STACK, 0x10000),
                              (CONTEXT, 0x20), (VTABLE + 0x480, 8), (MODE + 0xAC21C, 4),
                              (ASSOC_MANAGER + 0x6C, 4), (UI_MANAGER + 0x15C0, 0x18),
                              (UI + 0x518B0, 0x18), (AUX_CONFIG, 0x48)):
            self.map(address, size)
        globals64 = {0x3326468: S, 0x347CE60: 0x18200B00000, 0x3326340: MODE,
                     0x3326308: CONTEXT, 0x3326D20: ASSOC_MANAGER, 0x3326E68: UI_MANAGER,
                     0x33266A0: AUX_CONFIG}
        for rva, value in globals64.items(): self.map(GAME + rva, 8); self.write(GAME + rva, u64(value))
        for rva in (0x3483C20, 0x3483C34): self.map(GAME + rva, 4); self.write(GAME + rva, u32(0xFFFFFFFF))
        for rva, item in departure_ev['notification_literals'].items():
            blob = bytes.fromhex(item['bytes_hex']); assert sha(blob) == item['sha256']
            self.map(GAME + int(rva, 16), len(blob)); self.write(GAME + int(rva, 16), blob)
        # Fixed capture value at RVA 23C6D70, independently read as 0000803F.
        self.map(GAME + 0x23C6D70, 4); self.write(GAME + 0x23C6D70, bytes.fromhex('0000803f'))
        self.write(CONTEXT + 0x10, u64(VTABLE)); self.write(VTABLE + 0x480, u64(TAIL))
        self.write(MODE + 0xAC21C, u32(4)); self.write(ASSOC_MANAGER + 0x6C, u32(0))
        self.write(UI_MANAGER + 0x15C0, u32(1)); self.write(UI_MANAGER + 0x15C8, u64(UI))
        self.write(UI_MANAGER + 0x15D0, u32(0x3E)); self.write(UI + 0x518B0, struct.pack('<2f', 2.0, 3.0))
        self.write(UI + 0x518C4, u32(7)); self.write(AUX_CONFIG + 8, u32(0))
        for off, value in ((0x80, t), (0x84, d), (0x88, 0), (0xD8, 8), (0xDC, 0), (0xE0, 1)):
            self.write(S + off, u32(value))
        self.write(S + 0xD0, u64(MAP))
        table = [(0, 0xFFFFFFFF)] * 8
        for i in range(4):
            entity, key = ENTITIES + i * 0x40, 11 + i * 8
            self.write(entity + 8, u32(key)); self.write(entity + 0x10, u32(0xC0000000 + i)); self.write(entity + 0x14, b'\0')
            if i < t: table[(3 + i) & 7] = (key, i)
            for group, (label, offset, stride) in enumerate(LAYOUT):
                blob = u64(entity) if label == 'pointer' else bytes((i * 31 + j * 7 + group * 67) & 255 for j in range(stride))
                self.write(S + offset + i * stride, blob)
            self.write(S + 0x3A8 + i * 0x20, u32(0xFFFFFFFF))
            self.write(S + 0x3B4 + i * 0x20, u32(NETWORKS[i]))
        for i, (key, value) in enumerate(table): self.write(MAP + i * 8, u32(key) + u32(value))
        self.initial = self.snapshot()
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, data: self.writes.append((address, size)))

    def map(self, address, size):
        for page in range(address & ~0xFFF, (address + size + 0xFFF) & ~0xFFF, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000); self.uc.mem_write(page, b'\xa5' * 0x1000); self.pages.add(page)
    def write(self, address, blob): self.uc.mem_write(address, blob)
    def read(self, address, size): return bytes(self.uc.mem_read(address, size))
    def int32(self, address): return struct.unpack('<I', self.read(address, 4))[0]
    def counts(self): return [self.int32(S + off) for off in (0x80, 0x84, 0x88)]
    def snapshot(self): return {page: self.read(page, 0x1000) for page in self.pages if not STACK <= page < STACK + 0x10000}

    def on_code(self, uc, address, size, data):
        self.trace.append(address)
        if address == STOP: self.outcome = 'return'; uc.emu_stop(); return
        if address - GAME in BODIES:
            self.events.append(dict(phase=self.phase, kind='actual_body_entry', rva=hex(address - GAME), counts=self.counts()))
        role = 'tail_player_count' if address == TAIL else NOTIFICATION_ROLES.get(address - GAME)
        if role is None: return
        assert self.phase == 'departure' and self.counts() == [self.t, self.d, 0]
        assert self.snapshot() == self.initial, 'departure or earlier external stub changed nonstack fixture memory'
        rsp = uc.reg_read(reg('rsp'))
        assert rsp % 16 == 8 and STACK <= rsp < STACK + 0x10000
        event = dict(phase=self.phase, kind='external_contract_stub', role=role, counts=self.counts(),
                     rva=None if address == TAIL else hex(address - GAME), edx=uc.reg_read(reg('edx')), rsp_mod16=rsp % 16)
        if role == 'ui_notification': event['count_stack_argument'] = self.int32(rsp + 0x30)
        if role == 'tail_player_count':
            assert self.read(uc.reg_read(reg('rcx')), 13) == b'player_count\0'
            event['literal'] = 'player_count'
        self.events.append(event)
        # Known contracts only: associated lookup returns null; notifications
        # leave all fixture data intact and may clobber volatile registers.
        self.write(rsp + 8, b'\xc7' * 32)
        for i, name in enumerate(('rax', 'rcx', 'rdx', 'r8', 'r9', 'r10', 'r11')):
            uc.reg_write(reg(name), 0xCDCD000000000000 + i)
        for i in range(6): uc.reg_write(reg('xmm' + str(i)), (0xAABBCCDDEEFF0000 + i) * (1 + (1 << 64)))
        uc.reg_write(reg('rax'), 0)

    def run_phase(self, phase, entry):
        self.phase, self.outcome, self.writes, self.trace = phase, None, [], []
        for name, value in SEEDS.items(): self.uc.reg_write(reg(name), value)
        for i in range(6, 16): self.uc.reg_write(reg('xmm' + str(i)), (0x0102030405060708 + i) * (1 + (1 << 64)))
        self.write(RSP, u64(STOP))
        for name, value in dict(rsp=RSP, rcx=0xDEAD0000 if phase == 'departure' else self.entity,
                               rdx=self.entity, r8=0x8181818181818181, r9=0x9191919191919191).items():
            self.uc.reg_write(reg(name), value)
        self.uc.emu_start(GAME + entry, 0, count=15000)
        assert self.outcome == 'return'
        assert self.uc.reg_read(reg('rsp')) == RSP + 8
        for name, value in SEEDS.items(): assert self.uc.reg_read(reg(name)) == value, name
        for i in range(6, 16): assert self.uc.reg_read(reg('xmm' + str(i))) == (0x0102030405060708 + i) * (1 + (1 << 64))
        return dict(phase=phase, entry_rva=hex(entry), outcome=self.outcome, instructions=len(self.trace), counts_after=self.counts())

    def run(self):
        departure = self.run_phase('departure', 0x605950)
        assert self.snapshot() == self.initial and self.counts() == [self.t, self.d, 0]
        assert all(STACK <= address and address + size <= STACK + 0x10000 for address, size in self.writes)
        external = [event for event in self.events if event['kind'] == 'external_contract_stub']
        assert [event['role'] for event in external] == ['network_notification', 'associated_entity_lookup_returns_null',
                                                         'ui_notification', 'count_notification', 'tail_player_count']
        assert external[0]['edx'] == NETWORKS[self.ordinal]
        ui_count = external[2]['count_stack_argument']
        notified = external[3]['edx']
        tail_count = external[4]['edx']
        assert ui_count == notified == ((self.d - 1) & 0xFFFFFFFF)
        assert tail_count == self.d
        removal = self.run_phase('remove', 0x540A40)
        expected_d = self.d - int(self.ordinal < self.d)
        assert self.counts() == [self.t - 1, expected_d, 0]
        remaining = [struct.unpack('<II', self.read(MAP + i * 8, 8)) for i in range(8)]
        assert {key: ordinal for key, ordinal in remaining if key} == {11 + i * 8: i for i in range(self.t) if i != self.ordinal}
        assert [event['rva'] for event in self.events if event['kind'] == 'actual_body_entry'] == ['0x605950', '0x606820', '0x540a40', '0x172f8a0']
        tail_pos = next(i for i, event in enumerate(self.events) if event.get('role') == 'tail_player_count')
        remove_pos = next(i for i, event in enumerate(self.events) if event.get('rva') == '0x540a40')
        assert tail_pos < remove_pos
        return dict(name=self.name, t=self.t, d=self.d, p=0, target_ordinal=self.ordinal,
                    phases=[departure, removal], events=self.events, departure_roster_and_nonstack_unchanged=True,
                    ui_count_argument=ui_count, count_notification_edx=notified, tail_player_count_edx=tail_count,
                    actual_post_remove_dense=expected_d,
                    notification_equals_post_remove_dense=notified == expected_d,
                    tail_equals_pre_remove_dense=tail_count == self.d,
                    unsigned_decrement_underflow=self.d == 0, real_saved_mover_executions=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'roster_departure_native_probe_results.json')
    args = parser.parse_args()
    assert not args.output.exists(), 'refusing to overwrite a probe result'
    cases = [Probe('dense_one', 1, 1, 0).run(), Probe('pending_with_dense', 2, 1, 1).run(), Probe('pending_without_dense', 1, 0, 0).run()]
    result = dict(investigation_status='confirmed_count_argument_divergence_under_stated_fixture_contracts',
                  probe_sha256=sha(Path(__file__).read_bytes()),
                  evidence_sha256={str(DEPARTURE.relative_to(ROOT)): DEPARTURE_EVIDENCE_SHA, str(REMOVE.relative_to(ROOT)): REMOVE_EVIDENCE_SHA},
                  executed_body_sha256={hex(entry): sha(blob) for entry, blob in BODIES.items()},
                  float_literal={'rva': '0x23c6d70', 'bytes_hex': '0000803f', 'source': 'same fixed capture; independently read before probe construction'},
                  python_version=sys.version, unicorn_version=unicorn.__version__,
                  fixture_synthetic=True, game_process_accessed=False, host_native_code_executed=False,
                  candidate_emitted=False, top_level_function_executions=6,
                  nested_saved_getter_executions=3, nested_saved_map_delete_executions=3,
                  cases=cases,
                  contract_stubs={'0x139c360': 'observe network DWORD; preserve all nonstack state',
                                  '0xfd9c80': 'return null associated entity; preserve all nonstack state',
                                  '0x94c9c0': 'observe UI sixth stack argument; preserve all nonstack state',
                                  '0x60c2a0': 'observe EDX only; helper implementation and downstream UI callback not executed',
                                  'context.vtable+0x480': 'observe player_count literal and EDX; preserve all nonstack state'},
                  fixture_branch_conditions={'target_bit0': 0, 'prefix_count': 0, 'associated_entity': None,
                                             'associated_manager_count': 0, 'mode': 4, 'ui_listener_count': 1, 'ui_listener_tag': '0x3e',
                                             'aux_config_count': 0, 'original_roster_capacity': 4, 'map_capacity': 8},
                  limits=['External stubs deliberately exclude notifications changing roster, map, counts or globals; real callback interference remains unproven',
                          'The outer ordering is a synthetic two-call harness based on separately observed dispatch order, not execution of FDC820',
                          'The pending states are synthetic; their reachability through the real departure caller has not been established',
                          'Count argument purpose is not inferred: mismatch with actual post-remove D does not by itself justify changing its semantic value',
                          'Only unclassified, no-associated-entity path with one tag-3E UI listener is exercised; other branches and failure behavior remain untested',
                          'All three removals delete their segment-last record; original mover is not needed and is not executed',
                          'No eight-slot candidate, live process operation, installation or multiplayer verification'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['investigation_status'], 'cases': len(cases), 'top_level_executions': 6,
                      'mismatches': sum(not case['notification_equals_post_remove_dense'] for case in cases), 'output': str(args.output)}))


if __name__ == '__main__': main()
