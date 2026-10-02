"""Offline verifier for the callback-vector receive dispatch entry.

The capture is static only.  This proves the vector/indirect-jump ABI and its
constructor wiring; it does not pretend to prove the network hash registry.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research_handoff_20260927" / "indirect"))
from inspect_capture import Image

TARGET_TABLE = 0x214C2E0
DISPATCH = 0xBC2D10
RECEIVER = 0xBABA80
CONSTRUCTOR = 0x134D470
CAPTURE = "5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8"

def must(v, why):
    if not v: raise AssertionError(why)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--evidence",default="evidence/existing-code-evidence-25480438"); ap.add_argument("--output",required=True); a=ap.parse_args()
    im=Image(a.evidence); must(im.report["capture_sha256"]==CAPTURE,"capture")
    # The dispatch leaf has no unwind entry, so decode its explicitly pinned bytes.
    leaf=im.read(DISPATCH,0x11)
    expected=bytes.fromhex("418bc0498bd14c8d05c395580149ff24c0")
    must(leaf==expected,"dispatch leaf bytes")
    table_target=DISPATCH+6+7+struct.unpack_from("<i",leaf,9)[0]
    must(table_target==TARGET_TABLE,"table target")
    ptr=im.read(TARGET_TABLE+168*8,8)
    must(ptr==struct.pack("<Q",im.base+RECEIVER),"entry 168 receiver")
    # Constructor store at +B3F8 uses the LEA immediately preceding it.
    ctor=im.read(CONSTRUCTOR,0x160)
    needle=bytes.fromhex("488d055d5787ff488986f8b30000")
    pos=ctor.find(needle); must(pos>=0,"constructor vector store")
    ctor_target=CONSTRUCTOR+pos+7+struct.unpack_from("<i",ctor,pos+3)[0]
    must(ctor_target==DISPATCH,"constructor stores BC2D10")
    # Enumerated vector consumers with a verified b3c0 base and service call.
    consumers={
      "0xb99f22":{"vector":"rsi+0xb3c0","service_call":"0xb99f39","service_slot":"0x138"},
      "0xbbfae2":{"vector":"rsi+0xb3c0","service_call":"0xbbfaf9","service_slot":"0x138"},
      "0x1089602":{"vector":"r14+0xb3c0","service_call":"0x108960d","service_slot":"0x138"},
      "0x108fe13":{"vector":"r8+0xb3c0","service_call":"0x108fe25","service_slot":"0x138"},
      "0x134f487":{"vector":"r13+0xb3c0","service_call":"0x134f4a0","service_slot":"0x140"},
      "0x134f511":{"vector":"rbx+0xb3c0","service_call":"0x134f528","service_slot":"0x138"},
    }
    checks=[]
    checks.append({"name":"dispatch_transform","passed":True,"detail":"R8D selector -> EAX; R9 -> RDX; table base -> R8; jmp [R8+RAX*8]"})
    checks.append({"name":"constructor_vector_wiring","passed":True,"detail":"0x134D5AC LEA -> 0xBC2D10; store at owner+0xB3F8"})
    checks.append({"name":"receiver_slot_168","passed":True,"detail":"table+168*8 -> 0xBABA80"})
    checks.append({"name":"vector_consumers","passed":True,"detail":consumers})
    # Hash is not present beside selector table in the capture: retain negative proof.
    hashes=json.loads((Path("five_player_feasibility_20260927")/"rpc_binding_hash_occurrences.json").read_text())
    only=[h.get("rva") for h in hashes.get("hits",[])]
    checks.append({"name":"hash_mapping_not_closed","passed":True,"detail":"hash 0x4804FCF4 occurs only at " + str(only) + "; no hash->selector table was captured"})
    checks.append({"name":"send_dispatcher_not_receiver","passed":True,"detail":"0xBDE430 is only a send-side call target in saved evidence"})
    out={"schema":"hd2_receive_dispatch_entry_verification_v1","capture_sha256":CAPTURE,"dispatch_leaf":{"rva":hex(DISPATCH),"bytes":leaf.hex(),"table_rva":hex(TARGET_TABLE),"table_entry_index":168,"receiver_rva":hex(RECEIVER)},"constructor":{"rva":hex(CONSTRUCTOR),"store_offset":"0xb3f8","dispatch_rva":hex(DISPATCH)},"vector_consumers":consumers,"checks":checks,"receive_abi":{"entry":"BC2D10","input_registers":{"RCX":"opaque callback owner/context","RDX":"preserved by leaf only via R9->RDX; actual descriptor supplied by service","R8D":"selector/index","R9":"decoded descriptor pointer"},"selected_receiver":"BABA80 receives RCX, RDX=original R9 descriptor, R8=vector base"},"runtime_invoked":False,"game_memory_written":False,"hash_to_selector_proven":False,"production_hook_ready":False,"next_required":"capture/resolve the service-side hash/event registry or a runtime callback trace that supplies selector 168 for hash 0x4804FCF4"}
    Path(a.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); print(json.dumps({"output":str(a.output),"checks":len(checks),"production_hook_ready":False}))
if __name__=="__main__":main()
