"""Fixed-build Party handle/object relationship; never invoke or dereference a handle.

The game-side singleton wrapper and the Party C API handle are different values.
This observer follows only PartyWin's pinned manager global, then compares its
stored handle with the game's holder. A match is data evidence, not proof that
the protected game call slots invoke PartyWin or that admission above four works.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pefile

PARTY_SHA256 = "de34667c2f7084013d9c03cd5d1cb5dc3321bc36bb616a845e35534e4e7995e0"
HOLDER_RVA = 0x27CED10
HELPER_RVA = 0x8E25B0
HELPER_SIZE = 0x5B
HELPER_SHA256 = "6bbb8b0531d8caf268b2f2fd083edd0316bf2f30ca14048bd22b3d24a6edab9d"
MANAGER_GLOBAL_RVA = 0x3B6460
STORED_HANDLE_OFFSET = 0x600
CODE_PINS = (
    (0x15720, 0x3C0, "7f58b941e3b4315fd5a9f42c24597c1f9cf0ea6e677f8088a75b12efdf33e164"),
    (0x26860, 0x1F0, "7762fe35724e7cd67b85070003ecbd1c17449261f8fc015b54a4ccfad9fc9c21"),
    (0x26DB0, 0xBC, "0e0d1d83f285dd70b91e77a8ea74bfe02582b8b3d43cf5632d962a25aadaf58c"),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_backed_bytes(pe, raw: bytes, rva: int, size: int) -> bytes:
    """Refuse virtual-only tails instead of converting them to unrelated offsets."""
    if rva < 0 or size <= 0:
        raise ValueError("invalid PE range")
    sections = [s for s in pe.sections
                if s.VirtualAddress <= rva and
                rva + size <= s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData)]
    if len(sections) != 1:
        raise ValueError("PE range must fit one section")
    section = sections[0]
    delta = rva - section.VirtualAddress
    if delta + size > section.SizeOfRawData:
        raise ValueError("RVA has no file-backed bytes")
    offset = section.PointerToRawData + delta
    if offset < 0 or offset + size > len(raw):
        raise ValueError("truncated PE file")
    return raw[offset:offset + size]


def verify_party_file(path: Path) -> dict:
    raw = path.read_bytes()
    if sha(raw) != PARTY_SHA256:
        raise ValueError("unsupported PartyWin fingerprint")
    pe = pefile.PE(data=raw, fast_load=True)
    try:
        for rva, size, expected in CODE_PINS:
            if sha(file_backed_bytes(pe, raw, rva, size)) != expected:
                raise ValueError(f"Party code fingerprint mismatch: {rva:#x}")
        call = file_backed_bytes(pe, raw, 0x158F8, 5)
        load = file_backed_bytes(pe, raw, 0x26921, 7)
        getter = file_backed_bytes(pe, raw, 0x26E50, 7)
        if (call[0] != 0xE8 or 0x158FD + struct.unpack_from("<i", call, 1)[0] != 0x26860 or
                load[:3] != bytes.fromhex("4c8b35") or
                0x26928 + struct.unpack_from("<i", load, 3)[0] != MANAGER_GLOBAL_RVA or
                getter[:3] != bytes.fromhex("488b81") or
                struct.unpack_from("<i", getter, 3)[0] != STORED_HANDLE_OFFSET):
            raise ValueError("manager layout does not match the pinned instruction operands")
        return {"sha256": PARTY_SHA256, "image_size": pe.OPTIONAL_HEADER.SizeOfImage,
                "timestamp": pe.FILE_HEADER.TimeDateStamp,
                "create_resolver_call_rva": "0x158f8", "resolver_rva": "0x26860",
                "manager_global_load_rva": "0x26921",
                "manager_global_rva": hex(MANAGER_GLOBAL_RVA),
                "stored_handle_offset": hex(STORED_HANDLE_OFFSET),
                "equality_compare_rva": "0x26968",
                "code_sha256": {hex(rva): digest for rva, _, digest in CODE_PINS},
                "static_layout_only": True, "runtime_binding_proven": False}
    finally:
        pe.close()


def verify_live_layout(reader, exe_base: int, party_base: int) -> dict:
    """Called only after the caller verifies both loaded module identities."""
    helper = reader.read(exe_base + HELPER_RVA, HELPER_SIZE, executable=True)
    if sha(helper) != HELPER_SHA256:
        raise ValueError("game singleton helper fingerprint mismatch")
    for rva, size, expected in CODE_PINS:
        if sha(reader.read(party_base + rva, size, executable=True)) != expected:
            raise ValueError(f"loaded Party code fingerprint mismatch: {rva:#x}")
    return {"helper_sha256": HELPER_SHA256,
            "party_code_sha256": {hex(rva): digest for rva, _, digest in CODE_PINS}}


def observe(reader, exe_base: int, party_base: int) -> dict:
    """At most 48 data bytes, no function calls, no handle-pointer conversion.

    Caller must first verify_live_layout. Unchanged reads do not establish an
    atomic snapshot or owner lifetime; the result must never enable a provider.
    """
    def qword(address):
        if not 0x10000 <= address <= 0x800000000000 - 8:
            raise ValueError("invalid data address")
        raw = reader.read(address, 8)
        if len(raw) != 8:
            raise ValueError("short manager data read")
        return struct.unpack("<Q", raw)[0]

    holder_address = exe_base + HOLDER_RVA
    global_address = party_base + MANAGER_GLOBAL_RVA
    handle = qword(holder_address)
    manager = qword(global_address)
    stored = stored_again = None
    valid_manager_address = 0x10000 <= manager <= 0x800000000000 - STORED_HANDLE_OFFSET - 8
    if valid_manager_address:
        stored = qword(manager + STORED_HANDLE_OFFSET)
        stored_again = qword(manager + STORED_HANDLE_OFFSET)
    handle_again = qword(holder_address)
    manager_again = qword(global_address)
    stable = handle == handle_again and manager == manager_again and stored == stored_again
    # The pinned resolver checks this tagged-handle path. Other branches are
    # intentionally not assigned a manager identity from a mere nonzero value.
    tagged = bool(handle) and (handle & 1) == 0 and ((handle >> 1) & 0xF) == 1
    equal = stored is not None and bool(handle) and handle == stored
    if not stable:
        status = "changed_during_read"
    elif not handle:
        status = "null_game_handle"
    elif not manager:
        status = "null_party_manager"
    elif not valid_manager_address:
        status = "invalid_party_manager_address"
    elif not tagged:
        status = "outside_tagged_manager_path"
    elif not equal:
        status = "manager_handle_mismatch"
    else:
        status = "manager_handle_relationship_observed"
    return {
        "status": status, "game_holder_address": hex(holder_address),
        "game_handle": hex(handle), "party_manager_global_address": hex(global_address),
        "party_manager_object": hex(manager),
        "stored_handle_offset": hex(STORED_HANDLE_OFFSET),
        "stored_handle": hex(stored) if stored is not None else None,
        "tagged_manager_path": tagged, "handle_equality_observed": equal,
        "unchanged_on_reread": stable, "atomic_snapshot": False,
        "manager_data_relationship_observed": status == "manager_handle_relationship_observed",
        "target_binding_proven": False, "owner_lifetime_proven": False,
        "runtime_provider_ready": False, "multiplayer_verified": False,
        "handle_dereferenced": False,
    }
