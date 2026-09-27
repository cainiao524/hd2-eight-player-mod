"""Build a bounded, provenance-checked HostSynchronizer embedding inventory.

This reads only previously captured disassembly JSON. It does not read, run, or
modify the game. Literal displacement hits are promoted only where the group
below establishes the base register's origin.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_FILES = [
    "host_relocation_ctor_root.json",
    "host_owner_init_disasm.json",
    "host_relocation_134e160.json",
    "host_relocation_fragment_134e1c8.json",
    "host_relocation_134e400.json",
    "host_relocation_13500f0.json",
    "host_relocation_1350680.json",
    "host_relocation_fragment_13506ad.json",
    "host_relocation_1083150.json",
    "host_relocation_fragment_1083851.json",
    "host_relocation_10845b0.json",
    "host_relocation_fragment_10845fc.json",
    "host_relocation_fragment_1084a83.json",
    "host_relocation_b99ff0.json",
    "host_relocation_baa560.json",
]

GROUPS = [
    {
        "name": "inline_host_constructor",
        "root": "0x134d740",
        "base_provenance": "rsi is the outer owner from the global at 0x134d754; r9=outer+0x159b0 at 0x134dc9e; rax=outer+0x159f0 (=host+0x40) at 0x134dcba. edi=0. The peer clear is four unrolled records in one loop iteration: ecx begins 0, adds 4, then cmp ecx,4.",
        "conclusion": "Host is embedded; [host+0] is an owner backpointer. Four peer records are initialized inline, bypassing any HostSynchronizer method or pointer indirection. The next sibling begins at outer+0x162c8 (=host+0x918).",
        "sites": ["0x134d754", "0x134dc9e", "0x134dca8", "0x134dcab", "0x134dcb6", "0x134dcba", "0x134dcd0", "0x134dcd4", "0x134dcd7", "0x134dcd9", "0x134dcdd", "0x134dce0", "0x134dce4", "0x134dce7", "0x134dcee", "0x134dcf4", "0x134dcfb", "0x134dcfe", "0x134dd07", "0x134dd28"],
    },
    {
        "name": "outer_cleanup_dispatch",
        "root": "0x134e160",
        "base_provenance": "rdi=entry rcx at 0x134e16d; same rdi forms adjacent sibling and host addresses.",
        "conclusion": "Cleanup calls the sibling handler first and the embedded HostSynchronizer handler second. Callee internals were not analyzed in this bounded inventory.",
        "sites": ["0x134e16d", "0x134e1c8", "0x134e1e2", "0x134e1e7", "0x134e1ee"],
    },
    {
        "name": "outer_update_dispatch",
        "root": "0x134e400",
        "base_provenance": "rbx=entry rcx at 0x134e40f. This owner provides host+0x159b0 to 0x108a440 and sibling+0x162c8 to 0x1083150 and 0x10845b0.",
        "conclusion": "Normal update invokes the four-pending consumer on the embedded host, then the sibling subsystem. Another later path calls the sibling transition handler.",
        "sites": ["0x134e40f", "0x134e42b", "0x134e432", "0x134e437", "0x134e43e", "0x134e545", "0x134e550"],
    },
    {
        "name": "outer_start_hosting",
        "root": "0x13500f0",
        "base_provenance": "rbx=entry rcx at 0x13500fd; direct state access at outer+0x159c8 is host+0x18; rcx=outer+0x159b0.",
        "conclusion": "Owner state check and both hosting branches use the embedded host address directly.",
        "sites": ["0x13500fd", "0x1350125", "0x135012c", "0x135013a", "0x1350146"],
    },
    {
        "name": "outer_peer_and_tail_access",
        "root": "0x1350680",
        "base_provenance": "entry rcx is the owner (reads owner+0xb3a8 and owner+0xb398); rbp=owner+0x159b0 at 0x13506ad.",
        "conclusion": "Owner writes peer state fields, reads live tail qwords host+0x908/+0x910, and iterates exactly four peer records at host+0x20 stride 0x38 on two paths.",
        "sites": ["0x1350686", "0x1350694", "0x13506ad", "0x13506cf", "0x13506d7", "0x13506dc", "0x13506e2", "0x13506e8", "0x13506ee", "0x135071c", "0x135072d", "0x1350731", "0x135074a", "0x1350764", "0x13507ca", "0x13507ce", "0x13507d2", "0x13507e6", "0x13507eb", "0x1350835", "0x1350839", "0x135083d", "0x1350849"],
    },
    {
        "name": "sibling_direct_host_state",
        "root": "0x1083150",
        "base_provenance": "0x134e437 passes outer+0x162c8 as entry rcx; constructor sets [sibling+0]=outer at 0x134dd28. Here rdi=entry rcx and rbx=[rdi] at 0x108384e, 0x1084291, 0x10842d1.",
        "conclusion": "Sibling update directly reads and writes host state at outer+0x159c8, including qword stores, without receiving a HostSynchronizer pointer.",
        "sites": ["0x1083176", "0x1083179", "0x108384e", "0x1083851", "0x108386c", "0x1084291", "0x1084294", "0x10842b0", "0x10842b2", "0x10842d1", "0x10842d4", "0x10842f0"],
    },
    {
        "name": "sibling_transition_direct_host_state",
        "root": "0x10845b0",
        "base_provenance": "0x134e545 passes outer+0x162c8 as entry rcx; rdi=entry rcx at 0x10845d3; rbx=[rdi] at 0x10845f6, consistent with constructor-set owner backpointer at sibling+0. This proves the 0x134e545 call path; other callers are not classified here.",
        "conclusion": "Transition handler directly accesses owner+0x159c8 (=host+0x18), reads [owner+0x159b0] (=host+0 owner backpointer), and calls start_hosting with owner+0x159b0.",
        "sites": ["0x10845d3", "0x10845f6", "0x10845fc", "0x1084618", "0x1084a67", "0x1084a83", "0x1084a8a", "0x1084aa9", "0x1084ac2", "0x1084ac9"],
    },
    {
        "name": "peer_removal_fallback_a",
        "root": "0xb99ff0",
        "base_provenance": "rcx is outer owner loaded from an owner list at 0xb9a036; sibling is rcx+0x162c8 at 0xb9a06d; fallback r10=rcx+0x159b0 at 0xb9a0aa.",
        "conclusion": "Fallback scans exactly four embedded host peers, stride 0x38, and calls remove-peer with r10 as host pointer.",
        "sites": ["0xb9a036", "0xb9a06d", "0xb9a0aa", "0xb9a0b3", "0xb9a0be", "0xb9a0c2", "0xb9a0cf", "0xb9a0de", "0xb9a0e5"],
    },
    {
        "name": "peer_removal_fallback_b",
        "root": "0xbaa560",
        "base_provenance": "rcx is outer owner loaded from an owner list at 0xbaa5a6; sibling is rcx+0x162c8 at 0xbaa5dd; fallback r10=rcx+0x159b0 at 0xbaa61a.",
        "conclusion": "Second homologous path scans four embedded host peers, stride 0x38, and calls remove-peer with r10 as host pointer.",
        "sites": ["0xbaa5a6", "0xbaa5dd", "0xbaa61a", "0xbaa623", "0xbaa62e", "0xbaa632", "0xbaa63f", "0xbaa64e", "0xbaa655"],
    },
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, help="Pinned capture directory for byte, instruction-boundary, and unwind-root checks")
    args = parser.parse_args()
    sources = {}
    site_index = {}
    for name in SOURCE_FILES:
        path = HERE / name
        obj = json.loads(path.read_text(encoding="utf-8"))
        sources[name] = {"range": obj["range"], "fragment_sha256": obj["sha256"]}
        for ins in obj["instructions"]:
            site_index.setdefault(ins["rva"], (name, ins))

    out_groups = []
    for group in GROUPS:
        selected = []
        for rva in group["sites"]:
            if rva not in site_index:
                raise KeyError(f"missing captured instruction {rva} for {group['name']}")
            name, ins = site_index[rva]
            selected.append({
                "rva": rva,
                "bytes": ins["bytes"],
                "instruction_sha256": hashlib.sha256(bytes.fromhex(ins["bytes"])).hexdigest(),
                "asm": ins["asm"],
                "fragment_file": name,
                "fragment_sha256": sources[name]["fragment_sha256"],
            })
        out_groups.append({k: v for k, v in group.items() if k != "sites"} | {"sites": selected})

    verification = "not_run"
    if args.capture_dir:
        sys.path.insert(0, str(HERE.parent / "research_handoff_20260927" / "indirect"))
        from inspect_capture import Image

        image = Image(args.capture_dir)
        verified = 0
        for group in out_groups:
            for site in group["sites"]:
                rva = int(site["rva"], 16)
                raw = bytes.fromhex(site["bytes"])
                if image.read(rva, len(raw)) != raw:
                    raise ValueError(f"capture byte mismatch at {site['rva']}")
                ins = image.instruction(rva)
                if ins is None or ins.bytes != raw:
                    raise ValueError(f"capture instruction boundary mismatch at {site['rva']}")
                if hex(image.root(rva)[0]) != group["root"]:
                    raise ValueError(f"capture unwind root mismatch at {site['rva']}")
                verified += 1
        verification = f"{verified} sites: exact capture bytes, instruction boundaries, and unwind roots verified"

    obj = {
        "title": "Bounded exact-build HostSynchronizer embedded owner references",
        "capture_identity_sha256": "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8",
        "capture_report_sha256": "132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5",
        "captured_data_sha256": "31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d",
        "disk_game_dll_sha256": "2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e",
        "reproduction": "python host_relocation_inventory.py --capture-dir <pinned-capture-directory>; all RVA bytes come from captured code fragments and are validated against the pinned capture",
        "capture_verification": verification,
        "scope": "Only listed roots and listed instructions. Root bounds follow captured fragments, not independently established complete function boundaries. This is a proven subset, not all readers or writers.",
        "structural_constraints": {
            "host_owner_offset": "0x159b0",
            "host_state_owner_offset": "0x159c8",
            "next_sibling_owner_offset": "0x162c8",
            "host_sibling_delta": "0x918",
            "host_peer_region": "host+0x20, four records x 0x38",
            "host_large_region": "host+0x108, four records x 0x1c0; ends at host+0x808",
            "host_pending_region": "host+0x808, four records x 0x40; ends at host+0x908",
            "live_tail": "host+0x908 and host+0x910, two qwords",
        },
        "verified_groups": out_groups,
        "unverified_candidates": [
            "The literal-offset hits in host_embedded_region_refs.json outside these roots have not all had base-register provenance checked; shared displacements alone do not prove HostSynchronizer access.",
            "Callee 0xb3fcd0 (cleanup), constructor helper 0xb2afb0, and sibling constructor helper 0xb2abd0 may contain further references; this inventory records call sites but does not characterize those callees.",
            "Other callers of 0x10845b0 may pass a different object type. The owner/sibling provenance is verified for the 0x134e545 call path.",
            "Computed indexing, register aliases, callback calls, and dynamic API table targets can reference the same state without a literal outer displacement. They are outside this bounded scan.",
            "No runtime memory allocation, live join, or cross-client protocol behavior is inferred from the static capture.",
        ],
        "architecture_implication": "The four-slot host is embedded and multiple owner/sibling paths use absolute owner-relative offsets or inline loops. Replacing [host+0] with a sidecar pointer would corrupt the owner backpointer. Any expanded storage architecture must account for these direct sites and for the occupied host tail; the inventory does not establish a complete hook set or a working 8-player implementation.",
        "source_fragments": sources,
    }
    target = HERE / "host_relocation_inventory.json"
    target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{target} : {len(out_groups)} groups, {sum(len(g['sites']) for g in out_groups)} sites")

if __name__ == "__main__":
    main()
