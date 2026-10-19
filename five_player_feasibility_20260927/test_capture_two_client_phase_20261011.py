"""Exercise the phase command using a file-only reader; never access a process."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest


SCRIPT = Path(__file__).with_name("capture_two_client_phase_20261011.py")


def run_phase(tmp_path=None, *, status="observed_context", pid=123, errors=None, exit_code=0):
    tmp_path = tmp_path or Path(tempfile.mkdtemp(prefix=".phase-capture-test-", dir=SCRIPT.parent))
    document = {
        "schema": "hd2_live_session_snapshot_v1", "pid": pid, "status": status,
        "read_only": True, "calls_made": False, "writes_made": False,
        "hooks_installed": False, "errors": errors or [],
    }
    reader = tmp_path / "file_only_reader.py"
    reader.write_text(
        "import json, pathlib, sys\n"
        f"document = json.loads({json.dumps(document)!r})\n"
        "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "output.write_text(json.dumps(document), encoding='utf-8')\n"
        "print('file-only fixture', file=sys.stderr)\n"
        f"raise SystemExit({exit_code})\n", encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-B", str(SCRIPT.resolve()), "--pid", "123",
         "--phase", "host_before", "--output-dir", str(tmp_path / "output"),
         "--reader", str(reader)],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    receipt = json.loads((tmp_path / "output" / "two_client_host_before_receipt.json").read_text(encoding="utf-8"))
    return completed, receipt


def remove_test_directory(path):
    shutil.rmtree(path, ignore_errors=True)


def test_default_reader_resolves_to_existing_tool():
    spec = importlib.util.spec_from_file_location("phase_capture", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_READER.is_absolute()
    assert module.DEFAULT_READER.is_file()
    assert module.DEFAULT_READER.parent.name == "tools"


def test_successful_capture_from_another_working_directory():
    tmp_path = Path(tempfile.mkdtemp(prefix=".phase-capture-test-", dir=SCRIPT.parent))
    try:
        completed, receipt = run_phase(tmp_path)
        assert completed.returncode == 0, completed.stderr
        assert receipt["snapshot_observed"] is True
        assert receipt["snapshot_valid_read_only"] is True
        assert receipt["snapshot_error"] is None
    finally:
        remove_test_directory(tmp_path)


@pytest.mark.parametrize("fields", [
    {"status": "blocked_no_context"},
    {"status": "blocked_partial_context"},
    {"pid": 124},
    {"errors": ["roster_read_failed"]},
])
def test_failed_observation_is_not_a_successful_capture(fields):
    tmp_path = Path(tempfile.mkdtemp(prefix=".phase-capture-test-", dir=SCRIPT.parent))
    try:
        completed, receipt = run_phase(tmp_path, **fields)
        assert completed.returncode == 2
        assert receipt["snapshot_valid_read_only"] is True
        assert receipt["snapshot_observed"] is False
        assert receipt["snapshot_error"] == "snapshot_not_observed_for_requested_pid"
    finally:
        remove_test_directory(tmp_path)


def test_reader_failure_keeps_diagnostics():
    tmp_path = Path(tempfile.mkdtemp(prefix=".phase-capture-test-", dir=SCRIPT.parent))
    try:
        completed, receipt = run_phase(tmp_path, exit_code=7)
        assert completed.returncode == 2
        assert receipt["reader_returncode"] == 7
        assert "file-only fixture" in receipt["reader_stderr"]
    finally:
        remove_test_directory(tmp_path)


def test_existing_phase_is_not_overwritten():
    tmp_path = Path(tempfile.mkdtemp(prefix=".phase-capture-test-", dir=SCRIPT.parent))
    try:
        first, receipt = run_phase(tmp_path)
        assert first.returncode == 0
        snapshot = Path(receipt["snapshot"])
        before = snapshot.read_bytes()
        second, _ = run_phase(tmp_path, status="blocked_no_context")
        assert second.returncode != 0
        assert "refusing to overwrite" in second.stderr
        assert snapshot.read_bytes() == before
    finally:
        remove_test_directory(tmp_path)
