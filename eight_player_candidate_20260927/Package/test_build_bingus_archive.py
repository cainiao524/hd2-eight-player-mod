from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("build_bingus_archive", HERE / "build_bingus_archive.py")
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def read_resources(data: bytes) -> dict[int, bytes]:
    count = struct.unpack_from("<I", data, 8)[0]
    result: dict[int, bytes] = {}
    for index in range(count):
        row = struct.unpack_from("<7Q6I", data, 104 + index * 80)
        name_hash, kind, offset, length = row[0], row[1], row[2], row[7]
        assert kind == builder.ARCHIVE_TYPE
        assert offset % 16 == 0 and offset + length <= len(data)
        body_length, version = struct.unpack_from("<II", data, offset)
        assert version == 2 and body_length == length - 8
        result[name_hash] = data[offset + 8:offset + length]
    return result


class BingusArchiveTests(unittest.TestCase):
    def test_build_is_deterministic_and_declares_only_menu(self):
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "first.zip"
            second = Path(td) / "second.zip"
            report1 = builder.build_package(HERE / "data/mods/cainiao", first)
            report2 = builder.build_package(HERE / "data/mods/cainiao", second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(report1["archive_sha256"], report2["archive_sha256"])
            with zipfile.ZipFile(first) as package:
                self.assertEqual(
                    sorted(package.namelist()),
                    [
                        "Addon/9ba626afa44a3aa3.patch_0",
                        "Addon/9ba626afa44a3aa3.patch_0.gpu_resources",
                        "Addon/9ba626afa44a3aa3.patch_0.stream",
                        "HD2-Player-Capacity-manifest.json",
                        "manifest.json",
                    ],
                )
                manifest = json.loads(package.read("manifest.json"))
                self.assertEqual(manifest["Dependencies"][0]["Name"], "Bingus Shared Loader")
                resources = read_resources(package.read("Addon/9ba626afa44a3aa3.patch_0"))
            self.assertEqual(len(resources), 4)
            menu = resources[builder.resource_hash(builder.ENTRY)]
            self.assertTrue(menu.startswith(b"-- HD2-Addon: " + builder.ENTRY.encode() + b"\n"))
            for name in builder.MODULES:
                body = resources[builder.resource_hash(name)]
                self.assertFalse(body.startswith(b"-- HD2-Addon:"), name)

    def test_invalid_private_module_and_entry_are_rejected(self):
        with self.assertRaises(ValueError):
            builder.module_source(builder.ENTRY, b"-- HD2-Addon: " + builder.ENTRY.encode() + b"\n")
        with self.assertRaises(ValueError):
            builder.entry_source(builder.ENTRY, b"\xef\xbb\xbfreturn true\n")
        with self.assertRaises(ValueError):
            builder.entry_source("mods/codex/loader", b"return true\n")


if __name__ == "__main__":
    unittest.main()
