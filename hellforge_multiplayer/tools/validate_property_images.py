"""Differential native emitter validation; fixture addresses and our DLL only."""
import argparse
import ctypes as c
from datetime import datetime,timezone
import json
import random
from pathlib import Path
from generate_property_templates import REFERENCE,HEADER,render,producer,receiver,PROJECT
from native_property_library import Addresses,Image,Library


def validate(library):
    content,facts=render()
    producer.require(HEADER.read_bytes()==content,'Generated template mismatch')
    dll=Library(library); counts={'accepted':0,'rejected':0,'api_contract_checks':0,'owner_checks':0}
    failures={}; rng=random.Random(25480438)
    def compare(kind,module,addresses):
        try: expected=module.with_unwind(module.original(**addresses))
        except (ValueError,OverflowError): expected=None
        out=Image(); c.memset(c.byref(out),0xA5,c.sizeof(out))
        result=dll.build(kind,Addresses(**addresses),out)
        producer.require((result==0)==(expected is not None),'Acceptance mismatch '+repr((kind,addresses,result)))
        if expected is None:
            producer.require(bytes(out)==bytes(c.sizeof(out)),'Failed emission left partial output')
            counts['rejected']+=1; failures[str(result)]=failures.get(str(result),0)+1
        else:
            producer.require(bytes(out.data[:out.bytes])==expected['image'],'Different native image bytes')
            producer.require((out.code_bytes,out.unwind_offset,out.table_offset)==(expected['candidate']['size_bytes'],expected['unwind_offset'],expected['table_offset']),'Different image extents')
            counts['accepted']+=1
    for kind,name,module in ((1,'producer',producer),(2,'receiver',receiver)):
        cases=[dict(REFERENCE)]
        # Independently vary the image, code and both absolute storage bindings.
        for _ in range(256):
            game=rng.randrange(0x100000000,0x700000000000,0x1000)
            code=game+rng.randrange(-0x70000000,0x70000000,16)
            cases.append(dict(game_base=game,code_address=code,
                              roster_address=rng.randrange(0x10000000,0x700000000000,8),
                              property_address=rng.randrange(0x10000000,0x700000000000,8),
                              reject_address=code+rng.randrange(0x1000,0x100000)))
        cases += [{**REFERENCE,'property_address':0x3A8},
                  dict(game_base=(1<<47)-0x400000000,code_address=(1<<47)-0x3F0000000,
                       roster_address=(1<<47)-0x2000,property_address=(1<<47)-0x100,reject_address=(1<<47)-0x3F0010000)]
        for field in REFERENCE:
            for bad in (0,(1<<47),(1<<64)-1): cases.append({**REFERENCE,field:bad})
        for field in ('game_base','code_address','roster_address','property_address'):
            cases.append({**REFERENCE,field:REFERENCE[field]+1})
        cases += [{**REFERENCE,'property_address':0x3A0},
                  {**REFERENCE,'roster_address':(1<<47)-8},
                  {**REFERENCE,'property_address':(1<<47)-8},
                  {**REFERENCE,'game_base':(1<<47)-0x3483000}]
        # Include the metadata tail, not only executable instructions.
        rows=facts[name]; code=REFERENCE['code_address']
        for offset in (0,rows['code_bytes']-1,rows['unwind_offset'],rows['table_offset'],rows['image_bytes']-1,rows['image_bytes']):
            cases.append({**REFERENCE,'reject_address':code+offset})
        for rva in (0x3483C20,0x60C640 if kind==1 else 0x60C890):
            for field in ('roster_address','property_address','reject_address'):
                cases.append({**REFERENCE,field:REFERENCE['game_base']+rva})
        cases += [{**REFERENCE,'property_address':REFERENCE['roster_address']+0x420},
                  {**REFERENCE,'reject_address':REFERENCE['property_address']+0xFF},
                  {**REFERENCE,'roster_address':code+16}]
        if kind==1:
            for rva in (0x3326468,0x173B8D0,0x134F190,0x347CEF0):
                cases.append({**REFERENCE,'code_address':(REFERENCE['game_base']+rva)&~15})
        # Exact closed rel32 intersection, including the legacy intermediate
        # ranges; +/-1 around both endpoints must match reference refusal.
        jumps=[row[1] for row in rows['fixups']+rows['legacy_relative_ranges'] if row[2]==4]
        low=code+max(jumps)-(1<<31); high=code+min(jumps)+(1<<31)-1
        for value in (low-1,low,low+1,high-1,high,high+1): cases.append({**REFERENCE,'reject_address':value})
        # Move code across the signed RIP/call bounds at its required alignment.
        calls=[row for row in rows['fixups']+rows['legacy_relative_ranges'] if row[2]==0]
        for row in calls:
            target=REFERENCE['game_base']+row[4]
            for edge in (target-row[1]-(1<<31)+1,target-row[1]+(1<<31)):
                for delta in (-16,0,16):
                    boundary=(edge&~15)+delta
                    cases.append({**REFERENCE,'code_address':boundary,'reject_address':boundary+0x10000})
        for addresses in cases: compare(kind,module,addresses)
        addresses=Addresses(); actual=Image(); owner_checks=c.c_uint32()
        result=dll.prepare(kind,addresses,actual,owner_checks)
        producer.require(result==0,'Own-process prepare lifecycle failed at line '+str(result))
        values={field:getattr(addresses,field) for field in REFERENCE}
        expected=module.with_unwind(module.original(**values))
        producer.require(bytes(actual.data[:actual.bytes])==expected['image'],'Actual-allocation image differs')
        counts['owner_checks']+=owner_checks.value
    for kind,addr,output in ((0,Addresses(**REFERENCE),Image()),(3,Addresses(**REFERENCE),Image()),
                             (1,None,Image()),(1,Addresses(**REFERENCE),None)):
        producer.require(dll.build(kind,addr,output)==1,'Invalid API arguments accepted')
        if output is not None: producer.require(bytes(output)==bytes(c.sizeof(output)),'Invalid arguments left output')
        counts['api_contract_checks']+=1
    return {'schema':'hellforge_property_image_validation_v1','verified_at_utc':datetime.now(timezone.utc).isoformat(),
            'passed':True,'game_build':25480438,**counts,'failure_results':failures,
            'template_sha256':producer.sha(content),'functions':facts,
            'source_sha256':{p:producer.sha((PROJECT/p).read_bytes()) for p in (
                'mod/src/ep_property_image.h','mod/src/ep_property_image.cpp','mod/src/ep_property_templates.h',
                'mod/src/ep_property_code.h','mod/src/ep_property_code.cpp','mod/src/ep_session_code.h','mod/src/ep_session_code.cpp',
                'tests/property_image_dll.cpp','tools/generate_property_templates.py','tools/native_property_library.py',
                'tools/validate_property_images.py','tools/native_producer_unwind.py','tools/native_receiver_unwind.py',
                'tools/native_unwind_source.py','native-unwind-source.lock.json','native-storage.lock.json')},
            'artifacts':{dll.path.name:{'bytes':dll.path.stat().st_size,'sha256':producer.sha(dll.path.read_bytes())}},
            'game_access':False,'game_candidate_executed_natively':False,'hook_published':False,
            'production_mod_autobound':False,'runtime_verified':False,'multiplayer_verified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--library',type=Path,required=True)
    args=parser.parse_args(); receipt=validate(args.library)
    (PROJECT/'evidence/property-image-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:receipt[key] for key in ('passed','accepted','rejected','api_contract_checks','owner_checks','game_access')}))
