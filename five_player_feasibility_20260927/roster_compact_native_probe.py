"""Reproduce the saved roster compact flow in synthetic, original four-slot memory.

An investigation of the claimed no-loss property, not a passing candidate test.
Executes original captured x64 in Unicorn, including mover/map helpers, with no
game process access or host-native execution. No helper is replaced by a stub.
"""
from __future__ import annotations
import argparse,hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'eight_player_candidate_20260927/.native-test-deps'),
             str(HERE.parent/'research_handoff_20260927/indirect')]
import unicorn
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn import x86_const as xr
from inspect_capture import Image,EXPECTED
GAME=0x7FF600000000
S,BUCKETS,ENTITIES,FLAGS=0x18200100400,0x18200200100,0x18200300000,0x18200400000
STACK,RSP,STOP=0x182F0000000,0x182F0008008,GAME+0x100F0000
LAYOUT=[('pointer',0xE8,8),('primary',0x108,0x70),('auxiliary',0x2C8,0x38),('property',0x3A8,0x20)]
SEEDS={n:0xABCDEF0100000000+i for i,n in enumerate(('rbx','rbp','rsi','rdi','r12','r13','r14','r15'))}
BODIES={
    0x60CC70:(0x60CE76,'37b79524a6ed1b43d8ce3244c66288a0b921e1ea5766ba64fd7e0b186c41e452'),
    0x60C410:(0x60C5BE,'b977816b8863034f0c247d0ee58779ab0f7d87cdb54eaa49ebfcdd5cab95434b'),
    0x60CA80:(0x60CB9F,'974935cec813b3ce3f8d62cff1c7f46b17bb306f5bce020e8dde6fdccfc01e4f'),
    0x60CBA0:(0x60CC6B,'57a8d7f5d1dbb83f3a9a80918f740ce2065dfc1ac09b10952189b3693a7132c8'),
    0x172F790:(0x172F7FE,'57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375'),
}
sha=lambda b:hashlib.sha256(b).hexdigest()
u32=lambda n:struct.pack('<I',n)
u64=lambda n:struct.pack('<Q',n)
reg=lambda n:getattr(xr,'UC_X86_REG_'+n.upper())


