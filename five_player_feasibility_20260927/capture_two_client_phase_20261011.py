"""Capture one named two-client phase with the existing bounded reader.

This wrapper does not inspect processes itself and does not call game code. It
only invokes the already reviewed read-only snapshot reader supplied by the
caller, refuses to overwrite a previous phase, and records the reader result.
Run it only during an explicitly opened test room.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


PHASES = (
    "host_before", "joined", "after_leave",
    "migration_before", "migration_after", "cleanup",
)
DEFAULT_READER = Path(__file__).resolve().parent / "tools" / "capture_live_session_snapshot_20261003.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reader", type=Path, default=DEFAULT_READER)
    args = parser.parse_args()
    if args.pid <= 0:
        parser.error("pid must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = args.output_dir / f"two_client_{args.phase}.json"
    receipt_path = args.output_dir / f"two_client_{args.phase}_receipt.json"
    if snapshot_path.exists() or receipt_path.exists():
        raise SystemExit("refusing to overwrite an existing phase")

    command = [sys.executable, "-B", str(args.reader), "--pid", str(args.pid),
               "--output", str(snapshot_path)]
    completed = subprocess.run(command, cwd=Path.cwd(), capture_output=True,
                               text=True, check=False)
    snapshot_valid = False
    snapshot_observed = False
    snapshot_status = None
    snapshot_error = None
    if snapshot_path.exists():
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot_valid = (
                isinstance(snapshot, dict) and
                snapshot.get("schema") == "hd2_live_session_snapshot_v1" and
                snapshot.get("read_only") is True and
                snapshot.get("calls_made") is False and
                snapshot.get("writes_made") is False and
                snapshot.get("hooks_installed") is False
            )
            if not snapshot_valid:
                snapshot_error = "snapshot_schema_or_side_effect_flags_invalid"
            else:
                snapshot_status = snapshot.get("status")
                snapshot_observed = (
                    snapshot_status == "observed_context" and
                    snapshot.get("pid") == args.pid and
                    not snapshot.get("errors") and not snapshot.get("error")
                )
                if not snapshot_observed:
                    snapshot_error = "snapshot_not_observed_for_requested_pid"
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            snapshot_error = "snapshot_unreadable:" + str(exc)
    else:
        snapshot_error = "snapshot_not_written"

    receipt = {
        "schema": "hd2_two_client_phase_capture_v1",
        "phase": args.phase,
        "pid": args.pid,
        "snapshot": str(snapshot_path),
        "reader": str(args.reader),
        "reader_returncode": completed.returncode,
        "snapshot_valid_read_only": snapshot_valid,
        "snapshot_observed": snapshot_observed,
        "snapshot_status": snapshot_status,
        "snapshot_error": snapshot_error,
        "reader_stderr": completed.stderr,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(json.dumps({"phase": args.phase, "snapshot_valid_read_only": snapshot_valid,
                      "snapshot_observed": snapshot_observed, "snapshot_error": snapshot_error,
                      "receipt": str(receipt_path)}, ensure_ascii=False))
    return 0 if completed.returncode == 0 and snapshot_observed else 2


if __name__ == "__main__":
    raise SystemExit(main())
