"""Execute emitted consumer bytes with explicit synthetic callback contracts.

No game function, process, or service is accessed. Callback implementations
clobber volatile registers and use their whole Windows x64 shadow space.
"""
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / ".native-test-deps"))
sys.path.insert(0, str(HERE))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE
from unicorn import x86_const as xr
from platform_member_consumer_patch import bind_candidate, SENTINELS
from platform_member_consumer import OwnerState, MemberSidecar, evaluate

EVIDENCE = HERE / "platform_member_consumer_disasm_20261002.json"
REG = lambda name: getattr(xr, "UC_X86_REG_" + name.upper())
Q = lambda value: struct.pack("<Q", value)
D = lambda value: struct.pack("<I", value)
GAME = 0x10000000
CODE = 0x20000000
CALLBACKS = {name: 0x21000000 + i * 0x1000 for i, name in enumerate(SENTINELS)}
OWNER, SIDE, STACK, STOP = 0x30000000, 0x30010000, 0x40000000, 0x50000000
NONVOL = ["rbx", "rbp", "rsi", "rdi", "r12", "r13", "r14", "r15"]


class BoundExecutionTests(unittest.TestCase):
    def execute(self, ids, *, count=None, mode=True, ready=True,
                platform=0x12340000, missing=(), invalid=(), owner=OWNER,
                resolved=True, code_address=CODE):
        bound = bind_candidate(EVIDENCE, game_base=GAME, code_address=code_address,
                               unwind_address=code_address+0x1000, callbacks=CALLBACKS)
        uc = Uc(UC_ARCH_X86, UC_MODE_64)
        for base, size in ((code_address, 0x2000), (0x21000000, 0x5000),
                           (OWNER, 0x20000), (STACK, 0x10000), (STOP, 0x1000)):
            uc.mem_map(base, size)
        uc.mem_write(code_address, bytes.fromhex(bound["code_hex"]))
        uc.mem_write(OWNER, Q(platform))
        uc.mem_write(OWNER+0x1ba6, bytes([ready]))
        for i, value in enumerate(ids[:8]):
            uc.mem_write(SIDE+i*8, Q(value))
        uc.mem_write(SIDE+0x40, D(len(ids) if count is None else count))
        data_before = bytes(uc.mem_read(OWNER, 0x20000))
        entry_rsp = STACK+0x8008
        uc.mem_write(entry_rsp, Q(STOP))
        uc.reg_write(REG("rsp"), entry_rsp)
        uc.reg_write(REG("rcx"), owner)
        saved = {name: 0xabcdef0000+i for i, name in enumerate(NONVOL)}
        saved.update({f"xmm{i}": (1 << 100)+i for i in range(6, 16)})
        for name, value in saved.items(): uc.reg_write(REG(name), value)
        events = []
        by_address = {v: k for k, v in CALLBACKS.items()}

        def hook(vm, address, size, unused):
            if address == STOP:
                vm.emu_stop()
                return
            if address not in by_address: return
            name = by_address[address]
            rsp = vm.reg_read(REG("rsp"))
            self.assertEqual(rsp % 16, 8, name)
            args = tuple(vm.reg_read(REG(n)) for n in ("rcx", "rdx", "r8"))
            events.append((name, args))
            if name in ("resolver", "mode", "identity"):
                self.assertEqual(args[0], OWNER)
            if name == "resolver": value = SIDE if resolved else 0
            elif name == "mode": value = int(mode)
            elif name == "identity": value = 1
            elif name == "lookup":
                self.assertEqual((args[0], args[2]), (platform, OWNER))
                value = 0 if args[1] in missing else args[1]+0x1000
            else:
                value = 42 if args[0]-0x1000 in invalid else 0
            target = struct.unpack("<Q", bytes(vm.mem_read(rsp, 8)))[0]
            vm.mem_write(rsp+8, b"\xa5"*32)
            for n in ("rcx", "rdx", "r8", "r9", "r10", "r11"):
                vm.reg_write(REG(n), 0xfefefefe)
            for i in range(6): vm.reg_write(REG(f"xmm{i}"), 0xfefefefe)
            vm.reg_write(REG("rax"), value)
            vm.reg_write(REG("rsp"), rsp+8)
            vm.reg_write(REG("rip"), target)

        uc.hook_add(UC_HOOK_CODE, hook)
        uc.emu_start(code_address, STOP, count=10000)
        self.assertEqual(uc.reg_read(REG("rip")), STOP)
        self.assertEqual(uc.reg_read(REG("rsp")), entry_rsp+8)
        for name, value in saved.items(): self.assertEqual(uc.reg_read(REG(name)), value, name)
        self.assertEqual(bytes(uc.mem_read(OWNER, 0x20000)), data_before)
        result = uc.reg_read(REG("eax"))
        return result if result < (1 << 31) else result-(1 << 32), events

    def test_four_compatible_and_five_to_eight(self):
        for count in range(9):
            for mode in (False, True):
                with self.subTest(count=count, mode=mode):
                    ids = tuple(range(1, count+1))
                    want = evaluate(OwnerState(0x12340000, True), MemberSidecar(ids),
                                    local_id=1, flag_nonzero=mode, mode_enum=0,
                                    lookup=lambda p, i: i+0x1000, validate=lambda t: 0)
                    got, events = self.execute(ids, mode=mode)
                    self.assertEqual(got, want)
                    self.assertEqual(sum(n == "lookup" for n, _ in events), max(0, count-1))

    def test_failures_and_relocated_code(self):
        for ids, kwargs, want in (
            ((1, 2, 3), {"missing": (3,)}, -1),
            ((1, 2, 3), {"invalid": (3,)}, 0),
            ((2, 3), {}, -1), ((1, 1, 2), {}, -1),
            ((1, 2), {"ready": False}, -1),
            ((1,), {"platform": 0}, 1),
            ((1,), {"resolved": False}, -1),
            ((1,), {"owner": 0}, -1),
            ((1,), {"count": 9}, -1),
            ((1,), {"count": 0xffffffff}, -1),
            (tuple(range(1, 9)), {"code_address": 0x60000000}, 1),
        ):
            with self.subTest(ids=ids, kwargs=kwargs):
                got, events = self.execute(ids, **kwargs)
                self.assertEqual(got, want)
                if "count" in kwargs or "resolved" in kwargs or "owner" in kwargs:
                    self.assertFalse(any(n == "lookup" for n, _ in events))

    def test_address_binding_rejects_partial_and_overlap(self):
        defaults = dict(game_base=GAME, code_address=CODE,
                        unwind_address=CODE+0x1000, callbacks=CALLBACKS)
        for change in ({"callbacks": {}}, {"callbacks": SENTINELS},
                       {"code_address": GAME}, {"unwind_address": CODE},
                       {"code_address": True}, {"game_base": GAME+1},
                       {"unwind_address": CODE+(1 << 32)},
                       {"callbacks": {**CALLBACKS, "mode": CODE+0x10}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                bind_candidate(EVIDENCE, **{**defaults, **change})

    def test_unwind_at_each_prologue_instruction_boundary(self):
        b = bind_candidate(EVIDENCE, game_base=GAME, code_address=CODE,
                           unwind_address=CODE+0x1000, callbacks=CALLBACKS)
        code, info = bytes.fromhex(b["code_hex"]), bytes.fromhex(b["unwind_hex"])
        # Independently specified instruction ends from the x64 encodings.
        ends = [0, 1, 2, 3, 4, 6, 8, 10, 12, 16]
        for end in ends:
            uc = Uc(UC_ARCH_X86, UC_MODE_64)
            uc.mem_map(CODE, 0x1000); uc.mem_write(CODE, code)
            uc.mem_map(STACK, 0x10000)
            entry_rsp = STACK+0x8008
            uc.reg_write(REG("rsp"), entry_rsp)
            uc.mem_write(entry_rsp, Q(STOP))
            for i, n in enumerate(NONVOL): uc.reg_write(REG(n), 0xabcd0000+i)
            if end: uc.emu_start(CODE, CODE+end)
            rsp = uc.reg_read(REG("rsp"))
            registers = {i: uc.reg_read(REG(n)) for i, n in
                         ((3, "rbx"), (5, "rbp"), (6, "rsi"), (7, "rdi"),
                          (12, "r12"), (13, "r13"), (14, "r14"), (15, "r15"))}
            for offset, op in zip(info[4:22:2], info[5:22:2]):
                if offset > end: continue
                if (op & 15) == 2: rsp += (op >> 4)*8+8
                else:
                    self.assertEqual(op & 15, 0)
                    registers[op >> 4] = struct.unpack("<Q", bytes(uc.mem_read(rsp, 8)))[0]
                    rsp += 8
            self.assertEqual(rsp, entry_rsp)
            self.assertEqual(list(registers.values()), [0xabcd0000+i for i in range(8)])
        self.assertEqual(struct.unpack("<III", bytes.fromhex(b["runtime_function_hex"])),
                         (0, len(code), 0x1000))


if __name__ == "__main__": unittest.main(verbosity=2)
