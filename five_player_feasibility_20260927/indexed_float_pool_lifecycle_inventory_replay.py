"""Project direct constructor/destructor subobject visits from saved x64 bytes.

This is an address/control-flow projection, not game execution or an engine
resource emulator. Calls are bounded contracts; ignored SIMD writes are audited
against scalar reads. Eight-record scenarios are hypothetical address overrides
inside Python only, never binary patches.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image,EXPECTED,require,row
from capstone.x86 import X86_OP_IMM,X86_OP_MEM,X86_OP_REG

D=0x10000000
STACK=0x50000000
SIDE=0x40000000
CONTEXT_A=0x30000000
CONTEXT_B=0x20000000+0x6D30
SOURCE='indexed_float_subobjects_evidence.json'
SOURCE_SHA='5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54'
BOUNDS={0x142B990:0x142BEB3,0x142C9B0:0x142CB57}
PROJECTIONS={'construct':(0x142BA7B,0x142BE88),'cleanup':(0x142C9BF,0x142CB47)}
VOLATILE=['rax','rcx','rdx','r8','r9','r10','r11']


def sha(b):return hashlib.sha256(b).hexdigest()


def reg_info(s):
    names={'eax':('rax',32),'ebx':('rbx',32),'ecx':('rcx',32),'edx':('rdx',32),
      'esi':('rsi',32),'edi':('rdi',32),'ebp':('rbp',32),'esp':('rsp',32),
      'dil':('rdi',8),'bpl':('rbp',8),'sil':('rsi',8),'al':('rax',8)}
    if s in names:return names[s]
    if s.startswith('r') and s[-1:] in ('d','w','b') and s[1:-1].isdigit():
        return s[:-1],{'d':32,'w':16,'b':8}[s[-1]]
    return s,64


class Projection:
    def __init__(self,im,by,kind,records=4,relocated=False,fill=0):
        self.im,self.by,self.kind=im,by,kind
        self.records,self.relocated=records,relocated
        self.regs={'rbx':D,'rbp':CONTEXT_A,'rdi':0,'rcx':D,'rsp':STACK}
        self.regions=[(D,bytearray([fill])*0x90000),(STACK,bytearray(0x100)),
                      (SIDE,bytearray([fill])*(8*0x298))]
        self.visits=[];self.clears=[];self.node_initializers=[]
        self.scalar_reads=set();self.ignored_stores=set();self.branches=set();self.steps=0
        self.zf=self.cf=None

    def reg(self,s):
        name,bits=reg_info(s);require(name in self.regs,'unknown register '+s)
        return self.regs[name]&((1<<bits)-1)

    def setreg(self,s,value):
        name,bits=reg_info(s)
        if bits<32:
            require(name in self.regs,'partial write to unknown register')
            self.regs[name]=(self.regs[name]&~((1<<bits)-1))|(value&((1<<bits)-1))
        else:self.regs[name]=value&((1<<bits)-1)

    def address(self,i,o):
        m=o.mem;base=i.address+i.size if i.reg_name(m.base)=='rip' else (self.reg(i.reg_name(m.base)) if m.base else 0)
        idx=self.reg(i.reg_name(m.index)) if m.index else 0
        return (base+idx*m.scale+m.disp)&((1<<64)-1)

    def memory(self,a,size,value=None):
        if a==0x347CE90 and size==8 and value is None:return CONTEXT_B-0x6D30
        for base,b in self.regions:
            at=a-base
            if 0<=at and at+size<=len(b):
                if value is None:
                    self.scalar_reads.update(range(a,a+size))
                    return int.from_bytes(b[at:at+size],'little')
                b[at:at+size]=(value&((1<<(size*8))-1)).to_bytes(size,'little');return
        raise ValueError('out of projection memory '+hex(a))

    def read(self,i,o):
        if o.type==X86_OP_IMM:return o.imm
        if o.type==X86_OP_REG:return self.reg(i.reg_name(o.reg))
        require(o.type==X86_OP_MEM,'operand');return self.memory(self.address(i,o),o.size)

    def write(self,i,o,v):
        if o.type==X86_OP_REG:self.setreg(i.reg_name(o.reg),v)
        else:self.memory(self.address(i,o),o.size,v)

    def call(self,i):
        require(i.operands[0].type==X86_OP_IMM,'unknown indirect call')
        target=i.operands[0].imm;rcx=self.reg('rcx')
        if target==0x140C160:
            require(self.kind=='construct','wrong helper')
            args=dict(S=hex(rcx),context_A=hex(self.reg('rdx')),pool=hex(self.reg('r8')),
                      owner=hex(self.reg('r9')),context_B=hex(self.memory(STACK+0x20,8)))
            require(args['context_A']==hex(CONTEXT_A) and args['pool']==hex(D+0x36F8)
                    and args['owner']==hex(D) and args['context_B']==hex(CONTEXT_B),'constructor arguments')
            self.visits.append(dict(site=hex(i.address),**args))
        elif target==0x140C200:
            require(self.kind=='cleanup','wrong helper')
            self.visits.append(dict(site=hex(i.address),S=hex(rcx)))
        elif target==0x208AAA0:
            n=self.reg('r8');require(self.reg('rdx')==0 and n in (0x208,0x298),'clear contract')
            self.memory(rcx,n,0);self.clears.append(dict(site=hex(i.address),start=hex(rcx),size=n))
        elif target==0x1408FE0:
            self.node_initializers.append(hex(rcx))
        else:raise ValueError('unmodelled call '+hex(target))
        # These callees preserve nonvolatile GPRs (Windows x64 ABI). No assumptions
        # about volatile return values are needed by either projection.
        for r in VOLATILE:self.regs.pop(r,None)
        self.zf=self.cf=None

    def run(self):
        pc,end=PROJECTIONS[self.kind]
        while pc!=end:
            self.steps+=1;require(self.steps<30000,'projection step limit')
            require(pc in self.by,'unknown instruction');i=self.by[pc];m=i.mnemonic;ops=i.operands;nxt=pc+i.size
            # Hypothetical scenario controls, explicitly separated from raw bytes.
            if pc in (0x142BB94,0x142C9D5):
                self.write(i,ops[0],self.records)
            elif self.relocated and pc in (0x142BB8D,0x142C9CE):
                self.write(i,ops[0],SIDE+0xA0)
            elif m=='call':self.call(i)
            elif m in ('xorps','unpcklps','movsd','movss','movaps','movups'):
                # Only SIMD results/stores can be ignored. Audit at the end that
                # no ignored store supplies any scalar address or loop input.
                if ops and ops[0].type==X86_OP_MEM:
                    a=self.address(i,ops[0]);self.ignored_stores.update(range(a,a+ops[0].size))
                elif ops and ops[0].type==X86_OP_REG:
                    require(i.reg_name(ops[0].reg).startswith('xmm'),'ignored GPR write')
            elif m=='mov':self.write(i,ops[0],self.read(i,ops[1]))
            elif m=='lea':self.write(i,ops[0],self.address(i,ops[1]))
            elif m=='xor':
                require(ops[0].type==X86_OP_REG and ops[1].type==X86_OP_REG and ops[0].reg==ops[1].reg,'nonzero xor')
                self.write(i,ops[0],0);self.zf=True;self.cf=False
            elif m in ('add','sub','inc','dec','cmp'):
                a=self.read(i,ops[0]);b=1 if len(ops)==1 else self.read(i,ops[1]);bits=ops[0].size*8
                mask=(1<<bits)-1;b&=mask
                value=a+b if m in ('add','inc') else a-b
                self.zf=(value&mask)==0;self.cf=(a+b)>mask if m in ('add','inc') else a<b
                if m!='cmp':self.write(i,ops[0],value)
            elif m in ('jne','jb'):
                require(self.zf is not None and self.cf is not None,'unknown flags')
                take=not self.zf if m=='jne' else self.cf
                self.branches.add((hex(pc),take))
                if take:nxt=ops[0].imm
            elif m=='nop':pass
            else:raise ValueError('unhandled projection opcode '+m)
            pc=nxt
        require(not(self.scalar_reads&self.ignored_stores),'ignored SIMD store fed a scalar read')
        return self


def expected_visits(records,record_base):
    # Independent geometric specification of the direct member families.
    families=[('singleton_80da0',D+0x80DA0,1,0,[0]),
     ('player_records',record_base,records,0x298,[0x28,0xA0,0x118,0x1A0,0x218]),
     ('singletons_81888_81b88',D,1,0,[0x81888,0x81900,0x81988,0x81A00,0x81B10,0x81B88]),
     ('array_8b748',D+0x8B748,20,0x180,[0,0x78]),
     ('singletons_8d550_8d5c8',D,1,0,[0x8D550,0x8D5C8]),
     ('array_81c98',D+0x81C98,64,0x180,[0,0x78]),
     ('array_87da0',D+0x87DA0,5,0x180,[0,0x78]),
     ('singletons_88538_885b0',D,1,0,[0x88538,0x885B0]),
     ('array_886c0',D+0x886C0,32,0x180,[0,0x78,0xF0])]
    return [dict(name=name,base=hex(base),records=count,stride=hex(stride),offsets=[hex(x) for x in offsets],
                 members=[hex(base+n*stride+o) for n in range(count) for o in offsets])
            for name,base,count,stride,offsets in families]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--evidence',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();output=Path(args.output);require(not output.exists(),'refusing overwrite')
    prior_raw=(HERE/SOURCE).read_bytes();require(sha(prior_raw)==SOURCE_SHA,'prior changed');prior=json.loads(prior_raw)
    old={}
    def collect(x):
        if isinstance(x,dict):
            if all(k in x for k in ['rva','bytes','asm']):old[int(x['rva'],16)]=x
            for v in x.values():collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    collect(prior);im=Image(args.evidence);by={};spans={}
    for start,end in BOUNDS.items():
        fs=[f for f in im.functions if im.root(f[0])[0]==start]
        require(len(fs)==1 and fs[0][0]==start and fs[0][1]==end,'root fragments changed')
        raw=im.read(start,end-start);ins=list(im.md.disasm(raw,start));require(sum(i.size for i in ins)==len(raw),'decode')
        for i in ins:
            require(i.address in old and all(old[i.address].get(k)==v for k,v in row(i).items()),'prior bytes/asm changed')
            by[i.address]=i
        spans[hex(start)]=dict(start=hex(start),end_exclusive=hex(end),fragment=[hex(x) for x in fs[0]],
           sha256=sha(raw),instructions=[row(i) for i in ins])
    results={}
    for label,records,relocated in [('original',4,False),('eight_same_base_hypothetical',8,False),('eight_sidecar_hypothetical',8,True)]:
        pairs=[]
        for fill in (0,0xCC):
            ctor=Projection(im,by,'construct',records,relocated,fill).run()
            cleanup=Projection(im,by,'cleanup',records,relocated,fill).run()
            ca=[v['S'] for v in ctor.visits];cb=[v['S'] for v in cleanup.visits]
            spec=expected_visits(records,SIDE if relocated else D+0x80E18);wanted=[s for f in spec for s in f['members']]
            require(ca==cb==wanted,'constructor/cleanup/spec visit sequence mismatch')
            require(len(ca)==len(set(ca)),'duplicate S start')
            require(ctor.node_initializers==[hex(D+0x3718+i*0x208) for i in range(256)],'node init inventory')
            require(len(ctor.clears)==256+records,'clear inventory')
            pairs.append((ctor,cleanup,spec))
        require(pairs[0][0].visits==pairs[1][0].visits and pairs[0][1].visits==pairs[1][1].visits,'ambient fill dependence')
        ctor,cleanup,spec=pairs[0];members=sorted(int(v['S'],16) for v in ctor.visits)
        collisions=[dict(left=hex(a),right=hex(b),overlap_bytes=a+0x78-b) for a,b in zip(members,members[1:]) if b<a+0x78]
        if label=='eight_same_base_hypothetical':require(collisions,'expected overlap missing')
        else:require(not collisions,'unexpected S interval overlap')
        results[label]=dict(records=records,relocated=relocated,hypothetical=label!='original',
          constructor_visits=ctor.visits,cleanup_visits=cleanup.visits,families=spec,
          subobject_count=len(members),visit_order_identical=True,interval_collisions=collisions,
          node_initializer_count=len(ctor.node_initializers),clear_count=len(ctor.clears),
          projection_steps=dict(construct=ctor.steps,cleanup=cleanup.steps),
          branch_outcomes=dict(construct=sorted(ctor.branches),cleanup=sorted(cleanup.branches)),
          ignored_simd_never_feeds_scalar_reads=True)
    require(results['original']['subobject_count']==305 and results['eight_sidecar_hypothetical']['subobject_count']==325,'inventory size')
    # The address projection excludes constructor setup/epilogues. Pin its seed
    # definitions and preserve the full roots above for review of that boundary.
    seeds={0x142B9BE:'mov rbx, rcx',0x142B9C5:'mov rbp, rdx',0x142B9D0:'xor edi, edi',
           0x142BB94:'mov r12d, 4',0x142C9D5:'mov esi, 4',
           0x142BE26:'lea r15d, [r13 + 0x20]',0x142CB1D:'lea edi, [rsi + 0x20]'}
    for at,asm in seeds.items():require(row(by[at])['asm']==asm,'projection seed/count pin')
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256={SOURCE:SOURCE_SHA},
      runtime_verified=False,native_execution=False,code_spans=spans,projection_windows={k:[hex(x) for x in v] for k,v in PROJECTIONS.items()},
      seed_pins=[row(by[a]) for a in seeds],scenarios=results,
      contracts=['Only direct 140C160/140C200 calls in the two selected roots are inventoried.',
        'Fresh subobject helper and cleanup helper semantics come from pinned prior evidence; calls are not engine-executed.',
        'Calls invalidate volatile GPRs and preserve nonvolatile GPRs under Windows x64 ABI.',
        'Constructor seeded with RBX=D, RBP=context A, EDI=0 after prior setup; cleanup starts after prologue.',
        'Synthetic global347CE90 context and stack fifth argument are validated for every constructor call.',
        'Hypothetical eight cases override only record loop count and optionally record anchor inside Python.'],
      conditional_cleanup_invariant=['Each active pool node has exactly one owning S among the visited members.',
        'Each S count is valid; its listed indices are distinct, in bounds and marked occupied.',
        'Pool used count equals occupied slots, contexts remain valid, and cleanup callees return without reentrant mutation.',
        'Under those conditions all listed owned nodes are visited once; prior 140C200 clears occupancy and decrements used count.',
        'Full pool emptiness additionally requires no nodes owned by users outside this direct inventory.'],
      not_closed=['Actual resource release API behavior, exceptions, callbacks and reentrancy.',
        'Other owners/aliases, peak pool demand, native relocation and every consumer rewrite.',
        'Observed eight-player allocation, admission, spawning, gameplay and cleanup.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),scenarios={k:dict(count=v['subobject_count'],collisions=len(v['interval_collisions']),steps=v['projection_steps']) for k,v in results.items()})))


if __name__=='__main__':main()
