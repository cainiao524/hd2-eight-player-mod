"""Compile/run one owned loadout storage lifecycle smoke flow; no game access."""
import argparse
import subprocess
from pathlib import Path
from generate_loadout_links import MODULES,PROJECT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    p.add_argument('--executable',type=Path,default=PROJECT/'build/loadout_storage_smoke.exe')
    args=p.parse_args()
    if args.zig:
        if args.upstream is None:raise ValueError('--upstream required')
        args.executable.parent.mkdir(parents=True,exist_ok=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src']
        command += [PROJECT/'mod/src'/('ep_loadout_'+name+'.cpp') for name in MODULES]
        command += [PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in ('session_code','loadout_group','loadout_storage')]
        command += [PROJECT/'tests/loadout_storage_smoke.cpp','-o',args.executable.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    result=subprocess.run([str(args.executable.resolve())],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    print(result.stdout.strip())


if __name__=='__main__':main()
