"""Fixed-capture, offline map semantics and capacity checks; never runs game code.

Uses existing Capstone only for decoding. The small x64 interpreter below is
Python code, not native emulation/JIT, and uses invented memory/register state.
"""
import argparse
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

import capstone as cs
import capstone.x86 as x86
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image, EXPECTED, require, row

MASK32 = 0xffffffff
MASK64 = 0xffffffffffffffff
ROOTS = {
    0x172F790: (0x172F7FE, '57814b81c7a60e8d4ea989757b9a7d6d3dc3cfd9a81bc315794ca37b8885b375'),
    0x172F8A0: (0x172F9A3, 'd58cc9dbb3c79864b4ca0692be1fcf3a31ec267c059f7c904063aed53d05ec4f'),
    0x60C890: (0x60C9BF, '23d53b4f2f46ec26d23d79b958ee31d469910217ea843fb92bd98cf24c017411'),
}


def u32(x):
    return x & MASK32


def sha(x):
    return hashlib.sha256(x).hexdigest()


class NullStore(Exception):
    def __init__(self, address=4, rva=0x172F7F2):
        self.address, self.rva = address, rva


class MapModel:
    """Register-width-aware transliteration; each bucket is (u32 key,u32 value)."""
    def __init__(self, capacity=8, multiplier=2, invalid=MASK32):
        self.capacity, self.multiplier, self.invalid = capacity, u32(multiplier), u32(invalid)
        self.a = [(self.invalid, 0) for _ in range(capacity)]

    def clone(self):
        out = MapModel(self.capacity, self.multiplier, self.invalid)
        out.a = self.a.copy()
        return out

    def insert(self, key, value, trace=None):
        key, value = u32(key), u32(value)
        hashed, mask = u32(self.multiplier*key), u32(self.capacity-1)
        for eax in range(self.capacity):
            index = u32(eax+hashed) & mask  # LEA EDX zero-extends, AND RDX,RCX.
            if trace is not None:
                trace.append(dict(probe=eax, index=index, key=self.a[index][0]))
            if self.a[index][0] in (self.invalid, key):
                self.a[index] = (key, value)
                return index
        # 172F7E3 xor ECX,ECX; F7F2 writes value at [RCX+4] before key.
        raise NullStore()

    def lookup(self, key, trace=None):
        key = u32(key)
        # Representative actual consumer 60C897 checks the invalid-ID sentinel.
        if key == self.invalid:
            return None
        hashed, mask = u32(key*self.multiplier), u32(self.capacity-1)
        for ecx in range(self.capacity):
            index = u32(ecx+hashed) & mask
            found_key, value = self.a[index]
            if trace is not None:
                trace.append(dict(probe=ecx, index=index, key=found_key))
            if found_key == self.invalid:
                return None
            if found_key == key:
                return value
        return None

    def delete(self, key, trace=None):
        key = u32(key)
        hashed, mask = u32(key*self.multiplier), u32(self.capacity-1)
        # Unlike lookup, the search does not stop at an empty/invalid bucket.
        for r8d in range(self.capacity):
            index = u32(r8d+hashed) & mask
            if self.a[index][0] == key:
                break
        else:
            return 0
        old_value = self.a[index][1]
        self.a[index] = (self.invalid, old_value)  # Only key is cleared.
        r14d, hole = u32(hashed+r8d), index
        for r10d in range(1, self.capacity):
            current = u32(r14d+r10d) & mask
            current_key = self.a[current][0]
            if current_key == self.invalid:
                if trace is not None:
                    trace.append(dict(scan=r10d, current=current, stop='empty'))
                break
            home = u32(current_key*self.multiplier) & mask
            hole_distance = u32(u32(self.capacity-hole)+current) & mask
            home_distance = u32(u32(self.capacity-home)+current) & mask
            move = hole_distance <= home_distance  # unsigned CMP; JA skips.
            if trace is not None:
                trace.append(dict(scan=r10d, current=current, hole=hole, home=home,
                                  hole_distance=hole_distance, home_distance=home_distance, move=move))
            if move:
                pair = self.a[current]
                self.a[hole] = pair  # Whole QWORD: key AND ordinal.
                hole = current
                self.a[current] = (self.invalid, pair[1])
        return old_value


