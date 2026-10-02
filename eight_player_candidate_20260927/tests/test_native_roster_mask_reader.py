"""Offline instruction tests for the relocated 1277920 mask reader.

The tests use only the pinned bytes and synthetic Unicorn RAM.  They verify
relocation, the two shared-B roster reads, the pre-dereference guard, ordinary
map misses, and the bounded prefix through the mask loop.  They do not load a
game process or install a hook.
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
RESEARCH = ROOT.parent / "five_player_feasibility_20260927"
sha = lambda blob: hashlib.sha256(blob).hexdigest()
sys.path.insert(0, str(ROOT / ".native-test-deps"))
import capstone  # type: ignore
import unicorn  # type: ignore
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr  # type: ignore


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load_module("roster_mask_reader_under_test", ROOT / "Native" / "roster_mask_reader.py")
EVIDENCE = RESEARCH / "roster_mask_reader_evidence.json"
ADDRESSES = ROOT / "verification" / "native_roster_mask_reader_addresses_synthetic.json"
BUNDLE = ROOT / "verification" / "native_roster_mask_reader_bundle_synthetic.json"
SOURCE = json.loads(EVIDENCE.read_bytes())
BODY = bytes.fromhex(SOURCE["body"]["bytes_hex"])
ADDRESSES_DATA = json.loads(ADDRESSES.read_bytes())
native.EVIDENCE_SHA256 = sha(EVIDENCE.read_bytes())
ARTIFACT = native.build(BODY, SOURCE, **ADDRESSES_DATA)

u32 = lambda value: struct.pack("<I", value & 0xFFFFFFFF)
u64 = lambda value: struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)
reg = lambda name: getattr(xr, "UC_X86_REG_" + name.upper())

GAME = ADDRESSES_DATA["game_base"]
CODE = ADDRESSES_DATA["code_address"]
ROSTER = ADDRESSES_DATA["roster_address"]
STORAGE = ADDRESSES_DATA["storage_address"]
REJECT = ADDRESSES_DATA["reject_address"]
COOKIE_HELPER = ADDRESSES_DATA["cookie_helper_address"]
SLOT_TABLE = 0x18200200100
MASK = 0x18200300100
MASKS = 0x18200310100
INPUTS = 0x18200400100
RECORD = 0x18200500100
STACK = 0x18210000000
RSP = STACK + 0x8008
STOP = ARTIFACT["instruction_address_map"][hex(0x1277AA3)]
GPRS = ("rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "eflags")


def map_put(uc: Uc, pages: set[int], address: int, blob: bytes) -> None:
    if not blob:
        return
    for page in range(address & ~0xFFF, (address + len(blob) + 0xFFF) & ~0xFFF, 0x1000):
        if page not in pages:
            uc.mem_map(page, 0x1000)
            uc.mem_write(page, b"\xa5" * 0x1000)
            pages.add(page)
    uc.mem_write(address, blob)


def write_u32(uc: Uc, pages: set[int], address: int, value: int) -> None:
    map_put(uc, pages, address, u32(value))


def write_u64(uc: Uc, pages: set[int], address: int, value: int) -> None:
    map_put(uc, pages, address, u64(value))


def decode(blob: bytes, address: int):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    rows = list(md.disasm(blob, address))
    if sum(row.size for row in rows) != len(blob):
        raise AssertionError("candidate does not disassemble completely")
    return rows


class NativeRosterMaskReaderTests(unittest.TestCase):
    def test_source_and_full_relocation_are_pinned(self):
        self.assertEqual(len(BODY), native.END - native.ENTRY)
        self.assertEqual(sha(BODY), native.SOURCE_SHA256)
        self.assertEqual(sha(EVIDENCE.read_bytes()), ARTIFACT["evidence_sha256"])
        self.assertEqual(sha(bytes.fromhex(ARTIFACT["code_hex"])), ARTIFACT["code_sha256"])
        rows = decode(bytes.fromhex(ARTIFACT["code_hex"]), CODE)
        self.assertGreaterEqual(len(rows), 390)
        self.assertEqual(len(ARTIFACT["instruction_address_map"]), 390)
        self.assertEqual(len(ARTIFACT["relocations"]), 80)
        self.assertEqual(BUNDLE.exists(), True)
        saved = json.loads(BUNDLE.read_bytes())
        self.assertEqual(saved["code_sha256"], ARTIFACT["code_sha256"])

    def test_shared_b_patch_offsets_are_explicit(self):
        patches = {item["original_rva"]: item for item in ARTIFACT["array_patches"]}
        self.assertEqual(set(patches), {"0x12779f5", "0x1277a06"})
        self.assertEqual(patches["0x12779f5"]["storage_bias"], -0xC8)
        self.assertEqual(patches["0x1277a06"]["storage_bias"], 0x1D8)
        for item in patches.values():
            self.assertTrue(bytes.fromhex(item["replacement_hex"]).startswith(b"\x49\xbb"))
        self.assertEqual(ARTIFACT["reject_reasons"], {"1": "global_roster_binding_mismatch", "2": "null_input_record"})
        self.assertIn("ordinary_missing", ARTIFACT["reject_state"])

    def _guard_fixture(self, *, roster_binding: int, input_address: int):
        uc = Uc(UC_ARCH_X86, UC_MODE_64)
        pages: set[int] = set()
        code = bytes.fromhex(ARTIFACT["code_hex"])
        map_put(uc, pages, CODE, code)
        map_put(uc, pages, REJECT, b"\xcc")
        map_put(uc, pages, COOKIE_HELPER, b"\xc3")
        map_put(uc, pages, STACK, b"\xa5" * 0x10000)
        write_u64(uc, pages, GAME + 0x263C010, 0x12345678ABCDEF00)
        write_u64(uc, pages, GAME + native.GLOBAL_RVA, roster_binding)
        write_u64(uc, pages, RSP, REJECT)
        write_u64(uc, pages, RSP + 0x130, 0x1111222233334444)
        for i, name in enumerate(("rbx", "rbp", "rsi", "rdi", "r12", "r13", "r14", "r15")):
            uc.reg_write(reg(name), 0xABC0000000000000 + i)
        uc.reg_write(reg("rsp"), RSP)
        uc.reg_write(reg("rcx"), 0xDEAD111122223333)
        uc.reg_write(reg("rdx"), input_address)
        uc.reg_write(reg("xmm2"), 0)
        writes: list[tuple[int, int]] = []
        uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, a, address, size, value, data: writes.append((address, size)))
        uc.emu_start(CODE, REJECT, count=2000)
        return uc, writes

    def test_guard_rejects_only_binding_or_null_input(self):
        uc, writes = self._guard_fixture(roster_binding=ROSTER + 8, input_address=RECORD)
        self.assertEqual(uc.reg_read(reg("rip")), REJECT)
        self.assertEqual(uc.reg_read(reg("r10")) & 0xFFFFFFFF, 1)
        self.assertEqual(uc.reg_read(reg("rax")) & 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertEqual(uc.reg_read(reg("rcx")), 0xDEAD111122223333)
        self.assertEqual(uc.reg_read(reg("rbx")), 0xABC0000000000000)
        self.assertEqual(uc.reg_read(reg("r12")), 0xABC0000000000004)
        self.assertEqual(uc.reg_read(reg("r13")), 0xABC0000000000005)
        self.assertTrue(all(STACK <= address < STACK + 0x10000 for address, _ in writes))

        uc, writes = self._guard_fixture(roster_binding=ROSTER, input_address=0)
        self.assertEqual(uc.reg_read(reg("rip")), REJECT)
        self.assertEqual(uc.reg_read(reg("r10")) & 0xFFFFFFFF, 2)
        self.assertEqual(uc.reg_read(reg("rcx")), 0xDEAD111122223333)
        self.assertTrue(all(STACK <= address < STACK + 0x10000 for address, _ in writes))

    def _prefix(self, network: int, masks: list[int], *, primary: float = 0.0,
                count: int = 3, map_miss: bool = False):
        uc = Uc(UC_ARCH_X86, UC_MODE_64)
        pages: set[int] = set()
        code = bytes.fromhex(ARTIFACT["code_hex"])
        leaf_evidence = SOURCE["necessary_leaf"]
        leaf = bytes.fromhex(leaf_evidence["bytes_hex"])
        table = bytes.fromhex(leaf_evidence["jump_table"]["bytes_hex"])
        map_put(uc, pages, CODE, code)
        map_put(uc, pages, GAME + 0x585B80, leaf + table)
        map_put(uc, pages, COOKIE_HELPER, b"\xc3")
        map_put(uc, pages, STACK, b"\xa5" * 0x10000)
        miss_stop = CODE + len(code) + 0x100
        if map_miss:
            map_put(uc, pages, miss_stop, b"\xcc")
        map_put(uc, pages, RECORD, bytes(0x50))
        write_u32(uc, pages, RECORD + 4, 0x2468)
        write_u32(uc, pages, RECORD + 0xC, 11)
        map_put(uc, pages, RECORD + 0x10, struct.pack("<f", 2.0))
        write_u64(uc, pages, GAME + 0x3326468, ROSTER)
        write_u64(uc, pages, GAME + 0x33269C0, MASK)
        write_u64(uc, pages, GAME + 0x347CF18, INPUTS)
        write_u64(uc, pages, GAME + 0x3326D20, 0x18200600100)
        write_u64(uc, pages, GAME + 0x263C010, 0x12345678ABCDEF00)
        write_u32(uc, pages, GAME + 0x3483C20, 0xFFFFFFFF)
        write_u32(uc, pages, GAME + 0x3484788, 0xFFFFFFFF)
        write_u64(uc, pages, ROSTER + 0xD0, SLOT_TABLE)
        write_u32(uc, pages, ROSTER + 0xD8, 8)
        write_u32(uc, pages, ROSTER + 0xDC, 0)
        write_u32(uc, pages, ROSTER + 0xE0, 1)
        for i in range(8):
            write_u32(uc, pages, SLOT_TABLE + i * 8, 0)
            write_u32(uc, pages, SLOT_TABLE + i * 8 + 4, 0xFFFFFFFF)
        write_u32(uc, pages, SLOT_TABLE + (11 & 7) * 8, 99 if map_miss else 11)
        write_u32(uc, pages, SLOT_TABLE + (11 & 7) * 8 + 4, 3)
        map_put(uc, pages, STORAGE + 0x64 + 3 * 0x70, struct.pack("<f", primary))
        write_u32(uc, pages, STORAGE + 0x58C + 3 * 0x20, network)
        write_u32(uc, pages, MASK + 0xC, count)
        write_u64(uc, pages, MASK + 0x48, MASKS)
        for i, value in enumerate(masks):
            write_u32(uc, pages, MASKS + i * 4, value)
        map_put(uc, pages, INPUTS + 0x2788 + 13 * 0x20, b"\x01")
        map_put(uc, pages, INPUTS + 0x2788 + 14 * 0x20, b"\0")
        write_u64(uc, pages, RSP, miss_stop if map_miss else STOP)
        for i, name in enumerate(GPRS[:-1]):
            uc.reg_write(reg(name), 0x123400000000 + i)
        for i in range(16):
            uc.reg_write(reg("xmm" + str(i)), 0)
        uc.reg_write(reg("rsp"), RSP)
        uc.reg_write(reg("rcx"), 0x18200600100)
        uc.reg_write(reg("rdx"), RECORD)
        uc.reg_write(reg("xmm2"), int.from_bytes(struct.pack("<f", 0.5), "little"))
        reads: list[tuple[int, int, int]] = []
        writes: list[tuple[int, int]] = []
        calls: list[int] = []

        def on_code(u, address, size, data):
            if address == STOP or (map_miss and address == miss_stop):
                u.emu_stop()
            elif address == COOKIE_HELPER:
                return
            elif address == GAME + 0x585B80:
                calls.append(u.reg_read(reg("rcx")))
            elif not (CODE <= address < CODE + len(code)) and not (GAME + 0x585B80 <= address < GAME + 0x585BA8):
                raise AssertionError(f"unexpected execution {address:x}")

        uc.hook_add(UC_HOOK_CODE, on_code)
        uc.hook_add(UC_HOOK_MEM_READ, lambda u, a, address, size, value, data: reads.append((u.reg_read(reg("rip")), address, size)))
        uc.hook_add(UC_HOOK_MEM_WRITE, lambda u, a, address, size, value, data: writes.append((address, size)))
        uc.emu_start(CODE, 0, count=6000)
        self.assertEqual(uc.reg_read(reg("rip")), miss_stop if map_miss else STOP)
        if map_miss:
            self.assertEqual(calls, [])
            self.assertEqual(bytes(uc.mem_read(RECORD + 4, 4)), u32(0xFFFFFFFF))
            self.assertEqual(bytes(uc.mem_read(RECORD + 8, 4)), u32(0))
            return None
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls, [(13 << 32) | 3, (14 << 32) | 3])
        self.assertEqual(bytes(uc.mem_read(RECORD + 0x10, 4)), struct.pack("<f", 2.5))
        self.assertTrue(all(STACK <= address < STACK + 0x10000 or address == RECORD + 0x10 for address, _ in writes))
        mask_reads = [(address, size) for rip, address, size in reads if rip == ARTIFACT["instruction_address_map"][hex(0x1277A2C)]]
        expected = 0
        if primary <= 0 and count and network != 0xFFFFFFFF:
            for value in masks[:count]:
                expected += 1
                if not value & (1 << (network & 31)):
                    break
        self.assertEqual(mask_reads, [(MASKS + i * 4, 4) for i in range(expected)])
        state = {name: uc.reg_read(reg(name)) for name in GPRS}
        state.update({f"xmm{i}": uc.reg_read(reg(f"xmm{i}")) for i in range(16)})
        return state

    def test_prefix_reads_shared_b_and_keeps_mask_independent_state(self):
        for network in (0, 3, 4, 7, 31, 32, 0xFFFFFFFF):
            states = [self._prefix(network, masks) for masks in ([0, 0, 0], [1 << (network & 31), 0, 0], [1 << (network & 31)] * 3)]
            self.assertEqual(states[0], states[1])
            self.assertEqual(states[1], states[2])
        self._prefix(7, [128, 128, 128], primary=1.0, count=3)
        self._prefix(7, [128, 128, 128], primary=0.0, count=0)

    def test_ordinary_map_miss_keeps_original_fallback_stores(self):
        self._prefix(7, [0, 0, 0], map_miss=True)

    def test_bundle_is_reproducible_from_source(self):
        saved = json.loads(BUNDLE.read_bytes())
        self.assertEqual(saved["code_hex"], ARTIFACT["code_hex"])
        self.assertEqual(saved["known_regions"], ARTIFACT["known_regions"])
        self.assertFalse(saved["installable"])
        self.assertFalse(saved["game_execution"])
        self.assertFalse(saved["multiplayer_verified"])


if __name__ == "__main__":
    unittest.main()
