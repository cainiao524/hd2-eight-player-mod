"""Offline audit and safe player-count contract for AI scaling data.

The pinned public HiveMind snapshot contains 1..4 entries in every
``player_count_multipliers`` array.  This module does not patch a game or load
any native code.  It defines the only safe consumer policy that can be used
until a same-build native consumer is observed: select entries 1..4 directly,
reuse the four-player entry for 5..8, and reject every invalid or malformed
input before indexing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Iterable


BUILD = "25480438"
LOGICAL_MAX_PLAYERS = 8
LEGACY_PLAYER_COUNT = 4
EXPECTED_ARRAY_LENGTH = 4
EXPECTED_GAME_VERSION = "1.007.100"
EXPECTED_PATCH_DATE = "2026-09-22"
EXPECTED_ENTITY_COUNT = 19
EXPECTED_MULTIPLIER_ARRAY_COUNT = 247
EXPECTED_SOURCE_SHA256 = "b13dd18254513a2d8a6d14ae1a21262b7c3183fea4a36d3c950a7f2e0186d172"
SOURCE_URL = (
    "https://raw.githubusercontent.com/Darctor/Helldivers2_RawData/"
    "52056ecb5637bf8d71481a724b019a6bd3b0e9ea/Data/entities/HiveMindComponentData.json"
)


class ContractError(ValueError):
    """Raised when an AI scaling input cannot be consumed safely."""


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _walk(value: Any, path: str = "") -> Iterable[tuple[str, list[Any]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}/{key}"
            if key == "player_count_multipliers":
                if isinstance(child, list):
                    yield child_path, child
                else:
                    # Keep malformed arrays in the audit rather than silently
                    # dropping them.  The caller will fail closed.
                    yield child_path, child  # type: ignore[misc]
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _source_vectors(document: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, Any]], str | None]:
    """Read either the public full export or our compact, tracked snapshot."""
    if isinstance(document.get("player_count_multiplier_arrays"), list):
        rows: list[tuple[str, Any]] = []
        for item in document["player_count_multiplier_arrays"]:
            if not isinstance(item, dict):
                rows.append(("<malformed snapshot entry>", item))
                continue
            rows.append((str(item.get("path", "<missing path>")), item.get("values")))
        metadata = document.get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}, rows, document.get("source_sha256")
    return document.get("_metadata", {}), list(_walk(document)), None


def _validate_vector(vector: Any, *, path: str = "<vector>") -> list[float]:
    if not isinstance(vector, list):
        raise ContractError(f"{path}: player_count_multipliers is not an array")
    if len(vector) != EXPECTED_ARRAY_LENGTH:
        raise ContractError(
            f"{path}: expected exactly {EXPECTED_ARRAY_LENGTH} legacy entries, got {len(vector)}"
        )
    if any(not _finite_number(item) for item in vector):
        raise ContractError(f"{path}: multiplier must be a finite number (no coercion)")
    values = [float(item) for item in vector]
    if any(not math.isfinite(item) or item < 0.0 for item in values):
        raise ContractError(f"{path}: multiplier must be finite and non-negative")
    return values


def resolve_multiplier(vector: Any, player_count: int) -> dict[str, Any]:
    """Resolve one multiplier under the bounded 1..8 policy.

    The fourth legacy value is deliberately reused for 5..8.  No arithmetic
    extrapolation and no indexing beyond index 3 are permitted.  Invalid
    counts and malformed vectors raise ``ContractError`` before any access.
    """
    values = _validate_vector(vector)
    if not isinstance(player_count, int) or isinstance(player_count, bool):
        raise ContractError("player_count must be an integer")
    if player_count < 1 or player_count > LOGICAL_MAX_PLAYERS:
        raise ContractError(f"player_count {player_count} outside 1..{LOGICAL_MAX_PLAYERS}")
    index = min(player_count, LEGACY_PLAYER_COUNT) - 1
    return {
        "player_count": player_count,
        "legacy_index": index,
        "value": values[index],
        "fallback": player_count > LEGACY_PLAYER_COUNT,
        "fallback_policy": "reuse_4_player_entry" if player_count > LEGACY_PLAYER_COUNT else None,
    }


def resolve_host_client(vector: Any, player_count: int, *, client_vector: Any = None,
                        client_count: int | None = None) -> dict[str, Any]:
    """Compare independently supplied host/client inputs using one policy.

    Default client inputs only exercise the policy deterministically; this
    function is not evidence that actual network peers have equal inputs.
    """
    client_vector = vector if client_vector is None else client_vector
    client_count = player_count if client_count is None else client_count
    if _validate_vector(vector) != _validate_vector(client_vector):
        raise ContractError("host/client AI scaling vectors diverged")
    host = resolve_multiplier(vector, player_count)
    client = resolve_multiplier(client_vector, client_count)
    if host != client:
        raise ContractError("host/client AI scaling result diverged")
    return {"host": host, "client": client, "equal": True}


def validate_version(build: str, source_sha256: str) -> None:
    """Validate reference contract identity; this never authorizes runtime use."""
    if build != BUILD:
        raise ContractError("unsupported build")
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ContractError("source snapshot fingerprint mismatch")


def audit_source(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    # Git on Windows may materialize CRLF.  Only CRLF->LF normalization is
    # allowed, and both byte-level hashes are recorded, never silently mixed.
    canonical_digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    document = json.loads(raw.decode("utf-8"))
    metadata, rows, embedded_source_sha256 = _source_vectors(document)
    invalid: list[dict[str, Any]] = []
    lengths: dict[str, int] = {}
    for row_path, vector in rows:
        try:
            _validate_vector(vector, path=row_path)
            lengths[str(len(vector))] = lengths.get(str(len(vector)), 0) + 1
        except ContractError as exc:
            invalid.append({"path": row_path, "error": str(exc)})
    canonical_matches = canonical_digest == EXPECTED_SOURCE_SHA256 or embedded_source_sha256 == EXPECTED_SOURCE_SHA256
    valid_shape = (
        metadata.get("game_version") == EXPECTED_GAME_VERSION
        and metadata.get("patch_date") == EXPECTED_PATCH_DATE
        and metadata.get("exported_entity_count") == EXPECTED_ENTITY_COUNT
        and len(rows) == EXPECTED_MULTIPLIER_ARRAY_COUNT
        and not invalid
    )
    return {
        "schema": "hd2_ai_scaling_contract_audit_v1",
        "build": BUILD,
        "source": {
            "path": str(path),
            "url": SOURCE_URL,
            "commit": "52056ecb5637bf8d71481a724b019a6bd3b0e9ea",
            "sha256": digest,
            "canonical_lf_sha256": canonical_digest,
            "canonicalization": "CRLF to LF only",
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "sha256_matches_pinned_snapshot": canonical_matches,
            "embedded_source_sha256": embedded_source_sha256,
        },
        "metadata": metadata,
        "player_count_multiplier_arrays": {
            "count": len(rows),
            "length_histogram": lengths,
            "invalid": invalid,
            "all_exactly_four": not invalid and all(len(vector) == 4 for _, vector in rows),
            "paths": [row_path for row_path, _ in rows],
        },
        "evidence": {
            "arrays_are_data_only": True,
            "native_consumer_indexing_observed": False,
            "5_to_8_native_behavior_proven": False,
            "same_build_correspondence_proven": False,
        },
        "contract": {
            "logical_max_players": LOGICAL_MAX_PLAYERS,
            "legacy_array_length": EXPECTED_ARRAY_LENGTH,
            "player_counts_1_to_4": "direct index player_count - 1",
            "player_counts_5_to_8": "reuse index 3 (four-player fallback)",
            "invalid_counts": "reject before indexing",
            "malformed_array": "reject before indexing",
            "host_client_policy": "same resolver and equal result required",
            "version_policy": "exact build and source metadata required before activation",
        },
        "safe_contract_ready": bool(valid_shape and canonical_matches),
        "runtime_activation_allowed": False,
        "encounter_consumer_resolved": False,
        "patrol_consumer_resolved": False,
        "host_client_runtime_consistency_verified": False,
        "process_accessed": False,
        "writes_made": False,
        "game_modified": False,
        "installable": False,
        "multiplayer_verified": False,
    }


def _synthetic_document() -> dict[str, Any]:
    return {
        "_metadata": {
            "game_version": EXPECTED_GAME_VERSION,
            "patch_date": EXPECTED_PATCH_DATE,
            "exported_entity_count": EXPECTED_ENTITY_COUNT,
        },
        "entities": [
            {"mission_difficulty_settings": {
                "encounter_points_modifier": {"player_count_multipliers": [1.0, 1.6, 2.2, 2.5]},
                "patrol_count_max_modifier": {"player_count_multipliers": [1.0, 1.35, 1.45, 1.6]},
            }}
        ],
    }


def self_test() -> dict[str, Any]:
    vector = [1.0, 1.6, 2.2, 2.5]
    checks: dict[str, bool] = {}
    checks["1_to_4_direct"] = [resolve_multiplier(vector, n)["legacy_index"] for n in range(1, 5)] == [0, 1, 2, 3]
    checks["5_to_8_reuse_four"] = all(
        resolve_multiplier(vector, n)["value"] == vector[3] and resolve_multiplier(vector, n)["fallback"]
        for n in range(5, 9)
    )
    checks["host_client_equal"] = all(resolve_host_client(vector, n)["equal"] for n in range(1, 9))
    for invalid in (0, -1, 9, 99):
        checks[f"reject_{invalid}"] = _expect_error(vector, invalid)
    checks["reject_short_vector"] = _expect_error([1.0, 2.0, 3.0], 5)
    checks["reject_long_vector"] = _expect_error([1.0, 2.0, 3.0, 4.0, 5.0], 5)
    checks["reject_nan"] = _expect_error([1.0, 2.0, float("nan"), 4.0], 5)
    with tempfile.TemporaryDirectory(prefix="hd2-ai-contract-") as temporary:
        temp_path = Path(temporary) / "HiveMind.synthetic.json"
        temp_path.write_text(json.dumps(_synthetic_document()), encoding="utf-8")
        report = audit_source(temp_path)
    checks["synthetic_audit_detects_arrays"] = report["player_count_multiplier_arrays"]["count"] == 2
    checks["synthetic_audit_shape"] = report["player_count_multiplier_arrays"]["all_exactly_four"]
    return {"schema": "hd2_ai_scaling_contract_self_test_v1", "checks": checks, "passed": all(checks.values())}


def _expect_error(vector: Any, player_count: int) -> bool:
    try:
        resolve_multiplier(vector, player_count)
    except ContractError:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Pinned HiveMindComponentData.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.source:
        result = audit_source(args.source)
        result["synthetic_verification"] = self_test()
    else:
        parser.error("--source or --self-test is required")
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        if args.output is None:
            raise SystemExit("--write requires --output")
        if args.output.exists():
            raise SystemExit(f"refusing to overwrite output: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(json.dumps({"schema": result["schema"], "passed": result.get("passed"), "safe_contract_ready": result.get("safe_contract_ready")}, ensure_ascii=False))
    return 0 if result.get("passed", result.get("safe_contract_ready", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
