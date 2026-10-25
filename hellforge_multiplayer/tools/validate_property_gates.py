"""Verify real generated gate bytes and relocated unwind, never run a game."""
import argparse
import ctypes as c
from datetime import datetime,timezone
import json
from pathlib import Path
import struct
import native_producer_unwind as reference
from native_property_library import Library,Addresses,GetterAddresses,GateImage
import native_getter_image
from build_unwind_offline import load as producer_fixture,run
from build_receiver_unwind_offline import load as receiver_fixture
import unicorn as u
from unicorn import x86_const as r

PROJECT=reference.PROJECT
CONTROL=0x7FF000000000


def gate_paths(blob,base,body):
    regs=[r.UC_X86_REG_RBX,r.UC_X86_REG_RBP,r.UC_X86_REG_RSI,r.UC_X86_REG_RDI,
          r.UC_X86_REG_R12,r.UC_X86_REG_R13,r.UC_X86_REG_R14,r.UC_X86_REG_R15,
          r.UC_X86_REG_RCX,r.UC_X86_REG_RDX,r.UC_X86_REG_R8,r.UC_X86_REG_R9,
          r.UC_X86_REG_R10,r.UC_X86_REG_R11,r.UC_X86_REG_RSP]
    regs += [getattr(r,'UC_X86_REG_XMM'+str(i)) for i in range(16)]
    cases=0
    for active in (0,1,2):
        uc=u.Uc(u.UC_ARCH_X86,u.UC_MODE_64)
        start=base&~4095; uc.mem_map(start,((base+len(blob)+4095)&~4095)-start); uc.mem_write(base,blob)
        uc.mem_map(CONTROL,4096); uc.mem_write(CONTROL,struct.pack('<I',active))
        fallback=base-0x10000; uc.mem_map(fallback&~4095,4096)
        # End each destination's translation block before the page edge;
        # the code hook stops before this synthetic INT3 executes.
        uc.mem_write(fallback,b'\xCC'); uc.mem_write(fallback+16,b'\xCC')
        for destination in (fallback,fallback+16):
            uc.mem_write(CONTROL+8,struct.pack('<Q',destination)); reached=[]
            def stop(machine,address,size,data):
                if address in (body,destination): reached.append(address); machine.emu_stop()
            hook=uc.hook_add(u.UC_HOOK_CODE,stop)
            expected={reg:0x12340000+index for index,reg in enumerate(regs)}
            for reg,value in expected.items(): uc.reg_write(reg,value)
            uc.emu_start(base,base+len(blob),count=20)
            reference.require(reached==[body if active==1 else destination],'Gate selected wrong route')
            reference.require(all(uc.reg_read(reg)==value for reg,value in expected.items()),'Gate changed an argument, stack, vector or nonvolatile register')
            uc.hook_del(hook); cases+=1
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--library',type=Path,required=True)
    args=parser.parse_args(); library=Library(args.library); build=PROJECT/'build'
    results={}; artifacts=[]; branch_cases=refusals=0
    for kind,name,fixture in ((1,'producer',producer_fixture()),(2,'receiver',receiver_fixture()),(3,'getter',native_getter_image.load_fixture())):
        addresses=fixture.params() if kind==3 else fixture.parameters(); addresses['code_address']-=32
        def emit(bindings,control,next_pointer,out):
            return library.getter_gate(GetterAddresses(**bindings),control,next_pointer,out) if kind==3 else library.gate(kind,Addresses(**bindings),control,next_pointer,out)
        out=GateImage()
        reference.require(emit(addresses,CONTROL,CONTROL+8,out)==0,'Native gate generation failed')
        blob=bytes(out.data[:out.bytes]); branch_cases+=gate_paths(blob,addresses['code_address'],addresses['code_address']+32)
        # Keep the original negative control; rebase corrected contexts onto
        # the real C++ gate+candidate image and its two-entry function table.
        data=(build/(name+'-unwind-contexts.bin')).read_bytes(); reference.require(data[:12]==b'EPUWDV1\0'+struct.pack('<I',2),'Unexpected fixture')
        offset=12; variants=[]
        for variant in range(2):
            size,code,table,count=struct.unpack_from('<4I',data,offset); end=offset+16+size+72+count*332
            if variant==0: variants.append(data[offset:end])
            else:
                old=data[offset+16:offset+16+size]
                reference.require(blob[32:32+table]==old[:table],'Gated candidate differs from original validated image')
                contexts=bytearray(data[offset+16+size+72:end])
                for i in range(count): struct.pack_into('<I',contexts,i*332,struct.unpack_from('<I',contexts,i*332)[0]+32)
                variants.append(struct.pack('<4I',len(blob),code+32,out.table_offset,count)+blob+data[offset+16+size:offset+16+size+72]+contexts)
            offset=end
        reference.require(offset==len(data),'Trailing contexts')
        path=build/(name+'-gated-unwind-contexts.bin'); path.write_bytes(data[:12]+b''.join(variants)); artifacts.append(path)
        exe=build/('native_'+name+'_unwind_test.exe'); results[name]=json.loads(run([exe,path]))
        if kind==3: results[name]['injected_metadata_faults_rejected']=results[name].pop('legacy_rejection_failures_reproduced')
        for control,next_pointer,bindings in (
            (CONTROL+1,CONTROL+8,addresses),(CONTROL,CONTROL+4,addresses),
            (CONTROL,CONTROL,addresses),(addresses['roster_address'],CONTROL+8,addresses),
            (CONTROL,CONTROL+8,{**addresses,'reject_address':addresses['code_address']}),
            (CONTROL,CONTROL+8,{**addresses,'reject_address':addresses['code_address']+out.bytes-1}),
            (CONTROL,CONTROL+8,{**addresses,'code_address':addresses['game_base']+0x606AD0}),
            (addresses.get('storage_address',addresses.get('property_address')),CONTROL+8,addresses)):
            failed=GateImage(); c.memset(c.byref(failed),0xA5,c.sizeof(failed))
            reference.require(emit(bindings,control,next_pointer,failed)!=0 and bytes(failed)==bytes(c.sizeof(failed)),'Invalid gate image was accepted')
            refusals+=1
    paths=('mod/src/ep_property_gate.h','mod/src/ep_property_gate.cpp','mod/src/ep_property_image.h','mod/src/ep_property_image.cpp',
           'mod/src/ep_property_templates.h','tools/validate_property_gates.py','tools/native_property_library.py',
           'tests/native_producer_unwind_test.c','tests/property_image_dll.cpp','tools/build_unwind_offline.py',
           'tools/build_receiver_unwind_offline.py','tools/native_producer_unwind.py','tools/native_receiver_unwind.py',
           'tools/native_unwind_source.py','native-unwind-source.lock.json','native-storage.lock.json',
           'mod/src/ep_getter_image.h','mod/src/ep_getter_image.cpp','mod/src/ep_getter_template.h',
           'tools/native_getter_image.py','native-getter.lock.json')
    inputs=[build/(name+suffix) for name in ('producer','receiver','getter') for suffix in ('-unwind-contexts.bin',)]
    inputs += [build/('native_'+name+'_unwind_test.exe') for name in ('producer','receiver','getter')]
    receipt={'schema':'hellforge_property_gate_validation_v1','verified_at_utc':datetime.now(timezone.utc).isoformat(),
             'passed':True,'branch_cases':branch_cases,'placement_refusals':refusals,'windows_unwind':results,
             'source_sha256':{p:reference.sha((PROJECT/p).read_bytes()) for p in paths},
             'artifacts':{p.name:{'bytes':p.stat().st_size,'sha256':reference.sha(p.read_bytes())} for p in (*artifacts,library.path)},
             'inputs_sha256':{p.name:reference.sha(p.read_bytes()) for p in inputs},
             'reference_validation_sha256':{name:reference.sha((PROJECT/'evidence'/name).read_bytes()) for name in
                                            ('native-producer-unwind-validation.json','native-receiver-unwind-validation.json','native-unwind-source-validation.json','native-getter-validation.json')},
             'game_access':False,'native_execution_of_game_bodies':False,'runtime_verified':False,'multiplayer_verified':False}
    (PROJECT/'evidence/property-gate-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'branch_cases':branch_cases,'placement_refusals':refusals,
                      'windows_unwind_contexts':sum(r['windows_unwind_contexts'] for r in results.values()),'game_access':False}))


if __name__=='__main__': main()
