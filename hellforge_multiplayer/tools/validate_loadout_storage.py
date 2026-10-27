"""Run the selected owned storage flow only; no game access or receipt files."""
import argparse
import subprocess
from pathlib import Path
from generate_loadout_links import MODULES,PROJECT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path);p.add_argument('--upstream',type=Path)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--initialize-only',action='store_true',help='Owner/order/SEH flow with test-owned native entries; skip generated images')
    mode.add_argument('--commit-only',action='store_true',help='Joint coordinator/loadout flow; skip native image generation and other flows')
    p.add_argument('--executable',type=Path)
    args=p.parse_args()
    test='multiplayer_loadout_commit_smoke' if args.commit_only else 'loadout_initialization_smoke' if args.initialize_only else 'loadout_storage_smoke'
    args.executable=args.executable or PROJECT/'build'/(test+'.exe')
    if args.zig:
        if args.upstream is None:raise ValueError('--upstream required')
        args.executable.parent.mkdir(parents=True,exist_ok=True)
        command=[args.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror',
                 '-Wno-missing-field-initializers', # C-compatible roster module uses {0}.
                 '-I',args.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src']
        if not (args.initialize_only or args.commit_only):
            command += [PROJECT/'mod/src'/('ep_loadout_'+name+'.cpp') for name in MODULES]
            command += [PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in ('session_code','loadout_group')]
        command += [PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in ('loadout_storage','roster_owner','native_roster')]
        if args.commit_only:
            command += [PROJECT/'mod/src'/('ep_'+name+'.cpp') for name in ('multiplayer_commit','multiplayer_loadout_commit')]
        command += [PROJECT/'tests'/(test+'.cpp'),'-o',args.executable.resolve()]
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    result=subprocess.run([str(args.executable.resolve())],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    print(result.stdout.strip())


if __name__=='__main__':main()
