"""Own departure test DLL; never load this in the game."""
import ctypes as c
from pathlib import Path
class Addresses(c.Structure):
    _fields_=[(n,c.c_uint64) for n in ('game_base','code_address','roster_address','storage_address','getter_code_address','reject_address')]
class Image(c.Structure):
    _fields_=[(n,c.c_uint32) for n in ('bytes','code_bytes','unwind_offset','table_offset','function_count')]+[('data',c.c_ubyte*2712)]
class Library:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True);self.dll=c.CDLL(str(self.path))
        self.emit=self.dll.departure_image_test_build;self.emit.argtypes=[c.POINTER(Addresses),c.POINTER(Image)];self.emit.restype=c.c_int
        self.prepare=self.dll.departure_image_test_prepare;self.prepare.argtypes=[c.POINTER(c.c_uint32)];self.prepare.restype=c.c_int
    def departure_candidate(self,addresses,reference):
        out=Image();rc=self.emit(Addresses(**addresses),out)
        if rc or bytes(out.data[:out.bytes])!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset,out.function_count)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset'],reference['function_count']):
            raise RuntimeError('C++ departure differs from pinned reference: '+str(rc))
        return {**reference['candidate'],'code_hex':bytes(out.data[:out.code_bytes]).hex()}
