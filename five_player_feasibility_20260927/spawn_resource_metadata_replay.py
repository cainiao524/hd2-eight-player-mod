"""Offline entity metadata and captured loader/consumer evidence.

The bundled FileDiver plaintext is a reference snapshot. Its equality with the
installed encrypted file or current runtime metadata is deliberately unproven.
"""
import argparse
import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require, row

FILES = {
    "FileDiver/datalibrary/generated_entities.dl_bin": "21377252b81fdbc670eba1e59a8ab64b170323df208f175e708992e4c1fb515e",
    "FileDiver/datalibrary/generated_entities.dl_bin.gz": "5f1f54c39d51ddebdd8611b86701e038cdd9ae1821e03d67ca988962a03d19c7",
    "FileDiver/datalibrary/entity_component_settings.go": "d2aef3f6384724e51eb3e6b61a2312fb6d515947968161556fdfc113ddbf98f8",
    "FileDiver/datalibrary/entity_deltas.go": "32c14a7bcca62f49ed1ddbe4e640f4bd0594d53b72e42482d1ee96d8ae5d162f",
    "FileDiver/datalibrary/datalib_instance.go": "a9b3da4bc6ff40052034e8003cb4fe467057087d147f1340ab51112318bf42e8",
    "FileDiver/datalibrary/datalib.go": "63eff1802ac7ee8c4f43c40eb1b30371fe3cea9e1bdb08724e48708436fa097a",
    "FileDiver/hashes/dl_type_names.txt": "01eff67f430fa5df2d0677c07f72b229b61718face13cc2398f26f1f860ff750",
}
TARGETS = {
    0xB04D927AFB137B9B: "content/entities/dummy",
    0xCDC1F82CE3337A82: "content/entities/player",
    0x4D1C334D294DFA97: "content/fac_helldivers/cha_avatar/avatar_helldiver",
}
PINS = {
    "file_loader_to_metadata_pointer": [
        0xFDB454, 0xFDB456, 0xFDB464, 0xFDB46B, 0xFDB472,
        0xFDB479, 0xFDB480, 0xFDB485, 0xFDB489, 0xFDB499,
        0xFDB502, 0xFDB516, 0xFDB518, 0xFDB51D, 0xFDB51F,
        0xFDB524, 0xFDB526, 0xFDB52A, 0xFDB52D, 0xFDB537,
        0xFDB53A, 0xFDB53C, 0xFDB540, 0xFDB543, 0xFDB546,
        0xFDB54B, 0xFDB54E, 0xFDB553, 0xFDB557, 0xFDB55A,
        0xFDB561, 0xFDB56A, 0xFDB56E, 0xFDB571, 0xFDB573,
        0xFDB594, 0xFDB5A1, 0xFDB5B3, 0xFDB5C3,
        0xFDB649, 0xFDB659, 0xFDB660, 0xFDB664, 0xFDB66B,
        0xFDB6E1, 0xFDB6F0, 0xFDB6F7, 0xFDB6FD, 0xFDB704,
        0xFDB711, 0xFDB723, 0xFDB731,
    ],
    "lookup_record_and_u16_component_list": [
        0x581353, 0x58136E, 0x581377, 0x58137D, 0x581384,
        0x58138B, 0x5813A0, 0x5813A3, 0x5813A7, 0x5813AA,
        0x5813AD, 0x5813B0, 0x5813B2, 0x5813B5, 0x5813B7,
        0x5813BA, 0x5813BE, 0x5813CF, 0x5813D6, 0x5813D8,
        0x5813DC, 0x5813E1, 0x5813F4, 0x5813F9, 0x581403,
        0x58140A, 0x58140E, 0x581416, 0x58141B, 0x58141E,
        0x581421, 0x581505, 0x581509, 0x58152F,
        0x5817A0, 0x5817AA, 0x5817B0, 0x5817B3,
        0x58180D, 0x581816, 0x581A1E, 0x581A30,
        0x581A37, 0x581A3B, 0x581A48, 0x581A4B, 0x581A4E,
    ],
    "global_and_direct_loader_callers": [
        0xFDA1A4, 0xFDA352, 0xFDA356, 0xFDA360, 0xFDA375,
        0xAE0D84, 0xAE0D8B, 0xFDB866, 0xFDB86E,
        0xFDB873, 0xFDB878, 0xFDB880,
    ],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dlhash(name):
    result = 5381
    for char in name:
        result = (result * 33 + ord(char)) & 0xFFFFFFFF
    return (result - 5381) & 0xFFFFFFFF


def instance_records(data):
    at, has_index, items = 0, False, []
    while at < len(data):
        index = None
        if has_index:
            require(at + 4 <= len(data), "Truncated component index")
            index = struct.unpack_from("<I", data, at)[0]
            at += 4
        require(at + 28 <= len(data), "Truncated instance header")
        type0, magic, version, type_id, size, is64, reserved = struct.unpack_from("<7I", data, at)
        require(magic == 0x444C444C and version == 1, "Unexpected instance format")
        require(is64 == 1 and reserved == 0 and type0 == type_id, "Unexpected header flags")
        body = at + 28
        end = body + size
        require(end <= len(data), "Instance exceeds file")
        items.append({"index": index, "type": hex(type_id), "header_offset": hex(at),
                      "data_offset": hex(body), "size": size})
        at = end
        if at < len(data):
            require(at + 8 <= len(data), "Incomplete next instance")
            has_index = struct.unpack_from("<I", data, at + 4)[0] != 0x444C444C
    require(at == len(data), "Unparsed trailing bytes")
    return items


def metadata(data, names):
    records = instance_records(data)
    require(records[0]["type"] == hex(dlhash("EntitySettingsHashmap")), "Unexpected first type")
    body = int(records[0]["data_offset"], 16)
    end = body + records[0]["size"]
    require(body + 4096 * 32 <= end, "Truncated 4096-entry table")
    components = {}
    for item in records:
        if item["index"] is not None:
            require(item["index"] not in components, "Duplicate component data index")
            h = int(item["type"], 16)
            components[item["index"]] = {"data_type_hash": item["type"],
                                          "data_type_name": names.get(h)}
    rows, keys = [], set()
    for slot in range(4096):
        at = body + slot * 32
        resource, offset, count, game_object = struct.unpack_from("<QQQI", data, at)
        if not resource:
            continue
        require(resource not in keys, "Duplicate resource key")
        keys.add(resource)
        require(offset <= end - body and count * 2 <= end - body - offset, "Component list leaves instance")
        if resource in TARGETS:
            indices = list(struct.unpack_from("<" + "H" * count, data, body + offset))
            # Replay the code's low-12-bit hash and bounded linear probe.
            probe = resource & 0xFFF
            for depth in range(4096):
                key = struct.unpack_from("<Q", data, body + probe * 32)[0]
                require(key != 0, "Lookup encountered empty slot before match")
                if key == resource:
                    break
                probe = (probe + 1) & 0xFFF
            require(probe == slot, "Hash lookup does not reach recorded slot")
            rows.append({"resource_hash": hex(resource), "reference_name": TARGETS[resource],
                         "slot": slot, "record_file_offset": hex(at),
                         "record_bytes": data[at:at+32].hex(),
                         "component_list_file_offset": hex(body + offset),
                         "component_list_bytes": data[body+offset:body+offset+count*2].hex(),
                         "count": count, "indices": indices,
                         "includes_roster_callback_index_239": 239 in indices,
                         "hash_probe_steps": depth + 1, "game_object_value": hex(game_object),
                         "data_type_names": [{"index": index, **components.get(index, {
                             "data_type_hash": None, "data_type_name": None})} for index in indices]})
    require(len(rows) == len(TARGETS), "Missing target resource")
    return {"instance_count": len(records), "nonempty_resource_records": len(keys),
            "table_capacity": 4096, "record_stride": 32,
            "component_data_instance_count": len(components), "resources": rows,
            "component_239_data_type": components.get(239),
            "limits": ["Component indices select functions, not player slots.",
                       "No data-bearing instance for an index does not prove that component is absent.",
                       "Bundled plaintext is not verified equal to installed or runtime metadata."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing overwrite")
    sources = {}
    for filename, expected in FILES.items():
        data = (ROOT / filename).read_bytes()
        require(digest(data) == expected, "Changed reference source: " + filename)
        sources[filename] = data
    plain = sources["FileDiver/datalibrary/generated_entities.dl_bin"]
    require(gzip.decompress(sources["FileDiver/datalibrary/generated_entities.dl_bin.gz"]) == plain,
            "Plaintext differs from bundled gzip")
    names = {}
    for line in sources["FileDiver/hashes/dl_type_names.txt"].decode("utf-8-sig").splitlines():
        name = line.strip()
        if name and not name.startswith("//"):
            names[dlhash(name)] = name
    require(dlhash("EntitySettingsHashmap") == 0x80C1CA70, "DL hash disagreement")
    result = metadata(plain, names)
    image = Image(args.evidence)
    cache, groups = {}, {}
    for group, addresses in PINS.items():
        groups[group] = []
        for address in addresses:
            fragment = image.containing(address)
            require(fragment is not None, "Uncovered pin")
            if fragment not in cache:
                a, b, _ = fragment
                cache[fragment] = {i.address: i for i in image.md.disasm(image.read(a, b-a), a)}
            require(address in cache[fragment], "Pin not at instruction boundary")
            groups[group].append({**row(cache[fragment][address]), "root": hex(image.root(address)[0])})
    strings = []
    for rva, expected in [(0x225D2A0, b"generated_entities.dl_bin\0"),
                          (0x225D2F0, b"generated_entity_deltas.dl_bin\0")]:
        raw = image.read(rva, len(expected))
        require(raw == expected, "Loader string changed")
        strings.append({"rva": hex(rva), "bytes": raw.hex(), "sha256": digest(raw),
                        "text": raw[:-1].decode("ascii")})
    output = {"reference_files_sha256": FILES, "capture_source_sha256": EXPECTED,
              "reference_metadata": result, "captured_instructions": groups,
              "captured_strings": strings,
              "installed_asset_equivalence_verified": False,
              "runtime_component_selection_verified": False, "eight_player_verified": False}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"pins": sum(len(v) for v in groups.values()),
                      "instances": result["instance_count"],
                      "records": result["nonempty_resource_records"],
                      "resources": [{"name": r["reference_name"], "components": r["count"],
                                     "includes_239": r["includes_roster_callback_index_239"]}
                                    for r in result["resources"]]}))


if __name__ == "__main__":
    main()
