import pytest
import verify_live_capture_current_20261003 as current

verify = current.verify


def test_current_live_capture_receipt() -> None:
    result = verify()
    assert result["verification_passed"] is True
    assert result["checks_passed"] == result["checks_total"]
    assert result["multiplayer_verified"] is False
    assert result["installable"] is False


@pytest.mark.parametrize("filename, mutate, failed_check", [
    ("live_native_sites_20261003_r4.json", lambda d: d["sites"][0].update(bytes="00" * 4096), "native_sites_reread_stable"),
    ("live_session_member_sites_20261003_r3.json", lambda d: d["sites"][0].update(reread_sha256="0" * 64), "session_sites_reread_stable"),
    ("live_session_snapshot_20261003_r10.json", lambda d: d.pop("writes_made"), "no_process_mutation"),
    ("live_dispatcher_data_20261003_r5.json", lambda d: d.pop("eight_player_verified"), "read_only_flags"),
    ("live_registration_state_20261003_16m_r2.json", lambda d: d["scan_stats"].update(memory_bytes_read=4096), "bounded_registration_scan"),
    ("live_registration_state_20261003_16m_r2.json", lambda d: d["postflight"].update(module_list_unchanged=False), "bounded_registration_scan"),
    ("live_session_snapshot_20261003_r10.json", lambda d: d.pop("pid"), "same_live_pid"),
    ("live_session_snapshot_20261003_r10.json", lambda d: d["pinned_images"]["game.dll"].update(base=1), "same_live_pid"),
])
def test_capture_mutations_fail_validation(monkeypatch, filename, mutate, failed_check):
    original_read = current.read

    def changed_read(name):
        result = original_read(name)
        if name == filename:
            mutate(result)
        return result

    monkeypatch.setattr(current, "read", changed_read)
    result = verify()
    assert result["verification_passed"] is False
    assert next(row for row in result["checks"] if row["name"] == failed_check)["passed"] is False
