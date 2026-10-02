"""Emit and exercise the fixed-build platform-member eight-slot candidate.

The Steam build stores platform member IDs at ``owner+0x1b58`` with four
entries.  The fifth entry overlaps live control fields.  This candidate keeps
the original platform method calls and replaces only their destination/count
contract with an eight-slot sidecar.  The post-enumeration consumer is an
explicit callback because the captured ``0x1093590`` reader also assumes the
four-entry inline array.

This module only emits bytes and runs them in a synthetic Unicorn fixture.  It
does not discover symbols, write a process, install a hook, or claim online
multiplayer support.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ENTRY = 0x1092E60
END = 0x1092F63  # includes all three adjacent unwind fragments and ret
BODY_SHA256 = "337667006beecb7e40e381a76ffdcb10ebd4e539c4330e43494febd49d965abf"
GAME_IMAGE_SIZE = 0x39F0000
GLOBAL_API = 0x3326308
GLOBAL_FLAG = 0x3326E40

sha256 = lambda data: hashlib.sha256(data).hexdigest()


class EmitError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise EmitError(message)


def ptr(address: int, size: int = 1, alignment: int = 1, name: str = "pointer") -> None:
    require(type(address) is int and address >= 0, f"invalid {name}")
    require(address % alignment == 0, f"{name} alignment")
    require(address + size < 1 << 64, f"{name} overflow")


class Code:
    def __init__(self, base: int):
        self.base = base
        self.data = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, str]] = []

    def emit(self, blob: bytes) -> None:
        self.data.extend(blob)

    def label(self, name: str) -> None:
        require(name not in self.labels, f"duplicate label {name}")
        self.labels[name] = self.base + len(self.data)

    def jcc(self, opcode: bytes, target: str) -> None:
        self.emit(opcode)
        self.fixups.append((len(self.data), target))
        self.emit(b"\0" * 4)

    def jmp(self, target: str) -> None:
        self.emit(b"\xe9")
        self.fixups.append((len(self.data), target))
        self.emit(b"\0" * 4)

    def finish(self) -> bytes:
        out = bytearray(self.data)
        for offset, label in self.fixups:
            require(label in self.labels, f"missing label {label}")
            delta = self.labels[label] - (self.base + offset + 4)
            require(-(1 << 31) <= delta < (1 << 31), "rel32 out of range")
            out[offset:offset + 4] = struct.pack("<i", delta)
        return bytes(out)


def load_body(evidence: Path) -> tuple[bytes, dict]:
    doc = json.loads(evidence.read_text(encoding="utf-8"))
    rows = doc["instructions"]
    raw = b"".join(bytes.fromhex(r["bytes"]) for r in rows)
    cursor = ENTRY
    for row in rows:
        require(int(row["rva"], 16) == cursor, "instruction coverage changed")
        b = bytes.fromhex(row["bytes"])
        require(sha256(b) == row["sha256"], "instruction fingerprint changed")
        cursor += len(b)
    require(cursor == END and len(raw) == END - ENTRY, "body end changed")
    require(sha256(raw) == BODY_SHA256, "body fingerprint changed")
    return raw, doc


def _mov_rax_imm(c: Code, value: int) -> None:
    c.emit(b"\x48\xb8" + struct.pack("<Q", value))


def _mov_r11_stack(c: Code) -> None:
    c.emit(b"\x4c\x8b\x5c\x24\x28")  # r11=[rsp+28], sidecar


def build(*, game_base: int, code_address: int, resolver_address: int,
          consumer_address: int, sidecar_address: int) -> dict:
    """Build the replacement function and its explicit callback contract.

    Resolver ABI: ``Rcx=owner; Rax=sidecar`` (zero rejects).
    Consumer ABI: ``Rcx=owner; Rdx=sidecar; R8d=count; Eax=signed status``.
    Platform API ABIs are preserved from the captured function: the two
    interface methods receive their original object and destination arguments,
    but the destination is sidecar storage and capacity is eight.
    """
    for a, n, al, name in ((game_base, GAME_IMAGE_SIZE, 0x1000, "game_base"),
                           (code_address, 1, 16, "code_address"),
                           (resolver_address, 1, 1, "resolver_address"),
                           (consumer_address, 1, 1, "consumer_address"),
                           (sidecar_address, 0x50, 16, "sidecar_address")):
        ptr(a, n, al, name)
    require(not (code_address <= resolver_address < code_address + 0x1000),
            "callback overlaps emitted code")

    c = Code(code_address)
    # Entry and sidecar lease.  The extra 0x10 bytes remain inside the caller's
    # normal home area contract and keep the sidecar pointer stable across API
    # calls that may clobber all volatile registers.
    c.emit(b"\x53\x48\x83\xec\x30")       # push rbx; sub rsp,30h
    c.emit(b"\x48\x85\xc9")                 # test rcx,rcx
    c.jcc(b"\x0f\x84", "fail")
    c.emit(b"\x48\x8b\xd9")                 # rbx=owner
    _mov_rax_imm(c, resolver_address)
    c.emit(b"\xff\xd0")                     # resolver(owner)
    c.emit(b"\x48\x85\xc0")                 # resolver returned sidecar?
    c.jcc(b"\x0f\x84", "fail")
    c.emit(b"\x48\x89\x44\x24\x28")       # [rsp+28]=sidecar

    # The first platform path uses owner[0], API+F8/+138.
    c.emit(b"\x48\x8b\x0b\x48\x85\xc9")   # rcx=[owner]; test
    c.jcc(b"\x0f\x84", "platform_handle")
    _mov_rax_imm(c, game_base + GLOBAL_API)
    c.emit(b"\x48\x8b\x00")                 # rax=[global]
    c.emit(b"\x41\xb8\x08\x00\x00\x00")   # r8d=8
    c.emit(b"\x48\x8b\x90\xf8\x00\x00\x00") # rdx=[api+f8]
    c.emit(b"\x48\x8b\x82\x38\x01\x00\x00") # rax=[table+138]
    _mov_r11_stack(c); c.emit(b"\x41\xc6\x43\x48\x00") # mark bulk-fill path
    c.emit(b"\x49\x8d\x13") # rdx=sidecar ids
    c.emit(b"\xff\xd0")                         # call rax
    c.jmp("store_count")

    # The second path preserves the two captured platform API variants.
    c.label("platform_handle")
    c.emit(b"\x4c\x8b\x53\x08\x4d\x85\xd2") # r10=owner+8; test
    c.jcc(b"\x0f\x84", "fail")
    c.emit(b"\x4c\x89\x54\x24\x20")                 # [rsp+20]=platform handle
    _mov_rax_imm(c, game_base + GLOBAL_FLAG)
    c.emit(b"\x48\x8b\x00\x80\x78\x08\x00")   # rax=[flag]; cmp byte [flag+8],0
    _mov_rax_imm(c, game_base + GLOBAL_API)
    c.emit(b"\x0f\x84\x00\x00\x00\x00")         # placeholder -> alt path
    alt_fix = len(c.data) - 4
    # true path: count then per-index get, all into sidecar.
    c.emit(b"\x48\x8b\x00\x48\x8b\x50\x30")    # rax=[global]; rdx=[api+30]
    c.emit(b"\x48\x8b\x82\x80\x00\x00\x00")   # rax=[+80]
    _mov_r11_stack(c); c.emit(b"\x41\xc6\x43\x48\x01") # mark true path
    c.emit(b"\x48\x8b\x4c\x24\x20\xff\xd0")      # rcx=handle; call count
    c.jmp("store_count")

    # Alternative path target is patched after labels are known.  Reload API
    # root because the branch's flag read intentionally clobbers RAX.
    alt_label = "platform_alt"
    c.label(alt_label)
    _mov_rax_imm(c, game_base + GLOBAL_API)
    c.emit(b"\x48\x8b\x00")                         # rax=[global]
    c.emit(b"\x48\x8b\x88\x48\x01\x00\x00")   # rcx=[api+148]
    _mov_r11_stack(c); c.emit(b"\x49\x8d\x13")      # rdx=sidecar ids
    c.emit(b"\x41\xb8\x08\x00\x00\x00")         # r8d=8
    c.emit(b"\x48\x8b\x41\x10")                   # rax=[rcx+10]
    c.emit(b"\x4c\x8b\x48\x58")                   # r9=[rax+58]
    _mov_r11_stack(c); c.emit(b"\x41\xc6\x43\x48\x00") # mark alternate path
    c.emit(b"\x48\x8b\x4c\x24\x20\x41\xff\xd1") # rcx=handle; call r9
    c.jmp("store_count")

    # Count is in EAX.  Preserve a capped count in owner+1bb0 and sidecar+40.
    c.label("store_count")
    c.emit(b"\x83\xf8\x08")                         # cmp eax,8
    c.jcc(b"\x0f\x86", "count_ok")
    c.emit(b"\xb8\x08\x00\x00\x00")               # eax=8
    c.label("count_ok")
    c.emit(b"\x89\x83\xb0\x1b\x00\x00")           # owner count
    _mov_r11_stack(c); c.emit(b"\x41\x89\x43\x40") # sidecar count
    # For the true platform API, enumerate member IDs.  For the alternate
    # API the callee already filled sidecar storage; this loop is skipped.
    # EAX count is copied to EDI and a flag in sidecar+48 distinguishes path.
    c.emit(b"\x41\x80\x7b\x48\x00")               # cmp byte sidecar+48,0
    c.jcc(b"\x0f\x84", "post_consume")
    c.emit(b"\x33\xff")                             # edi=0
    c.label("get_loop_check")
    _mov_r11_stack(c)
    c.emit(b"\x41\x3b\x7b\x40")                    # cmp edi,sidecar count
    c.jcc(b"\x0f\x83", "post_consume")
    _mov_rax_imm(c, game_base + GLOBAL_API)
    c.emit(b"\x48\x8b\x00\x48\x8b\x50\x30\x48\x8b\x82\x88\x00\x00\x00")
    c.emit(b"\x48\x8b\x4c\x24\x20\x89\xfa\xff\xd0") # rcx=handle; edx=edi; call get
    _mov_r11_stack(c)
    c.emit(b"\x49\x89\x04\xfb")                     # [r11+rdi*8]=rax
    c.emit(b"\xff\xc7")                              # inc edi
    c.jmp("get_loop_check")

    c.label("post_consume")
    _mov_r11_stack(c)
    c.emit(b"\x48\x8b\xcb\x49\x8b\xd3\x44\x8b\x83\xb0\x1b\x00\x00")
    _mov_rax_imm(c, consumer_address)
    c.emit(b"\xff\xd0")                              # consumer(owner,sidecar,count)
    c.emit(b"\x85\xc0")                              # signed status
    c.jcc(b"\x0f\x88", "finish")
    c.emit(b"\x89\x83\x78\x1b\x00\x00")            # owner status
    c.jmp("finish")

    c.label("fail")
    c.emit(b"\xb8\xff\xff\xff\xff")                # fail closed status
    c.label("finish")
    c.emit(b"\x48\x83\xc4\x30\x5b\xc3")
    code = bytearray(c.finish())
    # The true/alternate condition uses `jz`; patch its placeholder now.
    delta = c.labels[alt_label] - (c.base + alt_fix + 4)
    require(-(1 << 31) <= delta < (1 << 31), "alternate branch out of range")
    code[alt_fix:alt_fix + 4] = struct.pack("<i", delta)
    code = bytes(code)
    ptr(code_address, len(code), 16, "complete code")
    return {
        "status": "native_platform_member_sidecar_candidate",
        "steam_build": 25480438,
        "entry_address": code_address,
        "size_bytes": len(code),
        "code_hex": code.hex(),
        "code_sha256": sha256(code),
        "source": {"entry": hex(ENTRY), "end_exclusive": hex(END),
                   "body_sha256": BODY_SHA256},
        "capacity": {"original": 4, "candidate": 8, "count_field": "owner+0x1bb0",
                     "sidecar_ids": "sidecar+0x00", "sidecar_count": "sidecar+0x40",
                     "alternate_path_marker": "sidecar+0x48"},
        "callbacks": {
            "resolve": {"address": hex(resolver_address), "abi": "RCX=owner; RAX=sidecar or 0"},
            "consume": {"address": hex(consumer_address),
                        "abi": "RCX=owner; RDX=sidecar; R8D=count; EAX=signed status"},
        },
        "platform_api": {
            "global_api": hex(game_base + GLOBAL_API),
            "global_flag": hex(game_base + GLOBAL_FLAG),
            "branch_true": "API+0x30 table +0x80 count, +0x88 member-at-index",
            "branch_false": "API+0x148 object +0x10 callback table +0x58 enumerator",
        },
        "installable": False,
        "game_execution": False,
        "multiplayer_verified": False,
        "limits": [
            "The resolver and consumer ABIs are new external contracts; no game callback has been identified for them.",
            "The original four-entry reader 0x1093590 is bypassed and must be replaced by a sidecar-aware production consumer.",
            "The platform service response, owner lifetime, hook/unwind, installation and client roster are not solved.",
            "The alternate path's callback must honor the expanded destination capacity; this candidate cannot force a service-side limit.",
        ],
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--game-base", type=lambda s: int(s, 0), required=True)
    p.add_argument("--code-address", type=lambda s: int(s, 0), required=True)
    p.add_argument("--resolver-address", type=lambda s: int(s, 0), required=True)
    p.add_argument("--consumer-address", type=lambda s: int(s, 0), required=True)
    p.add_argument("--sidecar-address", type=lambda s: int(s, 0), required=True)
    args = p.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    body, evidence = load_body(args.evidence)
    result = build(game_base=args.game_base, code_address=args.code_address,
                   resolver_address=args.resolver_address, consumer_address=args.consumer_address,
                   sidecar_address=args.sidecar_address)
    result["evidence_sha256"] = sha256(args.evidence.read_bytes())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "size_bytes": result["size_bytes"],
                      "code_sha256": result["code_sha256"]}))


if __name__ == "__main__":
    main()
