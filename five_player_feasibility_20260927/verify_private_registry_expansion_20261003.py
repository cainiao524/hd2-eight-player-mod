"""Verify the expanded read-only private-memory registry scan.

This verifier compares two bounded captures from the same fixed build.  It
only validates capture metadata and negative/positive observations; a pointer
or hash hit is never promoted to a receive registry without an ABI trace.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"capture is not an object: {path}")
    return value


def verify(baseline_path: Path, expanded_path: Path, output: Path) -> dict:
    baseline = load(baseline_path)
    expanded = load(expanded_path)
    for name, capture in (("baseline", baseline), ("expanded", expanded)):
        if capture.get("schema") != "hd2_live_private_registry_scan_v1":
            raise ValueError(f"{name}: unexpected schema")
        if str(capture.get("build")) != "25480438":
            raise ValueError(f"{name}: fixed build identity missing")
        if capture.get("read_only") is not True or capture.get("calls_made") is not False:
            raise ValueError(f"{name}: capture is not read-only")
        if capture.get("writes_made") is not False or capture.get("hooks_installed") is not False:
            raise ValueError(f"{name}: write/hook flag is not false")
        if not isinstance(capture.get("hits"), list):
            raise ValueError(f"{name}: hits is not a list")
    bstats = baseline["scan_stats"]
    estats = expanded["scan_stats"]
    if estats["limit_bytes"] < bstats["limit_bytes"]:
        raise ValueError("expanded limit is smaller than baseline")
    if estats["memory_bytes_read"] < bstats["memory_bytes_read"]:
        raise ValueError("expanded read is smaller than baseline")
    if baseline["build"] != expanded["build"]:
        raise ValueError("captures are from different builds")
    if baseline["patterns"] != expanded["patterns"]:
        raise ValueError("capture patterns differ (including ASLR pointer identity)")
    result = {
        "schema": "hd2_private_registry_expansion_verification_v1",
        "baseline": {
            "path": str(baseline_path),
            "sha256": sha256(baseline_path),
            "scan_stats": bstats,
            "hit_count": len(baseline["hits"]),
        },
        "expanded": {
            "path": str(expanded_path),
            "sha256": sha256(expanded_path),
            "scan_stats": estats,
            "hit_count": len(expanded["hits"]),
        },
        "same_fixed_build": baseline["build"] == expanded["build"],
        "expanded_scan_passed": True,
        "receiver_registry_resolved": False,
        "installable": False,
        "multiplayer_verified": False,
        "reason": (
            f"Observed {len(expanded['hits'])} target pointer/hash hits in the "
            f"{estats['limit_bytes']} byte bounded MEM_PRIVATE scan; "
            "no owner and receive-ABI proof was provided."
        ),
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--expanded", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite output")
    result = verify(args.baseline, args.expanded, args.output)
    print(json.dumps({
        "output": str(args.output),
        "baseline_hits": result["baseline"]["hit_count"],
        "expanded_hits": result["expanded"]["hit_count"],
        "limit_bytes": result["expanded"]["scan_stats"]["limit_bytes"],
        "installable": result["installable"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
