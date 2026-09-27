"""Offline proof of the enclosing allocation's initial zero-fill and pool offsets.

No process access or game execution. A static initialization source is proved;
continued zero state at a later constructor or a reusable reset is NOT proved.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image,EXPECTED,require,row
from capstone.x86 import X86_OP_IMM,X86_OP_MEM

PRIOR={
 'indexed_float_storage_evidence.json':'11e984e270540eded0e141f821ddfbb22118c0b99645237eca15e14149d42378',
 'indexed_float_subobjects_evidence.json':'5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
 'indexed_float_template_budget_evidence.json':'575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
}
ROOTS={0x4EE160:0x4EE689,0xAB4520:0xAB4F26,0xAB8B70:0xAB8E45,
       0xFDA190:0xFDA3E8,0x551B60:0x556D8B,0x568230:0x569374}
TAILS={0xAB8E40:0x12F8600,0x556D86:0x76A060}
PREFIX=(0xAB5000,0xAB5077)
MASK=(1<<64)-1


def sha(raw):return hashlib.sha256(raw).hexdigest()


def alias(name):
    names={'eax':'rax','ax':'rax','al':'rax','ah':'rax',
     'ebx':'rbx','bx':'rbx','bl':'rbx','bh':'rbx','ecx':'rcx','cx':'rcx','cl':'rcx','ch':'rcx',
     'edx':'rdx','dx':'rdx','dl':'rdx','dh':'rdx','esi':'rsi','si':'rsi','sil':'rsi',
     'edi':'rdi','di':'rdi','dil':'rdi','ebp':'rbp','bp':'rbp','bpl':'rbp',
     'esp':'rsp','sp':'rsp','spl':'rsp'}
    if name in names:return names[name]
    if name.startswith('r') and name[-1:] in ('d','w','b') and name[1:-1].isdigit():return name[:-1]
    return name


def cfg_for(ins,prefix=False):
    by={i.address:i for i in ins};edges={};exits=[]
    for i in ins:
        nxt=i.address+i.size
        if i.mnemonic=='ret':out=[]
        elif i.address in TAILS:
            require(i.mnemonic=='jmp' and i.operands[0].imm==TAILS[i.address],'tail target changed')
            out=[];exits.append(dict(site=hex(i.address),target=hex(TAILS[i.address])))
        elif i.mnemonic.startswith('j'):
            require(i.operands[0].type==X86_OP_IMM,'indirect jump needs separate table proof')
            out=[i.operands[0].imm]+([] if i.mnemonic=='jmp' else [nxt])
        elif prefix and i==ins[-1]:
            out=[];exits.append(dict(site=hex(i.address),unanalysed_continuation=hex(nxt)))
        else:out=[nxt]
        require(all(a in by for a in out),'branch outside proved root')
        edges[i.address]=out
    seen=set();work=[ins[0].address]
    while work:
        at=work.pop()
        if at not in seen:seen.add(at);work.extend(edges[at])
    require(seen==set(by),'unreachable decoded instructions')
    return edges,exits


def reaching(ins,edges,reg):
    """All normal CFG reaching writes to one full/partial register.

    Calls kill volatile GPRs. Nonvolatile preservation follows the Windows x64
    calling convention; exceptions, corrupted stacks and nonconforming callees
    are outside this static proof.
    """
    incoming={i.address:set() for i in ins};incoming[ins[0].address].add('entry')
    by={i.address:i for i in ins};pending=[ins[0].address]
    while pending:
        at=pending.pop();i=by[at]
        writes={alias(i.reg_name(r)) for r in i.regs_access()[1]}
        if i.mnemonic=='call':writes.update(['rax','rcx','rdx','r8','r9','r10','r11'])
        out={hex(at)} if reg in writes else incoming[at]
        for dst in edges[at]:
            new=incoming[dst]|out
            if new!=incoming[dst]:incoming[dst]=new;pending.append(dst)
    return incoming


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True);ap.add_argument('--output',required=True)
    args=ap.parse_args();output=Path(args.output);require(not output.exists(),'refusing overwrite')
    old={}
    def collect(x):
        if isinstance(x,dict):
            if all(k in x for k in ('rva','asm','bytes')):old[int(x['rva'],16)]=x
            for v in x.values():collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    for name,digest in PRIOR.items():
        raw=(HERE/name).read_bytes();require(sha(raw)==digest,'prior changed '+name);collect(json.loads(raw))
    im=Image(args.evidence);spans={};roots={};cfgs={};flat={}
    root_cache={f:im.root(f[0])[0] for f in im.functions}
    for start,end in ROOTS.items():
        fs=[f for f in im.functions if root_cache[f]==start]
        require(fs and fs[0][0]==start and fs[-1][1]==end,'family bounds changed')
        require(all(a[1]==b[0] for a,b in zip(fs,fs[1:])),'non-contiguous family')
        rs=[]
        for f in fs:
            raw=im.read(f[0],f[1]-f[0]);ins=list(im.md.disasm(raw,f[0]))
            require(sum(i.size for i in ins)==len(raw),'incomplete fragment decode')
            spans[hex(f[0])]=dict(start=hex(f[0]),end_exclusive=hex(f[1]),sha256=sha(raw),
                fragment=[hex(v) for v in f],root=hex(start),instructions=[row(i) for i in ins])
            rs+=ins
        cfg,exits=cfg_for(rs);roots[start]=rs;cfgs[start]=cfg;flat.update({i.address:i for i in rs})
        require(not exits or start in (0xAB8B70,0x551B60),'unexpected external tails')
    a,b=PREFIX
    prefix_fs=[f for f in im.functions if a<=f[0]<b and root_cache[f]==a]
    require(prefix_fs and prefix_fs[0][0]==a and prefix_fs[-1][1]>=b,'prefix not from unwind entry')
    require(all(x[1]==y[0] for x,y in zip(prefix_fs,prefix_fs[1:])),'prefix fragment gap')
    whole={i.address:i for f in prefix_fs for i in im.md.disasm(im.read(f[0],f[1]-f[0]),f[0])}
    ins=list(im.md.disasm(im.read(a,b-a),a));require(sum(i.size for i in ins)==b-a,'prefix decode')
    require(all(i.address in whole and i.bytes==whole[i.address].bytes for i in ins),'prefix boundaries')
    roots[a]=ins;cfgs[a],_=cfg_for(ins,prefix=True);flat.update({i.address:i for i in ins})
    spans['startup_prefix']=dict(start=hex(a),end_exclusive=hex(b),sha256=sha(im.read(a,b-a)),
        fragments=[[hex(v) for v in f] for f in prefix_fs],scope='Entry prefix through first AB4520 call only.',instructions=[row(i) for i in ins])

    pins={
     0x4EE51B:'mov edx, 0x7af7628',0x4EE524:'call r9',0x4EE527:'xor edx, edx',
     0x4EE529:'mov r8d, 0x7af7628',0x4EE52F:'mov rcx, rax',0x4EE532:'mov rbx, rax',
     0x4EE535:'call 0x208aaa0',
     0xAB5030:'mov rcx, r14',0xAB5072:'call 0xab4520',
     0xAB453F:'mov rdi, rcx',0xAB4766:'cmp byte ptr [rdi + 0x10b3], sil',
     0xAB476D:'jne 0xab4787',0xAB476F:'mov rcx, rdi',0xAB4772:'call 0xab8b70',
     0xAB4777:'mov byte ptr [rdi + 0x10b3], 1',
     0xAB8C48:'add rcx, 0xe49f0',0xAB8C76:'call 0xfda190',
     0xFDA1A4:'mov rbx, rcx',0xFDA352:'lea rcx, [rbx + 0x40]',0xFDA375:'call 0x551b60',
     0x551B7A:'mov rsi, rcx',0x551B7D:'call 0x568230',
     0x553E30:'lea rbx, [rsi + 0x1f7ae8]',0x553EB4:'call 0x1258050',
     0x568236:'mov rbx, rcx',0x5687E4:'lea rax, [rbx + 0x1f7ae8]',
    }
    for at,asm in pins.items():require(row(flat[at])['asm']==asm,'pin changed '+hex(at))
    rip=[]
    for at,target,kind in [(0x4EE564,0x3326340,'publish_zeroed_outer'),
                           (0xAB5025,0x3326340,'load_same_outer'),
                           (0x5687EB,0x3326AA0,'publish_manager')]:
        i=flat[at];ops=[o for o in i.operands if o.type==X86_OP_MEM and i.reg_name(o.mem.base)=='rip']
        require(len(ops)==1 and i.address+i.size+ops[0].mem.disp==target,'RIP identity')
        rip.append(dict(**row(i),target=hex(target),role=kind))
    require(flat[0x4EE564].reg_name(flat[0x4EE564].operands[1].reg)=='rbx','publication source')
    require(flat[0xAB5025].reg_name(flat[0xAB5025].operands[0].reg)=='r14','outer load register')
    require(flat[0x5687EB].reg_name(flat[0x5687EB].operands[1].reg)=='rax','manager publication source')
    # Every check is at an instruction's INPUT state.
    checks=[
     (0x4EE160,'rax',0x4EE52F,0x4EE524),(0x4EE160,'rax',0x4EE532,0x4EE524),
     (0x4EE160,'rcx',0x4EE535,0x4EE52F),(0x4EE160,'rdx',0x4EE535,0x4EE527),
     (0x4EE160,'r8',0x4EE535,0x4EE529),(0x4EE160,'rbx',0x4EE564,0x4EE532),
     (0xAB5000,'r14',0xAB5030,0xAB5025),(0xAB5000,'rcx',0xAB5072,0xAB5030),
     (0xAB4520,'rcx',0xAB453F,'entry'),(0xAB4520,'rdi',0xAB476F,0xAB453F),
     (0xAB4520,'rcx',0xAB4772,0xAB476F),
     (0xAB8B70,'rcx',0xAB8C48,'entry'),(0xAB8B70,'rcx',0xAB8C76,0xAB8C48),
     (0xFDA190,'rcx',0xFDA1A4,'entry'),(0xFDA190,'rbx',0xFDA352,0xFDA1A4),
     (0xFDA190,'rcx',0xFDA375,0xFDA352),
     (0x551B60,'rcx',0x551B7A,'entry'),(0x551B60,'rcx',0x551B7D,'entry'),
     (0x551B60,'rsi',0x553E30,0x551B7A),
     (0x568230,'rcx',0x568236,'entry'),(0x568230,'rbx',0x5687E4,0x568236),
     (0x568230,'rax',0x5687EB,0x5687E4),
    ]
    cache={};checked=[]
    for root,reg,at,expected in checks:
        key=(root,reg)
        if key not in cache:cache[key]=reaching(roots[root],cfgs[root],reg)
        want=expected if isinstance(expected,str) else hex(expected)
        got=cache[key][at];require(got=={want},f'reaching definition {hex(at)} {reg}: {got}')
        checked.append(dict(root=hex(root),register=reg,at=hex(at),definitions=sorted(got)))
    # The clear must occur on all normal paths reaching pointer publication.
    graph=cfgs[0x4EE160];seen=set();pending=[0x4EE160]
    while pending:
        at=pending.pop()
        if at in seen or at==0x4EE535:continue
        seen.add(at);pending.extend(graph[at])
    require(0x4EE564 not in seen,'clear does not dominate publication')
    # Preserve actual prior bytes for pool layout and the already-reviewed fill
    # implementation. No new native test or unbounded decompilation is implied.
    prior_pins=[]
    for at in [0x724292,0x724332,0x7244E2,0x7244FD,0x724542,0x142BB1B,0x142BB22,
               0x142BB25,0x142BB29,0x208AAA0,0x208AAA3,0x208AA80]:
        require(at in old,'prior pin absent '+hex(at));r=old[at];raw=bytes.fromhex(r['bytes'])
        require(im.read(at,len(raw))==raw,'prior bytes mismatch');prior_pins.append(r)
    outer_size=0x7AF7628;owner=0xE49F0+0x40;manager=owner+0x1F7AE8
    d=manager+0x4CD1F0;p=d+0x36F8
    fields={
     'pool_descriptor':(p,0x20),'used_count':(p+0x10,4),'search_cursor':(p+0x18,4),
     'node_backing':(d+0x3718,256*0x208),'occupancy':(d+0x23F18,256),
    }
    require(d+0x3718+256*0x208==d+0x23F18,'node/occupancy adjacency')
    require(all(0<=a and a+n<=outer_size for a,n in fields.values()),'pool outside clear')
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,
     runtime_verified=False,native_execution=False,
     scope='Initial whole-owner zero-fill source; not proof of later zero state or reusable reset.',
     code_spans=spans,complete_roots={hex(k):len(v) for k,v in roots.items() if k in ROOTS},
     normal_cfg_external_tails={hex(k):hex(v) for k,v in TAILS.items()},
     semantic_pins=[row(flat[a]) for a in pins],rip_identity=rip,reaching_definitions=checked,
     clear_dominates_publication=True,prior_layout_and_fill_pins=prior_pins,
     identity=dict(outer_global='0x3326340',manager_global='0x3326aa0',outer_size=hex(outer_size),
       world_offset='0xe49f0',owner_offset=hex(owner),manager_offset=hex(manager),
       D_offset_for_k0=hex(d),pool_offset_for_k0=hex(p),manager_instance_stride='0x55a698',
       note='k is manager instance ordinal, not player/network index. Field bounds below are for k=0.'),
     zeroed_ranges_for_k0={name:dict(start=hex(a),end_exclusive=hex(a+n),size=n) for name,(a,n) in fields.items()},
     template_initialization_edge=dict(caller='0x553eb4',callee='0x1258050',
       owner_constructor='0x551b60',meaning='Observed static call from same owner setup; live execution/order and later mutation not captured.'),
     not_closed=['Allocation API target and actual returned pointer/success.',
       'No lifetime-wide proof that these bytes stay zero until first D initialization.',
       'Reinitialization/reuse and cleanup invariants; never zero a live pool without releasing resources.',
       'Other manager ordinals require valid instance/bounds evidence; they are not player ordinals.',
       'Other pool users and peak/transient occupancy; all aliases and executable eight-player patch.',
       'Fifth/eighth-player multiplayer behavior and unapproved fourth capture.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),roots=result['complete_roots'],
      reaching_checks=len(checked),ranges=result['zeroed_ranges_for_k0']),ensure_ascii=False))


if __name__=='__main__':main()
