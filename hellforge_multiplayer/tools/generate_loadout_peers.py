"""Shared instruction emitter for saved UI confirmed-peer readers.

The native count destination is dead before its original load. Use that same
register to check the global owner before dereferencing it, then bound the
actual loop count. No stack changes or invented scratch-register lifetime.
"""


def count_guard(blob,fix,instruction,owner,count,client_key):
    raw=bytes((0x48+(count>=8),0xb8+(count&7)))+bytes(8)
    fix(raw,2,client_key,1,-0x162c8)
    blob.extend(bytes((0x48+4*(count>=8)+(owner>=8),0x39,0xc0+((count&7)<<3)+(owner&7))))
    fix(b'\x0f\x85'+bytes(4),2,6,0)
    blob.extend(instruction)
    raw=(b'\x41' if count>=8 else b'')+b'\x81'+bytes((0xf8+(count&7),))
    fix(raw+bytes(4),len(raw),5,2)
    fix(b'\x0f\x87'+bytes(4),2,6,0)
