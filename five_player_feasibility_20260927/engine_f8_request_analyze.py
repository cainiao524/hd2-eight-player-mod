"""Offline, bounded analysis of the saved EXE 0x8e1370 code window.

This reads saved JSON and the pinned disk PE only. It never opens a process.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import capstone
import pefile
from capstone.x86_const import X86_OP_IMM, X86_OP_MEM


HERE = Path(__file__).resolve().parent
CAPTURE = HERE / "engine_callee_live_20260927_1.json"
CALLER_CAPTURE = HERE / "interface_probe_live_20260927_1.json"
DISK_EXE = Path(r"F:\Game\Steam\steamapps\common\Helldivers 2\bin\helldivers2.exe")
OUTPUT = HERE / "engine_f8_request_evidence.json"
EXPECTED_CAPTURE_SHA256 = "157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a"
EXPECTED_WINDOW_SHA256 = "0e6e20315ee6e64b80c48b78197feb4b968e68e2995c659496d3c3fe049a5fb2"
EXPECTED_CALLER_SHA256 = "a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f"
EXPECTED_DISK_SHA256 = "f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def code_window(capture: dict, rva: str) -> tuple[int, bytes, dict]:
    entry = next(item for item in capture["ranges"] if item["rva"].lower() == rva)
    body = bytes.fromhex(entry["bytes"])
    assert len(body) == entry["size"] == 4096
    assert sha256(body) == entry["sha256"] == entry["reread_sha256"]
    assert entry["unchanged_on_reread"]
    return int(entry["rva"], 16), body, entry


def reachable(base: int, body: bytes, entry: int) -> tuple[list[dict], list[dict], list[dict]]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    end = base + len(body)
    todo = [entry]
    found: dict[int, dict] = {}
    edges: list[dict] = []
    unresolved: list[dict] = []
    while todo:
        address = todo.pop()
        while base <= address < end and address not in found:
            instructions = list(md.disasm(body[address - base : address - base + 15], address, count=1))
            if not instructions:
                unresolved.append({"from": hex(address), "reason": "decode failure"})
                break
            ins = instructions[0]
            next_address = address + ins.size
            found[address] = {
                "rva": hex(address),
                "bytes": ins.bytes.hex(),
                "asm": f"{ins.mnemonic} {ins.op_str}".strip(),
            }
            if ins.group(capstone.CS_GRP_RET):
                edges.append({"from": hex(address), "kind": "return"})
                break
            if ins.group(capstone.CS_GRP_CALL):
                operand = ins.operands[0]
                target = hex(operand.imm) if operand.type == X86_OP_IMM else None
                slot = None
                if operand.type == X86_OP_MEM and operand.mem.base == capstone.x86_const.X86_REG_RIP:
                    slot = hex(next_address + operand.mem.disp)
                edges.append({"from": hex(address), "kind": "call", "target": target, "rip_slot": slot})
                address = next_address
                continue
            if ins.group(capstone.CS_GRP_JUMP):
                operand = ins.operands[0]
                if operand.type != X86_OP_IMM:
                    unresolved.append({"from": hex(address), "reason": "indirect jump"})
                    break
                target = operand.imm
                edges.append({"from": hex(address), "kind": "jump" if ins.mnemonic == "jmp" else "conditional", "target": hex(target)})
                if base <= target < end:
                    todo.append(target)
                else:
                    unresolved.append({"from": hex(address), "target": hex(target), "reason": "outside saved window"})
                if ins.mnemonic != "jmp":
                    todo.append(next_address)
                break
            address = next_address
        else:
            if not (base <= address < end):
                unresolved.append({"from": hex(address), "reason": "fallthrough outside saved window"})
    return [found[a] for a in sorted(found)], edges, unresolved


def main() -> None:
    capture_raw = CAPTURE.read_bytes()
    caller_raw = CALLER_CAPTURE.read_bytes()
    assert sha256(capture_raw) == EXPECTED_CAPTURE_SHA256
    assert sha256(caller_raw) == EXPECTED_CALLER_SHA256
    capture = json.loads(capture_raw)
    caller = json.loads(caller_raw)
    base, body, _ = code_window(capture, "0x8e1370")
    assert base == 0x8E1370 and sha256(body) == EXPECTED_WINDOW_SHA256
    instructions, edges, unresolved = reachable(base, body, base)
    follow_instructions, follow_edges, follow_unresolved = reachable(base, body, 0x8E1970)
    by_address = {int(i["rva"], 16): i for i in instructions}
    assert len(instructions) == 170 and not unresolved
    assert len(follow_instructions) == 109 and not follow_unresolved
    assert [i["rva"] for i in instructions if i["asm"].startswith("ret")] == ["0x8e1682"]
    r13_usages = [i for i in instructions if "r13" in i["asm"]]
    assert [i["rva"] for i in r13_usages] == [
        "0x8e1382", "0x8e138f", "0x8e1551", "0x8e1559", "0x8e167d"
    ]

    caller_entry = next(
        f for table in caller["tables"] for f in table["functions"] if f["module_rva"] == "0x8c6730"
    )
    assert sha256(bytes.fromhex(caller_entry["bytes"])) == caller_entry["sha256"]
    constructor_base, constructor_body, _ = code_window(capture, "0x8ccfa0")
    constructor_instructions, _, constructor_unresolved = reachable(constructor_base, constructor_body, constructor_base)
    assert not constructor_unresolved
    constructor_by_address = {int(i["rva"], 16): i for i in constructor_instructions}
    follow_by_address = {int(i["rva"], 16): i for i in follow_instructions}

    disk_raw = DISK_EXE.read_bytes()
    disk_sha = sha256(disk_raw)
    assert disk_sha == EXPECTED_DISK_SHA256
    pe = pefile.PE(data=disk_raw, fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
    slot_rva = 0x8E15D1 + 0xB157E7
    imports = [
        {
            "dll": item.dll.decode(errors="replace"),
            "name": imp.name.decode(errors="replace") if imp.name else None,
            "thunk_rva": hex(imp.address - pe.OPTIONAL_HEADER.ImageBase),
        }
        for item in pe.DIRECTORY_ENTRY_IMPORT
        for imp in item.imports
    ]
    slot_section = next(
        section for section in pe.sections
        if section.VirtualAddress <= slot_rva < section.VirtualAddress + section.Misc_VirtualSize
    )
    section_start = slot_section.VirtualAddress
    section_raw_end = section_start + slot_section.SizeOfRawData
    section_virtual_end = section_start + slot_section.Misc_VirtualSize
    disk_slot_bytes = pe.get_data(slot_rva, 8)
    assert len(disk_slot_bytes) == 8

    selected_addresses = [
        0x8E138F, 0x8E1392, 0x8E13AA, 0x8E1526, 0x8E152F, 0x8E1537, 0x8E153E, 0x8E1546,
        0x8E1551, 0x8E1559, 0x8E1561, 0x8E156C, 0x8E1577, 0x8E1582,
        0x8E158D, 0x8E1592, 0x8E1599, 0x8E159E, 0x8E15A3, 0x8E15AB,
        0x8E15B0, 0x8E15B5, 0x8E15BD, 0x8E15C0, 0x8E15C3, 0x8E15C6,
        0x8E15CB, 0x8E15D1, 0x8E15D3, 0x8E15D5, 0x8E162A,
        0x8E1637, 0x8E1652, 0x8E1657, 0x8E1682,
    ]
    constructor_addresses = [0x8CCFBF, 0x8CCFF0, 0x8CD064, 0x8CD07E, 0x8CD214, 0x8CD27D, 0x8CD28D]
    follow_addresses = [
        0x8E1982, 0x8E1985, 0x8E198F, 0x8E1997, 0x8E199C, 0x8E19A3, 0x8E19A6,
        0x8E19A9, 0x8E19AC, 0x8E19B4, 0x8E19B6, 0x8E19FA, 0x8E1A01,
        0x8E1A04, 0x8E1A0B, 0x8E1A0E, 0x8E1A5A, 0x8E1A61, 0x8E1A64,
        0x8E1A6B, 0x8E1AAE, 0x8E1AB5, 0x8E1ABC, 0x8E1AC3,
        0x8E1AC6, 0x8E1ACB, 0x8E1ACE, 0x8E1AD3, 0x8E1AD8,
    ]
    assert all(a in by_address for a in selected_addresses)
    assert all(a in constructor_by_address for a in constructor_addresses)
    assert all(a in follow_by_address for a in follow_addresses)

    evidence = {
        "method": "offline disassembly and CFG traversal of saved process-code windows; disk PE import metadata",
        "runtime_invocation": False,
        "capture_file_sha256": sha256(capture_raw),
        "window_rva": hex(base),
        "window_sha256": sha256(body),
        "window_size": len(body),
        "caller_capture_sha256": sha256(caller_raw),
        "disk_exe_sha256": disk_sha,
        "cfg": {
            "reachable_instruction_count": len(instructions),
            "first_and_only_reachable_ret": "0x8e1682",
            "all_reachable_direct_branches_in_window": not unresolved,
            "unresolved_branches": unresolved,
            "edges": edges,
            "scope": "Normal static control flow in the saved 4096-byte window; called functions and exceptions not traversed.",
        },
        "code_evidence": [by_address[a] for a in selected_addresses],
        "constructor_code_evidence": [constructor_by_address[a] for a in constructor_addresses],
        "follow_on_function": {
            "entry_rva": "0x8e1970",
            "reachable_instruction_count": len(follow_instructions),
            "unresolved_branches": follow_unresolved,
            "code_evidence": [follow_by_address[a] for a in follow_addresses],
            "edges": [edge for edge in follow_edges if edge["kind"] == "call"],
        },
        "argument_flow": {
            "entry_edx": "0x8e138f: EDX -> R13D",
            "config_first_two_u32": ["0x8e1551: R13D -> [RSP+0x80]", "0x8e1559: R13D -> [RSP+0x84]"],
            "remaining_config_u32": ["[RSP+0x88]=1", "[RSP+0x8C]=1", "[RSP+0x90]=1", "[RSP+0x94]=0xF"],
            "invitation_layout": [
                "[RSP+0x98]=R12=object+0xA0 (identifier)",
                "[RSP+0xA0]=1 (revocability)",
                "[RSP+0xA4..0xAF]=0 (entityIdCount and entityIds)",
            ],
            "indirect_call": {"call_rva": "0x8e15cb", "rip_slot_rva": hex(slot_rva), "config_pointer_register": "R8=&[RSP+0x80]"},
            "r13_usages": r13_usages,
            "count_clamp_or_comparison_in_reachable_caller": False,
        },
        "disk_import_metadata": {
            "slot_rva": hex(slot_rva),
            "slot_has_named_disk_import": any(int(item["thunk_rva"], 16) == slot_rva for item in imports),
            "slot_in_virtual_only_part_of_section": slot_rva >= section_raw_end,
            "disk_slot_bytes": disk_slot_bytes.hex(),
            "slot_section": {
                "name": slot_section.Name.decode(errors="replace").rstrip("\0"),
                "virtual_start": hex(section_start),
                "virtual_end": hex(section_virtual_end),
                "raw_rva_end": hex(section_raw_end),
            },
            "partywin_imports": [item for item in imports if item["dll"].lower() == "partywin.dll"],
        },
        "official_signature_match": {
            "classification": "high-confidence inference, not a direct import-symbol identification",
            "configuration_type": "PartyNetworkConfiguration",
            "candidate_method": "PartyManager::CreateNewNetwork",
            "configuration_fields_in_order": [
                "maxUserCount", "maxDeviceCount", "maxUsersPerDeviceCount",
                "maxDevicesPerUserCount", "maxEndpointsPerDeviceCount", "directPeerConnectivityOptions",
            ],
            "observed_values": ["EDX", "EDX", 1, 1, 1, "0xF"],
            "call_abi_arguments": [
                "RCX=[return of 0x8e25b0] (candidate PartyManager this)",
                "RDX=[object+0x88] (candidate localUser)",
                "R8=&[RSP+0x80] (candidate networkConfiguration)",
                "R9=0 (regionCount)",
                "[RSP+0x20]=0 (regions)",
                "[RSP+0x28]=&[RSP+0x98] (initialInvitationConfiguration)",
                "[RSP+0x30]=object (asyncIdentifier)",
                "[RSP+0x38]=object+0x289 (networkDescriptor)",
                "[RSP+0x40]=0 (appliedInitialInvitationIdentifier)",
            ],
            "docs": [
                "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partynetworkconfiguration",
                "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/structs/partyinvitationconfiguration",
                "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/enums/partyinvitationrevocability",
                "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_createnewnetwork",
            ],
        },
        "follow_on_official_signature_matches": [
            {
                "call_rva": "0x8e19ac",
                "candidate": "PartyManager::ConnectToNetwork",
                "arguments": ["RCX=manager", "RDX=object+0x289 descriptor", "R8=object asyncIdentifier", "R9=&object+0x80 network output"],
                "doc": "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partymanager/methods/partymanager_connecttonetwork",
            },
            {
                "call_rva": "0x8e1a0e",
                "candidate": "PartyNetwork::AuthenticateLocalUser",
                "arguments": ["RCX=[object+0x80] network", "RDX=[object+0x88] localUser", "R8=object+0xA0 identifier", "R9=0 asyncIdentifier"],
                "doc": "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_authenticatelocaluser",
            },
            {
                "call_rva": "0x8e1ad8",
                "candidate": "PartyNetwork::CreateEndpoint",
                "arguments": ["RCX=[object+0x80] network", "RDX=[object+0x88] localUser", "R8=0 propertyCount", "R9=0 keys", "[RSP+0x20]=0 values", "[RSP+0x28]=object asyncIdentifier", "[RSP+0x30]=&object+0x90 localEndpoint output"],
                "doc": "https://learn.microsoft.com/en-us/xbox/playfab/multiplayer/networking/reference/classes/partynetwork/methods/partynetwork_createendpoint",
            },
        ],
        "limits": [
            "The indirect function pointer value at RVA 0x13f6db8 was not captured. The raw disk bytes at this RVA are not a named import thunk and cannot by themselves identify the loaded pointer.",
            "A zero immediate return from the indirect call would only indicate queuing of asynchronous network creation under the SDK signature.",
            "Neither server acceptance nor five-player same-mission gameplay was invoked or observed.",
        ],
    }
    OUTPUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {OUTPUT.name}; reachable={len(instructions)}; indirect slot={hex(slot_rva)}")


if __name__ == "__main__":
    main()
