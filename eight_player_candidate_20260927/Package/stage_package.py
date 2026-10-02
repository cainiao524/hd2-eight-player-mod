"""Build a reversible staging bundle for the eight-player native bridge.

The existing Arsenal loader can merge data archives and dispatch Lua modules. It
cannot add an executable native hook to game.dll. This command therefore keeps
the loader-facing package declarative and requires a separately supplied native
payload before it will create a staging bundle. It never writes to the game
installation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BUILD = 25480438
EXE_VERSION = "1.8.46015.0"
FILES = {
    "bin/helldivers2.exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "data/game/game.dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
    "bin/PartyWin.dll": "de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0",
    "bin/PlayFabMultiplayerWin.dll": "95bc5f958e519f612b479de4227f3bdffaba9b2b8de987eb3f7991960b8ced17",
    "data/game/dl_library.dl_typelib": "f446aa15c11871bada4839f4c8ea890cea3b46405d09954468319ef61b092c5d",
    "data/game/generated_entities.dl_bin": "7df1a07e90c61e0b8398ecbc5c088074655900943bf1cd7e09f69bccedec4a2a",
}
REQUIRED_PLAN_FIELDS = {
    "trampoline_unwind_registration",
    "host_sidecar_lifetime",
    "client_sidecar_lifetime",
    "confirmed_peer_dispatch",
    "player_creation_gate",
    "capacity_midfunction_bridge",
    "allocator_sidecar_continuation",
    "instruction_relocation",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def validate_plan(plan_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    errors: list[str] = []
    if plan.get("steam_build") != BUILD:
        errors.append("native_plan_build_mismatch")
    if plan.get("executable") is not True:
        errors.append("native_plan_not_executable")
    if plan.get("multiplayer_verified") is not False:
        errors.append("native_plan_multiplayer_verified_must_remain_false")
    sidecar = plan.get("sidecar")
    if not isinstance(sidecar, dict) or sidecar.get("host_peer_slots") != 8 or sidecar.get("client_confirmed_slots") != 8:
        errors.append("native_plan_sidecar_must_declare_eight_slots")
    required = plan.get("requires")
    if not isinstance(required, list) or not REQUIRED_PLAN_FIELDS.issubset(required):
        errors.append("native_plan_missing_lifetime_or_dispatch_requirement")
    return {
        "path": str(plan_path),
        "sha256": sha256(plan_path) if plan_path.is_file() else None,
        "valid": not errors,
        "executable": plan.get("executable") is True,
        "errors": errors,
    }


def verify_game_root(game_root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    errors: list[str] = []
    if not game_root.is_dir():
        return {"valid": False, "files": [], "errors": ["game_root_missing"]}
    for rel, expected in FILES.items():
        path = game_root / Path(rel)
        actual = sha256(path) if path.is_file() else None
        ok = actual == expected
        files.append({"path": rel, "expected_sha256": expected, "actual_sha256": actual, "matched": ok})
        if not ok:
            errors.append(f"file_hash_mismatch:{rel}")
    exe = game_root / "bin/helldivers2.exe"
    version = None
    try:
        # Version is an additional human-readable guard; hash remains authoritative.
        import ctypes
        from ctypes import wintypes
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(exe), None)
        if size:
            buf = ctypes.create_string_buffer(size)
            ctypes.windll.version.GetFileVersionInfoW(str(exe), 0, size, buf)
            lp = ctypes.c_void_p()
            ln = wintypes.UINT()
            ctypes.windll.version.VerQueryValueW(buf, "\\", ctypes.byref(lp), ctypes.byref(ln))
            if ln.value:
                class VS_FIXEDFILEINFO(ctypes.Structure):
                    _fields_ = [
                        ("dwSignature", wintypes.DWORD),
                        ("dwStrucVersion", wintypes.DWORD),
                        ("dwFileVersionMS", wintypes.DWORD),
                        ("dwFileVersionLS", wintypes.DWORD),
                        ("dwProductVersionMS", wintypes.DWORD),
                        ("dwProductVersionLS", wintypes.DWORD),
                        ("dwFileFlagsMask", wintypes.DWORD),
                        ("dwFileFlags", wintypes.DWORD),
                        ("dwFileOS", wintypes.DWORD),
                        ("dwFileType", wintypes.DWORD),
                        ("dwFileSubtype", wintypes.DWORD),
                        ("dwFileDateMS", wintypes.DWORD),
                        ("dwFileDateLS", wintypes.DWORD),
                    ]
                info = ctypes.cast(lp, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
                version = ".".join(
                    str(value)
                    for value in (
                        info.dwFileVersionMS >> 16,
                        info.dwFileVersionMS & 0xFFFF,
                        info.dwFileVersionLS >> 16,
                        info.dwFileVersionLS & 0xFFFF,
                    )
                )
    except Exception:
        # Hash guard still works on non-Windows test runners.
        version = None
    if version and version != EXE_VERSION:
        errors.append("exe_version_mismatch")
    return {"valid": not errors, "files": files, "exe_version": version, "errors": errors}


def build_diagnostics(game_root: Path, plan_path: Path, native_payload: Path | None) -> dict[str, Any]:
    plan = validate_plan(plan_path)
    build = verify_game_root(game_root)
    payload_ok = bool(native_payload and native_payload.is_file())
    errors = list(plan["errors"]) + list(build["errors"])
    if not payload_ok:
        errors.append("native_payload_missing")
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_staging" if not errors else "blocked",
        "activation_allowed": not errors,
        "game_root": str(game_root),
        "target": {"steam_build": BUILD, "exe_version": EXE_VERSION, "files": FILES},
        "native_plan": plan,
        "game_files": build,
        "native_payload": {"path": str(native_payload) if native_payload else None, "present": payload_ok},
        "errors": errors,
        "multiplayer_verified": False,
        "installation_performed": False,
    }


def stage(template_root: Path, output: Path, diagnostics: dict[str, Any], native_payload: Path | None) -> None:
    if not diagnostics["activation_allowed"]:
        raise RuntimeError("activation gate blocked: " + ", ".join(diagnostics["errors"]))
    game_root = Path(diagnostics["game_root"]).resolve()
    output_resolved = output.resolve()
    try:
        output_resolved.relative_to(game_root)
    except ValueError:
        pass
    else:
        raise RuntimeError("refusing to stage inside the game installation")
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing staging directory: {output}")
    output.mkdir(parents=True)
    for rel in ("manifest.json", "package.json", "README.zh-TW.md", "rollback.json", "diagnostics.json", "data"):
        src = template_root / rel
        if src.is_dir():
            shutil.copytree(src, output / rel)
        elif src.is_file():
            shutil.copy2(src, output / rel)
    if native_payload:
        (output / "native").mkdir()
        shutil.copy2(native_payload, output / "native" / native_payload.name)
    rollback = {
        "schema_version": 1,
        "mode": "reversible_staging_only",
        "game_root": diagnostics["game_root"],
        "activation": "native bridge must be stopped before removal",
        "restore": "remove only files listed under installed_files; restore backup_paths if populated",
        "installed_files": [],
        "backup_paths": [],
        "target_build": BUILD,
        "target_hashes": FILES,
    }
    (output / "rollback.json").write_text(json.dumps(rollback, indent=2) + "\n", encoding="utf-8")
    (output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--native-plan", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--native-payload", type=Path)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--stage-output", type=Path)
    args = parser.parse_args(argv)
    diagnostics = build_diagnostics(args.game_root, args.native_plan, args.native_payload)
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    args.diagnostics.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")
    if args.stage_output:
        try:
            stage(args.template_root, args.stage_output, diagnostics, args.native_payload)
        except RuntimeError as exc:
            print(f"blocked: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(diagnostics, indent=2))
    return 0 if diagnostics["activation_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
