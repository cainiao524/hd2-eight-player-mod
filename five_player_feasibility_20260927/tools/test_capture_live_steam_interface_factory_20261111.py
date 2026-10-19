"""Offline tests for the Steam interface-factory callsite decoder."""

from __future__ import annotations

import struct
from pathlib import Path
import sys
import unittest

import capstone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capture_live_steam_interface_factory_20261111 as capture


class FakeReader:
    def __init__(self, regions):
        self.regions = regions

    def read(self, address, size, executable=False):
        for start, data in self.regions.items():
            if start <= address and address + size <= start + len(data):
                offset = address - start
                return data[offset:offset + size]
        raise ValueError(f"unmapped read: {address:#x}+{size:#x}")


class DecoderTests(unittest.TestCase):
    def test_rip_target_decodes_interface_name_and_return_store(self):
        exe = 0x100000
        call = exe + 0x80
        iat = 0x200000
        name = 0x300000
        result_slot = exe + 0x400
        blob = bytearray(b"\x90" * 0x180)
        # lea rdx, [rip + name - next]
        lea_address = exe + 0x70
        lea = b"\x48\x8D\x15" + struct.pack("<i", name - (lea_address + 7))
        blob[0x70:0x70 + len(lea)] = lea
        # call qword ptr [rip + iat - next]
        call_bytes = b"\xFF\x15" + struct.pack("<i", iat - (call + 6))
        blob[0x80:0x80 + len(call_bytes)] = call_bytes
        # mov [rip + result_slot - next], rax
        store = b"\x48\x89\x05" + struct.pack("<i", result_slot - (call + 6 + 7))
        blob[0x86:0x86 + len(store)] = store
        modules = [
            {"base": exe, "size": 0x1000, "path": "helldivers2.exe"},
            {"base": iat, "size": 0x1000, "path": "steam_api64.dll"},
            {"base": name, "size": 0x1000, "path": "helldivers2.exe"},
        ]
        reader = FakeReader({name: b"SteamMatchmaking009\x00" + b"\x00" * 108})
        report = capture.callsite_details(reader, call, bytes(blob), exe, modules, exe)
        self.assertEqual(report["iat_target"]["address"], hex(iat))
        self.assertEqual(report["iat_target"]["owner"]["module"], "steam_api64.dll")
        self.assertEqual(report["candidate_interface_strings"][0]["text"], "SteamMatchmaking009")
        self.assertEqual(report["candidate_return_stores"][0]["address"], hex(result_slot))

    def test_no_false_interface_string_for_non_ascii_data(self):
        reader = FakeReader({0x300000: b"\x01\x02" + b"\x00" * 126})
        modules = [{"base": 0x300000, "size": 0x1000, "path": "helldivers2.exe"}]
        self.assertIsNone(capture.ascii_candidate(reader, 0x300000, modules))


if __name__ == "__main__":
    unittest.main()