class Interpreter:
    """Restricted x64 instruction interpreter for only the pinned helpers.

    Integer/register/memory semantics are modeled; no native code executes.
    Supports exactly the mnemonics exercised below, rejecting others. IMUL
    overflow flags are unnecessary: no control branch consumes them here.
    """
    HEADER, BUCKETS, STACK, OWNER = 0x10000, 0x20000, 0x30100, 0x40000

    def __init__(self, instructions, model, root, key, value=0):
        self.instructions = instructions
        self.reg = dict(rsp=self.STACK, rcx=self.HEADER, rdx=u32(key), r8=u32(value))
        self.mem = {}
        self.allowed = [(self.HEADER,self.HEADER+0x100), (self.BUCKETS,self.BUCKETS+8*model.capacity),
                        (self.STACK-0x100,self.STACK+0x100), (self.OWNER,self.OWNER+0x200)]
        self.rip, self.zf, self.cf = root, False, False
        self.events = []
        self.visited = set()
        self.branch_outcomes = set()
        self.steps = 0
        if root == 0x60C890:
            self.reg.update(rcx=self.OWNER, r8=0x50000, r9=0x60000)
            header = self.OWNER+0xD0
            sentinel = instructions[0x60C897]
            addr = sentinel.address+sentinel.size+sentinel.operands[1].mem.disp
            self.allowed.append((addr,addr+4))
            self.put(addr,4,model.invalid)
        else:
            header = self.HEADER
        self.put(header,8,self.BUCKETS)
        self.put(header+8,4,model.capacity)
        self.put(header+12,4,model.invalid)
        self.put(header+16,4,model.multiplier)
        for n,(k,v) in enumerate(model.a):
            self.put(self.BUCKETS+8*n,4,k)
            self.put(self.BUCKETS+8*n+4,4,v)

    def check(self, address, size):
        if not any(lo <= address and address+size <= hi for lo,hi in self.allowed):
            if address in (0,4):
                raise NullStore(address, self.rip)
            raise AssertionError(f'unmodeled memory {address:#x}/{size} at {self.rip:#x}')

    def get(self, address, size):
        self.check(address,size)
        return sum(self.mem.get(address+i,0) << (8*i) for i in range(size))

    def put(self, address, size, value):
        self.check(address,size)
        for i in range(size):
            self.mem[address+i] = (value >> (8*i)) & 255

    @staticmethod
    def alias(name):
        if name in ('eax','ebx','ecx','edx','esi','edi','ebp','esp'):
            return 'r'+name[1:],32
        if name.startswith('r') and name.endswith('d'):
            return name[:-1],32
        return name,64

    def regget(self, name):
        if not name:
            return 0
        base,width = self.alias(name)
        return self.reg.get(base,0) & ((1 << width)-1)

    def regput(self, name, value):
        base,width = self.alias(name)
        self.reg[base] = value & ((1 << width)-1)  # 32-bit write zero-extends.

    def addr(self, op, ins):
        base = ins.reg_name(op.mem.base)
        index = ins.reg_name(op.mem.index)
        b = ins.address+ins.size if base == 'rip' else self.regget(base)
        return (b+self.regget(index)*op.mem.scale+op.mem.disp) & MASK64

    def read(self, op, ins):
        if op.type == X86_OP_REG:
            return self.regget(ins.reg_name(op.reg))
        if op.type == X86_OP_IMM:
            return op.imm
        if op.type == X86_OP_MEM:
            return self.get(self.addr(op,ins),op.size)
        raise AssertionError('unknown operand')

    def write(self, op, ins, value):
        if op.type == X86_OP_REG:
            self.regput(ins.reg_name(op.reg),value)
        elif op.type == X86_OP_MEM:
            self.put(self.addr(op,ins),op.size,value)
        else:
            raise AssertionError('invalid destination')

    def run(self, stop=None):
        while self.rip != stop:
            self.steps += 1
            require(self.steps <= 2000,'instruction limit')
            ins = self.instructions[self.rip]
            self.visited.add(self.rip)
            op,m = ins.operands,ins.mnemonic
            nxt = self.rip+ins.size
            if m == 'ret':
                break
            if m == 'nop':
                pass
            elif m == 'mov':
                self.write(op[0],ins,self.read(op[1],ins))
            elif m == 'lea':
                self.write(op[0],ins,self.addr(op[1],ins))
            elif m == 'push':
                value = self.read(op[0],ins)
                self.reg['rsp'] -= 8
                self.put(self.reg['rsp'],8,value)
            elif m == 'pop':
                self.write(op[0],ins,self.get(self.reg['rsp'],8))
                self.reg['rsp'] += 8
            elif m in ('cmp','test'):
                bits = 8*op[0].size
                a,b = self.read(op[0],ins),self.read(op[1],ins)
                a,b = a&((1<<bits)-1),b&((1<<bits)-1)
                self.zf = (a == b) if m == 'cmp' else ((a&b) == 0)
                self.cf = (a < b) if m == 'cmp' else False
            elif m in ('xor','and','imul','add','sub','inc'):
                a = self.read(op[0],ins)
                b = self.read(op[1],ins) if len(op)>1 else 1
                value = {'xor':lambda:a^b,'and':lambda:a&b,'imul':lambda:a*b,
                         'add':lambda:a+b,'sub':lambda:a-b,'inc':lambda:a+1}[m]()
                self.write(op[0],ins,value)
                if m in ('xor','and'):
                    self.zf,self.cf = (value&((1<<(op[0].size*8))-1))==0,False
                # ADD/SUB/INC/IMUL flags are overwritten by CMP/TEST before use.
            elif m in ('je','jne','jb','jbe','ja','jmp'):
                take = {'je':self.zf,'jne':not self.zf,'jb':self.cf,
                        'jbe':self.cf or self.zf,'ja':not self.cf and not self.zf,'jmp':True}[m]
                self.branch_outcomes.add((self.rip,take))
                if take:
                    nxt = op[0].imm
            else:
                raise AssertionError('unsupported instruction '+m)
            self.rip = nxt
        return self.regget('rax')

    def buckets(self, capacity):
        return [(self.get(self.BUCKETS+8*n,4),self.get(self.BUCKETS+8*n+4,4)) for n in range(capacity)]


