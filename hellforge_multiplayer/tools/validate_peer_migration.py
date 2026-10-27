"""One owned-bank migration/rollback/fresh-retry flow; no game or receipts."""
import argparse
import ctypes
import subprocess
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zig',type=Path,required=True);parser.add_argument('--upstream',type=Path,required=True)
    args=parser.parse_args();project=Path(__file__).resolve().parents[1];library=project/'build/peer_migration_test.dll'
    library.parent.mkdir(exist_ok=True)
    names=('roster_migration','multiplayer_commit','roster_owner','native_roster','component33_resources','component33_consumers')
    command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
             '-Wno-missing-field-initializers','-I',args.upstream.resolve()/'native/mod-sdk','-I',project/'mod/src','-shared',
             *(project/'mod/src'/f'ep_{name}.cpp' for name in names),project/'tests/peer_migration_dll.cpp','-o',library]
    result=subprocess.run(list(map(str,command)),capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    dll=ctypes.CDLL(str(library));flow=dll.peer_migration_flow;flow.argtypes=[];flow.restype=ctypes.c_uint
    total=flow()
    print(f'PASS one peer migration/rollback/fresh-retry flow, {total} SDK bytes on successful attempt within shared 64 KiB limit; full records and permuted indices preserved, new slots clear, early aliases rejected. Group/component services are fixtures. Actual game/activation/multiplayer unverified; no game access.')


if __name__=='__main__':main()
