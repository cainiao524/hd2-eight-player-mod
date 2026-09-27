"""Exploratory read-only disassembly; --rva must be a known instruction boundary.

This utility alone does not prove boundaries or semantics. The reviewed claims
are separately checked by settings_findings.py against continuous decoding.
"""
import argparse
import json
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64

parser = argparse.ArgumentParser()
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--rva', type=lambda x: int(x, 0), required=True)
parser.add_argument('--size', type=lambda x: int(x, 0), required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.repo / 'tools'))
import generation_research as study
folder = args.repo / 'build/existing-code-evidence-25480438'
study.load_code_evidence(folder)
image = study.CapturedImage(json.loads((folder / 'capture-report.json').read_bytes()),
                            (folder / 'captured-data.bin').read_bytes())
dis = Cs(CS_ARCH_X86, CS_MODE_64)
for insn in dis.disasm(image.read(args.rva, args.size), args.rva):
    print(f'{insn.address:#x}: {insn.bytes.hex():24s} {insn.mnemonic} {insn.op_str}')
