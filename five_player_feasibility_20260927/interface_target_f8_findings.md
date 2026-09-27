# Offline inspection of `api+0xF8` / slot `+0xA0`

The saved probe `interface_probe_live_20260927_1.json` has SHA-256 `a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f`. It observed `api+0xF8` slot `+0xA0` pointing to `helldivers2.exe` RVA `0x8C6730` and saved 256 bytes with SHA-256 `14e69e3aaea1ffc9bc04ed88cbf0ac1be6887485f65b5330006c0c06e6520720`. The probe did not invoke the function. The analysis script `interface_target_f8_offline.py` reads this saved JSON and the pinned disk EXE only; it does not access the process.

## Disk identity and the missing code region

The installed EXE SHA-256 is `f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06`, matching the probe's pinned image. Its PE timestamp `1790149348` and `SizeOfImage` `60719104` also match. This verifies the **file identity**, not equality of the target's runtime and disk bytes.

RVA `0x8C6730` lies in the first PE section, which has virtual address `0x1000`, virtual size `0x13F364C`, and raw-data size `0x663400`. The target's offset within that section is `0x8C5730`, beyond the raw-data size. The target's 256 bytes have **no raw bytes at that RVA on disk** to compare with the saved runtime prefix. Both direct callee RVAs, `0x8CCFA0` and `0x8E1370`, are likewise outside this section's raw-data extent. The PE exception directory points to RVA `0x31840A0` in `.winlice`, whose raw-data size is zero; disk unwind entries cannot be parsed. There is consequently no justified disk-derived function body or unwind boundary for this target or either callee. See `interface_target_f8_offline_v2.json` for section bounds and callsite bytes.

## What the saved runtime prefix establishes

The 256-byte prefix contains a complete first function ending in `ret` at `0x8C67DB` (followed by `int3` padding and the start of another function). In this function, the first 32-bit argument in `ECX` is copied to `ESI` at `0x8C6742`. A separate byte argument in `DL` is zero-extended into `EDI` at `0x8C674F`. Fields at `r8+0x10,+0x18,+0x20,+0x28,+0x30,+0x38` are copied into locals; the meaning of that input record is unverified.

At `0x8C67AD`, the function directly calls `0x8CCFA0` with a pointer to a zero-initialized local record in `RDX` and an object pointer in `RCX` loaded through a writable global. The return value in `RAX` is kept as an object pointer. At `0x8C67B2`, `ESI` is copied to `EDX`; at `0x8C67BB`, it is stored as a dword at `[RAX+0x20]`, while the byte from `DL` is stored at `[RAX+0x24]` at `0x8C67BE`. The function then calls `0x8E1370` at `0x8C67C2`, passing `[RAX+0x18]` in `RCX` and the original 32-bit first argument in `EDX`. No comparison or clamp of that integer appears in the saved first function.

The two callee addresses are validated by the relative `call` instruction bytes in the saved runtime prefix. Their bodies were not captured and are not backed by raw disk bytes, so their behavior and any deeper constraints remain unknown. The first integer's meaning, service-side acceptance, and eight-player gameplay are unverified.
