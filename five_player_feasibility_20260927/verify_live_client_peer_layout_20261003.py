from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(first: Path, second: Path) -> dict:
    a = json.loads(first.read_text(encoding="utf-8"))
    b = json.loads(second.read_text(encoding="utf-8"))
    assert a["schema"] == b["schema"] == "hd2_live_client_peer_layout_v1"
    assert a["build"] == b["build"] == 25480438
    assert a["pid"] == b["pid"] == 45820
    assert a["read_only"] and b["read_only"]
    assert not a["calls_made"] and not b["calls_made"]
    assert not a["writes_made"] and not b["writes_made"]
    assert a["roots"] == b["roots"]
    assert a["offsets"] == b["offsets"]
    assert a["peer_count"] == b["peer_count"] == 0
    assert a["records"] == b["records"]
    assert a["adjacent_table"] == b["adjacent_table"]
    assert all(row["raw_hex"] == "00" * 0x20 for row in a["records"])
    assert all(row["raw_hex"] == "00" * 0x10 for row in a["adjacent_table"])
    assert a["runtime_verified"] is False and a["installable"] is False and a["multiplayer_verified"] is False
    return {
        "schema": "hd2_live_client_peer_layout_verification_v1",
        "build": 25480438,
        "pid": 45820,
        "checks": {
            "two_reads_same_owner_client": True,
            "four_record_layout_readable": True,
            "adjacent_table_readable": True,
            "zero_count_preserved_without_interpretation": True,
            "read_only": True,
            "runtime_verified": False,
            "installable": False,
            "multiplayer_verified": False,
        },
        "inputs": {"first_sha256": sha(first), "second_sha256": sha(second)},
        "client_root": a["roots"]["client"],
        "peer_count": 0,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, default=HERE / "live_client_peer_layout_20261003_r1.json")
    parser.add_argument("--second", type=Path, default=HERE / "live_client_peer_layout_20261003_r2.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_output")
    result = verify(args.first, args.second)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": result["schema"], "passed": sum(result["checks"].values())}))
