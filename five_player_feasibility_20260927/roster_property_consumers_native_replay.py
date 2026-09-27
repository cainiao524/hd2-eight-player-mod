"""Finite, saved-capture roster property relocation inventory; no global scan.

Rechecks imported instruction bytes and each explicit edit site. Whole-root
extent metadata is not a claim that all aliases or all CFG paths are closed.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'research_handoff_20260927'/'indirect'))
from inspect_capture import Image, EXPECTED, require, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

PRIOR={
 'roster_lifecycle_evidence.json':'969042e4d22464c96f510b4c06ed2af742985f96f9881fda338210368cf09ed5',
 'roster_dispatch_evidence_v2.json':'e83d0bc3ace27f26b7e77511cd01c09b9ed3b26996abe8661a21b77ae2d47f03',
 'roster_index_usage_evidence_v2.json':'d7098a7d698aa7daaf53e89c08b19cb01e243860f70fbba518690837baf121ee',
 'roster_property_apply_evidence_v3.json':'d0dd9c02db933c20801a366d9668131734a29106e46f8a8a0d0de43981a27d22',
 'player_roster_evidence.json':'606e6cb31fc55a1abfbc82224359fc1fc776f7a3f36838779a558700380e81a6',
 'roster_property_receive_evidence.json':'bad5661771df280dd5e982b765d2f4ab1c73de9ae7e86e974751af6c3c383c10',
 'roster_component_binding_evidence_v3.json':'274833c418bfa7dec4e4097dda5031f3a11e8c69689ae4ed758e75a40481c2e2',
}

# Every site is selected from an existing proven lineage. This is not a search
# for arbitrary identical displacements elsewhere in the capture.
ITEMS=[
 dict(id='producer',root=0x60C640,kind='producer',
      identity='RBP loads roster global3326468 at60C667; entity ID maps to ordinal; binding evidence connects component239 wrapper540AE0.',
      sites=[0x60C6F2,0x60C720,0x60C74C,0x60C77D,0x60C7A7,0x60C7D3,0x60C7FF,0x60C803,0x60C807,0x60C82F],
      site_note='Eight DWORD writes. Seventh field uses60C7FF lea rax,[r11+1Eh],60C803 shl rax,5, then60C807 stores through RAX+RBP.',
      aliases=['RBP=S','RBX=ordinal*20h','R11=unscaled ordinal retained across actual134F190 leaf;60C7FF/803 form field offset','allocated output buffer RSI/RAX is distinct from property storage'],
      changes='Redirect all eight property writes to B+ordinal*20h+[0..1C]; preserve descriptor/value output and original S for map lookup.',
      effects='Original allocator173B8D0 for20h payload before first property write; appends eight descriptors/count updates; network-index leaf134F190. Guard rejection must precede allocation.',
      closure='Existing full receiver/binding proof plus selected producer anchors; producer emitter has its own independent full-root contract.'),
 dict(id='receiver',root=0x60C890,kind='receiver',
      identity='Direct callerBD13B3 supplies same S inRCX; receiver copies S toR11, retains original map lookup.',
      sites=[0x60C938,0x60C946,0x60C954,0x60C962,0x60C970,0x60C97E,0x60C98C,0x60C9A2],
      aliases=['R11=S until property cutpoint','R8=ordinal*20h','RBP=payload; R14=cursor pointer'],
      changes='Redirect all eight stores together; keep payload DWORD order, original map, cursor+20h; reject invalid binding/ordinal before first store.',
      effects='No callee in complete receiver; writes eight fields and cursor. Map miss/payload bounds need integration contract.',
      closure='Complete303-byte72-instruction body already verified; aliases outside this body remain open.'),
 dict(id='move',root=0x60C410,kind='move',
      identity='EntryRCX=S; same-S callers in lifecycle pins pass global or owner+EA0818. RBX=RCX at60C420.',
      sites=[0x60C51F,0x60C528,0x60C531,0x60C53A],
      aliases=['R10=source ordinal*20h','R9=destination ordinal*20h','RBX=S remains live for map','R11=S+destination*8 for entity pointer'],
      changes='Redirect only four property loads/stores to B while preserving entity pointer,70h/38h copies and map destination ordinal.',
      effects='No calls in full root; original writes to three other arrays and map. Same ordinal returns before copies; invalid map result is not safe.',
      closure='Complete local body and normal CFG checked here; entry index/binding and all parallel storage validity are integration preconditions.'),
 dict(id='compact',root=0x60CC70,kind='move',
      identity='EntryRCX=S; proven owner caller57E00F/57E01C supplies owner+EA0818; RBX=RCX.',
      sites=[0x60CD90,0x60CD99,0x60CDA1,0x60CDAA],
      aliases=['RBX=S','R8=source*20h','RDX=destination*20h','R9 points into entity pointer array'],
      changes='Redirect inline property copy and its60CE24 call to patched60C410; preserve dense/tracked/prefix counts and map.',
      effects='Calls60C410; copies all parallel arrays, updates map and eventually dense count+84.',
      closure='Finite full-root direct property access set; no global alias closure.'),
 dict(id='promote',root=0x60CF50,kind='classify',
      identity='Global3326468 is saved inRBP; entity ID lookup obtains ordinal, prefix boundary comes fromS+88.',
      sites=[0x60D19F,0x60D1AA,0x60D1B6,0x60D1BF,0x60D1C7,0x60D1D0,0x60D1DB,0x60D1E8],
      aliases=['RBP=S','RDI/R15=two ordinals*20h','RAX=temporary20h record buffer, not S alias'],
      changes='Redirect all eight property accesses; retain temporary-copy order, map fixes and+88 increment;70h destination is initialized, not symmetrically swapped.',
      effects='Property path calls173B6F0 at60D17A, allocates20h via173B8D0 at60D18D, calls173BC20 at60D1F1/1FB. Do not remove/reorder resource protocol.',
      closure='Complete selected classification root; static callback order from apply evidence, runtime table values not checked.'),
 dict(id='demote',root=0x60D300,kind='classify',
      identity='Global3326468 saved inRBP; entity ID lookup; second ordinal=S+88-1.',
      sites=[0x60D61A,0x60D625,0x60D631,0x60D639,0x60D641,0x60D649,0x60D654,0x60D660],
      aliases=['RBP=S','RDI/RSI=two ordinals*20h','RAX=temporary20h record buffer, not S alias'],
      changes='Redirect all eight property accesses; preserve full70h/38h swaps, temporary protocol, two map repairs, and+88 decrement.',
      effects='Property path calls173B6F0 at60D5F5, allocates20h via173B8D0 at60D608, calls173BC20 at60D668/672; notification occurs before this callback and bit0 clears afterward.',
      closure='Complete selected classification root; other lifetime/alias sources remain open.'),
 dict(id='pre_remove_reader',root=0x605950,kind='reader-with-effects',
      identity='605962 loads global3326468; R13=S; entity map yields ordinal with byte offset inRSI.',
      sites=[0x605A5B],aliases=['R13=S','RSI=ordinal*20h; first DWORD is related entity ID, not network index'],
      changes='Read related entity ID fromB+ordinal*20h; preserve earlier70h state handling and notifications before roster removal.',
      effects='Resolves entity viaFD9C80; conditional disconnected notification/FDC310 actions; player_count notification. Property base change must not bypass these.',
      closure='Selected same-S reader and ordering proven; whole callee resource effects not expanded.'),
 dict(id='registry_property_reader_writer',root=0xB54E00,kind='reader-writer',
      identity='Same registry3326E68 table+10F8; tag69 branch loads S intoR14 atB55003.',
      sites=[0xB5501C,0xB55030,0xB5504A,0xB550FB],
      aliases=['RDI=S+3A8 then advances20h, dereference atB55030','R14=S remains used for pointers','R9=ordinal*20h for direct+3AC write'],
      changes='Replace derived loop start withB and redirect direct+3AC bit clear toB+ordinal*20h+4; keep R14 asS and pointer/map consumers intact.',
      effects='CallsFD9BA0 while finding related entity; other roster38h state writes and property flag bit clear.',
      closure='Known tag69 branch only; other tags/branches and heap aliases not covered.'),
 dict(id='tag_da_network_index',root=0xFFD8C0,kind='reader',
      identity='FFE3D6 explicitly loads global3326468 intoR9; loop bounded byS+84.',
      sites=[0xFFE3FF],aliases=['R9=S','RAX=ordinal*20h'],
      changes='Read B+ordinal*20h+Ch; independently retain requirement to expand downstream tagDA90h records before using indices4..7.',
      effects='Original downstream unchecked network-index writer hits separate four-record storage; property relocation alone does not fix it.',
      closure='Selected roster loop proven; downstream capacity defect has independent evidence.'),
 dict(id='first_record_vector_index',root=0xACA400,kind='reader',
      identity='ACA57B loads global3326468; ACA58B reads first property record index.',
      sites=[0xACA58B],aliases=['RAX=S; fixed ordinal0'],
      changes='Read B+Ch while keeping first-record semantics; do not replace network index with ordinal.',
      effects='Passes index toACF1F0; >=4 has bounded default path, not a join rejection.',
      closure='Selected same-S reader; exact desired extra-player vector behavior remains separate.'),
 dict(id='state_operation_index',root=0x12A98D0,kind='reader',
      identity='Global3326468 inR10; entity map lookup obtains ordinal then reads property index.',
      sites=[0x12A9C80],aliases=['R10=S','RCX=ordinal*20h'],
      changes='Read B+ordinal*20h+Ch; preserve entity map and downstream index meaning.',
      effects='Passes index toACF420, whose>=4 path returns false; not evidence of account join refusal.',
      closure='Selected call chain proven; downstream storage/operation extension separate.'),
 dict(id='mask_index',root=0x1277920,kind='reader',
      identity='Global3326468 and same entity map supply ordinal; R11=S.',
      sites=[0x1277A06],aliases=['R11=S','RCX=ordinal*20h'],
      changes='Redirect field read toB+ordinal*20h+Ch; preserve sentinel handling and32-bit mask operation.',
      effects='Tests masks in a different system; bits4..7 fit32-bit width, mask production remains unresolved.',
      closure='Selected same-S lookup/read proven; not a proof of complete mask producer.'),
 dict(id='index_getter',root=0x606AD0,kind='reader',
      identity='606AE4 loads same roster global; map yields ordinal; R10=S.',
      sites=[0x606B6B],aliases=['R10=S','RAX=ordinal*20h'],
      changes='Read B+ordinal*20h+Ch; preserve map-miss returnFFFFFFFF and raw DWORD value.',
      effects='Getter has no four clamp; only address changes needed for this field.',
      closure='Existing selected getter proof; no global callers closure claimed.'),
 dict(id='float_pair_reader',root=0x725160,kind='reader',
      identity='72757E/7275B1 load same global3326468; dense roster loop uses S+84.',
      sites=[0x7275D6,0x7275E1,0x7275EA],aliases=['RCX=S','RAX=ordinal*20h'],
      changes='Redirect network index+Ch and float fields+1Ch/+18h together, preserving EDX/XMM3/XMM2 arguments to14335F0.',
      effects='14335F0 writes indexed player component298h records; its storage expansion is independently required.',
      closure='Selected same-S caller block; entire giant manager root is not re-proved.'),
 dict(id='palette_index',root=0x6054F0,kind='reader-with-effects',
      identity='Binding evidence same global and entity map; RBP=S, RDI=ordinal*20h.',
      sites=[0x605760],aliases=['RBP=S','RDI=ordinal*20h'],
      changes='Redirect index read toB+ordinal*20h+Ch; preserve bounded palette fallback and independent player_count notification.',
      effects='Conditional indirect palette endpoint; count notification. >=4 returns fallback components, not index clamp.',
      closure='Selected same-S field read and palette paths proven; external API target not identified.'),
]

DELEGATED=[
 (0x60CA80,'insert',[0x60CAE9,0x60CB2B], [0x60CAC9], 'ABI RDX entity/R8 flags; four guard; initializes70h/38h; no direct property write; optional move via60C410.'),
 (0x60CBA0,'insert',[0x60CBDC,0x60CC14], [], 'ABI RDX entity; four guard; initializes70h/38h; property producer is a later stage.'),
 (0x540850,'insert',[0x54088F,0x5408CB], [], 'ABI RCX entity; four guard;70h/38h initialization; later property producer.'),
 (0x540920,'insert',[0x540984,0x5409CA], [0x540968], 'Component239 registered insert; ABI RCX entity/RDX flags; four guard; optional shared move.'),
 (0x60CEA0,'remove',[],[0x60CF0E,0x60CF3A], 'Removes map item, decreases tracked/dense counts and invokes60C410; no independent property clear inferred.'),
 (0x540A40,'remove',[],[0x540AA4,0x540AD5], 'Registered actual-removal wrapper; call/tail-jump60C410; keep map/count ordering after pre-removal notifications.'),
]

def sha(raw):return hashlib.sha256(raw).hexdigest()

def walk(x):
    if isinstance(x,dict):
        if {'rva','bytes','asm'}<=set(x):yield x
        for y in x.values():yield from walk(y)
    elif isinstance(x,list):
        for y in x:yield from walk(y)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output);require(not out.exists(),'refusing overwrite');im=Image(a.evidence)
    prior={};old={};origins={}
    for name,h in PRIOR.items():
        raw=(HERE/name).read_bytes();require(sha(raw)==h,'prior changed '+name);prior[name]=json.loads(raw)
        for r in walk(prior[name]):
            at=int(r['rva'],16);raw=bytes.fromhex(r['bytes']);require(im.read(at,len(raw))==raw,'prior bytes '+hex(at))
            decoded=list(im.md.disasm(raw,at));require(len(decoded)==1 and row(decoded[0])['asm']==r['asm'],'prior instruction '+hex(at))
            require(decoded[0].size==len(raw),'prior instruction extent')
            if 'sha256'in r:require(sha(raw)==r['sha256'],'prior instruction hash')
            if at in old:require(old[at]==row(decoded[0]),'conflicting prior')
            old[at]=row(decoded[0]);origins.setdefault(at,set()).add(name)

    wanted={x['root'] for x in ITEMS}|{x[0] for x in DELEGATED}
    fragments={r:[]for r in wanted}
    for f in im.functions:
        root=im.root(f[0])[0]
        if root in fragments:fragments[root].append(f)
    full={};decoded={}
    for root,fs in fragments.items():
        require(fs,'root absent');fr=[];rs=[]
        for start,end,unwind in fs:
            raw=im.read(start,end-start);code=list(im.md.disasm(raw,start));rs+=code
            fr.append(dict(start=hex(start),end_exclusive=hex(end),unwind=hex(unwind),sha256=sha(raw),
                           sequential_decode_covers_span=sum(i.size for i in code)==len(raw)))
        full[root]=fr;decoded[root]=rs

    def pin(at,root=None):
        ins=im.instruction(at);require(ins is not None,'unvalidated boundary '+hex(at))
        if root is not None:require(im.root(at)[0]==root,'wrong root')
        return dict(**row(ins),root=hex(im.root(at)[0]),prior_artifacts=sorted(origins.get(at,[])))
    entries=[]
    for spec in ITEMS:
        item=dict(spec);root=item.pop('root');sites=item.pop('sites')
        item.update(root=hex(root),complete_saved_unwind_fragments=full[root],
                    edit_sites=[pin(at,root) for at in sites],
                    whole_root_semantic_closure=False,all_external_aliases_closed=False)
        entries.append(item)
    for root,kind,anchors,calls,note in DELEGATED:
        entries.append(dict(id=hex(root),root=hex(root),kind=kind,
            identity='Same roster global3326468 in existing lifecycle/player/dispatch evidence; component registration only where explicitly noted.',
            complete_saved_unwind_fragments=full[root],anchor_instructions=[pin(x,root)for x in anchors],
            move_edges=[pin(x,root)for x in calls],changes=note,
            property_edit='No direct3A8..3C7 property operand in this finite complete root; shared move must be redirected where called.',
            whole_root_semantic_closure=False,all_external_aliases_closed=False))
        require(not any(op.type==X86_OP_MEM and 0x3A8<=op.mem.disp<=0x3C7 for i in decoded[root] for op in i.operands),'unexpected delegated property operand')
        for at in calls:
            i=im.instruction(at);require(i.mnemonic in('call','jmp')and i.operands[0].type==X86_OP_IMM and i.operands[0].imm==0x60C410,'move edge')

    # Full local body proves the smallest next candidate is a data mover,
    # not an allocation wrapper. Other array/map writes still matter.
    rs=decoded[0x60C410];by={i.address:i for i in rs};edges={}
    require(rs[0].address==0x60C410 and rs[-1].address+rs[-1].size==0x60C5BE,'mover bounds')
    require(not any(i.mnemonic=='call'for i in rs),'mover callee')
    for i in rs:
        if i.mnemonic=='ret':e=[]
        elif i.mnemonic.startswith('j'):
            require(i.operands[0].type==X86_OP_IMM,'mover indirect branch');e=[i.operands[0].imm]+([]if i.mnemonic=='jmp'else[i.address+i.size])
        else:e=[i.address+i.size]
        require(all(v in by for v in e),'mover CFG exit');edges[i.address]=e
    seen=set();todo=[0x60C410]
    while todo:
        at=todo.pop()
        if at not in seen:seen.add(at);todo+=edges[at]
    require(seen==set(by),'unreachable mover instruction')
    property_sites=[i.address for i in rs if any(op.type==X86_OP_MEM and 0x3A8<=op.mem.disp<=0x3C7 for op in i.operands)]
    require(property_sites==[0x60C51F,0x60C528,0x60C531,0x60C53A],'mover property set')
    require(all(len(edges[x])==1 for x in property_sites),'property straight-line block')
    raw=im.read(0x60C410,0x1AE)
    cut=dict(root='0x60c410',start='0x60c51f',end_exclusive='0x60c543',
        property_instructions=[row(by[x])for x in property_sites],body_sha256=sha(raw),body_bytes=len(raw),
        body_instructions=[row(i)for i in rs],cfg={hex(k):[hex(v)for v in vs]for k,vs in edges.items()},
        entry_contract='RCX=S, EDX=destination ordinal, R8D=source ordinal; equal ordinals return before writes.',
        at_property_block='RBX=S; R10=source*20h; R9=destination*20h; two16-byte loads/stores.',
        resource_calls=[],
        side_effects='Before property block: copies pointer,70h and38h records. After block: repairs entityID->destination ordinal. This is not an atomic transaction.',
        implementation='A pure offline local emitter can rewrite these four operands using a dedicated property-base scratch; never permanently bias RBX because map and pointer accesses still use S.',
        fail_before='Validate binding and both ordinals before first mutation60C440, preferably at entry. Rejecting only at60C51F leaves earlier parallel copies applied.',
        integration_gates=['Valid original entity map; full parallel arrays extended for indices4..7 before whole clone is executable.',
                           'Binding lifetime/concurrency; guard/no-op semantics; failure continuation before original writes.',
                           'Clone/unwind/relocation/hook installation and teardown; no executable output from this inventory.'])
    resource_sites=[0x60D17A,0x60D17F,0x60D184,0x60D189,0x60D18D,0x60D1F1,0x60D1FB,
                    0x60D5F5,0x60D5FA,0x60D5FF,0x60D604,0x60D608,0x60D668,0x60D672]
    owner_sites=[0x5565EF,0x5565F9,0x556605,0x568EC8,0x568ECF,0xB27564,0xB2756F,
                 0xB54E58,0xB54E5B,0xB55003,0x57E00F,0x57E01C]
    result=dict(schema_version=1,source_sha256=EXPECTED,prior_sha256=PRIOR,runtime_verified=False,executable=False,
        scope='Only explicitly listed roots and already-proven global/owner/registry lineages. No full-capture rescan, no new callee tree.',
        prior_unique_instruction_rows_rechecked=len(old),layout=dict(S='owner+EA0818',property_base='S+3A8',record_bytes=32,
          original_records=4,sidecar_records=8,sidecar_bytes=256,next_owner_member='S+428',ordinal_not_network_index=True),
        identity_anchors=[pin(x)for x in owner_sites],entries=entries,
        classification_resource_protocol=[pin(x)for x in resource_sites],next_cutpoint=cut,
        completeness=dict(finite_inventory_complete=True,global_alias_closure=False,
            full_root_extent_is_not_full_semantics=True,sidecar_allocation_lifetime_proved=False),
        decision='Patch only property operands/derived pointers; preserve S for maps,counts,other parallel arrays and original resource protocols. Do not enable receiver/producer alone.',
        stop_condition='Every selected producer/move/remove/classify/reader has fixed sites, source identity, effects and closure limits; stop before global/recursive expansion.',
        next_action='Implement and emulate smallest60C410 local property-copy redirect with entry validation and preserved other-array/map behavior, after current producer work.',
        limitations=['Writable runtime tables and heap state are absent; static callback registration is not runtime dispatch validation.',
                     'Imported narrow scans are not exhaustive. Same-S aliases outside listed blocks remain open.',
                     'Full saved unwind fragment hashes identify available code extents; large-root tables/other branches are not claimed semantically audited.',
                     'No live process query/read/write, capture, installation or multiplayer result.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),sha256=sha(out.read_bytes()),entries=len(entries),
      imported_unique_rows=len(old),edit_sites=sum(len(e.get('edit_sites',[]))for e in entries),mover_instructions=len(rs))))

if __name__=='__main__':main()
