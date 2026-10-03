"""Static verifier for the template-only consumer patch candidate."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import capstone  # type: ignore

from platform_member_consumer_patch import (
    ENTRY_END,
    ENTRY_RVA,
    PATCH_SPAN,
    SENTINELS,
    STUB_ADDRESS,
    UNWIND_ADDRESS,
    build,
    load_exact_site,
    sha256,
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def verify(evidence: Path, artifact_path: Path) -> dict:
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    original, body_hash = load_exact_site(evidence)
    entry = artifact["entry"]
    require(entry["rva"] == hex(ENTRY_RVA), "entry RVA mismatch")
    require(entry["original_end_exclusive"] == hex(ENTRY_END), "entry end mismatch")
    require(entry["captured_body_sha256"] == body_hash, "body fingerprint mismatch")
    require(entry["entry_patch_span"] == PATCH_SPAN, "patch span mismatch")
    expected = original[:PATCH_SPAN]
    require(entry["expected_entry_bytes"] == expected.hex(), "expected bytes mismatch")
    require(entry["rollback_bytes"] == expected.hex(), "rollback bytes mismatch")
    patch = bytes.fromhex(entry["patch_bytes_template"])
    require(len(patch) == PATCH_SPAN, "patch length mismatch")
    require(patch[:6] == b"\xff\x25\0\0\0\0", "detour encoding mismatch")
    require(struct.unpack_from("<Q", patch, 6)[0] == STUB_ADDRESS, "stub target mismatch")

    stub_doc = artifact["stub"]
    stub = bytes.fromhex(stub_doc["code_hex"])
    require(len(stub) == stub_doc["size_bytes"], "stub size mismatch")
    require(sha256(stub) == stub_doc["code_sha256"], "stub hash mismatch")
    require(stub_doc["address_template"] == hex(STUB_ADDRESS), "stub address mismatch")
    require(stub.startswith(b"\x53\x55\x56\x57\x41\x54\x41\x55\x41\x56\x41\x57\x48\x83\xec\x28"), "unsafe prologue")
    require(stub.endswith(b"\x48\x83\xc4\x28\x41\x5f\x41\x5e\x41\x5d\x41\x5c\x5f\x5e\x5d\x5b\xc3"), "unsafe epilogue")
    for value in SENTINELS.values():
        require(struct.pack("<Q", value) in stub, f"missing callback sentinel {value:#x}")
    disasm = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(stub, STUB_ADDRESS))
    require(disasm, "stub does not disassemble")
    require(sum(ins.size for ins in disasm) == len(stub), "stub has undecoded bytes")
    text = [(ins.mnemonic, ins.op_str) for ins in disasm]
    require(("cmp", "r14d, r13d") in text, "loop bound is not r14d/r13d")
    require(("and", "r15d, eax") in text, "mode predicate register is not preserved")
    require(("cmp", "ebp, r13d") in text, "successful-member count check is not exact")

    unwind = artifact["unwind"]
    info = bytes.fromhex(unwind["unwind_info_hex"])
    require(len(info) == 24, "unexpected unwind info size")
    # Derive instruction ends instead of repeating the generator's constant.
    prologue = disasm[:9]
    require([i.mnemonic for i in prologue] == ["push"] * 8 + ["sub"], "prologue shape")
    ends = [i.address + i.size - STUB_ADDRESS for i in prologue]
    require(info[:4] == bytes([1, ends[-1], 9, 0]), "unwind header mismatch")
    require(list(info[4:22:2]) == list(reversed(ends)), "unwind instruction offsets mismatch")
    require(unwind["prologue_size"] == ends[-1], "prologue size mismatch")
    require(unwind["unwind_info_address_template"] == hex(UNWIND_ADDRESS), "unwind address mismatch")
    runtime = unwind["runtime_function"]
    require(runtime == {"begin": hex(STUB_ADDRESS), "end": hex(STUB_ADDRESS + len(stub)), "unwind": hex(UNWIND_ADDRESS)}, "runtime function mismatch")
    require(artifact["continuation"]["mode"] == "full_replacement", "continuation must bypass four-slot body")
    require(artifact["continuation"]["forward_target"] is None, "unsafe forward continuation")
    require(artifact["rollback"]["restore_bytes"] == expected.hex(), "rollback mismatch")
    require(artifact["verification"]["installable"] is False, "candidate must remain non-installable")
    require(artifact["verification"]["multiplayer_verified"] is False, "candidate cannot claim multiplayer")
    return {"status": "passed_static_template_verification", "stub_bytes": len(stub), "patch_span": PATCH_SPAN}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence, args.artifact), ensure_ascii=False))


if __name__ == "__main__":
    main()
