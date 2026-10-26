"""Verify fifteen switches and rebase all validated body unwind PCs."""
import argparse,ctypes as c,json,struct
from pathlib import Path
from datetime import datetime,timezone
from native_property_library import Library,InsertAddresses
import native_producer_unwind as reference
import native_getter_image,native_mover_image,native_insert_image,native_remove_image,native_classify_image
import native_registry_image,native_departure_image
from build_unwind_offline import load as producer_fixture,run
from build_receiver_unwind_offline import load as receiver_fixture
from validate_property_gates import gate_paths,CONTROL
PROJECT=reference.PROJECT
class Gate(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','table_offset','function_count')]+[('data',c.c_ubyte*2816)]
def validate(path,zig):
    library=Library(path);emit=library.dll.roster_gate_test_build
    emit.argtypes=[c.c_uint32,c.POINTER(InsertAddresses),c.c_uint64,c.c_uint64,c.POINTER(Gate)];emit.restype=c.c_int
    build=PROJECT/'build';exe=build/'native_roster_gate_unwind_test.exe'
    run([zig,'cc','-std=c11','-target','x86_64-windows-gnu','-O1','-Wall','-Werror','-DEP_ROSTER_GATES=1','-DEP_CONTEXT_LIMIT=200000u',PROJECT/'tests/native_producer_unwind_test.c','-o',exe])
    cases=[('producer',producer_fixture().parameters()),('receiver',receiver_fixture().parameters()),
           ('getter',native_getter_image.load_fixture().params()),('mover',native_mover_image.load_fixture().parameters())]
    for module,prefix,kinds in ((native_insert_image,'insert-',native_insert_image.KINDS),(native_remove_image,'remove-',native_remove_image.KINDS),(native_classify_image,'classify-',('enter','leave'))):
        p=module.load_fixture()
        for kind in kinds:cases.append((prefix+kind,p.params(kind)))
    registry=native_registry_image.load_fixture();ra=registry.params()
    cases += [('registry-update',{k:v for k,v in ra.items() if k!='helper_reject_address'}),
              ('registry-association',dict(game_base=ra['game_base'],code_address=ra['helper_code_address'],
                  roster_address=ra['roster_address'],storage_address=ra['storage_address'],reject_address=ra['helper_reject_address']))]
    cases.append(('departure',native_departure_image.load_fixture().params()))
    departure_exe=build/'native_departure_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-O1','-Wall','-Werror',PROJECT/'tests/native_departure_unwind_test.c','-o',departure_exe])
    registry_exe=build/'native_registry_gates_unwind_test.exe'
    run([zig,'cc','-target','x86_64-windows-gnu','-std=c11','-DEP_REGISTRY=1','-DEP_CONTEXT_LIMIT=200000u','-O1','-Wall','-Werror',PROJECT/'tests/native_producer_unwind_test.c','-o',registry_exe])
    results={};artifacts=[exe,registry_exe,departure_exe,library.path];inputs={};branches=refusals=0
    for kind,(name,raw) in enumerate(cases,1):
        a={k:v for k,v in raw.items() if k!='kind'}
        if 'property_address' in a:a['storage_address']=a.pop('property_address')-0x580
        if 'helper_code_address' in a:a['move_code_address']=a.pop('helper_code_address')
        if 'getter_code_address' in a:a['move_code_address']=a.pop('getter_code_address')
        a.setdefault('move_code_address',0);a['code_address']-=32
        out=Gate();reference.require(emit(kind,InsertAddresses(**a),CONTROL,CONTROL+8,out)==0,'Roster gate generation failed: '+name)
        blob=bytes(out.data[:out.bytes]);branches+=gate_paths(blob,a['code_address'],a['code_address']+32)
        original=build/(name+'-unwind-contexts.bin');data=original.read_bytes();inputs[original.name]=reference.sha(data)
        wide=kind==15;variant_count=4 if wide else 2;expected_bytes=88 if wide else 72;row_bytes=476 if wide else 332
        reference.require(data[:12]==(b'EPUWDX1\0' if wide else b'EPUWDV1\0')+struct.pack('<I',variant_count),'Unknown context schema')
        offset=12;variants=[]
        for v in range(variant_count):
            size,code,table,count=struct.unpack_from('<4I',data,offset);end=offset+16+size+expected_bytes+count*row_bytes
            if v+1<variant_count:variants.append(data[offset:end])
            else:
                # Chained parent RVAs are rebased inside the metadata as well
                # as in the table; the Windows validator checks those links.
                unchanged=code if kind>=13 else table
                reference.require(blob[32:32+unchanged]==data[offset+16:offset+16+unchanged],'Candidate changed when gated: '+name)
                contexts=bytearray(data[offset+16+size+expected_bytes:end])
                for i in range(count):struct.pack_into('<I',contexts,i*row_bytes,struct.unpack_from('<I',contexts,i*row_bytes)[0]+32)
                variants.append(struct.pack('<4I',len(blob),code+32,out.table_offset,count)+blob+data[offset+16+size:offset+16+size+expected_bytes]+contexts)
            offset=end
        reference.require(offset==len(data),'Trailing context data')
        target=build/(name+'-roster-gated-contexts.bin');target.write_bytes(data[:12]+b''.join(variants));artifacts.append(target)
        windows=json.loads(run([departure_exe if wide else registry_exe if kind>=13 else exe,target]))
        results[name]=dict(bytes=out.bytes,function_count=out.function_count,windows_unwind_contexts=windows['windows_unwind_contexts'],reference_negative_controls_rejected=windows['negative_controls_rejected' if wide else 'legacy_rejection_failures_reproduced'])
        bad=[(CONTROL+1,CONTROL+8,a),(CONTROL,CONTROL+4,a),(CONTROL,CONTROL,a),
             (a['roster_address'],CONTROL+8,a),(a['storage_address'],CONTROL+8,a),
             (CONTROL,CONTROL+8,{**a,'reject_address':a['code_address']+out.bytes-1}),
             (CONTROL,CONTROL+8,{**a,'storage_address':a['game_base']+0x60D300}),
             (CONTROL,CONTROL+8,{**a,'roster_address':a['game_base']+0x173B9F0})]
        if 5<=kind<=10:bad.append((CONTROL,a['move_code_address']+608,a))
        if kind==13:bad.append((CONTROL,a['move_code_address']+480,a))
        if kind==15:bad.append((CONTROL,a['move_code_address']+384,a))
        bad += [(a['game_base']+0xFD9C80,CONTROL+8,a),(CONTROL,a['game_base']+0x605F00,a)]
        for control,next_pointer,bindings in bad:
            failed=Gate();c.memset(c.byref(failed),0xA5,c.sizeof(failed))
            reference.require(emit(kind,InsertAddresses(**bindings),control,next_pointer,failed)!=0 and bytes(failed)==bytes(c.sizeof(failed)),'Invalid roster gate accepted: '+name);refusals+=1
    for kind in (0,16,0xFFFFFFFF):
        failed=Gate();c.memset(c.byref(failed),0xA5,c.sizeof(failed));reference.require(emit(kind,InsertAddresses(**a),CONTROL,CONTROL+8,failed)==1 and bytes(failed)==bytes(c.sizeof(failed)),'Invalid kind accepted');refusals+=1
    paths=['mod/src/ep_roster_gate.h','mod/src/ep_roster_gate.cpp','tests/native_producer_unwind_test.c','tests/property_image_dll.cpp',
           'tools/validate_roster_gates.py','tools/validate_property_gates.py','tools/native_property_library.py']
    paths += [f'mod/src/ep_{name}.{suffix}' for name in ('property_gate','property_image','getter_image','mover_image','insert_image','remove_image','classify_image','registry_image','departure_image') for suffix in ('h','cpp')]
    paths += ['tools/native_registry_image.py','native-registry.lock.json','tools/native_departure_image.py','native-departure.lock.json','tests/native_departure_unwind_test.c']
    refs=['property-image','native-getter','native-mover','native-insert','native-remove','native-classify','native-registry','native-departure','property-gate']
    receipt=dict(schema='hellforge_roster_gate_validation_v1',verified_at_utc=datetime.now(timezone.utc).isoformat(),passed=True,
                 branch_cases=branches,placement_refusals=refusals,variants=results,
                 windows_unwind_contexts=sum(x['windows_unwind_contexts'] for x in results.values()),
                 source_sha256={p:reference.sha((PROJECT/p).read_bytes()) for p in paths},
                 artifacts={p.name:dict(bytes=p.stat().st_size,sha256=reference.sha(p.read_bytes())) for p in artifacts},inputs_sha256=inputs,
                 reference_validation_sha256={n+'-validation.json':reference.sha((PROJECT/'evidence'/(n+'-validation.json')).read_bytes()) for n in refs},
                 game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False)
    (PROJECT/'evidence/roster-gate-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','branch_cases','placement_refusals','windows_unwind_contexts','game_access')}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--zig',type=Path,required=True)
    a=p.parse_args();print(json.dumps(validate(a.library.resolve(),a.zig.resolve())))
