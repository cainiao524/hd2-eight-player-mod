"""Read-only disassembly of pinned existing capture; no live-process access."""
from pathlib import Path
import argparse, hashlib, json, struct, sys
import capstone

REPO = Path(r'C:\Users\OvO\Documents\Codex\2026-09-26\referenced-chatgpt-conversation-this-is-an\outputs\healing-pistol-enhanced')
sys.path.insert(0, str(REPO / 'tools'))
from generation_research import CapturedImage, load_code_evidence

def load():
    folder = REPO / 'build/existing-code-evidence-25480438'
    evidence = load_code_evidence(folder)
    report = json.loads((folder / 'capture-report.json').read_text())
    return CapturedImage(report, (folder / 'captured-data.bin').read_bytes()), evidence, report

def read_large(image, rva, size):
    return b''.join(image.read(at,min(4096,rva+size-at)) for at in range(rva,rva+size,4096))

def fragments(image,report):
    region=next(x for x in report['ranges'] if x['label']=='unwind')
    data=read_large(image,region['rva'],region['size'])
    return [struct.unpack_from('<III',data,at) for at in range(0,len(data),12)]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('rva', type=lambda x:int(x,0))
    p.add_argument('size', type=lambda x:int(x,0))
    p.add_argument('--pattern')
    p.add_argument('--filter')
    p.add_argument('--rip-target',type=lambda x:int(x,0))
    p.add_argument('--fragment',action='store_true')
    a = p.parse_args()
    image, evidence, report = load()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    if a.fragment:
        for start,end,unwind in fragments(image,report):
            if start<=a.rva<end:
                print(hex(start),hex(end),hex(unwind))
        return
    if a.rip_target is not None:
        import re
        region=next(x for x in report['ranges'] if x['label']=='code')
        first=next(x for x in report['chunks'] if x['range']=='code')
        data=image.raw[first['file_offset']:first['file_offset']+region['size']]
        for match in re.finditer(rb'[\x40-\x4f]?[\x8b\x89\x8d][\x05\x0d\x15\x1d\x25\x2d\x35\x3d]',data):
            start=match.start(); end=match.end()+4
            if end>len(data): continue
            at=first['rva']+start
            dest=first['rva']+end+struct.unpack('<i',data[match.end():end])[0]
            if dest==a.rip_target:
                i=next(md.disasm(data[start:end],at),None)
                if i: print(f'{i.address:#010x} {i.bytes.hex():24s} {i.mnemonic:8s} {i.op_str}')
        return
    if a.pattern:
        pat=bytes.fromhex(a.pattern)
        for row in report['chunks']:
            if row['range'] != 'code' or row['kind'] != 'DATA': continue
            raw=image.read(row['rva'],row['size'])
            off=raw.find(pat)
            while off >= 0:
                at=row['rva']+off
                print(hex(at))
                off=raw.find(pat,off+1)
        return
    for i in md.disasm(image.read(a.rva,a.size),a.rva):
        if a.filter and not __import__('re').search(a.filter,i.mnemonic+' '+i.op_str): continue
        print(f'{i.address:#010x} {i.bytes.hex():24s} {i.mnemonic:8s} {i.op_str}')
if __name__ == '__main__': main()
