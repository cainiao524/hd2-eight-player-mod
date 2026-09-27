"""Offline resource-name matching and post-handle dispatch evidence."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row

FILES = {
    "FileDiver/stingray/hash.go": "3206b6f98f75401266f6ce374a5b41c1fa8e491d36e6b8c606df48d7b369cbd5",
    "FileDiver/stingray/hash_test.go": "4c0b4b7b619b579264880880aaee0caca90769fef61e6697a48032d3f2cde9b1",
    "FileDiver/hashes/hashes.txt": "a9ee27bff4766c07d92a713667e467fc6c6449b49ad5cad66896d2bc4a5cb63b",
    "FileDiver/hashes/thinhashes.txt": "a0bdca1e94555551c825f067f718dba98454a14a7752318d5a26a34be44f5fb5",
}
TARGETS = {0xB04D927AFB137B9B, 0x4D1C334D294DFA97, 0xCDC1F82CE3337A82}
PINS = {
    "respawn_resource_and_returned_handle": [
        0xAC9B9F, 0xAC9BB0, 0xAC9BE4, 0xAC9BE9, 0xAC9BF7,
        0xAC9BFE, 0xAC9C05, 0xAC9C08, 0xAC9C0B, 0xAC9C15,
        0xAC9C19, 0xAC9C23, 0xAC9C26, 0xAC9C28, 0xAC9C2B,
        0xAC9C2D, 0xAC9C42, 0xAC9C49, 0xAC9C4C, 0xAC9C4E,
    ],
    "index_gated_resource_variant": [
        0x1086823, 0x1086837, 0x10868AA, 0x10868B1, 0x10868B4,
        0x10868BB, 0x10868BF, 0x10868C9, 0x10868CC,
        0x10868CE, 0x10868D5, 0x10868D7,
    ],
    "resource_handle_record_and_dispatch": [
        0xFDC165, 0xFDC172, 0xFDC175, 0xFDC178, 0xFDC184,
        0xFDC18B, 0xFDC18E, 0xFDC191, 0xFDC1A4, 0xFDC1AC,
        0xFDC1AF, 0xFDC1BB, 0xFDC1C3, 0xFDC207, 0xFDC20D,
        0xFDC214, 0xFDC221, 0xFDC24C, 0xFDC250, 0xFDC254,
        0xFDC257, 0xFDC25A, 0xFDC2A0, 0xFDC2AA, 0xFDC2AD,
        0xFDC2B1,
    ],
    "component_list_to_callback_tables": [
        0x581348, 0x581353, 0x581366, 0x581377, 0x58138B,
        0x5813AA, 0x5813B2, 0x5813D8, 0x5813F9, 0x581403,
        0x58140A, 0x58140E, 0x581416, 0x58141B, 0x58141E, 0x581421,
        0x581505, 0x581509, 0x58152F,
        0x5817AA, 0x5817AD, 0x5817B0, 0x5817B3, 0x5817E2,
        0x58180D, 0x581A1E, 0x581A30, 0x581A37, 0x581A3B,
        0x581A43, 0x581A48, 0x581A4B, 0x581A4E,
    ],
}


def murmur64a(data):
    mask, mix = (1 << 64) - 1, 0xC6A4A7935BD1E995
    value, at = len(data) * mix & mask, 0
    while at + 8 <= len(data):
        key = int.from_bytes(data[at:at+8], "little")
        at += 8
        key = key * mix & mask
        key ^= key >> 47
        key = key * mix & mask
        value ^= key
        value = value * mix & mask
    if at < len(data):
        value ^= int.from_bytes(data[at:], "little")
        value = value * mix & mask
    value ^= value >> 47
    value = value * mix & mask
    return value ^ (value >> 47)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), "Refusing overwrite")
    im = Image(args.evidence)
    matches, checked = [], {}
    # Independent expected values are copied from the pinned FileDiver tests.
    require(murmur64a(b"hello, world!") == 0xD18ABE154A2A9637, "Hash vector 1 mismatch")
    require(murmur64a(b"hello, world!!!!") == 0x2F9DEA7BD39B9F7D, "Hash vector 2 mismatch")
    for relative, expected in FILES.items():
        raw = (ROOT / relative).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "Source changed: " + relative)
        if not relative.endswith(".txt"):
            continue
        checked[relative] = 0
        for line_no, name in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
            if not name or name.startswith("//"):
                continue
            checked[relative] += 1
            value = murmur64a(name.encode("utf-8"))
            if value in TARGETS:
                matches.append({"file": relative, "line": line_no, "name": name, "hash": hex(value)})
    pins = {}
    for group, addresses in PINS.items():
        pins[group] = []
        for address in addresses:
            ins = im.instruction(address)
            require(ins is not None, f"Unproven instruction boundary {address:#x}")
            pins[group].append({**row(ins), "root": hex(im.root(address)[0])})
    require(im.read(0x225D3A8, 12) == b"entity_path\0", "Entity path label changed")
    result = {
        "capture_sha256": im.report["capture_sha256"], "source_sha256": EXPECTED,
        "name_and_algorithm_file_sha256": FILES, "hash_vectors_passed": 2,
        "names_checked": checked, "resource_name_matches": matches, "pins": pins,
        "entity_path_label": {"rva": "0x225d3a8", "bytes": im.read(0x225D3A8, 12).hex()},
        "runtime_verified": False,
        "limits": [
            "Matching a 64-bit name hash establishes equality, not uniqueness or current installed asset contents.",
            "Two stages are observed: one interface returns a handle with the dummy hash, then 0xfdc140 associates the handle with a different entity-path hash.",
            "Callback-table addresses and component indices are runtime data not present in the old capture; no callback is assigned a name from these tables.",
            "The 0x800 record-search/wrap constants are not a supported-player count.",
            "No game process, installed archive, engine call, or multiplayer result was accessed.",
        ],
    }
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps({"matches": matches, "instruction_sites": sum(map(len, pins.values()))}))


if __name__ == "__main__":
    main()
