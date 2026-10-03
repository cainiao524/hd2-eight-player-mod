import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "resource_bridge_adapter_receipt_20261003.json"


def test_receipt_is_fail_closed_and_hashes_match():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["schema"] == "hd2_resource_bridge_adapter_receipt_v1"
    assert receipt["steam_build"] == 25480438
    assert receipt["tests"]["status"] == "passed"
    assert receipt["tests"]["adapter_output"] == "ep_resource_bridge_adapter_synthetic_passed"
    assert all(value is False for value in receipt["checks"].values())
    for name, digest in receipt["source_sha256"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    for name, digest in receipt["binary_sha256"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest


def test_transaction_contract_is_explicit_and_index_preserving():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    contract = receipt["contract"]
    assert contract["stage_callback_version"] == 1
    assert contract["valid_network_indexes"] == [0, 7]
    assert contract["exact_index_passthrough"] is True
    assert contract["transaction_order"][-1] == "resource_publish"
    assert "stage failure" in contract["fail_closed"]
