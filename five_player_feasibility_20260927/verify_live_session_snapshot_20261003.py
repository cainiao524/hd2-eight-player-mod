"""Verify two bounded live session snapshots without treating them as 8-player proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BUILD = 25480438
PID = 36900
ROOT = Path(__file__).resolve().parent


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("snapshot_root_not_object")
    return value


def image_hashes(value: dict) -> tuple[tuple[str, str | None], ...]:
    return tuple(sorted(
        (str(name), item.get("sha256"))
        for name, item in value.get("pinned_images", {}).items()
        if isinstance(item, dict)
    ))


def verify(paths: list[Path]) -> dict:
    if len(paths) != 2:
        raise ValueError("exactly_two_snapshots_required")
    snapshots = [load(path) for path in paths]
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("fixed_build", all(item.get("build") == BUILD for item in snapshots), str({item.get("build") for item in snapshots}))
    check("single_pid", all(item.get("pid") == PID for item in snapshots), str({item.get("pid") for item in snapshots}))
    check("image_identity", len({image_hashes(item) for item in snapshots}) == 1, "pinned image hashes match")
    check("read_only", all(item.get("read_only") is True and not item.get("calls_made") and not item.get("writes_made") and not item.get("hooks_installed") for item in snapshots), "no calls/writes/hooks")
    check("context_observed", all(item.get("status") == "observed_context" for item in snapshots), str([item.get("status") for item in snapshots]))
    counts = [item.get("session", {}).get("peer_count_raw", -1) for item in snapshots]
    check("peer_count_within_documented_limit", all(0 <= count <= 4 for count in counts), repr(counts))
    check("peer_rows_match_count", all(len(item.get("session", {}).get("peers", [])) == item.get("session", {}).get("peer_count_raw") for item in snapshots), "each row is fully read")
    check("peer_indexes_in_range", all(all(0 <= int(peer.get("network_index", -1)) <= 7 for peer in item.get("session", {}).get("peers", [])) for item in snapshots), "observed indexes in 0..7")
    check("peer_indexes_unique", all(len({peer.get("network_index") for peer in item.get("session", {}).get("peers", [])}) == item.get("session", {}).get("peer_count_raw") for item in snapshots), "no duplicate observed index")
    check("documented_roster_is_four", all(item.get("roster", {}).get("documented_slot_count") == 4 and len(item.get("roster", {}).get("records", [])) <= 4 for item in snapshots), "only documented inline records are accepted")
    check("out_of_contract_roster_slots", all(item.get("roster", {}).get("out_of_contract_slots") == [4, 5, 6, 7] for item in snapshots), "slots 4..7 are not read as roster records")

    passed = sum(row["passed"] for row in checks)
    return {
        "schema": "hd2_live_session_snapshot_verification_v1",
        "build": BUILD,
        "pid": PID,
        "source_files": [str(path) for path in paths],
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "verification_passed": passed == len(checks),
        "session_peer_count": snapshots[-1].get("session", {}).get("peer_count_raw"),
        "maximum_observed_peer_count": max(item.get("session", {}).get("peer_count_raw", 0) for item in snapshots),
        "documented_roster_slots": 4,
        "meaning": "The live process exposes a readable baseline session snapshot; this does not prove a fifth peer, player creation, installation, or multiplayer success.",
        "resolver_closed": False,
        "installable": False,
        "multiplayer_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify([args.first, args.second])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "verification_passed": result["verification_passed"]}, ensure_ascii=False))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
