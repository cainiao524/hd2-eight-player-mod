"""Regression tests for the offline AI scaling contract."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_scaling_contract_20261003 import (
    ContractError,
    EXPECTED_ARRAY_LENGTH,
    EXPECTED_ENTITY_COUNT,
    EXPECTED_GAME_VERSION,
    EXPECTED_PATCH_DATE,
    LOGICAL_MAX_PLAYERS,
    audit_source,
    resolve_host_client,
    resolve_multiplier,
    self_test,
    validate_version,
    BUILD,
    EXPECTED_SOURCE_SHA256,
)


def test_self_test_passes() -> None:
    result = self_test()
    assert result["passed"] is True
    assert all(result["checks"].values())


def test_five_to_eight_reuse_fourth_value() -> None:
    vector = [1.0, 1.6, 2.2, 2.5]
    for count in range(5, LOGICAL_MAX_PLAYERS + 1):
        result = resolve_multiplier(vector, count)
        assert result["legacy_index"] == EXPECTED_ARRAY_LENGTH - 1
        assert result["value"] == vector[-1]
        assert result["fallback"] is True


def test_host_and_client_are_identical() -> None:
    vector = [1.0, 1.25, 1.45, 1.6]
    for count in range(1, LOGICAL_MAX_PLAYERS + 1):
        result = resolve_host_client(vector, count)
        assert result["equal"] is True
        assert result["host"] == result["client"]


@pytest.mark.parametrize("count", [0, -1, 9, 99, True, 4.0, "5"])
def test_invalid_count_is_rejected_before_indexing(count: int) -> None:
    with pytest.raises(ContractError):
        resolve_multiplier([1.0, 2.0, 3.0, 4.0], count)


@pytest.mark.parametrize(
    "vector",
    [
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 2.0, float("nan"), 4.0],
        [1.0, 2.0, -1.0, 4.0],
        [1.0, 2.0, True, 4.0],
        [1.0, 2.0, "3.0", 4.0],
        [1.0, 2.0, None, 4.0],
    ],
)
def test_malformed_vector_is_rejected(vector: list[float]) -> None:
    with pytest.raises(ContractError):
        resolve_multiplier(vector, 5)


def test_source_audit_records_shape_and_version(tmp_path: Path) -> None:
    source = {
        "_metadata": {
            "game_version": EXPECTED_GAME_VERSION,
            "patch_date": EXPECTED_PATCH_DATE,
            "exported_entity_count": EXPECTED_ENTITY_COUNT,
        },
        "entities": [
            {"mission_difficulty_settings": {
                "encounter_points_modifier": {
                    "player_count_multipliers": [1.0, 1.6, 2.2, 2.5]
                },
                "patrol_count_max_modifier": {
                    "player_count_multipliers": [1.0, 1.35, 1.45, 1.6]
                },
            }}
        ],
    }
    path = tmp_path / "HiveMindComponentData.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    report = audit_source(path)
    arrays = report["player_count_multiplier_arrays"]
    assert arrays["count"] == 2
    assert arrays["all_exactly_four"] is True
    assert report["metadata"]["game_version"] == EXPECTED_GAME_VERSION
    assert report["evidence"]["native_consumer_indexing_observed"] is False
    assert report["runtime_activation_allowed"] is False
    assert report["safe_contract_ready"] is False


def test_tracked_compact_snapshot_is_replayable() -> None:
    snapshot = Path(__file__).with_name("ai_scaling_source_snapshot_20261003.json")
    report = audit_source(snapshot)
    assert report["source"]["sha256_matches_pinned_snapshot"] is True
    assert report["player_count_multiplier_arrays"]["count"] == 247
    assert report["player_count_multiplier_arrays"]["all_exactly_four"] is True
    assert report["safe_contract_ready"] is True


def test_client_mismatch_is_rejected_even_if_four_player_fallback_equal() -> None:
    with pytest.raises(ContractError):
        resolve_host_client([1, 2, 3, 4], 8, client_vector=[9, 2, 3, 4])
    with pytest.raises(ContractError):
        resolve_host_client([1, 2, 3, 4], 8, client_count=7)


def test_version_is_exact_and_does_not_coerce_build() -> None:
    validate_version(BUILD, EXPECTED_SOURCE_SHA256)
    for build, digest in [("25480439", EXPECTED_SOURCE_SHA256),
                          (25480438, EXPECTED_SOURCE_SHA256), (BUILD, "0" * 64)]:
        with pytest.raises(ContractError):
            validate_version(build, digest)
