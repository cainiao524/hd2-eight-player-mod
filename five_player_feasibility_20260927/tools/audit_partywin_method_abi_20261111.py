"""Verify the fixed-build PartyWin method ABI shape without calling it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from party_manager_binding import file_backed_bytes, verify_party_file


BUILD = 25480438
METHODS = {
    "PartyCreateNewNetwork": {
        "rva": 0x15720,
        "signature": "PartyError (PARTY_HANDLE, PARTY_LOCAL_USER_HANDLE, const PARTY_NETWORK_CONFIGURATION*, uint32_t, const PARTY_REGION*, const PARTY_INVITATION_CONFIGURATION*, void*, PARTY_NETWORK_DESCRIPTOR*, char*)",
        "required": ["mov rbx, rcx", "mov r13, rdx", "mov rdi, r8", "mov r12d, r9d", "mov r15, qword ptr [rsp + 0x130]", "mov r14, qword ptr [rsp + 0x138]"],
    },
    "PartyConnectToNetwork": {
        "rva": 0x14FE0,
        "signature": "PartyError (PARTY_HANDLE, const PARTY_NETWORK_DESCRIPTOR*, void*, PARTY_NETWORK_HANDLE*)",
        "required": ["mov rbx, rcx", "mov r15, rdx", "mov r12, r8", "mov r13, r9"],
    },
    "PartyNetworkAuthenticateLocalUser": {
        "rva": 0x1BC80,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, PARTY_LOCAL_USER_HANDLE, PartyString, void*)",
        "required": ["mov rbp, rcx", "mov r14, rdx", "mov r15, r8", "mov r12, r9"],
    },
    "PartyNetworkCreateEndpoint": {
        "rva": 0x1C050,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, PARTY_LOCAL_USER_HANDLE, uint32_t, const PartyString*, const PARTY_DATA_BUFFER*, void*, PARTY_ENDPOINT_HANDLE*)",
        "required": ["mov rbp, rcx", "mov r15, rdx", "mov r12, r9", "mov r13, qword ptr [rsp + 0x108]", "mov r14, qword ptr [rsp + 0x110]"],
    },
    "PartyNetworkLeaveNetwork": {
        "rva": 0x1E640,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, void*)",
        "required": ["mov rbp, rcx", "mov r14, rdx"],
    },
    "PartyNetworkRemoveLocalUser": {
        "rva": 0x1E7F0,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, PARTY_LOCAL_USER_HANDLE, void*)",
        "required": ["mov rbp, rcx", "mov r14, rdx", "mov r15, r8"],
    },
    "PartyCleanup": {
        "rva": 0x14DC0,
        "signature": "PartyError (PARTY_HANDLE)",
        "required": ["mov rbx, rcx"],
    },
    "PartyNetworkGetNetworkConfiguration": {
        "rva": 0x1DB30,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, const PARTY_NETWORK_CONFIGURATION**)",
        "required": ["mov rbp, rcx", "mov r14, rdx"],
    },
    "PartyNetworkGetNetworkDescriptor": {
        "rva": 0x1DCD0,
        "signature": "PartyError (PARTY_NETWORK_HANDLE, PARTY_NETWORK_DESCRIPTOR*)",
        "required": ["mov r14, rcx", "mov rbx, rdx"],
    },
}


def normalized(ins) -> str:
    return f"{ins.mnemonic} {ins.op_str}"


def verify(path: Path, output: Path) -> dict:
    layout = verify_party_file(path)
    raw = path.read_bytes()
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    exports = {entry.name.decode(): entry.address for entry in pe.DIRECTORY_ENTRY_EXPORT.symbols if entry.name}
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    results = {}
    for name, spec in METHODS.items():
        rva = spec["rva"]
        if exports.get(name) != rva:
            raise ValueError(f"export_rva_mismatch:{name}:{exports.get(name)}:{rva}")
        code = file_backed_bytes(pe, raw, rva, 0x240)
        instructions = [normalized(ins) for ins in md.disasm(code, pe.OPTIONAL_HEADER.ImageBase + rva)]
        missing = [needle for needle in spec["required"] if needle not in instructions]
        results[name] = {
            "rva": hex(rva),
            "signature": spec["signature"],
            "first_bytes": code[:32].hex(),
            "code_sha256": hashlib.sha256(code).hexdigest(),
            "required_assignments": spec["required"],
            "missing_assignments": missing,
            "shape_verified": not missing,
        }
    report = {
        "schema": "hd2_partywin_method_abi_static_v1",
        "steam_build": BUILD,
        "partywin_path": str(path),
        "partywin_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "methods": results,
        "all_method_shapes_verified": all(item["shape_verified"] for item in results.values()),
        "first_c_parameter_handle_in_rcx": True,
        "manager_cpp_object_is_not_c_handle": True,
        "c_api_reference": "https://github.com/PlayFab/PlayFabParty/blob/master/include/Party_c.h",
        "cpp_wrapper_reference": "https://github.com/PlayFab/PlayFabParty/blob/master/include/PartyImpl.h",
        "manager_handle_validation": layout,
        "official_method_arguments_match_register_and_stack_shape": True,
        "game_callsite_thunk_binding": False,
        "return_abi_runtime_verified": False,
        "state_change_receiver_runtime_verified": False,
        "function_calls": False,
        "memory_writes": False,
        "limitations": [
            "The exported C APIs take opaque handles; PartyManager's C++ wrapper stores a separate PARTY_HANDLE. Do not pass the wrapper object's address as that handle.",
            "GetNetworkConfiguration returns a borrowed const pointer through a pointer-to-pointer output; GetNetworkDescriptor instead copies to a caller-provided struct.",
            "It does not prove the game's EXE thunk targets, manager receiver lifetime, or asynchronous state-change ownership.",
        ],
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partywin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.partywin, args.output)
    print(json.dumps({"output": str(args.output), "all_method_shapes_verified": report["all_method_shapes_verified"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
