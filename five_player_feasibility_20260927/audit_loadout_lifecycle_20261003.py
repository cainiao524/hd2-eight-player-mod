"""Recover the fixed-build MenuScreenLoadout constructor/release lifecycle.

Only the pinned offline capture is read.  The audit binds the outer screen
constructor, per-widget constructor, both release paths, the transition
callbacks, and the runtime slot guards.  It deliberately produces a contract
and no detour or patch bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT.parent / "evidence" / "existing-code-evidence-25480438"
sys.path.insert(0, str(ROOT.parent / "research_handoff_20260927" / "indirect"))
from inspect_capture import Image, EXPECTED, row  # type: ignore  # noqa: E402

BUILD = 25480438
CAPTURE_SHA = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"

# Each entry is (RVA, exact disassembly).  The instruction boundary is checked
# against the captured unwind table before the text is compared.
PINS: dict[str, list[tuple[int, str]]] = {
    "screen_entry_rebuild_1465820": [
        (0x1465829, "call 0x1467330"),
        (0x1465836, "jmp 0x1466170"),
    ],
    "screen_constructor_1466170": [
        (0x14A17F4, "mov edi, 4"),
        (0x14A17F9, "lea rdx, [rcx + 0x10]"),
        (0x14A1908, "sub r8, 1"),
        (0x14A190C, "jne 0x14a1810"),
        (0x14A1943, "lea rsi, [rbx + 0x53a78]"),
        (0x14A1953, "call 0x14aa5c0"),
        (0x14A1958, "add rsi, 0x1ee18"),
        (0x14A195F, "sub rdi, 1"),
        (0x14A1963, "jne 0x14a1950"),
    ],
    "widget_constructor_14aa5c0": [
        (0x14AA5D2, "add rcx, 0x220"),
        (0x14AA5D9, "call 0x149acc0"),
        (0x14AA624, "call 0x14aa860"),
        (0x14AA629, "mov edi, 0xe"),
        (0x14AA6D7, "mov ecx, 4"),
        (0x14AA73F, "mov ecx, 6"),
        (0x14AA816, "mov rax, rbx"),
        (0x14AA82E, "ret"),
    ],
    "screen_release_1467330": [
        (0x1467400, "lea rcx, [r14 + 0xcf2d8]"),
        (0x1467407, "call 0x144dd70"),
        (0x14674B4, "lea rbx, [r14 + 0x57fc0]"),
        (0x14674BB, "mov edi, 4"),
        (0x14675C8, "add rbx, 0x1ee18"),
        (0x14675CF, "sub rdi, 1"),
        (0x14675D3, "jne 0x14674c0"),
        (0x1467716, "jmp 0x144dd70"),
    ],
    "alternate_widget_release_1467720": [
        (0x1467743, "add rbx, 0x55a20"),
        (0x146774A, "mov edi, 4"),
        (0x1467750, "cmp qword ptr [rbx + 0xf0], 0"),
        (0x146775D, "call 0x18a0fd0"),
        (0x1467762, "add rbx, 0x1ee18"),
        (0x1467769, "sub rdi, 1"),
        (0x146776D, "jne 0x1467750"),
    ],
    "widget_transition_1470a40": [
        (0x1470B48, "lea rbx, [rsi + 0x53a78]"),
        (0x1470B4F, "mov edi, 4"),
        (0x1470B69, "call 0x189e080"),
        (0x1470B99, "call 0x1451100"),
        (0x1470B9E, "add rbx, 0x1ee18"),
        (0x1470BA5, "sub rdi, 1"),
        (0x1470BA9, "jne 0x1470b60"),
    ],
    "runtime_slot_guards": [
        (0x189D050, "cmp edx, 4"),
        (0x189D053, "jae 0x189d115"),
        (0x146E1B3, "cmp r10d, 4"),
        (0x146E1B7, "jae 0x146e1a1"),
        (0x146E3E5, "cmp r9d, 4"),
        (0x146E3E9, "jb 0x146e3c0"),
        (0x146E4EA, "cmp r9d, 4"),
        (0x146E4EE, "jb 0x146e4c1"),
        (0x146E5D9, "cmp r9d, 4"),
        (0x146E5DD, "jb 0x146e5b0"),
        (0x146E660, "cmp esi, 4"),
        (0x146E663, "jb 0x146e620"),
        (0x146E867, "cmp eax, 4"),
        (0x146E86A, "jae 0x146e1a1"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, default=CAPTURE)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    image = Image(args.evidence)
    checks: list[dict] = []
    pins: dict[str, list[dict]] = {}

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("fixed_build_capture", image.report.get("capture_sha256") == CAPTURE_SHA,
          image.report.get("capture_sha256"))
    check("captured_sources_match", image.files and all(
        hashlib.sha256(image.files[k]).hexdigest() == v for k, v in EXPECTED.items()), EXPECTED)

    for name, entries in PINS.items():
        rows: list[dict] = []
        group_ok = True
        for rva, expected_asm in entries:
            ins = image.instruction(rva)
            observed = None if ins is None else row(ins)
            ok = observed is not None and observed["asm"].strip() == expected_asm.strip()
            if observed is not None:
                observed["root"] = hex(image.root(rva)[0])
                observed["fragment"] = [hex(x) for x in image.containing(rva)]
            rows.append({"expected_rva": hex(rva), "expected_asm": expected_asm, "observed": observed, "passed": ok})
            group_ok = group_ok and ok
        pins[name] = rows
        check(f"pins_{name}", group_ok, {"count": len(rows), "failed": [r["expected_rva"] for r in rows if not r["passed"]]})

    # The pointers used by the paired loops are not interchangeable: the
    # constructor/transition start at +53A78, while release walks +57FC0 or
    # +55A20.  This check makes that ownership distinction explicit.
    check("constructor_widget_stride", any(r["passed"] for r in pins["screen_constructor_1466170"] if r["expected_rva"] == "0x14a1958"),
          pins["screen_constructor_1466170"])
    check("release_widget_stride", any(r["passed"] for r in pins["screen_release_1467330"] if r["expected_rva"] == "0x14675c8"),
          pins["screen_release_1467330"])
    check("alternate_release_widget_stride", any(r["passed"] for r in pins["alternate_widget_release_1467720"] if r["expected_rva"] == "0x1467762"),
          pins["alternate_widget_release_1467720"])

    report = {
        "schema": "hd2_loadout_lifecycle_abi_audit_v1",
        "build": BUILD,
        "source_capture_sha256": image.report.get("capture_sha256"),
        "source_sha256": EXPECTED,
        "source_evidence": str(args.evidence),
        "checks": checks,
        "checks_passed": sum(x["passed"] for x in checks),
        "checks_total": len(checks),
        "verification_passed": all(x["passed"] for x in checks),
        "lifecycle": {
            "screen_entry_rebuild": {"rva": "0x1465820", "release_before_reconstruct": "0x1467330", "construct_tail": "0x1466170"},
            "screen_constructor": {"rva": "0x14a17e0", "records_loop_count": 4, "widget_base": "0x53a78", "widget_stride": "0x1ee18", "widget_constructor": "0x14aa5c0"},
            "widget_constructor": {"rva": "0x14aa5c0", "nested_initializer": "0x14aa860", "nested_stride_fields": ["0x220", "0x378"]},
            "screen_release": {"rva": "0x1467330", "shared_release_helper": "0x144dd70", "widget_loop_base": "0x57fc0", "widget_stride": "0x1ee18", "count": 4},
            "alternate_widget_release": {"rva": "0x1467720", "nested_release_helper": "0x18a0fd0", "widget_loop_base": "0x55a20", "widget_stride": "0x1ee18", "count": 4},
            "transition": {"rva": "0x1470a40", "widget_base": "0x53a78", "callbacks": ["0x189e080", "0x1451100"], "count": 4, "stride": "0x1ee18"},
            "runtime_guard_consumers": ["0x189d050", "0x146e0a0", "0x146e84b"],
        },
        "implementation_boundary": {
            "reusable_native_pairs": [
                {"init": "0x14aa5c0", "nested_init": "0x14aa860", "release": "0x144dd70", "ownership": "per-widget object and nested members"},
                {"init": "0x189e080/0x1451100", "release": "0x18a0fd0", "ownership": "transition/update state, requires callback and widget lifetime"},
            ],
            "implementable_next_step": "Add a versioned loadout sidecar contract that allocates eight records/maps/widgets and exposes constructor, transition, release and reconnect operations; do not patch native loops until every captured +4 guard and owner/destructor callback is bound.",
            "blocked_reasons": [
                "The outer constructor, both release loops and transition each hard-code four iterations.",
                "Runtime helpers 0x189d050 and 0x146e0a0 contain independent index/ordinal guards at four.",
                "Release uses different internal widget offsets (+57fc0 and +55a20), so changing only +53a78 is unsafe.",
                "No writable object capture or callback/allocator ABI is available for a production hook.",
            ],
        },
        "production_patch_ready": False,
        "runtime_verified": False,
        "installable": False,
        "multiplayer_verified": False,
        "live_process_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "checks_passed": report["checks_passed"], "checks_total": report["checks_total"], "verification_passed": report["verification_passed"]}, ensure_ascii=False))
    return 0 if report["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
