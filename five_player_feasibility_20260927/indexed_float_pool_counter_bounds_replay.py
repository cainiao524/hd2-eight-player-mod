"""Prove selected stored-count guards and reset/cache semantics offline.

This inspects saved x64 instructions and their CFG. It does not execute native
code, query a process, or assert that the finite displacement scan is exhaustive.
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
    'indexed_float_pool_lifecycle_inventory_evidence.json': '7722b443b293e565b1600fccbbb8820c0ef01e281f86aac237abb1419e20fda6',
    'indexed_float_pool_optional_members_evidence.json': '2f955ad49c85cf0b1e24379c2fb3d8b75e15da6b6957ddda29b250af2429f436',
    'indexed_float_pool_counter_refs_discovery.json': 'e28dbc45b885146b6c8b70aeb9a364d8078647487e10f5227d7751aadc6d83cd',
    'indexed_float_pool_counter_cache_refs_discovery.json': 'c97c14d2a86e8bae3fbdba4fe23f1665e51ba88aec12f1729272ffdff8a78b53',
}
DEP = {'indexed_float_pool_initial_zero_replay.py': '38e9946c23f846d39cb99f8a394ea7ebdc8605bed26135e8a1214ef0f77db4dc'}
ROOTS = {0x142BED0: 0x142C89E, 0x142CB90: 0x142D864, 0x142D870: 0x142EE66}
# field, capacity, load, count-register, cmp, jae, reject, record LEA,
# record store, increment, record base, metadata store (optional), metadata base.
APPENDS = [
    (0x87D88, 64, 0x142CE38, 'rcx', 0x142CE3E, 0x142CE41, 0x142CECE,
     0x142CE54, 0x142CE80, 0x142CEC3, 0x81C88, 0x142CEBC, 0x87C88),
    (0x88524, 5, 0x142CEE1, 'rdx', 0x142CEE7, 0x142CEEA, 0x142CF44,
     0x142CEF4, 0x142CF20, 0x142CF36, 0x87D90, 0x142CF2E, 0x88510),
    (0x886AC, 1, 0x142D5DE, 'rdx', 0x142D5E4, 0x142D5E7, 0x142D642,
     0x142D5F1, 0x142D61A, 0x142D637, 0x88528, 0x142D630, 0x886A8),
    (0x8D6C0, 1, 0x142D64B, 'rcx', 0x142D65C, 0x142D65F, 0x142D1D0,
     0x142D66D, 0x142D699, 0x142D6A1, 0x8D540, None, None),
    (0x88524, 5, 0x142D791, 'rax', 0x142D797, 0x142D79A, 0x142D7CB,
     0x142D79C, 0x142D7AC, 0x142D7C5, 0x87D90, 0x142D7BA, 0x88510),
]
RESETS = {0x8D6C0: 0x142BFC2, 0x87D88: 0x142BFCE, 0x88524: 0x142BFD4, 0x886AC: 0x142BFDA}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def reach(g, start, omit=None, stops=()):
    seen = set()
    todo = [start]
    while todo:
        a = todo.pop()
        if a not in seen:
            seen.add(a)
            if a not in stops:
                todo.extend(b for b in g[a] if (a, b) != omit)
    return seen


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = Path(args.output)
    require(not out.exists(), 'refusing overwrite')
    for name, digest in DEP.items():
        require(sha((HERE / name).read_bytes()) == digest, 'dependency changed')
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
        require(sha(raw) == digest, 'prior changed: ' + name)
        prior[name] = json.loads(raw)
        collect(prior[name])
    im = Image(args.evidence)
    roots, graphs, spans, flat = {}, {}, {}, {}
    table_raw = im.read(0x142D831, 0x33)
    require(sha(table_raw) == 'abfcc71e0a91e2fa50e012c094e93af404bd4dceaeead721ebfb583b50ccd5bf', 'switch tail changed')
    table = list(struct.unpack('<12I', table_raw[3:]))
    require(table == [0x142CEA5, 0x142CEB6, 0x142CEAA, 0x142CEB1] * 3, 'switch values')
    for root, end in ROOTS.items():
        fs = [f for f in im.functions if im.root(f[0])[0] == root]
        require(fs[0][0] == root and fs[-1][1] == end, 'unwind family bounds')
        require(all(a[1] == b[0] for a, b in zip(fs, fs[1:])), 'family gap')
        ins = []
        for f in fs:
            stop = min(f[1], 0x142D831) if root == 0x142CB90 else f[1]
            raw = im.read(f[0], stop - f[0])
            rs = list(im.md.disasm(raw, f[0]))
            require(sum(i.size for i in rs) == len(raw), 'decode closure')
            for i in rs:
                require(i.address in old and all(old[i.address].get(k) == v for k, v in row(i).items()), 'prior instruction mismatch')
            spans[hex(f[0])] = dict(root=hex(root), fragment=[hex(v) for v in f],
                start=hex(f[0]), end_exclusive=hex(stop), sha256=sha(raw), instructions=[row(i) for i in rs])
            ins += rs
        by = {i.address: i for i in ins}
        g = {}
        for i in ins:
            nxt = i.address + i.size
            if i.mnemonic == 'ret':
                targets = []
            elif i.address == 0x142CEA3:
                require(row(i)['asm'] == 'jmp rcx', 'switch dispatch')
                targets = sorted(set(table))
            elif i.mnemonic.startswith('j'):
                require(i.operands[0].type == X86_OP_IMM, 'unknown indirect branch')
                targets = [i.operands[0].imm] + ([] if i.mnemonic == 'jmp' else [nxt])
            else:
                targets = [nxt]
            require(all(a in by for a in targets), 'unclassified CFG exit')
            g[i.address] = targets
        require(reach(g, root) == set(by), 'unreachable code')
        roots[root], graphs[root] = ins, g
        flat.update(by)

    pins = {}

    def pin(at, asm):
        require(row(flat[at])['asm'] == asm, 'semantic pin ' + hex(at))
        pins[at] = row(flat[at])

    rd = {}
    checks = []

    def rdcheck(root, reg, at, expected):
        key = (root, reg)
        if key not in rd:
            rd[key] = reaching(roots[root], graphs[root], reg)
        expected = {expected} if isinstance(expected, str) else {hex(expected)}
        require(rd[key][at] == expected, 'reaching definition ' + hex(at) + ' ' + reg)
        checks.append(dict(root=hex(root), register=reg, at=hex(at), definitions=sorted(expected)))

    pin(0x142BEF6, 'mov rbx, rcx')
    pin(0x142CBBA, 'mov rdi, rcx')
    pin(0x142BFAC, 'xor ecx, ecx')
    pin(0x142D8B6, 'mov rsi, rcx')
    append_proofs = []
    for field, cap, load, reg, cmp_at, branch, reject, scale, write, inc, base, meta_write, meta in APPENDS:
        g = graphs[0x142CB90]
        dreg = {'rcx': 'ecx', 'rdx': 'edx', 'rax': 'eax'}[reg]
        pin(load, f'mov {dreg}, dword ptr [rdi + {hex(field)}]')
        pin(cmp_at, f'cmp {dreg}, {hex(cap) if cap > 9 else cap}')
        pin(branch, f'jae {hex(reject)}')
        pin(scale, f'lea rcx, [{reg} + {reg}*2]')
        shift = next(i for i in roots[0x142CB90] if scale < i.address < write and i.mnemonic == 'shl' and i.op_str == 'rcx, 7')
        pin(shift.address, 'shl rcx, 7')
        pin(write, f'mov qword ptr [rcx + rdi + {hex(base)}], rax')
        pin(inc, f'inc dword ptr [rdi + {hex(field)}]')
        require(cmp_at + flat[cmp_at].size == branch, 'intervening flags writer')
        rdcheck(0x142CB90, reg, cmp_at, load)
        rdcheck(0x142CB90, reg, scale, load)
        rdcheck(0x142CB90, 'rcx', shift.address, scale)
        rdcheck(0x142CB90, 'rcx', write, shift.address)
        passed = branch + flat[branch].size
        stop = inc + flat[inc].size
        region = reach(g, load, stops=(reject, stop)) - {reject, stop}
        require(inc in region and all(a in region or a in (reject, stop) for x in region for a in g[x]), 'append region exits')
        incoming = [(a, b) for a, bs in g.items() for b in bs if b in region and a not in region and b != load]
        require(not incoming, 'append window has alternate entry')
        require(inc not in reach(g, 0x142CB90, omit=(branch, passed)), 'increment bypasses guard')
        require(write not in reach(g, 0x142CB90, omit=(branch, passed)), 'record store bypasses guard')
        require(all(flat[a].mnemonic != 'call' for a in region), 'opaque mutation inside guarded append')
        # Require the region to be acyclic, so an accepted count cannot be used
        # again for a later append without returning through its load/guard.
        active, done = set(), set()

        def acyclic(a):
            if a not in region or a in done:
                return
            require(a not in active, 'append cycle')
            active.add(a)
            for b in g[a]:
                acyclic(b)
            active.remove(a)
            done.add(a)

        acyclic(load)
        owner_writes = []
        for at in sorted(region):
            i = flat[at]
            for op in i.operands:
                if op.type != X86_OP_MEM or not op.access & CS_AC_WRITE:
                    continue
                bname, iname = i.reg_name(op.mem.base), i.reg_name(op.mem.index)
                if bname in ('rsp', 'rbp') and not op.mem.index:
                    continue
                require(at in (write, inc, meta_write), 'unclassified append memory write')
                owner_writes.append(row(i))
                rdcheck(0x142CB90, 'rdi', at, 0x142CBBA)
                if at == meta_write:
                    require(op.size == 4 and bname == 'rdi' and iname in ('rax', 'rcx')
                        and op.mem.scale == 4 and op.mem.disp == meta, 'metadata target')
                    defs = reaching(roots[0x142CB90], g, iname)[at]
                    require(len(defs) == 1, 'metadata index multiple definitions')
                    load_at = int(next(iter(defs)), 16)
                    want = 'eax' if iname == 'rax' else 'ecx'
                    pin(load_at, f'mov {want}, dword ptr [rdi + {hex(field)}]')
                    require(load_at in region, 'metadata count loaded outside accepted window')
        require(len(owner_writes) == (3 if meta is not None else 2), 'write inventory')
        data_end = base + cap * 0x180
        require(data_end == (meta if meta is not None else field), 'physical record limit')
        if meta is not None:
            require(meta + cap * 4 == field, 'metadata extent')
        # This enumerates every accepted count and checks both indexed write
        # ranges. The instruction checks above justify scale=3*128 and +1.
        cases = []
        for n in range(cap):
            start = base + n * 0x180
            require(base <= start and start + 8 <= data_end, 'record range')
            if meta is not None:
                require(meta + n * 4 + 4 <= field, 'metadata range')
            require(n + 1 <= cap, 'bounded increment')
            cases.append(dict(before=n, after=n + 1, data_write=[hex(start), hex(start + 8)],
                metadata_write=None if meta is None else [hex(meta+n*4), hex(meta+n*4+4)]))
        append_proofs.append(dict(counter=hex(field), capacity=cap, load=hex(load), cmp=hex(cmp_at),
            branch=hex(branch), reject=hex(reject), increment=hex(inc),
            guard_pass_edge_required=True, region_acyclic=True, alternate_entries=[], calls_inside=[],
            region_instructions=[hex(a) for a in sorted(region)], owner_writes=owner_writes,
            record_extent=[hex(base), hex(data_end)],
            metadata_extent=None if meta is None else [hex(meta), hex(field)], cases=cases,
            rejected_u32_interval=[cap, 0xffffffff],
            interpretation='Unsigned count >= capacity skips this append. Existing invalid counts are not repaired.'))

    # Every writable encoded-displacement match in the saved finite scan is one
    # of the four resets or five guarded increments; this is not all aliases.
    refs = prior['indexed_float_pool_counter_refs_discovery.json']['offsets']
    scanned_writes = [r for v in refs.values() for r in v['references'] if r['access'] & CS_AC_WRITE]
    want_writes = set(RESETS.values()) | {v[9] for v in APPENDS}
    require({int(r['rva'], 16) for r in scanned_writes} == want_writes, 'new direct counter writer')
    for field, at in RESETS.items():
        pin(at, f'mov dword ptr [rbx + {hex(field)}], ecx')
        rdcheck(0x142BED0, 'rbx', at, 0x142BEF6)
        rdcheck(0x142BED0, 'rcx', at, 0x142BFAC)

    # Audit only the post-call reset suffix. Earlier calls remain opaque. All
    # suffix stores are either fixed D offsets or fixed local stack slots.
    lifecycle = prior['indexed_float_pool_lifecycle_inventory_evidence.json']['scenarios']['original']
    ss = [int(v['S'], 16) - 0x10000000 for v in lifecycle['constructor_visits']]
    require(len(ss) == len(set(ss)) == 305, 'S inventory')
    protected = [(s, s + 0x78) for s in ss] + [(0x36F8, 0x24018)]
    suffix = [i for i in roots[0x142BED0] if 0x142BFA2 <= i.address < 0x142C88B]
    require(all(not i.mnemonic.startswith('j') and i.mnemonic != 'call' for i in suffix), 'nonlinear reset suffix')
    stores = []
    for i in suffix:
        for op in i.operands:
            if op.type != X86_OP_MEM or not op.access & CS_AC_WRITE:
                continue
            bname = i.reg_name(op.mem.base)
            require(not op.mem.index and bname in ('rbx', 'rsp'), 'unclassified reset write')
            if bname == 'rsp':
                continue
            rdcheck(0x142BED0, 'rbx', i.address, 0x142BEF6)
            a, b = op.mem.disp, op.mem.disp + op.size
            require(not any(a < y and x < b for x, y in protected), 'reset suffix changes pool or S')
            stores.append(dict(instruction=row(i), D_interval=[hex(a), hex(b)]))
    # This flag controls the discovered builder call; other flag invalidators
    # exist in the finite scan and are deliberately not treated as understood.
    flag_pins = {
        0x142BFE0: 'mov byte ptr [rbx + 0x8d709], cl',
        0x142D7CB: 'mov byte ptr [rdi + 0x8d709], 1',
        0x142D965: 'cmp byte ptr [rsi + 0x8d709], 0',
        0x142D970: 'jne 0x142d97a',
        0x142D972: 'mov rcx, rsi',
        0x142D975: 'call 0x142cb90',
        0x142D8BE: 'cmp byte ptr [rsi + 0x80d9c], 0',
        0x142D8C5: 'jne 0x142d8ed',
        0x142D8E0: 'mov rcx, rsi',
        0x142D8E3: 'call 0x142bed0',
        0x142D8E8: 'jmp 0x142ee3d',
    }
    for a, s in flag_pins.items():
        pin(a, s)
    rdcheck(0x142BED0, 'rcx', 0x142BFE0, 0x142BFAC)
    rdcheck(0x142CB90, 'rdi', 0x142D7CB, 0x142CBBA)
    for at in (0x142D965, 0x142D972, 0x142D8E0):
        rdcheck(0x142D870, 'rsi', at, 0x142D8B6)
    rdcheck(0x142D870, 'rcx', 0x142D975, 0x142D972)
    rdcheck(0x142D870, 'rcx', 0x142D8E3, 0x142D8E0)
    require(0x142D975 not in reach(graphs[0x142D870], 0x142D870, omit=(0x142D970, 0x142D972)), 'builder not gated')
    require(0x142D8E3 not in reach(graphs[0x142D870], 0x142D870, omit=(0x142D8C5, 0x142D8C7)), 'reset branch not gated')
    cache_refs = prior['indexed_float_pool_counter_cache_refs_discovery.json']['offsets']['0x8d709']['references']
    result = dict(schema_version=1, source_sha256=EXPECTED, prior_sha256=PRIOR, dependency_sha256=DEP,
        runtime_verified=False, native_execution=False, code_spans=spans,
        switch_tail=dict(start='0x142d831', end_exclusive='0x142d864', bytes=table_raw.hex(),
            sha256=sha(table_raw), targets=[hex(v) for v in table], proof_inherited='indexed_float_consumers_evidence.json'),
        instruction_counts={hex(k): len(v) for k, v in roots.items()},
        semantic_pins=list(pins.values()), reaching_definitions=checks,
        append_proofs=append_proofs, finite_counter_scan_writes=scanned_writes,
        reset_suffix=dict(start='0x142bfa2', end_exclusive='0x142c88b', stores=stores,
            preserved_direct_S_count=305, protected_pool_interval=['0x36f8', '0x24018'],
            calls_inside=0, overlap_with_protected_intervals=0,
            limit='Earlier reset-function callees are not included; no claim about their effects or external concurrent writers.'),
        cache_flag=dict(D_offset='0x8d709', reset_zero='0x142bfe0', built_one='0x142d7cb',
            zero_required_for_builder_call='0x142d975', conditional_reset='0x142d8e3',
            finite_references=cache_refs, unclassified_flag_writer_sites=['0x72336a', '0x724e4e', '0x142c940']),
        conditional_invariant=[
            'If the four counters start in [0, capacity], their four zero stores and five guarded appends preserve those bounds.',
            'No concurrent/reentrant/opaque alias writer changes a counter between its guard and store. Guarded append windows contain no calls.',
            'The nine encoded-disp32 writers are a finite discovered set, not proof that no computed-address or uncaptured writer exists.',
            'Already-invalid counters are skipped by each append guard, not clamped; readers remain dependent on valid counts.',
            'The no-call reset suffix clears counts and the cached-builder flag without writing any of the 305 inventoried S objects or the pool region.',
            '72 remains a subset requested-template budget, not total live/retained occupancy; eight-player functionality remains unverified.',
        ])
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(out), sha256=sha(out.read_bytes()),
        instructions=result['instruction_counts'], guarded_appends=len(append_proofs),
        accepted_count_cases=sum(len(v['cases']) for v in append_proofs),
        reaching_checks=len(checks), reset_owner_stores=len(stores))))


if __name__ == '__main__':
    main()
