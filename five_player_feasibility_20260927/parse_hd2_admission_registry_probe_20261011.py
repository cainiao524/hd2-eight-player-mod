"""Parse a read-only HD2Scanner registry-marker probe.

This parser records only structural evidence.  It deliberately does not turn
the event hash or the nearby string into a callback, registry, or Session API
claim without a pointer or call-site relationship.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


BUILD = 25480438
MARKER = b"rpc_from_host_peer_c"
EVENT_HASH = bytes.fromhex("f4fc0448")
DEFAULT_LOG = Path(__file__).parents[1] / "output/native_dispatch_20261010/hd2_admission_registry_probe_20261011_r3.log"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def latest_section(log_text: str) -> tuple[str, list[str]]:
    sections = re.split(
        r"(?=^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START )",
        log_text,
        flags=re.MULTILINE,
    )
    starts = [s for s in sections if re.search(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d START ", s, re.MULTILINE)]
    if not starts:
        raise ValueError("probe_start_missing")
    section = starts[-1]
    if "DONE read_only=true no_calls=true no_writes=true" not in section:
        raise ValueError("latest_probe_section_incomplete")
    return section, [line for line in section.splitlines() if line]


def parse_hex_context(value: str) -> bytes:
    if len(value) != 256:
        raise ValueError("context_window_not_128_bytes")
    try:
        return bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("context_not_hex") from exc


def build_receipt(log_path: Path) -> dict:
    raw = log_path.read_bytes()
    section, lines = latest_section(raw.decode("utf-8"))
    request = re.search(r"REQUEST id=([^ ]+) game_base=0x([0-9A-Fa-f]+)", section)
    if not request:
        raise ValueError("request_missing")

    marker_pattern = re.compile(
        r"marker_occurrence=(\d+) at=0x([0-9A-Fa-f]+) stable=(true|false) "
        r"event_offsets=([^ ]*) context=([0-9A-Fa-f]+)"
    )
    marker_rows = []
    for line in lines:
        match = marker_pattern.search(line)
        if not match:
            continue
        context = parse_hex_context(match.group(5))
        marker_offset = context.find(MARKER)
        if marker_offset < 0:
            raise ValueError("marker_missing_from_context")
        offsets = []
        if match.group(4):
            offsets = [int(value, 16) for value in match.group(4).split(",")]
        for offset in offsets:
            if context[offset : offset + 4] != EVENT_HASH:
                raise ValueError("event_offset_bytes_mismatch")
        marker_address = int(match.group(2), 16)
        marker_rows.append(
            {
                "occurrence": int(match.group(1)),
                "address": hex(marker_address),
                "stable_reread": match.group(3) == "true",
                "event_offsets": [hex(offset) for offset in offsets],
                "record_address": hex(marker_address - marker_offset),
                "context_sha256": sha256(context),
                "marker_is_inline_in_context": True,
                "contains_event_hash": bool(offsets),
            }
        )

    pointer_pattern = re.compile(
        r"HIT key=(ptr_to_(record|event_hash)_\d+) label=([^ ]+) "
        r"target=0x([0-9A-Fa-f]+) count=(\d+)"
    )
    pointer_rows = []
    for line in lines:
        match = pointer_pattern.search(line)
        if match:
            pointer_rows.append(
                {
                    "key": match.group(1),
                    "target_kind": match.group(2),
                    "label": match.group(3),
                    "target": hex(int(match.group(4), 16)),
                    "count": int(match.group(5)),
                }
            )

    data_rows = [row for row in marker_rows if row["contains_event_hash"]]
    if not data_rows:
        raise ValueError("stable_marker_with_event_hash_missing")
    if not all(row["stable_reread"] for row in data_rows):
        raise ValueError("marker_reread_unstable")
    if not pointer_rows or any(row["count"] != 0 for row in pointer_rows):
        raise ValueError("unexpected_record_or_hash_pointer_reference")
    if "POINTER_REQUEST markers=" not in section:
        raise ValueError("pointer_scan_missing")

    return {
        "schema": "hd2_live_admission_registry_probe_v1",
        "build": BUILD,
        "probe": {
            "log_path": str(log_path),
            "log_sha256": sha256(raw),
            "request_id": request.group(1),
            "game_base": hex(int(request.group(2), 16)),
            "read_only": True,
            "calls_made": False,
            "writes_made": False,
            "hooks_installed": False,
            "latest_completed_run_only": True,
        },
        "marker_observations": {
            "marker": MARKER.decode("ascii"),
            "event_hash": "0x4804FCF4",
            "all_marker_rows": marker_rows,
            "stable_marker_rows_with_event_hash": data_rows,
            "event_hash_and_marker_cooccurred": True,
            "record_or_hash_pointer_rows": pointer_rows,
            "record_or_hash_pointer_count": sum(row["count"] for row in pointer_rows),
        },
        "interpretation": {
            "inline_data_record_observed": True,
            "pointer_to_record_or_hash_observed": False,
            "callback_registry_binding_proven": False,
            "session_party_api_binding_proven": False,
            "capacity_semantics_proven": False,
        },
        "production": {
            "installable": False,
            "runtime_verified": False,
            "multiplayer_verified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_receipt(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "stable_data_rows": len(receipt["marker_observations"]["stable_marker_rows_with_event_hash"]),
        "pointer_count": receipt["marker_observations"]["record_or_hash_pointer_count"],
        "registry_binding_proven": receipt["interpretation"]["callback_registry_binding_proven"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
