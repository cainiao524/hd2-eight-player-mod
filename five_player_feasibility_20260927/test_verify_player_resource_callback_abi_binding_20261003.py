from verify_player_resource_callback_abi_binding_20261003 import BUILD, CALLBACK_ORDER, CALLBACK_TABLES, verify


def test_fixed_build_callback_and_cleanup_binding_is_complete():
    report = verify()
    assert report["schema"] == "hd2_player_resource_callback_abi_binding_v1"
    assert report["build"] == BUILD
    assert report["callback_order"] == ["first_callback", "second_callback", "third_callback", "roster_insert"]
    assert report["callback_tables"] == CALLBACK_TABLES
    checks = report["checks"]
    assert all(checks[key] is True for key in (
        "fixed_build_matches",
        "callback_tables_match",
        "callback_stage_order_complete",
        "roster_component_matches",
        "roster_leaf_guard_and_writes_present",
        "resource_dispatch_abi_present",
        "resource_record_rollback_requirement_present",
        "reverse_cleanup_anchors_complete",
        "reverse_cleanup_edges_complete",
    ))
    assert checks["production_patch_ready"] is False
    assert checks["runtime_verified"] is False
    assert checks["installable"] is False
    assert checks["multiplayer_verified"] is False
