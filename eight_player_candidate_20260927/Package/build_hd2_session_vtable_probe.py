"""Build the temporary read-only GameSession vtable probe addon."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid
import zipfile

from build_hd2_admission_probe import ARCHIVE_TYPE, resource_hash


ARCHIVE = "9ba626afa44a3aa3.patch_0"
GUID = "6c7e8f90-a1b2-4c3d-9e0f-1a2b3c4d5e6f"
ENTRY = "mods/cainiao/hd2_session_vtable_probe"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_archive(resource: bytes) -> bytes:
    body_resource = struct.pack("<II", len(resource), 2) + resource
    offset = (104 + 80 + 15) & ~15
    body = bytearray(offset)
    entry = struct.pack(
        "<7Q6I",
        resource_hash(ENTRY), ARCHIVE_TYPE, offset, 0, 0, 0, 0,
        len(body_resource), 0, 0, 16, 16, 0,
    )
    body += body_resource
    body += b"\0" * (-len(body) % 16)
    header = struct.pack("<III20sQQ24s", 0xF0000011, 1, 1, b"", len(body), 0, b"")
    types = struct.pack("<IIQIIII", 0, 0, ARCHIVE_TYPE, 1, 0, 16, 16)
    body[:184] = header + types + entry
    return bytes(body)


def build_package(source_root: Path, output: Path) -> dict:
    source_path = source_root / "hd2_session_vtable_probe.lua"
    source = source_path.read_bytes()
    source.decode("utf-8")
    if b"\0" in source:
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
        "package_id": "hd2-session-vtable-probe",
        "revision": "2026-10-11-read-only-vtable",
        "steam_build": 25480438,
        "archive": ARCHIVE,
        "entry": ENTRY,
        "source_sha256": sha256(entry_source),
        "archive_sha256": sha256(archive),
        "read_only": True,
        "native_calls": False,
        "memory_writes": False,
        "semantic_claims": False,
        "multiplayer_verification": False,
    }
    manifest = {
        "Version": 1,
        "Guid": str(uuid.UUID(GUID)),
        "Name": "HD2 Session Vtable Probe",
        "Description": (
            "Temporary read-only diagnostic addon for the fixed-build GameSession vtable. "
            "It reads pointer entries and code windows without invoking any game function."
        ),
        "Dependencies": [{"Name": "Bingus Shared Loader", "MinimumVersion": "18"}],
        "Options": [{"Name": "Session vtable probe", "Description": "Read-only diagnostic", "Include": ["Addon"]}],
    }
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "Addon/" + ARCHIVE: archive,
        "Addon/" + ARCHIVE + ".stream": b"",
        "Addon/" + ARCHIVE + ".gpu_resources": b"",
        "HD2-Session-Vtable-Probe-manifest.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8"),
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
