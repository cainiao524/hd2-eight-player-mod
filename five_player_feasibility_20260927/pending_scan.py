"""Bounded, fingerprinted static scan for HostSynchronizer pending-record offsets."""
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import CS_OP_MEM

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str((SCRIPT_DIR / '../research_handoff_20260927/indirect').resolve()))
from inspect_capture import Image, row  # noqa: E402

EVIDENCE = Path(
    r'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced\build\existing-code-evidence-25480438'
)
OFFSETS = (0x808, 0x810, 0x820, 0x830, 0x838, 0x840, 0x848, 0x888, 0x8C8)
START, END = 0x1070000, 0x10A0000


def main():
    im = Image(EVIDENCE)
    code = im.read(START, END - START)
    results = []
    seen = set()
    for offset in OFFSETS:
        pattern = struct.pack('<I', offset)
        at = 0
        while True:
            at = code.find(pattern, at)
            if at < 0:
                break
            rva = START + at
            for start in range(max(START, rva - 10), rva + 1):
                ins = im.instruction(start)
                if ins is None or not (ins.address <= rva < ins.address + ins.size):
                    continue
                if not any(op.type == CS_OP_MEM and op.mem.disp == offset for op in ins.operands):
                    continue
                if ins.address in seen:
                    break
                seen.add(ins.address)
                item = row(ins)
                item['displacement'] = hex(offset)
                item['fragment'] = [hex(x) for x in im.containing(ins.address)]
                item['root'] = [hex(x) for x in im.root(ins.address)]
                results.append(item)
                break
            at += 1
    results.sort(key=lambda x: int(x['rva'], 16))
    output = {
        'scope': 'Pinned capture code range 0x1070000..0x10a0000, validated against captured unwind instruction boundaries',
        'capture_report_sha256': hashlib.sha256(im.files['capture-report.json']).hexdigest(),
        'captured_data_sha256': hashlib.sha256(im.files['captured-data.bin']).hexdigest(),
        'offsets': [hex(x) for x in OFFSETS],
        'matches': results,
        'limits': [
            'A matching displacement alone does not establish that the base register is a HostSynchronizer.',
            'Derived-address and register arithmetic may refer to pending records without a literal offset.',
            'The bounded range omits functions outside 0x1070000..0x10a0000.',
        ],
    }
    target = SCRIPT_DIR / 'pending_offset_candidates.json'
    target.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(target)
    print(len(results))


if __name__ == '__main__':
    main()