class Fixture:
    def __init__(self,code,t,d,p):
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64);self.pages=set();self.events=[];self.writes=[];self.trace=[];self.runs=[]
        for a,n in [(S-0x80,0x600),(BUCKETS,0x100),(ENTITIES,0x1000),(FLAGS,1),(STACK,0x10000),
                    (GAME+0x3326468,8),(STOP,1)]:self.map(a,n)
        self.write(STOP,b'\xcc');self.write(GAME+0x3326468,u64(S));self.write(FLAGS,b'\0')
        for a,blob in code.items():self.map(GAME+a,len(blob));self.write(GAME+a,blob)
        for off,value in ((0x80,t),(0x84,d),(0x88,p),(0x7C,4)):self.write(S+off,u32(value))
        self.write(S+0xD0,u64(BUCKETS));self.write(S+0xD8,u32(8));self.write(S+0xDC,u32(0));self.write(S+0xE0,u32(1))
        for i in range(8):self.write(BUCKETS+i*8,u32(0)+u32(0xFFFFFFFF))
        for i in range(4):
            entity=ENTITIES+i*0x40;entity_id=11+i*8;self.write(entity+8,u32(entity_id))
            if i<t:self.write(BUCKETS+((3+i)&7)*8,u32(entity_id)+u32(i))
            for k,(name,off,stride)in enumerate(LAYOUT):
                value=u64(entity)if name=='pointer'else bytes((i*53+j*7+k*61)&255 for j in range(stride))
                self.write(S+off+i*stride,value)
        self.outcome=None
        self.uc.hook_add(UC_HOOK_CODE,self.on_code)
        self.uc.hook_add(UC_HOOK_MEM_WRITE,self.on_write)
    def map(self,a,n):
        for p in range(a&~0xFFF,(a+n+0xFFF)&~0xFFF,0x1000):
            if p not in self.pages:self.uc.mem_map(p,0x1000);self.uc.mem_write(p,b'\xa5'*0x1000);self.pages.add(p)
    def write(self,a,b):self.uc.mem_write(a,b)
    def read(self,a,n):return bytes(self.uc.mem_read(a,n))
    def count(self,off):return struct.unpack('<I',self.read(S+off,4))[0]
    def records(self):return [[self.read(S+off+i*stride,stride)for name,off,stride in LAYOUT]for i in range(4)]
    def entity_id(self,record):return struct.unpack('<I',self.read(struct.unpack('<Q',record[0])[0]+8,4))[0]
    def ids(self):return [self.entity_id(v)for v in self.records()[:self.count(0x80)]]
    def table(self):return [struct.unpack('<II',self.read(BUCKETS+i*8,8))for i in range(8)]
    def snapshot(self):return {p:self.read(p,0x1000)for p in self.pages if not STACK<=p<STACK+0x10000}
    def on_write(self,uc,access,address,size,value,data):
        if not STACK<=address<STACK+0x10000:
            self.writes.append({'rva':hex(uc.reg_read(reg('rip'))-GAME),'address':hex(address),'size':size,'value_low64':hex(value&((1<<64)-1))})
    def on_code(self,uc,address,size,data):
        self.trace.append(address)
        if address==STOP:self.outcome='return';uc.emu_stop();return
        rva=address-GAME
        if rva in (0x60CCB5,0x60CE18,0x60CE24,0x60C410):
            e={'rva':hex(rva),'ids':self.ids(),'P':self.count(0x88),'D':self.count(0x84),'T':self.count(0x80)}
            if rva in (0x60CE24,0x60C410):e.update(destination=uc.reg_read(reg('edx')),source=uc.reg_read(reg('r8d')))
            e['map']={str(key):value for key,value in self.table()if key}
            self.events.append(e)
    def run(self,rva,arguments):
        self.events=[];self.writes=[];self.trace=[];self.outcome=None
        for n,v in SEEDS.items():self.uc.reg_write(reg(n),v)
        for i in range(6,16):self.uc.reg_write(reg('xmm'+str(i)),(0x102030405060708+i)*(1+(1<<64)))
        self.write(RSP,u64(STOP));self.uc.reg_write(reg('rsp'),RSP)
        for n,v in arguments.items():self.uc.reg_write(reg(n),v)
        self.uc.emu_start(GAME+rva,0,count=5000)
        assert self.outcome=='return'
        assert self.uc.reg_read(reg('rsp'))==RSP+8
        assert all(self.uc.reg_read(reg(n))==v for n,v in SEEDS.items())
        assert all(self.uc.reg_read(reg('xmm'+str(i)))==(0x102030405060708+i)*(1+(1<<64))for i in range(6,16))
        self.runs.append({'entry_rva':hex(rva),'instructions':len(self.trace),'outcome':self.outcome})


