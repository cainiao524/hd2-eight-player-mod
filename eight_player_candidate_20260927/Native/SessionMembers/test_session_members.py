"""Execute the captured four-slot function and the eight-slot candidate.

The fixture supplies explicit platform methods and callback contracts.  It
compares the original build on counts 0..4 with the candidate, then exercises
the newly reachable counts 5..8 and the fail-closed count cap.  No game
process, DLL, Steam account or network is touched.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / "five_player_feasibility_20260927"
sys.path.insert(0, str(ROOT / ".native-test-deps"))
sys.path.insert(0, str(ROOT / "Native" / "SessionMembers"))

import capstone  # type: ignore
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE  # type: ignore
from unicorn import x86_const as xr  # type: ignore

import session_members as native


GAME = 0x7FF600000000
ORIGINAL = GAME + native.ENTRY
CANDIDATE = GAME + 0x10000000
RESOLVER = GAME + 0x10020000
CONSUMER = GAME + 0x10021000
SIDE = GAME + 0x10022000
API_ROOT = GAME + 0x10023000
API_TABLE = GAME + 0x10024000
F8_TABLE = GAME + 0x10025000
ALT_OBJECT = GAME + 0x10026000
ALT_TABLE = GAME + 0x10027000
COUNT_STUB = GAME + 0x10028000
GET_STUB = GAME + 0x10029000
F8_STUB = GAME + 0x1002A000
ALT_STUB = GAME + 0x1002B000
UPDATE_STUB = GAME + 0x1093590
STOP = GAME + 0x1002C000
OWNER = GAME + 0x20000000
STACK = GAME + 0x30000000
RSP = STACK + 0x8000

u32 = lambda n: struct.pack("<I", n & 0xFFFFFFFF)
u64 = lambda n: struct.pack("<Q", n & 0xFFFFFFFFFFFFFFFF)
reg = lambda n: getattr(xr, "UC_X86_REG_" + n.upper())
sha = lambda b: hashlib.sha256(b).hexdigest()


def ret_from_stub(uc: Uc, value: int | None = None) -> None:
    if value is not None:
        uc.reg_write(xr.UC_X86_REG_RAX, value & 0xFFFFFFFFFFFFFFFF)
    rsp = uc.reg_read(xr.UC_X86_REG_RSP)
    target = struct.unpack("<Q", bytes(uc.mem_read(rsp, 8)))[0]
    uc.reg_write(xr.UC_X86_REG_RSP, rsp + 8)
    uc.reg_write(xr.UC_X86_REG_RIP, target)


class Fixture:
    def __init__(self, *, original: bool, branch: str, count: int):
        self.original = original
        self.branch = branch
        self.count = count
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.pages: set[int] = set()
        self.events: list[dict] = []
        self.sidecar = SIDE
        self.code_address = ORIGINAL if original else CANDIDATE
        self.body, _ = native.load_body(RESEARCH / "creation_enumeration_helper_full_disasm_20261002.json")
        if original:
            self.code = self.body
        else:
            self.artifact = native.build(game_base=GAME, code_address=CANDIDATE,
                                         resolver_address=RESOLVER,
                                         consumer_address=CONSUMER,
                                         sidecar_address=SIDE)
            self.code = bytes.fromhex(self.artifact["code_hex"])
        self.map(self.code_address, len(self.code)); self.write(self.code_address, self.code)
        # Code hook stubs need one mapped byte; they are intercepted before it executes.
        for address in (RESOLVER, CONSUMER, COUNT_STUB, GET_STUB, F8_STUB,
                        ALT_STUB, UPDATE_STUB, STOP):
            self.map(address, 1); self.write(address, b"\xcc")
        self.map(OWNER, 0x2200)
        self.map(SIDE, 0x100)
        self.map(STACK, 0x10000)
        self.map(GAME + native.GLOBAL_API, 0x100)
        self.map(GAME + native.GLOBAL_FLAG, 0x100)
        self.map(API_ROOT, 0x300); self.map(API_TABLE, 0x200)
        self.map(F8_TABLE, 0x200); self.map(ALT_OBJECT, 0x100); self.map(ALT_TABLE, 0x100)
        self.setup_memory()
        self.uc.reg_write(xr.UC_X86_REG_RSP, RSP)
        self.uc.mem_write(RSP, u64(STOP))
        for name, value in (("rbx", 0xAABBCCDDEEFF0011), ("rsi", 0x1111),
                            ("rdi", 0x2222), ("r12", 0x3333), ("r13", 0x4444)):
            self.uc.reg_write(reg(name), value)
        self.uc.reg_write(xr.UC_X86_REG_RCX, OWNER)
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)

    def map(self, address: int, size: int) -> None:
        first = address & ~0xFFF
        last = (address + size + 0xFFF) & ~0xFFF
        for page in range(first, last, 0x1000):
            if page not in self.pages:
                self.uc.mem_map(page, 0x1000)
                self.uc.mem_write(page, b"\xA5" * 0x1000)
                self.pages.add(page)

    def write(self, address: int, data: bytes) -> None:
        self.uc.mem_write(address, data)

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", bytes(self.uc.mem_read(address, 4)))[0]

    def read_u64(self, address: int) -> int:
        return struct.unpack("<Q", bytes(self.uc.mem_read(address, 8)))[0]

    def setup_memory(self) -> None:
        # owner[0] selects the first platform path; owner[8] selects the second.
        self.write(OWNER, u64(0 if self.branch != "first" else API_ROOT))
        self.write(OWNER + 8, u64(0 if self.branch == "first" else 0xBEEF))
        self.write(OWNER + 0x1B58, b"\0" * (8 * 8))
        self.write(OWNER + 0x1BB0, u32(0))
        self.write(OWNER + 0x1B78, u32(0xDEADBEEF))
        self.write(OWNER + 0x1B7C, u32(0xA5A5A5A5))
        self.write(SIDE, b"\0" * 0x100)
        self.write(GAME + native.GLOBAL_API, u64(API_ROOT))
        flag_object = GAME + native.GLOBAL_FLAG + 0x40
        self.map(flag_object, 0x100)
        self.write(GAME + native.GLOBAL_FLAG, u64(flag_object))
        self.write(flag_object + 8, bytes([1 if self.branch == "true" else 0]))
        self.write(API_ROOT + 0x30, u64(API_TABLE))
        self.write(API_ROOT + 0xF8, u64(F8_TABLE))
        self.write(API_ROOT + 0x148, u64(ALT_OBJECT))
        self.write(API_TABLE + 0x80, u64(COUNT_STUB))
        self.write(API_TABLE + 0x88, u64(GET_STUB))
        self.write(F8_TABLE + 0x138, u64(F8_STUB))
        self.write(ALT_OBJECT + 0x10, u64(ALT_TABLE))
        self.write(ALT_TABLE + 0x58, u64(ALT_STUB))

    def on_code(self, uc: Uc, address: int, size: int, data: bytes) -> None:
        if address == STOP:
            self.events.append({"kind": "return"})
            uc.emu_stop()
        elif address == RESOLVER:
            self.events.append({"kind": "resolve", "owner": uc.reg_read(xr.UC_X86_REG_RCX)})
            ret_from_stub(uc, SIDE)
        elif address == CONSUMER:
            self.events.append({"kind": "consume", "owner": uc.reg_read(xr.UC_X86_REG_RCX),
                                "sidecar": uc.reg_read(xr.UC_X86_REG_RDX),
                                "count": uc.reg_read(xr.UC_X86_REG_R8) & 0xFFFFFFFF})
            ret_from_stub(uc, 77)
        elif address == COUNT_STUB:
            self.events.append({"kind": "count", "handle": uc.reg_read(xr.UC_X86_REG_RCX)})
            ret_from_stub(uc, self.count)
        elif address == GET_STUB:
            idx = uc.reg_read(xr.UC_X86_REG_RDX) & 0xFFFFFFFF
            self.events.append({"kind": "get", "index": idx})
            ret_from_stub(uc, 0x1000 + idx)
        elif address == F8_STUB:
            self.events.append({"kind": "first", "destination": uc.reg_read(xr.UC_X86_REG_RDX),
                                "capacity": uc.reg_read(xr.UC_X86_REG_R8) & 0xFFFFFFFF})
            destination = uc.reg_read(xr.UC_X86_REG_RDX)
            for i in range(min(self.count, 8)):
                self.write(destination + 8 * i, u64(0x2000 + i))
            ret_from_stub(uc, self.count)
        elif address == ALT_STUB:
            self.events.append({"kind": "alternate", "destination": uc.reg_read(xr.UC_X86_REG_RDX),
                                "capacity": uc.reg_read(xr.UC_X86_REG_R8) & 0xFFFFFFFF})
            destination = uc.reg_read(xr.UC_X86_REG_RDX)
            for i in range(min(self.count, 8)):
                self.write(destination + 8 * i, u64(0x3000 + i))
            ret_from_stub(uc, self.count)
        elif address == UPDATE_STUB:
            self.events.append({"kind": "update", "owner": uc.reg_read(xr.UC_X86_REG_RCX)})
            ret_from_stub(uc, 77)

    def run(self) -> None:
        self.uc.emu_start(self.code_address, 0, count=20000)
        self.asserted = self.events and self.events[-1]["kind"] == "return"


class SessionMembersTests(unittest.TestCase):
    def run_original(self, branch: str, count: int) -> Fixture:
        return Fixture(original=True, branch=branch, count=count)

    def test_source_body_and_candidate_metadata(self):
        body, _ = native.load_body(RESEARCH / "creation_enumeration_helper_full_disasm_20261002.json")
        self.assertEqual(len(body), native.END - native.ENTRY)
        self.assertEqual(sha(body), native.BODY_SHA256)
        artifact = native.build(game_base=GAME, code_address=CANDIDATE,
                                resolver_address=RESOLVER, consumer_address=CONSUMER,
                                sidecar_address=SIDE)
        self.assertFalse(artifact["installable"])
        self.assertEqual(artifact["capacity"]["candidate"], 8)
        # Candidate is real x64 code, not a declarative count model.
        rows = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(
            bytes.fromhex(artifact["code_hex"]), CANDIDATE))
        self.assertEqual(sum(row.size for row in rows), artifact["size_bytes"])
        self.assertGreaterEqual(len(rows), 50)

    def test_original_four_behavior_is_preserved(self):
        for branch in ("true", "false"):
            for count in range(5):
                with self.subTest(branch=branch, count=count):
                    f = self.run_original(branch, count)
                    f.run()
                    self.assertTrue(f.asserted)
                    self.assertEqual(f.read_u32(OWNER + 0x1BB0), count)
                    self.assertEqual(f.read_u32(OWNER + 0x1B78), 77)
                    # The original always uses its four-entry capacity.
                    capacities = [e["capacity"] for e in f.events if e["kind"] in ("first", "alternate")]
                    if capacities:
                        self.assertEqual(capacities[0], 4)
                    gets = [e["index"] for e in f.events if e["kind"] == "get"]
                    if branch == "true":
                        self.assertEqual(gets, list(range(count)))

    def test_candidate_preserves_old_inputs_and_expands_true_path(self):
        for count in range(9):
            with self.subTest(count=count):
                f = Fixture(original=False, branch="true", count=count)
                f.run()
                self.assertTrue(f.asserted)
                capped = min(count, 8)
                self.assertEqual(f.read_u32(OWNER + 0x1BB0), capped)
                self.assertEqual(f.read_u32(SIDE + 0x40), capped)
                self.assertEqual([e["index"] for e in f.events if e["kind"] == "get"], list(range(capped)))
                self.assertEqual([f.read_u64(SIDE + 8 * i) for i in range(capped)],
                                 [0x1000 + i for i in range(capped)])
                self.assertEqual([e["count"] for e in f.events if e["kind"] == "consume"], [capped])

    def test_candidate_expands_alternate_path_without_clobbering_owner_fields(self):
        for count in (0, 4, 5, 8, 9):
            with self.subTest(count=count):
                f = Fixture(original=False, branch="false", count=count)
                f.run()
                self.assertTrue(f.asserted)
                capped = min(count, 8)
                self.assertEqual(f.read_u32(OWNER + 0x1BB0), capped)
                self.assertEqual(f.read_u32(SIDE + 0x40), capped)
                self.assertEqual(f.read_u32(OWNER + 0x1B78), 77)
                self.assertEqual([f.read_u64(SIDE + 8 * i) for i in range(capped)],
                                 [0x3000 + i for i in range(capped)])
                self.assertEqual(f.read_u32(OWNER + 0x1B78), 77)
                self.assertEqual(f.read_u32(OWNER + 0x1B7C), 0xA5A5A5A5)

    def test_candidate_expands_first_platform_path(self):
        for count in (0, 4, 5, 8, 9):
            with self.subTest(count=count):
                f = Fixture(original=False, branch="first", count=count)
                f.run()
                self.assertTrue(f.asserted)
                capped = min(count, 8)
                bulk = [e for e in f.events if e["kind"] == "first"]
                self.assertEqual(len(bulk), 1)
                self.assertEqual(bulk[0]["destination"], SIDE)
                self.assertEqual(bulk[0]["capacity"], 8)
                self.assertEqual(f.read_u32(SIDE + 0x40), capped)
                self.assertEqual([f.read_u64(SIDE + 8 * i) for i in range(capped)],
                                 [0x2000 + i for i in range(capped)])
                self.assertEqual(f.read_u32(OWNER + 0x1B78), 77)


if __name__ == "__main__":
    unittest.main(verbosity=2)
