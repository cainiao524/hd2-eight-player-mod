"""Prepare a bounded interface observation for HD2 build 25480438.

Default/--plan is offline. --capture --pid N reads an explicitly chosen process;
it does not start a game, load an addon, call game functions, or change memory.
Runtime execution is a separate research step, not covered by offline tests.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

BUILD = 25480438
HASHES = {
    "helldivers2.exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game.dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}
PINS = (
    (0x108C18F, 76, "e56eba5ea8a480553db61f70a65f1e036bd9ef81946ad7c8208832e1c700858a"),
    (0x4EDAA4, 36, "3647ce88ba32769a28256de285303692863403e763ee6bffcdca69a3f0320562"),
)
API_RVA, CONFIG_RVA = 0x3326308, 0x3326340
TABLE_SLOTS = {0x30: (0x18,), 0xF8: (0xA0,)}
CODE_BYTES, READ_BUDGET = 256, 65536


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pointer(value):
    require(0x10000 <= value < 0x800000000000, "Null or non-user pointer")
    return value


def owner(modules, address, size=1):
    matches = [m for m in modules if m["base"] <= address
               and address + size <= m["base"] + m["size"]]
    require(len(matches) == 1, "Address does not belong to one enumerated image")
    return matches[0]


def pe_identity(header):
    require(len(header) == 4096 and header[:2] == b"MZ", "Invalid PE header page")
    pe = struct.unpack_from("<I", header, 0x3C)[0]
    require(64 <= pe <= 4096 - 88 and header[pe:pe+4] == b"PE\0\0", "Invalid PE offset/signature")
    machine, _, timestamp = struct.unpack_from("<HHI", header, pe + 4)
    require(machine == 0x8664 and struct.unpack_from("<H", header, pe + 24)[0] == 0x20B,
            "Expected x64 PE32+ image")
    return {"timestamp": timestamp, "image_size": struct.unpack_from("<I", header, pe + 80)[0]}


def check_files(modules, executable):
    selected = {}
    for name, expected in HASHES.items():
        found = [m for m in modules if Path(m["path"]).name.lower() == name]
        require(len(found) == 1, "Expected exactly one loaded " + name)
        module = found[0]
        path = Path(module["path"]).resolve(strict=True)
        if name == "helldivers2.exe":
            require(path == Path(executable).resolve(strict=True), "Executable path mismatch")
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            header = handle.read(4096)
            handle.seek(0)
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
            after = os.fstat(handle.fileno())
        final = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino) ==
                (final.st_size, final.st_mtime_ns, final.st_ino), "File changed during hashing")
        require(actual == expected, "Unsupported file fingerprint: " + name)
        identity = pe_identity(header)
        require(identity["image_size"] == module["size"], "Loaded image size mismatch")
        selected[name] = {**module, "sha256": actual, "pe_identity": identity}
    return selected


def verify_loaded(reader, selected):
    for module in selected.values():
        require(pe_identity(reader.read(module["base"], 4096)) == module["pe_identity"],
                "Loaded PE identity mismatch")
    base = selected["game.dll"]["base"]
    for rva, size, expected in PINS:
        require(digest(reader.read(base + rva, size)) == expected,
                "Loaded code pin mismatch at " + hex(rva))


def observe(reader, game_base, modules):
    """Reader injection permits offline tests without loading any Windows DLL."""
    watched = []

    def read_field(address, size, label):
        raw = reader.read(pointer(address), size)
        require(len(raw) == size, "Short field read")
        watched.append((address, raw, label))
        return int.from_bytes(raw, "little")

    result = {"api_global_rva": hex(API_RVA), "config_global_rva": hex(CONFIG_RVA),
              "tables": [], "atomic_snapshot": False, "eight_player_verified": False}
    root = pointer(read_field(game_base + API_RVA, 8, "api_root"))
    config = pointer(read_field(game_base + CONFIG_RVA, 8, "config_root"))
    result["api_root"] = hex(root)
    result["config_root"] = hex(config)
    result["config_plus_20_u32"] = read_field(config + 0x20, 4, "config_plus_20")
    for offset, slots in TABLE_SLOTS.items():
        table = pointer(read_field(root + offset, 8, f"table_{offset:x}"))
        row = {"root_offset": hex(offset), "table": hex(table), "functions": []}
        for slot in slots:
            target = pointer(read_field(table + slot, 8, f"slot_{offset:x}_{slot:x}"))
            module = owner(modules, target)
            size = min(CODE_BYTES, module["base"] + module["size"] - target)
            code = reader.read(target, size, executable=True)
            require(len(code) == size, "Short code read")
            row["functions"].append({"slot": hex(slot), "address": hex(target),
                "module": module["path"], "module_rva": hex(target - module["base"]),
                "size": size, "bytes": code.hex(), "sha256": digest(code),
                "interpretation": "Function pointer and prefix only; ABI/semantics unverified"})
        result["tables"].append(row)
    changed = []
    for address, raw, label in watched:
        if reader.read(address, len(raw)) != raw:
            changed.append(label)
    result["observed_fields_unchanged_on_reread"] = not changed
    result["changed_fields"] = changed
    result["field_samples"] = [{"label": label, "address": hex(address), "bytes": raw.hex()}
                               for address, raw, label in watched]
    result["limitations"] = ["Unchanged rereads cannot exclude intervening changes or address reuse.",
        "No function invocation, service response, RPC trace, player data, or gameplay validation.",
        "Function prefixes may be stubs; no automatic pointer or branch following."]
    return result


class WindowsReader:
    def __init__(self, pid):
        require(sys.platform == "win32" and C.sizeof(C.c_void_p) == 8, "Requires 64-bit Windows Python")
        require(0 < pid <= 0xFFFFFFFF, "Invalid explicit PID")
        self.used = 0
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.p = C.WinDLL("psapi", use_last_error=True)
        self.k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        self.k.OpenProcess.restype = W.HANDLE
        self.k.CloseHandle.argtypes = [W.HANDLE]
        self.k.CloseHandle.restype = W.BOOL
        self.k.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
        self.k.ReadProcessMemory.restype = W.BOOL
        self.k.VirtualQueryEx.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t]
        self.k.VirtualQueryEx.restype = C.c_size_t
        self.k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
        self.k.QueryFullProcessImageNameW.restype = W.BOOL
        self.p.EnumProcessModulesEx.argtypes = [W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD), W.DWORD]
        self.p.EnumProcessModulesEx.restype = W.BOOL
        self.p.GetModuleInformation.argtypes = [W.HANDLE, W.HMODULE, C.c_void_p, W.DWORD]
        self.p.GetModuleInformation.restype = W.BOOL
        self.p.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]
        self.p.GetModuleFileNameExW.restype = W.DWORD
        # Only QUERY_INFORMATION | VM_READ. No privilege adjustment or retry.
        self.handle = self.k.OpenProcess(0x0410, False, pid)
        if not self.handle:
            raise C.WinError(C.get_last_error())

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None

    def executable(self):
        buf, count = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not self.k.QueryFullProcessImageNameW(self.handle, 0, buf, C.byref(count)):
            raise C.WinError(C.get_last_error())
        require(Path(buf.value).name.lower() == "helldivers2.exe", "PID is not Helldivers 2")
        return buf.value

    def modules(self):
        class ModuleInfo(C.Structure):
            _fields_ = [("base", C.c_void_p), ("size", W.DWORD), ("entry", C.c_void_p)]
        array, needed = (W.HMODULE * 2048)(), W.DWORD()
        if not self.p.EnumProcessModulesEx(self.handle, array, C.sizeof(array), C.byref(needed), 3):
            raise C.WinError(C.get_last_error())
        require(0 < needed.value <= C.sizeof(array) and needed.value % 8 == 0, "Module enumeration changed/overflowed")
        result = []
        for module in array[:needed.value // 8]:
            info, path = ModuleInfo(), C.create_unicode_buffer(32768)
            if not self.p.GetModuleInformation(self.handle, module, C.byref(info), C.sizeof(info)):
                raise C.WinError(C.get_last_error())
            length = self.p.GetModuleFileNameExW(self.handle, module, path, len(path))
            require(0 < length < len(path), "Module path unavailable/truncated")
            result.append({"base": pointer(info.base), "size": info.size, "path": path.value})
        return sorted(result, key=lambda item: item["base"])

    def read(self, address, size, executable=False):
        class MemoryInfo(C.Structure):
            _fields_ = [("base", C.c_void_p), ("allocation", C.c_void_p),
                ("allocation_protect", W.DWORD), ("partition", W.WORD),
                ("size", C.c_size_t), ("state", W.DWORD), ("protect", W.DWORD), ("kind", W.DWORD)]
        pointer(address)
        require(self.handle and 0 < size <= 4096 and address + size <= 0x800000000000, "Invalid bounded read")
        require(self.used + size <= READ_BUDGET, "Read budget exceeded")
        self.used += size
        result = bytearray()
        cursor = address
        while cursor < address + size:
            info = MemoryInfo()
            count = self.k.VirtualQueryEx(self.handle, cursor, C.byref(info), C.sizeof(info))
            require(count == C.sizeof(info), "Memory query failed")
            allowed = (0x20, 0x40, 0x80) if executable else (2, 4, 8, 0x20, 0x40, 0x80)
            require(info.state == 0x1000 and not (info.protect & 0x100)
                    and (info.protect & 0xFF) in allowed, "Unreadable/guard/non-executable region")
            require(info.base <= cursor < info.base + info.size, "Malformed region")
            if executable:
                require(info.kind == 0x1000000, "Function target is not an image region")
            amount = min(address + size - cursor, info.base + info.size - cursor)
            buffer, copied = C.create_string_buffer(amount), C.c_size_t()
            if not self.k.ReadProcessMemory(self.handle, cursor, buffer, amount, C.byref(copied)):
                raise C.WinError(C.get_last_error())
            require(copied.value == amount, "Short process read")
            result.extend(buffer.raw)
            cursor += amount
        return bytes(result)


def plan():
    return {"mode": "offline_plan", "build": BUILD, "file_sha256": HASHES,
        "code_pins": [{"rva": hex(r), "size": n, "sha256": h} for r, n, h in PINS],
        "pointer_paths": ["game.dll+0x3326308 -> +0x30 -> +0x18",
                          "game.dll+0x3326308 -> +0xf8 -> +0xa0",
                          "game.dll+0x3326340 -> +0x20 (u32)"],
        "code_prefix_limit": CODE_BYTES, "total_memory_read_limit": READ_BUDGET,
        "runtime_tested": False, "eight_player_mod": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--capture", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.capture:
        require(args.pid is None and args.output is None, "PID/output require --capture")
        print(json.dumps(plan(), indent=2))
        return
    require(args.pid is not None and args.output is not None, "Capture requires explicit --pid and new --output")
    require(not args.output.exists(), "Refusing to overwrite output")
    reader = WindowsReader(args.pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = check_files(modules, executable)
        verify_loaded(reader, selected)
        report = observe(reader, selected["game.dll"]["base"], modules)
        verify_loaded(reader, selected)
        require(reader.executable() == executable and reader.modules() == modules, "Process image/module list changed")
        require(check_files(modules, executable) == selected, "Disk identity changed")
        report.update({"schema_version": 1, "build": BUILD, "pid": args.pid,
            "utc": datetime.now(timezone.utc).isoformat(), "pinned_images": selected,
            "modules": modules, "memory_bytes_read": reader.used, "runtime_capture": True,
            "utility_file_sha256_at_output": digest(Path(__file__).read_bytes())})
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(str(args.output.resolve()))
    finally:
        reader.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
