"""Check the saved fifteen bodies' direct stack-argument accesses; no game access.

This finite CFG check does not certify live callers, indirect helpers or a new
game build. It pins original evidence and supplies the bridge's stack-copy gate.
"""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT.parent
sys.path.insert(0,str(ROOT/'eight_player_candidate_20260927/.native-test-deps'))
import capstone as cs
from capstone.x86_const import X86_OP_REG,X86_OP_MEM,X86_OP_IMM
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def canonical(reg):
    if not reg:return ''
    return {'eax':'rax','ecx':'rcx','edx':'rdx','ebx':'rbx','esp':'rsp','ebp':'rbp','esi':'rsi','edi':'rdi'}.get(reg,reg[:-1] if reg.startswith('r') and reg[-1:] in ('d','w','b') else reg)
def find(value,entry):
    if isinstance(value,dict):
        if value.get('entry')==entry and 'instructions' in value:return value
        for child in value.values():
            got=find(child,entry)
            if got:return got
    if isinstance(value,list):
        for child in value:
            got=find(child,entry)
            if got:return got
    return None
def audit(code,entry):
    md=cs.Cs(cs.CS_ARCH_X86,cs.CS_MODE_64);md.detail=True
    ins=list(md.disasm(code,entry));need(sum(i.size for i in ins)==len(code),'incomplete decode')
    by={i.address:i for i in ins};queue=[(entry,{'rsp':0})];seen=set();accesses=set();tails=set();indirect=[];returns=0
    while queue:
        pc,aliases=queue.pop();key=(pc,tuple(sorted(aliases.items())))
        if key in seen:continue
        seen.add(key);need(len(seen)<10000,'unbounded stack-state graph')
        need(pc in by,'branch outside instruction boundary');i=by[pc];ops=i.operands
        for op in ops:
            if op.type!=X86_OP_MEM:continue
            base=canonical(i.reg_name(op.mem.base));index=canonical(i.reg_name(op.mem.index))
            need(index not in aliases,'stack pointer used as indexed address')
            if base in aliases:
                need(not op.mem.index,'indexed stack access needs separate ABI proof')
                offset=aliases[base]+op.mem.disp
                if offset>=0x28:accesses.add((i.address,offset,op.size,i.mnemonic=='lea'))
        if i.mnemonic.startswith('ret'):
            need(aliases['rsp']==0 and not ops,'nonstandard return stack');returns+=1;continue
        next_alias=dict(aliases)
        if i.group(cs.CS_GRP_CALL):
            for r in ('rax','rcx','rdx','r8','r9','r10','r11'):next_alias.pop(r,None)
        elif i.mnemonic=='push':next_alias['rsp']-=8
        elif i.mnemonic=='pop':
            next_alias['rsp']+=8;next_alias.pop(canonical(i.reg_name(ops[0].reg)),None)
        else:
            assign=None
            if len(ops)>=2 and ops[0].type==X86_OP_REG:
                dest=canonical(i.reg_name(ops[0].reg));src=ops[1]
                if i.mnemonic=='mov' and src.type==X86_OP_REG and canonical(i.reg_name(src.reg)) in aliases:
                    assign=(dest,aliases[canonical(i.reg_name(src.reg))])
                elif i.mnemonic=='lea' and src.type==X86_OP_MEM and canonical(i.reg_name(src.mem.base)) in aliases and not src.mem.index:
                    assign=(dest,aliases[canonical(i.reg_name(src.mem.base))]+src.mem.disp)
                elif i.mnemonic in ('add','sub') and dest in aliases and src.type==X86_OP_IMM:
                    assign=(dest,aliases[dest]+src.imm*(1 if i.mnemonic=='add' else -1))
            for r in i.regs_access()[1]:
                name=canonical(i.reg_name(r));next_alias.pop(name,None)
            if assign:next_alias[assign[0]]=assign[1]
            need('rsp' in next_alias,'unsupported stack mutation')
        if i.group(cs.CS_GRP_JUMP):
            if ops[0].type!=X86_OP_IMM:
                # One exact saved departure tail is recorded as an unresolved
                # target contract, never silently treated as a proved ABI.
                need(entry==0x605950 and i.address==0x605F28 and i.bytes.hex()=='49ffa080040000' and next_alias['rsp']==0,'unrecognized indirect tail')
                indirect.append(dict(rva=hex(i.address),operand=i.op_str,encoding=i.bytes.hex(),target_contract_verified=False))
                continue
            if ops[0].imm not in by:
                need(i.mnemonic=='jmp' and next_alias['rsp']==0,'external branch without restored stack')
                tails.add((i.address,ops[0].imm));continue
            queue.append((ops[0].imm,next_alias))
            if i.mnemonic=='jmp':continue
        queue.append((pc+i.size,next_alias))
    return {'cfg_states':len(seen),'returns':returns,'indirect_tail_abi_pending':indirect,'external_tail_abi_pending':[{'rva':hex(pc),'target':hex(target)} for pc,target in sorted(tails)],'stack_arguments':[
        {'rva':hex(pc),'entry_rsp_offset':offset,'bytes':n,'address_taken':lea} for pc,offset,n,lea in sorted(accesses)]}
