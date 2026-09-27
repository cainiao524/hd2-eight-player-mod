# Confirmed-peer RPC binding: pinned-capture evidence

All observations use the existing build `25480438` `game.dll` capture. `inspect_capture.py` revalidated capture identity SHA-256 `5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8`, report SHA-256 `132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5`, and captured-data SHA-256 `31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d`. No game or installed file was executed or changed.

## Strongest semantic pairing

The same host loop `0x108C760` chooses two implementations for the same five values. It reads the member identifier, secondary identifier, `+0x10` dword, `+0x14` player-index dword, and state-derived byte, then compares the member identifier with `[global+0xB398]` at `0x108C943`.

| Case | Control-flow and call | Five-argument effect |
| --- | --- | --- |
| Earlier member description | `0x108C8F0–0x108C923` | Sends member slot fields through `0xBE4910` to the newly joined identifier. |
| Identifier equals `[global+0xB398]` | `0x108C943–0x108C960` | Calls `0xB90B20` directly with the new member fields. |
| Identifier differs | `0x108C967–0x108C97B` | Calls `0xBE4910` with the same new member fields. |

The argument setup in the equal and unequal arms uses the same `r8`, `r9d`, `[rsp+0x20]`, and `[rsp+0x28]` values; only the selected call target differs. `0xBE4910` supplies hash `0x4804FCF4` and five descriptors to `0xBDE430` at `0xBE4981–0xBE49B8`. The fourth descriptor has type `1`, size `4` and points to the player-index argument. This is stronger than matching the number of fields alone: the native host explicitly uses `0xB90B20` as the direct equivalent of that outgoing RPC call. See `rpc_binding_host_peer_loop_a.json`, `rpc_binding_host_peer_loop_b.json`, `protocol_host_to_client_dispatch.json`, and `protocol_confirmed_peer_sender.json`.

The only validated direct callers of `0xB90B20` found by the bounded code xref scan are this host branch at `0x108C960` and wrapper `0xBABA80` at `0xBABAAF`. `0xBABA80` reads five decoded field pointers at input offsets `+8,+0x18,+0x28,+0x38,+0x48`, passes their values in the same argument positions, and calls `0xB90B20`. That function appends the fourth dword to client peer record `+0x14` (`0xB90C0B–0xB90C12`). See `protocol_client_dispatch_xrefs.json`, `protocol_client_dispatch_alt.json`, and `protocol_b90b20_body.json`.

This establishes a **code-level semantic pairing** among hash `0x4804FCF4`'s send wrapper, the direct client handler, and the matching receive wrapper. It does not independently show that the runtime RPC registry dispatches that hash to `0xBABA80`.

## Static pointer and hash observations

The captured readonly pointer at RVA `0x214C820` equals image-base plus `0xBABA80`. It is entry **168** (zero-based) of a contiguous 592-entry, ascending code-pointer run at `0x214C2E0–0x214D55F`, whose first and last function RVAs are `0xBA23C0` and `0xBC2C80`. This run hashes to SHA-256 `6b24549f9c893123f4ea0b41e34e67bf92430b523ed9717b404fcc94c9d79aae`. It contains function pointers, with no observed per-entry hashes or receiver-registration metadata. See `rpc_binding_callback_table.json`.

Scanning every captured range for little-endian bytes `f4 fc 04 48` finds one occurrence, the `mov ecx,0x4804FCF4` immediate at `0xBE4981`. Thus this capture contains no second plain 32-bit copy of that hash alongside the wrapper-pointer run. This negative result covers only the captured ranges: headers, code, readonly, unwind, and three small later readonly regions. See `rpc_binding_hash_occurrences.json`.

The quick code scan finds no validated RIP `LEA`/`MOV` target inside `0x214C000–0x214CA00`, including the start and entry 168 of the pointer run; the exact-base xref scan also finds no branch, RIP reference, absolute pointer, or RVA literal to `0x214C2E0` or `0x214C820` elsewhere in the captured areas. Those bounded scans do not exclude other opcode forms, computed addresses, or uncaptured writable pointers. See `rpc_binding_table_refs.json` and `rpc_binding_table_base_xrefs.json`.

The outgoing generic dispatcher `0xBDE430` loads a pointer from RVA `0x3326308` at `0xBDE48B`/`0xBDE68A`, selects `[api+0x38]`, and invokes `[subtable+0x40]` or `[subtable+0x38]` depending on target mode. RVA `0x3326308` lies in the uncaptured writable interval `0x263C000–0x37D7FFF`; neither that API object nor its implementation is present in this capture. This is a concrete missing **send-side** datum. The specific hash-to-callback **receive-side** registry/global was not identified; it must not be equated with the send-side API slot. See `protocol_status_serializer.json`.

## Remaining binding observation

A read-only capture of the runtime RPC registration table, or a validated receive-dispatch trace showing input hash `0x4804FCF4` selecting callback `0xBABA80`, would close the remaining registry edge. The static pointer index `168` narrows the candidate table entry but cannot by itself establish the hash-to-callback mapping. No fifth-player gameplay or on-wire frame can be inferred from this binding evidence.
