"""Relocate the saved 1466170 native screen setup; never access a game.

The original controls/parent attachment stay native. Player widget positions
come from an immutable per-slot table, not a read past the four-float table.
"""
from generate_loadout_peers import count_guard
import argparse
import json
import struct
from generate_loadout_lifecycle import Capture, PROJECT, need, GS_HANDLER
from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_RIP

START,END=0x1466170,0x1467325
UNWIND=bytes.fromhex('19350f002768140023743300236432002334310023012a0018f016e014d012c010500000')
COOKIE=0x130
MAX_IMAGE=8192
HEADER=PROJECT/'mod/src/ep_loadout_setup_template.h'


def build(peers=False):
    capture=Capture();b,e,at=next(f for f in capture.functions if f[0]==START)
    need(e==END and capture.read(at,len(UNWIND)+8)==UNWIND+struct.pack('<II',GS_HANDLER,COOKIE),'Changed setup unwind/GS contract')
    blob=bytearray();fixes=[];branches=[];mapping={}
    def fix(raw,operand,key,kind=1,add=0):
        base=len(blob);blob.extend(raw);fixes.append((base+operand,len(blob),key,kind,add))
    def absolute(reg,key,add=0):fix(bytes((0x48+(reg>=8),0xb8+(reg&7)))+bytes(8),2,key,1,add)
    def branch(op,target):
        base=len(blob);blob.extend(op+bytes(4));branches.append((base+len(op),len(blob),target))
    absolute(11,2);blob.extend(b'\x4c\x39\xd9');fix(b'\x0f\x85'+bytes(4),2,6,0)
    body=len(blob);source=capture.read(b,e-b);insns=list(capture.md.disasm(source,b))
    need(insns[-1].address+insns[-1].size==END,'Incomplete setup decode')
    layout_fix=None
    expected={
        0x1466ad4:'lea r12, [rip + 0xd724dd]',0x1466adb:'lea rbx, [rdi + 0x562f9]',
        0x1466ae2:'lea rsi, [rdi + 0x53a78]',0x1466afd:'mov dword ptr [rbp + 0x20], 0',
        0x1466b07:'mov dword ptr [rbp + 0x24], 0x42de0000',0x1466b0e:'mov rdx, qword ptr [rbp + 0x20]',
        0x1466b17:'movss xmm1, dword ptr [r12]',0x1466b20:'movss dword ptr [rsp + 0x48], xmm1',
        0x1466b26:'mov dword ptr [rsp + 0x4c], 0',0x1466b2e:'mov rdx, qword ptr [rsp + 0x48]',
        0x1466b38:'mov qword ptr [rsp + 0x40], 0x3f000000',0x1466b44:'mov rdx, qword ptr [rsp + 0x40]',
        0x1466c42:'add r12, 4',0x14670c1:'mov dword ptr [rdi + 0x27d4], ecx',
        0x14670c7:'mov dword ptr [rdi + rcx*4 + 0x27d8], r14d',0x14670cf:'mov dword ptr [rdi + 0x27e8], ecx',
    }
    seen=set()
    for ins in insns:
        a=ins.address;mapping[a]=len(blob);start=len(blob)
        if a in expected:
            need(ins.mnemonic+' '+ins.op_str==expected[a],'Changed setup operand');seen.add(a)
        if peers and a==0x1466f5d:
            need(ins.mnemonic+' '+ins.op_str=='mov r9d, dword ptr [r8 + 0x16390]','Changed setup peer count')
            count_guard(blob,fix,ins.bytes,8,9,11)
        elif peers and a==0x1466f88:
            # R8 still owns the native session pointer at +162C8. R11 is dead
            # in this lookup window; do not rebase R8 before the local-ID read.
            absolute(11,12);blob.extend(b'\x4d\x39\x14\x03')
        elif peers and a==0x14670b0:
            absolute(1,12);blob.extend(b'\x8b\x4c\x11\x14')
        elif a==0x1466ad4:
            absolute(12,1);layout_fix=len(fixes)-1
        elif a==0x1466adb:absolute(3,4,0x2881)
        elif a==0x1466ae2:
            absolute(6,4)
            # R13=4 was an equipment enum AND a byte stride earlier. Replace
            # it only here, once it becomes the outer player-loop counter.
            fix(b'\x41\xbd'+bytes(4),2,5,2)
        elif a in (0x1466afd,0x1466b07,0x1466b17,0x1466b20,0x1466b26,0x1466b38):blob.extend(b'\x90')
        elif a==0x1466b0e:blob.extend(b'\x49\x8b\x14\x24')
        elif a==0x1466b2e:blob.extend(b'\x49\x8b\x54\x24\x08')
        elif a==0x1466b44:blob.extend(b'\x49\x8b\x54\x24\x10')
        elif a==0x1466c42:blob.extend(b'\x49\x83\xc4\x18')
        elif a in (0x1466f26,0x1466f31,0x1466f3c,0x1466f47):
            need(ins.mnemonic=='mov' and ins.op_str.endswith(', 0xffffffffffffffff'),'Changed map reset')
            if a in (0x1466f26,0x1466f31):
                absolute(11,7 if a==0x1466f26 else 8)
                for offset in (0,8,16,24):blob.extend(b'\x49\xc7\x43'+bytes((offset,))+b'\xff'*4)
            else:blob.extend(b'\x90')
        elif a==0x14670c1:
            fix(b'\x81\xf9'+bytes(4),2,5,2);branch(b'\x0f\x83',0x1466f9d)
            blob.extend(ins.bytes)
        elif a==0x14670c7:absolute(11,7);blob.extend(b'\x45\x89\x34\x8b')
        elif a==0x14670cf:absolute(11,8);blob.extend(b'\x41\x89\x0b')
        elif (ins.mnemonic=='call' or ins.mnemonic.startswith('j')) and ins.operands[0].type==X86_OP_IMM:
            raw=bytes(ins.bytes);target=ins.operands[0].imm
            if raw[0] in (0xe8,0xe9):op=raw[:1]
            elif raw[0]==0xeb:op=b'\xe9'
            elif 0x70<=raw[0]<=0x7f:op=bytes((0x0f,raw[0]+0x10))
            else:
                need(raw[0]==0x0f and 0x80<=raw[1]<=0x8f,'Unsupported setup branch');op=raw[:2]
            if START<=target<END:branch(op,target)
            else:fix(op+bytes(4),len(op),0,0,target)
        else:
            blob.extend(ins.bytes)
            if any(o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP for o in ins.operands):
                need(struct.unpack_from('<i',ins.bytes,ins.disp_offset)[0]==ins.disp,'Invalid RIP operand')
                fixes.append((start+ins.disp_offset,len(blob),0,0,a+ins.size+ins.disp))
        if a<START+UNWIND[1]:need(blob[start:]==ins.bytes and start-body==a-START,'Setup prologue moved')
    need(seen==set(expected) and layout_fix is not None,'Missing setup replacement')
    for offset,nxt,target in branches:
        need(target in mapping,'Invalid branch boundary');fixes.append((offset,nxt,1,0,mapping[target]))
    body_end=len(blob)
    # Configure already constructed, not-yet-attached player widgets without
    # running full screen setup a second time. Keep the original GS prologue,
    # RDI/screen + zero-XMM6 + R15/parent definitions, the complete player loop,
    # and cookie/epilogue. All nonplayer setup, local-user/map reset and final
    # screen refresh are omitted. The existing parent must be ready already.
    pieces=((0,mapping[0x14661a5]),(mapping[0x14661c3],mapping[0x14661c9]),
            (mapping[0x14661df],mapping[0x14661e6]),
            (mapping[0x1466ad4],mapping[0x1466c57]),(mapping[0x14672f3],body_end))
    blob.extend(b'\xcc'*(-len(blob)%16));attach=len(blob);clones=[]
    for lo,hi in pieces:
        need(lo<hi,'Empty player attachment segment')
        dest=len(blob);clones.append((lo,hi,dest));blob.extend(blob[lo:hi])
    def cloned_offset(old):
        matches=[dest+old-lo for lo,hi,dest in clones if lo<=old<hi]
        need(len(matches)==1,'Attachment branches into omitted screen setup')
        return matches[0]
    layout_fixes=[layout_fix];layout_operand=fixes[layout_fix][0]
    for offset,nxt,key,kind,add in list(fixes):
        for lo,hi,dest in clones:
            if not lo<=offset<hi:continue
            need(offset+(8 if kind==1 else 4)<=hi and lo<=nxt<=hi,'Split attachment relocation')
            need(key!=1 or kind==0 or offset==layout_operand,'Unexpected attachment code pointer')
            if offset==layout_operand:layout_fixes.append(len(fixes))
            fixes.append((dest+offset-lo,dest+nxt-lo,key,kind,
                          cloned_offset(add) if key==1 and kind==0 else add))
    attach_body=attach+body;attach_end=len(blob)
    attach_mapping={rva:cloned_offset(off) for rva,off in mapping.items()
                    if any(lo<=off<hi for lo,hi,dest in clones)}
    # Replace the FOUR original inline roots only. 144C9F0(parent,child,false)
    # unlinks one root without running the destructive 144DD70 branch. Native
    # render invalidation and descendant activation flags still change.
    # Keep one complete GS frame around record/map migration -> detach ->
    # attach. The native record-sync itself value-copies 9F0-byte records;
    # copying those values does not clone or transfer pointed-to ownership.
    original_fixes=list(fixes)
    def copy_segment(lo,hi):
        dest=len(blob);blob.extend(blob[lo:hi])
        for offset,nxt,key,kind,add in original_fixes:
            if lo<=offset<hi:
                need(key!=1 and offset+(8 if kind==1 else 4)<=hi and lo<=nxt<=hi,
                     'Unsupported replacement frame relocation')
                fixes.append((dest+offset-lo,dest+nxt-lo,key,kind,add))
    blob.extend(b'\xcc'*(-len(blob)%16));replace=len(blob)
    copy_segment(0,body)
    # All preflight is leaf code, before stack saves and before any writes.
    # Check complete, sorted parent child-list membership/backpointers within
    # 4096 nodes. This rejects missing/repeated old roots and malformed chains.
    labels={};jumps=[]
    def local(op,label):
        fix(op+bytes(4),len(op),1,0);jumps.append((len(fixes)-1,label))
    def reject(op=b'\x0f\x85'):fix(op+bytes(4),len(op),6,0)
    # Retain existing UI slots, including holes. Validate BOTH directions:
    # FF is unmapped, otherwise only four native slots/indices are legal.
    for source_map,reverse in ((0x27d8,0x27e8),(0x27e8,0x27d8)):
        for slot in range(4):
            label=f'map_{source_map:x}_{slot}'
            blob.extend(b'\x8b\x81'+struct.pack('<I',source_map+4*slot)+b'\x83\xf8\xff')
            local(b'\x0f\x84',label)
            blob.extend(b'\x83\xf8\x03');reject(b'\x0f\x87')
            blob.extend(b'\x83\xbc\x81'+struct.pack('<I',reverse)+bytes((slot,)));reject()
            labels[label]=len(blob)
    # +27D4 is the local network index; +27D0 is a cached record index that
    # can be FF before the first synchronization. Neither is a UI ordinal.
    blob.extend(b'\x8b\x81'+struct.pack('<I',0x27d0)+b'\x83\xf8\xff')
    local(b'\x0f\x84','cached_local')
    blob.extend(b'\x83\xf8\x03');reject(b'\x0f\x87')
    labels['cached_local']=len(blob)
    blob.extend(b'\x8b\x81'+struct.pack('<I',0x27d4)+b'\x83\xf8\x03');reject(b'\x0f\x87')
    blob.extend(b'\x83\xbc\x81'+struct.pack('<I',0x27d8)+b'\0');reject()
    blob.extend(b'\x4c\x8d\x99'+struct.pack('<I',0x2820)) # r11 = parent
    blob.extend(b'\x49\x8b\x83'+struct.pack('<I',0xe0))   # rax = first child
    blob.extend(b'\x45\x31\xc9\x41\xba'+struct.pack('<I',4096))
    labels['children']=len(blob)
    blob.extend(b'\x48\x85\xc0');reject(b'\x0f\x84')
    blob.extend(b'\x4c\x39\x98'+struct.pack('<I',0xf0));reject()
    for slot in range(4):
        blob.extend(b'\x48\x8d\x91'+struct.pack('<I',0x53a78+slot*0x1ee18))
        blob.extend(b'\x48\x39\xd0\x75\x05\x41\x0f\xba\xe9'+bytes((slot,)))
    blob.extend(b'\x4c\x8b\x80'+struct.pack('<I',0xe8)+b'\x4d\x85\xc0')
    local(b'\x0f\x84','end_children')
    blob.extend(b'\x49\x39\xc0');reject(b'\x0f\x86') # next must be > current
    blob.extend(b'\x4c\x89\xc0\x41\xff\xca');local(b'\x0f\x85','children')
    reject(b'\xe9')
    labels['end_children']=len(blob)
    blob.extend(b'\x41\x83\xf9\x0f');reject()
    absolute(10,4);fix(b'\x41\xb9'+bytes(4),2,5,2)
    blob.extend(b'\x41\x83\xf9\x04');reject(b'\x0f\x82')
    labels['fresh']=len(blob)
    for offset in (0xe8,0xf0):
        blob.extend(b'\x49\x83\xba'+struct.pack('<I',offset)+b'\0');reject()
    blob.extend(b'\x49\x81\xc2'+struct.pack('<I',0x1ee18)+b'\x41\xff\xc9')
    local(b'\x0f\x85','fresh')
    for index,label in jumps:fixes[index]=fixes[index][:-1]+(labels[label],)
    replace_body=len(blob)
    copy_segment(body,mapping[0x14661a5])
    copy_segment(mapping[0x14661c3],mapping[0x14661c9])
    copy_segment(mapping[0x14661df],mapping[0x14661e6])
    replace_point=len(blob)
    # The constructor already initialized the destination. Preserve its new
    # rows while importing every byte of the four old network-indexed records,
    # including currently inactive opaque values. Source inline records/maps
    # stay intact. The original screen's local/cache fields also stay intact.
    absolute(6,2,0x10);absolute(7,3)
    blob.extend(b'\xb9'+struct.pack('<I',4*0x9f0//8)+b'\xfc\xf3\x48\xa5')
    absolute(7,2) # restore RDI/screen for native detach and attachment
    for key,source_map in ((7,0x27d8),(8,0x27e8)):
        absolute(11,key)
        for offset in (0,8):
            blob.extend(b'\x48\x8b\x87'+struct.pack('<I',source_map+offset))
            blob.extend(b'\x49\x89\x43'+bytes((offset,)))
        for offset in (16,24):blob.extend(b'\x49\xc7\x43'+bytes((offset,))+b'\xff'*4)
    for slot in range(4):
        blob.extend(b'\x4c\x89\xf9\x48\x8d\x97'+struct.pack('<I',0x53a78+slot*0x1ee18))
        blob.extend(b'\x45\x31\xc0');fix(b'\xe8'+bytes(4),1,0,0,0x144c9f0)
    blob.extend(b'\x4c\x89\xf9');fix(b'\xe8'+bytes(4),1,0,0,0x144c2c0)
    blob.extend(b'\x48\x89\xf9');fix(b'\xe8'+bytes(4),1,1,0,attach)
    copy_segment(mapping[0x14672f3],body_end);replace_end=len(blob)
    blob.extend(b'\xcc'*(-len(blob)%16));handler=len(blob)
    fix(b'\xe9'+bytes(4),1,0,0,GS_HANDLER);code_bytes=len(blob)
    blob.extend(bytes(-len(blob)%8));placements=len(blob);blob.extend(bytes(8*24))
    for at in layout_fixes:
        f=fixes[at];fixes[at]=f[:-1]+(placements,)
    unwind_offset=len(blob);functions=[]
    gs=UNWIND+struct.pack('<II',handler,COOKIE)
    for begin,end,uw in ((0,body,b'\x01\0\0\0'),(body,body_end,gs),
                         (attach,attach_body,b'\x01\0\0\0'),(attach_body,attach_end,gs),
                         (replace,replace_body,b'\x01\0\0\0'),(replace_body,replace_end,gs),
                         (handler,code_bytes,b'\x01\0\0\0')):
        functions.append((begin,end,len(blob)));blob.extend(uw)
    table_offset=len(blob)
    for row in functions:blob.extend(struct.pack('<III',*row))
    need(len(blob)<=MAX_IMAGE,'Setup image exceeds storage')
    return dict(blob=bytes(blob),fixes=fixes,mapping=mapping,source=source,functions=functions,
                code_bytes=code_bytes,unwind_offset=unwind_offset,table_offset=table_offset,
                handler_offset=handler,placements_offset=placements,attach_widgets=attach,attach_mapping=attach_mapping,
                replace_widgets=replace,replace_point=replace_point)


def render(a,peers=False):
    lines=['// Generated from saved build 25480438 by generate_loadout_setup.py.',
           'static const uint8_t ep_loadout_setup_template[] = {']
    lines+=['    '+','.join(f'0x{x:02x}' for x in a['blob'][i:i+16])+',' for i in range(0,len(a['blob']),16)]
    lines+=['};','static const EpLoadoutSetupFixup ep_loadout_setup_fixups[] = {']
    lines+=['    {'+','.join(map(str,f))+'},' for f in a['fixes']];lines+=['};']
    for key in ('code_bytes','unwind_offset','table_offset','handler_offset','placements_offset','attach_widgets','replace_widgets'):
        lines.append(f'static const uint32_t ep_loadout_setup_{key} = {a[key]};')
    text='\n'.join(lines)+'\n'
    return text.replace('ep_loadout_setup_','ep_loadout_peer_setup_') if peers else text


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');args=p.parse_args();a=build()
    if args.write:
        HEADER.write_text(render(a),encoding='utf-8',newline='\n')
        HEADER.with_name('ep_loadout_peer_setup_template.h').write_text(render(build(True),True),encoding='utf-8',newline='\n')
    print(json.dumps(dict(image_bytes=len(a['blob']),game_access=False)))
