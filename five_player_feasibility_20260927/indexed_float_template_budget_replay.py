"""Offline replay of four player-record template emission blocks.

Reads only the pinned saved capture and prior evidence. Executes a small Python
instruction model on synthetic bytes; never executes or loads game code. The
result is conditional on the observed initializer's templates being the ones
used at runtime. Other writers, initialization ordering and pool users remain
outside this proof.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone import CS_AC_WRITE
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

BASE = 0x3492F20
SELECTOR = 0x346D248
STRIDE = 0xA0E8
COUNT = 0xA0E0
NODE = 0xD68
EVENT = 0xFC
INPUT = 0x600000000
LEAVES = {
    0x1257720: 0x125774B,  # select template / reset its node count
    0x1257830: 0x12578D4,  # append type 1
    0x1257C90: 0x1257D44,  # append type 2
    0x1257E00: 0x1257EE9,  # append event to last node
    0x1257EF0: 0x125803D,  # append secondary payload; BOTH return paths
}
GROUPS = {
    0x17: (0x125EA82, 0x125EBA9),
    0x18: (0x125EC6E, 0x125ECA8),
    0x19: (0x125EE51, 0x125EEA3),
    0x1B: (0x125F404, 0x125F44A),
}
PRIOR = {
    'indexed_float_consumers_evidence.json': '503050c1fbd198ff4e751df80a5b8fa6d349d2bf992ecb9c4a0a050a8a6b6578',
    'indexed_float_subobjects_evidence.json': '5468aca4b6b456c8714e0cf922fe3e473fe2de2b4dbebc2531118eb8c737bf54',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def normal_cfg(instructions):
    by = {i.address: i for i in instructions}
    edges = {}
    for i in instructions:
        nxt = i.address + i.size
        if i.mnemonic == 'ret':
            out = []
        elif i.mnemonic.startswith('j'):
            require(i.operands[0].type == X86_OP_IMM, 'indirect branch')
            out = [i.operands[0].imm]
            if i.mnemonic != 'jmp':
                out.append(nxt)
        else:
            out = [nxt]
        require(all(x in by for x in out), 'branch/fallthrough outside code span')
        edges[i.address] = out
    seen, pending = set(), [instructions[0].address]
    while pending:
        n = pending.pop()
        if n not in seen:
            seen.add(n)
            pending.extend(edges[n])
    require(seen == set(by), 'unreachable decoded instructions')
    return edges


class Machine:
    """Integer address/counter and byte-copy subset used by the five leaves.

    This is not a general emulator. Unsupported opcodes, unknown register reads
    and out-of-region memory fail closed. The only interpreted branches are
    JE/JNE. SIMD MOVs copy raw bytes; no native or floating-point execution.
    """
    def __init__(self, decoded, template_id):
        self.decoded = decoded
        self.regs = {}
        self.regions = [(BASE, bytearray(73 * STRIDE)),
                        (SELECTOR, bytearray(4)), (INPUT, bytearray(0x400))]
        self.template_id = template_id
        self.zf = None
        self.branches = set()
        self.writes = []
        self.steps = 0

    def memory(self, address, size, value=None):
        for base, data in self.regions:
            at = address - base
            if 0 <= at and at + size <= len(data):
                if value is None:
                    return int.from_bytes(data[at:at+size], 'little')
                self.writes.append((address, size))
                data[at:at+size] = (value & ((1 << (size*8))-1)).to_bytes(size, 'little')
                return
        raise ValueError('synthetic memory access outside regions: ' + hex(address))

    @staticmethod
    def alias(name):
        aliases = {'eax':'rax', 'ebx':'rbx', 'ecx':'rcx', 'edx':'rdx',
                   'esi':'rsi', 'edi':'rdi', 'ebp':'rbp', 'esp':'rsp'}
        if name in aliases:
            return aliases[name], 32
        if name.startswith('r') and name.endswith('d') and name[1:-1].isdigit():
            return name[:-1], 32
        return name, 128 if name.startswith('xmm') else 64

    def getreg(self, name):
        name, bits = self.alias(name)
        require(name in self.regs, 'unknown register read ' + name)
        return self.regs[name] & ((1 << bits)-1)

    def setreg(self, name, value):
        name, bits = self.alias(name)
        self.regs[name] = value & ((1 << bits)-1)

    def address(self, i, op):
        m = op.mem
        base = i.address+i.size if i.reg_name(m.base) == 'rip' else (self.getreg(i.reg_name(m.base)) if m.base else 0)
        index = self.getreg(i.reg_name(m.index)) if m.index else 0
        return (base + index*m.scale + m.disp) & ((1 << 64)-1)

    def read(self, i, op):
        if op.type == X86_OP_IMM:
            return op.imm
        if op.type == X86_OP_REG:
            return self.getreg(i.reg_name(op.reg))
        require(op.type == X86_OP_MEM, 'unsupported read operand')
        return self.memory(self.address(i, op), op.size)

    def write(self, i, op, value):
        if op.type == X86_OP_REG:
            self.setreg(i.reg_name(op.reg), value)
        else:
            require(op.type == X86_OP_MEM, 'unsupported write operand')
            self.memory(self.address(i, op), op.size, value)

    def call(self, entry, rcx=INPUT, fill=0):
        require(entry in LEAVES, 'unsupported call')
        self.regs = {'rcx':rcx, 'xmm1':0x3F800000}
        # Arbitrary payload bytes, with a valid zero secondary count for events.
        # This is a synthetic precondition, not reconstructed game stack data.
        self.regions[-1][1][:] = bytes([fill]) * 0x400
        self.memory(INPUT+0xE4, 4, 0)
        pc, steps = entry, 0
        while True:
            require(pc in self.decoded[entry], 'instruction outside proven leaf')
            i = self.decoded[entry][pc]
            op, m = i.operands, i.mnemonic
            nxt = pc + i.size
            steps += 1
            require(steps < 2000, 'step limit')
            if m == 'ret':
                self.steps += steps
                return
            if m in ('mov', 'movups', 'movaps', 'movsd', 'movss'):
                self.write(i, op[0], self.read(i, op[1]))
            elif m == 'lea':
                self.write(i, op[0], self.address(i, op[1]))
            elif m == 'imul':
                require(len(op) == 3, 'unsupported imul')
                self.write(i, op[0], self.read(i, op[1])*self.read(i, op[2]))
            elif m in ('inc', 'dec', 'add', 'sub'):
                a = self.read(i, op[0])
                b = 1 if len(op) == 1 else self.read(i, op[1])
                value = a+b if m in ('inc', 'add') else a-b
                self.write(i, op[0], value)
                self.zf = (value & ((1 << (op[0].size*8))-1)) == 0
            elif m == 'test':
                self.zf = (self.read(i, op[0]) & self.read(i, op[1])) == 0
            elif m in ('je', 'jne'):
                require(self.zf is not None, 'unknown branch flags')
                taken = self.zf if m == 'je' else not self.zf
                self.branches.add((hex(pc), bool(taken)))
                if taken:
                    nxt = op[0].imm
            else:
                raise ValueError('unsupported instruction ' + m)
            pc = nxt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(), 'refusing overwrite')
    prior_rows = {}
    def collect(x):
        if isinstance(x, dict):
            if all(k in x for k in ('rva', 'bytes', 'asm')):
                prior_rows[int(x['rva'], 16)] = x
            for v in x.values(): collect(v)
        elif isinstance(x, list):
            for v in x: collect(v)
    for name, digest in PRIOR.items():
        raw = (HERE / name).read_bytes()
        require(sha(raw) == digest, 'prior evidence changed ' + name)
        collect(json.loads(raw))
    im = Image(args.evidence)
    root = 0x1258050
    fragments = [f for f in im.functions if im.root(f[0])[0] == root]
    require(fragments == [(root, 0x12616B6, 0x24F839C)], 'initializer family changed')
    raw = im.read(root, 0x12616B6-root)
    instructions = list(im.md.disasm(raw, root))
    require(sum(i.size for i in instructions) == len(raw), 'incomplete initializer decode')
    by = {i.address:i for i in instructions}
    cfg = normal_cfg(instructions)
    spans = {'initializer':dict(start=hex(root), end_exclusive=hex(0x12616B6),
        sha256=sha(raw), instruction_count=len(instructions), fragment=[hex(x) for x in fragments[0]],
        instructions=[row(i) for i in instructions])}
    decoded, leaves = {}, {}
    for entry, end in LEAVES.items():
        calls = [i for i in instructions if i.mnemonic == 'call' and i.operands[0].type == X86_OP_IMM and i.operands[0].imm == entry]
        require(calls, 'no proven entry call')
        raw = im.read(entry, end-entry)
        ins = list(im.md.disasm(raw, entry))
        require(sum(i.size for i in ins) == len(raw), 'leaf decode truncated')
        leaf_cfg = normal_cfg(ins)
        require(all(i.mnemonic != 'call' for i in ins), 'unexpected nested call')
        decoded[entry] = {i.address:i for i in ins}
        leaves[hex(entry)] = dict(start=hex(entry), end_exclusive=hex(end), sha256=sha(raw),
            instructions=[row(i) for i in ins], entry_call=row(calls[0]),
            all_return_sites=[hex(i.address) for i in ins if i.mnemonic == 'ret'],
            cfg={hex(a):[hex(b) for b in bs] for a,bs in leaf_cfg.items()})
    # These are semantic pins, not an inference from an address-name convention.
    pins = {
        0x1257722:'imul rdx, rax, 0xa0e8',
        0x125773F:'mov dword ptr [rdx + rax + 0xa0e0], 0',
        0x1257847:'mov eax, dword ptr [r8 + 0xa0e0]',
        0x1257855:'inc eax', 0x1257857:'mov dword ptr [r8 + 0xa0e0], eax',
        0x1257865:'mov dword ptr [rdx + r8], 1',
        0x1257CA7:'mov eax, dword ptr [r8 + 0xa0e0]',
        0x1257CB8:'inc eax', 0x1257CBA:'mov dword ptr [r8 + 0xa0e0], eax',
        0x1257CC1:'mov dword ptr [rdx], 2',
        0x1257E3D:'mov dword ptr [r8 + 0xd64], eax',
        0x1257F48:'mov dword ptr [rdx + 0xe4], eax',
        0x1257FC0:'mov dword ptr [r9 + 0x388], eax',
    }
    flat = {a:i for d in decoded.values() for a,i in d.items()}
    for at, asm in pins.items():
        require(row(flat[at])['asm'].strip() == asm, 'semantic pin changed ' + hex(at))
    for entry, ds in decoded.items():
        refs = [(i, o, i.address+i.size+o.mem.disp) for i in ds.values() for o in i.operands
                if o.type == X86_OP_MEM and i.reg_name(o.mem.base) == 'rip']
        require(set(t for _,_,t in refs) == {BASE, SELECTOR}, 'leaf template globals changed')
        require(sum(bool(o.access & CS_AC_WRITE) for _,o,_ in refs) == (1 if entry == 0x1257720 else 0),
                'unexpected RIP-relative write')

    emission = {}
    branches = set()
    model_cases = 0
    model_steps = 0
    for ident, (start,end) in GROUPS.items():
        group = [i for i in instructions if start <= i.address < end]
        require(group[0].address == start and group[-1].address+group[-1].size == end, 'group bounds')
        require(row(group[0])['asm'] == f'mov ecx, {hex(ident)}', 'selector immediate')
        require(group[1].mnemonic == 'call' and group[1].operands[0].imm == 0x1257720, 'selector call')
        require(all(i.mnemonic in ('mov','lea','call') for i in group), 'nonlinear group')
        require(not [(a,b) for a,bs in cfg.items() for b in bs if b > start and b < end and not start <= a < end],
                'external entry inside emission block')
        # MOV selector, then exact alternating CALL and LEA stack source / CALL.
        require(all(i.mnemonic == ('lea' if n % 2 == 0 else 'call') for n,i in enumerate(group[2:],2)),
                'unexpected emission instruction sequence')
        for i in group[2::2]:
            require(i.reg_name(i.operands[0].reg) == 'rcx' and i.reg_name(i.operands[1].mem.base) == 'rbp'
                    and not i.operands[1].mem.index, 'unexpected source argument')
        calls = [i for i in group if i.mnemonic == 'call']
        require(all(i.operands[0].imm in LEAVES for i in calls), 'unmodelled emission helper')
        nodes, secondary = [], []
        for i in calls:
            t = i.operands[0].imm
            if t == 0x1257720:
                require(not nodes, 'unexpected reset')
            elif t in (0x1257830,0x1257C90):
                nodes.append(dict(type=1 if t == 0x1257830 else 2, events=0, append_call=hex(i.address)))
            elif t == 0x1257E00:
                require(nodes, 'event with no node')
                nodes[-1]['events'] += 1
            else:
                require(nodes, 'secondary payload with no node')
                secondary.append(dict(call=hex(i.address), node=len(nodes)-1,
                                      event=nodes[-1]['events']-1 if nodes[-1]['events'] else None))
        require(len(nodes)<=12 and max(n['events'] for n in nodes)<=10, 'physical template bounds')
        for fill in (0, 0xA5):
            machine = Machine(decoded, ident)
            for call in calls:
                target = call.operands[0].imm
                machine.call(target, ident if target == 0x1257720 else INPUT, fill)
            ptr = BASE+ident*STRIDE
            require(machine.memory(ptr+COUNT,4) == len(nodes), 'node model disagreement')
            for n, data in enumerate(nodes):
                require(machine.memory(ptr+n*NODE,4) == data['type'], 'node type disagreement')
                require(machine.memory(ptr+n*NODE+0xD64,4) == data['events'], 'event model disagreement')
            for s in secondary:
                at = ptr+s['node']*NODE
                at += 0x388 if s['event'] is None else 0x38C+s['event']*EVENT+0xE4
                require(machine.memory(at,4)==1, 'secondary model disagreement')
            template_writes = [(a,n) for a,n in machine.writes if BASE <= a < BASE+73*STRIDE]
            require(all(ptr <= a and a+n <= ptr+STRIDE for a,n in template_writes), 'cross-template write')
            branches.update(machine.branches); model_steps += machine.steps; model_cases += 1
        emission[hex(ident)] = dict(start=hex(start), end_exclusive=hex(end), instructions=[row(i) for i in group],
            helper_calls=[row(i) for i in calls], nodes=nodes, secondary_payloads=secondary,
            node_count=len(nodes), event_count=sum(n['events'] for n in nodes),
            normal_external_entry_only_at_start=True)

    # Exercise every legal node position for the two appenders. Nonzero source
    # bytes detect copy-overrun assumptions; count and copy ranges are checked.
    boundary_cases = []
    for entry, type_id in [(0x1257830,1),(0x1257C90,2)]:
        for n in range(12):
            machine = Machine(decoded, 0x17)
            ptr=BASE+0x17*STRIDE
            machine.memory(SELECTOR,4,0x17); machine.memory(ptr+COUNT,4,n)
            before=len(machine.writes)
            machine.call(entry,fill=0xA5)
            require(machine.memory(ptr+COUNT,4)==n+1 and machine.memory(ptr+n*NODE,4)==type_id, 'append count/type')
            writes=[(a,s) for a,s in machine.writes[before:] if BASE <= a < BASE+73*STRIDE]
            require(all((a==ptr+COUNT and s==4) or (ptr+n*NODE <= a and a+s<=ptr+(n+1)*NODE)
                        for a,s in writes), 'node copy crosses its element')
            branches.update(machine.branches); model_steps+=machine.steps; model_cases+=1
            boundary_cases.append(dict(helper=hex(entry), old_count=n, new_count=n+1))
    # Verify the alternate no-event branch of 1257EF0 as well as the event branch
    # exercised by template 17. The previously truncated exploratory prefix did
    # not contain this complete branch.
    machine=Machine(decoded,0x17); ptr=BASE+0x17*STRIDE
    machine.memory(SELECTOR,4,0x17); machine.memory(ptr+COUNT,4,1)
    machine.call(0x1257EF0,fill=0xA5)
    require(machine.memory(ptr+0x388,4)==1 and machine.memory(ptr+COUNT,4)==1
            and machine.memory(ptr+0xD64,4)==0, 'no-event secondary branch')
    branches.update(machine.branches); model_steps+=machine.steps; model_cases+=1
    require(branches == {('0x12578c3',False),('0x12578c3',True),('0x1257f25',False),('0x1257f25',True)},
            'branch outcomes not fully covered')

    caller_ranges = [(0x142DA78,0x142DA7F),(0x142DABE,0x142DACF),(0x142DE0E,0x142DE40),
                     (0x142DE63,0x142DE74),(0x142DF00,0x142DF0E),(0x142DF82,0x142DF98)]
    callers=[]
    for a,b in caller_ranges:
        ins=list(im.md.disasm(im.read(a,b-a),a))
        require(sum(i.size for i in ins)==b-a, 'caller decode')
        require(all(i.address in prior_rows and all(prior_rows[i.address].get(k)==v for k,v in row(i).items())
                    for i in ins), 'caller prior mismatch')
        callers.extend(row(i) for i in ins)
    record_map=[(0x28,0x17,0x142DE22),(0xA0,0x18,0x142DE3B),(0x118,0x1B,0x142DACA),
                (0x1A0,0x19,0x142DE6F),(0x218,0x1B,0x142DF09)]
    # Keep the address/argument derivation explicit rather than trusting the
    # hand-labelled mapping. RSI=D is inherited from pinned prior CFG evidence.
    caller_semantics = {
        0x142DA78:'lea r14, [rsi + 0x810a5]',
        0x142DABE:'mov edx, 0x1b', 0x142DAC3:'lea rcx, [r14 - 0x175]',
        0x142DACA:'call 0x140c2e0',
        0x142DE0E:'mov r8d, 0x17', 0x142DE1B:'lea rdx, [r14 - 0x265]',
        0x142DE22:'call 0x142f6e0',
        0x142DE27:'mov r8d, 0x18', 0x142DE34:'lea rdx, [r14 - 0x1ed]',
        0x142DE3B:'call 0x142f6e0',
        0x142DE63:'mov edx, 0x19', 0x142DE68:'lea rcx, [r14 - 0xed]',
        0x142DE6F:'call 0x140c2e0',
        0x142DF00:'mov edx, 0x1b', 0x142DF05:'lea rcx, [r14 - 0x75]',
        0x142DF09:'call 0x140c2e0', 0x142DF82:'add r14, 0x298',
        0x142DF8E:'cmp r13d, 4', 0x142DF92:'jb 0x142dab0',
    }
    caller_by={int(r['rva'],16):r for r in callers}
    for at,asm in caller_semantics.items():
        require(caller_by[at]['asm']==asm, 'caller semantic pin changed')
    require([0x810A5-0x80E18+d for d in (-0x265,-0x1ED,-0x175,-0xED,-0x75)]
            == [o for o,_,_ in record_map], 'record offset derivation')
    per_record=sum(emission[hex(t)]['node_count'] for _,t,_ in record_map)
    require(per_record==11, 'budget changed')
    result=dict(schema_version=1, source_sha256=EXPECTED, prior_sha256=PRIOR,
        runtime_verified=False, native_execution=False,
        scope='Four straight-line template emission blocks and complete called leaves, conditional allocation budget.',
        initializer=spans['initializer'], leaves=leaves, emission_blocks=emission,
        caller_pins=callers, record_template_mapping=[dict(record_offset=hex(o),template=hex(t),
            caller=hex(c),nodes=emission[hex(t)]['node_count']) for o,t,c in record_map],
        layout=dict(template_base=hex(BASE), selector=hex(SELECTOR), template_stride=hex(STRIDE),
            template_node_count_offset=hex(COUNT), node_stride=hex(NODE), physical_nodes_per_template=12,
            event_start='0x38c',event_stride='0xfc',event_count_offset='0xd64',physical_events_per_node=10),
        synthetic_replay=dict(cases=model_cases,instruction_steps=model_steps,branch_outcomes=sorted(branches),
            boundary_cases=boundary_cases,payload_fills=[0,165],
            preconditions=['Fresh zeroed template elements, as intended by initializer bulk clear.',
                'Event input secondary count at +E4 is zero; payload bytes otherwise synthetic.',
                'No interleaved writers, callbacks, exceptions or native execution.']),
        budget=dict(nodes_per_record=per_record, four_records=4*per_record,eight_records=8*per_record,
            added_four_records=4*per_record,pool_capacity=256,
            maximum_other_simultaneous_nodes_for_eight=256-8*per_record,
            node_bytes=0x208,added_node_storage_bytes=4*per_record*0x208,
            added_occupancy_bytes=4*per_record,
            caveat='44 new nodes is this record family only; storage bytes are accounting, not an allocation prescription.'),
        not_closed=['Initializer runtime invocation and writable-template equivalence.',
            'Writes from outside the selected emission groups and all later template mutations.',
            'Other pool users, peak/transient occupancy and initialization of occupancy/used-count/cursor.',
            'All record aliases, safe relocation, actual patching and fifth/eighth-player multiplayer behavior.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),budget=result['budget'],
        model_cases=model_cases,instruction_steps=model_steps,initializer_instructions=len(instructions),
        leaf_instructions=sum(len(ds) for ds in decoded.values())),ensure_ascii=False))


if __name__ == '__main__':
    main()
