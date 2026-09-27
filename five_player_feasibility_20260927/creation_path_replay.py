"""Pin the exact-build lobby-creation and member-enumeration instructions.

Reads only the existing, fingerprint-checked offline capture. Does not load or
modify the game, and does not infer runtime targets of uncaptured pointers.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row  # noqa: E402


PINS = {
    "capacity_source": [
        0x10919CA, 0x10919D1, 0x10919D6, 0x10919DB, 0x10919DE,
    ],
    "initial_create": [
        0x1091A29, 0x1091A31, 0x1091A42, 0x1091A46,
        0x1091A76, 0x1091A7B, 0x1091A82, 0x1091A87,
        0x1091A8E, 0x1091A95, 0x1091A9C, 0x1091AA2, 0x1091AA5,
        0x1091AA7,
    ],
    "secondary_create_interface": [
        0x10919E4, 0x10919E9, 0x10919F6, 0x1091A01,
        0x1091845, 0x109184F, 0x109185B, 0x109185F,
        0x109186C, 0x1091870, 0x1091874, 0x109187A,
        0x109187C, 0x10918B5, 0x10918BC, 0x10918D4,
        0x10918DA, 0x10918DE, 0x10918E2, 0x10918E8,
        0x1091912, 0x1091930, 0x109193E, 0x1091948,
        0x1094475, 0x1094579,
    ],
    "recreate": [
        0x1093A6A, 0x1093A6F, 0x1093A76, 0x1093A7B, 0x1093A82,
        0x1093A89, 0x1093A90, 0x1093A96, 0x1093A99, 0x1093A9B,
    ],
    "initial_member_metadata": [
        0x10915DA, 0x10915DF, 0x10915E2, 0x10915E6,
    ],
    "numeric_key_config_builder": [
        0x10922C0, 0x1092305, 0x109230B, 0x1092312,
        0x109233D, 0x109234D, 0x109241B,
    ],
    "enumeration_helper": [
        0x1092E78, 0x1092E8C, 0x1092E93, 0x1092EC9, 0x1092ECB,
        0x1092ED0, 0x1092EDC, 0x1092F31, 0x1092F42, 0x1092F45,
    ],
    "enumeration_update": [
        0x1093C8B, 0x1093C91, 0x1093C96, 0x1093CCB, 0x1093CE0,
        0x1093CF8, 0x1093CFE, 0x1093D06, 0x1093D1E, 0x1093D2F,
    ],
    "ambiguous_lobby_strings": [
        0x10544B3, 0x1054529, 0x12CBB9A, 0x12CBD31, 0x133769E,
    ],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    image = Image(args.evidence)
    pins = {}
    for group, addresses in PINS.items():
        pins[group] = []
        for address in addresses:
            instruction = image.instruction(address)
            require(instruction is not None, f"not an instruction boundary: {address:#x}")
            item = row(instruction)
            item["root"] = hex(image.root(address)[0])
            pins[group].append(item)

    # The outgoing config builder uses numeric string keys; a separate
    # display-name table labels property index 4 NumMembers. This labels
    # current-member metadata, not the create call's capacity argument.
    key_pointer = struct.unpack("<Q", image.read(0x21D61E0, 8))[0]
    require(key_pointer - image.base == 0x22C65B0, "NumMembers key pointer moved")
    require(image.read(0x22C65B0, 11) == b"NumMembers\x00", "key text moved")
    numeric_key_pointer = struct.unpack("<Q", image.read(0x2264280, 8))[0]
    require(image.read(numeric_key_pointer - image.base, 2) == b"4\x00", "numeric key moved")

    # These globals reside in writable data that the earlier capture omitted.
    missing_globals = []
    for address in (0x3326308, 0x3326340):
        try:
            image.read(address, 8)
        except ValueError:
            missing_globals.append(hex(address))

    result = {
        "source": {
            "build_id": image.report["build_id"],
            "capture_sha256": image.report["capture_sha256"],
            "file_sha256": EXPECTED,
            "game_sha256": image.report["game_sha256"],
            "base_address": image.report["base_address"],
            "runtime_verified": image.report["runtime_verified"],
        },
        "pins": pins,
        "metadata_key_index_4": {
            "display_name_table_base_rva": "0x21d61c0",
            "display_name_pointer_rva": "0x21d61e0",
            "display_name_pointer_bytes": image.read(0x21D61E0, 8).hex(),
            "display_name_string_rva": "0x22c65b0",
            "display_name": "NumMembers",
            "outgoing_numeric_key_table_base_rva": "0x2264260",
            "numeric_key_pointer_rva": "0x2264280",
            "numeric_key_pointer_bytes": image.read(0x2264280, 8).hex(),
            "outgoing_numeric_key": "4",
        },
        "unavailable_writable_global_rvas": missing_globals,
        "limits": [
            "The +0xA0 function pointer is read from a runtime interface; its target and signature are not in this capture.",
            "The configuration value at [global 0x3326340]+0x20 is not captured; 4 is the code path when that value is zero.",
            "The creation argument base+4 is not proven to be a backend MaxPlayers value or eight playable slots.",
            "No game execution, service response, or fifth-player test was performed.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
