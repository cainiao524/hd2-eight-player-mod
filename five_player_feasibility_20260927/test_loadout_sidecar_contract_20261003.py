import pytest

from loadout_sidecar_contract_20261003 import LoadoutSidecar, LoadoutToken, synthetic_report


def test_loadout_sidecar_preserves_holes_and_separates_keys():
    sidecar = LoadoutSidecar(0x1000)
    tokens = [sidecar.reserve(i, i, 100 + i) for i in range(8)]
    for token in tokens:
        sidecar.confirm(token)
    sidecar.begin_release(tokens[7])
    sidecar.finish_release(tokens[7])
    sidecar.move_ui(tokens[0], 7)
    sidecar.begin_release(tokens[2])
    sidecar.finish_release(tokens[2])
    assert sidecar.get(2) is None
    replacement = sidecar.reserve(2, 0, 202)
    assert replacement.generation == 2
    sidecar.confirm(replacement)
    assert sidecar.get(2).ui_slot == 0
    assert sidecar.by_widget(202).network_index == 2
    sidecar.validate()


def test_loadout_sidecar_rejects_stale_or_duplicate_operations():
    sidecar = LoadoutSidecar(0x1000)
    token = sidecar.reserve(4, 4, 404)
    other = sidecar.reserve(5, 5, 505)
    with pytest.raises(ValueError, match="occupied"):
        sidecar.reserve(4, 5, 405)
    with pytest.raises(ValueError, match="stale"):
        sidecar.confirm(LoadoutToken(4, token.generation + 1))
    sidecar.confirm(token)
    with pytest.raises(ValueError, match="confirmed"):
        sidecar.confirm(token)
    with pytest.raises(ValueError, match="occupied"):
        sidecar.move_ui(token, other.network_index)
    sidecar.begin_release(token)
    with pytest.raises(ValueError, match="releasing"):
        sidecar.move_ui(token, 6)


def test_loadout_sidecar_report_is_fail_closed_and_json_safe():
    report = synthetic_report()
    assert report["schema"] == "hd2_loadout_sidecar_contract_v1"
    assert report["build"] == 25480438
    assert report["capacity"] == 8
    assert report["active_records"] == 8
    assert report["hole_preserved_after_release"] is True
    assert report["network_index_ui_slot_separate"] is True
    assert report["production_patch_ready"] is False
    assert report["runtime_verified"] is False
    assert report["installable"] is False
    assert report["multiplayer_verified"] is False
