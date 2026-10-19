"""Read-only audit of the fixed-build native loader boundary.

This deliberately inspects files only.  It does not start Helldivers 2,
open a process handle, load a DLL, patch bytes, or install anything.  The
result is evidence for the package gate, not a loader or an activation path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pefile


BUILD = 25480438
APP_ID = "553850"
OFFICIAL_CHAIN = (
    "bin/helldivers2.exe",
    "data/game/game.dll",
    "bin/PartyWin.dll",
    "bin/PlayFabMultiplayerWin.dll",
    "bin/steam_api64.dll",
    "bin/lua51.dll",
)
KNOWN_USER_LOADERS = re.compile(r"(?i)(?:^|[-_. ])(?:arsenal|bingus|hd2mm)(?:[-_. ]|$)")
DISALLOWED_INJECTION_NAMES = re.compile(
    r"(?i)(?:havoc|hh\.sys|pyinjector|(?:^|[/\\])dxgi\.dll$)"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pe_inventory(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": path.as_posix(),
        "present": path.is_file(),
        "sha256": sha256(path) if path.is_file() else None,
        "exports": [],
        "imports": [],
        "parse_error": None,
    }
    if not path.is_file():
        return result
    try:
        pe = pefile.PE(str(path), fast_load=False)
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            result["exports"] = sorted(
                (item.name.decode("ascii", "replace") if item.name else "")
                for item in pe.DIRECTORY_ENTRY_EXPORT.symbols
            )
        if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
            result["imports"] = sorted(
                {entry.dll.decode("ascii", "replace") for entry in pe.DIRECTORY_ENTRY_IMPORT}
            )
    except Exception as exc:  # pragma: no cover - depends on target binaries
        result["parse_error"] = f"{type(exc).__name__}: {exc}"
    return result


def audit(game_root: Path) -> dict[str, Any]:
    official = [pe_inventory(game_root / rel) for rel in OFFICIAL_CHAIN]
    all_files = [p for p in game_root.rglob("*") if p.is_file()] if game_root.is_dir() else []
    loader_matches = [
        p.relative_to(game_root).as_posix()
        for p in all_files
        if KNOWN_USER_LOADERS.search(p.name)
    ]
    injection_matches = [
        p.relative_to(game_root).as_posix()
        for p in all_files
        if DISALLOWED_INJECTION_NAMES.search(p.relative_to(game_root).as_posix())
    ]
    game_exports = next((item["exports"] for item in official if item["path"].endswith("data/game/game.dll")), [])
    game_imports = next((item["imports"] for item in official if item["path"].endswith("bin/helldivers2.exe")), [])
    return {
        "schema": "hd2_native_loader_boundary_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "steam_app_id": APP_ID,
        "steam_build": BUILD,
        "game_root": str(game_root),
        "official_chain": official,
        "game_dll_exports": game_exports,
        "helldivers2_imports": game_imports,
        "known_user_loader_matches": sorted(loader_matches),
        "disallowed_injection_artifacts": sorted(injection_matches),
        "observations": [
            "The official executable imports Party/PlayFab/Steam/Lua libraries but no user Mod, Plugin or Loader entry.",
            "game.dll exposes only get_plugin_api in the static export table; this is not a proven player-admission ABI.",
            "PartyWin and PlayFabMultiplayerWin are official networking APIs and do not prove game-layer roster expansion.",
            "Havoc/HH.sys/pyinjector artifacts are classified as disallowed injection tooling and are excluded from this audit's activation path.",
        ],
        "supported_native_loader_found": bool(loader_matches),
        "production_native_entry_proven": False,
        "read_only": True,
        "process_started": False,
        "process_mutated": False,
        "installable": False,
        "multiplayer_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.game_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
