"""Pin confirmed-peer follow-up and one four-candidate gameplay update path.

Only reads the existing fingerprinted Steam-build capture. Does not load the
game, modify installed files, or resolve uncaptured runtime interface targets.
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
    "client_append_then_peer_id_callback": [
        0x10872D5, 0x1087333, 0x1087342, 0x108734C, 0x1087354,
        0x108736A, 0x1087378, 0x108751C, 0x108751F,
        0xB90B46, 0xB90BE3, 0xB90C03, 0xB90C12, 0xB90E6B, 0xB90E6E,
    ],
    "peer_id_snapshot_dispatch": [
        0xB5EAA5, 0xB5EAF6, 0xB5EAFD, 0xB5EB1D, 0xB5EB4D,
        0xB5EB7A, 0xB5EB83, 0xB5ED30, 0xB5ED35, 0xB5ED3F,
        0x66FC20, 0x6702DA, 0x670405, 0xBEC984, 0xBECB84, 0xBECB89,
        0x1382C75, 0x1382CC4, 0x1382DA6,
    ],
    "game_state_dispatch": [
        0xAB609B, 0xAB60A2, 0xAB60A4, 0xAB60A9,
        0xAB60B0, 0xAB60BA, 0xAB60EF, 0xAB60F9,
    ],
    "four_candidate_construction": [
        0xACBE8A, 0xACC122, 0xACC28A, 0xACC297,
        0xACC30C, 0xACC33C, 0xACC343, 0xACC394, 0xACC3C4,
        0xACC3D1, 0xACC3D8, 0xACC424, 0xACC450, 0xACC454,
        0xACC461, 0xACC468, 0xACC4B4, 0xACC522, 0xACC53A,
        0xACC541, 0xACC5CA, 0xACC605, 0xACC617,
    ],
    "four_candidate_consumer": [
        0xACC620, 0xACC622, 0xACC638, 0xACC645,
        0xACC773, 0xACC886, 0xACC89E, 0xACC8A5,
        0xACC8C0, 0xACC8CC, 0xACCA12, 0xACCA1D,
        0xACCA21, 0xACCA25, 0xACCA2D, 0xACCA31,
    ],
    "respawn_followup_not_entity_allocation": [
        0xAC7C29, 0xAC7C45, 0xAC7C56, 0xAC7D50,
        0xAC7D67, 0xAC7E0E, 0xAC7ECB, 0xAC81F2,
        0xAC82E8, 0xAC8303, 0xAC8333, 0xAC8343,
        0xBE19E8, 0xBE19F9,
    ],
    "player_state_label_strings": [0xACC7F1, 0xACC850, 0xACC87A],
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    im = Image(args.evidence)
    pins = {}
    for group, addresses in PINS.items():
        pins[group] = []
        for address in addresses:
            ins = im.instruction(address)
            require(ins is not None, f"not a validated instruction boundary: {address:#x}")
            pins[group].append({**row(ins), "root": hex(im.root(address)[0])})
    table = [x[0] for x in struct.iter_unpack("<I", im.read(0xAB7664, 24))]
    require(table == [0xAB60BC, 0xAB60CD, 0xAB60DE, 0xAB60EF,
                      0xAB6100, 0xAB610E], "game state switch changed")
    result = {
        "source_sha256": EXPECTED,
        "capture_sha256": im.report["capture_sha256"],
        "game_sha256": im.report["game_sha256"],
        "build_id": im.report["build_id"],
        "runtime_verified": im.report["runtime_verified"],
        "pins": pins,
        "game_state_switch": {
            "table_rva": "0xab7664",
            "bytes": im.read(0xAB7664, 24).hex(),
            "targets": [hex(t) for t in table],
            "state_4_target": "0xab60ef",
            "state_4_call": "0xab60f9",
        },
        "limits": [
            "The confirmed-peer follow-up passes the peer ID, not the stored +0x14 index, to 0xB5EA90.",
            "The four-candidate state-4 path uses roster ordinals 0..3; their equality to the network-assigned player index is unproven.",
            "This is one gameplay update path and does not establish that every player or every spawn must use it.",
            "Neither this path nor its 0xAC7BE0 follow-up proves a four-slot player-entity allocator.",
            "The game was not executed and the uncaptured runtime interfaces were not resolved.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
