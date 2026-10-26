"""Bridge to our own numeric image-emitter DLL; never executes emitted code."""
import ctypes as c
import functools
from pathlib import Path
import native_component33_image as n
class Addresses(c.Structure):
    _fields_=[(k,c.c_uint64) for k in ('game_base','code_address','component_address','storage_address','move_code_address','reject_address')]
class Image(c.Structure):
    _fields_=[(k,c.c_uint32) for k in ('bytes','code_bytes','unwind_offset','table_offset','function_count')]+[('data',c.c_ubyte*4096)]
class Library:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True);self.dll=c.CDLL(str(self.path))
        self.build=self.dll.component33_image_test_build
        self.build.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)];self.build.restype=c.c_int
    @functools.lru_cache(maxsize=128)
    def candidate(self,kind,**addresses):
        ref=n.build(kind,**addresses);out=Image();rc=self.build(n.ALL_KINDS.index(kind)+1,Addresses(**addresses),out)
        n.need(rc==0 and bytes(out.data[:out.bytes])==ref['image'],'C++ component33 differs')
        n.need((out.code_bytes,out.unwind_offset,out.table_offset,out.function_count)==tuple(ref[k] for k in ('code_bytes','unwind_offset','table_offset','function_count')),'C++ metadata differs')
        return {**ref,'image':bytes(out.data[:out.bytes])}
