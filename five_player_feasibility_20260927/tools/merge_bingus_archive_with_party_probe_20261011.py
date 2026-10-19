"""Merge the read-only Party probe resource into the verified capacity archive.

The game-side mod loader consumes numbered ``.patch_N`` archives.  This tool
keeps the already working capacity archive's resource bytes unchanged and adds
one additional private read-only probe resource, so the test does not require
inventing a new patch number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


HEADER = struct.Struct("<III20sQQ24s")
TYPE = struct.Struct("<IIQIIII")
ENTRY = struct.Struct("<7Q6I")
MAGIC = 0xF0000011
ARCHIVE_TYPE = 0xA14E8DFA2CD117E2
PARTY_PROBE_RESOURCE = 0xCA03BAEF8F9416AA


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_archive(path: Path) -> tuple[int, dict[int, bytes]]:
    raw = path.read_bytes()
    if len(raw) < HEADER.size + TYPE.size:
        raise ValueError(f"archive too small: {path}")
    magic, version, count, _reserved, body_size, _flags, _tail = HEADER.unpack_from(raw)
    if magic != MAGIC or version != 1 or body_size != len(raw):
        raise ValueError(f"invalid archive header: {path}")
    type_magic, type_flags, archive_type, type_count, _zero, alignment, block_alignment = TYPE.unpack_from(raw, HEADER.size)
    if type_magic != 0 or type_flags != 0 or archive_type != ARCHIVE_TYPE or type_count != count:
        raise ValueError(f"unexpected archive type table: {path}")
    if alignment != 16 or block_alignment != 16:
        raise ValueError(f"unexpected archive alignment: {path}")
    table_end = HEADER.size + TYPE.size + count * ENTRY.size
    if table_end > len(raw):
        raise ValueError(f"truncated archive table: {path}")
    resources: dict[int, bytes] = {}
    for index in range(count):
        fields = ENTRY.unpack_from(raw, HEADER.size + TYPE.size + index * ENTRY.size)
        name_hash, item_type, offset, _a, _b, _c, _d, size, _e, _f, _g, _h, _ordinal = fields
        if item_type != ARCHIVE_TYPE or name_hash in resources:
            raise ValueError(f"invalid or duplicate resource entry: {path}")
        end = offset + size
        if offset < table_end or end > len(raw):
            raise ValueError(f"resource outside archive: {path}")
        resources[name_hash] = raw[offset:end]
    return archive_type, resources


def make_archive(resources: dict[int, bytes]) -> bytes:
    if not resources or len(resources) != len(set(resources)):
        raise ValueError("resource set is empty or duplicated")
    count = len(resources)
    offset = (HEADER.size + TYPE.size + ENTRY.size * count + 15) & ~15
    body = bytearray(offset)
    entries = bytearray()
    for ordinal, (name_hash, resource) in enumerate(sorted(resources.items())):
        entries += ENTRY.pack(
            name_hash, ARCHIVE_TYPE, offset, 0, 0, 0, 0,
            len(resource), 0, 0, 16, 16, ordinal,
        )
        body += resource
        body += b"\0" * (-len(body) % 16)
        offset = len(body)
    header = HEADER.pack(MAGIC, 1, count, b"", len(body), 0, b"")
    types = TYPE.pack(0, 0, ARCHIVE_TYPE, count, 0, 16, 16)
    body[:HEADER.size + TYPE.size] = header + types
    body[HEADER.size + TYPE.size:HEADER.size + TYPE.size + len(entries)] = entries
    return bytes(body)


def merge(capacity_archive: Path, probe_archive: Path, output: Path) -> dict:
    capacity_type, capacity_resources = read_archive(capacity_archive)
    probe_type, probe_resources = read_archive(probe_archive)
    if capacity_type != ARCHIVE_TYPE or probe_type != ARCHIVE_TYPE:
        raise ValueError("archive type mismatch")
    if len(probe_resources) != 1:
        raise ValueError("Party probe archive must contain exactly one resource")
    probe_hash, probe_resource = next(iter(probe_resources.items()))
    if probe_hash != PARTY_PROBE_RESOURCE:
        raise ValueError(f"unexpected Party probe resource hash: {probe_hash:#x}")
    if probe_hash in capacity_resources:
        raise ValueError("Party probe resource already exists")
    merged = dict(capacity_resources)
    merged[probe_hash] = probe_resource
    raw = make_archive(merged)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".pending")
    pending.write_bytes(raw)
    pending.replace(output)
    return {
        "schema": "hd2_bingus_capacity_party_probe_merge_v1",
        "capacity_archive": str(capacity_archive),
        "capacity_archive_sha256": sha256(capacity_archive.read_bytes()),
        "probe_archive": str(probe_archive),
        "probe_archive_sha256": sha256(probe_archive.read_bytes()),
        "output": str(output),
        "output_sha256": sha256(raw),
        "capacity_resource_count": len(capacity_resources),
        "merged_resource_count": len(merged),
        "party_probe_resource_hash": hex(probe_hash),
        "capacity_resources_preserved": all(merged[key] == value for key, value in capacity_resources.items()),
        "read_only_probe_payload": True,
        "native_calls": False,
        "memory_writes": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity-archive", type=Path, required=True)
    parser.add_argument("--probe-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = merge(args.capacity_archive, args.probe_archive, args.output)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