def compact_case(f):
    t,d,p=(f.count(off)for off in (0x80,0x84,0x88))
    before_records=f.records();before_table=f.table();before_pages=f.snapshot();before_ids=f.ids()
    assert len(set(before_ids))==t
    assert all(before_ids[value]==key for key,value in before_table if key)
    # This order model verifies correspondence to the observed instructions;
    # the no-loss/unique-ID/map-bijection checks below are a separate property.
    expected_records=[list(v)for v in before_records];expected_table=list(before_table);q=p
    def set_map(entity,ordinal):
        k=next(i for i,(key,value)in enumerate(expected_table)if key==entity)
        expected_table[k]=(entity,ordinal)
    for source in range(d,t):
        if q<source:
            expected_records[source]=list(expected_records[q]);set_map(f.entity_id(expected_records[source]),source)
        if q!=source:
            expected_records[q]=list(expected_records[source]);set_map(f.entity_id(expected_records[q]),q)
        q+=1
    changes=[]
    for i,record in enumerate(expected_records):
        for (name,off,stride),blob in zip(LAYOUT,record):changes.append((S+off+i*stride,blob))
    for i,(key,value)in enumerate(expected_table):changes.append((BUCKETS+i*8,u32(key)+u32(value)))
    changes.extend([(S+0x84,u32(t)),(S+0x88,u32(q))])
    expected={a:bytearray(v)for a,v in before_pages.items()}
    for a,blob in changes:
        for i,v in enumerate(blob):expected[(a+i)&~0xFFF][(a+i)&0xFFF]=v
    f.run(0x60CC70,{'rcx':S});after=f.snapshot()
    assert after=={a:bytes(v)for a,v in expected.items()},'unexpected bytes outside finite order model'
    after_ids=f.ids();lost=sorted(set(before_ids)-set(after_ids));map_after={key:value for key,value in f.table()if key}
    bad_map={str(key):{'ordinal':value,'actual_id':after_ids[value]if value<t else None}
             for key,value in map_after.items()if value>=t or after_ids[value]!=key}
    preserves=(len(set(after_ids))==t and not lost and not bad_map)
    # This assertion validates the inferred boundary; it does not assert that
    # this body is safe over the tested count domain.
    assert preserves==(not(p<d<t))
    return {'input_counts':{'T':t,'D':d,'P':p},'before_ids':before_ids,'after_ids':after_ids,
            'after_counts':{'T':f.count(0x80),'D':f.count(0x84),'P':f.count(0x88)},
            'all_original_ids_preserved':not lost,'unique_records':len(set(after_ids))==t,
            'map_bijection_preserved':not bad_map,'no_loss_property_holds':preserves,
            'lost_ids':lost,'invalid_map_entries':bad_map,'map_after':{str(k):v for k,v in map_after.items()},
            'exact_nonstack_pages_match_order_model':True,'nonvolatile_and_stack_restored':True,
            'original_instruction_run':f.runs[-1],
            'before_record_sha256':[[sha(b)for b in record]for record in before_records[:t]],
            'after_record_sha256':[[sha(b)for b in record]for record in f.records()[:t]],
            'events':f.events,'writes':f.writes}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();assert not args.output.exists(),'refusing to overwrite output'
    image=Image(args.capture);code={}
    for start,(end,pin)in BODIES.items():
        code[start]=image.read(start,end-start);assert sha(code[start])==pin
    cases=[]
    for t in range(5):
        for d in range(t+1):
            for p in range(d+1):cases.append(compact_case(Fixture(code,t,d,p)))
    losses=[c for c in cases if not c['no_loss_property_holds']]
    assert len(cases)==35 and len(losses)==10
    minimum=next(c for c in cases if c['input_counts']=={'T':2,'D':1,'P':0})
    assert minimum['before_ids']==[11,19]and minimum['after_ids']==[11,11]
    assert minimum['map_after']=={'11':0,'19':1}
    # Synthetic call ordering only: its reachability in the real dispatch is
    # not implied. All three calls execute the original saved bodies.
    f=Fixture(code,0,0,0)
    f.run(0x60CA80,{'rcx':0,'rdx':ENTITIES,'r8':FLAGS})
    assert (f.count(0x80),f.count(0x84),f.count(0x88))==(1,1,0)and f.ids()==[11]
    f.run(0x60CBA0,{'rcx':0,'rdx':ENTITIES+0x40})
    assert (f.count(0x80),f.count(0x84),f.count(0x88))==(2,1,0)and f.ids()==[11,19]
    chain=compact_case(f);assert not chain['no_loss_property_holds']
    result={'investigation_status':'confirmed_counterexample','candidate_shippable':False,
            'program_sha256':sha(Path(__file__).read_bytes()),'source_capture_sha256':EXPECTED,
            'original_body_sha256':{hex(k):v[1]for k,v in BODIES.items()},
            'python_version':sys.version,'unicorn_version':unicorn.__version__,
            'synthetic_original_four_slot_memory':True,'game_process_accessed':False,'host_native_code_executed':False,
            'helpers_stubbed':False,'real_dispatch_reachability_proven':False,'candidate_emitted':False,
            'count_domain_cases':35,'counterexample_cases':10,'property_preserved_cases':25,
            'top_level_function_executions':38,'minimal_counterexample':minimum,'cases':cases,
            'synthetic_dense_append_compact_chain':{'calls':f.runs,'result':chain},
            'decision':'Do not implement or certify a lossless compactor by simply redirecting this body over P<=D<=T.',
            'limits':['Original four-slot layout only; no eight-player candidate or account test',
                      'Input ID/map consistency is established in synthetic memory, not as a reachable game state',
                      'The order model verifies emulator correspondence, not logical correctness',
                      'No claim that the shipping game has a reachable bug; stronger caller/lifecycle preconditions may exist',
                      'Real pending-tail identity/ownership and caller guarantees are needed before choosing a replacement or restriction']}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k]for k in ('investigation_status','count_domain_cases','counterexample_cases','property_preserved_cases','top_level_function_executions','candidate_emitted')}))


if __name__=='__main__':main()
