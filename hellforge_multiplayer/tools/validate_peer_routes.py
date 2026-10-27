"""One group/owner/peer-route lifecycle in owned memory; no game access.

The SDK hook callback is a recording fixture. Actual generated lookup/contains
execute on our allocations; OLD insert stubs check six/seven-argument transport.
No full regression, receipt, fingerprint, package or game installation.
"""
import argparse
import ctypes
import subprocess
import struct
import sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT.parent/'eight_player_candidate_20260927/.native-test-deps'))


def update_window(dll):
    """Execute the real relocated inline lookup and its native continuations.

    The rest of the update/native services are not executed or simulated as
    successful gameplay. This is part of the single owned routing flow below.
    """
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
    from unicorn import x86_const as x
    from generate_client_update import build
    from generate_loadout_lifecycle import Capture
    from validate_client_disconnect import Addresses,need

    class UpdateImage(ctypes.Structure):
        _fields_=[(n,ctypes.c_uint32) for n in ('bytes','table_offset','function_count','handler_offset','body_offset')]+[('data',ctypes.c_uint8*8192)]
    emit=dll.client_update_emit;emit.argtypes=[ctypes.POINTER(Addresses),ctypes.POINTER(UpdateImage)];emit.restype=ctypes.c_int
    a=Addresses(0x140000000,0x180000000,0x2100162c8,0x220000000,0x1c0000000,8,0);out=UpdateImage()
    need(emit(ctypes.byref(a),ctypes.byref(out))==0,'Update emission')
    plan=build();mapping=plan['mapping'];capture=Capture()
    store=next(capture.md.disasm(capture.read(0x1083ca4,15),0x1083ca4))
    finish=a.code+mapping[store.address+store.size];owner=a.client-0x162c8;host=owner+0x159b0
    for count,index,peer,foreign in ((8,2,0x107,False),(8,2,0x999,False),(8,7,0x107,False),(9,2,0x107,False),(8,2,0x107,True)):
        u=Uc(UC_ARCH_X86,UC_MODE_64)
        for address,size in ((a.code,8192),(owner,0x30000),(a.peers,4096),(a.reject,4096),(0x230000000,4096)):
            u.mem_map(address,size)
        u.mem_write(a.code,bytes(out.data));u.mem_write(host,struct.pack('<Q',owner+(0x3000 if foreign else 0)))
        u.mem_write(a.client+0xc8,struct.pack('<I',count));u.mem_write(a.client+0xd0,b'\xa5'*128)
        u.mem_write(host+0x34,struct.pack('<I',0xdeadbeef));u.mem_write(host+0x100,b'\x5a'*12)
        for i in range(8):
            row=bytearray(32);struct.pack_into('<Q',row,0,0x100+i);struct.pack_into('<I',row,0x14,index if i==7 else i)
            u.mem_write(a.peers+32*i,bytes(row))
        u.reg_write(x.UC_X86_REG_RBX,host);u.reg_write(x.UC_X86_REG_RCX,0);u.reg_write(x.UC_X86_REG_R10,peer)
        u.reg_write(x.UC_X86_REG_R11,0);u.reg_write(x.UC_X86_REG_RSP,0x230000800)
        rejected=[]
        def hook(cpu,address,size,data):
            if address==a.reject:rejected.append(True);cpu.emu_stop()
        u.hook_add(UC_HOOK_CODE,hook)
        u.emu_start(a.code+mapping[0x1083c37],finish,count=500)
        bad=foreign or count>8 or index>=4
        need(bool(rejected)==bad,'Update reject boundary')
        if bad:
            need(u.mem_read(host+0x34,4)==struct.pack('<I',0xdeadbeef) and u.mem_read(host+0x100,12)==b'\x5a'*12,
                 'Rejected update changed host index/flags')
        else:
            selected=index if peer==0x107 else 0;flags=bytearray(4);flags[selected]=1
            need(u.reg_read(x.UC_X86_REG_RIP)==finish and u.reg_read(x.UC_X86_REG_R8)==owner and u.reg_read(x.UC_X86_REG_R11)==0,
                 'Update continuation/live owner registers')
            need(u.mem_read(host+0x34,4)==struct.pack('<I',selected) and u.mem_read(host+0x100,12)==bytes(flags)+b'\x5a'*8,
                 'Ordinal/index mapping or host flag extent')
            for offset in (0x162d8,0x16300,0x16348):need(u.mem_read(owner+offset,4)==bytes(4),'Native owner reset')
        need(u.mem_read(a.client+0xd0,128)==b'\xa5'*128,'Old inline bank was modified')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True)
    p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/peer_routes_test.dll';library.parent.mkdir(exist_ok=True)
    names=('player_join_image','client_peers','client_update','client_disconnect','session_code','roster_group','roster_gate',
           'roster_call','roster_owner','native_roster','property_gate','property_image','getter_image','mover_image',
           'insert_image','remove_image','classify_image','registry_image','departure_image','arrival_image')
    sources=[PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in names]+[PROJECT/'tests/peer_routes_dll.cpp']
    command=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
             '-Wno-missing-field-initializers','-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src',
             '-shared',*sources,'-o',library]
    result=subprocess.run(list(map(str,command)),capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    dll=ctypes.CDLL(str(library));flow=dll.peer_routes_flow;flow.argtypes=[];flow.restype=ctypes.c_int
    result=flow()
    if result:raise RuntimeError(f'Peer routing flow failed at C++ line {result}')
    update_window(dll)
    print('PASS one peer/update routing flow: real group prepare/cancel/retain, 27 recorded hooks, '
          'owned update route, Windows chained unwind, actual inline lookup/continuation and host bound; '
          'game_access=false. SDK hooks/native services are fixtures; full update/runtime/UI/multiplayer unverified.')


if __name__=='__main__':main()
