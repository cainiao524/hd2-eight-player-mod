"""Read-only live-build preflight for the fixed Helldivers 2 eight-player candidate.

This module only reads explicitly supplied files, the native admission-plan JSON,
and (on Windows) the process list.  It never patches, injects, installs, copies,
or deletes game files.  A passing result means that a reversible staging step may
be considered; it never means that the native hook is executable or that a
multiplayer mission has succeeded.

The six hashes below are pinned observations for Steam build 25480438.  They are
kept separate from ``Integration/build_profile.py`` so that the existing offline
profile remains fail-closed and unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Callable

try:  # direct execution from this directory
    from build_profile import GateError, _reparse, _root
except ImportError:  # package-style import in a caller's test runner
    from .build_profile import GateError, _reparse, _root


STEAM_BUILD = 25480438
EXE_VERSION = "1.8.46015.0"
PLAN_SCHEMA = 1
PROCESS_NAME = "helldivers2.exe"

ROLE_FILES: dict[str, str] = {
    "exe": "bin/helldivers2.exe",
    "game_dll": "data/game/game.dll",
    "party": "bin/PartyWin.dll",
    "playfab_multiplayer": "bin/PlayFabMultiplayerWin.dll",
    "data_typelib": "data/game/dl_library.dl_typelib",
    "data_entities": "data/game/generated_entities.dl_bin",
}

EXPECTED_HASHES: dict[str, str] = {
    "exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game_dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
    "party": "de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0",
    "playfab_multiplayer": "95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17",
    "data_typelib": "f446aa15c11871bada4839f4c8ea890cea3b46405d09954468319ef61b092c5d",
    "data_entities": "7df1a07e90c61e0b8398ecbc5c088074655900943bf1cd7e09f69bccedec4a2a",
}


def _safe_json(path: Path) -> dict[str, Any]:
    """Read one regular JSON file without following a reparse point."""
    path = Path(path).absolute()
    if _reparse(path):
        raise GateError("native plan is a symlink or reparse point")
    if not path.is_file():
        raise GateError("native plan must be an existing regular file")
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise GateError("native plan path resolves through a symlink or reparse point")
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError("native plan is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise GateError("native plan JSON root must be an object")
    return value


def _hash_file(path: Path) -> tuple[str, int]:
    """Hash a regular file and detect a replacement while it is being read."""
    if _reparse(path):
        raise GateError("game file is a symlink or reparse point: " + str(path))
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise GateError("game file is not a regular file: " + str(path))
        hasher = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            hasher.update(chunk)
        after = os.fstat(stream.fileno())
    final = path.stat()
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if stamp(before) != stamp(after) or stamp(after) != stamp(final) or size != after.st_size:
        raise GateError("game file changed while being read: " + str(path))
    return hasher.hexdigest(), size


def _check_reparse_chain(path: Path) -> None:
    """Reject a root reached through a symlink/junction in any parent component."""
    absolute = Path(path).absolute()
    # Checking every component also catches a junction in a parent such as a
    # Steam-library link.  ``anchor`` is a drive root on Windows.
    chain = list(reversed(absolute.parents)) + [absolute]
    for component in chain:
        try:
            if _reparse(component):
                raise GateError("game root contains a symlink or reparse point: " + str(component))
        except FileNotFoundError:
            # Missing parents are handled by _root with a clearer error.
            continue


def _detect_process(name: str = PROCESS_NAME) -> bool | None:
    """Return True/False from tasklist, or None when stopped-state is unknown."""
    if os.name != "nt":
        return None
    try:
        completed = subprocess.run(
            ["tasklist.exe", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {name}"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    needle = '"' + name.casefold() + '"'
    return any(line.strip().casefold().startswith(needle) for line in completed.stdout.splitlines())


def _validate_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if type(plan.get("steam_build")) is not int or plan.get("steam_build") != STEAM_BUILD:
        errors.append("native_plan_build_mismatch")
    if type(plan.get("executable")) is not bool:
        errors.append("native_plan_executable_must_be_boolean")
    if type(plan.get("multiplayer_verified")) is not bool:
        errors.append("native_plan_multiplayer_verified_must_be_boolean")
    if plan.get("multiplayer_verified") is True:
        # This preflight is not allowed to manufacture a multiplayer claim.
        errors.append("native_plan_multiplayer_verified_must_remain_false")
    sidecar = plan.get("sidecar")
    if not isinstance(sidecar, dict) or sidecar.get("host_peer_slots") != 8 or sidecar.get("client_confirmed_slots") != 8:
        errors.append("native_plan_sidecar_must_declare_eight_slots")
    return not errors, errors


def preflight(
    game_root: Path,
    native_plan: Path,
    *,
    expected_build: int = STEAM_BUILD,
    require_stopped: bool = True,
    process_check: Callable[[str], bool | None] = _detect_process,
) -> dict[str, Any]:
    """Verify the fixed build and native plan without making any changes."""
    result: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA,
        "steam_build": STEAM_BUILD,
        "expected_exe_version": EXE_VERSION,
        "status": "blocked",
        "build_verified": False,
        "files_verified": False,
        "native_peer_admission_plan": {"path": str(native_plan), "valid": False, "executable": False,
                                        "multiplayer_verified": False, "errors": []},
        "process_name": PROCESS_NAME,
        "process_running": None,
        "stopped_process_gate_passed": False,
        "staging_preflight_passed": False,
        "pre_install_gate_passed": False,
        "live_ready": False,
        "installation_authorized": False,
        "multiplayer_verified": False,
        "process_accessed": False,
        "installation_performed": False,
        "files": [],
        "errors": [],
        "blockers": [],
        "remaining_gates": ["multiplayer_verification_required_for_live_ready"],
    }
    if expected_build != STEAM_BUILD:
        result["errors"].append("unsupported_expected_build")
        result["blockers"].append("steam_build_contract_is_25480438")
        return result
    try:
        _check_reparse_chain(Path(game_root))
        root = _root(Path(game_root))
    except (OSError, GateError) as exc:
        result["errors"].append(str(exc))
        result["blockers"].append("invalid_game_root")
        return result

    for role, relative in ROLE_FILES.items():
        row: dict[str, Any] = {"role": role, "path": relative,
                               "expected_sha256": EXPECTED_HASHES[role],
                               "observed_sha256": None, "size": None, "matched": False,
                               "status": "missing"}
        try:
            # Explicitly validate each path component under the selected root.
            file_path = root.joinpath(*relative.split("/"))
            if _reparse(file_path):
                raise GateError("symlink or reparse point")
            resolved = file_path.resolve(strict=True)
            if not resolved.is_relative_to(root) or resolved != file_path:
                raise GateError("path resolves outside the explicit game root")
            observed, size = _hash_file(file_path)
            row.update(observed_sha256=observed, size=size,
                       matched=observed == EXPECTED_HASHES[role],
                       status="matched" if observed == EXPECTED_HASHES[role] else "mismatch")
            if observed != EXPECTED_HASHES[role]:
                result["errors"].append("fingerprint_mismatch:" + role)
        except (OSError, GateError) as exc:
            row["status"] = "rejected"
            row["error"] = str(exc)
            result["errors"].append(role + ":" + str(exc))
        result["files"].append(row)
    result["files_verified"] = all(row["matched"] for row in result["files"])
    result["build_verified"] = result["files_verified"] and expected_build == STEAM_BUILD
    if not result["files_verified"]:
        result["blockers"].append("six_pinned_build_fingerprints_not_verified")

    try:
        plan = _safe_json(Path(native_plan))
        valid, plan_errors = _validate_plan(plan)
        plan_result = result["native_peer_admission_plan"]
        plan_result.update(valid=valid, executable=plan.get("executable") is True,
                           multiplayer_verified=plan.get("multiplayer_verified") is True,
                           errors=plan_errors)
        if not valid:
            result["errors"].extend(plan_errors)
            result["blockers"].append("native_peer_admission_plan_invalid")
        if valid and not plan.get("executable"):
            result["blockers"].append("native_peer_admission_plan_not_executable")
    except (OSError, GateError) as exc:
        result["errors"].append("native_plan:" + str(exc))
        result["blockers"].append("native_peer_admission_plan_unreadable")

    if require_stopped:
        process_state = process_check(PROCESS_NAME)
        result["process_accessed"] = process_state is not None
        result["process_running"] = process_state
        if process_state is True:
            result["blockers"].append("game_process_running_staging_requires_stopped_process")
        elif process_state is None:
            result["blockers"].append("cannot_verify_game_process_stopped")
        else:
            result["stopped_process_gate_passed"] = True
    else:
        result["stopped_process_gate_passed"] = True

    plan_result = result["native_peer_admission_plan"]
    result["staging_preflight_passed"] = bool(
        result["build_verified"] and result["stopped_process_gate_passed"]
        and plan_result["valid"] and plan_result["executable"]
        and plan_result["multiplayer_verified"] is False
    )
    result["pre_install_gate_passed"] = result["staging_preflight_passed"]
    if result["staging_preflight_passed"]:
        result["status"] = "ready_for_reversible_staging"
    # Keep these claims false even on a successful preflight.  Only a separate
    # eight-account mission record can ever set multiplayer_verified true.
    result["live_ready"] = False
    result["installation_authorized"] = False
    result["multiplayer_verified"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True,
                        help="explicit Helldivers 2 installation root")
    parser.add_argument("--native-plan", type=Path, required=True,
                        help="explicit native_peer_admission_plan JSON path")
    parser.add_argument("--expected-build", type=int, default=STEAM_BUILD)
    parser.add_argument("--allow-running", action="store_true",
                        help="skip the stopped-process gate for read-only inspection")
    args = parser.parse_args(argv)
    result = preflight(args.game_root, args.native_plan,
                       expected_build=args.expected_build,
                       require_stopped=not args.allow_running)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("staging_preflight_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