def verify_members(model, expected, missing):
    require(sum(k != model.invalid for k,_ in model.a) == len(expected),'occupancy mismatch')
    require(len({k for k,_ in model.a if k != model.invalid}) == len(expected),'duplicate real key')
    for k,v in expected.items():
        require(model.lookup(k) == v,'key unreachable/value lost')
    require(model.lookup(missing) is None,'absent key found')


def exhaustive():
    counts = dict(hash_class_sequences=0,prefix_states=0,full_table_deletions=0,
                  reinserts=0,full_table_updates=0,ninth_key_faults=0)
    digest = hashlib.sha256()
    # For multiplier 2 and cap 8, home = 2*(key mod 4). Insertion order is
    # represented by the key's i*4 label, so each low-two-bit sequence is covered.
    for classes in itertools.product(range(4),repeat=8):
        m = MapModel()
        keys = [4*i+c for i,c in enumerate(classes)]
        expected = {}
        for i,k in enumerate(keys):
            m.insert(k,i)
            expected[k] = i
            verify_members(m,expected,0x12345678)
            counts['prefix_states'] += 1
        for i,k in enumerate(keys):
            b = m.clone()
            require(b.delete(k) == i,'wrong removed ordinal')
            remain = dict(expected)
            del remain[k]
            verify_members(b,remain,k)
            counts['full_table_deletions'] += 1
            b.insert(k,0x80000000+i)
            remain[k] = 0x80000000+i
            verify_members(b,remain,0x12345678)
            counts['reinserts'] += 1
            b.insert(k,MASK32-i)
            remain[k] = MASK32-i
            verify_members(b,remain,0x12345678)
            counts['full_table_updates'] += 1
        before = m.a.copy()
        try:
            m.insert(0x12345678,8)
        except NullStore as e:
            require(e.address == 4 and e.rva == 0x172F7F2,'wrong full failure')
            require(m.a == before,'bucket mutated before fault')
            counts['ninth_key_faults'] += 1
        else:
            raise AssertionError('ninth different key unexpectedly fits')
        digest.update(bytes(classes))
        for k,v in m.a:
            digest.update(k.to_bytes(4,'little')+v.to_bytes(4,'little'))
        counts['hash_class_sequences'] += 1
    counts['full_table_digest_sha256'] = digest.hexdigest()
    return counts


