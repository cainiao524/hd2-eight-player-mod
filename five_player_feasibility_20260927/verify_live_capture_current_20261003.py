"""Verify the current fixed-build read-only capture bundle.

The receipt validates identity continuity and known signatures only.  It never
opens a process, calls game code, writes memory, installs hooks, or claims that
the four-slot runtime admitted a fifth player.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BUILD = 25480438
EXE_SHA = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
DLL_SHA = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"


def read(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def check(rows: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    rows.append({"name": name, "passed": bool(ok), "detail": detail})


def image_ok(item: dict[str, Any]) -> bool:
    images = item.get("pinned_images", {})
    return (
        images.get("helldivers2.exe", {}).get("sha256") == EXE_SHA
        and images.get("game.dll", {}).get("sha256") == DLL_SHA
    )


def site_map(item: dict[str, Any]) -> dict[str, str]:
    return {row["rva"]: row["sha256"] for row in item.get("sites", [])}


def sites_valid(item: dict[str, Any], count: int) -> bool:
    sites = item.get("sites", [])
    if len(sites) != count or len(site_map(item)) != count:
        return False
    try:
        game_base = item["pinned_images"]["game.dll"]["base"]
        return all(
            len(bytes.fromhex(row["bytes"])) == row["size"] == 4096
            and hashlib.sha256(bytes.fromhex(row["bytes"])).hexdigest()
                == row["sha256"] == row["reread_sha256"]
            and row["unchanged_on_reread"] is True
            and int(row["address"], 16) == game_base + int(row["rva"], 16)
            for row in sites
        )
    except (KeyError, TypeError, ValueError):
        return False


def verify() -> dict[str, Any]:
    native = read("live_native_sites_20261003_r4.json")
    native_old = read("live_native_sites_20261003_r2.json")
    members = read("live_session_member_sites_20261003_r3.json")
    members_old = read("live_session_member_sites_20261003_r2.json")
    dispatcher = read("live_dispatcher_data_20261003_r5.json")
    registration = read("live_registration_state_20261003_16m_r2.json")
    session = read("live_session_snapshot_20261003_r10.json")

    rows: list[dict[str, Any]] = []
    pids = {native.get("pid"), members.get("pid"), dispatcher.get("pid"),
            registration.get("pid"), session.get("pid")}
    check(rows, "fixed_build_all_artifacts", all(
        item.get("build") == BUILD and item.get("schema") == schema
        for item, schema in zip(
            (native, members, dispatcher, registration, session),
            ("hd2_native_site_capture_v1", "hd2_session_member_site_capture_v1",
             "hd2_live_dispatcher_data_capture_v1", "hd2_live_registration_state_scan_v2",
             "hd2_live_session_snapshot_v1"))
    ), "all artifacts use the expected schema and build 25480438")
    check(rows, "same_live_pid", len(pids) == 1 and
          all(type(pid) is int and pid > 0 for pid in pids) and
          all(item.get("pinned_images") == native.get("pinned_images")
              for item in (members, dispatcher, registration, session)),
          "same PID and loaded image base/path/size/identity across the captures")
    check(rows, "native_image_identity", image_ok(native), "exe/game hashes match")
    check(rows, "member_image_identity", image_ok(members), "exe/game hashes match")
    check(rows, "dispatcher_image_identity", image_ok(dispatcher), "exe/game hashes match")
    check(rows, "registration_image_identity", image_ok(registration), "exe/game hashes match")
    check(rows, "session_image_identity", image_ok(session), "exe/game hashes match")
    check(rows, "native_sites_reread_stable", sites_valid(native, 6) and
          site_map(native) == site_map(native_old), "6 sites match prior fixed-build reread")
    check(rows, "session_sites_reread_stable", sites_valid(members, 5) and
          site_map(members) == site_map(members_old), "5 sites match prior fixed-build reread")
    signature = sorted((row.get("pattern"), row.get("rva")) for row in dispatcher.get("hits", []))
    check(rows, "dispatcher_signature", signature == [
        ("confirmed_peer_event_hash", "0xbe4982"),
        ("confirmed_peer_receiver", "0x214c820"),
    ], repr(signature))
    check(rows, "bounded_registration_scan", registration.get("coverage_complete") is True and
          registration.get("postflight_verified") is True and
          registration.get("negative_observation_valid") is True and
          registration.get("hits") == [] and registration.get("errors") == [] and
          registration.get("status") == "bounded_scan_complete" and
          all(registration.get("postflight", {}).get(key) is True for key in
              ("executable_unchanged", "module_list_unchanged", "disk_identity_unchanged")) and
          registration.get("scan_stats", {}).get("memory_bytes_read") == 16 * 1024 * 1024 and
          registration.get("scan_stats", {}).get("limit_bytes") == 16 * 1024 * 1024 and
          registration.get("scan_stats", {}).get("pages_read") == 4096 and
          registration.get("scan_stats", {}).get("termination_reason") == "scan_limit_reached" and
          registration.get("scan_stats", {}).get("coverage_complete") is True and
          registration.get("scan_stats", {}).get("truncated") is False,
          "16 MiB complete prefix, stable postflight, zero hits")
    check(rows, "session_baseline_four_slot", session.get("status") == "observed_context" and
          session.get("session", {}).get("peer_count_raw") == 0 and
          session.get("roster", {}).get("documented_slot_count") == 4 and
          session.get("roster", {}).get("out_of_contract_slots") == [4, 5, 6, 7],
          "menu baseline has zero peers and four documented roster slots")
    check(rows, "read_only_flags", all(
        item.get(key) is False
        for item in (native, members)
        for key in ("multiplayer_verified", "mod_installed")
    ) and all(registration.get(key) is False for key in
              ("resolver_closed", "installable", "multiplayer_verified")) and
          all(dispatcher.get(key) is False for key in
              ("resolver_closed", "eight_player_verified")),
          "each capture's explicit production claims remain false")
    check(rows, "no_process_mutation", all(
        item.get(key) is False
        for item in (dispatcher, registration, session)
        for key in ("calls_made", "writes_made", "hooks_installed")
    ) and all(item.get("read_only") is True for item in
              (dispatcher, registration, session)),
          "capture metadata explicitly reports read-only with calls, writes and hooks false")
    passed = sum(row["passed"] for row in rows)
    return {
        "schema": "hd2_live_capture_current_verification_v1",
        "build": BUILD,
        "pid": next(iter(pids)) if len(pids) == 1 else None,
        "artifacts": [
            "live_native_sites_20261003_r4.json",
            "live_session_member_sites_20261003_r3.json",
            "live_dispatcher_data_20261003_r5.json",
            "live_registration_state_20261003_16m_r2.json",
            "live_session_snapshot_20261003_r10.json",
        ],
        "checks": rows,
        "checks_passed": passed,
        "checks_total": len(rows),
        "verification_passed": passed == len(rows),
        "read_only": True,
        "resolver_closed": False,
        "installable": False,
        "multiplayer_verified": False,
        "meaning": "Fresh fixed-build read-only evidence is internally consistent; it does not prove a fifth peer, native resolver ownership, installation or eight-player multiplayer.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "verification_passed": result["verification_passed"]}, ensure_ascii=False))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
