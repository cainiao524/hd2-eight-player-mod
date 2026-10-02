"""Bounded original-code prefix probe; not a candidate or multiplayer test.

Runs 1277920 through1277AA3 (exclusive), with the real saved585B80 leaf and
its RVA jump table. All memory is synthetic Unicorn RAM; no process APIs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'eight_player_candidate_20260927/.native-test-deps'))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr
import unicorn
from roster_mask_reader_replay import BODY_SHA, LEAF_SHA, TABLE_SHA

GAME = 0x7FF600000000
S, TABLE, RECORD, MASK, MASKS, INPUTS, OTHER = [0x18200000000 + i * 0x10000 for i in range(7)]
STACK, RSP = 0x18210000000, 0x18210008008
STOP = GAME + 0x1277AA3
GPRS = ('rax', 'rbx', 'rcx', 'rdx', 'rsi', 'rdi', 'rbp', 'rsp',
        'r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r14', 'r15', 'eflags')
reg = lambda name: getattr(xr, 'UC_X86_REG_' + name.upper())
sha = lambda blob: hashlib.sha256(blob).hexdigest()
u32 = lambda value: struct.pack('<I', value)
u64 = lambda value: struct.pack('<Q', value)


def execute(evidence, network, masks, primary=0.0, count=3, ordinal=3):
    uc = Uc(UC_ARCH_X86, UC_MODE_64)
    pages, reads, writes, calls = set(), [], [], []

    def put(address, blob):
        for page in range(address & ~0xFFF, (address + len(blob) + 0xFFF) & ~0xFFF, 0x1000):
            if page not in pages:
                uc.mem_map(page, 0x1000)
                uc.mem_write(page, b'\xa5' * 0x1000)
                pages.add(page)
        uc.mem_write(address, blob)

    body = bytes.fromhex(evidence['body']['bytes_hex'])
    leaf = bytes.fromhex(evidence['necessary_leaf']['bytes_hex'])
    table = bytes.fromhex(evidence['necessary_leaf']['jump_table']['bytes_hex'])
    assert sha(body) == BODY_SHA and sha(leaf) == LEAF_SHA and sha(table) == TABLE_SHA
    put(GAME + 0x1277920, body)
    put(GAME + 0x585B80, leaf + table)
    put(STACK, b'\xa5' * 0x10000)
    for rva, value in ((0x3326468, S), (0x33269C0, MASK), (0x347CF18, INPUTS),
                       (0x3326D20, OTHER), (0x263C010, 0x12345678ABCDEF00)):
        put(GAME + rva, u64(value))
    put(GAME + 0x3483C20, u32(0xFFFFFFFF))
    put(RECORD, bytes(0x50))
    put(RECORD + 4, u32(0x2468))
    put(RECORD + 0xC, u32(11))
    put(RECORD + 0x10, struct.pack('<f', 2.0))
    put(S + 0xD0, u64(TABLE) + u32(8) + u32(0) + u32(1))
    put(TABLE, b''.join(u32(0) + u32(0xFFFFFFFF) for _ in range(8)))
    put(TABLE + (11 & 7) * 8, u32(11) + u32(ordinal))
    put(S + 0x108 + ordinal * 0x70 + 0x24, struct.pack('<f', primary))
    put(S + 0x3A8 + ordinal * 0x20 + 0xC, u32(network))
    put(MASK + 0xC, u32(count))
    put(MASK + 0x48, u64(MASKS))
    put(MASKS, b''.join(u32(value) for value in masks))
    put(INPUTS + 0x2788 + 13 * 0x20, b'\x01')
    put(INPUTS + 0x2788 + 14 * 0x20, b'\x00')
    for i, name in enumerate(GPRS[:-1]):
        uc.reg_write(reg(name), 0x123400000000 + i)
    for i in range(16):
        uc.reg_write(reg('xmm' + str(i)), 0)
    uc.reg_write(reg('rsp'), RSP)
    uc.reg_write(reg('rcx'), OTHER)
    uc.reg_write(reg('rdx'), RECORD)
    uc.reg_write(reg('xmm2'), int.from_bytes(struct.pack('<f', 0.5), 'little'))
    before = {page: bytes(uc.mem_read(page, 0x1000)) for page in pages if not STACK <= page < STACK + 0x10000}
    stopped = []

    def on_code(uc, address, size, data):
        if address == STOP:
            stopped.append(True)
            uc.emu_stop()
        elif address == GAME + 0x585B80:
            calls.append(uc.reg_read(reg('rcx')))
            assert calls[-1] == ((13 if len(calls) == 1 else 14) << 32) | 3
        elif address not in range(GAME + 0x1277920, STOP) and not GAME + 0x585B80 <= address < GAME + 0x585BA8:
            raise AssertionError(f'Unexpected execution {address:x}')

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.hook_add(UC_HOOK_MEM_READ, lambda u, a, address, size, v, d: reads.append((u.reg_read(reg('rip')), address, size)))
    uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, a, address, size, v, d: writes.append((address, size)))
    uc.emu_start(GAME + 0x1277920, 0, count=3000)
    assert stopped and len(calls) == 2
    assert all(STACK <= address and address + size <= STACK + 0x10000 or (address, size) == (RECORD + 0x10, 4)
               for address, size in writes)
    assert bytes(uc.mem_read(RECORD + 0x10, 4)) == struct.pack('<f', 2.5)
    for page, blob in before.items():
        expected = bytearray(blob)
        if page <= RECORD + 0x10 < page + 0x1000:
            expected[RECORD + 0x10 - page:RECORD + 0x14 - page] = struct.pack('<f', 2.5)
        assert bytes(uc.mem_read(page, 0x1000)) == bytes(expected)
    actual_reads = [(address, size) for rip, address, size in reads if rip == GAME + 0x1277A2C]
    expected_count = 0
    if primary <= 0 and count and network != 0xFFFFFFFF:
        for value in masks[:count]:
            expected_count += 1
            if not value & (1 << (network & 31)):
                break
    assert actual_reads == [(MASKS + i * 4, 4) for i in range(expected_count)]
    state = {name: uc.reg_read(reg(name)) for name in GPRS}
    state.update({f'xmm{i}': uc.reg_read(reg(f'xmm{i}')) for i in range(16)})
    return dict(network=network, ordinal=ordinal, primary=primary, mask_count=count,
                masks=masks, mask_reads=expected_count, actual_leaf_calls=2,
                stopped_before=hex(STOP - GAME), register_state_sha256=sha(json.dumps(state, sort_keys=True).encode())), state


def probe(evidence):
    runs = []
    for network in (0, 3, 4, 7, 31, 32, 0xFFFFFFFF):
        bit = 1 << (network & 31)
        states = []
        for masks in ([0, 0, 0], [bit, 0, 0], [bit, bit, bit]):
            result, state = execute(evidence, network, masks)
            runs.append(result)
            states.append(state)
        assert states[0] == states[1] == states[2], 'Mask changed downstream prefix registers'
    for primary, count, ordinal in ((1.0, 3, 0), (0.0, 0, 2), (-1.0, 3, 1)):
        result, _ = execute(evidence, 7, [128] * 3, primary, count, ordinal)
        runs.append(result)
    return dict(status='passed', prefix_observations=len(runs), runs=runs,
                actual_nested_leaf_calls=sum(x['actual_leaf_calls'] for x in runs),
                saved_root_sha256=BODY_SHA, leaf_sha256=LEAF_SHA, table_sha256=TABLE_SHA,
                program_sha256=sha(Path(__file__).read_bytes()), unicorn_version=unicorn.__version__,
                candidate_emitted=False, full_function_executed=False, game_process_accessed=False,
                included_in_delivery_suite_totals=False,
                conclusion='At1277AA3 all GPR/flags/XMM state matches across three mask contents for each network input; only original input+10 timer store occurred outside stack',
                limits=['Prefix only; no later ring operations, callbacks, notification or original return',
                        'Original ordinal0..3 uses valid four-slot layout; network0..7 does not prove original eight-slot capacity',
                        'Mask/state ownership and concurrent mutation supplied by synthetic fixture; no live mask producer verified'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=HERE / 'roster_mask_reader_evidence.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite output')
    evidence = json.loads(args.evidence.read_bytes())
    result = probe(evidence)
    result['evidence_sha256'] = sha(args.evidence.read_bytes())
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'prefix_observations', 'actual_nested_leaf_calls')}))