def deletion_orders():
    reports = []
    for label,keys in [('all_collide_at_6',[3+4*i for i in range(8)]),
                       ('mixed_wrap',[3,4,6,13,19,23,26,28])]:
        m = MapModel()
        for i,k in enumerate(keys):
            m.insert(k,i)
        n = 0
        for order in itertools.permutations(keys):
            b,expected = m.clone(),dict(zip(keys,range(8)))
            for k in order:
                require(b.delete(k) == expected.pop(k),'delete permutation value')
                verify_members(b,expected,k)
            require(all(k == b.invalid for k,_ in b.a),'not empty after all removals')
            n += 1
        reports.append(dict(case=label,keys=keys,orders=n,delete_operations=n*8))
    return reports


def interpreted_checks(instructions):
    rng = random.Random(0x172F790172F8A0)
    counts = dict(insert=0,delete=0,lookup=0,fault=0,instruction_steps=0)
    visited = set()
    branch_outcomes = set()
    def check(m,kind,key,value=0):
        root = {'insert':0x172F790,'delete':0x172F8A0,'lookup':0x60C890}[kind]
        machine = Interpreter(instructions,m,root,key,value)
        b = m.clone()
        model_fault = machine_fault = None
        try:
            result = getattr(b,kind)(key,value) if kind == 'insert' else getattr(b,kind)(key)
        except NullStore as e:
            model_fault = (e.address,e.rva)
        try:
            actual = machine.run(stop=0x60C928 if kind == 'lookup' else None)
        except NullStore as e:
            machine_fault = (e.address,e.rva)
        require(model_fault == machine_fault,'interpreter/model fault mismatch')
        require(machine.buckets(m.capacity) == b.a,'interpreter/model bucket mismatch')
        if model_fault:
            counts['fault'] += 1
        elif kind == 'insert':
            require(actual == machine.BUCKETS+result*8,'insert return pointer mismatch')
        elif kind == 'lookup':
            require(u32(actual) == (MASK32 if result is None else result),'lookup return mismatch')
        else:
            require(u32(actual) == result,'delete return mismatch')
        counts[kind] += 1
        counts['instruction_steps'] += machine.steps
        visited.update(machine.visited)
        branch_outcomes.update(machine.branch_outcomes)
        return b,model_fault

    # Boundary values exercise 32-bit IMUL/LEA wrap, even/odd/zero multipliers,
    # and both sentinel values. Non-power-two is deliberately excluded here.
    configurations = []
    for cap in (1,2,4,8,16):
        for multiplier in (0,1,2,3,0x80000000,MASK32):
            for invalid in (0,MASK32):
                m = MapModel(cap,multiplier,invalid)
                expected = {}
                keys = [k for k in (0,1,2,3,4,7,8,0x7fffffff,0x80000000,0xfffffffe,MASK32)
                        if k != invalid]
                while len(keys)<cap+2:
                    k = rng.getrandbits(32)
                    if k != invalid and k not in keys:
                        keys.append(k)
                for i,k in enumerate(keys[:cap]):
                    m,fault = check(m,'insert',k,u32(0x80000000+i))
                    require(not fault,'premature insertion failure')
                    expected[k] = u32(0x80000000+i)
                full = m.clone()
                for k,v in expected.items():
                    check(full,'lookup',k)
                    deleted,fault = check(full,'delete',k)
                    require(not fault,'delete fault')
                    verify_members(deleted,{x:y for x,y in expected.items() if x!=k},k)
                    check(deleted,'insert',k,v)
                    check(full,'insert',k,7)
                check(full,'lookup',keys[cap])
                check(full,'delete',keys[cap])
                check(full,'insert',keys[cap],8)
                check(full,'lookup',invalid)
                for _ in range(40):
                    k = rng.choice(keys)
                    kind = rng.choice(('insert','delete','lookup'))
                    value = rng.getrandbits(32)
                    m,fault = check(m,kind,k,value)
                    if kind == 'insert' and not fault:
                        expected[k] = value
                    if kind == 'delete':
                        expected.pop(k,None)
                    verify_members(m,expected,next(x for x in keys if x not in expected))
                configurations.append(dict(capacity=cap,multiplier=hex(multiplier),invalid=hex(invalid)))
    check(MapModel(0),'insert',1,0)
    check(MapModel(0),'delete',1)
    check(MapModel(0),'lookup',1)
    # Sentinel insertion leaves a bucket empty but changes its stale value.
    empty = MapModel()
    sentinel_insert,_ = check(empty,'insert',MASK32,0x12345678)
    check(sentinel_insert,'lookup',MASK32)
    check(sentinel_insert,'delete',MASK32)
    required = {a for a in instructions if 0x172F790 <= a < 0x172F7FE or 0x172F8A0 <= a < 0x172F9A3}
    require(required <= visited,'insertion/deletion interpreter left unvisited instructions')
    conditional = {a for a in required if instructions[a].group(cs.CS_GRP_JUMP) and instructions[a].mnemonic!='jmp'}
    require(all((a,True) in branch_outcomes and (a,False) in branch_outcomes for a in conditional),
            'insertion/deletion interpreter left untested branch outcome')
    return dict(seed=hex(0x172F790172F8A0),configurations=configurations,counts=counts,
                includes_invalid_key_demonstration=True,includes_zero_capacity=True,
                insertion_deletion_instruction_coverage=dict(required=len(required),visited=len(required&visited)),
                insertion_deletion_conditionals_both_outcomes=len(conditional),
                visited_instructions=[hex(a) for a in sorted(visited)],
                branch_outcomes=[dict(rva=hex(a),taken=b) for a,b in sorted(branch_outcomes)])


