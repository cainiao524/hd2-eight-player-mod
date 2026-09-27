"""Bounded static replay of the saved 94BE10 player-count consumer.

Only build 25480438's pinned capture is read. The complete chained body is
code through 94C44A, including the branch target after its first RET. The
existing 94C9C0 callee evidence is pinned as the count producer. No process,
hook, new capture, or broad callee traversal is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import capstone as cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

START, END = 0x94BE10, 0x94C44A
BODY_SHA = '0316a5430e599017d5a3251dd3b2f63e5bfad65190afb3fc10e19b55ccf81c9e'
CALLER_START, CALLER_END = 0x94C9C0, 0x94D308
CALLER_SHA = '7cc342fdc09d11b0bde285b179adcd4b5356df5df667be89bd7d5c6f76ca4ef2'
CALLEE_EVIDENCE_SHA = '04e16b4b9a301ba2fbd796528df6e53f9d3d8a25626cd459cc9f1329edd5d0d0'
PREDICATE_START, PREDICATE_END = 0x177E3C0, 0x177E45C
PREDICATE_SHA = '6f2946133c59eff112dee7cd648bef3126d78e4f9b4dde1fc07f32af4db54a38'
PREDICATE_UNWIND = 0x256C9B4
FRAGMENTS = (
    (0x94BE10, 0x94BEBC, 0x247E8BC, '35d06954b9ea75ea1d559c01747bd38d50547f9c1d33a0217431aecb764245b9'),
    (0x94BEBC, 0x94C423, 0x247E8D0, '18be75dbc40f86bbef194b3b487cfc6bc79d8d0e72219a0d6e71feeea53b1e07'),
    (0x94C423, 0x94C43E, 0x247E90C, 'd5a7a37a76e2805ac9718760857fd12239059d542563ab20b284fbeb936d7170'),
    (0x94C43E, 0x94C44A, 0x247E91C, '9820cb293211876f816bfab9b73da36d0e49f2b766e6aa2020faf19dc7f2df02'),
)
RIPS = {
    (0x94BE1B, 0x263C010), (0x94BE5A, 0x33266A0),
    (0x94BF21, 0x23C675C), (0x94BF36, 0x23C7A74),
    (0x94C16F, 0x33262F0),
}
CALLS = {
    (0x94C03A, 0x94A0A0), (0x94C185, 0x173B8D0),
    (0x94C1D6, 0x177E3C0), (0x94C27A, 0x949E10),
    (0x94C2EE, 0x949E10), (0x94C42E, 0x2088770),
}
# Corresponding caller stores of clamped EBP into outgoing +38, then calls.
COUNT_STORE_CALL_PAIRS = (
    (0x94CC60, 0x94CC7A), (0x94CCC1, 0x94CCD3),
    (0x94CD7C, 0x94CD92), (0x94CDC5, 0x94CDDB),
    (0x94CE0E, 0x94CE24), (0x94CE57, 0x94CE6D),
    (0x94CEA0, 0x94CEB6), (0x94CEE5, 0x94CF05),
    (0x94CF3B, 0x94CF54), (0x94D027, 0x94D03D),
    (0x94D08D, 0x94D0DC), (0x94D114, 0x94D12A),
    (0x94D171, 0x94D1B6), (0x94D1EE, 0x94D204),
    (0x94D232, 0x94D252),
)
CRITICAL = {
    'entry_r9d_record_count_test': 0x94BEB3,
    'r8_record_base_bias_f0': 0x94BEF4,
    'tech_level_stack_150_read': 0x94BEDC,
    'record_tech_min_compare': 0x94C05D,
    'record_tech_max_compare': 0x94C063,
    'player_count_stack_158_read': 0x94C06E,
    'record_player_min_compare': 0x94C075,
    'record_player_max_compare': 0x94C07B,
    'count_pass_al': 0x94C081,
    'count_fail_al': 0x94C085,
    'override_flag_168_read': 0x94C08E,
    'count_fail_gate': 0x94C0AD,
    'count_gate_skip': 0x94C0AF,
    'accepted_record_write': 0x94C0D4,
    'record_stride_118': 0x94C3AD,
    'record_count_loop': 0x94C3C2,
    'normal_return': 0x94C43D,
    'late_zero_branch_target': 0x94C43E,
}
CLAMP = (0x94CA1D, 0x94CA24, 0x94CA27, 0x94CA29, 0x94CA30, 0x94CA35, 0x94CA37)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detail(ins):
    result = row(ins)
    result['encoding'] = dict(rex=ins.rex, modrm=ins.modrm, sib=ins.sib,
                              displacement_offset=ins.disp_offset,
                              displacement_size=ins.disp_size,
                              immediate_offset=ins.imm_offset,
                              immediate_size=ins.imm_size)
    return result


def pin_body(im):
    found = [f for f in im.functions if im.root(f[0])[0] == START]
    require(found == [(a, b, u) for a, b, u, _ in FRAGMENTS], 'changed unwind chain')
    require(all(x[1] == y[0] for x, y in zip(found, found[1:])), 'gap in unwind chain')
    fragments = []
    for a, b, u, expected in FRAGMENTS:
        data = im.read(a, b-a)
        require(sha(data) == expected, 'changed fragment ' + hex(a))
        fragments.append(dict(start=hex(a), end_exclusive=hex(b), unwind=hex(u),
                              size_bytes=len(data), sha256=expected))
    data = im.read(START, END-START)
    require(sha(data) == BODY_SHA, 'changed complete body')
    ins = list(im.md.disasm(data, START))
    require(len(ins) == 359 and sum(x.size for x in ins) == len(data), 'incomplete instruction decode')
    boundaries = {x.address for x in ins}
    require(len(boundaries) == len(ins), 'duplicate instruction boundary')
    cfg, branches, relocations, indirect = {}, [], [], []
    for x in ins:
        for op in x.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                relocations.append(dict(kind='rip_address' if x.mnemonic == 'lea' else 'rip_memory',
                                        rva=hex(x.address), target_rva=hex(x.address+x.size+op.mem.disp),
                                        displacement_offset=x.disp_offset,
                                        displacement_size=x.disp_size, instruction=detail(x)))
        if x.group(cs.CS_GRP_CALL):
            require(len(x.operands) == 1, 'unexpected call operands')
            if x.operands[0].type == X86_OP_IMM:
                relocations.append(dict(kind='call_rel32', rva=hex(x.address),
                                        target_rva=hex(x.operands[0].imm),
                                        displacement_offset=x.imm_offset,
                                        displacement_size=x.imm_size, instruction=detail(x)))
            else:
                indirect.append(dict(kind='call_indirect', rva=hex(x.address), instruction=detail(x)))
        if x.group(cs.CS_GRP_RET):
            successors = []
        elif x.group(cs.CS_GRP_JUMP):
            require(len(x.operands) == 1 and x.operands[0].type == X86_OP_IMM,
                    'unexpected indirect jump')
            target = x.operands[0].imm
            require(target in boundaries, 'branch leaves body or targets noninstruction')
            successors = [target] + ([] if x.mnemonic == 'jmp' else [x.address+x.size])
            branches.append(detail(x))
        else:
            successors = [x.address+x.size]
        require(all(t in boundaries for t in successors), 'bad CFG successor')
        cfg[hex(x.address)] = [hex(t) for t in successors]
    require(not indirect, 'unexpected indirect control')
    actual_rips = {(int(x['rva'],16),int(x['target_rva'],16))
                   for x in relocations if x['kind'].startswith('rip_')}
    actual_calls = {(int(x['rva'],16),int(x['target_rva'],16))
                    for x in relocations if x['kind'] == 'call_rel32'}
    require(actual_rips == RIPS and actual_calls == CALLS, 'changed external relocation set')
    require(all(x['displacement_size'] == 4 for x in relocations), 'non-disp32 relocation')
    reached, todo = set(), [START]
    while todo:
        address = todo.pop()
        if address in reached:
            continue
        reached.add(address)
        todo.extend(int(t,16) for t in cfg[hex(address)])
    require(reached == boundaries, 'unreachable decoded bytes in unwind chain')
    by_address = {x.address:x for x in ins}
    require(all(x in by_address for x in CRITICAL.values()), 'critical site no longer instruction')
    # The bytes after the first RET remain reachable code through the C1AB branch.
    require(0x94C43E in reached and by_address[0x94C43D].mnemonic == 'ret',
            'late fragment mistaken for table data')
    require([(x.address, x.mnemonic) for x in ins if x.group(cs.CS_GRP_RET)]
            == [(0x94C43D, 'ret')], 'unexpected return set')
    return dict(entry=hex(START), end_exclusive=hex(END), size_bytes=len(data),
                sha256=BODY_SHA, bytes_hex=data.hex(), fragments=fragments,
                code_start=hex(START), code_end_exclusive=hex(END),
                instruction_count=len(ins), instructions=[detail(x) for x in ins],
                cfg=cfg, local_branches=branches, external_relocations=relocations,
                indirect_control=indirect,
                critical_instructions={name:detail(by_address[at]) for name,at in CRITICAL.items()},
                abi='Windows x64: RDX=R13 context, R8=record-array base, R9D=record count; '
                    'entry outgoing stack +38h is clamped player count, at this body RSP+158h '
                    'after two pushes and sub RSP,108h. Body RSP+150h/R12D is a distinct '
                    'tech-level argument. Record stride is 118h; returns through 94C43D.')


def pin_caller(im):
    evidence = HERE / 'roster_departure_callee_evidence.json'
    require(sha(evidence.read_bytes()) == CALLEE_EVIDENCE_SHA, 'changed pinned caller evidence')
    require(sha(im.read(CALLER_START, CALLER_END-CALLER_START)) == CALLER_SHA,
            'changed 94C9C0 caller body')
    pairs = []
    for store, call in COUNT_STORE_CALL_PAIRS:
        a,b = im.instruction(store),im.instruction(call)
        require(a is not None and b is not None and
                a.mnemonic == 'mov' and a.op_str == 'dword ptr [rsp + 0x38], ebp' and
                b.mnemonic == 'call' and b.operands[0].type == X86_OP_IMM and
                b.operands[0].imm == START,
                'changed count-argument callsite at '+hex(call))
        pairs.append(dict(count_store=detail(a), call=detail(b)))
    clamp = [im.instruction(at) for at in CLAMP]
    require(all(x is not None for x in clamp), 'changed clamp instruction boundaries')
    require(clamp[0].op_str == 'ebp, dword ptr [rsp + 0x168]' and
            clamp[1].op_str == 'ebp, 1' and
            clamp[4].op_str == 'eax, 4' and
            clamp[6].op_str == 'ebp, eax', 'changed [1,4] clamp')
    return dict(body_start=hex(CALLER_START), body_end_exclusive=hex(CALLER_END),
                body_sha256=CALLER_SHA, preexisting_evidence_sha256=CALLEE_EVIDENCE_SHA,
                clamp_instructions=[detail(x) for x in clamp],
                count_argument_sites=pairs,
                count_argument_site_count=len(pairs),
                note='All 15 pinned 94C9C0 calls store clamped EBP into outgoing +38h. '
                     'At callee body this is +158h; outgoing +30h becomes +150h and is tech level.')


def pin_tag_predicate(im):
    """Pin only the directly called record/source tag comparison at C1D6."""
    require([f for f in im.functions if im.root(f[0])[0] == PREDICATE_START]
            == [(PREDICATE_START, PREDICATE_END, PREDICATE_UNWIND)],
            'changed tag-predicate unwind')
    raw = im.read(PREDICATE_START, PREDICATE_END-PREDICATE_START)
    require(sha(raw) == PREDICATE_SHA, 'changed tag-predicate body')
    instructions = list(im.md.disasm(raw, PREDICATE_START))
    require(len(instructions) == 55 and sum(x.size for x in instructions) == len(raw),
            'incomplete tag-predicate decode')
    boundaries = {x.address for x in instructions}
    cfg, branches = {}, []
    for ins in instructions:
        require(not ins.group(cs.CS_GRP_CALL), 'unexpected tag-predicate call')
        require(not any(op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP
                        for op in ins.operands), 'unexpected tag-predicate RIP reference')
        if ins.group(cs.CS_GRP_RET):
            successors = []
        elif ins.group(cs.CS_GRP_JUMP):
            require(len(ins.operands) == 1 and ins.operands[0].type == X86_OP_IMM,
                    'unexpected tag-predicate indirect jump')
            successors = [ins.operands[0].imm]
            if ins.mnemonic != 'jmp':
                successors.append(ins.address+ins.size)
            branches.append(detail(ins))
        else:
            successors = [ins.address+ins.size]
        require(all(t in boundaries for t in successors), 'bad tag-predicate CFG edge')
        cfg[hex(ins.address)] = [hex(t) for t in successors]
    visited, todo = set(), [PREDICATE_START]
    while todo:
        at = todo.pop()
        if at in visited:
            continue
        visited.add(at)
        todo.extend(int(t,16) for t in cfg[hex(at)])
    require(visited == boundaries, 'unreachable tag-predicate instructions')
    return dict(entry=hex(PREDICATE_START), end_exclusive=hex(PREDICATE_END),
                size_bytes=len(raw), sha256=PREDICATE_SHA, bytes_hex=raw.hex(),
                fragments=[dict(start=hex(PREDICATE_START), end_exclusive=hex(PREDICATE_END),
                                unwind=hex(PREDICATE_UNWIND), size_bytes=len(raw),
                                sha256=PREDICATE_SHA)],
                code_start=hex(PREDICATE_START), code_end_exclusive=hex(PREDICATE_END),
                instruction_count=len(instructions), instructions=[detail(x) for x in instructions],
                cfg=cfg, local_branches=branches, external_relocations=[], indirect_control=[],
                abi='RCX=record tag filter, RDX=&source+58h; compares up to four DWORD '
                    'source tags against filter DWORDs and filter count at +40h, returns AL. '
                    'No player-count input and no calls or RIP references.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    im = Image(args.evidence)
    body = pin_body(im)
    predicate = pin_tag_predicate(im)
    caller = pin_caller(im)
    result = dict(schema='roster_player_count_native_v1', source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  replay_sha256=sha(Path(__file__).read_bytes()),
                  bodies={hex(START):body, hex(PREDICATE_START):predicate},
                  caller_count_producer=caller,
                  count_flow=dict(source='94C9C0 [RSP+168h] unsigned clamp [1,4] -> EBP',
                                  call_abi='15 callsites store EBP to caller [RSP+38h]; 94BE10 body [RSP+158h]',
                                  consumer='94C06E loads DWORD; 94C075/7B compares against each record min/max at R8+F4h/F8h, inclusive unsigned; AL gates normal accept at 94C0AD/AF',
                                  override='If [body RSP+168h] is nonzero and SIL matches, 94C09B jumps to 94C0BD, bypassing the normal BL/CL/AL/DL gates',
                                  distinct_tech_level='94BEDC reads [body RSP+150h] to R12D; downstream [rsi+rax*4+30h] tables index R12D-1, not player count'),
                  limits=['No record-array heap capture: actual R8/R9 backing and min/max values for 5..8 remain unknown.',
                          'The consumer has no literal four-player clamp; the caller clamps [1,4] before all 15 calls.',
                          '177E3C0 is pinned only as the directly called tag predicate; its result gates records but it has no player-count input.',
                          'No live process, new capture, code emission, hook, or multiplayer execution.'])
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), body_sha256=BODY_SHA,
                          instructions=body['instruction_count'],
                          local_branches=len(body['local_branches']),
                          external_relocations=len(body['external_relocations']),
                          caller_sites=caller['count_argument_site_count'])))


if __name__ == '__main__':
    main()
