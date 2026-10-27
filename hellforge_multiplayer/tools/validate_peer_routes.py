"""One group/owner/peer-route lifecycle in owned memory; no game access.

The SDK hook callback is a recording fixture. Actual generated lookup/contains
execute on our allocations; OLD insert stubs check six/seven-argument transport.
No full regression, receipt, fingerprint, package or game installation.
"""
import argparse
import ctypes
import subprocess
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zig',type=Path,required=True)
    p.add_argument('--upstream',type=Path,required=True);a=p.parse_args()
    library=PROJECT/'build/peer_routes_test.dll';library.parent.mkdir(exist_ok=True)
    names=('player_join_image','client_peers','client_disconnect','session_code','roster_group','roster_gate',
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
    print('PASS one peer routing flow: real group prepare/cancel/retain, 26 recorded hooks, shared latch/barrier, '
          'OLD stack ABI, NEW generated lookup/contains, scoped pointer and quarantine; game_access=false. '
          'SDK hooks and engine services are fixtures; runtime/UI/multiplayer unverified.')


if __name__=='__main__':main()
