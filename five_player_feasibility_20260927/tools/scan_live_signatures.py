"""Bounded, read-only scan for fixed-build native signatures.

The scanner only uses VirtualQueryEx and ReadProcessMemory with
PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. It never calls a game function,
changes memory, loads a DLL, or installs a hook. The scan is evidence about
one process state; no hit is not proof that a function is absent in another
state.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path

SIGNATURES = {
    "host_join": bytes.fromhex("405553564154488d6c24e94881ecc8000000"),
    "member_enum": bytes.fromhex(
        "40534883ec20488bd9488b094885c97e080fb702f30f104204f30f59c7"
    ),
}


class MemoryInfo(C.Structure):
    _fields_ = [
        ("base", C.c_void_p),
        ("allocation", C.c_void_p),
        ("allocation_protect", W.DWORD),
        ("partition", W.WORD),
        ("size", C.c_size_t),
        ("state", W.DWORD),
        ("protect", W.DWORD),
        ("kind", W.DWORD),
    ]


def scan(pid: int, limit_mib: int) -> dict:
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.ReadProcessMemory.argtypes = [
        W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)
    ]
    kernel.ReadProcessMemory.restype = W.BOOL
    kernel.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t]
    kernel.VirtualQueryEx.restype = C.c_size_t

    handle = kernel.OpenProcess(0x0410, False, pid)
    if not handle:
        raise C.WinError(C.get_last_error())
    scanned = 0
    regions = 0
    hits: list[dict] = []
    limit = limit_mib * 1024 * 1024
    address = 0x10000
    try:
        while address < 0x800000000000 and scanned < limit:
            info = MemoryInfo()
            result = kernel.VirtualQueryEx(
                handle, C.c_void_p(address), C.byref(info), C.sizeof(info)
            )
            if result != C.sizeof(info) or not info.size:
                break
            base = int(info.base)
            end = base + int(info.size)
            executable_image = (
                info.state == 0x1000
                and info.kind == 0x1000000
                and (info.protect & 0xFF) in (0x20, 0x40, 0x80)
                and not (info.protect & 0x100)
            )
            if executable_image:
                regions += 1
                cursor = base
                while cursor < end and scanned < limit:
                    amount = min(0x10000, end - cursor)
                    buffer = C.create_string_buffer(amount)
                    copied = C.c_size_t()
                    if kernel.ReadProcessMemory(
                        handle, C.c_void_p(cursor), buffer, amount, C.byref(copied)
                    ) and copied.value == amount:
                        data = buffer.raw
                        scanned += amount
                        for name, signature in SIGNATURES.items():
                            start = 0
                            while True:
                                offset = data.find(signature, start)
                                if offset < 0:
                                    break
                                hits.append(
                                    {
                                        "name": name,
                                        "address": hex(cursor + offset),
                                        "region": hex(base),
                                        "region_size": hex(int(info.size)),
                                        "signature_sha256": hashlib.sha256(signature).hexdigest(),
                                    }
                                )
                                start = offset + 1
                    cursor += amount
            address = end
    finally:
        kernel.CloseHandle(handle)

    return {
        "schema_version": 1,
        "build": 25480438,
        "pid": pid,
        "scan": "VirtualQueryEx committed executable image regions; ReadProcessMemory only",
        "limit_mib": limit_mib,
        "bytes_scanned": scanned,
        "regions_scanned": regions,
        "signatures": {
            name: {"length": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            for name, value in SIGNATURES.items()
        },
        "hits": hits,
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit-mib", type=int, default=256)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite output")
    result = scan(args.pid, args.limit_mib)
    result["interpretation"] = (
        "No hit is process-state evidence only; it does not prove a function is absent "
        "from another loaded state."
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "hits": len(result["hits"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
