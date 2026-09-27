"""Extract the current bundled Chinese string banks without changing game files.

Helldivers 2's prod_slim build stores the boot archive in DSAR bundle chunks.
This script reads the DSAA catalog in bundles.nxa, reconstructs only the archive
metadata and requested resources, then records checksums for review.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import re
import struct
from pathlib import Path


ARCHIVE_NAME = "9ba626afa44a3aa3"
STRINGS_TYPE = 0x0D972BAB10B40FD3
STRING_MAGIC = bytes.fromhex("aef3853e")
RESOURCES = {
    "cn-main": (0x0F4D232E1EA74C41, 0x5942CCF7),
    "cn-ui": (0x81437B1AF39A8497, 0x5942CCF7),
    "tc-main": (0x0603A65953E81B5A, 0x9EBA952A),
    "tc-ui": (0x61CF58D44B3536B4, 0x9EBA952A),
}


def unpack(fmt: str, data: bytes, offset: int = 0):
    return struct.unpack_from(fmt, data, offset)


def decode_lz4_block(data: bytes, expected_size: int) -> bytes:
    """Decode the raw LZ4 blocks used by DSAR (no external dependencies)."""
    output = bytearray()
    index = 0
    while index < len(data):
        token = data[index]
        index += 1
        literal_count = token >> 4
        if literal_count == 15:
            while True:
                extra = data[index]
                index += 1
                literal_count += extra
                if extra != 255:
                    break
        output.extend(data[index : index + literal_count])
        index += literal_count
        if index == len(data):
            break
        if index > len(data):
            raise ValueError("LZ4 literal crosses block boundary")
        distance = data[index] | (data[index + 1] << 8)
        index += 2
        if distance == 0 or distance > len(output):
            raise ValueError("Invalid LZ4 match distance")
        match_count = token & 15
        if match_count == 15:
            while True:
                extra = data[index]
                index += 1
                match_count += extra
                if extra != 255:
                    break
        for _ in range(match_count + 4):
            output.append(output[-distance])
    if len(output) != expected_size:
        raise ValueError(f"LZ4 size mismatch: {len(output)} != {expected_size}")
    return bytes(output)


class DSAR:
    def __init__(self, path: Path):
        self.path = path
        self.used_chunks: set[int] = set()
        self.cache: dict[int, bytes] = {}
        with path.open("rb") as file:
            header = file.read(32)
            magic, _unknown, count, _header_size, _size, _padding = unpack(
                "<4s4sIIQ8s", header
            )
            if magic != b"DSAR":
                raise ValueError(f"Invalid DSAR magic in {path}")
            self.chunks = [
                unpack("<QQIIBB6s", file.read(32)) for _ in range(count)
            ]
        self.offsets = [chunk[0] for chunk in self.chunks]

    def chunk(self, index: int) -> bytes:
        self.used_chunks.add(index)
        if index not in self.cache:
            _uncompressed_at, compressed_at, size, compressed_size, kind, _flags, _pad = (
                self.chunks[index]
            )
            with self.path.open("rb") as file:
                file.seek(compressed_at)
                data = file.read(compressed_size)
            if len(data) != compressed_size:
                raise ValueError(f"Truncated DSAR chunk in {self.path}")
            if kind == 3:
                data = decode_lz4_block(data, size)
            elif kind != 0 or len(data) != size:
                raise ValueError(f"Unsupported DSAR compression {kind}")
            self.cache[index] = data
        return self.cache[index]


class BundledArchive:
    def __init__(self, game_data: Path):
        self.game_data = game_data
        catalog_bundle = DSAR(game_data / "bundles.nxa")
        catalog = b"".join(
            catalog_bundle.chunk(index) for index in range(len(catalog_bundle.chunks))
        )
        magic, _unknown1, _unknown2, nxa_count, archive_count, _pad = unpack(
            "<4sIIII4s", catalog
        )
        if magic != b"DSAA":
            raise ValueError("Invalid DSAA catalog magic")
        archive_headers = [
            unpack("<QIIQ", catalog, 24 + index * 24)
            for index in range(archive_count)
        ]
        filename_offsets = unpack(
            f"<{nxa_count}I", catalog, 24 + archive_count * 24
        )

        def filename(offset: int) -> str:
            return catalog[offset : catalog.index(b"\0", offset)].decode("ascii")

        self.nxa_names = [filename(offset) for offset in filename_offsets]
        self.bundles: dict[int, DSAR] = {}
        matched = [
            header for header in archive_headers if filename(header[1]) == ARCHIVE_NAME
        ]
        if len(matched) != 1:
            raise ValueError(f"Expected one bundled {ARCHIVE_NAME}, found {len(matched)}")
        self.archive_size, _filename_at, count, entries_at = matched[0]
        self.entries = [
            unpack("<I4sI3sB", catalog, entries_at + index * 16)
            for index in range(count)
        ]
        self.entry_offsets = [entry[0] for entry in self.entries]
        if self.entry_offsets != sorted(self.entry_offsets):
            raise ValueError("DSAA archive entries are out of order")

    def bundle(self, index: int) -> DSAR:
        if index not in self.bundles:
            self.bundles[index] = DSAR(self.game_data / self.nxa_names[index])
        return self.bundles[index]

    def read(self, position: int, count: int) -> bytes:
        if position < 0 or count < 0 or position + count > self.archive_size:
            raise ValueError("Read outside bundled archive")
        result = bytearray()
        while count:
            entry_index = bisect.bisect_right(self.entry_offsets, position) - 1
            if entry_index < 0:
                raise ValueError("Missing DSAA archive entry")
            entry = self.entries[entry_index]
            entry_end = (
                self.entry_offsets[entry_index + 1]
                if entry_index + 1 < len(self.entries)
                else self.archive_size
            )
            bundle = self.bundle(entry[4])
            chunk_index = bisect.bisect_left(bundle.offsets, entry[2])
            if bundle.offsets[chunk_index] != entry[2]:
                raise ValueError("DSAA entry does not match a DSAR chunk")
            within = position - entry[0]
            while within >= bundle.chunks[chunk_index][2]:
                within -= bundle.chunks[chunk_index][2]
                chunk_index += 1
            data = bundle.chunk(chunk_index)
            take = min(count, len(data) - within, entry_end - position)
            if take <= 0:
                raise ValueError("Invalid DSAR/DSAA boundary")
            result.extend(data[within : within + take])
            position += take
            count -= take
        return bytes(result)


def archive_files(read):
    header = read(0, 72)
    magic, type_count, file_count = unpack("<4sII", header)
    if magic != bytes.fromhex("110000f0"):
        raise ValueError("Invalid Stingray archive magic")
    metadata_size = 72 + type_count * 32 + file_count * 80
    metadata = read(0, metadata_size)
    start = 72 + type_count * 32
    files = {}
    for index in range(file_count):
        row = unpack("<QQ3Q2Q3I3I", metadata, start + index * 80)
        files[(row[0], row[1])] = (row[2], row[7])
    return files, {"types": type_count, "files": file_count, "metadata_size": metadata_size}


def string_header(data: bytes) -> dict:
    magic, version, count, language = unpack("<4sIII", data)
    if magic != STRING_MAGIC or version != 1:
        raise ValueError("Unexpected .strings format")
    if 16 + count * 8 > len(data):
        raise ValueError(".strings table exceeds resource")
    ids = unpack(f"<{count}I", data, 16)
    offsets = unpack(f"<{count}I", data, 16 + count * 4)
    if len(set(ids)) != count:
        raise ValueError("Duplicate .strings IDs")
    for offset in offsets:
        if offset >= len(data) or b"\0" not in data[offset:]:
            raise ValueError("Invalid .strings offset or terminator")
    return {"magic": magic.hex(), "version": version, "count": count,
            "language_hash": f"{language:08x}", "ids": set(ids)}


def loose_overrides(game_data: Path) -> list[dict]:
    found = []
    target_names = {name for name, _language in RESOURCES.values()}
    for path in game_data.glob("*.patch_*"):
        if not re.fullmatch(r"[0-9a-f]{16}\.patch_\d+", path.name):
            continue
        with path.open("rb") as file:
            files, _archive_meta = archive_files(lambda offset, n: (
                file.seek(offset), file.read(n)
            )[1])
            for (name, kind), (offset, size) in files.items():
                if name not in target_names or kind != STRINGS_TYPE:
                    continue
                file.seek(offset)
                data = file.read(size)
                header = string_header(data)
                found.append({"patch": path.name, "resource_hash": f"{name:016x}",
                              "size": size, "count": header["count"],
                              "language_hash": header["language_hash"],
                              "sha256": hashlib.sha256(data).hexdigest()})
    return sorted(found, key=lambda row: (int(row["patch"].split("_")[-1]), row["resource_hash"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", type=Path,
                        default=Path(r"F:\Game\Steam\steamapps\common\Helldivers 2\data"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "baseline")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = BundledArchive(args.game_data)
    files, archive_meta = archive_files(archive.read)
    manifest = {
        "source": "Installed game's prod_slim bundled base archive; no game files modified",
        "game_data": str(args.game_data.resolve()),
        "catalog": str((args.game_data / "bundles.nxa").resolve()),
        "catalog_sha256": hashlib.sha256((args.game_data / "bundles.nxa").read_bytes()).hexdigest(),
        "archive": ARCHIVE_NAME,
        "archive_metadata": archive_meta,
        "resources": {},
    }
    for label, (name, expected_language) in RESOURCES.items():
        offset, size = files[(name, STRINGS_TYPE)]
        data = archive.read(offset, size)
        header = string_header(data)
        if int(header["language_hash"], 16) != expected_language:
            raise ValueError(f"Unexpected language for {label}")
        output = args.output / f"{label}.{name:016x}.strings"
        output.write_bytes(data)
        manifest["resources"][label] = {
            "resource_hash": f"{name:016x}", "type_hash": f"{STRINGS_TYPE:016x}",
            "archive_offset": offset, "size": size,
            "magic": header["magic"], "version": header["version"],
            "count": header["count"], "language_hash": header["language_hash"],
            "sha256": hashlib.sha256(data).hexdigest(), "file": output.name,
        }
    manifest["loose_overrides"] = loose_overrides(args.game_data)
    manifest["bundles_read"] = [
        {"file": archive.nxa_names[index], "chunks": sorted(bundle.used_chunks)}
        for index, bundle in sorted(archive.bundles.items())
    ]
    manifest_path = args.output / "provenance.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()),
                      "resources": manifest["resources"],
                      "loose_overrides": manifest["loose_overrides"]}, indent=2))


if __name__ == "__main__":
    main()