def examples():
    m = MapModel()
    keys = [3+4*i for i in range(8)]
    inserts = []
    for i,k in enumerate(keys):
        tr = []
        slot = m.insert(k,i,tr)
        inserts.append(dict(key=k,ordinal=i,slot=slot,probes=tr))
    full = m.a.copy()
    delete_trace = []
    removed = m.delete(keys[0],delete_trace)
    after_delete = m.a.copy()
    reinsert = m.insert(keys[0],7)
    # Six buckets is not a valid replacement for an AND(capacity-1) table.
    broken = MapModel(6)
    failed_key = None
    for k in range(6):
        try:
            broken.insert(k,k)
        except NullStore:
            failed_key = k
            break
    require(failed_key == 4,'non-power-two demonstration changed')
    s = MapModel()
    idx = s.insert(s.invalid,0x12345678)
    return dict(all_collide_and_wrap=dict(keys=keys,inserts=inserts,full=full,
                removed_key=keys[0],removed_ordinal=removed,delete_trace=delete_trace,
                after_delete=after_delete,reinsert_slot=reinsert,after_reinsert=m.a),
                non_power_two=dict(capacity=6,failed_insert_key=failed_key,buckets=broken.a,
                                   empty_buckets=sum(k==broken.invalid for k,_ in broken.a)),
                invalid_key=dict(insert_slot=idx,buckets=s.a,lookup_result=s.lookup(s.invalid),
                                 note='Sentinel key is not an occupied/mappable entity; wrapper precondition.'),
                ordinal_zero_note='delete returns 0 for both absent key and a real key whose value was 0.')


