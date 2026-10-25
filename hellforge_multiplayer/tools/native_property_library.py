"""Own test-library bridge; never load this in a game or execute emitted code."""
import ctypes as c
from pathlib import Path

class Addresses(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('game_base','code_address','roster_address','property_address','reject_address')]

class Image(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('bytes','code_bytes','unwind_offset','table_offset')]+[('data',c.c_ubyte*708)]

class Library:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        self.dll=c.CDLL(str(self.path))
        self.build=self.dll.property_image_test_build
        self.build.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)]; self.build.restype=c.c_int
        self.prepare=self.dll.property_image_test_prepare
        self.prepare.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image),c.POINTER(c.c_uint32)]; self.prepare.restype=c.c_int

    def candidate(self,kind,addresses,reference):
        out=Image(); result=self.build(kind,Addresses(**addresses),out)
        if result: raise RuntimeError('Native property generation failed: '+str(result))
        image=bytes(out.data[:out.bytes])
        if image!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset']):
            raise RuntimeError('C++ property image differs from pinned reference')
        # Emulator consumes the native-produced bytes; metadata comes from the
        # independent reference, checked above before using its instruction map.
        candidate=dict(reference['candidate']); candidate['code_hex']=image[:out.code_bytes].hex()
        return candidate
