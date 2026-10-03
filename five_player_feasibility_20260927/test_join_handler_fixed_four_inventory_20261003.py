import json

import join_handler_fixed_four_inventory_20261003 as inventory


def test_all_join_handler_four_literals_are_classified():
    report = inventory.verify()
    assert report["verification_passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 7
    assert len(report["fixed_four_sites"]) == 5
    assert len(report["protected_four_literals"]) == 3
    assert report["decision"]["installable"] is False


def test_literal_classification_rejects_an_unreviewed_four(monkeypatch, tmp_path):
    source = inventory.DISASM
    data = json.loads(source.read_text(encoding="utf-8"))
    data["instructions"].append({"rva": "0x108c5d7", "bytes": "b804000000", "asm": "mov eax, 4", "sha256": ""})
    copy = tmp_path / source.name
    copy.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(inventory, "DISASM", copy)
    try:
        inventory.verify()
    except ValueError as exc:
        assert "unclassified_or_missing_literal_four" in str(exc)
    else:
        raise AssertionError("unclassified literal-four site was accepted")
