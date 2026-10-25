"""Build and test this source mod; never discover an installation or run a game.

Requires an explicit, clean, pinned HellForge source checkout and Zig executable.
All game-facing callbacks during tests are fake. Backend transport stays in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: list[str | Path], cwd: Path = PROJECT) -> str:
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1")
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                            text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args[0]}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def summary(output: str, suite: str) -> dict:
    for line in output.splitlines():
        if line.startswith('{'):
            value = json.loads(line)
            if value.get("suite") == suite and value.get("passed") is True:
                return value
    raise RuntimeError(f"Missing successful result for {suite}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument("--zig", required=True, type=Path)
    args = parser.parse_args()
    upstream, zig = args.upstream.resolve(), args.zig.resolve()
    lock = json.loads((PROJECT / "upstream.lock.json").read_text(encoding="utf-8"))
    if run(["git", "rev-parse", "HEAD"], upstream).strip() != lock["commit"]:
        raise RuntimeError("HellForge commit differs from upstream.lock.json")
    if run(["git", "status", "--porcelain", "--untracked-files=no"], upstream).strip():
        raise RuntimeError("Use an unmodified HellForge source checkout")
    for name, sha in lock["source_sha256"].items():
        if digest(upstream / name) != sha:
            raise RuntimeError(f"Upstream source pin mismatch: {name}")
    for item in lock["reused_core"]:
        if digest(REPO / item["original"]) != item["sha256"] or digest(PROJECT / item["copy"]) != item["sha256"]:
            raise RuntimeError("Reused capacity contract differs from its pinned original")
    if digest(zig) != lock["zig"]["exe_sha256"] or run([zig, "version"]).strip() != lock["zig"]["version"]:
        raise RuntimeError("Zig differs from the checksum-verified pinned compiler")
    manifest = json.loads((PROJECT / "mod/hellforge-mod.json").read_text(encoding="utf-8"))
    if manifest["code"]["sdk"] != 13 or manifest["code"]["game"] != "25480438" or manifest["gameplay"] is not True:
        raise RuntimeError("Manifest does not describe the reviewed SDK/build/gameplay compatibility")
    build = PROJECT / "build"
    build.mkdir(exist_ok=True)
    sources = sorted((PROJECT / "mod/src").rglob("*.cpp"))
    templates=json.loads(run([sys.executable,'-B',PROJECT/'tools/generate_property_templates.py']))
    getter_template=json.loads(run([sys.executable,'-B',PROJECT/'tools/generate_getter_template.py']))
    mover_template=json.loads(run([sys.executable,'-B',PROJECT/'tools/generate_mover_template.py']))
    insert_templates=json.loads(run([sys.executable,'-B',PROJECT/'tools/generate_insert_templates.py']))
    dll = build / "ep_hellforge.dll"
    test = build / "adapter_test.exe"
    common = [zig, "c++", "-std=c++17", "-target", "x86_64-windows-gnu", "-O2", "-Wall", "-Werror",
              "-Wno-unused-parameter", "-I", upstream / "native/mod-sdk", "-I", PROJECT / "mod/src"]
    run([*common, "-shared", "-s", *sources, "-o", dll])
    run([*common, *sources, PROJECT / "tests/adapter_test.cpp", "-o", test])
    adapter = summary(run([test, dll]), "hellforge_adapter")
    backend = summary(run(["dotnet", "run", "--project", PROJECT / "tests/backend/Backend.csproj",
                           f"-p:HellForgeRoot={upstream.as_posix()}", "-p:PublishAot=false", "--configuration", "Release"]),
                      "hellforge_backend_eight_nodes")
    package = build / "eight-player-research-hellforge-0.1.0-source.zip"
    files = sorted(p for p in (PROJECT / "mod").rglob("*") if p.is_file())
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(PROJECT / "mod").as_posix(), (2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {p.relative_to(PROJECT / "mod").as_posix() for p in files}:
            raise RuntimeError("Source package verification failed")
        for path in files:
            if archive.read(path.relative_to(PROJECT / "mod").as_posix()) != path.read_bytes():
                raise RuntimeError("Packaged source mismatch")
    validation = {
        "schema": "hd2_hellforge_migration_validation_v1",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "upstream_commit": lock["commit"], "sdk": 13, "game_build": "25480438",
        "adapter": adapter, "backend": backend,
        "native_property_template_sha256": templates['header_sha256'],
        "native_getter_template_sha256":getter_template['header_sha256'],
        "native_mover_template_sha256":mover_template['header_sha256'],
        "native_insert_template_sha256":insert_templates['header_sha256'],
        "source_sha256": {p.relative_to(PROJECT).as_posix(): digest(p) for p in files},
        "test_source_sha256": {p.relative_to(PROJECT).as_posix(): digest(p) for p in [
            PROJECT / "tests/adapter_test.cpp", PROJECT / "tests/backend/Program.cs", PROJECT / "tests/backend/Backend.csproj",
            Path(__file__).resolve(), PROJECT / "upstream.lock.json", PROJECT / 'tools/generate_property_templates.py',PROJECT/'tools/generate_getter_template.py',PROJECT/'tools/generate_mover_template.py',PROJECT/'tools/generate_insert_templates.py']},
        "artifacts": {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in [dll, test, package]},
        "game_started": False, "game_checked": False, "game_read": False, "installed": False,
        "runtime_verified": False, "multiplayer_verified": False, "public_release_allowed": False,
    }
    (PROJECT / "evidence/offline-validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "adapter_checks": adapter["checks"], "backend_checks": backend["checks"],
                      "package": package.name, "game_access": False}))


if __name__ == "__main__":
    main()
