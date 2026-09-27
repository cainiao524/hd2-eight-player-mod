"""Offline component238 lifecycle and storage-boundary replay; no process APIs."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'research_handoff_20260927' / 'indirect'))
from inspect_capture import EXPECTED, Image, require, row
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP

PRIOR = {
    'player_component_capacity_evidence.json':'4dedec98d7759d1f629500c42bb9a70ff611d0e0b73175e36f2c0306c37f8147',
    'spawn_callback_registration_evidence_v2.json':'142df92c5411697e03914be224d30e05f85a02011c2c96e00be2e2aa9b9a5109',
}
TABLES = {
    0xF0B6F0:0x5405D0, 0xF0C110:0x540660, 0xF0CB30:0x5407E0,
    0xF0D550:0x540810, 0xF0DF70:0x540820, 0xF0E990:0x540740,
    0xF0F3B0:0x540830, 0xF0FDD0:None, 0xF107F0:0x540840, 0xF11210:None,
}
ROOTS = {
    0x5405D0:'simple_append', 0x540660:'classified_append',
    0x540740:'remove_entity_and_compact', 0x5407E0:'property_stage_wrapper',
    0x87B5D0:'move_pointer_primary44_property40_and_fix_map',
    0x87B7B0:'build_twelve_property_descriptors_and_64_byte_values',
    0x874290:'post_callback_initializes_primary_record_from_properties',
    0x873C10:'record_property_consumer_callback',
    0x87C120:'partition_boundary_increment_with_swaps',
    0x87C480:'partition_boundary_decrement_with_swaps_and_byte_flag_access',
    0x87BB30:'deserialize_64_byte_property_record',
    0x873A70:'resource_storage_cleanup',
    0xB24BD0:'register_tag18_aliases',
    0x172F790:'map_insert', 0x172F8A0:'map_remove_and_repair_probe_chain',
}
LEAVES = [
    # Proven direct-call/tail-jump or registration entry, exact end, external tail.
    (0x540810,0x54081B,None,0x874290),
    (0x540820,0x540828,None,0x873C10),
    (0x540830,0x540838,None,0x87C120),
    (0x540840,0x540848,None,0x87C480),
    (0x87BC90,0x87BD08,0x5565DE,0x873370),
    (0xB2FC70,0xB2FEB1,0x56535F,None),
    (0x60C9C0,0x60CA65,0x5565F9,None),
]
PINS = {
    'owner_global_and_adjacent_roster':[
        0xFDA352,0xFDA360,0xFDA375,0x551B7A,0x551B7D,
        0x568236,0x568239,0x568242,0x568EBA,0x568EC1,0x568EC8,0x568ECF],
    'initialize_and_register_both_members':[
        0x5565D7,0x5565DE,0x5565E3,0x5565EA,0x5565EF,0x5565F6,0x5565F9,
        0x5565FE,0x556605],
    'destroy_owner_and_unregister_component':[
        0x55E203,0x56534C,0x565353,0x565358,0x56535F,0x565364,0x56536B],
    'reload_resources_with_same_embedded_pointer':[
        0x56949E,0x5694A8,0x569B0A,0x569B11,0x569B13,0x569B1A,0x569B1F,0x569B26],
    'owner_tick_alias':[
        0x57128D,0x571290,0x5727D6,0x57324A,0x573251,0x573254],
    'owner_batch_partition_move_and_absolute_count_alias':[
        0x576D0D,0x57DFB5,0x57DFBF,0x57DFC5,0x57DFCB,0x57DFCD,
        0x57DFCF,0x57DFD5,0x57DFD7,0x57DFD9,0x57DFDC,0x57DFDF,0x57DFE1,
        0x57DFE6,0x57DFEC,0x57DFEF,0x57DFF2,0x57DFF7,0x57DFFD,
        0x57DFFF,0x57E005,0x57E00B,0x57E00D,0x57E016],
    'owner_deserialize_alias':[
        0xBC2D85,0xBD13B8,0xBD13BB,0xBD13C2,0xBD13C6,0xBD13C9],
    'resource_initialization_scope_and_names':[
        0x87339B,0x8733A2,0x8733A7,0x8733AF,0x8733B2,0x8733B4,0x8733BA,
        0x8733E6,0x8735B0,0x873895],
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def annotated(im, ins):
    return dict(**row(ins),rip_targets=[hex(ins.address+ins.size+o.mem.disp)
                for o in ins.operands if o.type==X86_OP_MEM and o.mem.base==X86_REG_RIP])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    out=Path(args.output)
    require(not out.exists(),'refusing overwrite')
    priors={}
    for file,digest in PRIOR.items():
        raw=(HERE/file).read_bytes()
        require(sha(raw)==digest,'prior changed: '+file)
        priors[file]=json.loads(raw)
    prior_entry=next(e for e in priors['player_component_capacity_evidence.json']['entries'] if e['component_index']==238)
    require(prior_entry['global_rva']=='0x33264f8' and prior_entry['entry']=='0x540660','prior identity changed')
    im=Image(args.evidence)
    require(sha(im.read(0x540660,0xDA))==prior_entry['sha256'],'prior append bytes changed')

    # Reuse the already-proven complete leaf's fingerprint and simple encoded
    # assignment structure; emit only component238 assignments, not 4255 rows.
    start,end=0x556D90,0x55E1E3
    raw=im.read(start,end-start)
    init_digest='22c57829a02419f7e8689a6e2ca501c353fa5362904c6b49e108689d842c91b2'
    require(sha(raw)==init_digest and len(raw)==2127*14+1 and raw[-1]==0xC3,'initializer identity changed')
    require(im.instruction(0x568239).op_str=='0x556d90','initializer caller changed')
    assignments={}
    for n in range(0,len(raw)-1,14):
        pair=raw[n:n+14]
        require(pair[:3]==b'\x48\x8d\x05' and pair[7:10]==b'\x48\x89\x81','unexpected assignment')
        dest=struct.unpack_from('<i',pair,10)[0]
        require(dest not in assignments,'duplicate assignment')
        assignments[dest]=(start+n+7+struct.unpack_from('<i',pair,3)[0],start+n,pair)
    callbacks=[]
    for base,target in TABLES.items():
        slot=base+238*8
        value=assignments.get(slot)
        if target is None:
            require(value is None,'previously absent slot now assigned')
            callbacks.append(dict(table=hex(base),slot=hex(slot),entry=None,
                                  status='No assignment in proven initializer; initial/live value is not established.'))
        else:
            require(value is not None and value[0]==target,'callback target changed')
            callbacks.append(dict(table=hex(base),slot=hex(slot),entry=hex(target),
                                  status='Static explicit assignment',
                                  registration=[annotated(im,i) for i in im.md.disasm(value[2],value[1])]))

    functions=[]
    total=0
    for root,label in ROOTS.items():
        fragments=[]
        for f in im.functions:
            if root<=f[0] and im.root(f[0])[0]==root:
                b=im.read(f[0],f[1]-f[0]);decoded=list(im.md.disasm(b,f[0]))
                require(sum(i.size for i in decoded)==len(b),'fragment decode incomplete')
                total+=len(decoded)
                fragments.append(dict(start=hex(f[0]),end_exclusive=hex(f[1]),sha256=sha(b),
                                      instructions=[annotated(im,i) for i in decoded]))
        require(fragments,'root not found '+hex(root))
        functions.append(dict(root=hex(root),purpose=label,fragments=fragments))

    leaves=[]
    for entry,stop,callsite,tail in LEAVES:
        if callsite is not None:
            call=im.instruction(callsite)
            require(call and call.mnemonic=='call' and call.operands[0].type==X86_OP_IMM and call.operands[0].imm==entry,'leaf entry proof changed')
        else:
            require(entry in TABLES.values(),'leaf lacks registered entry proof')
        b=im.read(entry,stop-entry);decoded=list(im.md.disasm(b,entry))
        require(sum(i.size for i in decoded)==len(b),'leaf boundary incomplete')
        starts={i.address for i in decoded}
        for i in decoded:
            if i.mnemonic.startswith('j') and i.operands[0].type==X86_OP_IMM:
                target=i.operands[0].imm
                require(target in starts or (i.address==decoded[-1].address and target==tail),'unclosed leaf branch')
        require(decoded[-1].mnemonic==('jmp' if tail else 'ret'),'leaf final instruction mismatch')
        leaves.append(dict(entry=hex(entry),end_exclusive=hex(stop),entry_proof_call=hex(callsite) if callsite else None,
                           entry_proof_registration=entry in TABLES.values(),tail_target=hex(tail) if tail else None,
                           sha256=sha(b),instructions=[annotated(im,i) for i in decoded]))

    pins={}
    for label,sites in PINS.items():
        pins[label]=[]
        for site in sites:
            ins=im.instruction(site)
            require(ins is not None,'not a proven boundary '+hex(site))
            pins[label].append(dict(**annotated(im,ins),root=hex(im.root(site)[0])))
    literals=[]
    for at,expected in [(0x224B928,b'generated_body_settings.dl_bin\0'),
                        (0x224B9B0,b'generated_customization_armor_sets.dl_bin\0'),
                        (0x224B980,b'generated_customization_passive_bonuses.dl_bin\0')]:
        b=im.read(at,len(expected));require(b==expected,'literal changed')
        literals.append(dict(rva=hex(at),text=b[:-1].decode(),sha256=sha(b)))
    arrays=[('entity_pointer',0x948,8),('ordinal_byte_flags',0x968,1),
            ('primary_record',0x96C,0x44),('replicated_property_record',0xA7C,0x40)]
    spans=[]
    for name,base,stride in arrays:
        spans.append(dict(name=name,base=hex(base),stride=hex(stride),
                          four_span=[hex(base),hex(base+4*stride)],
                          eight_if_unmoved_span=[hex(base),hex(base+8*stride)],
                          slot_four_span=[hex(base+4*stride),hex(base+5*stride)]))
    result=dict(source_sha256=EXPECTED,capture_identity_sha256=im.report['capture_sha256'],prior_sha256=PRIOR,
        component_index=238,global_rva='0x33264f8',
        initializer_reuse=dict(sha256=init_digest,validated_assignment_count=len(assignments),
                               source_proof='spawn_callback_registration_evidence_v2.json',emitted_only_selected_pairs=True),
        callbacks=callbacks,functions=functions,proven_leaves=leaves,pins=pins,literals=literals,
        layout=dict(owner_offset='0xe9fc98',next_member_owner_offset='0xea0818',next_member='roster/global3326468',
                    separation='0xb80',system_tag='0x18',
                    counters={'high_water_active':'0x8e0','total':'0x8e4','active_partition':'0x8e8','flagged_prefix':'0x8ec'},
                    map=dict(inline_pairs=['0x8f0','0x930'],descriptor='0x930',entry_count=8,
                             capacity_field='0x938',sentinel_field='0x93c',multiplier_field='0x940',multiplier=2),
                    arrays=spans,additional_four_record_payload_bytes=4*(8+1+0x44+0x40),
                    map_growth_from8_to16_extra_bytes=8*8,
                    collisions=[
                        'pointer slot4 [968,970) overwrites all four byte flags [968,96C) and primary0 first4 bytes',
                        'byte flag slot4 at96C overwrites primary0 byte0',
                        'primary slot4 [A7C,AC0) overlaps property0 [A7C,ABC) and property1 first4 bytes',
                        'property slot4 [B7C,BBC) crosses next roster base B80 after4 bytes; roster+8 pointer lies in this range'],
                    tag_alias_registry='global3326E68',tag_alias_lists=['0xc98','0xcc0','0xcd8','0xcf0','0xd18','0x4250','0x4268'],
                    owner_absolute_count_alias='owner+EA0584 == component+8EC'),
        lifecycle=dict(
            initialization='87BC90 clears total/active counts, sets inline map8, then tails873370 resource initializer; no complete initialization claim for8E0/8EC or all byte/property rows',
            move='87B5D0(self,destination,source) copies pointer8+primary44+property40 and changes moved entity map value to destination; it does not copy the ordinal-byte flag array',
            remove='540740 removes map key then decrements total/active/prefix as applicable and calls/tails87B5D0 to fill removed positions',
            partition_callbacks='87C120 swaps arrays then increases prefix;87C480 decreases prefix and accesses byte flags in addition to swapping the three larger arrays',
            properties='87B7B0 allocates64 bytes and emits12 descriptors;87BB30 deserializes one64-byte record by entityID map ordinal',
            destruction='owner55E1F0 calls873A70 thenB2FC70; the latter removes matching object pointer from all seven registry lists',
            owner_aliases='construction, destruction, resource reload, tick, batch partition, deserialize and global publishing embed owner+E9FC98; changing global alone does not redirect these'),
        runtime_verified=False,
        limits=[
            'Only saved capture read. No live process query/read, capture, probe, game execution or patch.',
            'Reference-player membership is inherited reference metadata, not verified installed/runtime metadata.',
            'Eight callback assignments are proven. F0FDD0[238] and F11210[238] lack assignments here; zero/default/live values are not inferred.',
            'Function labels describe observed code behavior; callback table phase names not established here are not invented.',
            'Resource names associate this system with body/customization/passive-bonus data; no formal component name is proven.',
            'Map capacity8 can physically hold eight entries, but this is a full map. Doubling to16 preserves the original two-slots-per-player ratio and requires moved backing; no claim that16 is the only valid design.',
            'Storage ranges and byte collisions are static conditional deductions, not observed fifth-player execution.',
            'This scoped lifecycle closure does not claim every direct global consumer or owner alias has been exhaustively audited.'])
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(out),root_instructions=total,leaf_instructions=sum(len(x['instructions']) for x in leaves),
                          pins=sum(map(len,pins.values())),sha256=sha(out.read_bytes()))))


if __name__=='__main__':
    main()
