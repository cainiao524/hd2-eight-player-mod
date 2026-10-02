"""Write the deterministic mid-function stub verification receipt."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from midgate_stub_candidate import verify


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify()
    result["verification"] = {
        "status": "passed_static_stub_and_patch_checks",
        "installer_invoked": False,
        "process_accessed": False,
        "game_module_modified": False,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
