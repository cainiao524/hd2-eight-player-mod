"""Bounded source audit for D+8B7C0+n*180, without expanding helper trees.

Reads only pinned saved artifacts/capture. This proves selected argument paths
and the scope of a negative result, not absence of all allocation sources.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import Image, EXPECTED, require, row
from capstone.x86 import X86_OP_IMM

PRIOR = {
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
    'indexed_float_helper_boundaries_evidence.json': 'c70e0f48ce069decf271f9b69631695da41faaa7c5a373263d0f57a315e6e5d6',
    'indexed_float_pool_optional_members_evidence.json': '2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436',
    'indexed_float_pool_double_records_evidence_v2.json': '324b4d436d28b041963d5cb27db0a3496350c292a0e9b026bc885dc3bfc34650',
    'indexed_float_pool_double_records_refs_discovery.json': '6fd917ff2f4d41804612a5a0b935eee22ec4c0c8413e53041a1f9f9d660a137e',
}
DEP = {'indexed_float_pool_initial_zero_replay.py': '38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc'}
CONFIG_TARGETS = {0x140C2E0,0x142F6E0,0x142F530,0x142F780}
ADMITTED_ROOTS = {
    0x142B990:0x142BEB3,0x142BED0:0x142C89E,0x142C9B0:0x142CB57,
    0x142CB90:0x142D864,0x142D870:0x142EE66,0x142EE70:0x142F528,
    0x142FED0:0x142FF8B,0x142FF90:0x1430444,0x1430450:0x1431FE4,
    0x14329B0:0x1432F09,0x1433020:0x14332D9,0x14335F0:0x143372C,
}
CLASSIFIED = {
    0x142D0BD:'triple-group primary',0x142D144:'triple-group tertiary',0x142D171:'triple-group primary ID0',
    0x142DACA:'player record S+118',0x142DE22:'player record S+28',0x142DE3B:'player record S+A0',
    0x142DE6F:'player record S+1A0',0x142DF09:'player record S+218',
    0x142DFAC:'singleton D+81888',0x142E00F:'singleton D+81900',0x142E0B1:'family secondary D+81A00',
    0x142E2F5:'family primary D+81988',0x142E34D:'F530 record D+886B0+n*180',
    0x142E391:'family secondary D+81B88',0x142E5D5:'family primary D+81B10',
    0x142E7F3:'double-group PRIMARY D+8B748+n*180',0x142E84B:'F530 record D+8D540+n*180',
    0x142E8D9:'F530 record D+81C88+n*180',0x142E933:'F530 record D+87D90+n*180',
    0x142E9D6:'F530 record D+88528+n*180',0x14304E3:'singleton D+80DA0',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();out=Path(args.output);require(not out.exists(),'refusing overwrite')
    for n,h in DEP.items():require(sha((HERE/n).read_bytes())==h,'dependency changed')
    from indexed_float_pool_initial_zero_replay import reaching
    prior={}
    for n,h in PRIOR.items():
        raw=(HERE/n).read_bytes();require(sha(raw)==h,'prior changed '+n);prior[n]=json.loads(raw)
    im=Image(args.evidence);roots={};summaries=[];flat={}

    def source(root,start,end,expected,old):
        raw=im.read(start,end-start);require(sha(raw)==expected,'span hash')
        ins=list(im.md.disasm(raw,start));require(sum(i.size for i in ins)==len(raw),'decode closure')
        require([row(i) for i in ins]==old,'prior rows')
        roots.setdefault(root,[]).extend(ins);flat.update({i.address:i for i in ins})
        summaries.append(dict(root=hex(root),start=hex(start),end_exclusive=hex(end),sha256=expected,instructions=len(ins)))

    # Reuse the exact finite twelve-root admitted same-D set, not a new global scan.
    consumer=prior['indexed_float_consumers_evidence.json']
    admitted=set()
    for s in consumer['code_spans'].values():
        if 'root' not in s.get('proof',{}):continue
        root=int(s['proof']['root'],16)
        if root not in ADMITTED_ROOTS:continue
        require(root<=int(s['start'],16)<int(s['end_exclusive'],16)<=ADMITTED_ROOTS[root],
                'admitted root fragment bounds changed')
        admitted.add(root)
        source(root,int(s['start'],16),int(s['end_exclusive'],16),s['sha256'],s['instructions'])
    helper=prior['indexed_float_helper_boundaries_evidence.json']
    for fn in helper['functions']:
        if fn['root']!='0x142fa60':continue
        for s in fn['fragments']:
            start=int(s['bounds'][0],16);end=int(s['code_end_exclusive'],16)
            # The older artifact hashes the full unwind fragment including the
            # final table; pin that too, then keep its code/data split unchanged.
            require(sha(im.read(start,int(s['bounds'][1],16)-start))==s['sha256'],'helper full-fragment hash')
            source(0x142FA60,start,end,sha(im.read(start,end-start)),s['instructions'])
    double=prior['indexed_float_pool_double_records_evidence_v2.json']
    for s in double['code_spans'].values():
        if s['root']=='0x1431ff0':source(0x1431FF0,int(s['start'],16),int(s['end_exclusive'],16),s['sha256'],s['instructions'])
    for rs in roots.values():rs.sort(key=lambda i:i.address)
    require(admitted==set(ADMITTED_ROOTS),'admitted source scope changed')
    for root in admitted:
        rs=roots[root]
        # The inherited consumer proof splits chained unwind fragments and
        # excludes 142D831..142D864 (NOP padding plus a referenced RVA table).
        expected_end=0x142D831 if root==0x142CB90 else ADMITTED_ROOTS[root]
        require(rs[0].address==root and rs[-1].address+rs[-1].size==expected_end,
                'admitted code extent changed')
        require(all(a.address+a.size==b.address for a,b in zip(rs,rs[1:])),
                'admitted code fragment gap')

    pins,checks,graphs={},[],{}
    def pin(at,text):
        require(row(flat[at])['asm']==text,'pin '+hex(at));pins[at]=row(flat[at])
    for root in (0x1430450,0x1431FF0,0x142FA60):
        by={i.address:i for i in roots[root]};g={}
        for i in roots[root]:
            if i.mnemonic=='ret':edges=[]
            elif i.address==0x142FAA3:edges=sorted({int(v['target'],16) for v in helper['selector_table']['selector_values']})
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type==X86_OP_IMM,'indirect branch')
                edges=[i.operands[0].imm]+([] if i.mnemonic=='jmp' else [i.address+i.size])
            else:edges=[i.address+i.size]
            require(all(a in by for a in edges),'CFG exit');g[i.address]=edges
        seen=set();todo=[root]
        while todo:
            a=todo.pop()
            if a not in seen:seen.add(a);todo.extend(g[a])
        require(seen==set(by),'CFG closure');graphs[root]=g
    def rd(root,reg,at,definitions):
        expected={hex(v) if isinstance(v,int) else v for v in definitions}
        got=reaching(roots[root],graphs[root],reg)[at];require(got==expected,'reaching '+hex(at)+' '+reg)
        checks.append(dict(root=hex(root),register=reg,at=hex(at),definitions=sorted(got)))

    # One necessary derived-address chain: admitted D -> record R -> R+88.
    for a,t in {
        0x14304C8:'mov rsi, rcx',0x14310F0:'mov eax, ebx',0x14310F2:'lea r8, [rsi + 0x8b738]',
        0x1431109:'lea rcx, [rax + rax*2]',0x143110D:'shl rcx, 7',0x1431111:'add r8, rcx',
        0x1431114:'mov rcx, rsi',0x1431117:'call 0x1431ff0',0x1432040:'mov rsi, r8',
        0x14321CF:'lea rbx, [rsi + 0x88]',0x14321D6:'mov rcx, rbx',0x14321D9:'call 0x140d4f0',
        0x14322AF:'mov rcx, rbx',0x14322F1:'call 0x140de80',
        0x142FA7C:'mov rbx, rcx',0x142FB30:'lea rcx, [rbx + 0x8b7c0]',
        0x142FB3B:'add rcx, rdi',0x142FB43:'call 0x140d710',
        0x142FDFF:'lea rcx, [rbx + 0x8b7c0]',0x142FE0A:'add rcx, rdi',0x142FE0F:'call 0x140d710',
    }.items():pin(a,t)
    for args2 in [
        (0x1430450,'rsi',0x14310F2,[0x14304C8]),(0x1430450,'rax',0x1431109,[0x14310F0]),
        (0x1430450,'rcx',0x1431111,[0x143110D]),(0x1430450,'r8',0x1431111,[0x14310F2]),
        (0x1430450,'r8',0x1431117,[0x1431111]),(0x1431FF0,'r8',0x1432040,['entry']),
        (0x1431FF0,'rsi',0x14321CF,[0x1432040]),(0x1431FF0,'rbx',0x14321D6,[0x14321CF]),
        (0x1431FF0,'rcx',0x14321D9,[0x14321D6]),(0x1431FF0,'rbx',0x14322AF,[0x14321CF]),
        (0x1431FF0,'rcx',0x14322F1,[0x14322AF]),
        (0x142FA60,'rbx',0x142FB30,[0x142FA7C]),(0x142FA60,'rcx',0x142FB43,[0x142FB3B]),
        (0x142FA60,'rbx',0x142FDFF,[0x142FA7C]),(0x142FA60,'rcx',0x142FE0F,[0x142FE0A]),
    ]:rd(*args2)
    calls=[]
    for root in sorted(admitted):
        rs=roots[root]
        for n,i in enumerate(rs):
            if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM and i.operands[0].imm in CONFIG_TARGETS:
                require(i.address in CLASSIFIED,'unclassified admitted configuration call')
                calls.append(dict(root=hex(root),instruction=row(i),classification=CLASSIFIED[i.address],
                    caller_window=[row(x) for x in rs[max(0,n-8):n+1]]))
    require({int(x['instruction']['rva'],16) for x in calls}==set(CLASSIFIED),'configuration set changed')
    helper_calls={}
    for root in (0x142FA60,0x1431FF0):
        cs=[i for i in roots[root] if i.mnemonic=='call']
        require(all(i.operands[0].type==X86_OP_IMM for i in cs),'unexpected indirect helper call')
        require(not any(i.operands[0].imm in CONFIG_TARGETS for i in cs),'configuration helper call found')
        helper_calls[hex(root)]=[row(i) for i in cs]
    require({i.operands[0].imm for i in roots[0x142FA60] if i.mnemonic=='call'}=={0x140D710},'event helper callees')

    # F530 can configure R+88 via F780, but its five admitted record families
    # have different affine phases from the desired double-group record R.
    families=[(0x142E34D,0x886B0),(0x142E84B,0x8D540),(0x142E8D9,0x81C88),
              (0x142E933,0x87D90),(0x142E9D6,0x88528)]
    phases=[]
    for call,base in families:
        difference=(base-0x8B738)%0x180;require(difference!=0,'F530 family could equal wanted affine address')
        phases.append(dict(call=hex(call),record_base=hex(base),stride='0x180',
            secondary_base=hex(base+0x88),wanted_secondary_base='0x8b7c0',phase_difference=hex(difference)))
    refs=prior['indexed_float_pool_double_records_refs_discovery.json']['offsets']['0x8b7c0']
    literal=[];unadmitted=[]
    kinds={0x142BCD9:'constructor 140C160, empty S initialization',0x142CA67:'cleanup 140C200',
           0x142E61D:'existing secondary indices/events; local allocator call uses primary S instead',
           0x142FB30:'event update 140D710',0x142FDFF:'event update 140D710'}
    for r in refs['references']:
        at=int(r['rva'],16);i=im.instruction(at)
        require(i and all(row(i)[k]==r[k] for k in ('rva','bytes','sha256','asm')),'literal reference bytes')
        if at in kinds:literal.append(dict(instruction=r,classification=kinds[at]))
        else:unadmitted.append(dict(instruction=r,reason='Same-D base provenance not established; offset match alone is not admitted.'))
    require({int(x['instruction']['rva'],16) for x in literal}==set(kinds),'literal admitted set')
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,dependency_sha256=DEP,
        runtime_verified=False,native_execution=False,global_source_absence_proved=False,
        scope='Existing finite twelve same-D roots, admitted FA60 event helper, and one derived-record chain into already saved 1431FF0. No new global scan or recursive callee expansion.',
        source_spans=summaries,argument_pins=[pins[a] for a in sorted(pins)],reaching_checks=checks,
        derived_address_chain='D in caller RSI -> R8=D+8B738+ordinal*180 at1431117 -> helper RSI=R8 -> RBX=R+88 ->140D4F0/140DE80',
        derived_allocation_source_found=False,admitted_configuration_calls=calls,helper_calls=helper_calls,
        F530_secondary_affine_exclusions=phases,
        affine_assumptions='Equal D, integer ordinals, ordinary nonwrapping address arithmetic. Invalid/out-of-range memory accesses are not treated as intended configuration sources.',
        literal_secondary_references=literal,unadmitted_literal_candidates=unadmitted,
        config_targets=[hex(t) for t in sorted(CONFIG_TARGETS)],
        missing_provenance=['An admitted same-D direct or derived allocation call with RCX/ RDX equal to D+8B7C0+n*180, or F530 R8 equal to D+8B738+n*180 and enabled secondary flag.',
                            'Alternatively, a proved initialization/alias-closure contract establishing these S remain empty. That contract is not supplied by finite negative scans.'],
        decision='Keep actual allocated nodes and template IDs for all twenty secondary S. Do not assign zero demand, a guessed 1B template, or an ID0 reset/recovery operation from this negative result.',
        stop_reason='All selected references and the one necessary derived-address chain are classified without finding an admitted configuration source. Stop this branch pending new provenance; do not expand the render/helper tree.',
        limitations=['Calls below 140D4F0/140DE80 and external event/API callbacks are not recursively expanded; no semantic purity of arbitrary callees is claimed.',
                     'Computed aliases outside the selected paths, other-entry instances, indirect calls, unbound same-offset candidates and uncaptured/unwind-uncovered code remain outside scope.',
                     'No runtime state, lifetime exclusivity, complete pool bound or multiplayer acceptance is proved.'])
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),admitted_roots=len(admitted),
        configuration_calls=len(calls),literal_admitted=len(literal),literal_unadmitted=len(unadmitted),reaching_checks=len(checks))))


if __name__=='__main__':main()
