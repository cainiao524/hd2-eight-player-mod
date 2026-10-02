"""Verify the 2026-10-03 read-only live preflight bundle.

The verifier joins the fixed-build image identity, the bounded native-site
captures, the direct call-edge scan, the dispatcher/config scan, and the
negative private-registry scan.  It is intentionally an evidence verifier:
it never opens a process, calls game code, writes memory, installs a hook, or
changes an installation gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BUILD = 25480438
EXE_SHA = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
GAME_SHA = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
ROOT = Path(__file__).resolve().parent


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def check(rows: list[dict], name: str, passed: bool, detail: str) -> None:
    rows.append({"name": name, "passed": bool(passed), "detail": detail})


def image_sha(obj: dict, name: str) -> str | None:
    return obj.get("pinned_images", {}).get(name, {}).get("sha256")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root = args.root
    names = {
        "interface": "live_interface_probe_20261003.json",
        "private": "live_private_registry_20261003_current.json",
        "signature": "live_signature_scan_20261003.json",
        "native": "live_native_sites_20261003.json",
        "session": "live_session_member_sites_20261003.json",
        "edges": "live_call_edges_20261003.json",
        "dispatcher": "live_dispatcher_data_20261003.json",
    }
    data = {key: load(root, name) for key, name in names.items()}
    rows: list[dict] = []
    all_objs = list(data.values())
    builds = {x.get("build") for x in all_objs}
    exes = {image_sha(x, "helldivers2.exe") for x in all_objs if "pinned_images" in x}
    games = {image_sha(x, "game.dll") for x in all_objs if "pinned_images" in x}
    pids = {x.get("pid") for x in all_objs if x.get("pid") is not None}
    check(rows, "fixed_build", builds == {BUILD}, repr(sorted(builds)))
    check(rows, "exe_identity", exes == {EXE_SHA}, repr(sorted(exes)))
    check(rows, "game_identity", games == {GAME_SHA}, repr(sorted(games)))
    check(rows, "single_pid_continuity", pids == {36900}, repr(sorted(pids)))

    native = data["native"]
    session = data["session"]
    check(rows, "native_sites_schema", native.get("schema") == "hd2_native_site_capture_v1", str(native.get("schema")))
    check(rows, "native_sites_count", len(native.get("sites", [])) == 6, str(len(native.get("sites", []))))
    check(rows, "native_sites_reread", all(x.get("unchanged_on_reread") for x in native.get("sites", [])), "six fixed sites")
    check(rows, "session_sites_schema", session.get("schema") == "hd2_session_member_site_capture_v1", str(session.get("schema")))
    check(rows, "session_sites_count", len(session.get("sites", [])) == 5, str(len(session.get("sites", []))))
    check(rows, "session_sites_reread", all(x.get("unchanged_on_reread") for x in session.get("sites", [])), "five fixed sites")

    edges = data["edges"]
    check(rows, "direct_edge_scan_schema", edges.get("schema") == "hd2_live_native_call_edges_v1", str(edges.get("schema")))
    check(rows, "direct_edge_count", len(edges.get("calls", [])) == 27, str(len(edges.get("calls", []))))
    hash_hits = edges.get("confirmed_peer_event_hash_hits", [])
    check(rows, "confirmed_peer_hash_send_only", len(hash_hits) == 1 and hash_hits[0].get("rva") == "0xbe4982", repr(hash_hits))
    check(rows, "edge_scan_read_only", edges.get("read_only") and not edges.get("calls_made") and not edges.get("writes_made"), "calls/writes false")

    dispatcher = data["dispatcher"]
    check(rows, "dispatcher_schema", dispatcher.get("schema") == "hd2_live_dispatcher_data_capture_v1", str(dispatcher.get("schema")))
    check(rows, "dispatcher_code_pin", dispatcher.get("generic_send_dispatcher_code", {}).get("sha256") == "ab22276e39bd854e07e369533ff043f1b8c5b9afd03d2da4a81c0b5d219861c5", "0xBDE430")
    check(rows, "dispatcher_code_reread", dispatcher.get("generic_send_dispatcher_code", {}).get("unchanged_on_reread") is True, "reread")
    check(rows, "dispatcher_hash_hit", any(x.get("pattern") == "confirmed_peer_event_hash" and x.get("rva") == "0xbe4982" for x in dispatcher.get("hits", [])), repr(dispatcher.get("hits", [])))
    check(rows, "private_registry_negative", data["private"].get("hits") == [], "bounded private scan")
    check(rows, "image_signature_host_join", any(x.get("name") == "host_join" for x in data["signature"].get("hits", [])), repr(data["signature"].get("hits", [])))
    check(rows, "all_capture_flags_read_only", all(x.get("read_only", True) and not x.get("calls_made", False) and not x.get("writes_made", False) for x in all_objs), "all captures")

    static_ok = all(x["passed"] for x in rows)
    result = {
        "schema": "hd2_live_preflight_continuation_verification_v1",
        "build": BUILD,
        "pid": 36900,
        "source_files": names,
        "checks": rows,
        "checks_passed": sum(x["passed"] for x in rows),
        "checks_total": len(rows),
        "verification_passed": static_ok,
        "runtime_calls_made": False,
        "game_memory_written": False,
        "hooks_installed": False,
        "resolver_closed": False,
        "installable": False,
        "multiplayer_verified": False,
        "decision": {
            "status": "live_image_aligned_registry_unresolved",
            "meaning": "The fixed build and native boundaries are stable in one process state; no service-side hash/selector registry or player creation success was observed.",
            "next_required": [
                "Bind the service-side event-hash to selector registry or a real callback trace.",
                "Run a real fifth-peer session and capture confirmed-peer to player creation on host and client.",
                "Only then construct a production hook and ladder to eight accounts.",
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "verification_passed": static_ok, "installable": False}, ensure_ascii=False))
    return 0 if static_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