def verify_flag_producers(functions, instructions):
    """Backward reaching definitions for every consumed CF/ZF at a branch.

    Capstone's flag-effect metadata determines whether an instruction changes
    (including makes undefined) a bit. Do not assume MOV/LEA-only gaps or that
    physical instruction order equals control-flow order.
    """
    consumers = {'je':['ZF'],'jne':['ZF'],'jb':['CF'],'jbe':['CF','ZF'],'ja':['CF','ZF']}
    effects = {flag:sum(getattr(x86,'X86_EFLAGS_'+effect+'_'+flag)
                       for effect in ('MODIFY','RESET','SET','UNDEFINED')) for flag in ('CF','ZF')}
    checks = []
    for function in functions:
        entry = int(function['entry'],16)
        reverse = {int(a,16):[] for a in function['normal_cfg']}
        for a,successors in function['normal_cfg'].items():
            for target in successors:
                reverse[int(target,16)].append(int(a,16))
        for address in reverse:
            branch = instructions[address]
            if not branch.group(cs.CS_GRP_JUMP) or branch.mnemonic=='jmp':
                continue
            require(branch.mnemonic in consumers,'unsupported condition flag consumer')
            for flag in consumers[branch.mnemonic]:
                seen,definitions = set(),set()
                todo = reverse[address].copy()
                reaches_entry = False
                while todo:
                    previous = todo.pop()
                    if previous in seen:
                        continue
                    seen.add(previous)
                    ins = instructions[previous]
                    if ins.eflags & effects[flag]:
                        definitions.add(previous)
                    else:
                        reaches_entry |= previous == entry
                        todo.extend(reverse[previous])
                require(definitions and not reaches_entry,'branch consumes unspecified entry flags')
                require(all(instructions[p].mnemonic in ('cmp','test','and','xor') for p in definitions),
                        'branch consumes omitted ADD/SUB/INC/IMUL/SHL flag semantics')
                checks.append(dict(root=hex(entry),branch=row(branch),flag=flag,
                                   closest_reaching_definitions=[row(instructions[p]) for p in sorted(definitions)]))
    return dict(method='Per-flag backward CFG traversal; Capstone MODIFY/RESET/SET/UNDEFINED metadata.',
                checks=checks,all_consumed_flags_have_implemented_producer=True,
                note='No tested conditional consumes omitted arithmetic flags; IMUL undefined ZF is also treated as a definition.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--output',required=True)
    args = ap.parse_args()
    output = Path(args.output)
    require(not output.exists(),'refusing overwrite')
    im = Image(args.evidence)
    functions,all_instructions = [],{}
    for root,(end,digest) in ROOTS.items():
        fragments = [f for f in im.functions if im.root(f[0])[0] == root]
        require(fragments[0][0]==root and fragments[-1][1]==end,'function extent changed')
        data = b''.join(im.read(a,b-a) for a,b,_ in fragments)
        require(sha(data)==digest,'helper bytes changed')
        decoded = []
        fs = []
        for a,b,u in fragments:
            raw = im.read(a,b-a)
            ins = list(im.md.disasm(raw,a))
            require(sum(x.size for x in ins)==len(raw),'incomplete decode')
            decoded.extend(ins)
            fs.append(dict(start=hex(a),end_exclusive=hex(b),unwind=hex(u),sha256=sha(raw)))
        boundaries = {i.address for i in decoded}
        edges = {}
        for i in decoded:
            require(not i.group(cs.CS_GRP_CALL),'unexpected call')
            if i.group(cs.CS_GRP_RET):
                successors = []
            elif i.group(cs.CS_GRP_JUMP):
                require(i.operands[0].type==X86_OP_IMM,'indirect branch')
                successors = [i.operands[0].imm]
                if i.mnemonic!='jmp':
                    successors.append(i.address+i.size)
            else:
                successors = [i.address+i.size]
            require(all(x in boundaries for x in successors),'branch outside pinned root')
            edges[hex(i.address)] = [hex(x) for x in successors]
        all_instructions.update((i.address,i) for i in decoded)
        functions.append(dict(entry=hex(root),sha256=digest,bytes=len(data),fragments=fs,
                              instructions=[row(i) for i in decoded],normal_cfg=edges))
    # Exact constructor constants: component41's header is S+50, cap8, mult2.
    constructor = [row(im.instruction(a)) for a in (0x55270A,0x552711,0x55271E,0x552728,0x552732,0x552738)]
    require(im.instruction(0x552728).op_str=='dword ptr [rsi + 0x41a0], 8','capacity pin')
    require(im.instruction(0x552738).op_str=='dword ptr [rsi + 0x41a8], 2','multiplier pin')
    map_invalid_source = im.instruction(0x552711)
    entity_invalid_source = all_instructions[0x60C897]
    map_invalid_global = map_invalid_source.address+map_invalid_source.size+map_invalid_source.operands[1].mem.disp
    entity_invalid_global = entity_invalid_source.address+entity_invalid_source.size+entity_invalid_source.operands[1].mem.disp
    require(map_invalid_global==0x3483C34 and entity_invalid_global==0x3483C20,'sentinel address provenance changed')
    flag_producers = verify_flag_producers(functions,all_instructions)
    print('Pinned helpers and representative lookup consumer verified.',flush=True)
    instruction_comparison = interpreted_checks(all_instructions)
    print('Restricted instruction interpretation matches semantic model.',flush=True)
    exhaustive_result = exhaustive()
    print('All 65,536 eight-key home-class sequences passed.',flush=True)
    orders = deletion_orders()
    result = dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],
        replay_sha256=sha(Path(__file__).read_bytes()),functions=functions,constructor_pins=constructor,
        model=dict(capacity=8,multiplier=2,key_bits=32,value_bits=32,bucket_bytes=8,
            hash='u32(key*multiplier)',probe='u32(hash+probe_number) & u32(capacity-1)',
            insertion_probes='at most capacity; empty OR equal key accepts; no load-factor/resize guard',
            deletion_search='at most capacity, without empty-key early stop',
            backshift='at most capacity-1; stops at empty; move when ((cap-hole+j)&mask) <= ((cap-home+j)&mask)',
            invalid_key='Must not be an entity key; stored invalid key still denotes an empty bucket.',
            conditions=['Power-of-two nonzero capacity','Unique real u32 keys distinct from map invalid sentinel',
                        'Valid entity inputs also exclude caller-specific invalid-ID sentinels',
                        'Header points at writable capacity*8 bytes; constructor-initialized empty keys',
                        'No concurrent mutations during an operation','At most capacity distinct live keys',
                        'Ordinal validity for external component arrays is a separate invariant']),
        sentinel_assumptions=dict(
            component41_map_invalid_global=hex(map_invalid_global),map_invalid_source=row(map_invalid_source),
            representative_lookup_invalid_id_global=hex(entity_invalid_global),entity_invalid_source=row(entity_invalid_source),
            addresses_differ=True,runtime_values_captured=False,runtime_value_equality_proven=False,
            lookup_model_input_assumption='Both invented sentinel locations receive the same value, tested as 0 and FFFFFFFF. This is NOT runtime equality evidence.',
            internal_map_condition='A real map key must differ from header.invalid; no sentinel constant value is inferred from the saved code.',
            caller_condition='Valid entity inputs must also avoid each relevant caller invalid-ID value; representative lookup comparisons use the stated artificial equality assumption.',
            conclusion_scope='Eight-key map insertion/deletion capacity is an internal-map result. The representative 60C890 lookup check has its separate input assumption.'),
        conditional_flag_producers=flag_producers,
        restricted_instruction_comparison=instruction_comparison,exhaustive=exhaustive_result,
        deletion_permutations=orders,examples=examples(),
        conclusions=dict(eight_entries_supported_in_model=True,
            sixteenth_bucket_requirement_proven=False,
            full_table_existing_key_update='succeeds within 8 probes without new entry',
            ninth_distinct_key='first attempted store is 4 bytes at address 0x4, RVA 0x172F7F2; no safe return',
            deletion_return='deleted DWORD value, or 0 on not-found; zero is ambiguous',
            allocation='Model does not change or prove actual game heap/array/storage sizes'),
        limits=['This is Python-model verification against captured instructions, not game execution.',
                'Restricted interpreter is not a general x64 implementation or formal proof.',
                'Exhaustive enumeration covers home-class sequences for multiplier2/cap8, not all process states.',
                'Representative lookup is 60C890; other call sites and map types are not universally proved.',
                'Sentinel global equality is modeled as a precondition; capture contains no writable runtime globals.',
                'No live process query/read, new capture, game patch, mod install, or network test occurred.'])
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),sha256=sha(output.read_bytes()),
                         interpreter=instruction_comparison['counts'],exhaustive=exhaustive_result,
                         deletion_permutations=orders),ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
