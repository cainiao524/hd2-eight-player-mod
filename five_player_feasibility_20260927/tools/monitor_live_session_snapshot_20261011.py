"""Bounded read-only monitor built on the pinned live Session snapshot reader.

This helper never calls game code, writes process memory, installs hooks, or
traverses unknown pointers.  It repeatedly invokes the existing bounded reader
and stops early when a second peer is observed or the game process disappears.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def process_alive(pid: int) -> bool:
    # Windows-only task: the reader itself remains the authority for memory.
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ '1' }} else {{ '0' }}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() == "1"


def read_peer_count(path: Path) -> int | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("session", {}).get("peer_count_raw")
        return value if isinstance(value, int) else None
    except (OSError, ValueError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=8.0)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--reader", type=Path,
                        default=Path(__file__).with_name("capture_live_session_snapshot_20261003.py"))
    args = parser.parse_args()
    if args.interval <= 0 or args.timeout <= 0:
        parser.error("interval and timeout must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    samples = []
    index = 0
    status = "timeout"
    while time.monotonic() - started <= args.timeout:
        if not process_alive(args.pid):
            status = "process_gone"
            break
        index += 1
        output = args.output_dir / f"live_session_snapshot_20261011_monitor_{index:03d}.json"
        try:
            result = subprocess.run(
                [sys.executable, "-B", str(args.reader), "--pid", str(args.pid),
                 "--output", str(output)],
                cwd=Path.cwd(), capture_output=True, text=True, check=False,
                timeout=max(5.0, min(args.interval * 2.0, 30.0)),
            )
            returncode = result.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = None
            timed_out = True
        peer_count = read_peer_count(output) if output.exists() else None
        samples.append({
            "index": index,
            "output": str(output),
            "returncode": returncode,
            "timed_out": timed_out,
            "peer_count": peer_count,
        })
        if peer_count is not None and peer_count >= 2:
            status = "second_peer_observed"
            break
        remaining = args.timeout - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(args.interval, remaining))
    receipt = {
        "schema": "hd2_live_session_snapshot_monitor_v1",
        "pid": args.pid,
        "status": status,
        "read_only": True,
        "calls_made": False,
        "writes_made": False,
        "hooks_installed": False,
        "samples": samples,
    }
    receipt_path = args.output_dir / "live_session_snapshot_monitor_20261011.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "samples": len(samples),
                      "receipt": str(receipt_path)}, ensure_ascii=False))
    return 0 if status in {"second_peer_observed", "timeout"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
