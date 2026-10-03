"""Bounded read-only scan for fixed-build receive registration values."""
from __future__ import annotations
import argparse,ctypes as C,hashlib,json,struct,sys
from datetime import datetime,timezone
from pathlib import Path
from ctypes import wintypes as W
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'tools'))
import interface_probe as base
PAGE=0x1000; READABLE={0x02,0x04,0x08,0x20,0x40,0x80}; MEM_COMMIT=0x1000; MEM_PRIVATE=0x20000
class MEMORY_BASIC_INFORMATION(C.Structure):
    _fields_=[('base',C.c_void_p),('allocation',C.c_void_p),('allocation_protect',W.DWORD),('partition',W.WORD),('size',C.c_size_t),('state',W.DWORD),('protect',W.DWORD),('kind',W.DWORD)]
STATIC_HASHES={0xBDE53653,0x3E3F525A,0x5DCD723A,0x19339CD6,0x36334D22,0x520227A4,0x068601A2}
def digest(x): return hashlib.sha256(x).hexdigest()
def main(pid:int,out:Path,limit:int,max_read:int):
    base.READ_BUDGET=max_read
    reader=base.WindowsReader(pid)
    try:
        executable=reader.executable(); modules=reader.modules(); selected=base.check_files(modules,executable); base.verify_loaded(reader,selected); game=int(selected['game.dll']['base'])
        patterns={
          'confirmed_peer_receiver_ptr':struct.pack('<Q',game+0x0BABA80),
          'confirmed_peer_insert_ptr':struct.pack('<Q',game+0x0B90B20),
          'platform_member_consumer_ptr':struct.pack('<Q',game+0x1093590),
          'platform_member_state_update_ptr':struct.pack('<Q',game+0x10937A0),
          'confirmed_peer_event_hash':struct.pack('<I',0x4804FCF4),
        }
        for i,v in enumerate(sorted(STATIC_HASHES)): patterns[f'static_registration_hash_{i}']=struct.pack('<I',v)
        k=reader.k; k.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t]; k.VirtualQueryEx.restype=C.c_size_t
        address=0x10000; consumed=regions=pages=0; hits=[]
        while address<0x800000000000 and consumed<limit:
            info=MEMORY_BASIC_INFORMATION(); size=k.VirtualQueryEx(reader.handle,C.c_void_p(address),C.byref(info),C.sizeof(info))
            if size!=C.sizeof(info) or not info.size: break
            start=int(info.base); end=start+int(info.size)
            if info.state==MEM_COMMIT and info.kind==MEM_PRIVATE and (info.protect&0xFF) in READABLE and not (info.protect&0x100):
                regions+=1; cursor=start
                while cursor<end and consumed<limit:
                    amount=min(PAGE,end-cursor,limit-consumed)
                    try: raw=reader.read(cursor,amount,executable=False)
                    except (ValueError,OSError): cursor+=amount; continue
                    consumed+=len(raw); pages+=1
                    for name,pat in patterns.items():
                        off=0
                        while True:
                            found=raw.find(pat,off)
                            if found<0: break
                            hits.append({'pattern':name,'address':hex(cursor+found),'region':hex(start),'offset':hex(found)})
                            off=found+1
                    cursor+=amount
            address=end
        result={'schema':'hd2_live_registration_state_scan_v1','build':base.BUILD,'pid':pid,'captured_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'authorized read-only bounded MEM_PRIVATE scan for fixed registration values; no calls, writes, hooks, injection or installation','pinned_images':selected,'patterns':{k:{'length':len(v),'sha256':digest(v)} for k,v in patterns.items()},'hits':hits,'scan_stats':{'private_regions':regions,'pages_read':pages,'memory_bytes_read':consumed,'limit_bytes':limit,'truncated':consumed>=limit},'read_only':True,'calls_made':False,'writes_made':False,'hooks_installed':False,'hash_to_selector_proven':False,'resolver_closed':False,'installable':False,'multiplayer_verified':False,'meaning':'Pointer/hash hits are observational only; no ownership or dispatch ABI is inferred.'}
        out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n'); return result
    finally: reader.close()
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--pid',type=int,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--limit-mib',type=int,default=128); ap.add_argument('--max-read-mib',type=int,default=160); a=ap.parse_args()
    r=main(a.pid,a.output,a.limit_mib*1024*1024,a.max_read_mib*1024*1024); counts={}
    for h in r['hits']: counts[h['pattern']]=counts.get(h['pattern'],0)+1
    print(json.dumps({'output':str(a.output),'hits':counts,'stats':r['scan_stats']},ensure_ascii=False))
