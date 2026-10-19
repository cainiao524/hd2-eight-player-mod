"""Replay saved wrapper prefixes only, stopping at the first unavailable read.

Inputs are recovered historical bytes and pinned workspace receipts. Unicorn
executes them in isolated emulated memory; this tool has no live-game reader,
native-call backend, or fallback that invents the missing data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eight_player_candidate_20260927/.native-test-deps"))
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_MEM_READ_UNMAPPED, UC_ERR_READ_UNMAPPED
from unicorn.x86_const import UC_X86_REG_RSP, UC_X86_REG_RIP

DATA = ROOT / "output/native_dispatch_20261010"
RECOVERED = DATA / "recovered_party_windows_20261015"
EXPECTED_READS = {
    "create_network_candidate": 0x2985447,
    "async_or_state_candidate": 0x2985527,
    "authenticate_or_state_candidate": 0x29848A7,
    "create_endpoint_candidate": 0x2984B7F,
    "connect_network_candidate": 0x2984C3F,
    "auth_network_candidate": 0x298568F,
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pinned_json(name: str, expected: str) -> dict:
    raw = (DATA / name).read_bytes()
    if digest(raw) != expected:
        raise ValueError(f"saved receipt fingerprint mismatch: {name}")
    return json.loads(raw)


def analyze() -> dict:
    r13 = pinned_json("live_party_api_pointer_probe_20261011_r13.json",
                      "10fe30287ba16eedae2c6ebb48a99cae71215e20ab8bf5275ead65564d30433f")
    r5 = pinned_json("live_party_jump_chains_20261111_pid38492_r5.json",
                     "dd41ee4dd10021cb2b5e91bba9702d2e5abb5b98698f6bc717017b41d8ea5254")
    manifest = json.loads((RECOVERED / "manifest.json").read_text(encoding="utf-8"))
    base = int(r13["probe"]["exe_base"], 16)
    rows = []
    for label, expected_read in EXPECTED_READS.items():
        recovered = next(r for r in manifest["windows"] if r["label"] == label and r["depth"] == 1)
        pin = next(r for r in r13["jump_chain_4096_windows"] if r["label"] == label and r["depth"] == 1)
        code = (RECOVERED / recovered["file"]).read_bytes()
        if len(code) != 4096 or digest(code) != pin["sha256"]:
            raise ValueError(f"recovered wrapper fingerprint mismatch: {label}")
        start = int(pin["address"], 16)
        helper = next(c for c in r5["chains"] if c["label"] == label)["hops"][-1]["direct_relative_calls"][0]
        helper_code = bytes.fromhex(helper["code"])
        target = int(helper["target"], 16)
        helper_pin = next(r for r in r13["heuristic_direct_call_targets"] if int(r["target"], 16) == target)
        if digest(helper_code[:128]) != helper_pin["code128_sha256"]:
            raise ValueError(f"helper does not match r13: {label}")
        if helper_code[:9] != bytes.fromhex("e8000000005d4881ed") or helper_code[13] != 0xC3:
            raise ValueError(f"unexpected helper body: {label}")

        emu = Uc(UC_ARCH_X86, UC_MODE_64)
        mapped = set()
        for address, raw in ((start, code), (target, helper_code[:14])):
            for page in range(address & ~4095, (address + len(raw) + 4095) & ~4095, 4096):
                if page not in mapped:
                    emu.mem_map(page, 4096)
                    mapped.add(page)
            emu.mem_write(address, raw)
        emu.mem_map(0x1000000, 0x20000)
        emu.reg_write(UC_X86_REG_RSP, 0x1010000)
        missing = []

        def stop_at_missing(machine, access, address, size, value, user_data):
            missing.append({"instruction_rva": hex(machine.reg_read(UC_X86_REG_RIP) - base),
                            "read_rva": hex(address - base), "size": size})
            return False

        emu.hook_add(UC_HOOK_MEM_READ_UNMAPPED, stop_at_missing)
        try:
            emu.emu_start(start, start + len(code), count=512)
        except UcError as error:
            if error.errno != UC_ERR_READ_UNMAPPED:
                raise
        if len(missing) != 1 or int(missing[0]["read_rva"], 16) != expected_read or missing[0]["size"] != 8:
            raise ValueError(f"unexpected prefix boundary: {label}: {missing}")
        rows.append({"label": label, "wrapper_sha256": pin["sha256"],
                     "first_unavailable_data_read": missing[0]})
    return {"schema": "hd2_saved_party_prefix_analysis_v1", "prefixes": rows,
            "scope": "offline replay of saved instructions through the first unavailable data read",
            "initial_state": "Unicorn default registers and a zeroed synthetic stack; no live register snapshot",
            "missing_values_supplied": False, "game_process_access": False,
            "native_game_calls": False, "provider_binding_proven": False,
            "runtime_verified": False, "multiplayer_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(analyze(), indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
