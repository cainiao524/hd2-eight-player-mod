"""Bounded offline check of roster append registration and known dispatch paths.

Reads only the pinned capture and prior evidence. No live process or hook.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row

PRIOR = {
    'spawn_callback_registration_evidence_v2.json':
        '142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109',
    'spawn_callback_registration_first_phase_fields.json':
        '64ed066dd5f6496a7fae13ffcec2f885a05d9cdbe50203898e67416736adce10',
    'roster_dispatch_evidence_v2.json':
        'e83d0bc3ace27f26b7e77511cd01c09b9ed3b26996abe8661a21b77ae2d47f03',
    'roster_compact_native_evidence.json':
        '7648e3bcdcbb4a58fd76b5387ee276fdd7c6b3fd8fa5630c2ea5c3a6d53c7cc3',
}
FDC780_SHA256 = '61bda56a4260158aeff7b3bc5ab3dbb6fb8ad639187ec11d964773eec2f63400'
SLICES = {
    'known_create_call': (0xFDC250, 0xFDC25F,
        '007199007ebc6eb9edd387931ba481e280f3c1f93a746c88458699adecb446cf'),
    'known_second_table_reader': (0x58140A, 0x581423,
        '873f0c672ebb8d2b28171a7c95ba06086947fed5705809191e6057881c83fcd8'),
    'compact_owner_call': (0xFDC7A3, 0xFDC7AC,
        '23ae77443741a56c8832456b35127ac0ffd73ef8e41213c7f654a0ac09b886d4'),
    'bounded_spawn_update_caller': (0xAB5135, 0xAB5158,
        '73e165a2f96c3cf060d4b4ccb541a6017b63129b491b97fce36f65736f1efbbc'),
    'bounded_global_update_caller': (0x108AE23, 0x108AE36,
        'd254dc0523c042ab965ed71f73ce05614ba2e155c783527b3e32d3028f5a86b1'),
}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def slice_row(im, start, end, expected_sha):
    raw = im.read(start, end - start)
    require(sha(raw) == expected_sha, 'slice changed at ' + hex(start))
    ins = list(im.md.disasm(raw, start))
    require(sum(x.size for x in ins) == len(raw),
            'slice not on complete instruction boundaries at ' + hex(start))
    return dict(start=hex(start), end_exclusive=hex(end),
                sha256=sha(raw), bytes_hex=raw.hex(),
                instructions=[row(x) for x in ins]), {x.address: x for x in ins}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    require(not args.output.exists(), 'refusing to overwrite output')
    prior = {}
    for name, expected in PRIOR.items():
        data = (HERE / name).read_bytes()
        require(sha(data) == expected, 'prior evidence changed: ' + name)
        prior[name] = json.loads(data)
    im = Image(args.evidence)

    registration = prior['spawn_callback_registration_evidence_v2.json']['component_239'][0]
    require(registration['table_base_offset'] == '0xf0b6f0' and
            registration['component_index'] == 239 and
            registration['destination_offset'] == '0xf0be68' and
            registration['target_rva'] == '0x540850' and
            0xF0B6F0 + 239 * 8 == 0xF0BE68,
            'component 239 first-table assignment changed')
    for kind in ('lea', 'store'):
        x = registration[kind]
        require(im.read(int(x['rva'], 16), len(bytes.fromhex(x['bytes']))) ==
                bytes.fromhex(x['bytes']), 'initializer instruction changed')
    second_registration = prior['spawn_callback_registration_evidence_v2.json']['component_239'][1]
    require(second_registration['table_base_offset'] == '0xf0c110' and
            second_registration['component_index'] == 239 and
            second_registration['destination_offset'] == '0xf0c888' and
            second_registration['target_rva'] == '0x540920' and
            0xF0C110 + 239 * 8 == 0xF0C888,
            'component 239 second-table assignment changed')
    for kind in ('lea', 'store'):
        x = second_registration[kind]
        require(im.read(int(x['rva'], 16), len(bytes.fromhex(x['bytes']))) ==
                bytes.fromhex(x['bytes']), 'second-table initializer changed')
    fields = prior['spawn_callback_registration_first_phase_fields.json']['offsets']
    require(all(fields[k]['references'] == [] and
                fields[k]['raw_matches_outside_unwind'] == 1
                for k in ('0xf0b6f0', '0xf0b730')),
            'previous bounded first-phase fieldscan changed')

    slices, ins = {}, {}
    for name, (start, end, digest) in SLICES.items():
        slices[name], ins[name] = slice_row(im, start, end, digest)
    require(im.root(0xFDC25A)[0] == 0xFDC140 and
            im.root(0x581421)[0] == 0x581320 and
            im.root(0xFDC7A7)[0] == 0xFDC780 and
            im.root(0x57E01C)[0] == 0x576CF0,
            'known path unwind roots changed')
    create = ins['known_create_call']
    second = ins['known_second_table_reader']
    owner = ins['compact_owner_call']
    require(create[0xFDC250].bytes.hex() == '488d4e40' and
            create[0xFDC25A].operands[0].type == X86_OP_IMM and
            create[0xFDC25A].operands[0].imm == 0x581320,
            'FDC140 owner+40 dispatch edge changed')
    require(second[0x58140A].bytes.hex() == '0fb70c48' and
            second[0x58140E].bytes.hex() == '498b84cc10c1f000' and
            second[0x581416].bytes.hex() == '4885c0' and
            second[0x581419].bytes.hex() == '740c' and
            second[0x58141B].bytes.hex() == '488bd6' and
            second[0x58141E].bytes.hex() == '498bcf' and
            second[0x581421].bytes.hex() == 'ffd0',
            'second table index/conditional call changed')
    require(owner[0xFDC7A3].bytes.hex() == '488d4b40' and
            owner[0xFDC7A7].operands[0].imm == 0x576CF0,
            'FDC780 owner update edge changed')
    full_update, full_ins = slice_row(im, 0xFDC780, 0xFDC81F,
                                      FDC780_SHA256)
    require(im.root(0xFDC780)[:2] == (0xFDC780, 0xFDC81F) and
            full_ins[0xFDC78F].bytes.hex() == '488bd9' and
            full_ins[0xFDC7A7].operands[0].imm == 0x576CF0,
            'complete FDC780 body changed')
    compact = prior['roster_compact_native_evidence.json']
    compact_caller = compact['caller_slice']
    require(compact_caller['start'] == '0x57e00f' and
            compact_caller['instructions'][2]['rva'] == '0x57e01c' and
            compact_caller['instructions'][2]['asm'] == 'call 0x60cc70',
            'owner-to-compactor edge changed')
    bounded = ins['bounded_global_update_caller']
    rip = [op.mem.disp for op in bounded[0x108AE23].operands
           if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP]
    require(rip and 0x108AE23 + bounded[0x108AE23].size + rip[0] == 0x346BF98 and
            bounded[0x108AE31].operands[0].imm == 0xFDC780,
            'bounded global-context update caller changed')
    spawn = ins['bounded_spawn_update_caller']
    require(spawn[0xAB513E].operands[0].imm == 0xFDC780 and
            spawn[0xAB5143].operands[1].mem.base == X86_REG_RIP and
            0xAB5143 + spawn[0xAB5143].size +
            spawn[0xAB5143].operands[1].mem.disp == 0x3326468,
            'bounded spawn update and subsequent roster count read changed')

    result = dict(source_sha256=EXPECTED,
                  capture_identity_sha256=im.report['capture_sha256'],
                  prior_sha256=PRIOR,
                  first_table_registration=registration,
                  second_table_registration=second_registration,
                  prior_first_table_fieldscan={k: fields[k]
                                               for k in ('0xf0b6f0', '0xf0b730')},
                  verified_slices=slices,
                  complete_FDC780=full_update,
                  owner_compact_caller=compact_caller,
                  known_dispatch=dict(
                      path='FDC140 → 581320; resource component index → owner+F0C110[index] → conditional call',
                      component239_registered_target='0x540920',
                      null_skip='0x581416 test; 0x581419 je 581427',
                      callback_abi='RCX=entity record; RDX=creation params',
                      creation_following_steps='FDC275 handle-map insertion when handle!=7FFF; '
                                               'FDC29B apply only on params[0]==0; FDC2B1 later 581780'),
                  compact_update=dict(
                      path='FDC780 → unconditional FDC7A7 call 576CF0 → owner+EA0818 at 57E00F → 57E01C call 60CC70',
                      bounded_other_callers=['AB513E uses R14+E49F0 then reads roster dense+84',
                                             '108AE31 uses global346BF98 if nonnull']),
                  conclusion='No verified F0B6F0 table reader in the pinned prior fieldscan or bounded paths. '
                             'Registration alone does not establish 540850 invocation, order against 540920, '
                             'or a shared lifecycle with compact.',
                  limits=[
                      'The prior fieldscan checks exact encoded offsets with unwind-covered instruction validation; computed table addresses, non-unwind leaf readers, and uncaptured code remain possible.',
                      'The two bounded FDC780 callers do not establish a call order with FDC140/581320.',
                      'No live table value, runtime branch, game process, hook, or multiplayer execution was observed.'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), registration_target='0x540850',
                          verified_reader='F0C110 only',
                          update_body_bytes=len(bytes.fromhex(full_update['bytes_hex'])))))


if __name__ == '__main__':
    main()
