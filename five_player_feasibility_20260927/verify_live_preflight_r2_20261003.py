"""Verify a second bounded read-only capture of the fixed native sites.

The second capture is deliberately compared with the first capture instead of
being treated as a new runtime result.  Matching code-image hashes and the
same negative registry result increase confidence in the build identity; they
do not provide a peer-admission or player-creation trace.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BUILD = 25480438
PID = 36900
ROOT = Path(__file__).resolve().parent


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def images(obj: dict) -> dict[str, str | None]:
    return {
        key: value.get("sha256")
        for key, value in obj.get("pinned_images", {}).items()
        if isinstance(value, dict)
    }


def site_hashes(obj: dict) -> dict[str, str | None]:
    return {str(row.get("rva")): row.get("sha256") for row in obj.get("sites", [])}


def edge_key(row: dict) -> tuple[str | None, str | None, str | None]:
    target = row.get("target", {})
    return row.get("caller_rva"), target.get("rva"), row.get("instruction")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    pairs = {
        "native_sites": ("live_native_sites_20261003.json", "live_native_sites_20261003_r2.json"),
        "session_sites": ("live_session_member_sites_20261003.json", "live_session_member_sites_20261003_r2.json"),
        "call_edges": ("live_call_edges_20261003.json", "live_call_edges_20261003_r2.json"),
        "private_registry": ("live_private_registry_20261003_current.json", "live_private_registry_20261003_r2.json"),
    }
    first = {key: load(root, names[0]) for key, names in pairs.items()}
    second = {key: load(root, names[1]) for key, names in pairs.items()}
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    all_captures = [*first.values(), *second.values()]
    check("fixed_build", all(obj.get("build") == BUILD for obj in all_captures), str({obj.get("build") for obj in all_captures}))
    check("single_pid", all(obj.get("pid") == PID for obj in all_captures), str({obj.get("pid") for obj in all_captures}))
    check("image_identity", len({tuple(sorted(images(obj).items())) for obj in all_captures}) == 1, "all pinned image hashes match")
    check("native_site_hashes", site_hashes(first["native_sites"]) == site_hashes(second["native_sites"]), "six site hashes match")
    check("native_site_rereads", all(row.get("unchanged_on_reread") for row in second["native_sites"].get("sites", [])), "second capture rereads stable")
    check("session_site_hashes", site_hashes(first["session_sites"]) == site_hashes(second["session_sites"]), "five site hashes match")
    check("session_site_rereads", all(row.get("unchanged_on_reread") for row in second["session_sites"].get("sites", [])), "second capture rereads stable")

    first_edges = {edge_key(row) for row in first["call_edges"].get("calls", [])}
    second_edges = {edge_key(row) for row in second["call_edges"].get("calls", [])}
    check("call_edge_set", first_edges == second_edges and len(second_edges) == 27, f"first={len(first_edges)} second={len(second_edges)}")
    first_hits = first["call_edges"].get("confirmed_peer_event_hash_hits", [])
    second_hits = second["call_edges"].get("confirmed_peer_event_hash_hits", [])
    check("confirmed_peer_hash_hit", first_hits == second_hits and len(second_hits) == 1 and second_hits[0].get("rva") == "0xbe4982", repr(second_hits))
    check("private_registry_negative", first["private_registry"].get("hits") == [] and second["private_registry"].get("hits") == [], "both bounded scans negative")
    check("read_only", all(obj.get("read_only", True) and not obj.get("calls_made", False) and not obj.get("writes_made", False) for obj in all_captures), "all captures read-only")

    passed = sum(row["passed"] for row in checks)
    result = {
        "schema": "hd2_live_preflight_r2_verification_v1",
        "build": BUILD,
        "pid": PID,
        "source_files": {key: list(value) for key, value in pairs.items()},
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "verification_passed": passed == len(checks),
        "meaning": "A second bounded reread matches the fixed build and remains registry-negative; it does not prove peer admission, player creation, installation, or multiplayer success.",
        "resolver_closed": False,
        "installable": False,
        "multiplayer_verified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": passed, "checks_total": len(checks), "verification_passed": result["verification_passed"]}, ensure_ascii=False))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
