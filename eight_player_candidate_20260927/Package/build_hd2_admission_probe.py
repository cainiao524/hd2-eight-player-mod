"""Build the temporary read-only HD2Scanner admission probe addon."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
import zipfile


ARCHIVE = "9ba626afa44a3aa3.patch_0"
ARCHIVE_TYPE = 0xA14E8DFA2CD117E2
GUID = "55b2c4d6-7e8f-4091-a2b3-c4d5e6f70819"
ENTRY = "mods/cainiao/hd2_admission_probe"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resource_hash(name: str) -> int:
    raw = name.encode("utf-8")
    mask = (1 << 64) - 1
    mix = 0xC6A4A7935BD1E995
    value = len(raw) * mix & mask
    end = len(raw) // 8 * 8
    for (word,) in struct.iter_unpack("<Q", raw[:end]):
        word = word * mix & mask
        word ^= word >> 47
        value = (value ^ (word * mix & mask)) * mix & mask
    if raw[end:]:
        value = (value ^ int.from_bytes(raw[end:], "little")) * mix & mask
    value ^= value >> 47
    value = value * mix & mask
    return value ^ (value >> 47)


def make_archive(resource: bytes) -> bytes:
    resource = struct.pack("<II", len(resource), 2) + resource
    offset = (104 + 80 + 15) & ~15
    body = bytearray(offset)
    entry = struct.pack(
        "<7Q6I",
        resource_hash(ENTRY), ARCHIVE_TYPE, offset, 0, 0, 0, 0,
        len(resource), 0, 0, 16, 16, 0,
    )
    body += resource
    body += b"\0" * (-len(body) % 16)
    header = struct.pack("<III20sQQ24s", 0xF0000011, 1, 1, b"", len(body), 0, b"")
    types = struct.pack("<IIQIIII", 0, 0, ARCHIVE_TYPE, 1, 0, 16, 16)
    body[:184] = header + types + entry
    return bytes(body)


def build_package(source_root: Path, output: Path) -> dict:
    source_path = source_root / "hd2_admission_probe.lua"
    source = source_path.read_bytes()
    if b"\0" in source or not source.decode("utf-8"):
        raise ValueError("probe must be plaintext UTF-8")
    marker = ("-- HD2-Addon: " + ENTRY + "\n").encode("utf-8")
    if source.startswith(b"-- HD2-Addon:"):
        first, sep, rest = source.partition(b"\n")
        if not sep or first.rstrip(b"\r") != marker.rstrip(b"\n"):
            raise ValueError("probe declaration does not match entry")
        source = rest
    entry_source = marker + source
    archive = make_archive(entry_source)
    provenance = {
        "schema_version": 1,
        "package_id": "hd2-admission-registry-probe",
        "revision": "2026-10-11-read-only-registry-record-refs",
        "steam_build": 25480438,
        "archive": ARCHIVE,
        "entry": ENTRY,
        "source_sha256": sha256(entry_source),
        "archive_sha256": sha256(archive),
        "read_only": True,
        "native_calls": False,
        "memory_writes": False,
        "multiplayer_verification": False,
    }
    manifest = {
        "Version": 1,
        "Guid": str(uuid.UUID(GUID)),
        "Name": "HD2 Admission Probe (HD2Scanner)",
        "Description": (
            "Temporary read-only diagnostic addon for the installed HD2Scanner service. "
            "It records runtime matches for known admission symbols and performs no native calls or writes."
        ),
        "Dependencies": [{"Name": "Bingus Shared Loader", "MinimumVersion": "18"}],
        "Options": [{"Name": "Admission probe", "Description": "Read-only diagnostic", "Include": ["Addon"]}],
    }
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "Addon/" + ARCHIVE: archive,
        "Addon/" + ARCHIVE + ".stream": b"",
        "Addon/" + ARCHIVE + ".gpu_resources": b"",
        "HD2-Admission-Probe-manifest.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".pending")
    with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, content)
    pending.replace(output)
    provenance["package_sha256"] = sha256(output.read_bytes())
    return provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path(__file__).parent / "data/mods/cainiao")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_package(args.source_root, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
