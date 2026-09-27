"""Verify and decode the saved third observation without any process access."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from exe_capture_cfg import decode

CAPTURE_SHA = "44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a"
PREFIX_SHA = "484f5437b325ff273041e496b4f609d393ed24a4af38b63cce5c6f63d706b04a"
CALLER_SHA = "6c78736c1f150bd2f9e600a811d71464658f0dd8093768f8f4cfb60a073d8536"
IMAGE_HASHES = {
    "helldivers2.exe": "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06",
    "game.dll": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
}
READ_COMPONENTS = {
    "pe_header_pages": 16384,
    "previous_game_code_pins": 224,
    "spawn_caller_pin": 102,
    "four_pointer_fields": 64,
    "target_code_prefix": 8192,
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replay(path):
    raw = path.read_bytes()
    require(sha(raw) == CAPTURE_SHA, "Saved capture fingerprint mismatch")
    capture = json.loads(raw)
    require(capture["build"] == 25480438 and capture["runtime_capture"], "Source identity mismatch")
    require(capture["read_components"] == READ_COMPONENTS, "Read components changed")
    require(capture["memory_bytes_read"] == sum(READ_COMPONENTS.values()) == 24966, "Read count mismatch")
    require(capture["observed_fields_unchanged_on_reread"] and not capture["atomic_snapshot"], "Observation flags changed")
    pin = capture["caller_pin"]
    require((pin["game_rva"], pin["size"], pin["sha256"], pin["call_rva"])
            == ("0xac9be9", 51, CALLER_SHA, "0xac9c19"), "Caller identity mismatch")
    images = capture["pinned_images"]
    require(set(images) == set(IMAGE_HASHES), "Image set changed")
    for name, expected in IMAGE_HASHES.items():
        require(images[name]["sha256"] == expected, "Saved image hash mismatch")

    fields = capture["field_samples"]
    require(len(fields) == 4, "Expected four pointer observations")
    labels = ["api_root", "api_plus_c0_object", "object_vtable", "vtable_plus_18_target"]
    addresses, values = [], []
    for field, label in zip(fields, labels):
        data = bytes.fromhex(field["bytes"])
        value = int(field["value"], 16)
        require(field["label"] == label and len(data) == 8, "Pointer shape changed")
        require(int.from_bytes(data, "little") == value, "Pointer bytes mismatch")
        require(0x10000 <= value < 0x800000000000, "Invalid saved pointer")
        addresses.append(int(field["address"], 16))
        values.append(value)
    require(addresses == [images["game.dll"]["base"] + 0x3326308,
                          values[0] + 0xC0, values[1], values[2] + 0x18], "Pointer chain mismatch")

    function = capture["function"]
    data = bytes.fromhex(function["bytes"])
    require(len(data) == function["size"] == 4096, "Prefix size changed")
    require(sha(data) == function["sha256"] == function["reread_sha256"] == PREFIX_SHA,
            "Saved prefix hash mismatch")
    require(function["unchanged_on_reread"], "Prefix changed during capture")
    exe = images["helldivers2.exe"]
    require(function["module"] == exe["path"], "Target module changed")
    require(function["module_rva"] == "0x30ff50", "Target RVA changed")
    require(int(function["address"], 16) == values[3] == exe["base"] + 0x30FF50,
            "Target address mismatch")
    require(0x30FF50 + 4096 <= exe["size"], "Prefix leaves image")

    cfg = decode({"rva": function["module_rva"], "bytes": function["bytes"]})
    cfg["limits"][0] = ("Entry is established by the saved four-pointer chain and pinned indirect caller; "
                        "no invocation is observed.")
    cfg["limits"].append("An empty unresolved list concerns jumps only; the call target 0x1ae380 is outside this prefix.")
    require(cfg["instruction_count"] == 9 and cfg["decoded_bytes"] == 34, "Unexpected entry flow")
    require(cfg["unresolved"] == [], "Unexpected unresolved normal branches")
    require(cfg["edges"] == [{"from": "0x30ff66", "kind": "call", "target": "0x1ae380"},
                             {"from": "0x30ff71", "kind": "return"}], "Unexpected entry edges")
    return {
        "capture_file_sha256": CAPTURE_SHA,
        "capture_utc": capture["utc"],
        "memory_bytes_read": capture["memory_bytes_read"],
        "saved_pointer_chain_verified": True,
        "entry": cfg,
        "callee": {"module": "helldivers2.exe", "rva": "0x1ae380", "in_this_capture": False},
        "argument_flow": {
            "helper_rcx": "entry RCX unchanged; caller supplies its world/context value",
            "helper_rdx": "address of stack storage at entry RSP+8; semantic output role inferred",
            "helper_r8": "address of copied entry RDX resource hash at entry RSP+0x10",
            "helper_r9": "entry R8 unchanged",
            "wrapper_return_eax": "DWORD at the RAX pointer returned by helper",
        },
        "capacity_conclusion": "No four/eight-player capacity comparison occurs in these nine instructions; helper remains unknown.",
        "runtime_invocation_verified": False,
        "eight_player_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Refusing overwrite")
    result = replay(args.capture)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps({"entry": result["entry"]["entry_rva"],
                      "instructions": result["entry"]["instruction_count"],
                      "callee": result["callee"], "memory_bytes_read": result["memory_bytes_read"]}))


if __name__ == "__main__":
    main()