def main():
    need(cs.__version__=='5.0.7','wrong Capstone')
    profiles=[('native-unwind-source',('producer','receiver')),('native-getter',('getter',)),('native-mover',('mover',)),
        ('native-insert',('dense_legacy','append_legacy','append_registered','dense_registered')),
        ('native-remove',('legacy','registered')),('native-classify',('enter','leave')),
        ('native-registry',('update','association')),('native-departure',('departure',))]
    rows=[];inputs={};indirect_rejections=0
    for name,keys in profiles:
        path=PROJECT/(name+'.lock.json');inputs[path.relative_to(ROOT).as_posix()]=sha(path)
        lock=json.loads(path.read_bytes())
        for key in keys:
            f=lock['functions'][key];p=ROOT/f['evidence_path'];need(sha(p)==f['evidence_sha256'],'changed evidence')
            inputs[f['evidence_path']]=sha(p);node=find(json.loads(p.read_bytes()),f['entry']);need(node is not None,'missing body')
            code=b''.join(bytes.fromhex(i['bytes']) for i in node['instructions'])
            need(hashlib.sha256(code).hexdigest()==f['code_sha256'],'changed original bytes')
            proof=audit(code,int(f['entry'],16));kind=len(rows)+1;args=proof['stack_arguments']
            if kind==1:
                need({a['entry_rsp_offset'] for a in args}=={40,48} and all(a['bytes']==8 and not a['address_taken'] for a in args),'producer stack ABI changed')
            else:need(not args,'unaccounted stack arguments')
            need((len(proof['indirect_tail_abi_pending'])==1)==(key=='departure'),'unexpected indirect-tail contract')
            if key=='departure':
                entry=int(f['entry'],16)
                wrong_target=bytearray(code);wrong_target[0x605F28-entry+3]=0x88
                wrong_stack=bytearray(code);wrong_stack[0x605F1D-entry+3]=0x78
                for malformed,base in ((bytes(wrong_target),entry),(bytes(wrong_stack),entry),(b'\xff\xe0',0x606AD0)):
                    try:audit(malformed,base)
                    except ValueError as ex:
                        need(str(ex)=='unrecognized indirect tail','negative control failed for unrelated reason')
                        indirect_rejections+=1
                    else:raise ValueError('unproved indirect tail was accepted')
            rows.append(dict(kind=kind,name=key,entry=f['entry'],stack_copy_bytes=16 if kind==1 else 0,**proof))
    receipt=dict(schema='hellforge_roster_call_abi_v1',passed=True,verified_at_utc=datetime.now(timezone.utc).isoformat(),
        game_build=25480438,indirect_tail_rejection_controls=indirect_rejections,indirect_tail_target_abi_verified=False,entries=rows,test_source_sha256={Path(__file__).relative_to(PROJECT).as_posix():sha(Path(__file__))},
        legacy_source_sha256=inputs,live_callers_verified=False,transitive_helper_abi_verified=False,game_access=False)
    (PROJECT/'evidence/roster-call-abi-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':True,'entries':len(rows),'producer_stack_copy_bytes':16,'cfg_states':sum(r['cfg_states'] for r in rows),'game_access':False}))
if __name__=='__main__':main()
