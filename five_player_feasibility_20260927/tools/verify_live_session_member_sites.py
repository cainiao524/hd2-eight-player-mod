"""Verify a bounded read-only live site capture against saved build evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BUILD = 25480438
EXE_SHA = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"
GAME_SHA = "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e"
KNOWN = {
    0x1092E60: (259, "337667006beecb7e40e381a76ffdcb10ebd4e539c4330e43494febd49d965abf"),
    0x1093590: (335, "940aa51124b7e6cab994cd4916165e4197ea2baf1df9427c642e7e67a1693c88"),
    0x10936E0: (126, "61b38874c67e6ea40b0c3fe3ca8ec80895d0f86fee14addf112d13b0a60eca65"),
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def verify(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    require(doc["schema"] == "hd2_session_member_site_capture_v1", "schema mismatch")
    require(doc["build"] == BUILD, "build mismatch")
    require(doc["runtime_capture"] is True, "not a live capture")
    require(doc["multiplayer_verified"] is False and doc["mod_installed"] is False,
            "capture gate was marked as a result")
    pins = doc["pinned_images"]
    require(pins["helldivers2.exe"]["sha256"] == EXE_SHA, "exe fingerprint mismatch")
    require(pins["game.dll"]["sha256"] == GAME_SHA, "game fingerprint mismatch")
    rows = {int(row["rva"], 16): row for row in doc["sites"]}
    require(len(rows) == 5, "site count mismatch")
    for rva, (size, expected_hash) in KNOWN.items():
        row = rows[rva]
        raw = bytes.fromhex(row["bytes"])
        require(len(raw) == row["size"] == 0x1000, f"site size mismatch: {hex(rva)}")
        body = raw[:size]
        require(hashlib.sha256(body).hexdigest() == expected_hash,
                f"saved body mismatch: {hex(rva)}")
        require(row["sha256"] == row["reread_sha256"] and row["unchanged_on_reread"],
                f"reread mismatch: {hex(rva)}")
    host = rows[0x108BC70]
    require(bytes.fromhex(host["bytes"]).startswith(
        bytes.fromhex("405553564154488d6c24e94881ecc8000000")),
        "host join prefix mismatch")
    return {
        "status": "passed_live_read_only_site_revalidation",
        "pid": doc["pid"],
        "build": BUILD,
        "sites": [hex(x) for x in sorted(rows)],
        "known_bodies_revalidated": [hex(x) for x in sorted(KNOWN)],
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "runtime_behavior_verified": False,
        "multiplayer_verified": False,
        "mod_installed": False,
        "limits": [
            "This proves only that the fixed native image is present and matches saved bytes.",
            "No function was called and no resolver, peer admission, player creation, or cleanup behavior was exercised.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    result = verify(args.capture)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
