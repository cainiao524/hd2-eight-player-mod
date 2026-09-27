"""Read a saved live prefix and pinned disk EXE; never access the game process."""
import argparse
import hashlib
import json
from pathlib import Path

import capstone
import pefile
from capstone.x86 import X86_OP_IMM

EXPECTED_PROBE_SHA256 = 'a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def section_row(section, rva, size):
    delta = rva - section.VirtualAddress
    return {'name': section.Name.rstrip(b'\0 ').decode('ascii', 'replace'),
            'virtual_address': hex(section.VirtualAddress),
            'virtual_size': hex(section.Misc_VirtualSize),
            'raw_size': hex(section.SizeOfRawData),
            'raw_file_offset': hex(section.PointerToRawData),
            'rva_delta': hex(delta),
            'requested_size': size,
            'backed_by_raw_file_bytes': 0 <= delta and delta + size <= section.SizeOfRawData}


def section_for(pe, rva):
    return next((s for s in pe.sections
                 if s.VirtualAddress <= rva < s.VirtualAddress+s.Misc_VirtualSize), None)


def ins_row(ins):
    return {'rva': hex(ins.address), 'bytes': ins.bytes.hex(),
            'sha256': digest(ins.bytes), 'asm': ins.mnemonic + ' ' + ins.op_str}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--probe', required=True)
    p.add_argument('--exe', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    probe_raw = Path(a.probe).read_bytes()
    probe_sha = digest(probe_raw)
    require(probe_sha == EXPECTED_PROBE_SHA256, 'saved probe JSON hash mismatch')
    probe = json.loads(probe_raw)
    pinned = probe['pinned_images']['helldivers2.exe']
    require(str(Path(a.exe)).lower() == str(Path(pinned['path'])).lower(),
            'EXE path differs from pinned probe path')
    raw = Path(a.exe).read_bytes()
    disk_sha = digest(raw)
    require(disk_sha == pinned['sha256'], 'pinned EXE hash mismatch')
    pe = pefile.PE(data=raw, fast_load=True)
    require(pe.FILE_HEADER.TimeDateStamp == pinned['pe_identity']['timestamp'],
            'PE timestamp mismatch')
    require(pe.OPTIONAL_HEADER.SizeOfImage == pinned['pe_identity']['image_size'],
            'PE image size mismatch')
    table = next(x for x in probe['tables'] if x['root_offset'] == '0xf8')
    slot = next(x for x in table['functions'] if x['slot'] == '0xa0')
    rva = int(slot['module_rva'], 0)
    prefix = bytes.fromhex(slot['bytes'])
    require(len(prefix) == slot['size'] and digest(prefix) == slot['sha256'],
            'saved live prefix fingerprint mismatch')
    target_section = section_for(pe, rva)
    require(target_section is not None, 'target RVA outside EXE sections')
    target_coverage = section_row(target_section, rva, len(prefix))
    if target_coverage['backed_by_raw_file_bytes']:
        disk_prefix = pe.get_data(rva, len(prefix))
        prefix_disk_comparison = {'available': True,
                                  'exact_match': disk_prefix == prefix,
                                  'disk_prefix_sha256': digest(disk_prefix)}
    else:
        prefix_disk_comparison = {'available': False, 'exact_match': None,
                                  'reason': 'RVA extends beyond this PE section raw-data size'}
    exc = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
    exc_section = section_for(pe, exc.VirtualAddress)
    exc_coverage = section_row(exc_section, exc.VirtualAddress, exc.Size) if exc_section else None
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    instructions = []
    direct_calls = []
    first_ret = None
    for ins in md.disasm(prefix, rva):
        instructions.append(ins_row(ins))
        if ins.mnemonic == 'call' and ins.operands[0].type == X86_OP_IMM:
            callee = ins.operands[0].imm
            section = section_for(pe, callee)
            direct_calls.append({'site': ins_row(ins), 'callee_rva': hex(callee),
                                 'callee_section': section_row(section, callee, 1) if section else None,
                                 'callee_bytes_in_saved_probe': rva <= callee < rva+len(prefix)})
        if ins.mnemonic == 'ret':
            first_ret = ins.address
            break
    require(first_ret is not None, 'saved prefix does not contain function return')
    result = {'schema_version': 1,
              'evidence_kind': 'saved live prefix and pinned offline EXE only',
              'probe_path': str(Path(a.probe)),
              'probe_json_sha256': probe_sha,
              'probe_utc': probe['utc'], 'probe_build': probe['build'],
              'runtime_capture_prefix_sha256': slot['sha256'],
              'disk_path': str(Path(a.exe)), 'disk_sha256': disk_sha,
              'pe_timestamp': pe.FILE_HEADER.TimeDateStamp,
              'pe_image_size': pe.OPTIONAL_HEADER.SizeOfImage,
              'target_rva': hex(rva), 'target_section': target_coverage,
              'prefix_disk_comparison': prefix_disk_comparison,
              'exception_directory': {'rva': hex(exc.VirtualAddress),
                                      'size': hex(exc.Size),
                                      'section': exc_coverage,
                                      'disk_unwind_entries_parseable': bool(exc_coverage and exc_coverage['backed_by_raw_file_bytes'])},
              'saved_prefix_first_ret_rva': hex(first_ret),
              'saved_prefix_function_instructions': instructions,
              'direct_calls_from_saved_prefix_function': direct_calls,
              'observed_int_arg_flow': [
                  {'rva': '0x8c6742', 'effect': 'ECX first integer argument copied to ESI'},
                  {'rva': '0x8c67b2', 'effect': 'ESI copied to EDX for call at 0x8c67c2'},
                  {'rva': '0x8c67bb', 'effect': 'ESI stored as dword at [returned object + 0x20]'},
              ],
              'limits': ['Only the saved 256-byte prefix was observed at runtime.',
                         'The target and both direct callees are virtual-only in the pinned disk EXE; no disk code bodies can be validated.',
                         'PE exception directory is virtual-only, so disk unwind bounds cannot be parsed.',
                         'No invocation, server acceptance, or eight-player mission was observed.']}
    output = Path(a.output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
