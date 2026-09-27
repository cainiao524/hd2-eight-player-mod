"""Build a bounded host lifecycle dependency map from pinned static disassembly."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

GROUPS = [
    {
        "name": "embedded_constructor",
        "provenance": "outer=rsi; host=outer+0x159b0 in root 0x134d740.",
        "sites": [
            ("0x134dc9e", "address", "embedded host base"),
            ("0x134dca8", "write", "host+0 owner backpointer"),
            ("0x134dcb6", "write", "host+0x18 state"),
            ("0x134dcba", "address", "peer inline clear anchor host+0x40"),
            ("0x134dcd0", "write", "peer 0 at host+0x20; unrolled four records follow"),
            ("0x134dcf4", "address", "advance unrolled peer block by 0xe0"),
            ("0x134dcfb", "bound", "one unrolled iteration of four peer records"),
            ("0x134dd07", "address", "next sibling outer+0x162c8 = host+0x918"),
        ],
    },
    {
        "name": "start_hosting_reset",
        "provenance": "root 0x1088a30 receives host in RCX and saves it to RDI at 0x1088a62.",
        "sites": [
            ("0x1088a62", "base", "host=RDI"),
            ("0x1088a7a", "write", "host+0x18 state=1"),
            ("0x1088a87", "address", "anchor for inline four peer records"),
            ("0x1088a93", "value", "zero fill byte passed as EDX to 0x208aaa0 later"),
            ("0x1088aa3", "write", "first peer zeroed; three more unrolled"),
            ("0x1088af5", "address", "advance four-peer clear block by 0xe0"),
            ("0x1088afc", "bound", "one unrolled iteration of four peer records"),
            ("0x1088b8c", "write", "host+0x100..0x103 flags zeroed as dword"),
            ("0x1088b95", "write", "one host+0x100 indexed flag set"),
            ("0x1088bc5", "size", "0x700-byte large-record reset length"),
            ("0x1088be6", "address", "host+0x108 large-record start"),
            ("0x1088bef", "call", "zero-fill host+0x108 for 0x700 bytes via 0x208aaa0"),
        ],
    },
    {
        "name": "stop_hosting_state_only",
        "provenance": "root 0x1088f00 receives host in RCX and saves it to RBX.",
        "sites": [
            ("0x1088f06", "read", "host+0x18 state"),
            ("0x1088f24", "write", "host+0x18 qword cleared when nonzero"),
        ],
        "limit": "This root itself does not reset arrays; it can be called within wider workflows.",
    },
    {
        "name": "host_migration_reset",
        "provenance": "root 0x1089720 receives host in RCX, saved as R13 at 0x108973d.",
        "sites": [
            ("0x108973d", "base", "host=R13"),
            ("0x10897b1", "write", "host+0x18 state=1"),
            ("0x10897a3", "address", "peer clear anchor host+0x58"),
            ("0x10897c3", "value", "zero fill byte held in EDX for later 0x208aaa0 call"),
            ("0x10897d1", "write", "peer 0 zero-fill; remaining three unrolled"),
            ("0x108982c", "address", "advance peer clear block by 0xe0"),
            ("0x1089833", "bound", "one unrolled iteration of four peers"),
            ("0x1089838", "address", "host+0x108 large-record start"),
            ("0x108983f", "size", "0x700-byte large-record reset length"),
            ("0x1089845", "call", "zero-fill four large records via 0x208aaa0"),
            ("0x108984c", "write", "host+0x100..0x103 flags zeroed"),
            ("0x108985e", "write", "host+0x20 self peer"),
            ("0x108987b", "write", "host+0x40 self peer state"),
        ],
    },
    {
        "name": "host_migration_peer_rebuild",
        "provenance": "R13 remains host; peer reads and writes use R13+0x20 with stride 0x38. A separate outer-owner registry at +0x16390/+0x16398 can supply an index for host flags.",
        "sites": [
            ("0x1089d2e", "address", "host+0x20 peer scan"),
            ("0x1089d39", "address", "peer stride 0x38"),
            ("0x1089d3d", "bound", "four peer scan limit"),
            ("0x1089d53", "value", "RDX=0 asks leaf to find an empty peer slot"),
            ("0x1089d58", "call", "direct leaf 0x108b520 searches a peer slot"),
            ("0x1089d60", "write", "returned peer slot first qword; no local null guard"),
            ("0x1089d9d", "read", "owner registry count at +0x16390, separate from host"),
            ("0x1089e93", "address", "owner registry stride 0x20"),
            ("0x1089eab", "write", "host+0x100 indexed flag set from registry-derived index"),
            ("0x1089f7c", "call", "remove-peer helper 0x108d190 during migration"),
            ("0x1089fb7", "address", "host peer stride 0x38 in later scan"),
            ("0x1089fbb", "bound", "four peer scan limit"),
            ("0x1089fd7", "address", "host+0x100 flags scan"),
            ("0x1089fea", "bound", "four flag scan limit"),
            ("0x1089ff4", "write", "host+0x100 indexed flag set"),
            ("0x108a02d", "bound", "four peer transition iteration"),
            ("0x108a0a2", "address", "peer stride 0x38"),
        ],
    },
    {
        "name": "peer_slot_lookup_leaf",
        "provenance": "0x108b520 is a direct-call target from migration; no unwind entry. It receives host in RCX and target qword in RDX; two RETs and INT3 padding bound candidate leaf.",
        "sites": [
            ("0x108b523", "address", "host+0x20 peer base"),
            ("0x108b530", "read", "peer first qword"),
            ("0x108b537", "address", "peer stride 0x38"),
            ("0x108b53b", "bound", "four peers"),
            ("0x108b540", "return", "zero return when no matching slot"),
            ("0x108b545", "address", "index*0x38 slot address"),
        ],
        "limit": "This leaf searches for a peer qword equal to the caller's RDX; its broader call set is not inventoried.",
    },
    {
        "name": "remove_peer_dispatch",
        "provenance": "root 0x108d190 receives host in RCX and saves it to RSI at 0x108d1a7; peer id from RDX to R14.",
        "sites": [
            ("0x108d1a7", "base", "host=RSI"),
            ("0x108d272", "call", "0x108b6b0 removes ID from four large records and peer/flag"),
            ("0x108d2d4", "bound", "four peer event iteration"),
            ("0x108d2d9", "address", "host+0x20 peer base"),
            ("0x108d349", "address", "peer stride 0x38"),
            ("0x108d351", "bound", "end of four peer event iteration"),
            ("0x108d370", "address", "second four peer loop anchor"),
            ("0x108d38c", "address", "second loop stride 0x38"),
            ("0x108d394", "bound", "second four peer loop end"),
        ],
    },
    {
        "name": "remove_from_four_large_records_and_peer",
        "provenance": "root 0x108b6b0 receives host in RCX; RBP=host at 0x108b6d7, RDI=peer id at 0x108b6d4.",
        "sites": [
            ("0x108b6c7", "address", "large record 0 host+0x108"),
            ("0x108b6e9", "write", "large record 0 list count at record+8"),
            ("0x108b704", "read", "large record 0 secondary list count at record+0x38"),
            ("0x108b724", "write", "large record 0 secondary count"),
            ("0x108b768", "size", "0x1c0-byte record zero-fill buffer"),
            ("0x108b76e", "call", "zero-fill temporary record buffer"),
            ("0x108b7f1", "address", "large record 1 host+0x2c8"),
            ("0x108b911", "address", "large record 2 host+0x488"),
            ("0x108ba31", "address", "large record 3 host+0x648"),
            ("0x108bb53", "address", "host+0x20 peer scan"),
            ("0x108bb62", "bound", "four peers"),
            ("0x108bb79", "write", "matched peer first qword cleared"),
            ("0x108bb80", "write", "matched peer +0x20 state cleared"),
            ("0x108bb87", "write", "matched peer +0x18 field cleared"),
            ("0x108bb93", "write", "host+0x100 indexed flag cleared unless prior index=-1"),
        ],
    },
    {
        "name": "lookup_four_large_records",
        "provenance": "root 0x108b560 receives host in RCX, peer ID in RDX; R11=host and large-record list cursor starts at host+0x110.",
        "sites": [
            ("0x108b577", "address", "first large record sublist count host+0x110"),
            ("0x108b5a9", "read", "large-record sublist peer qword"),
            ("0x108b5b6", "address", "host+0x108 large-record base"),
            ("0x108b5bd", "address", "index*0x1c0"),
            ("0x108b5d5", "address", "large-record stride 0x1c0"),
            ("0x108b5e0", "bound", "four large records"),
        ],
    },
    {
        "name": "pending_consumer",
        "provenance": "root 0x108a440 has R12=host; earlier pending_consumer_findings.json proves calls from owner+0x159b0.",
        "sites": [
            ("0x108af53", "address", "host+0x808 pending base"),
            ("0x108af5b", "bound", "four pending records"),
            ("0x108af70", "read", "pending record first qword"),
            ("0x108b245", "address", "host+0x108 large-record base"),
            ("0x108b250", "read", "large-record first qword"),
            ("0x108b258", "address", "large-record stride 0x1c0"),
            ("0x108b25f", "bound", "four large records"),
            ("0x108b270", "write", "copy pending first qword into large record"),
            ("0x108b494", "write", "pending record zero-fill begins, four 16-byte stores"),
            ("0x108b4c8", "address", "pending stride 0x40"),
            ("0x108b4cc", "bound", "pending iteration decrement"),
        ],
    },
    {
        "name": "live_tail_and_adjacent_sibling",
        "provenance": "root 0x1350680 receives outer owner in RCX and forms host=outer+0x159b0 as RBP; root 0x134d740 constructs sibling at outer+0x162c8.",
        "sites": [
            ("0x13506ad", "address", "embedded host=owner+0x159b0"),
            ("0x135071c", "address", "host+0x908 tail qword address"),
            ("0x135074a", "read", "host+0x910 tail qword"),
            ("0x1350764", "read", "host+0x908 tail qword"),
            ("0x134dd07", "address", "next sibling=host+0x918"),
        ],
    },
]


def main():
    index = {}
    fragments = {}
    for path in HERE.glob("host_expansion_disasm_*.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        for frag in obj["fragments"]:
            fragments[(path.name, frag["range"][0])] = frag["sha256"]
            for site in frag["instructions"]:
                index.setdefault(site["rva"], (path.name, frag["range"], frag["sha256"], site))
    for path in [HERE / "host_owner_init_disasm.json", HERE / "host_relocation_ctor_root.json",
                 HERE / "host_relocation_fragment_13506ad.json", HERE / "pending_candidate_108af53.json"]:
        obj = json.loads(path.read_text(encoding="utf-8"))
        for site in obj["instructions"]:
            index.setdefault(site["rva"], (path.name, obj["range"], obj["sha256"], site))

    groups = []
    for item in GROUPS:
        sites = []
        for rva, kind, field in item["sites"]:
            if rva not in index:
                raise KeyError(f"Missing selected site {rva}")
            file, bounds, frag_hash, ins = index[rva]
            if hashlib.sha256(bytes.fromhex(ins["bytes"])).hexdigest() != ins["sha256"]:
                raise ValueError(f"Instruction hash mismatch {rva}")
            sites.append({
                "rva": rva, "bytes": ins["bytes"], "instruction_sha256": ins["sha256"],
                "asm": ins["asm"], "kind": kind, "field_or_effect": field,
                "fragment_file": file, "fragment_range": bounds, "fragment_sha256": frag_hash,
            })
        groups.append({k: v for k, v in item.items() if k != "sites"} | {"sites": sites})
    out = {
        "capture_identity_sha256": "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8",
        "scope": "Bounded exact-build static map of verified host lifecycle read/write sites; not a complete write set or hook list.",
        "groups": groups,
        "layout": {
            "outer_host": "outer+0x159b0",
            "owner_backpointer": "host+0x0",
            "peer": "host+0x20, 4 x 0x38; state/index fields within each record",
            "flags": "host+0x100..+0x103",
            "large": "host+0x108, 4 x 0x1c0; end-exclusive host+0x808",
            "pending": "host+0x808, 4 x 0x40; end-exclusive host+0x908",
            "tail": "host+0x908 and +0x910 live qwords",
            "next_sibling": "host+0x918",
        },
        "dependencies": [
            {"from": "constructor", "to": ["peer", "owner_backpointer", "sibling"], "why": "inline embedded initialization and sibling placement"},
            {"from": "start_hosting", "to": ["peer", "flags", "large"], "why": "four-record clear and fixed 0x700 zero-fill"},
            {"from": "migration", "to": ["peer", "flags", "large", "owner registry", "remove_peer"], "why": "reset, four-slot rebuild, registry-derived flag index and remove call"},
            {"from": "pending_consumer", "to": ["pending", "large"], "why": "four pending entries feed four large records"},
            {"from": "remove_peer", "to": ["peer", "flags", "large"], "why": "four explicit large record removals, then four-peer clear"},
            {"from": "outer/sibling transitions", "to": ["host+0x18 state", "tail", "sibling"], "why": "direct outer-relative state writes and live tail read"},
        ],
        "architecture_assessment": {
            "inline_eight_pending": "Contradicted by live tail at host+0x908/+0x910 and sibling at host+0x918; eight 0x40 pending entries from +0x808 end at +0xa08.",
            "replace_host_plus_zero_with_pointer": "Contradicted by constructor and sibling paths: [host+0] is the outer owner backpointer.",
            "move_whole_host_alone": "Would break direct owner+0x159b0/+0x159c8 and adjacent sibling+0x162c8 sites; moving the sibling would propagate offset changes to other owner fields. The full write set is not known.",
            "sidecar_candidate": "Keeping the first four inline records and external extra storage would preserve current embedded addresses but requires new routing for every four-bound peer/flag/large/pending consumer plus owner registries and other subsystems. No complete hook set or working mod is established.",
        },
        "limits": [
            "Selected pins are a proven subset; computed addresses and callbacks can evade literal scans.",
            "0x108b520 has direct-target plus RET/INT3 boundary evidence, not an unwind entry.",
            "The 0x208aaa0 routine behaves as a byte-fill function in captured code, and callers pass zero and exact sizes; this map does not assume a C library symbol name.",
            "No process was read and no game binary or report was modified in this pass.",
        ],
    }
    target = HERE / "host_expansion_inventory.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target.name, len(groups), "groups", sum(len(g["sites"]) for g in groups), "pins")


if __name__ == "__main__":
    main()
