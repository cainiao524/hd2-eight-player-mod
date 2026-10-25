"""Own test-library bridge; never load this in a game or execute emitted code."""
import ctypes as c
from pathlib import Path

class Addresses(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('game_base','code_address','roster_address','property_address','reject_address')]

class Image(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('bytes','code_bytes','unwind_offset','table_offset')]+[('data',c.c_ubyte*708)]

class GateImage(c.Structure):
    _fields_=[('bytes',c.c_uint32),('table_offset',c.c_uint32),('data',c.c_ubyte*756)]

class GetterAddresses(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('game_base','code_address','roster_address','storage_address','reject_address')]

class InsertAddresses(c.Structure):
    _fields_=[(name,c.c_uint64) for name in ('game_base','code_address','roster_address','storage_address','move_code_address','reject_address')]

class RemoveImage(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('bytes','code_bytes','unwind_offset','table_offset')]+[('data',c.c_ubyte*776)]

class ClassifyImage(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('bytes','code_bytes','unwind_offset','table_offset')]+[('data',c.c_ubyte*2768)]

class Library:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        self.dll=c.CDLL(str(self.path))
        self.build=self.dll.property_image_test_build
        self.build.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image)]; self.build.restype=c.c_int
        self.prepare=self.dll.property_image_test_prepare
        self.prepare.argtypes=[c.c_uint32,c.POINTER(Addresses),c.POINTER(Image),c.POINTER(c.c_uint32)]; self.prepare.restype=c.c_int
        self.gate=self.dll.property_image_test_gate
        self.gate.argtypes=[c.c_uint32,c.POINTER(Addresses),c.c_uint64,c.c_uint64,c.POINTER(GateImage)]; self.gate.restype=c.c_int
        self.getter=self.dll.getter_image_test_build
        self.getter.argtypes=[c.POINTER(GetterAddresses),c.POINTER(Image)];self.getter.restype=c.c_int
        self.mover=self.dll.mover_image_test_build
        self.mover.argtypes=[c.POINTER(GetterAddresses),c.POINTER(Image)];self.mover.restype=c.c_int
        self.insert=self.dll.insert_image_test_build
        self.insert.argtypes=[c.c_uint32,c.POINTER(InsertAddresses),c.POINTER(Image)];self.insert.restype=c.c_int
        self.insert_prepare=self.dll.insert_image_test_prepare
        self.insert_prepare.argtypes=[c.c_uint32,c.POINTER(InsertAddresses),c.POINTER(Image),c.POINTER(c.c_uint32)];self.insert_prepare.restype=c.c_int
        self.remove=self.dll.remove_image_test_build
        self.remove.argtypes=[c.c_uint32,c.POINTER(InsertAddresses),c.POINTER(RemoveImage)];self.remove.restype=c.c_int
        self.remove_prepare=self.dll.remove_image_test_prepare
        self.remove_prepare.argtypes=[c.c_uint32,c.POINTER(InsertAddresses),c.POINTER(RemoveImage),c.POINTER(c.c_uint32)];self.remove_prepare.restype=c.c_int
        self.classify=self.dll.classify_image_test_build
        self.classify.argtypes=[c.c_uint32,c.POINTER(GetterAddresses),c.POINTER(ClassifyImage)];self.classify.restype=c.c_int
        self.classify_prepare=self.dll.classify_image_test_prepare
        self.classify_prepare.argtypes=[c.c_uint32,c.POINTER(GetterAddresses),c.POINTER(ClassifyImage),c.POINTER(c.c_uint32)];self.classify_prepare.restype=c.c_int
        self.getter_gate=self.dll.getter_image_test_gate
        self.getter_gate.argtypes=[c.POINTER(GetterAddresses),c.c_uint64,c.c_uint64,c.POINTER(GateImage)];self.getter_gate.restype=c.c_int

    def classify_candidate(self,addresses,reference):
        kinds=('enter','leave');out=ClassifyImage()
        result=self.classify(kinds.index(addresses['kind'])+1,GetterAddresses(**{k:v for k,v in addresses.items() if k!='kind'}),out)
        if result:raise RuntimeError('Native classification generation failed: '+str(result))
        if bytes(out.data[:out.bytes])!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset']):
            raise RuntimeError('C++ classification image differs from pinned reference')
        return {**reference['candidate'],'code_hex':bytes(out.data[:out.code_bytes]).hex()}

    def remove_candidate(self,addresses,reference):
        kinds=('legacy','registered');out=RemoveImage()
        result=self.remove(kinds.index(addresses['kind'])+1,InsertAddresses(**{k:v for k,v in addresses.items() if k!='kind'}),out)
        if result:raise RuntimeError('Native removal generation failed: '+str(result))
        if bytes(out.data[:out.bytes])!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset']):
            raise RuntimeError('C++ removal image differs from pinned reference')
        return {**reference['candidate'],'code_hex':bytes(out.data[:out.code_bytes]).hex()}

    def insert_candidate(self,addresses,reference):
        kinds=('dense_legacy','append_legacy','append_registered','dense_registered')
        out=Image();result=self.insert(kinds.index(addresses['kind'])+1,InsertAddresses(**{k:v for k,v in addresses.items() if k!='kind'}),out)
        if result:raise RuntimeError('Native insertion generation failed: '+str(result))
        if bytes(out.data[:out.bytes])!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset']):
            raise RuntimeError('C++ insertion image differs from pinned reference')
        return {**reference['candidate'],'code_hex':bytes(out.data[:out.code_bytes]).hex()}

    def mover_candidate(self,addresses,reference):
        out=Image();result=self.mover(GetterAddresses(**addresses),out)
        if result: raise RuntimeError("Native mover generation failed: "+str(result))
        if bytes(out.data[:out.bytes])!=reference["image"] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference["candidate"]["size_bytes"],reference["unwind_offset"],reference["table_offset"]):
            raise RuntimeError("C++ mover image differs from pinned reference")
        return {**reference["candidate"],"code_hex":bytes(out.data[:out.code_bytes]).hex()}

    def getter_candidate(self,addresses,reference):
        out=Image();result=self.getter(GetterAddresses(**addresses),out)
        if result: raise RuntimeError('Native getter generation failed: '+str(result))
        if bytes(out.data[:out.bytes])!=reference['image'] or (out.code_bytes,out.unwind_offset,out.table_offset)!=(reference['candidate']['size_bytes'],reference['unwind_offset'],reference['table_offset']):
            raise RuntimeError('C++ getter image differs from pinned reference')
        return {**reference['candidate'],'code_hex':bytes(out.data[:out.code_bytes]).hex()}

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
