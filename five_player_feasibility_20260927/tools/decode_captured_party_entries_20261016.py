"""Decode the six saved PID30776 entry values in isolated emulated memory.

Only workspace files are inputs. Stop BEFORE the common indirect call; never
load a game image, open a process, invoke a native target or supply missing data.
The synthetic registers/stack are not a captured native invocation context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "output/native_dispatch_20261010"
sys.path.insert(0, str(ROOT / "eight_player_candidate_20260927/.native-test-deps"))
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM, X86_REG_RBP
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE)
from unicorn import x86_const as regs

SOURCES = {
    "party_capture_authorized_20261016_pid30776_01.json": "b5b81a890e9a0e81808bcd74a736a75ac48f59de33cf393f135ef9c5478d13ac",
    "party_capture_plan_v2_20261015.json": "3a9fae2bba12ddf680b15a45f4f5590b98329d8153c1cb93057d8685f935528e",
    "live_party_jump_chains_20261111_pid38492_r5.json": "dd41ee4dd10021cb2b5e91bba9702d2e5abb5b98698f6bc717017b41d8ea5254",
    "live_party_api_pointer_probe_20261011_r13.json": "10fe30287ba16eedae2c6ebb48a99cae71215e20ab8bf5275ead65564d30433f",
    "recovered_party_windows_20261015/manifest.json": "6fb6280868e6c16cccce899c5a47852c1226c0f31c1cf4196c3da7d4f495742b",
    "partywin_c_handle_abi_20261015.json": "87ae7faaa947ef41c05e3125437ffb2b380047f686e9e0aa864abbbf2acf3c94",
}
COMMON_SLOT_RVA = 0x2C75FEC
SEEDS = (0, 0x5555555555555555, 0xAAAAAAAAAAAAAAAA)
STACK_BASE, STACK_SIZE, STACK_POINTER = 0x1000000, 0x20000, 0x1010000
MASK64 = (1 << 64) - 1


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_json(name):
    raw = (DATA / name).read_bytes()
    if digest(raw) != SOURCES[name]:
        raise ValueError("saved source hash mismatch: " + name)
    return json.loads(raw)


def replay(exe, wrapper_rva, wrapper, helper_rva, helper, entry_rva, entry, seed=0):
    """Replay only the supplied code/data, with a deliberately synthetic stack."""
    chunks = [(exe + wrapper_rva, wrapper), (exe + helper_rva, helper), (exe + entry_rva, entry)]
    machine = Uc(UC_ARCH_X86, UC_MODE_64)
    mapped = set()
    for address, raw in chunks:
        for page in range(address & ~4095, (address + len(raw) + 4095) & ~4095, 4096):
            if page not in mapped:
                machine.mem_map(page, 4096)
                mapped.add(page)
        machine.mem_write(address, raw)
    machine.mem_map(STACK_BASE, STACK_SIZE)
    machine.mem_write(STACK_BASE, struct.pack("<Q", seed) * (STACK_SIZE // 8))
    # Distinct caller markers expose stack shifts that uniform fill would hide.
    caller_return = seed ^ 0x1111222233334444
    caller_arguments = {number: seed ^ (0x5555000000000000 + number) for number in range(5, 10)}
    machine.mem_write(STACK_POINTER, struct.pack("<Q", caller_return))
    for number, value in caller_arguments.items():
        machine.mem_write(STACK_POINTER + 0x28 + (number - 5) * 8, struct.pack("<Q", value))
    initial_registers = {}
    for index, name in enumerate(("RAX", "RBX", "RCX", "RDX", "RBP", "RSI", "RDI",
                                  "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15")):
        initial_registers[name] = (seed ^ (index * 0x0101010101010101)) & MASK64
        machine.reg_write(getattr(regs, "UC_X86_REG_" + name), initial_registers[name])
    machine.reg_write(regs.UC_X86_REG_RSP, STACK_POINTER)
    machine.reg_write(regs.UC_X86_REG_EFLAGS, 2 | (seed & 0x8D5))
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    decoder.detail = True
    result, errors, reads, trace = {}, [], [], []

    def stop_error(message):
        errors.append(message)
        machine.emu_stop()

    def on_code(m, address, size, _):
        if not any(start <= address and address + size <= start + len(raw) for start, raw in chunks[:2]):
            stop_error(f"unavailable instruction bytes at {address - exe:#x}")
            return
        instruction = next(decoder.disasm(bytes(m.mem_read(address, size)), address))
        trace.append(address - exe)
        if instruction.mnemonic != "call":
            return
        operand = instruction.operands[0]
        if operand.type == X86_OP_IMM:
            if operand.imm not in (exe + helper_rva, exe + helper_rva + 5):
                stop_error("unexpected direct call")
            return
        if (operand.type != X86_OP_MEM or operand.mem.base != X86_REG_RBP
                or operand.mem.index or operand.mem.disp != 0x2FCFEC):
            stop_error("unexpected indirect call operand")
            return
        slot = m.reg_read(regs.UC_X86_REG_RBP) + operand.mem.disp
        if slot != exe + COMMON_SLOT_RVA:
            stop_error("unexpected common call slot address")
            return
        rsp = m.reg_read(regs.UC_X86_REG_RSP)
        arguments = {
            name: {"input": hex(initial_registers[name]),
                   "before_common_call": hex(m.reg_read(getattr(regs, "UC_X86_REG_" + name)))}
            for name in ("RCX", "RDX", "R8", "R9")
        }
        stack_arguments = []
        for number, expected in caller_arguments.items():
            original_address = STACK_POINTER + 0x28 + (number - 5) * 8
            # CALL pushes 8 bytes. A plain JMP RAX would leave argument 5 at
            # (rsp - 8) + 0x28 == rsp + 0x20. This is a hypothesis, not a
            # fabricated implementation of the unavailable dispatcher.
            plain_jump_address = rsp + 0x20 + (number - 5) * 8
            stack_arguments.append({
                "argument_number": number, "input_marker": hex(expected),
                "original_slot_before_common_call": hex(int.from_bytes(m.mem_read(original_address, 8), "little")),
                "plain_jump_callee_slot": hex(int.from_bytes(m.mem_read(plain_jump_address, 8), "little")),
                "original_slot_relative_to_current_rsp": hex(original_address - rsp),
            })
        result.update(instruction_rva=hex(address - exe), call_operand=instruction.op_str,
                      common_slot_rva=hex(slot - exe), derived_rax=hex(m.reg_read(regs.UC_X86_REG_RAX)),
                      rsp_delta=rsp - STACK_POINTER,
                      argument_registers=arguments,
                      four_argument_registers_preserved=all(x["input"] == x["before_common_call"] for x in arguments.values()),
                      synthetic_caller_return=hex(caller_return),
                      caller_stack_arguments=stack_arguments,
                      dispatcher_stack_forwarding_proven=False)
        m.emu_stop()

    def on_read(m, access, address, size, value, _):
        if STACK_BASE <= address and address + size <= STACK_BASE + STACK_SIZE:
            return
        if not any(start <= address and address + size <= start + len(raw) for start, raw in chunks):
            stop_error(f"unavailable data bytes at {address - exe:#x} size={size}")
            return
        reads.append({"rva": hex(address - exe), "size": size})

    def on_write(m, access, address, size, value, _):
        if not STACK_BASE <= address or address + size > STACK_BASE + STACK_SIZE:
            stop_error("write outside synthetic stack")

    machine.hook_add(UC_HOOK_CODE, on_code)
    machine.hook_add(UC_HOOK_MEM_READ, on_read)
    machine.hook_add(UC_HOOK_MEM_WRITE, on_write)
    try:
        machine.emu_start(exe + wrapper_rva, exe + wrapper_rva + len(wrapper), count=1024)
    except UcError as error:
        raise ValueError("isolated replay stopped on unavailable/invalid execution: " + str(error)) from error
    if errors:
        raise ValueError(errors[0])
    if not result:
        raise ValueError("replay ended without the expected indirect-call boundary")
    if reads != [{"rva": hex(entry_rva), "size": 8}]:
        raise ValueError("replay used data beyond its one captured entry qword")
    return {**result, "nonstack_data_reads": reads, "instruction_count": len(trace),
            "instruction_path_sha256": digest(json.dumps(trace).encode()), "seed": hex(seed),
            "stopped_before_indirect_call": True}


def analyze():
    source = {name: checked_json(name) for name in SOURCES}
    receipt = source["party_capture_authorized_20261016_pid30776_01.json"]
    plan = source["party_capture_plan_v2_20261015.json"]
    r5 = source["live_party_jump_chains_20261111_pid38492_r5.json"]
    r13 = source["live_party_api_pointer_probe_20261011_r13.json"]
    manifest = source["recovered_party_windows_20261015/manifest.json"]
    abi = source["partywin_c_handle_abi_20261015.json"]
    exe, old_exe = int(receipt["exe_base"], 16), int(manifest["exe_base"], 16)
    party = receipt["pinned_images"]["PartyWin.dll"]
    if receipt["status"] != "captured" or party["sha256"] != abi["partywin_sha256"]:
        raise ValueError("receipt identity mismatch")
    export_names = {int(row["rva"], 16): row["name"] for row in r13["partywin_exports"]}
    for name, method in abi["methods"].items():
        export_names[int(method["rva"], 16)] = name
    rows = []
    for entry in receipt["entry_qwords"]:
        label = entry["label"]
        wrapper_pin = next(p for p in plan["fixed_memory_reads"] if p["label"] == label + "_wrapper_pin")
        helper_pin = next(p for p in plan["fixed_memory_reads"] if p["label"] == label + "_position_helper")
        recovered = next(p for p in manifest["windows"] if p["label"] == label and p["depth"] == 1)
        window = (DATA / "recovered_party_windows_20261015" / recovered["file"]).read_bytes()
        if digest(window) != recovered["sha256"] or digest(window[:1024]) != wrapper_pin["sha256"]:
            raise ValueError("saved wrapper bytes do not match the current pinned prefix")
        helper_saved = next(c for c in r5["chains"] if c["label"] == label)["hops"][-1]["direct_relative_calls"][0]
        helper = bytes.fromhex(helper_saved["code"])[:14]
        helper_rva = int(helper_saved["target"], 16) - old_exe
        if helper_rva != int(helper_pin["rva"], 16) or digest(helper) != helper_pin["sha256"]:
            raise ValueError("saved helper does not match the current pin")
        for pin in (wrapper_pin, helper_pin):
            matches = [p for p in receipt["read_ledger"] if int(p["address"], 16) == exe + int(pin["rva"], 16)
                       and p["size"] == pin["bytes_per_read"]]
            if len(matches) != 2 or any(p["sha256"] != pin["sha256"] for p in matches):
                raise ValueError("missing before/after current code verification")
        if entry["raw"] != entry["reread_raw"]:
            raise ValueError("entry changed during capture")
        runs = [replay(exe, int(wrapper_pin["rva"], 16), window[:1024], helper_rva, helper,
                       int(entry["rva"], 16), bytes.fromhex(entry["raw"]), seed) for seed in SEEDS]
        if len({(r["derived_rax"], r["instruction_rva"], r["instruction_path_sha256"]) for r in runs}) != 1:
            raise ValueError("target/path varies with synthetic initial register or stack values")
        target = int(runs[0]["derived_rax"], 16)
        if not party["base"] <= target < party["base"] + party["size"]:
            raise ValueError("decoded value is not in the pinned PartyWin image")
        target_rva = target - party["base"]
        if label == "connect_network_candidate":
            x = int(entry["value"], 16)
            independent = ((((x & 0xFFFFFFFF) - 0x38C38943) & 0xFFFFFFFF) ^ 0x5FA365AE)
            independent |= ((x >> 32) ^ 0x86A1AF6E) << 32
            if independent != target:
                raise ValueError("independent connect formula disagrees")
        rows.append({"candidate_label": label, "entry_rva": entry["rva"], "entry_value": entry["value"],
                     "derived_target": hex(target), "partywin_rva": hex(target_rva),
                     "matching_saved_export": export_names.get(target_rva),
                     "runs": runs, "actual_native_call_observed": False})
    common = receipt["common_call_slot"]
    code = bytes.fromhex(common["target_prefix"]["code"])
    if code[0] != 0xE9:
        raise ValueError("common prefix is no longer the captured direct jump")
    common_rva = int(common["value"], 16) - exe
    destination = common_rva + 5 + struct.unpack_from("<i", code, 1)[0]
    historical = next(w for w in manifest["windows"]
                      if int(w["rva"], 16) <= common_rva < int(w["rva"], 16) + int(w["size"], 16))
    raw = (DATA / "recovered_party_windows_20261015" / historical["file"]).read_bytes()
    if digest(raw) != historical["sha256"]:
        raise ValueError("historical common-entry source mismatch")
    offset = common_rva - int(historical["rva"], 16)
    if raw[offset:offset + 5] != code[:5]:
        raise ValueError("historical and current common-entry jumps differ")
    covered = [w["file"] for w in manifest["windows"]
               if int(w["rva"], 16) <= destination < int(w["rva"], 16) + int(w["size"], 16)]
    return {"schema": "hd2_saved_party_entry_decode_v2", "source_sha256": SOURCES,
            "scope": "Saved current data plus historical code whose prefix hashes were verified in the current capture; isolated emulation stops before the common call.",
            "synthetic_context": "Three different register/stack/flags patterns with distinct caller return/argument markers; same decoded target/path in all three. This is not a live register snapshot or proof of all possible inputs.",
            "stack_boundary_finding": "The four argument registers are preserved at the common call in all saved cases, but RSP is entry RSP minus 32. Under a plain JMP RAX hypothesis, native argument 5 would be the original caller return marker, not original argument 5. The unavailable dispatcher must not be replaced with that assumed implementation, especially for CreateNewNetwork/CreateEndpoint stack arguments.",
            "decoded_entries": rows,
            "common_jump": {"entry_rva": hex(common_rva), "destination_rva": hex(destination),
                            "same_first_jump_in_historical_window": historical["file"],
                            "destination_in_recovered_12_windows": covered,
                            "jump_followed": False, "destination_bytes_available_in_this_analysis": bool(covered)},
            "unnamed_rvas": [r["partywin_rva"] for r in rows if r["matching_saved_export"] is None],
            "native_game_calls": False, "new_game_reads": 0, "provider_binding_proven": False,
            "runtime_verified": False, "multiplayer_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze()
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(content)
        print(json.dumps({"output": str(args.output), "decoded_entries": len(report["decoded_entries"]),
                          "unnamed_rvas": report["unnamed_rvas"], "new_game_reads": 0}))
    else:
        print(content, end="")
