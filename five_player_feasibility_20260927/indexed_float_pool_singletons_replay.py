"""Pinned offline proof of seven singleton S requests and two count-one guards.

The replay does not access a game process or run native game functions. Template
emission counts are conditional on valid payloads and unchanged runtime tables;
the finite reference scan is not a proof that no computed aliases exist.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import Image, EXPECTED, require, row
from capstone import CS_AC_WRITE
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

PRIOR = {
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
    'indexed_float_template_budget_evidence.json': '575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
    'indexed_float_pool_counter_bounds_evidence.json': 'aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4',
    'indexed_float_pool_singletons_refs_discovery.json': 'dbab53634956077e53bbe4eac811a5e61fdf061b070166582fe69195e8ffd288',
}
DEP = {
    'indexed_float_template_budget_replay.py': '7de63b88d3d7ca56746851b59b2b537fe774447df1b5f7384b5e4ec636817689',
    'indexed_float_pool_initial_zero_replay.py': '38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc',
}
GROUPS = {0x16: (0x125E511, 0x125E58B), 0x1A: (0x125F0E5, 0x125F14C),
          0x1D: (0x125F6DF, 0x125F779), 0x1E: (0x125F7E4, 0x125F81E)}
ROOTS = (0x142BED0, 0x142CB90, 0x142D870, 0x1430450)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reach(graph, start, omit=None, stops=()):
    seen, pending = set(), [start]
    while pending:
        at = pending.pop()
        if at not in seen:
            seen.add(at)
            if at not in stops:
                pending.extend(b for b in graph[at] if (at, b) != omit)
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = Path(args.output)
    require(not out.exists(), 'refusing overwrite')
    for name, expected in DEP.items():
        require(sha((HERE / name).read_bytes()) == expected, 'dependency changed: ' + name)
    from indexed_float_template_budget_replay import Machine, LEAVES, BASE, STRIDE, COUNT, NODE, INPUT, normal_cfg
    from indexed_float_pool_initial_zero_replay import reaching
    prior = {}
    for name, expected in PRIOR.items():
        raw = (HERE / name).read_bytes()
        require(sha(raw) == expected, 'prior changed: ' + name)
        prior[name] = json.loads(raw)
    im = Image(args.evidence)
    consumers = prior['indexed_float_consumers_evidence.json']
    spans = consumers['code_spans']
    flat, roots, graphs, summaries = {}, {}, {}, []
    table_raw = im.read(0x142D831, 0x33)
    require(sha(table_raw) == 'abfcc71e0a91e2fa50e012c094e93af404bd4dceaeead721ebfb583b50ccd5bf', 'switch tail changed')
    table = sorted(set(struct.unpack('<12I', table_raw[3:])))
    for root in ROOTS:
        fs = [f for f in im.functions if im.root(f[0])[0] == root]
        rs, parts = [], []
        for f in fs:
            s = spans[hex(f[0])]
            a, b = int(s['start'], 16), int(s['end_exclusive'], 16)
            require(a == f[0] and b == (min(f[1], 0x142D831) if root == 0x142CB90 else f[1]), 'span mismatch')
            raw = im.read(a, b-a)
            require(sha(raw) == s['sha256'], 'root bytes changed')
            ins = list(im.md.disasm(raw, a))
            require(sum(i.size for i in ins) == b-a and [row(i) for i in ins] == s['instructions'], 'prior row mismatch')
            rs += ins
            parts.append(dict(start=hex(a), end_exclusive=hex(b), sha256=sha(raw), instruction_count=len(ins)))
        by = {i.address: i for i in rs}
        graph = {}
        for i in rs:
            nxt = i.address+i.size
            if i.mnemonic == 'ret':
                dest = []
            elif i.address == 0x142CEA3:
                require(row(i)['asm'] == 'jmp rcx', 'switch changed')
                dest = table
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type == X86_OP_IMM, 'unknown branch')
                dest = [i.operands[0].imm] + ([] if i.mnemonic == 'jmp' else [nxt])
            else:
                dest = [nxt]
            require(all(a in by for a in dest), 'unclassified exit')
            graph[i.address] = dest
        require(reach(graph, root) == set(by), 'unreachable code')
        roots[root], graphs[root] = rs, graph
        flat.update(by)
        summaries.append(dict(root=hex(root), fragments=parts, instruction_count=len(rs)))

    pins, checks, cache = {}, [], {}
    def pin(at, asm):
        require(row(flat[at])['asm'] == asm, 'semantic pin: ' + hex(at))
        pins[at] = row(flat[at])
    def rd(root, reg, at, expected):
        if (root, reg) not in cache:
            cache[root, reg] = reaching(roots[root], graphs[root], reg)
        values=expected if isinstance(expected,(list,tuple)) else [expected]
        want={x if isinstance(x,str) else hex(x) for x in values}
        require(cache[root, reg][at] == want, 'reaching: ' + hex(at) + ' ' + reg + ': ' + str(cache[root, reg][at]))
        checks.append(dict(root=hex(root), register=reg, at=hex(at), definitions=sorted(want)))

    pin(0x142CBBA, 'mov rdi, rcx')
    pin(0x142BEF6, 'mov rbx, rcx')
    pin(0x142BFAC, 'xor ecx, ecx')
    guards = []
    for field, load, cmp_at, branch, first, scale, shift, write, inc, reset, base in (
        (0x81AF8,0x142D528,0x142D52E,0x142D531,0x142D537,0x142D53F,0x142D543,0x142D568,0x142D570,0x142BFAE,0x81978),
        (0x81C80,0x142D580,0x142D586,0x142D589,0x142D58B,0x142D593,0x142D597,0x142D5BC,0x142D5C4,0x142BFB6,0x81B00),
    ):
        pin(load, f'mov edx, dword ptr [rdi + {hex(field)}]')
        pin(cmp_at, 'cmp edx, 1')
        pin(branch, 'jae 0x142d5cf')
        pin(scale, 'lea rcx, [rdx + rdx*2]')
        pin(shift, 'shl rcx, 7')
        pin(write, f'mov qword ptr [rcx + rdi + {hex(base)}], rax')
        pin(inc, f'inc dword ptr [rdi + {hex(field)}]')
        pin(reset, f'mov dword ptr [rbx + {hex(field)}], ecx')
        rd(0x142BED0,'rbx',reset,0x142BEF6)
        rd(0x142BED0,'rcx',reset,0x142BFAC)
        for at in (cmp_at,scale): rd(0x142CB90,'rdx',at,load)
        rd(0x142CB90,'rcx',shift,scale)
        rd(0x142CB90,'rcx',write,shift)
        for at in (load,write,inc): rd(0x142CB90,'rdi',at,0x142CBBA)
        graph = graphs[0x142CB90]
        stop = inc+flat[inc].size
        region = reach(graph,load,stops=(0x142D5CF,stop))-{0x142D5CF,stop}
        require(cmp_at+flat[cmp_at].size==branch and branch+flat[branch].size==first,'guard layout')
        require(not [(a,b) for a,bs in graph.items() for b in bs if b in region and a not in region and b!=load], 'alternate entry')
        require(all(flat[a].mnemonic!='call' for a in region),'call within append')
        require(all(b>a for a in region for b in graph[a] if b in region),'cyclic append')
        for at in (write,inc): require(at not in reach(graph,0x142CB90,omit=(branch,first)),'guard bypass')
        stores=[]
        for a in sorted(region):
            i=flat[a]
            for n,op in enumerate(i.operands):
                if op.type!=X86_OP_MEM or not ((op.access&CS_AC_WRITE) or (n==0 and i.mnemonic.startswith('mov'))):continue
                if i.reg_name(op.mem.base) in ('rsp','rbp') and not op.mem.index:continue
                require(a in (write,inc),'unclassified append store')
                stores.append(row(i))
        require(len(stores)==2,'store count')
        refs=prior['indexed_float_pool_singletons_refs_discovery.json']['offsets'][hex(field)]['references']
        writes=[int(r['rva'],16) for r in refs if r['access']&CS_AC_WRITE]
        require(set(writes)=={reset,inc},'additional finite writer')
        require(base+0x180==field,'physical extent')
        guards.append(dict(counter=hex(field),capacity=1,reset=hex(reset),increment=hex(inc),
            guard=hex(branch),body=[row(flat[a]) for a in sorted(region)],guard_pass_required=True,
            no_calls_or_cycles=True,finite_writers=[hex(x) for x in sorted(writes)],
            accepted_case=dict(before=0,after=1,record_store=[hex(base),hex(base+8)]),
            rejected_u32_interval=[1,0xffffffff],invalid_initial_counts_repaired=False))

    # The saved caller proof establishes the same D; here pin the concrete S
    # argument and template ID. Count-one loops require unchanged valid counts.
    caller_pins = {
      0x14304AE:'lea rbx, [rcx + 0x80da0]',0x14304D3:'mov rcx, rbx',0x14304D6:'mov edx, 0x16',0x14304E3:'call 0x140c2e0',
      0x142D8A7:'mov qword ptr [rsp + 0x68], rcx',0x142DF98:'mov r14, qword ptr [rsp + 0x68]',
      0x142DF9D:'mov edx, 0x1a',0x142DFA2:'lea rbx, [r14 + 0x81888]',0x142DFA9:'mov rcx, rbx',0x142DFAC:'call 0x140c2e0',
      0x142E000:'lea rbx, [r14 + 0x81900]',0x142E007:'mov edx, 0x1b',0x142E00C:'mov rcx, rbx',0x142E00F:'call 0x140c2e0',
      0x142E07D:'cmp dword ptr [r14 + 0x81af8], 0',0x142E085:'mov eax, r12d',0x142E088:'mov dword ptr [rsp + 0x50], eax',0x142E08C:'jbe 0x142e311',
      0x142E092:'lea rax, [rax + rax*2]',0x142E096:'mov edx, 0x1b',0x142E09B:'shl rax, 7',0x142E09F:'mov qword ptr [rsp + 0x70], rax',
      0x142E0A4:'lea r13, [rax + 0x81a00]',0x142E0AB:'add r13, r14',0x142E0AE:'mov rcx, r13',0x142E0B1:'call 0x140c2e0',
      0x142E2D4:'mov r14, qword ptr [rsp + 0x68]',0x142E2D9:'mov rdx, qword ptr [rsp + 0x70]',0x142E2DE:'mov r8d, 0x1d',0x142E2E4:'add rdx, 0x81988',0x142E2F2:'add rdx, r14',0x142E2F5:'call 0x142f6e0',
      0x142E2FA:'mov eax, dword ptr [rsp + 0x50]',0x142E2FE:'inc eax',0x142E300:'mov dword ptr [rsp + 0x50], eax',0x142E304:'cmp eax, dword ptr [r14 + 0x81af8]',0x142E30B:'jb 0x142e092',
      0x142E35D:'cmp dword ptr [r14 + 0x81c80], 0',0x142E365:'mov eax, r12d',0x142E368:'mov dword ptr [rsp + 0x48], eax',0x142E36C:'jbe 0x142e5f1',
      0x142E372:'lea rax, [rax + rax*2]',0x142E376:'mov edx, 0x1b',0x142E37B:'shl rax, 7',0x142E37F:'mov qword ptr [rsp + 0x70], rax',0x142E384:'lea r13, [rax + 0x81b88]',0x142E38B:'add r13, r14',0x142E38E:'mov rcx, r13',0x142E391:'call 0x140c2e0',
      0x142E5B4:'mov r14, qword ptr [rsp + 0x68]',0x142E5B9:'mov rdx, qword ptr [rsp + 0x70]',0x142E5BE:'mov r8d, 0x1e',0x142E5C4:'add rdx, 0x81b10',0x142E5D2:'add rdx, r14',0x142E5D5:'call 0x142f6e0',
      0x142E5DA:'mov eax, dword ptr [rsp + 0x48]',0x142E5DE:'inc eax',0x142E5E0:'mov dword ptr [rsp + 0x48], eax',0x142E5E4:'cmp eax, dword ptr [r14 + 0x81c80]',0x142E5EB:'jb 0x142e372',
    }
    for at,asm in caller_pins.items():pin(at,asm)
    for root,reg,at,want in (
      (0x1430450,'rcx',0x14304AE,'entry'),(0x1430450,'rbx',0x14304D3,0x14304AE),(0x1430450,'rcx',0x14304E3,0x14304D3),(0x1430450,'rdx',0x14304E3,0x14304D6),
      (0x142D870,'r14',0x142DFA2,0x142DF98),(0x142D870,'rbx',0x142DFA9,0x142DFA2),(0x142D870,'rcx',0x142DFAC,0x142DFA9),(0x142D870,'rdx',0x142DFAC,0x142DF9D),
      (0x142D870,'rbx',0x142E00C,0x142E000),(0x142D870,'rcx',0x142E00F,0x142E00C),(0x142D870,'rdx',0x142E00F,0x142E007),
      (0x142D870,'rcx',0x142E0B1,0x142E0AE),(0x142D870,'rdx',0x142E0B1,0x142E096),
      (0x142D870,'rdx',0x142E2F5,0x142E2F2),(0x142D870,'r8',0x142E2F5,0x142E2DE),
      (0x142D870,'rcx',0x142E391,0x142E38E),(0x142D870,'rdx',0x142E391,0x142E376),
      (0x142D870,'rdx',0x142E5D5,0x142E5D2),(0x142D870,'r8',0x142E5D5,0x142E5BE),
      (0x142D870,'r13',0x142E0AE,0x142E0AB),(0x142D870,'r13',0x142E0AB,0x142E0A4),
      (0x142D870,'r13',0x142E38E,0x142E38B),(0x142D870,'r13',0x142E38B,0x142E384),
      (0x142D870,'rax',0x142E0A4,0x142E09B),(0x142D870,'rax',0x142E384,0x142E37B),
      (0x142D870,'rdx',0x142E2E4,0x142E2D9),(0x142D870,'rdx',0x142E2F2,0x142E2E4),
      (0x142D870,'rdx',0x142E5C4,0x142E5B9),(0x142D870,'rdx',0x142E5D2,0x142E5C4),
      (0x142D870,'r14',0x142E0AB,[0x142DF98,0x142E2D4]),
      (0x142D870,'r14',0x142E000,0x142DF98),(0x142D870,'r14',0x142E07D,0x142DF98),
      (0x142D870,'r14',0x142E35D,[0x142DF98,0x142E2D4]),
      (0x142D870,'r14',0x142E38B,[0x142DF98,0x142E2D4,0x142E5B4]),
      (0x142D870,'r14',0x142E2F2,[0x142DF98,0x142E2D4]),
      (0x142D870,'r14',0x142E5D2,[0x142DF98,0x142E2D4,0x142E5B4]),
      (0x142D870,'r12',0x142E085,[0x142DA87,0x142DE97]),
      (0x142D870,'r12',0x142E365,[0x142DA87,0x142DE97,0x142E2AA]),
    ):rd(root,reg,at,want)
    for at in (0x142DA87,0x142DE97,0x142E2AA):pin(at,'xor r12d, r12d')
    pin(0x142D874,'lea rbp, [rsp - 0x90]')
    pin(0x142D87C,'sub rsp, 0x190')
    def stack_writes(instructions,lo,hi):
        writes=[]
        for i in instructions:
            for n,op in enumerate(i.operands):
                if op.type!=X86_OP_MEM or not ((op.access&CS_AC_WRITE) or (n==0 and i.mnemonic.startswith('mov'))):continue
                base=i.reg_name(op.mem.base)
                if base not in ('rsp','rbp') or op.mem.index:continue
                offset=op.mem.disp+(0x100 if base=='rbp' else 0)
                if offset<hi and offset+op.size>lo:writes.append(i.address)
        return writes
    saved_d_writes=stack_writes(roots[0x142D870],0x68,0x70)
    require(saved_d_writes==[0x142D8A7],'saved D overwritten by direct frame store')
    loop_proofs=[]
    for branch,first,stop,calls,stride_store,index_offset,index_init,index_update in (
        (0x142E08C,0x142E092,0x142E311,[0x142E0B1,0x142E2F5],0x142E09F,0x50,0x142E088,0x142E300),
        (0x142E36C,0x142E372,0x142E5F1,[0x142E391,0x142E5D5],0x142E37F,0x48,0x142E368,0x142E5E0),
    ):
        graph=graphs[0x142D870]
        for call in calls:
            require(call not in reach(graph,0x142D870,omit=(branch,first)),'loop call bypasses count check')
        stride_writes=stack_writes([i for i in roots[0x142D870] if first<=i.address<stop],0x70,0x78)
        require(stride_writes==[stride_store],'saved index stride overwritten directly')
        index_writes=stack_writes([i for i in roots[0x142D870] if index_init<=i.address<stop],index_offset,index_offset+4)
        require(index_writes==[index_init,index_update],'outer index overwritten directly')
        loop_proofs.append(dict(count_pass_edge=[hex(branch),hex(first)],allocation_calls=[hex(a) for a in calls],
            calls_require_pass_edge=True,loop_initial_index_zero=True,
            saved_stride_direct_writes=[hex(a) for a in stride_writes],
            outer_index_direct_writes=[hex(a) for a in index_writes],frame_aliases_checked=['rsp','rbp=rsp+0x100'],
            valid_stable_counter_cases=[dict(count=0,ordinals=[]),dict(count=1,ordinals=[0])],
            opaque_calls_cannot_mutate_loop_state='required assumption, not proven'))

    # Reuse exact previously verified emitter leaves; model only bounded blocks.
    budget=prior['indexed_float_template_budget_evidence.json']
    builder=budget['initializer'];a,b=int(builder['start'],16),int(builder['end_exclusive'],16)
    raw=im.read(a,b-a);require(sha(raw)==builder['sha256'],'initializer changed')
    ins=list(im.md.disasm(raw,a));require([row(i) for i in ins]==builder['instructions'],'initializer rows')
    graph=normal_cfg(ins)
    decoded={}
    for entry,end in LEAVES.items():
        raw=im.read(entry,end-entry);s=budget['leaves'][hex(entry)]
        require(sha(raw)==s['sha256'],'leaf changed')
        rs=list(im.md.disasm(raw,entry));require([row(i) for i in rs]==s['instructions'],'leaf rows')
        decoded[entry]={i.address:i for i in rs}
    emissions={}
    for ident,(a,b) in GROUPS.items():
        block=[i for i in ins if a<=i.address<b]
        require(block[0].address==a and block[-1].address+block[-1].size==b,'block extent')
        require(row(block[0])['asm']==f'mov ecx, {hex(ident)}','selector')
        require(all(i.mnemonic in ('mov','lea','call') for i in block),'nonlinear block')
        require(not [(x,y) for x,ys in graph.items() for y in ys if a<y<b and not a<=x<b],'external block entry')
        calls=[i for i in block if i.mnemonic=='call']
        require(calls[0].operands[0].imm==0x1257720 and all(i.operands[0].imm in LEAVES for i in calls),'unknown emitter')
        require(sum(i.operands[0].imm==0x1257720 for i in calls)==1,'selector count')
        values=[]
        for fill in (0,0xA5):
            m=Machine(decoded,ident)
            for i in calls:
                t=i.operands[0].imm;m.call(t,ident if t==0x1257720 else INPUT,fill)
            p=BASE+ident*STRIDE;n=m.memory(p+COUNT,4)
            values.append(dict(nodes=n,types=[m.memory(p+j*NODE,4) for j in range(n)],events=[m.memory(p+j*NODE+0xD64,4) for j in range(n)],steps=m.steps))
        require(values[0]==values[1],'payload dependent counts')
        emissions[hex(ident)]=dict(start=hex(a),end_exclusive=hex(b),instructions=[row(i) for i in block],**values[0])
    require([emissions[hex(t)]['nodes'] for t in GROUPS]==[2,3,3,1],'unexpected cardinality')
    selected=[(0x80DA0,0x16,0x14304E3,None),(0x81888,0x1A,0x142DFAC,None),(0x81900,0x1B,0x142E00F,None),
              (0x81988,0x1D,0x142E2F5,0x81AF8),(0x81A00,0x1B,0x142E0B1,0x81AF8),
              (0x81B10,0x1E,0x142E5D5,0x81C80),(0x81B88,0x1B,0x142E391,0x81C80)]
    mappings=[dict(S_offset=hex(s),template=hex(t),call=hex(c),count_field=None if n is None else hex(n),
        nodes=1 if t==0x1B else emissions[hex(t)]['nodes']) for s,t,c,n in selected]
    require(budget['emission_blocks']['0x1b']['node_count']==1,'prior 1B count')
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,dependency_sha256=DEP,
        source_program_sha256=sha(Path(__file__).read_bytes()),runtime_verified=False,native_execution=False,
        root_summaries=summaries,initializer_summary={k:builder[k] for k in ('start','end_exclusive','sha256','instruction_count')},
        semantic_pins=[pins[a] for a in sorted(pins)],reaching_checks=checks,count_one_guards=guards,loop_proofs=loop_proofs,
        saved_D_direct_writers=[hex(a) for a in saved_d_writes],
        template_emissions=emissions,selected_S_requests=mappings,
        bounded_request_budget=dict(expression='2+3+1+4*c81AF8+2*c81C80',maximum_for_valid_count_one=12,
            retained_member_envelope=12,scope='Only these seven S using these template IDs; not a bound on unknown prior heap states or global coexistence.'),
        preconditions=['Valid count initial values 0 or 1; finite encoded-displacement writers preserve that bound.',
            'No computed-alias/concurrent/opaque-callee mutation of counters, saved D or loop state.',
            'Fresh template emission storage and valid synthetic event payload secondary count zero.',
            'Runtime templates match the replay; later writers and all initialization ordering remain unproved.',
            'Selected loop index follows the observed zero-based progression; old skipped S allocations may remain.'],
        not_closed=['Finite references include other candidate callers with unproved D identity; not an exhaustive alias proof.',
            'The two count-zero skip paths do not prove S cleanup; counter/cache resets must not subtract node demand.',
            'Complete request demand does not prove native allocation completes; partial allocation and same-ID non-retry still apply.',
            'Whole pool peak and template transitions outside this fixed-ID subset.',
            'Synchronization, native executor, external resource validity and multiplayer acceptance.'])
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),roots=sum(len(v) for v in roots.values()),
        checks=len(checks),templates={k:v['nodes'] for k,v in emissions.items()},bounded_seven_S_nodes=12)))


if __name__=='__main__':main()
