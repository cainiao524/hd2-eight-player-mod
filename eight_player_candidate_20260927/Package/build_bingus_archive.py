"""Build the Lua-only Bingus Shared Loader package for the capacity menu.

This builder creates an ``Addon/9ba626afa44a3aa3.patch_0`` archive with one
declared entry and three private Lua modules.  It never reads the game
installation, loads a DLL, or claims that native multiplayer admission is
implemented.  The menu remains fail-closed until the separately loaded native
control boundary reports a matching ABI and a verified provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import uuid
import zipfile


ARCHIVE = "9ba626afa44a3aa3.patch_0"
ARCHIVE_TYPE = 0xA14E8DFA2CD117E2
BUILD = 25480438
EXE_VERSION = "1.8.46015.0"
GUID = "f74f1e2f-9ef9-4a30-b8d5-8c2d5c6d8e81"
ENTRY = "mods/cainiao/hd2_capacity_menu"
MODULES = {
    "mods/cainiao/hd2_capacity_contract": "hd2_capacity_contract.lua",
    "mods/cainiao/hd2_capacity_native": "hd2_capacity_native.lua",
    "mods/cainiao/hd2_capacity_runtime": "hd2_capacity_runtime.lua",
}
NAME_RE = re.compile(r"mods/[A-Za-z0-9_]+/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resource_hash(name: str) -> int:
    """Return the 64-bit resource identity used by Bingus Shared Loader."""
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


def _validate_name(name: str) -> None:
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"invalid resource name: {name!r}")
    if name == "mods/codex/loader":
        raise ValueError("the loader dispatcher name is reserved")


def entry_source(name: str, source: bytes) -> bytes:
    """Validate and normalize the single loader-discovered entry."""
    _validate_name(name)
    if source.startswith((b"\xef\xbb\xbf", b"\x1b")) or b"\0" in source:
        raise ValueError("Lua must be plaintext UTF-8 without BOM or bytecode")
    source.decode("utf-8")
    marker = ("-- HD2-Addon: " + name + "\n").encode("utf-8")
    if len(marker) > 256:
        raise ValueError("addon declaration exceeds the loader limit")
    if source.startswith(b"-- HD2-Addon:"):
        line, separator, remainder = source.partition(b"\n")
        if not separator or line.rstrip(b"\r") != marker[:-1]:
            raise ValueError("existing addon declaration does not match the resource name")
        source = remainder
    return marker + source


def module_source(name: str, source: bytes) -> bytes:
    """Validate a private ``require`` module, which must stay undiscovered."""
    _validate_name(name)
    if source.startswith((b"\xef\xbb\xbf", b"\x1b")) or b"\0" in source:
        raise ValueError("Lua must be plaintext UTF-8 without BOM or bytecode")
    source.decode("utf-8")
    if source.startswith(b"-- HD2-Addon:"):
        raise ValueError(f"private module must not declare an addon: {name}")
    return source


def make_archive(resources: dict[int, bytes]) -> bytes:
    """Encode resources in the fixed Lua archive format used by the loader."""
    if not resources:
        raise ValueError("archive needs at least one resource")
    if len(resources) != len(set(resources)):
        raise ValueError("duplicate resource identity")
    count = len(resources)
    offset = (104 + 80 * count + 15) & ~15
    entries = bytearray()
    body = bytearray(offset)
    for index, (name_hash, resource) in enumerate(sorted(resources.items())):
        entries += struct.pack(
            "<7Q6I",
            name_hash,
            ARCHIVE_TYPE,
            offset,
            0,
            0,
            0,
            0,
            len(resource),
            0,
            0,
            16,
            16,
            index,
        )
        body += resource
        body += b"\0" * (-len(body) % 16)
        offset = len(body)
    header = struct.pack("<III20sQQ24s", 0xF0000011, 1, count, b"", offset, 0, b"")
    types = struct.pack("<IIQIIII", 0, 0, ARCHIVE_TYPE, count, 0, 16, 16)
    body[: 104 + len(entries)] = header + types + entries
    return bytes(body)


def _envelope(source: bytes) -> bytes:
    return struct.pack("<II", len(source), 2) + source


def build_package(source_root: Path, output: Path) -> dict:
    source_root = source_root.resolve()
    output = output.resolve()
    entry_path = source_root / "hd2_capacity_menu.lua"
    if not entry_path.is_file():
        raise FileNotFoundError(entry_path)
    resources: dict[int, bytes] = {}
    source_hashes: dict[str, str] = {}
    entry = entry_source(ENTRY, entry_path.read_bytes())
    resources[resource_hash(ENTRY)] = _envelope(entry)
    source_hashes[ENTRY] = sha256(entry)
    for name, filename in MODULES.items():
        path = source_root / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        source = module_source(name, path.read_bytes())
        key = resource_hash(name)
        if key in resources:
            raise ValueError(f"resource hash collision: {name}")
        resources[key] = _envelope(source)
        source_hashes[name] = sha256(source)
    archive = make_archive(resources)
    provenance = {
        "schema_version": 1,
        "package_id": "hd2-player-capacity-bingus-addon",
        "revision": "0.15.0-capacity-staging",
        "steam_build": BUILD,
        "exe_version": EXE_VERSION,
        "guid": GUID,
        "archive": ARCHIVE,
        "resources": source_hashes,
        "archive_sha256": sha256(archive),
        "native_control_boundary": {
            "abi": 1,
            "provider_bound": False,
            "multiplayer_verified": False,
            "fail_closed": True,
        },
    }
    manifest = {
        "Version": 1,
        "Guid": str(uuid.UUID(GUID)),
        "Name": "HD2 Player Capacity (Bingus)",
        "Description": (
            "Host-only configurable capacity menu for build 25480438. "
            "Requires Bingus Shared Loader v18/API 1, Mod Options Menu and HD2Runtime. "
            "The package is staging-only until a verified native provider and multiplayer receipt exist."
        ),
        "Dependencies": [
            {"Name": "Bingus Shared Loader", "MinimumVersion": "18"},
            {"Name": "Mod Options Menu", "MinimumVersion": "1.1"},
            {"Name": "HD2Runtime", "MinimumVersion": "0.28.0"},
        ],
        "Options": [{"Name": "Player Capacity", "Description": "Enable the staging menu", "Include": ["Addon"]}],
    }
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "Addon/" + ARCHIVE: archive,
        "Addon/" + ARCHIVE + ".stream": b"",
        "Addon/" + ARCHIVE + ".gpu_resources": b"",
        "HD2-Player-Capacity-manifest.json": (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".pending")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, content)
    temporary.replace(output)
    provenance["package_sha256"] = sha256(output.read_bytes())
    return provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).parent / "data/mods/cainiao")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() in {p.resolve() for p in args.source_root.glob("*.lua")}:
        parser.error("output must not overwrite a Lua source")
    report = build_package(args.source_root, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
