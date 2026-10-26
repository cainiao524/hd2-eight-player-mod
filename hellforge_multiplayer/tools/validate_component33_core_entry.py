"""Directly related core/entry tests in owned Windows memory. No receipts."""
import argparse,ctypes as c,json,struct,subprocess,sys
from pathlib import Path
import native_component33_image as n
import validate_component33_leave_entry as leave
PROJECT=n.PROJECT


def saved_maps():
    """Copy saved hash helpers with their original captured unwind records.

    Only these saved JSON bytes enter the test page; no installed game read,
    engine callbacks, generated fingerprint or binary receipt is involved.
    """
    p=json.loads((PROJECT/'native-component33.lock.json').read_bytes());base=0x1720000
    # Rows in the same capture's exception table: 172F790..172F7FE at
    # unwind RVA 2567A18; 172F8A0..172F9A3 at 2567A5C. Neither is chained.
    metadata={'map_insert':'010f06000f7403000a64020005340100',
              'map_delete':'0175090075e403006c5402000b6405000b3404000b700000'}
    blob=bytearray(65536);at=0x1000;rows=[]
    for key in ('map_insert','map_delete'):
        f=p['functions'][key];start=f['start']-base;raw=bytes.fromhex(f['body_hex'])
        blob[start:start+len(raw)]=raw
        raw=bytes.fromhex(metadata[key]);blob[at:at+len(raw)]=raw;rows.append((f,at));at+=len(raw)
    table=(at+3)&~3
    for i,(row,off) in enumerate(rows):struct.pack_into('<III',blob,table+i*12,row['start']-base,row['end']-base,off)
    return bytes(blob),table,len(rows)


def worker(library,mode):
    dll=c.CDLL(str(library));fn=dll.c33_core_entries_test
    fn.argtypes=[c.c_uint,c.c_void_p,c.c_uint,c.c_uint,c.c_uint];fn.restype=c.c_uint
    raw,table,count=saved_maps();buffer=c.create_string_buffer(raw)
    return fn(mode,buffer,len(raw),table,count)


def main():
    ap=argparse.ArgumentParser()
    for key in ('zig','upstream','library'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--worker',type=int);ap.add_argument('--group',default='core');a=ap.parse_args()
    library=(a.library or PROJECT/'build/component33_core_entry_test.dll').resolve()
    if a.worker is not None:
        checks=worker(library,a.worker) if a.group=='core' else leave.refresh.reset.update.entries.native.worker(library,a.group,a.worker)
        print(json.dumps(dict(checks=checks)));return
    if a.zig:
        if not a.upstream:ap.error('--upstream required')
        cmd=[a.zig.resolve(),'c++','-std=c++17','-target','x86_64-windows-gnu','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-missing-field-initializers',
            '-I',a.upstream.resolve()/'native/mod-sdk','-I',PROJECT/'mod/src','-shared',*(PROJECT/s for s in leave.refresh.reset.update.entries.native.admission.SOURCES),
            PROJECT/'mod/src/ep_component33_resource_provider.cpp',PROJECT/'tests/component33_core_entry_dll.cpp','-o',library]
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True);n.need(p.returncode==0,p.stdout+p.stderr)
    checks=0
    for group,count in (('core',19),('whole_leave',30),('whole_refresh',25),('whole_reset',24),('whole_update',18),('update_entry',10),('entries',29)):
        for mode in range(count):
            p=subprocess.run([sys.executable,'-B',__file__,'--library',str(library),'--worker',str(mode),'--group',group],capture_output=True,text=True,timeout=30)
            n.need(p.returncode==0,f'{group}/{mode}: '+p.stdout+p.stderr);checks+=json.loads(p.stdout)['checks']
    print(json.dumps(dict(passed=True,core_scenarios=19,core_abi_entries=14,related_entry_regressions=136,checks=checks,game_access=False)))
if __name__=='__main__':main()
