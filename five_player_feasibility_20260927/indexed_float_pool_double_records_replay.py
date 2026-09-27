"""Saved-capture-only proof of the 20-record shared-pool group.

Native code and opaque callees are not executed. Floating-point predicates are
treated as arbitrary filters, so the append projection is an upper bound only.
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
    'indexed_float_pool_lifecycle_inventory_evidence.json': '7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6',
    'indexed_float_pool_counter_bounds_evidence.json': 'aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4',
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
    'indexed_float_template_budget_evidence.json': '575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
    'indexed_float_pool_optional_members_evidence.json': '2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436',
    'indexed_float_pool_double_records_refs_discovery.json': '6fd917ff2f4d41804612a5a0b935eee22ec4c0c8413e53041a1f9f9d660a137e',
}
DEP = {
    'indexed_float_pool_initial_zero_replay.py': '38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc',
    'indexed_float_template_budget_replay.py': '7de63b88d3d7ca56746851b59b2b537fe774447df1b5f7384b5e4ec636817689',
}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def reach(g, start, omit=None, stops=()):
    seen, todo = set(), [start]
    while todo:
        a = todo.pop()
        if a not in seen:
            seen.add(a)
            if a not in stops:
                todo.extend(b for b in g[a] if (a, b) != omit)
    return seen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    dest = Path(args.output)
    require(not dest.exists(), 'refusing overwrite')
    for n, h in DEP.items():
        require(sha((HERE / n).read_bytes()) == h, 'dependency changed ' + n)
    from indexed_float_pool_initial_zero_replay import reaching, alias
    from indexed_float_template_budget_replay import Machine, LEAVES, BASE, STRIDE, COUNT, NODE, INPUT, normal_cfg
    prior, old = {}, {}

    def collect(x):
        if isinstance(x, dict):
            if all(k in x for k in ('rva', 'bytes', 'asm')):
                old[int(x['rva'], 16)] = x
            for v in x.values():
                collect(v)
        elif isinstance(x, list):
            for v in x:
                collect(v)

    for n, h in PRIOR.items():
        raw = (HERE / n).read_bytes()
        require(sha(raw) == h, 'prior changed ' + n)
        prior[n] = json.loads(raw)
        collect(prior[n])
    im = Image(args.evidence)
    roots, graphs, flat, spans = {}, {}, {}, {}
    root_cache = {f: im.root(f[0])[0] for f in im.functions}
    for root, end in {0x142BED0:0x142C89E, 0x142CB90:0x142D864,
                      0x142D870:0x142EE66, 0x18A3450:0x18A39AE,
                      0x1431FF0:0x14324D8}.items():
        fs = [f for f in im.functions if root_cache[f] == root]
        require(fs and fs[0][0] == root and fs[-1][1] == end, 'root bounds')
        require(all(a[1] == b[0] for a,b in zip(fs,fs[1:])), 'root gap')
        rs = []
        for f in fs:
            stop = min(f[1], 0x142D831) if root == 0x142CB90 else f[1]
            raw = im.read(f[0], stop-f[0])
            ins = list(im.md.disasm(raw, f[0]))
            require(sum(i.size for i in ins) == len(raw), 'decode closure')
            if root in (0x142BED0,0x142CB90,0x142D870):
                for i in ins:
                    require(all(old[i.address].get(k) == v for k,v in row(i).items()), 'prior instruction')
            spans[hex(f[0])] = dict(root=hex(root), start=hex(f[0]), end_exclusive=hex(stop),
                sha256=sha(raw), fragment=[hex(v) for v in f], instructions=[row(i) for i in ins])
            rs += ins
        by = {i.address:i for i in rs}
        g = {}
        for i in rs:
            nxt = i.address+i.size
            if i.mnemonic == 'ret':
                edges = []
            elif i.address == 0x142CEA3:
                edges = sorted(set(struct.unpack('<12I', im.read(0x142D834,48))))
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type == X86_OP_IMM, 'unresolved indirect branch')
                edges = [i.operands[0].imm] + ([] if i.mnemonic == 'jmp' else [nxt])
            else:
                edges = [nxt]
            require(all(a in by for a in edges), 'CFG exit')
            g[i.address] = edges
        require(reach(g,root) == set(by), 'normal CFG closure')
        roots[root], graphs[root] = rs,g
        flat.update(by)
    pins, checks, defs = {}, [], {}

    def pin(a, text):
        require(row(flat[a])['asm'] == text, 'pin ' + hex(a))
        pins[a] = row(flat[a])

    def rd(root, reg, at, expected):
        if (root,reg) not in defs:
            defs[root,reg] = reaching(roots[root],graphs[root],reg)
        want = {hex(v) if isinstance(v,int) else v for v in expected}
        require(defs[root,reg][at] == want, 'reaching ' + hex(at) + ' ' + reg)
        checks.append(dict(root=hex(root), reg=reg, at=hex(at), definitions=sorted(want)))

    # Fifth/sixth arguments: callee delta 5 pushes + F0 = 118; call adds 8.
    for a,t in {
        0x142D264:'lea rax, [rbp + 0xa0]',
        0x142D277:'mov qword ptr [rsp + 0x28], rax',
        0x142D27F:'mov dword ptr [rsp + 0x20], 0x14',
        0x142D287:'call 0x18a3450',
        0x18A3462:'mov rax, qword ptr [rsp + 0x148]',
        0x18A346A:'xor esi, esi',
        0x18A346C:'mov r15d, dword ptr [rsp + 0x140]',
        0x18A349A:'mov qword ptr [rsp + 0x40], rax',
        0x18A38CC:'mov rdx, qword ptr [rsp + 0x40]',
        0x18A38D1:'cmp esi, r15d',
        0x18A38D4:'jae 0x18a3935',
        0x18A38D9:'lea rcx, [rsi + rsi*2]',
        0x18A38E6:'inc esi',
        0x18A392A:'movsd qword ptr [rdx + rcx*4], xmm0',
        0x18A392F:'mov dword ptr [rdx + rcx*4 + 8], eax',
        0x18A3933:'ja 0x18a38d1',
        0x18A3991:'mov eax, esi',
    }.items():
        pin(a,t)
    rd(0x142CB90,'rax',0x142D277,[0x142D264])
    rd(0x18A3450,'r15',0x18A38D1,[0x18A346C])
    rd(0x18A3450,'rsi',0x18A38D1,[0x18A346A,0x18A38E6])
    rd(0x18A3450,'rsi',0x18A3991,[0x18A346A,0x18A38E6])
    rd(0x18A3450,'rcx',0x18A392A,[0x18A38D9])
    rd(0x18A3450,'rdx',0x18A392A,[0x18A38CC])
    rd(0x18A3450,'rax',0x18A349A,[0x18A3462])
    for reg,expected in [('rsi',{0x18A346A,0x18A38E6,0x18A39AB}),
                         ('r15',{0x18A346C,0x18A39A5})]:
        writers = {i.address for i in roots[0x18A3450]
                   if reg in {alias(i.reg_name(r)) for r in i.regs_access()[1]}}
        require(writers == expected, 'bounded producer register writers')
    g = graphs[0x18A3450]
    require(0x18A38E6 not in reach(g,0x18A3450,(0x18A38D4,0x18A38D6)), 'count increment bypasses guard')
    require(0x18A38E6 not in reach(g,0x18A38E8,stops=(0x18A38D1,)), 'repeat increment bypasses guard')
    # Output pointer slot remains stable; producer calls only scalar math helper.
    slot_writes = []
    for i in roots[0x18A3450]:
        for n,o in enumerate(i.operands):
            if o.type == X86_OP_MEM and ((o.access & CS_AC_WRITE) or (n == 0 and i.mnemonic.startswith('mov'))):
                if i.reg_name(o.mem.base) == 'rsp' and o.mem.disp <= 0x40 < o.mem.disp+o.size:
                    slot_writes.append(i.address)
    require(slot_writes == [0x18A349A], 'producer output slot writer')
    require({i.operands[0].imm for i in roots[0x18A3450] if i.mnemonic=='call'} == {0x210D0B4}, 'producer callees')
    # Bound follows ESI=0, only guarded INC, preserved nonvolatile registers and
    # no interleaved calls inside the guard/output store window. It needs no
    # assumption about the floating-point branch's numerical outcome.
    require(not any(i.mnemonic=='call' for i in roots[0x18A3450] if 0x18A38D1 <= i.address <= 0x18A3933), 'opaque output call')

    # Five append sites: four-way unrolling and one scalar remainder.
    loads = [0x142D31D,0x142D3AE,0x142D440,0x142D4D2,0x142D729]
    stores = [0x142D344,0x142D3D5,0x142D467,0x142D4F9,0x142D750]
    incs = [0x142D34C,0x142D3DD,0x142D46F,0x142D501,0x142D758]
    for a in loads:
        pin(a,'mov eax, dword ptr [rdi + 0x8d538]')
    for a in stores:
        pin(a,'mov qword ptr [rcx + rdi + 0x8b738], rax')
    for a in incs:
        pin(a,'inc dword ptr [rdi + 0x8d538]')
    for a,store in zip(loads,stores):
        pin(a+0xA,'lea rcx, [rax + rax*2]')
        pin(a+0xE,'shl rcx, 7')
        rd(0x142CB90,'rax',a+0xA,[a])
        rd(0x142CB90,'rcx',store,[a+0xE])
    for a,t in {
        0x142CBBA:'mov rdi, rcx', 0x142BFBC:'mov dword ptr [rbx + 0x8d538], ecx',
        0x142BFAC:'xor ecx, ecx',0x142BEF6:'mov rbx, rcx',
        0x142D28C:'mov r9d, eax',0x142D292:'cmp eax, 4',
        0x142D29B:'lea ecx, [rax - 4]',0x142D29E:'shr ecx, 2',
        0x142D2A8:'inc ecx',0x142D2AA:'mov r8d, ecx',
        0x142D2AD:'lea r11d, [rcx*4]',0x142D2B5:'lea r10, [rcx*4]',
        0x142D507:'add rdx, 0x30',0x142D50B:'sub r8, 1',
        0x142D50F:'jne 0x142d2c0',0x142D6BC:'sub r9d, r11d',
        0x142D6C6:'mov r8d, r9d',0x142D75E:'add rdx, 0xc',
        0x142D762:'sub r8, 1',0x142D766:'jne 0x142d6cd',
        0x142E5F1:'cmp dword ptr [r14 + 0x8d538], 0',
        0x142E61D:'lea rdx, [r14 + 0x8b7c0]',
        0x142E7DC:'lea rdx, [rax + 0x8b748]',
        0x142E7EA:'add rdx, r14',0x142E7ED:'mov r8d, 0x1f',
        0x142E7F3:'call 0x142f6e0',0x142E802:'cmp eax, dword ptr [r14 + 0x8d538]',
        0x1432040:'mov rsi, r8',0x14321CF:'lea rbx, [rsi + 0x88]',
        0x14322FF:'lea rcx, [rsi + 0x10]',
    }.items():
        pin(a,t)
    rd(0x142BED0,'rcx',0x142BFBC,[0x142BFAC])
    rd(0x142BED0,'rbx',0x142BFBC,[0x142BEF6])
    for a in loads+stores+incs:
        rd(0x142CB90,'rdi',a,[0x142CBBA])
    rd(0x142D870,'r8',0x142E7F3,[0x142E7ED])
    rd(0x142D870,'rdx',0x142E7F3,[0x142E7EA])
    rd(0x142CB90,'rax',0x142D28C,[0x142D287])
    require(not any(i.mnemonic=='call' for i in roots[0x142CB90] if 0x142D28C <= i.address <= 0x142D76C), 'append phase call')
    phase_writers=[]
    for i in roots[0x142CB90]:
        for n,o in enumerate(i.operands):
            if o.type == X86_OP_MEM and o.mem.disp == 0x8D538 and ((o.access&CS_AC_WRITE) or (n==0 and i.mnemonic.startswith('mov'))):
                phase_writers.append(i.address)
    require(phase_writers==incs,'builder counter writers')
    refs=prior['indexed_float_pool_double_records_refs_discovery.json']
    scanned_writers=[]
    for r in refs['offsets']['0x8d538']['references']:
        i=im.instruction(int(r['rva'],16))
        require(i and all(row(i)[k]==r[k] for k in ('rva','bytes','sha256','asm')),'count xref bytes')
        if any(o.type==X86_OP_MEM and (o.access & CS_AC_WRITE) for o in i.operands):
            scanned_writers.append(i.address)
    require(set(scanned_writers)==set(incs+[0x142BFBC]),'finite count writer scan')
    projections=[]
    for returned in range(21):
        groups = ((returned-4)//4+1) if returned>=4 else 0
        unrolled = 4*groups
        remainder = returned-unrolled
        visits = [j for k in range(groups) for j in range(4*k,4*k+4)] + list(range(unrolled,unrolled+remainder))
        require(visits==list(range(returned)), 'return-count projection')
        projections.append(dict(returned=returned,unrolled_groups=groups,remainder=remainder,visited_ordinals=visits,
            maximum_appends=len(visits),max_final_count_from_zero=len(visits)))

    # Main S is configured with template 1F. Secondary event handling neither
    # assigns a template nor cleans the S in this caller segment.
    window=[i for i in roots[0x142D870] if 0x142E5F1<=i.address<0x142E80F]
    direct_calls=[i.operands[0].imm for i in window if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
    require(set(direct_calls)=={0x12556E0,0x142F6E0}, 'update segment direct calls')
    helper_calls=[i.operands[0].imm for i in roots[0x1431FF0] if i.mnemonic=='call' and i.operands[0].type==X86_OP_IMM]
    require(not ({0x140C2E0,0x140C200} & set(helper_calls)), 'generic renderer direct allocation/release')

    # Actual template emitter instructions; synthetic payload data only.
    init=prior['indexed_float_template_budget_evidence.json']['initializer']
    a,b=int(init['start'],16),int(init['end_exclusive'],16)
    raw=im.read(a,b-a)
    require(sha(raw)==init['sha256'],'initializer')
    ini=list(im.md.disasm(raw,a));ig=normal_cfg(ini)
    a,b=0x125F891,0x125F8CB
    block=[i for i in ini if a<=i.address<b]
    require(block[0].address==a and block[-1].address+block[-1].size==b,'emitter block')
    require(row(block[0])['asm']=='mov ecx, 0x1f','template id')
    require(not [(x,y) for x,ys in ig.items() for y in ys if a<y<b and not a<=x<b],'emitter alternate entry')
    require(all(i.mnemonic in ('mov','lea','call') for i in block),'emitter flow')
    decoded={}
    for start,end in LEAVES.items():
        ins=list(im.md.disasm(im.read(start,end-start),start))
        for i in ins:
            require(all(old[i.address].get(k)==v for k,v in row(i).items()),'emitter leaf')
        decoded[start]={i.address:i for i in ins}
    cs=[i for i in block if i.mnemonic=='call']
    require([i.operands[0].imm for i in cs]==[0x1257720,0x1257C90,0x1257E00,0x1257E00,0x1257E00],'emitter sequence')
    emission=[]
    for fill in (0,0xA5):
        m=Machine(decoded,0x1F)
        for i in cs:
            t=i.operands[0].imm;m.call(t,0x1F if t==0x1257720 else INPUT,fill)
        ptr=BASE+0x1F*STRIDE;n=m.memory(ptr+COUNT,4)
        emission.append(dict(nodes=n,types=[m.memory(ptr+j*NODE,4) for j in range(n)],
            events=[m.memory(ptr+j*NODE+0xD64,4) for j in range(n)],steps=m.steps))
    require(emission[0]==emission[1] and emission[0]['nodes']==1 and emission[0]['events']==[3],'template count')
    # The old lifecycle projection is authoritative for all 40 S, regardless of
    # the current active record count. Recheck its source pointers and call rows.
    life=prior['indexed_float_pool_lifecycle_inventory_evidence.json']
    lifecycle_rows=[]
    for span in life['code_spans'].values():
        for r in span['instructions']:
            if any(v in r['asm'] for v in ('0x8b7c0','0x14','0x180')) or r['asm'] in ('call 0x140c160','call 0x140c200'):
                at=int(r['rva'],16);ins=im.instruction(at)
                require(ins and row(ins)==r,'lifecycle bytes')
                lifecycle_rows.append(r)
    caller_render=[old[a] for a in sorted(old) if 0x14310E6<=a<0x1431126]
    for r in caller_render:
        i=im.instruction(int(r['rva'],16));require(i and all(row(i)[k]==r[k] for k in ('rva','bytes','sha256','asm')),'renderer caller bytes')
    require(any(r['asm']=='lea r8, [rsi + 0x8b738]' for r in caller_render),'renderer record source')
    require(any(r['asm']=='call 0x1431ff0' for r in caller_render),'renderer call')

    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,dependency_sha256=DEP,
        capture_identity_sha256=im.report['capture_sha256'],runtime_verified=False,native_execution=False,
        code_spans=spans,semantic_pins=[pins[a] for a in sorted(pins)],argument_reaching_definitions=checks,
        producer=dict(root='0x18a3450',max_argument=20,callee_stack_delta='0x118',return_bound=[0,20],
            output_stride=12,maximum_output_bytes=240,guard_required_for_every_increment=True,
            assumptions=['Normal Windows x64 calling convention, valid stack and nonvolatile registers.',
                         'Opaque scalar-math helper 210D0B4 is not executed; it preserves nonvolatile registers and does not corrupt caller storage.']),
        append_projection=projections,
        count_contract=dict(field='D+8D538',physical_records=20,append_sites=[hex(a) for a in incs],
            reset='0x142bfbc',no_local_count_capacity_guard=True,
            conditional_bound='If count is zero before one producer/filter pass, no interfering mutation and normal callees, final count is 0..20.',
            nonzero_initial_count='At most 20 append attempts; count + accepted holds only until an invalid record address overwrites adjacent data. Zero-before-pass and safe repeated rebuild are not proved.',
            finite_scan_writers=[hex(a) for a in sorted(scanned_writers)],
            counterexample=dict(kind='address arithmetic only, global gameplay reachability unproved',initial_count=20,accepted_new_points=1,
                first_invalid_record='D+8D538; its qword position store overwrites the count and adjacent field before INC reads the count again',
                final_count='not generally 21; depends on the overwritten position bytes')),
        group=dict(record_base='D+8B738',stride='0x180',S_offsets=['0x10','0x88'],S_count=40,
            record_end_exclusive='D+8D538',primary_template='0x1f',primary_nodes=1,
            primary_call='0x142e7f3',secondary_template='not established in admitted paths',
            request_budget='current count * 1 for primary requests only; not total retained occupancy',
            retention='Lowering/resetting count or clearing events does not directly call S cleanup here. Keep all 40 physical S in ownership snapshot; full lifecycle cleanup visits all 40.'),
        update_segment_direct_calls=[hex(a) for a in sorted(set(direct_calls))],
        generic_render_direct_calls=[hex(a) for a in sorted(set(helper_calls))],
        render_caller=caller_render,lifecycle_pins=lifecycle_rows,
        template_1f=dict(start='0x125f891',end_exclusive='0x125f8cb',instructions=[row(i) for i in block],replays=emission,
            preconditions=['Fresh zeroed template, event payload +E4=0, synthetic zero/A5 inputs; actual runtime template and other writers not verified.']),
        implementation_decision='Do not scale the physical 20 count with player count. Validate count in 0..20, inventory all 40 owners even when count shrinks, and retain unclassified secondary occupancy.',
        stop_criterion='Producer maximum, append visiting count, main template cardinality, and physical S lifecycle are connected; stop following numerical math/render callees for this capacity question.',
        next_step='Use a layout-driven 40-owner collection specification and preserve node ownership independent of the active count; separately establish reset-before-rebuild and secondary-template writers if a static whole-pool bound is required.',
        limits=['No live memory, process discovery, native execution, game modification, or multiplayer test.',
                'Normal CFG proofs omit exceptions, corrupted inputs, concurrency, reentrancy and nonconforming callees.',
                'Physical capacity is not proof of initial stored-count validity or of all external aliases.',
                'Generic render helper accesses optional R+100 if R+178>0, but this group lifecycle initializes only the two listed S. No active third-S ownership is inferred.',
                'The group has a 20-node primary request upper bound only under the stated count/template assumptions; secondary and retained owners remain in occupancy.'])
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(dest),sha256=sha(dest.read_bytes()),instructions=sum(len(v) for v in roots.values()),
        reaching_checks=len(checks),producer_return_bound=[0,20],template_nodes=1,template_events=3)))


if __name__=='__main__':
    main()
