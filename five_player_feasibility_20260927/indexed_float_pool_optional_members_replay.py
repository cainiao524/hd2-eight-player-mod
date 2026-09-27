"""Offline proof of optional member selection and four additional template counts."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image,EXPECTED,require,row
from capstone.x86 import X86_OP_IMM

DEP={
 'indexed_float_template_budget_replay.py':'7de63b88d3d7ca56746851b59b2b537fe774447df1b5f7384b5e4ec636817689',
 'indexed_float_pool_initial_zero_replay.py':'38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc',
}
PRIOR={
 'indexed_float_consumers_evidence.json':'503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
 'indexed_float_template_budget_evidence.json':'575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
 'indexed_float_pool_lifecycle_inventory_evidence.json':'7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6',
}
ROOTS={0x142F530:0x142F6D9,0x142F780:0x142F810}
TAILS={0x142F6D4:0x142F6E0,0x142F80B:0x140D710}
GROUPS={0x20:(0x125F93A,0x125F974),0x21:(0x125FDA1,0x125FDDD),
        0x2F:(0x125FF6F,0x125FF85),0x22:(0x12600D5,0x126010F)}


def sha(b):return hashlib.sha256(b).hexdigest()


def reachable(graph,start,omit_edge=None):
    seen=set();work=[start]
    while work:
        at=work.pop()
        if at not in seen:
            seen.add(at);work.extend(x for x in graph[at] if (at,x)!=omit_edge)
    return seen


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--evidence',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();output=Path(args.output);require(not output.exists(),'refusing overwrite')
    for name,digest in DEP.items():require(sha((HERE/name).read_bytes())==digest,'dependency changed')
    from indexed_float_template_budget_replay import Machine,LEAVES,BASE,STRIDE,COUNT,NODE,INPUT,normal_cfg
    from indexed_float_pool_initial_zero_replay import reaching
    old={};prior={}
    def collect(x):
        if isinstance(x,dict):
            if all(k in x for k in ('rva','bytes','asm')):old[int(x['rva'],16)]=x
            for v in x.values():collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    for name,digest in PRIOR.items():
        raw=(HERE/name).read_bytes();require(sha(raw)==digest,'prior changed '+name);prior[name]=json.loads(raw);collect(prior[name])
    im=Image(args.evidence);spans={};roots={};cfgs={};flat={}
    for root,end in ROOTS.items():
        fs=[f for f in im.functions if im.root(f[0])[0]==root]
        require(fs and fs[0][0]==root and fs[-1][1]==end,'helper root bounds')
        require(all(a[1]==b[0] for a,b in zip(fs,fs[1:])),'fragment gaps')
        ins=[]
        for f in fs:
            raw=im.read(f[0],f[1]-f[0]);rs=list(im.md.disasm(raw,f[0]));require(sum(i.size for i in rs)==len(raw),'truncated decode')
            spans[hex(f[0])]=dict(start=hex(f[0]),end_exclusive=hex(f[1]),root=hex(root),
                fragment=[hex(v) for v in f],sha256=sha(raw),instructions=[row(i) for i in rs]);ins+=rs
        by={i.address:i for i in ins};graph={}
        for i in ins:
            nxt=i.address+i.size
            if i.address in TAILS:
                require(i.mnemonic=='jmp' and i.operands[0].imm==TAILS[i.address],'tail target');out=[]
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type==X86_OP_IMM,'indirect branch');out=[i.operands[0].imm]+([] if i.mnemonic=='jmp' else [nxt])
            else:out=[nxt]
            require(all(x in by for x in out),'unclassified exit');graph[i.address]=out
        require(reachable(graph,root)==set(by),'unreachable code');roots[root]=ins;cfgs[root]=graph;flat.update(by)
    pins={
     0x142F536:'sub rsp, 0x40',0x142F53A:'cmp byte ptr [rsp + 0x78], 0',
     0x142F53F:'mov ebp, r9d',0x142F547:'mov rsi, r8',
     0x142F550:'je 0x142f567',0x142F552:'lea rdx, [r8 + 0x88]',
     0x142F55F:'mov r8d, r9d',0x142F562:'call 0x142f780',
     0x142F567:'cmp byte ptr [rsp + 0x80], 0',0x142F56F:'je 0x142f6a1',
     0x142F57A:'lea rbx, [rsi + 0x100]',0x142F589:'xor edi, edi',
     0x142F58B:'mov edx, edi',0x142F58D:'cmp ebp, 0x28',
     0x142F590:'sete dl',0x142F593:'add edx, 0x2d',0x142F596:'call 0x140c2e0',
     0x142F6A1:'movzx r8d, byte ptr [rsp + 0x78]',0x142F6A7:'lea rcx, [rsi + 0x88]',
     0x142F6AE:'mov edx, 0x1f',0x142F6B3:'call 0x140d710',
     0x142F6B8:'lea rdx, [rsi + 0x10]',0x142F6C2:'mov r8d, ebp',
     0x142F78A:'mov rbx, rdx',0x142F78D:'xor edi, edi',0x142F78F:'mov edx, edi',
     0x142F791:'cmp r8d, 0x28',0x142F795:'mov rcx, rbx',
     0x142F798:'sete dl',0x142F79B:'add edx, 0x1b',0x142F79E:'call 0x140c2e0',
    }
    for at,asm in pins.items():require(row(flat[at])['asm']==asm,'semantic pin '+hex(at))
    checks=[(0x142F530,'rsi',0x142F57A,0x142F547),(0x142F530,'rbp',0x142F58D,0x142F53F),
      (0x142F530,'rsi',0x142F6A7,0x142F547),(0x142F530,'rsi',0x142F6B8,0x142F547),
      (0x142F530,'rbp',0x142F6C2,0x142F53F),(0x142F530,'rdx',0x142F6D4,0x142F6B8),
      (0x142F530,'r8',0x142F6D4,0x142F6C2),
      (0x142F780,'rbx',0x142F795,0x142F78A),(0x142F780,'rcx',0x142F79E,0x142F795),
      (0x142F780,'r8',0x142F791,'entry')]
    reaching_checks=[]
    for root,reg,at,expected in checks:
        got=reaching(roots[root],cfgs[root],reg)[at];want=expected if isinstance(expected,str) else hex(expected)
        require(got=={want},'argument reaching definition');reaching_checks.append(dict(at=hex(at),reg=reg,definitions=sorted(got)))
    require(0x142F562 not in reachable(cfgs[0x142F530],0x142F530,(0x142F550,0x142F552)),'secondary call not gated')
    require(0x142F596 not in reachable(cfgs[0x142F530],0x142F530,(0x142F56F,0x142F575)),'tertiary call not gated')
    calls=[i.operands[0].imm for ins in roots.values() for i in ins if i.mnemonic=='call']
    require(set(calls)=={0x142F780,0x140C2E0,0x140D710},'unexpected helper callees')
    require(0x140C200 not in calls,'direct cleanup unexpectedly present')

    # Reuse the previously verified five complete template leaves. Their exact
    # code and the Python interpreter dependency are both fingerprinted.
    decoded={}
    for entry,end in LEAVES.items():
        ins=list(im.md.disasm(im.read(entry,end-entry),entry))
        for i in ins:require(i.address in old and all(old[i.address].get(k)==v for k,v in row(i).items()),'leaf bytes changed')
        decoded[entry]={i.address:i for i in ins}
    builder=prior['indexed_float_template_budget_evidence.json']['initializer']
    a=int(builder['start'],16);b=int(builder['end_exclusive'],16);raw=im.read(a,b-a)
    require(sha(raw)==builder['sha256'],'builder source changed')
    builder_ins=list(im.md.disasm(raw,a));builder_cfg=normal_cfg(builder_ins);emissions={}
    for ident,(a,b) in GROUPS.items():
        ins=[i for i in builder_ins if a<=i.address<b];require(ins and ins[0].address==a and ins[-1].address+ins[-1].size==b,'group bounds')
        require(row(ins[0])['asm']==f'mov ecx, {hex(ident)}','template ID')
        require(not [(x,y) for x,ys in builder_cfg.items() for y in ys if a<y<b and not a<=x<b],'external group entry')
        require(all(i.mnemonic in ('mov','lea','call') for i in ins),'nonlinear emission block')
        cs=[i for i in ins if i.mnemonic=='call'];require(cs[0].operands[0].imm==0x1257720,'selector call')
        require(all(i.operands[0].imm in LEAVES for i in cs),'unmodelled emitter call')
        counters=[]
        for fill in (0,0xA5):
            m=Machine(decoded,ident)
            for i in cs:
                t=i.operands[0].imm;m.call(t,ident if t==0x1257720 else INPUT,fill)
            ptr=BASE+ident*STRIDE;n=m.memory(ptr+COUNT,4)
            counters.append(dict(nodes=n,types=[m.memory(ptr+j*NODE,4) for j in range(n)],
               events=[m.memory(ptr+j*NODE+0xD64,4) for j in range(n)],steps=m.steps))
        require(counters[0]==counters[1] and counters[0]['nodes']==1,'template count changed')
        emissions[hex(ident)]=dict(start=hex(a),end_exclusive=hex(b),instructions=[row(i) for i in ins],**counters[0])
    # Source slices from the already-proved same-D 142D870 consumer. Stored count
    # values and global execution are not captured; member capacities below are
    # physical bounds inherited from the direct lifecycle inventory.
    caller_ranges=[(0x142E820,0x142E850),(0x142E8B8,0x142E8DE),(0x142E900,0x142E938),(0x142E9AD,0x142E9DB),
                   (0x142E7D7,0x142E7DC),(0x142E870,0x142E881)]
    caller=[]
    for a,b in caller_ranges:
        ins=list(im.md.disasm(im.read(a,b-a),a));require(sum(i.size for i in ins)==b-a,'caller span')
        for i in ins:require(i.address in old and all(old[i.address].get(k)==v for k,v in row(i).items()),'caller prior mismatch')
        caller.extend(row(i) for i in ins)
    selected=[dict(call='0x142e84b',record_base='0x8d540',primary_S='0x8d550',template='0x20',count_field='0x8d6c0',physical_records=1,flag6=0,flag7=0),
      dict(call='0x142e8d9',record_base='0x81c88',primary_S='0x81c98',template='0x21',count_field='0x87d88',physical_records=64,flag6=0,flag7=0),
      dict(call='0x142e933',record_base='0x87d90',primary_S='0x87da0',template='0x2f',count_field='0x88524',physical_records=5,flag6=0,flag7=0),
      dict(call='0x142e9d6',record_base='0x88528',primary_S='0x88538',template='0x22',count_field='0x886ac',physical_records=1,flag6=1,flag7=0)]
    result=dict(schema_version=1,source_sha256=EXPECTED,dependency_sha256=DEP,prior_sha256=PRIOR,
      runtime_verified=False,native_execution=False,helper_spans=spans,semantic_pins=[row(flat[a]) for a in pins],
      argument_reaching_definitions=reaching_checks,conditional_calls_gated=True,
      stack_mapping=dict(prologue_delta='0x48',float_arg5_current_rsp='0x70',flag_arg6_current_rsp='0x78',flag_arg7_current_rsp='0x80',
        caller_float_arg5='0x20',caller_flag6='0x28',caller_flag7='0x30'),
      selector_rules=dict(primary='record+10, caller template T, always tail to 142F6E0',
        secondary='record+88, only when arg6 is nonzero; template 1B + (T == 28)',
        tertiary='record+100, only when arg7 is nonzero; template 2D + (T == 28)',
        false_flag='No direct 140C200 or zero-template request for that optional S; do not assume visibility false releases nodes.'),
      template_emission_blocks=emissions,caller_pins=caller,selected_callers=selected,
      synthetic_template_preconditions=['Fresh zeroed template elements; valid event input secondary count at +E4 is zero.',
        'Payloads use zero/A5 synthetic bytes. Actual initializer stack payloads are not reconstructed.',
        'Other writers, invocation ordering, callbacks and concurrent mutation are outside the model.'],
      bounded_request_budget=dict(expression='c20 + c21 + c2F + 2*c22',maximum_at_physical_counts=72,
        caveat='Only the templates requested by these four call sites, with valid bounded counters and matching runtime templates. Not total or lifetime pool occupancy.'),
      not_closed=['Runtime template equivalence, stored counts and writers enforcing their physical bounds.',
        'Other callers or previously configured optional members; caching, external events, reentrancy and actual release.',
        'Whole-pool peak, relocation aliases, executable eight-player patch and multiplayer verification.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),helper_instructions=sum(len(v) for v in roots.values()),
      templates={k:dict(nodes=v['nodes'],events=v['events']) for k,v in emissions.items()},checks=len(reaching_checks))))


if __name__=='__main__':main()
