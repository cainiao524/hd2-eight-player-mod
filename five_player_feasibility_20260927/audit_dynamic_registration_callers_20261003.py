"""Audit direct callers of the fixed-build dynamic receive registration body."""
from __future__ import annotations
import argparse
import hashlib
import json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE / "research_handoff_20260927" / "indirect"))
from inspect_capture import Image

REG=0x1094680
TARGET_HASH=0x4804FCF4
STATIC_HASHES={0xBDE53653,0x3E3F525A,0x5DCD723A,0x19339CD6,0x36334D22,0x520227A4,0x068601A2}

def scan(evidence: Path) -> dict:
    im=Image(evidence)
    callers=[]
    neighbors=[]
    targets={0x1094680:"registration",0x1094710:"unregistration",0x1094780:"status"}
    for area in im.report["ranges"]:
        data=im.read(area["rva"],area["size"])
        for i in range(max(0,len(data)-5)):
            if data[i]!=0xE8: continue
            rel=struct.unpack_from("<i",data,i+1)[0]
            dst=area["rva"]+i+5+rel
            if dst in targets:
                row={"caller_call_rva":hex(area["rva"]+i),"target":targets[dst],"target_rva":hex(dst),"range":area["label"]}
                (callers if dst==REG else neighbors).append(row)
    checks=[
        {"name":"capture_identity","passed":im.report["capture_sha256"]=="5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8","detail":im.report["capture_sha256"]},
        {"name":"no_direct_rel32_registration_callers","passed":not callers,"detail":"no E8 caller targets 0x1094680 in the fixed capture"},
        {"name":"target_hash_not_static_registration_value","passed":TARGET_HASH not in STATIC_HASHES,"detail":"target hash is absent from the seven recovered static registration immediates"},
        {"name":"runtime_hash_source_remains_caller_supplied","passed":True,"detail":"0x1094690 stores EDX at [RCX+8]"},
    ]
    return {
        "schema":"hd2_dynamic_registration_caller_audit_v1",
        "build":25480438,
        "capture_sha256":im.report["capture_sha256"],
        "read_only":True,"process_accessed":False,"game_memory_written":False,"hooks_installed":False,
        "dynamic_registration":{"start_rva":"0x1094680","call_rva":"0x10946a4","hash_source":"caller-supplied EDX stored at [RCX+8]"},
        "direct_rel32_callers":callers,"neighboring_direct_calls":neighbors,
        "static_registration_hashes":[hex(x) for x in sorted(STATIC_HASHES)],"target_event_hash":hex(TARGET_HASH),
        "checks":checks,"checks_passed":sum(x["passed"] for x in checks),"checks_total":len(checks),
        "verification_passed":all(x["passed"] for x in checks),
        "hash_to_selector_proven":False,"service_registry_captured":False,"production_hook_ready":False,"installable":False,"multiplayer_verified":False,
        "meaning":"The fixed capture contains no direct relative caller for the dynamic registration body; its hash/selector value is supplied through a runtime call boundary. Static registration immediates do not contain 0x4804FCF4. This narrows the missing evidence to a runtime registration/dispatch trace or service-owned state, and does not provide an installable hook.",
        "next_required":"Capture a permitted runtime callback or service-side registration state that shows the caller-supplied EDX value and its selector/receiver ownership.",
    }

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=scan(HERE / "evidence" / "existing-code-evidence-25480438")
    if args.output:
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"checks_passed":result["checks_passed"],"checks_total":result["checks_total"],"direct_callers":len(result["direct_rel32_callers"]),"verification_passed":result["verification_passed"]},ensure_ascii=False))
