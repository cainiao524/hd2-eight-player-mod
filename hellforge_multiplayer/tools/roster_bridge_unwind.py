"""Emit every instruction boundary of our compiled DLL's two assembly bridges.

The Windows C harness applies RtlVirtualUnwind to these states and verifies the
actual PE registrations. Only our own locally compiled test DLL is loaded.
"""
import argparse,ctypes as c,json,struct
from pathlib import Path
from verify_roster_call_abi import cs,need
class RuntimeFunction(c.Structure):
    _fields_=[('begin',c.c_uint32),('end',c.c_uint32),('unwind',c.c_uint32)]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    library=c.CDLL(str(a.library.resolve()));get=library.roster_call_test_api;get.restype=c.c_void_p
    api=c.cast(get(),c.POINTER(c.c_void_p));entry=c.CFUNCTYPE(c.c_size_t)(api[14])()
    lookup=c.WinDLL('kernel32').RtlLookupFunctionEntry;lookup.argtypes=[c.c_uint64,c.POINTER(c.c_uint64),c.c_void_p];lookup.restype=c.POINTER(RuntimeFunction)
    md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64);md.detail=True;result=bytearray(b'EPBRUW1\0'+struct.pack('<I',2));total=0
    for index,address in enumerate((entry,api[13])):
        base=c.c_uint64();row=lookup(address,c.byref(base),None);need(bool(row),'missing bridge unwind registration')
        need(address==base.value+row.contents.begin,'bridge entry mismatch');code=c.string_at(address,row.contents.end-row.contents.begin)
        instructions=list(md.disasm(code,0));need(sum(i.size for i in instructions)==len(code),'bridge decode incomplete')
        records=[];delta=0;rbx_frame=0;branches=[]
        for i in instructions:
            records.append((i.address,delta,rbx_frame));text=i.op_str
            if i.mnemonic=='sub' and text.startswith('rsp, '):delta-=i.operands[1].imm
            elif i.mnemonic=='add' and text.startswith('rsp, '):delta+=i.operands[1].imm
            elif i.mnemonic=='push':need(text=='rbx','unexpected bridge push');delta-=8
            elif i.mnemonic=='pop':need(text=='rbx','unexpected bridge pop');delta+=8;rbx_frame=0
            elif i.mnemonic=='mov' and text=='rbx, rcx':rbx_frame=1
            elif i.mnemonic=='ret':need(delta==0 and not rbx_frame,'bridge return did not restore frame')
            elif i.group(cs.CS_GRP_CALL):pass
            else:need(not {'rsp','rbx'}&{i.reg_name(r) for r in i.regs_access()[1]},'unmodelled bridge stack/register write')
            if i.group(cs.CS_GRP_JUMP):branches.append((i.operands[0].imm,delta,rbx_frame))
        states={r[0]:r[1:] for r in records}
        for target,d,f in branches:need(states.get(target)==(d,f),'branch changes stack model')
        result+=struct.pack('<III',index,len(code),len(records))+code
        result+=b''.join(struct.pack('<IiI',*r) for r in records);total+=len(records)
    a.output.write_bytes(result);print(json.dumps({'functions':2,'instruction_contexts':total,'game_access':False}))
if __name__=='__main__':main()
