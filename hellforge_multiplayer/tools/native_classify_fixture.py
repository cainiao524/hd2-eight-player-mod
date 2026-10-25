"""Export C++ classification results for the real loader's synthetic reader test."""
import argparse,json,struct
from pathlib import Path
import native_classify_image as native
from native_property_library import Library

def generate(output,library):
    p=native.load_fixture();native.bind_fixture(p,Library(library))
    f=p.Fixture('enter',8,8,2,7)
    for i in range(8):
        f.write(p.B+0x3C0+i*0x38,p.u64(100+i));f.write(p.B+0x3C0+i*0x38+0x18,p.u32(3))
        f.write(p.B+0x580+i*0x20,p.u32(0x1000+i));f.write(p.B+0x580+i*0x20+12,p.u32((3*i+2)%8))
    exports={};runs=[]
    def export(path):
        regions=[(p.S,f.read(p.S,0xE8)),(p.B,f.read(p.B,0x680)),(p.MAP,f.read(p.MAP,64))]
        regions += [(p.ENTITY+i*0x40,f.read(p.ENTITY+i*0x40,12)) for i in range(8)]
        user=0x18201000000
        regions += [(p.GAME+0x3326468,p.u64(p.S)),(p.GAME+0x347CEF0,p.u64(user)),(user+0xB398,p.u64(107))]
        blob=b'EPNATV1\0'+struct.pack('<QQQI',p.GAME,p.S,p.B,len(regions))
        for address,data in regions:blob+=struct.pack('<QI',address,len(data))+data
        path.write_bytes(blob);exports[path.name]=dict(bytes=len(blob),sha256=native.sha(blob))
    export(output)
    for kind,key,expected in [('enter',67,[0,1,7,3,4,5,6,2]),('leave',11,[7,1,0,3,4,5,6,2])]:
        f.select(kind);f.capture_records();f.t,f.d,f.p=struct.unpack('<III',f.read(p.S+0x80,12))
        f.ordinal=f.keys.index(key);f.target=f.int64(f.slot('pointer',f.ordinal))
        f.write(f.target+0x14,b'\x01');f.reset_call();f.run('hellforge_classify_'+kind)
        p.ClassifyTests().success(f)
        if kind=='leave':f.write(f.target+0x14,b'\0')
        actual=[(f.int32(f.int64(p.B+i*8)+8)-11)//8 for i in range(8)]
        native.require(actual==expected,'Classification identity order differs')
        runs.append(dict(kind=kind,instructions=len(f.trace),helper_calls=len(f.calls),peer_order=actual,
                         counts=list(struct.unpack('<III',f.read(p.S+0x80,12)))))
        export(output.with_suffix('.'+kind+'.bin'))
    return dict(classify_images_emitted_by_native_mod_code=True,fixtures=exports,runs=runs,
                temporary_helpers_are_contract_stubs=True,caller_flags_and_identity_are_synthetic=True,
                real_admission_executed=False,game_access=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--property-library',type=Path,required=True)
    a=p.parse_args();print(json.dumps(generate(a.output.resolve(),a.property_library)))
