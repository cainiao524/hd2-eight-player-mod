"""Static verifier for the template-only 0x10936e0 reader detour."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import capstone  # type: ignore

from platform_member_consumer_patch import SENTINELS, sha256
from platform_member_leaf_reader_patch import (
    ENTRY_END, ENTRY_RVA, PATCH_SPAN, RESULT_OFFSET, STUB_ADDRESS,
    UNWIND_ADDRESS, load_exact_site,
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
    require(len(patch) == PATCH_SPAN and patch[:6] == b"\xff\x25\0\0\0\0", "detour encoding mismatch")
    require(struct.unpack_from("<Q", patch, 6)[0] == STUB_ADDRESS, "stub target mismatch")
    stub = bytes.fromhex(artifact["stub"]["code_hex"])
    require(len(stub) == artifact["stub"]["size_bytes"], "stub size mismatch")
    require(sha256(stub) == artifact["stub"]["code_sha256"], "stub hash mismatch")
    require(stub.startswith(b"\x53\x48\x83\xec\x20"), "unsafe prologue")
    require(stub.endswith(b"\x48\x83\xc4\x20\x5b\xc3"), "unsafe epilogue")
    require(struct.pack("<Q", SENTINELS["resolver"]) in stub, "resolver sentinel missing")
    require(struct.pack("<Q", SENTINELS["mode"]) in stub, "mode sentinel missing")
    text = [(i.mnemonic, i.op_str) for i in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64).disasm(stub, STUB_ADDRESS)]
    require(("mov", "eax, dword ptr [rbx + 0x44]") in text, "sidecar result read missing")
    require(("js", "") in text or any(m == "js" for m, _ in text), "negative fallback missing")
    require(artifact["unwind"]["unwind_info_hex"] == "0105020005320103", "unwind bytes mismatch")
    require(artifact["unwind"]["unwind_info_address_template"] == hex(UNWIND_ADDRESS), "unwind address mismatch")
    require(artifact["continuation"]["mode"] == "full_replacement", "unsafe continuation")
    require(artifact["continuation"]["forward_target"] is None, "unsafe forward target")
    require(artifact["verification"]["installable"] is False, "candidate must remain non-installable")
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

