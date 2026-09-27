"""Offline template cardinality, triple-member selection and transition demand.

Native callees are never run. The builder-domain induction explicitly assumes
opaque callees do not mutate its count, local stack array, or template table.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import Image, EXPECTED, require, row
from capstone import CS_AC_WRITE
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

DEP = {
    'indexed_float_template_budget_replay.py': '7de63b88d3d7ca56746851b59b2b537fe774447df1b5f7384b5e4ec636817689',
    'indexed_float_pool_initial_zero_replay.py': '38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc',
}
PRIOR = {
    'indexed_float_pool_counter_bounds_evidence.json': 'aae3906ab3672a3b0f8ed631fdfddeec11bb7b636e3b5bfbb7083d3554f048d4',
    'indexed_float_template_budget_evidence.json': '575501706ca9dd257f4cd155325b6a809ed303037736359fb4da6918ee5117bc',
    'indexed_float_pool_optional_members_evidence.json': '2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436',
    'indexed_float_subobjects_evidence.json': '5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
    'indexed_float_pool_triple_refs_discovery.json': 'eed4f4f30ed8ef3bb73a861575ebcae12b21172ee34bbf693772da1f15ce40e2',
}
GROUPS = {
    0x1C: (0x125F4F7, 0x125F53D), 0x2D: (0x125FA14, 0x125FA42),
    0x2E: (0x125FA60, 0x125FBA4), 0x24: (0x126034B, 0x12603E5),
    0x25: (0x12603E9, 0x1260483), 0x26: (0x12604BB, 0x1260525),
    0x27: (0x126054C, 0x12605B6), 0x28: (0x12605BA, 0x1260624),
}
HELPERS = {0x1257980: 0x125799E, 0x12579A0: 0x12579CD,
           0x12579D0: 0x12579F4, 0xB6C30: 0xB6C4E}


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


def writes(i):
    # Capstone 5 does not reliably mark MOVUPS memory destinations as writes.
    # Account for the architectural first destination in addition to access bits.
    return [o for n, o in enumerate(i.operands) if o.type == X86_OP_MEM and
            ((o.access & CS_AC_WRITE) or (n == 0 and i.mnemonic.startswith('mov')))]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    for name, digest in DEP.items():
        require(sha((HERE / name).read_bytes()) == digest, 'dependency changed')
    from indexed_float_template_budget_replay import Machine, LEAVES, BASE, STRIDE, COUNT, NODE, INPUT, normal_cfg
    from indexed_float_pool_initial_zero_replay import reaching
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

    for name, digest in PRIOR.items():
        raw = (HERE / name).read_bytes()
        require(sha(raw) == digest, 'prior changed ' + name)
        prior[name] = json.loads(raw)
        collect(prior[name])
    im = Image(args.evidence)
    roots, graphs, flat, root_proofs = {}, {}, {}, []
    counter = prior['indexed_float_pool_counter_bounds_evidence.json']
    builder = prior['indexed_float_template_budget_evidence.json']['initializer']
    for root in (0x142CB90, 0x142D870, 0x1258050):
        fs = [f for f in im.functions if im.root(f[0])[0] == root]
        source_spans = [s for s in counter['code_spans'].values() if int(s['root'], 16) == root] if root != 0x1258050 else [builder]
        require({int(s['start'], 16) for s in source_spans} == {f[0] for f in fs}, 'full root fragment set')
        rs, summaries = [], []
        for s in source_spans:
            a, b = int(s['start'], 16), int(s['end_exclusive'], 16)
            f = im.containing(a)
            require(f[1] == b or (root == 0x142CB90 and b == 0x142D831 and f[1] == 0x142D864), 'fragment end')
            raw = im.read(a, b-a)
            require(sha(raw) == s['sha256'], 'root bytes')
            ins = list(im.md.disasm(raw, a))
            require(sum(i.size for i in ins) == b-a, 'decode truncation')
            for i in ins:
                require(all(old[i.address].get(k) == v for k, v in row(i).items()), 'source instruction')
            rs += ins
            summaries.append(dict(start=hex(a), end_exclusive=hex(b), sha256=sha(raw),
                fragment=[hex(x) for x in f], instructions=len(ins)))
        rs.sort(key=lambda i: i.address)
        by = {i.address: i for i in rs}
        g = {}
        for i in rs:
            nxt = i.address+i.size
            if i.mnemonic == 'ret':
                targets = []
            elif i.address == 0x142CEA3:
                targets = sorted(set(int(v, 16) for v in counter['switch_tail']['targets']))
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type == X86_OP_IMM, 'indirect jump')
                targets = [i.operands[0].imm] + ([] if i.mnemonic == 'jmp' else [nxt])
            else:
                targets = [nxt]
            require(all(v in by for v in targets), 'CFG exit')
            g[i.address] = targets
        require(reach(g, root) == set(by), 'root reachability')
        roots[root], graphs[root] = rs, g
        flat.update(by)
        root_proofs.append(dict(root=hex(root), fragments=summaries, instructions=len(rs)))
    pins, checks, defs = {}, [], {}

    def pin(at, asm):
        require(row(flat[at])['asm'] == asm, 'pin '+hex(at))
        pins[at] = row(flat[at])

    def rdcheck(root, reg, at, expected):
        if (root, reg) not in defs:
            defs[root, reg] = reaching(roots[root], graphs[root], reg)
        expected = {hex(v) for v in expected}
        require(defs[root, reg][at] == expected, 'definition '+hex(at)+' '+reg)
        checks.append(dict(root=hex(root), register=reg, at=hex(at), definitions=sorted(expected)))

    # Four new call-proven payload helper leaves. Only the -1 setter mode is
    # used in the 2E block. All writes are input-relative or local stack, with
    # no calls or global/selector writes. They do not emit pool nodes/events.
    helper_proofs = []
    for a, b in HELPERS.items():
        ins = list(im.md.disasm(im.read(a, b-a), a))
        require(sum(i.size for i in ins) == b-a, 'helper decode')
        g = normal_cfg(ins)
        require(reach(g, a) == {i.address for i in ins}, 'helper path closure')
        require(all(i.mnemonic != 'call' for i in ins), 'helper calls')
        stores = []
        for i in ins:
            for op in writes(i):
                base, index = i.reg_name(op.mem.base), i.reg_name(op.mem.index)
                require(base in ('rcx', 'rsp') and index in (None, 'rax'), 'nonlocal helper write')
                stores.append(row(i))
        helper_proofs.append(dict(start=hex(a), end_exclusive=hex(b), sha256=sha(im.read(a, b-a)),
            scope='Call-proven leaf including all return paths; padding excluded.', instructions=[row(i) for i in ins], stores=stores))
    emitter_code = {}
    for a, b in LEAVES.items():
        ins = list(im.md.disasm(im.read(a, b-a), a))
        for i in ins:
            require(all(old[i.address].get(k) == v for k, v in row(i).items()), 'emitter bytes')
        emitter_code[a] = {i.address: i for i in ins}
    emissions = {}
    for ident, (a, b) in GROUPS.items():
        ins = [i for i in roots[0x1258050] if a <= i.address < b]
        require(ins[0].address == a and ins[-1].address+ins[-1].size == b, 'group bounds')
        require(not any(i.mnemonic.startswith('j') for i in ins), 'nonlinear group')
        require(not [(x, y) for x, ys in graphs[0x1258050].items() for y in ys if a < y < b and not a <= x < b], 'alternate emission entry')
        for i in ins:
            for op in writes(i):
                require(i.reg_name(op.mem.base) in ('rbp','rsp') and not op.mem.index,
                    'emission block has nonlocal direct write')
        pin(a, f'mov ecx, {hex(ident)}')
        calls = [i for i in ins if i.mnemonic == 'call']
        require(calls[0].operands[0].imm == 0x1257720, 'missing selector')
        payload_calls = []
        for i in calls:
            target = i.operands[0].imm
            require(target in LEAVES or target in HELPERS, 'unknown group callee')
            if target in HELPERS:
                rcx_defs = reaching(roots[0x1258050], graphs[0x1258050], 'rcx')[i.address]
                require(len(rcx_defs) == 1, 'payload destination definition')
                src = flat[int(next(iter(rcx_defs)), 16)]
                require(src.mnemonic == 'lea' and src.reg_name(src.operands[1].mem.base) == 'rbp'
                    and not src.operands[1].mem.index, 'payload destination not local')
                info = dict(call=row(i), destination_definition=row(src))
                if target != 0xB6C30:
                    ds = reaching(roots[0x1258050], graphs[0x1258050], 'r8')[i.address]
                    require(len(ds) == 1, 'setter mode definition')
                    src8 = flat[int(next(iter(ds)), 16)]
                    require(row(src8)['asm'] == 'mov r8d, 0xffffffff', 'setter mode')
                    info['mode_definition'] = row(src8)
                payload_calls.append(info)
        cases = []
        for fill in (0, 0xA5):
            machine = Machine(emitter_code, ident)
            for i in calls:
                target = i.operands[0].imm
                if target in LEAVES:
                    machine.call(target, ident if target == 0x1257720 else INPUT, fill)
            p = BASE+ident*STRIDE
            n = machine.memory(p+COUNT, 4)
            cases.append(dict(nodes=n, types=[machine.memory(p+k*NODE, 4) for k in range(n)],
                events=[machine.memory(p+k*NODE+0xD64, 4) for k in range(n)], steps=machine.steps))
        require(cases[0] == cases[1], 'payload-dependent counts')
        emissions[hex(ident)] = dict(start=hex(a), end_exclusive=hex(b), instructions=[row(i) for i in ins],
            payload_calls=payload_calls, **cases[0])
    # Four loop-generated templates 29..2C. Payload floating arithmetic is not
    # emulated; count/ID loop and emitter effects are separately accounted for.
    for a, asm in {
        0x1258570: 'xor r12d, r12d', 0x1260642: 'mov ebx, r12d',
        0x1260655: 'lea ecx, [rbx + 0x29]', 0x1260691: 'call 0x1257720',
        0x126069D: 'call 0x1257c90', 0x12606A9: 'call 0x1257e00',
        0x12606B5: 'call 0x1257e00', 0x12606BA: 'inc ebx',
        0x12606BC: 'cmp ebx, 4', 0x12606BF: 'jb 0x1260650',
    }.items():
        pin(a, asm)
    rdcheck(0x1258050, 'r12', 0x1260642, [0x1258570])
    rdcheck(0x1258050, 'rbx', 0x1260655, [0x1260642, 0x12606BA])
    rdcheck(0x1258050, 'rcx', 0x1260691, [0x1260655])
    loop = [i for i in roots[0x1258050] if 0x1260642 <= i.address < 0x12606C1]
    require([i.operands[0].imm for i in loop if i.mnemonic=='call']==
        [0x1257720,0x1257C90,0x1257E00,0x1257E00], 'loop emitter sequence')
    require([i.address for i in loop if i.mnemonic.startswith('j')]==[0x12606BF], 'loop branches')
    for ident in range(0x29, 0x2D):
        cases = []
        for fill in (0, 0xA5):
            machine = Machine(emitter_code, ident)
            for target in (0x1257720, 0x1257C90, 0x1257E00, 0x1257E00):
                machine.call(target, ident if target == 0x1257720 else INPUT, fill)
            p = BASE+ident*STRIDE
            cases.append(dict(nodes=machine.memory(p+COUNT, 4), types=[machine.memory(p, 4)],
                events=[machine.memory(p+0xD64, 4)], steps=machine.steps))
        require(cases[0] == cases[1] and cases[0]['nodes'] == 1, 'loop template count')
        emissions[hex(ident)] = dict(loop_ordinal=ident-0x29, **cases[0])
    require({k: v['nodes'] for k, v in emissions.items()} == {
        '0x1c': 1, '0x2d': 1, '0x2e': 2, '0x24': 3, '0x25': 3,
        '0x26': 2, '0x27': 2, '0x28': 2, '0x29': 1, '0x2a': 1, '0x2b': 1, '0x2c': 1}, 'cardinality changed')

    # Count/domain source and same-record update call.
    source_pins = {
        0x142CBBA:'mov rdi, rcx', 0x142CC21:'xorps xmm0, xmm0', 0x142CC37:'xor r12d, r12d',
        0x142CC5C:'mov r14d, 0x25', 0x142CC7E:'mov dword ptr [rsp + 0x38], r14d',
        0x142CD27:'mov r14d, 0x24', 0x142CD2D:'mov dword ptr [rsp + 0x38], r14d',
        0x142CF4D:'mov eax, dword ptr [rdi + 0x8b730]', 0x142CF53:'cmp eax, 0x20',
        0x142CF56:'jae 0x142d5cf', 0x142CFB9:'cmp byte ptr [rax + 0xa84], r12b',
        0x142CFC0:'jne 0x142d01d', 0x142CFCA:'mov r8d, dword ptr [rdi + 0x8b730]',
        0x142CFE9:'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x27',
        0x142CFF7:'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x28',
        0x142D005:'mov dword ptr [rdi + r8*4 + 0x8b6b0], 0x26',
        0x142D013:'mov dword ptr [rdi + r8*4 + 0x8b6b0], r14d',
        0x142D01D:'mov ecx, dword ptr [rdi + 0x8b730]',
        0x142D023:'mov eax, dword ptr [rbp + rcx*4 - 0x60]', 0x142D027:'add eax, 0x29',
        0x142D02A:'mov dword ptr [rdi + rcx*4 + 0x8b6b0], eax',
        0x142D031:'mov eax, dword ptr [rdi + 0x8b730]', 0x142D041:'inc dword ptr [rbp + rax*4 - 0x60]',
        0x142D193:'mov eax, dword ptr [rdi + 0x8b730]', 0x142D1A9:'inc eax',
        0x142D1B2:'mov dword ptr [rdi + 0x8b730], eax', 0x142D1D0:'mov r14d, dword ptr [rsp + 0x38]',
        0x142E311:'cmp dword ptr [r14 + 0x8b730], 0', 0x142E320:'mov ecx, ebx',
        0x142E322:'mov byte ptr [rsp + 0x30], 1', 0x142E327:'mov byte ptr [rsp + 0x28], 1',
        0x142E333:'mov r9d, dword ptr [r14 + rcx*4 + 0x8b6b0]',
        0x142E33B:'lea r8, [rcx + rcx*2]', 0x142E33F:'shl r8, 7',
        0x142E343:'add r8, 0x886b0', 0x142E34A:'add r8, r14',
        0x142E34D:'call 0x142f530', 0x142E352:'inc ebx',
        0x142E354:'cmp ebx, dword ptr [r14 + 0x8b730]', 0x142E35B:'jb 0x142e320',
    }
    for a, asm in source_pins.items():
        pin(a, asm)
    for reg, at, sources in [
        ('rax',0x142CF53,[0x142CF4D]), ('r14',0x142D013,[0x142CC5C,0x142CD27,0x142D1D0]),
        ('r14',0x142CC7E,[0x142CC5C]), ('r14',0x142CD2D,[0x142CD27]),
        ('rcx',0x142D023,[0x142D01D]), ('rax',0x142D027,[0x142D023]),
        ('rax',0x142D02A,[0x142D027]), ('rax',0x142D041,[0x142D031]),
        ('rax',0x142D1A9,[0x142D193]), ('rax',0x142D1B2,[0x142D1A9]),
    ]:
        rdcheck(0x142CB90,reg,at,sources)
    rdcheck(0x142D870, 'r9', 0x142E34D, [0x142E333])
    rdcheck(0x142D870, 'r8', 0x142E34D, [0x142E34A])
    g = graphs[0x142CB90]
    guarded = (0x142CFE9,0x142CFF7,0x142D005,0x142D013,0x142D02A,0x142D1B2)
    cut = reach(g,0x142CB90,omit=(0x142CF56,0x142CF5C))
    require(all(a not in cut for a in guarded), 'guard bypass')
    for a in guarded:
        rdcheck(0x142CB90,'rdi',a,[0x142CBBA])
    # Stack layout: RBP=entry RSP-1E8, current RSP=entry RSP-2E8.
    pin(0x142CB93,'lea rbp, [rsp - 0x1d8]')
    pin(0x142CB9B,'sub rsp, 0x2d8')
    initializers = []
    for at, disp in zip(range(0x142CCE1,0x142CD01,4),range(-0x60,0x20,0x10)):
        i = flat[at]
        require(i.mnemonic=='movups' and i.operands[0].mem.disp==disp and i.op_str.endswith(', xmm0'), 'stack clear')
        rdcheck(0x142CB90,'xmm0',at,[0x142CC21])
        require(0x142D023 not in reach(g,0x142CB90,omit=(at,at+i.size)), 'initialization does not dominate')
        initializers.append(row(i))
    phase = reach(g,0x142CDE0,stops=(0x142D1E7,))-{0x142D1E7}
    setup_and_phase = reach(g,0x142CC21,stops=(0x142D1E7,))-{0x142D1E7}
    saved_template_writes=[]
    for at in sorted(setup_and_phase):
        for op in writes(flat[at]):
            if flat[at].reg_name(op.mem.base)=='rsp' and not op.mem.index and op.mem.disp<=0x38<op.mem.disp+op.size:
                saved_template_writes.append(at)
    require(saved_template_writes==[0x142CC7E,0x142CD2D], 'saved fixed template aliases')
    stack_writes = []
    for at in sorted(phase):
        i = flat[at]
        for op in writes(i):
            base = i.reg_name(op.mem.base)
            if base not in ('rbp','rsp'):
                continue
            disp = op.mem.disp+(0x100 if base=='rbp' else 0)
            if op.mem.index:
                require(at==0x142D041 and disp==0xA0 and op.mem.scale==4,'unclassified indexed stack write')
            elif disp < 0x120 and 0xA0 < disp+op.size:
                raise ValueError('another local-counter write '+hex(at))
            stack_writes.append(row(i))
    require(0x142D023 not in reach(g,0x142D041,stops=(0x142D1B2,)), 'local slot can be reused before count commit')
    # All direct exact-field stores found by the finite scan: reset and commit.
    refs = prior['indexed_float_pool_triple_refs_discovery.json']['offsets']
    c_writes=[r for r in refs['0x8b730']['references'] if r['access']&CS_AC_WRITE]
    t_writes=[r for r in refs['0x8b6b0']['references'] if r['access']&CS_AC_WRITE]
    require({int(r['rva'],16) for r in c_writes}=={0x142BFC8,0x142D1B2}, 'counter scan writers')
    require({int(r['rva'],16) for r in t_writes}==set(guarded[:-1]), 'template table writers')
    # Conditional induction: each accepted append uses the next increasing
    # ordinal once; its fresh per-call local counter is zero, then increments.
    induction=[]
    for initial in range(33):
        local=[0]*32;count=initial;generated=[]
        while count<32:
            n=count;generated.append(0x29+local[n]);local[n]+=1;count+=1
        require(all(v==0x29 for v in generated),'conditional template domain')
        induction.append(dict(initial_count=initial,final_count=count,appends=len(generated),
            dynamic_templates=sorted(set(hex(v) for v in generated))))

    # Cardinality/ID model of 140C2E0, from the pinned subobject evidence:
    # same ID early return; differing nonzero ID frees old nodes; requested ID
    # stored before allocation; full pool returns with partial allocation.
    counts={int(k,16):v['nodes'] for k,v in emissions.items()};counts[0x1B]=1
    expected={t:[counts[t],counts[0x1B+(t==0x28)],counts[0x2D+(t==0x28)]] for t in range(0x24,0x2D)}
    require(max(sum(v) for v in expected.values())==5,'stable triple count')
    transition_pin_asms={
        0x142F562:'call 0x142f780',0x142F596:'call 0x140c2e0',0x142F6D4:'jmp 0x142f6e0',
        0x142D0AF:'lea rcx, [rbx + 0x886c0]',
        0x142D0B6:'mov edx, dword ptr [rdi + rax*4 + 0x8b6b0]',
        0x142D0BD:'call 0x140c2e0',0x142D12B:'lea rcx, [rdi + 0x887b0]',
        0x142D135:'add rcx, r14',0x142D138:'add eax, -2',0x142D13B:'cmp eax, 2',
        0x142D13E:'setbe dl',0x142D141:'add edx, 0x2d',0x142D144:'call 0x140c2e0',
        0x140C2E8:'mov eax, dword ptr [rcx + 0x1c]',0x140C2F0:'cmp eax, edx',
        0x140C2F2:'je 0x140c4b3',0x140C306:'call 0x140c200',
        0x140C319:'mov dword ptr [r14 + 0x1c], ebx',0x140C38B:'jmp 0x140c495',
        0x140C3A1:'inc dword ptr [r9 + 0x10]',0x140C3AF:'inc dword ptr [r14 + 0x58]',
    }
    transition_pins=[]
    for at,asm in transition_pin_asms.items():
        i=im.instruction(at)
        require(i is not None and row(i)['asm']==asm and
            all(old[at].get(k)==v for k,v in row(i).items()),'transition source pin')
        transition_pins.append(row(i))
    transitions=[]
    scenarios=[
        ('helper_24_to_28', [0x24,0x1B,0x2D], [0x28,0x1C,0x2E],
         [(1,0x1C),(2,0x2E),(0,0x28)], [2,1,1],
         'Local 142F530 input-state example only; the builder may already replace primary before this helper is called.'),
        ('builder_28_to_24_then_helper', [0x28,0x1C,0x2E], [0x24,0x1B,0x2D],
         [(0,0x24),(2,0x2D),(1,0x1B),(2,0x2D),(0,0x24)], [2,1,1],
         '142D0BD primary request precedes optional 142D144 tertiary request. Model assumes that optional branch runs with source state 0, plus later helper update. Global reachability of old/new game states is not proved.'),
    ]
    for name,initial_ids,target_ids,sequence,incomplete,limit in scenarios:
      for capacity in (5,6):
        ids=list(initial_ids);owned=[counts[t] for t in ids];initial_owned=list(owned)
        used=sum(owned);peak=used;events=[]

        def update(index,ident):
            nonlocal used,peak
            if ids[index]==ident:
                events.append(dict(S=index,requested=hex(ident),same_id_skip=True,used=used,owned=list(owned)))
                return
            used-=owned[index];owned[index]=0;ids[index]=ident
            for _ in range(counts[ident]):
                if used>=capacity:
                    break
                used+=1;owned[index]+=1;peak=max(peak,used)
            events.append(dict(S=index,requested=hex(ident),used=used,owned=list(owned),
                complete=owned[index]==counts[ident]))

        for k,t in sequence:
            update(k,t)
        first_owned=list(owned)
        for k in (1,2,0):
            t=target_ids[k]
            update(k,t)
        require(owned==first_owned,'same ID unexpectedly retried')
        complete=[counts[t] for t in target_ids]
        require((peak,used,owned)==((5,4,incomplete) if capacity==5 else (6,5,complete)),'transition')
        transitions.append(dict(scenario=name,capacity=capacity,initial_ids=[hex(t) for t in initial_ids],initial_owned=initial_owned,
            target_ids=[hex(t) for t in target_ids],peak=peak,final_used=used,final_owned=list(owned),steps=events,
            model_only=True,external_resource_effects_not_executed=True,reachability_limit=limit))
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,dependency_sha256=DEP,
        runtime_verified=False,native_execution=False,complete_roots=root_proofs,
        helper_leaves=helper_proofs,template_emissions=emissions,template_loop=[row(i) for i in loop],
        semantic_pins=list(pins.values()),reaching_definitions=checks,
        selection_slice=[row(i) for i in roots[0x142CB90] if 0x142CFC2<=i.address<0x142D045],
        guard_pass_edge_required=True,local_zero_initializers=initializers,phase_stack_writes=stack_writes,
        finite_count_writers=c_writes,finite_template_writers=t_writes,conditional_domain_induction=induction,
        caller=dict(site='0x142e34d',record_base='D+886B0+n*180',template_table='D+8B6B0+n*4',
            count='D+8B730',flags=[1,1],subobjects=['record+10','record+88','record+100']),
        budgets=dict(stable_requested_counts={hex(k):v for k,v in expected.items()},
            conditional_stable_max_per_record=5,conditional_stable_32_records=160,
            independent_subobject_maxima=[3,1,2],conditional_retained_upper_per_record=6,
            conditional_independent_32_upper=192,
            not_a_total_pool_bound=True,transition_order=['secondary','tertiary','primary']),
        transitions=transitions,transition_source_pins=transition_pins,
        preconditions=[
            'Fixed capture, valid object/stack addresses, saved initializer semantics and matching runtime templates.',
            'Synthetic emitter inputs are zero/A5 with valid fresh elements and input event +E4=0; real payloads are not reconstructed.',
            'Helper leaves receive disjoint local payload pointers; only the observed -1 setters are used in the 2E block.',
            'Builder count initially in 0..32; opaque callees do not mutate D+8B730, its template table or the caller local counter array.',
            'Only discovered count writes act; no computed alias, concurrent/reentrant mutation, or exception changes the induction.',
            'The local slot induction constrains newly appended rows. Existing rows require previously valid template contents.',
            'Primary template domain for this budget is 24..2C. The builder also requests primary ID0; its cardinality and unknown callers are outside this bound.',
            'Retained per-record upper 6 combines separate S maxima. Multiplying by 32 is a conditional envelope, not proof it occurs concurrently.',
            'Transition model assumes valid unique ownership and successful old-node cleanup; it counts nodes, not engine resource effects.',
        ],
        not_closed=['Opaque builder callees, remaining callers/aliases, actual template equivalence and global pool lifetime peak.',
                    'Native eight-player patch, platform/handle constraints and multiplayer validation.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),
        root_instructions={v['root']:v['instructions'] for v in root_proofs},
        helper_instructions=sum(len(v['instructions']) for v in helper_proofs),
        templates={k:v['nodes'] for k,v in emissions.items()},reaching_checks=len(checks),
        transition_peaks=[v['peak'] for v in transitions])))


if __name__=='__main__':
    main()
