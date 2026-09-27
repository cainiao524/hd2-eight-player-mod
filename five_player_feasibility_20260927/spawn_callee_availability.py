"""Check saved EXE callee availability; this script has no process APIs."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import capstone

HERE = Path(__file__).resolve().parent
EXE_SHA = 'f5fee03dcfdb2e553a4752c283590950ac13316b376d8196aa556ff0400d5f06'
CAPTURES = {
    'interface_probe_live_20260927_1.json': 'a45e5f5b1647d808b8b7716fd750e4a894ab39a3021b52a0b10c404403a8b85f',
    'engine_callee_live_20260927_1.json': '157ddf9f9f9c04265dbc80109441af7090fcf78316e8642781857668348f129a',
    'spawn_interface_live_20260927_1.json': '44773c271226df2df3a93991421287cee71ea7971cbad877ed5a70275dff798a',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError('SHA mismatch: '+str(path))
    return raw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    dest = Path(a.output)
    if dest.exists():
        raise FileExistsError(dest)
    raw = checked(Path(a.exe), EXE_SHA)
    nt = struct.unpack_from('<I', raw, 0x3C)[0]
    n = struct.unpack_from('<H', raw, nt+6)[0]
    opt = struct.unpack_from('<H', raw, nt+20)[0]
    table = nt+24+opt
    sections = []
    for k in range(n):
        off = table+k*40
        vs, va, rs, rp = struct.unpack_from('<4I', raw, off+8)
        ch = struct.unpack_from('<I', raw, off+36)[0]
        sections.append(dict(index=k, name_hex=raw[off:off+8].hex(),
                             virtual_address=hex(va), virtual_size=hex(vs), virtual_end=hex(va+vs),
                             raw_size=hex(rs), raw_pointer=hex(rp), raw_backed_rva_end=hex(va+rs),
                             characteristics=hex(ch)))
    def disk(rva, size):
        for s in sections:
            va = int(s['virtual_address'], 16)
            vs = int(s['virtual_size'], 16)
            rs = int(s['raw_size'], 16)
            if va <= rva < va+max(vs, rs):
                delta = rva-va
                backed = delta+size <= rs
                at = int(s['raw_pointer'], 16)+delta
                b = raw[at:at+size] if backed else None
                return dict(rva=hex(rva), size=size, section=s, section_offset=hex(delta),
                            fully_raw_backed=backed, file_offset=hex(at) if backed else None,
                            first32_hex=b[:32].hex() if b is not None else None,
                            sha256=sha(b) if b is not None else None), b
        raise ValueError('no section: '+hex(rva))
    captured = []
    js = {}
    for name, digest in CAPTURES.items():
        j = json.loads(checked(HERE/name, digest))
        assert j['pinned_images']['helldivers2.exe']['sha256'] == EXE_SHA
        js[name] = j
        ranges = list(j.get('ranges', []))
        for t in j.get('tables', []):
            ranges.extend(t.get('functions', []))
        if 'function' in j:
            ranges.append(j['function'])
        for r in ranges:
            start = int(r.get('module_rva', r.get('rva')), 0)
            data = bytes.fromhex(r['bytes'])
            assert len(data) == r['size'] and sha(data) == r['sha256']
            captured.append(dict(file=name, file_sha256=digest, module='helldivers2.exe',
                                 rva=hex(start), size=len(data), end_exclusive=hex(start+len(data)),
                                 sha256=sha(data), covers_callee_entry=start <= 0x1AE380 < start+len(data)))
    f = js['spawn_interface_live_20260927_1.json']['function']
    loaded = bytes.fromhex(f['bytes'])
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    insns = []
    for i in md.disasm(loaded, int(f['module_rva'], 0)):
        insns.append(dict(rva=hex(i.address), bytes=i.bytes.hex(), asm=i.mnemonic+' '+i.op_str))
        if i.mnemonic == 'ret':
            break
    assert len(insns) == 9 and insns[5]['asm'] == 'call 0x1ae380'
    wrapper, disk_wrapper = disk(0x30FF50, len(loaded))
    callee, _ = disk(0x1AE380, 256)
    diff = next((k for k, (x, y) in enumerate(zip(loaded, disk_wrapper)) if x != y), None)
    result = dict(
        exe=dict(path=str(Path(a.exe).resolve()), size=len(raw), sha256=EXE_SHA),
        target='0x1ae380', callee_disk=callee, wrapper_disk=wrapper,
        loaded_wrapper=dict(source='spawn_interface_live_20260927_1.json', sha256=f['sha256'],
                            instructions=insns, first32_hex=loaded[:32].hex()),
        same_section_disk_loaded_comparison=dict(first_differing_offset=diff,
                                                complete_4096_equal=loaded == disk_wrapper),
        saved_exe_ranges=captured, covered_by_identified_saved_exe_capture=any(r['covers_callee_entry'] for r in captured),
        conclusion='Disk raw bytes exist, but no validated loaded implementation for EXE RVA 1AE380 is available in the identified saved captures.',
        limits=[
            'Disk bytes at the called RVA were not interpreted as loaded code.',
            'The wrapper disk mismatch establishes that raw mapping alone is insufficient; it does not directly compare the unobserved loaded callee.',
            'Inventory covers the three identified EXE captures in this workspace, not every file on the computer.',
            'The older pinned large capture is game.dll; identical numeric RVAs there are a different module.',
            'No live process read, new capture, game-file change, or new authorization request.'])
    dest.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(dest), callee_raw_backed=callee['fully_raw_backed'],
                          saved_exe_windows=len(captured), callee_saved=False, wrapper_disk_difference=diff)))


if __name__ == '__main__':
    main()
