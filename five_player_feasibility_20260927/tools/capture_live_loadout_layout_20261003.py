"""Bounded read-only live image preflight for MenuScreenLoadout pins.

The utility verifies the fixed build and rereads only the game.dll code anchors
saved in ``index_slot_mapping_evidence_v2.json``.  It does not inspect heap
objects, invoke functions, follow pointers, write memory, install hooks or
change files in the game directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import interface_probe as base


BUILD = 25480438
EVIDENCE = Path(__file__).resolve().parent.parent / "index_slot_mapping_evidence_v2.json"
CAPTURE_IDENTITY = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"
READ_BUDGET = 64 * 1024


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_pins() -> tuple[str, list[dict]]:
    doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    identity = doc.get("capture_identity_sha256")
    if identity != CAPTURE_IDENTITY:
        raise ValueError("unsupported capture identity")
    pins: list[dict] = []
    seen: dict[int, bytes] = {}
    for group in doc.get("groups", []):
        for anchor in group.get("anchors", []):
            rva = anchor.get("rva")
            raw_hex = anchor.get("bytes")
            if not isinstance(rva, str) or not isinstance(raw_hex, str):
                raise ValueError("malformed loadout anchor")
            address = int(rva, 16)
            raw = bytes.fromhex(raw_hex)
            if address < 0 or not 0 < len(raw) <= 4096:
                raise ValueError("invalid bounded anchor")
            if anchor.get("sha256") != digest(raw):
                raise ValueError("anchor bytes/hash mismatch at " + rva)
            if address in seen:
                if seen[address] != raw:
                    raise ValueError("conflicting anchor at " + rva)
                continue
            seen[address] = raw
            pins.append({
                "group": group.get("name"),
                "rva": hex(address),
                "expected_bytes": raw.hex(),
                "expected_sha256": digest(raw),
                "root": anchor.get("root"),
            })
    if not pins:
        raise ValueError("no loadout anchors in evidence")
    if sum(len(raw) * 2 for raw in seen.values()) > READ_BUDGET:
        raise ValueError("anchor set exceeds read budget")
    return identity, pins


def capture(pid: int, output: Path) -> dict:
    if output.exists():
        raise ValueError(f"refusing to overwrite output: {output}")
    identity, pins = load_pins()
    base.READ_BUDGET = READ_BUDGET
    reader = base.WindowsReader(pid)
    try:
        executable = reader.executable()
        modules = reader.modules()
        selected = base.check_files(modules, executable)
        # These pins come from the fixed game.dll capture, not the launcher EXE.
        # Keep the module choice explicit so a matching EXE cannot accidentally
        # make a game.dll RVA appear valid.
        image = selected["game.dll"]
        image_base = int(image["base"])
        # Reject every out-of-image RVA before reading any of the anchors.
        for pin in pins:
            if int(pin["rva"], 16) + len(bytes.fromhex(pin["expected_bytes"])) > image["size"]:
                raise ValueError("anchor exceeds pinned image at " + pin["rva"])
        rows: list[dict] = []
        mismatches: list[str] = []
        for pin in pins:
            rva = int(pin["rva"], 16)
            expected = bytes.fromhex(pin["expected_bytes"])
            live = reader.read(image_base + rva, len(expected), executable=True)
            reread = reader.read(image_base + rva, len(expected), executable=True)
            row = {
                "group": pin["group"],
                "rva": pin["rva"],
                "address": hex(image_base + rva),
                "size": len(expected),
                "expected_sha256": pin["expected_sha256"],
                "live_sha256": digest(live),
                "reread_sha256": digest(reread),
                "expected_bytes": pin["expected_bytes"],
                "live_bytes": live.hex(),
                "matches_expected": live == expected,
                "unchanged_on_reread": live == reread,
                "root": pin["root"],
            }
            rows.append(row)
            if not row["matches_expected"] or not row["unchanged_on_reread"]:
                mismatches.append(pin["rva"])
        # Recheck image identity and the exact module list before releasing the
        # read handle.  No pointer discovered in code is followed.
        if reader.executable() != executable or reader.modules() != modules:
            raise ValueError("process image/module list changed")
        if base.check_files(modules, executable) != selected:
            raise ValueError("disk identity changed")
        if output.exists():
            raise ValueError(f"refusing to overwrite output: {output}")
        return {
            "schema_version": 1,
            "schema": "hd2_live_loadout_layout_preflight_v1",
            "build": BUILD,
            "pid": pid,
            "utc": datetime.now(timezone.utc).isoformat(),
            "evidence": str(EVIDENCE),
            "evidence_capture_identity_sha256": identity,
            "pinned_module": image,
            "anchor_count": len(rows),
            "matched_count": sum(row["matches_expected"] for row in rows),
            "unchanged_count": sum(row["unchanged_on_reread"] for row in rows),
            "mismatched_rvas": mismatches,
            "rows": rows,
            "bytes_read": reader.used,
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "heap_objects_read": False,
            "runtime_verified": False,
            "installable": False,
            "multiplayer_verified": False,
            "preflight_passed": not mismatches,
        }
    finally:
        reader.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = capture(args.pid, args.output)
    # Exclusive creation also closes the race after capture's existence check.
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "anchor_count": report["anchor_count"],
        "matched_count": report["matched_count"],
        "bytes_read": report["bytes_read"],
        "preflight_passed": report["preflight_passed"],
    }, ensure_ascii=False))
    return 0 if report["preflight_passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
