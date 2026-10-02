"""Verify the external confirmed-peer chain inventory without touching a process."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    "0x108c18f": "host_capacity_gate",
    "0x108c3d8": "host_index_allocator",
    "0x108c760": "host_confirmed_peer_sender",
    "0xb90b20": "client_confirmed_peer_insert",
    "0x1086460": "player_creation_gate",
}

def fail(msg: str) -> None:
    raise SystemExit(msg)

def verify(path: Path) -> dict:
    d=json.loads(path.read_text(encoding="utf-8"))
    if d.get("schema") != "confirmed_peer_external_chain_v1": fail("schema mismatch")
    if d.get("status") != "static_external_abi_blocker": fail("status mismatch")
    sites={s["rva"].lower(): s for s in d.get("sites",[])}
    if set(sites) != set(EXPECTED): fail("site set mismatch")
    for rva,name in EXPECTED.items():
        s=sites[rva]
        if s.get("name") != name: fail(f"name mismatch {rva}")
        if s.get("read_only") is not True: fail(f"read-only missing {rva}")
        if not s.get("source_row_sha256") or len(s["source_row_sha256"]) != 64: fail(f"row hash missing {rva}")
    c=d.get("capture_integrity",{})
    for key in ("main_capture_sha256","confirmed_capture_sha256"):
        if len(c.get(key,"")) != 64: fail(f"capture hash missing {key}")
    contract=d.get("sidecar_contract",{})
    if contract.get("logical_max_players") != 8: fail("logical max must be 8")
    if contract.get("valid_network_index") != [0,7]: fail("index interval mismatch")
    if contract.get("installable") is not False or contract.get("runtime_verified") is not False or contract.get("multiplayer_verified") is not False:
        fail("artifact must remain fail-closed")
    if len(d.get("required_lifecycle_paths",[])) != 4: fail("lifecycle path inventory incomplete")
    return {"status":"passed_static_external_chain_verification","sites":len(sites),"installable":False,"multiplayer_verified":False}

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--artifact",type=Path,required=True)
    print(json.dumps(verify(ap.parse_args().artifact),ensure_ascii=False))
if __name__ == "__main__": main()
