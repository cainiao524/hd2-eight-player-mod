"""Bounded read-only monitor for a live peer-count transition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--baseline", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    samples = []
    index = 0
    status = "timeout"
    while time.monotonic() - started <= args.timeout:
        index += 1
        output = args.output_dir / f"peer_transition_{index:03d}.json"
        try:
            result = subprocess.run(
                [sys.executable, "-B", str(args.reader), "--pid", str(args.pid),
                 "--output", str(output)],
                cwd=Path.cwd(), capture_output=True, text=True, check=False,
                timeout=max(5.0, min(args.interval * 2.0, 30.0)),
            )
            timed_out = False
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
        peer_count = None
        if output.exists():
            try:
                data = json.loads(output.read_text(encoding="utf-8"))
                peer_count = data.get("session", {}).get("peer_count_raw")
            except (OSError, ValueError, TypeError):
                pass
        samples.append({"index": index, "output": str(output),
                        "returncode": returncode, "timed_out": timed_out,
                        "peer_count": peer_count})
        if isinstance(peer_count, int) and peer_count != args.baseline:
            status = "peer_count_changed"
            break
        remaining = args.timeout - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(args.interval, remaining))
    receipt = {"schema": "hd2_peer_count_transition_monitor_v1", "pid": args.pid,
               "baseline": args.baseline, "status": status, "read_only": True,
               "calls_made": False, "writes_made": False, "hooks_installed": False,
               "samples": samples}
    receipt_path = args.output_dir / "peer_transition_monitor.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "samples": len(samples),
                      "receipt": str(receipt_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
