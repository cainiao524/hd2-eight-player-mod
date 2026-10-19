import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "integration_preflight_receipt_20261004.json"


def test_receipt_is_fail_closed_and_hashes_match():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "hd2_eight_player_integration_preflight_v1"
    assert receipt["steam_build"] == 25480438
    assert receipt["required_capacity"] == 8
    assert receipt["test"]["output"] == "ep_eight_preflight_synthetic_passed"
    assert receipt["test"]["status"] == "passed"
    assert all(value is False for value in receipt["gates"].values())
    for name, record in receipt["source_sha256"].items():
        digest = record["sha256"] if isinstance(record, dict) else record
        expected_bytes = record.get("bytes") if isinstance(record, dict) else None
        path = HERE / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        if expected_bytes is not None:
            assert path.stat().st_size == expected_bytes
    for name, record in receipt["binary_sha256"].items():
        digest = record["sha256"] if isinstance(record, dict) else record
        expected_bytes = record.get("bytes") if isinstance(record, dict) else None
        path = HERE / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        if expected_bytes is not None:
            assert path.stat().st_size == expected_bytes


def test_contract_rejects_partial_configuration():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["contract"]["all_component_capacities_must_equal"] == 8
    assert receipt["contract"]["authoritative_index_required"] is True
    assert receipt["contract"]["compact_ordinal_separate"] is True
    assert receipt["contract"]["holes_preserved"] is True
    assert receipt["contract"]["host_client_same_build"] is True
    assert "client_capacity_4" in receipt["test"]["rejections"]
