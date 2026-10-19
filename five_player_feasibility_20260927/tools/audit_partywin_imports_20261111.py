"""Audit fixed-build EXE imports for PartyWin/PlayFab multiplayer entrypoints.

This is a static PE check only.  It records named IAT entries and explicitly
reports core Session/Party methods that are absent from the EXE import table;
absence is evidence that an internal binding cannot be inferred from a normal
named import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pefile


CORE = {
    "PartyCreateNewNetwork",
    "PartyConnectToNetwork",
    "PartyNetworkAuthenticateLocalUser",
    "PartyNetworkCreateEndpoint",
    "PartyNetworkLeaveNetwork",
    "PartyNetworkRemoveLocalUser",
    "PartyCleanup",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.exe.read_bytes()
    image = pefile.PE(data=raw, fast_load=False)
    rows = []
    for entry in getattr(image, "DIRECTORY_ENTRY_IMPORT", []):
        dll = entry.dll.decode("utf-8", errors="replace")
        if "Party" not in dll and "PlayFab" not in dll:
            continue
        for imp in entry.imports:
            rows.append({
                "dll": dll,
                "name": imp.name.decode("utf-8", errors="replace") if imp.name else None,
                "ordinal": imp.ordinal,
                "iat_rva": hex(imp.address - image.OPTIONAL_HEADER.ImageBase),
            })
    names = {row["name"] for row in rows if row["name"]}
    receipt = {
        "schema": "hd2_partywin_named_import_audit_v1",
        "build": 25480438,
        "exe": str(args.exe),
        "exe_sha256": hashlib.sha256(raw).hexdigest(),
        "read_only": True,
        "named_imports": rows,
        "known_named_party_imports": sorted(names & {"PartyNetworkSetCustomContext"}),
        "known_named_playfab_imports": sorted(names & {"PFLobbySendInvite"}),
        "core_party_methods_absent_from_named_imports": sorted(CORE - names),
        "core_party_methods_all_named_imported": CORE <= names,
        "direct_named_core_binding_proven": CORE <= names,
        "limits": [
            "A missing named import does not prove that no internal EXE thunk exists.",
            "This audit does not call an entrypoint and does not infer an ABI from a slot address.",
        ],
    }
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "core_party_methods_all_named_imported": receipt["core_party_methods_all_named_imported"],
        "named_import_count": len(rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
