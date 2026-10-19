"""Build a test archive containing capacity, HD2Scanner, and the Party probe.

The Party probe consumes the existing HD2Scanner API.  This builder keeps the
verified capacity resources byte-for-byte, imports the pinned scanner archive,
and adds the read-only Party resource into one numbered addon archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import importlib.util


def _load_archive_helpers():
    path = Path(__file__).with_name("merge_bingus_archive_with_party_probe_20261011.py")
    spec = importlib.util.spec_from_file_location("archive_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load archive helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helpers = _load_archive_helpers()
ARCHIVE_TYPE = helpers.ARCHIVE_TYPE
PARTY_PROBE_RESOURCE = helpers.PARTY_PROBE_RESOURCE
make_archive = helpers.make_archive
read_archive = helpers.read_archive


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(capacity: Path, scanner: Path, probe: Path, output: Path) -> dict:
    capacity_type, capacity_resources = read_archive(capacity)
    scanner_type, scanner_resources = read_archive(scanner)
    probe_type, probe_resources = read_archive(probe)
    if capacity_type != ARCHIVE_TYPE or scanner_type != ARCHIVE_TYPE or probe_type != ARCHIVE_TYPE:
        raise ValueError("archive type mismatch")
    if len(probe_resources) != 1 or next(iter(probe_resources)) != PARTY_PROBE_RESOURCE:
        raise ValueError("Party probe archive has an unexpected resource set")
    overlap = set(capacity_resources) & set(scanner_resources)
    if overlap:
        raise ValueError(f"capacity/scanner resource collision: {sorted(hex(x) for x in overlap)}")
    overlap = (set(capacity_resources) | set(scanner_resources)) & set(probe_resources)
    if overlap:
        raise ValueError(f"probe resource collision: {sorted(hex(x) for x in overlap)}")

    merged = dict(capacity_resources)
    merged.update(scanner_resources)
    merged.update(probe_resources)
    raw = make_archive(merged)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_suffix(output.suffix + ".pending")
    pending.write_bytes(raw)
    pending.replace(output)
    return {
        "schema": "hd2_bingus_capacity_scanner_party_probe_merge_v1",
        "capacity_archive": str(capacity),
        "capacity_archive_sha256": sha256(capacity),
        "scanner_archive": str(scanner),
        "scanner_archive_sha256": sha256(scanner),
        "scanner_resource_count": len(scanner_resources),
        "probe_archive": str(probe),
        "probe_archive_sha256": sha256(probe),
        "output": str(output),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "capacity_resource_count": len(capacity_resources),
        "merged_resource_count": len(merged),
        "party_probe_resource_hash": hex(PARTY_PROBE_RESOURCE),
        "capacity_resources_preserved": all(merged[k] == v for k, v in capacity_resources.items()),
        "scanner_resources_preserved": all(merged[k] == v for k, v in scanner_resources.items()),
        "read_only_probe_payload": True,
        "native_calls": False,
        "memory_writes": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capacity-archive", type=Path, required=True)
    parser.add_argument("--scanner-archive", type=Path, required=True)
    parser.add_argument("--probe-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = merge(args.capacity_archive, args.scanner_archive, args.probe_archive, args.output)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
