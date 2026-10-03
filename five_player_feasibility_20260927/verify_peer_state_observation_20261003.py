"""Validate the fixed-build GameSession peer-state observation without treating it as player proof."""
import json
from pathlib import Path

HERE = Path(__file__).parent
LOG = HERE / "live_capacity_patch_runtime_20261003_peer_slots.jsonl"
REPORT = HERE / "live_capacity_patch_peer_state_20261003.json"
rows = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
applied = [row for row in rows if row.get("event") == "applied"]
observed = [row for row in rows if row.get("event") == "session_observe"]
counts = [int(row.get("peer_count", 0)) for row in observed]
slot_vectors = [tuple(row.get("peer_slots", [])) for row in observed]
distinct_slot_values = sorted({value for vector in slot_vectors for value in vector if value not in ("0x0", "0")})
result = {
    "schema": "hd2_capacity_patch_peer_state_observation_v1",
    "build": 25480438,
    "log": LOG.as_posix(),
    "events": len(rows),
    "loaded": any(row.get("event") == "loaded" for row in rows),
    "applied": len(applied) == 1 and applied[0].get("patched") == 35,
    "patched_count": applied[0].get("patched", 0) if applied else 0,
    "session_observations": len(observed),
    "peer_count_min": min(counts) if counts else None,
    "peer_count_max": max(counts) if counts else None,
    "peer_slot_widths": sorted({len(vector) for vector in slot_vectors}),
    "distinct_nonzero_peer_slot_values": distinct_slot_values,
    "peer_id_semantics_unresolved": True,
    "count_is_not_player_admission": True,
    "player_admission_proven": False,
    "player_creation_proven": False,
    "read_only_observation": True,
    "process_mutated": True,
    "installable": False,
    "multiplayer_verified": False,
}
result["verification_passed"] = (
    result["loaded"]
    and result["applied"]
    and result["session_observations"] > 0
    and result["peer_id_semantics_unresolved"]
    and not result["player_admission_proven"]
    and not result["player_creation_proven"]
)
REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
assert result["verification_passed"]
