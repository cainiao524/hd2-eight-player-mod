"""Execute the saved entity dispatcher with real relocated roster callbacks.

Only Unicorn RAM and our image-emitter DLL are used. External interfaces are
explicit contract stubs, not recovered implementations or production ABI proof.
"""
import argparse
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import native_departure_image as departure
import native_getter_image as getter
import native_remove_image as removal
import native_mover_image as mover
from native_departure_library import Library as DepartureLibrary
from native_property_library import Library

PROJECT, ROOT = departure.PROJECT, departure.ROOT
need, sha = departure.require, departure.sha
u32 = lambda n: struct.pack('<I', n)
u64 = lambda n: struct.pack('<Q', n)


def source():
    lock = json.loads((PROJECT / 'native-entity-remove.lock.json').read_bytes())
    f = lock['functions']['entity_remove']
    code = bytes.fromhex(f['body_hex'])
    need(sha(code) == f['code_sha256'] == '8ef7ad9fbf59756023045f94c796bfb96a2f43876d8c64052c0d306a8b5c6094', 'dispatcher changed')
    path = ROOT / f['evidence_path']
    need(sha(path.read_bytes()) == f['evidence_sha256'], 'dispatcher evidence changed')
    evidence = json.loads(path.read_bytes())
    cursor = 0xFDC820
    for fragment in evidence['full_function_fragments'][f['entry']]:
        a, b = int(fragment['start'], 16), int(fragment['end_exclusive'], 16)
        need(a == cursor and sha(code[a-0xFDC820:b-0xFDC820]) == fragment['sha256'], 'dispatcher fragment changed')
        cursor = b
    need(cursor == 0xFDCDFF, 'incomplete dispatcher')
    leaf = next(r for r in evidence['callback_leaves'] if r['entry'] == '0x540b20')
    leaf_code = b''.join(bytes.fromhex(i['bytes']) for i in leaf['instructions'])
    need(sha(leaf_code) == leaf['sha256'] == '87ca4a815284d6d035dd700a5de16a8141544f8c5a5099001b5a0727a480af7e', 'departure leaf changed')
    rp = ROOT / lock['registration_evidence_path']
    need(sha(rp.read_bytes()) == lock['registration_evidence_sha256'], 'registration changed')
    registration = json.loads(rp.read_bytes())
    for row in lock['callback_tables']:
        registered = [x for x in registration['component_239'] if x['target_rva'] == row['registered_callback']]
        need(len(registered) == 1 and int(registered[0]['table_base_offset'], 16) + 64 == int(row['context_table'], 16), 'callback registration mismatch')
    return code, leaf_code, {f['evidence_path']: f['evidence_sha256'], lock['registration_evidence_path']: lock['registration_evidence_sha256']}


def validate(library):
    code, leaf, pins = source()
    lib, dep_lib = Library(library), DepartureLibrary(library)
    p = departure.load_fixture()
    departure.bind_fixture(p, dep_lib)
    def emit_getter(body, **addresses):
        need(sha(body) == getter.profile()['functions']['getter']['code_sha256'], 'getter source changed')
        return lib.getter_candidate(addresses, getter.build(**addresses))
    p.getter.build = emit_getter
    # Separate synthetic regions; none is a host pointer.
    MANAGER, HASH, COMPONENTS, API, WORLD = [0x18220000000 + i * 0x1000000 for i in range(5)]
    OBJECT, OBJECT_TABLE, RECORDS, AUDIO_MAP, OUTER_MAP = [0x18225000000 + i * 0x1000000 for i in range(5)]
    TYPE = 0x11223FFF  # A collision crosses bucket 4095 -> 0.
    COOKIE = 0x619A8247B1C3D5E7
    cases = []

    class Fixture(p.Fixture):
        def __init__(self, *, original=False, t=8, d=6, prefix=2, ordinal=1,
                     audio_count=None, collision=True, mode='normal', game=p.GAME):
            self.outer_events, self.array_reads = [], []
            self.case_mode, self.audio_count = mode, audio_count
            self.buffer = None
            self.outer_ready = False
            super().__init__(original=original, t=t, d=d, p=prefix, ordinal=ordinal,
                             associated=False, ui=False, manager_loop=False, game=game)
            self.remove_start, move_start = game+0x100C0000, game+0x10040000
            addresses = dict(kind='registered', game_base=game, code_address=self.remove_start,
                             roster_address=p.S, storage_address=p.B, move_code_address=move_start,
                             reject_address=game+0x100C8000)
            if original:
                remove_code = bytes.fromhex(p.remove_ev['bodies']['0x540a40']['bytes_hex'])
                self.remove_start = game+0x540A40
                _,old_move=mover.legacy()
                self.map(game+0x60C410,len(old_move)); self.write(game+0x60C410,old_move)
            else:
                remove_code = bytes.fromhex(
                    lib.remove_candidate(addresses, removal.build(**addresses))['code_hex'])
                move_args = dict(game_base=game, code_address=move_start, roster_address=p.S,
                                 storage_address=p.B, reject_address=game+0x10048000)
                move_code = bytes.fromhex(lib.mover_candidate(move_args, mover.build(**move_args))['code_hex'])
                self.map(move_start, len(move_code)); self.write(move_start, move_code)
                self.map(game+0x10048000, 1); self.write(game+0x10048000, b'\xcc')
                self.map(game+0x100C8000, 1); self.write(game+0x100C8000, b'\xcc')
            for addr, blob in ((game+0xFDC820, code), (game+0x540B20, leaf),
                               (self.remove_start, remove_code), (game+0x172F8A0, bytes.fromhex(p.remove_ev['bodies']['0x172f8a0']['bytes_hex']))):
                self.map(addr, len(blob)); self.write(addr, blob)
            if not original:
                # The saved leaf really transfers to 605950. The explicit test
                # hook jumps to the current C++ departure image without changing registers.
                self.map(game+0x605950, 5)
                self.write(game+0x605950, b'\xe9'+struct.pack('<i', self.start-(game+0x605955)))
            self.stub_addresses = {game+0x10400000+i*0x100: name for i, name in enumerate(
                ('before_other', 'remove_other', 'audio_enabled', 'audio_world', 'unit_of', 'enumerate', 'release', 'final_release'))}
            self.stub_addresses.update({game+rva: name for rva, name in
                ((0xB4BAD0, 'begin'), (0x870310, 'lookup'), (0xB50E60, 'end'), (0xB225F0, 'reset'), (0x2088770, 'cookie'))})
            self.by_role = {v:k for k,v in self.stub_addresses.items()}
            need(not set(self.stub_addresses).intersection((self.stop,self.tail,self.predicate,self.start,self.remove_start)), 'test code overlap')
            for addr in self.stub_addresses:
                self.map(addr, 1); self.write(addr, b'\xc3')
            for addr, size in ((MANAGER, 0x80), (HASH, 0x20000), (COMPONENTS, 16), (API, 0x600),
                               (OBJECT, 8), (OBJECT_TABLE, 16), (RECORDS, 0x400), (AUDIO_MAP, 32),
                               (OUTER_MAP, 32), (p.CONTEXT, 0x100)):
                self.map(addr, size)
            self.write(HASH, bytes(0x20000))
            for rva, value in ((0x3326508, MANAGER), (0x3326318, API), (0x263C010, COOKIE), (0x346BFA0, p.ASSOC_CONTEXT+0x1000)):
                self.map(game+rva, 8); self.write(game+rva, u64(value))
            self.map(game+0x348456C, 4); self.write(game+0x348456C, u32(0xFFFFFFFF))
            self.write(self.target, u64(TYPE)); self.write(self.target+0xC, u32(p.CONTROLLER_ID if audio_count is not None else 0))
            self.write(self.target+0x10, u32(0x7FFF))
            self.map(p.ASSOC_CONTEXT+0xF12EA0, 8); self.write(p.ASSOC_CONTEXT+0xF12EA0, u64(HASH))
            self.write(COMPONENTS, struct.pack('<3H', 5, 239, 7))
            bucket = TYPE & 4095
            if collision:
                self.write(HASH+bucket*32, u64(TYPE+4096)); bucket = 0
            self.write(HASH+bucket*32, u64(TYPE)+u64(COMPONENTS)+u32(3))
            for off, actual, other in ((0xF0DFB0, game+0x540B20, 'before_other'),
                                       (0xF0E9D0, self.remove_start, 'remove_other')):
                for index, target in ((5, 0), (239, actual), (7, self.by_role[other])):
                    addr=p.ASSOC_CONTEXT+off+index*8; self.map(addr, 8); self.write(addr, u64(target))
            self.write(MANAGER+0x48, u32(0))
            self.write(p.CONTEXT+0xC0, u64(OBJECT)); self.write(OBJECT, u64(OBJECT_TABLE))
            self.write(OBJECT_TABLE+8, u64(self.by_role['final_release']))
            # Execute the saved map-delete helper for the outer entity registry too.
            self.setup_map(p.ASSOC_CONTEXT+0xF1AEB0, OUTER_MAP, self.keys[ordinal], 2)
            if audio_count is not None:
                self.setup_map(MANAGER+0x40, AUDIO_MAP, self.keys[ordinal], 0)
                self.write(MANAGER+0x68, u64(RECORDS)); self.write(RECORDS+0x300, b'\1')
                self.write(MANAGER+0x70, u64(RECORDS+0x380)); self.write(RECORDS+0x380, u32(0))
                for off, role in ((0x10,'audio_enabled'), (0x58,'audio_world'), (0x2D0,'enumerate'), (0x2E8,'release')):
                    self.write(API+off, u64(self.by_role[role]))
                self.write(p.VTABLE+0x748, u64(self.by_role['unit_of']))
            self.uc.hook_add(p.UC_HOOK_MEM_READ, self.on_array_read)
            self.seed()
            self.uc.reg_write(p.reg('rcx'), p.ASSOC_CONTEXT)
            self.uc.reg_write(p.reg('rdx'), 0 if mode=='null' else self.target)
            self.uc.reg_write(p.reg('r8'), 0 if mode=='unflagged' else 1)
            if mode=='invalid': self.write(self.target+8, u32(0xFFFFFFFF))
            if mode=='unflagged': self.write(self.target+0x14, b'\0')
            self.initial_records = {name:[self.read(self.slot(name,i),stride) for i in range(t)] for name,off,old,stride in p.LAYOUT}
            self.initial_counts = self.counts()
            self.before = self.snapshot()
            self.outer_ready = True

        def setup_map(self, base, table, key, value):
            self.map(base, 0x18)
            self.write(base, u64(table)+u32(4)+u32(0)+u32(1))
            self.write(table, (u32(0)+u32(0xFFFFFFFF))*4)
            self.write(table+(key&3)*8, u32(key)+u32(value))

        def stub(self, role):
            if role != 'tail':
                return super().stub(role)
            # Tail return belongs to the real dispatcher's CALL at FDC953.
            rsp=self.uc.reg_read(p.reg('rsp'))
            need(self.int64(rsp)==self.game+0xFDC955, 'tail did not inherit real outer return')
            need(self.counts()==self.initial_counts, 'roster removed before departure tail')
            need(self.read(self.uc.reg_read(p.reg('rcx')),13)==b'player_count\0', 'tail literal')
            need(self.uc.reg_read(p.reg('rdx'))==self.d, 'tail dense count')
            self.outer_events.append(dict(role='departure_tail', counts=self.counts()))
            self.clobber(0)

        def clobber(self, result):
            rsp=self.uc.reg_read(p.reg('rsp'))
            need(rsp%16==8, 'external ABI alignment')
            self.write(rsp+8,b'\xc7'*32)
            for index, name in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):
                self.uc.reg_write(p.reg(name),0xCDCD000000000000+index)
            for i in range(6): self.uc.reg_write(p.reg('xmm'+str(i)),(0xAABBCCDDEEFF0000+i)*(1+(1<<64)))
            self.uc.reg_write(p.reg('rax'), result)

        def outer_stub(self, role):
            uc=self.uc
            args={n:uc.reg_read(p.reg(n)) for n in ('rcx','rdx','r8','r9')}
            event=dict(role=role,counts=self.counts())
            result=0
            if role in ('before_other','remove_other','reset'):
                need(args['rcx']==self.target, 'entity callback argument')
                if role=='before_other': need(self.counts()==self.initial_counts, 'pre-remove callback order')
            elif role in ('begin','end','final_release'):
                need(args['rcx']==self.keys[self.ordinal], 'entity ID callback argument')
            elif role=='lookup': need(args['rdx']==self.keys[self.ordinal], 'lookup ID')
            elif role=='cookie': need(args['rcx']==COOKIE, 'dispatcher stack cookie changed')
            elif role=='audio_enabled': result=1
            elif role=='audio_world': need(args['rcx']==p.ASSOC_CONTEXT+0x1000, 'world context'); result=WORLD
            elif role=='unit_of': need(args['rcx']==p.CONTROLLER_ID, 'unit index'); result=0xDDCCBBAA11223344
            elif role=='enumerate':
                need(args['rcx']==WORLD and args['rdx']==0xDDCCBBAA11223344 and args['r9']==16, 'array callback ABI')
                self.buffer=args['r8']; need(self.buffer==p.RSP-200, 'local array position')
                # The provider writes at most its requested capacity, including
                # the adversarial count-only cases. No overflow is injected.
                for i in range(min(self.audio_count,16)): self.write(self.buffer+8*i,u64(0xA000+i))
                result=self.audio_count; event['returned_count']=result
            elif role=='release':
                need(args['rcx']==WORLD and args['r8']==0, 'release callback ABI')
                event['value']=hex(args['rdx'])
            else: raise ValueError(role)
            self.outer_events.append(event)
            self.clobber(result)

        def on_array_read(self, uc, access, address, size, value, data):
            if self.buffer is None or uc.reg_read(p.reg('rip'))!=self.game+0xFDCAAA: return
            index=(address-self.buffer)//8
            need(size==8 and address==self.buffer+8*index, 'array stride')
            self.array_reads.append(dict(index=index,entry_rsp_offset=address-p.RSP,bytes=size,within_requested_capacity=index<16))
            if index>=16 and self.audio_count==0xFFFFFFFF:
                self.outcome='out_of_bounds_read'; uc.emu_stop()

        def on_code(self,uc,address,size,data):
            if self.outer_ready:
                if address in (self.game+0x100C8000,self.game+0x10048000):
                    self.outcome='reject'; uc.emu_stop(); return
                if address in (self.game+0x540B20,self.remove_start):
                    self.outer_events.append(dict(role='departure_entry' if address==self.game+0x540B20 else 'remove_entry',counts=self.counts()))
                if address==self.predicate and self.int64(uc.reg_read(p.reg('rsp'))) in (self.game+0xFDCA3D,self.game+0xFDCCBF):
                    need(uc.reg_read(p.reg('rcx'))==p.CONTROLLER_ID, 'outer unit predicate')
                    self.outer_events.append(dict(role='unit_exists',counts=self.counts()))
                    self.clobber(1); return
                if address in self.stub_addresses:
                    self.trace.append(address); self.outer_stub(self.stub_addresses[address]); return
            super().on_code(uc,address,size,data)

        def execute(self, name):
            try:
                self.uc.emu_start(self.game+0xFDC820,0,count=100000)
            except Exception as ex:
                state={n:hex(self.uc.reg_read(p.reg(n))) for n in ('rip','rsp','rax','rcx','rdx','r8','rdi')}
                raise RuntimeError(name+' '+json.dumps(state)) from ex
            need(self.outcome in ('return','out_of_bounds_read'), 'dispatcher did not finish: '+str(self.outcome))
            if self.outcome=='return':
                need(self.uc.reg_read(p.reg('rsp'))==p.RSP+8, 'outer return stack')
                for n,v in p.SEEDS.items(): need(self.uc.reg_read(p.reg(n))==v, 'outer nonvolatile '+n)
                for i in range(6,16): need(self.uc.reg_read(p.reg('xmm'+str(i)))==(0x0102030405060708+i)*(1+(1<<64)), 'outer XMM')
            early=self.case_mode in ('null','invalid','unflagged')
            if self.audio_count==0xFFFFFFFF:
                need(self.outcome=='out_of_bounds_read' and len(self.array_reads)==17, 'unbounded count control not stopped at first invalid read')
                need(self.counts()==self.initial_counts and not any(e['role']=='remove_entry' for e in self.outer_events), 'unexpected work after unbounded count')
            if early:
                need(self.counts()==self.initial_counts and self.snapshot()==self.before, 'early return changed data')
                need([e['role'] for e in self.outer_events] == ([] if self.case_mode=='null' else ['cookie']), 'early callbacks')
            elif self.outcome=='return':
                roles=[e['role'] for e in self.outer_events]
                sequence=['begin','departure_entry','departure_tail','before_other','lookup','remove_entry','remove_other','end','reset','final_release','cookie']
                need([r for r in roles if r in sequence]==sequence, 'real dispatch order')
                expected=[self.t-1,self.d-int(self.ordinal<self.d),self.p-int(self.ordinal<self.p)]
                need(self.counts()==expected, 'post-remove counts')
                # Derive the independent segment-compaction model from the old
                # boundaries: prefix last, dense last, pending last.
                indices=list(range(self.t)); hole=self.ordinal
                for end in (self.p,self.d,self.t):
                    if hole<end:
                        indices[hole]=indices[end-1];hole=end-1
                indices=indices[:-1]
                for group,off,old,stride in p.LAYOUT:
                    for at,old_index in enumerate(indices):
                        need(self.read(self.slot(group,at),stride)==self.initial_records[group][old_index], 'compaction '+group)
                for key,ordinal in (struct.unpack('<II',self.read(p.MAP+i*8,8)) for i in range(8)):
                    if key: need(ordinal<len(indices) and self.keys[indices[ordinal]]==key, 'map relocation')
                need(self.keys[self.ordinal] not in [self.int32(p.MAP+i*8) for i in range(8)], 'deleted ID remained')
                need(self.int32(self.target+8)==0xFFFFFFFF and self.int32(self.target+0xC)==0 and self.int32(self.target+0x10)==0x7FFF and self.int32(self.target+0x14)==0, 'final entity reset')
                need(self.int32(OUTER_MAP+(self.keys[self.ordinal]&3)*8)==0, 'outer registry not deleted')
                if self.audio_count is not None:
                    released=[e['value'] for e in self.outer_events if e['role']=='release']
                    need(len(released)==self.audio_count, 'returned count not consumed')
                    need(released[:16]==[hex(0xA000+i) for i in range(min(self.audio_count,16))], 'enumerated values')
                    if self.audio_count==17:
                        need(released[16]==hex(COOKIE^(p.RSP-264)), '17th read did not consume stack cookie')
            allowed=[(p.STACK,0x10000),(p.S+0x80,12),(p.MAP,64),(OUTER_MAP,32),(self.target+8,16)]
            allowed += [(self.slot(group,0),stride*self.t) for group,off,old,stride in p.LAYOUT]
            allowed += [(address,len(blob)) for address,blob in self.expected_changes]
            need(all(any(lo<=address and address+size<=lo+length for lo,length in allowed)
                     for address,size in self.writes), 'native store escaped declared data regions')
            rows=[pc-self.game for pc in self.trace if self.game+0xFDC820<=pc<self.game+0xFDCDFF]
            case=dict(name=name,original_roster_callbacks=self.original,outcome=self.outcome,
                      initial_counts=self.initial_counts,final_counts=self.counts(),ordinal=self.ordinal,
                      native_stores_checked=len(self.writes),
                      dispatcher_unique_instructions=len(set(rows)),dispatcher_trace_sha256=sha(b''.join(u32(pc) for pc in rows)),
                      events=self.outer_events,array_reads=self.array_reads,dispatcher_instruction_rvas=sorted(set(rows)))
            cases.append(case)
            return self

    for mode in ('null','invalid','unflagged'):
        Fixture(mode=mode).execute(mode)
    # Original four-slot baseline also executes the saved mover's self-copy.
    Fixture(original=True,t=4,d=4,prefix=0,ordinal=3).execute('original_four')
    Fixture(t=4,d=4,prefix=0,ordinal=3).execute('candidate_four')
    for t,d,prefix,ordinal in ((5,5,0,4),(6,3,1,4),(7,5,2,1),(8,6,2,0),(8,6,2,3),(8,6,2,6),(8,0,0,7),(8,8,8,7)):
        Fixture(t=t,d=d,prefix=prefix,ordinal=ordinal).execute('candidate_'+str((t,d,prefix,ordinal)))
    Fixture(game=0x7FF800000000,collision=False,ordinal=5).execute('second_base_no_collision')
    for count in (0,1,16,17,0xFFFFFFFF):
        Fixture(audio_count=count).execute('callback_count_'+str(count))
    union=sorted({pc for row in cases for pc in row.pop('dispatcher_instruction_rvas')})
    instructions=p.decode(code,0xFDC820)
    need(any(not a['within_requested_capacity'] for row in cases for a in row['array_reads']), 'missing caller-bound counterexample')
    paths=['tools/validate_entity_remove.py','native-entity-remove.lock.json','tools/native_departure_image.py',
           'native-departure.lock.json','native-getter.lock.json','native-remove.lock.json','native-mover.lock.json',
           'tools/native_departure_library.py','tools/native_property_library.py','tools/native_getter_image.py',
           'tools/native_remove_image.py','tools/native_mover_image.py',
           'mod/src/ep_departure_image.cpp','mod/src/ep_departure_templates.h','mod/src/ep_remove_image.cpp',
           'mod/src/ep_remove_templates.h','mod/src/ep_mover_image.cpp','mod/src/ep_mover_template.h',
           'mod/src/ep_getter_image.cpp','mod/src/ep_getter_template.h']
    legacy={**pins,**departure.profile()['legacy_source_sha256']}
    legacy[departure.profile()['fixture_path']]=departure.profile()['fixture_sha256']
    receipt=dict(schema='hellforge_entity_remove_dispatch_validation_v1',passed=True,
                 verified_at_utc=datetime.now(timezone.utc).isoformat(),game_build=25480438,
                 cases=cases,case_count=len(cases),dispatcher_bytes=len(code),dispatcher_sha256=sha(code),
                 dispatcher_unique_instructions=len(union),dispatcher_total_instructions=len(instructions),
                 unexecuted_instruction_rvas=[hex(i.address) for i in instructions if i.address not in union],
                 actual_saved_dispatcher_executed=True,actual_saved_departure_leaf_executed=True,
                 actual_saved_map_delete_executed=True,cpp_roster_images_executed_in_emulator=True,
                 caller_count_bound_counterexamples=2,provider_return_bound_verified=False,
                 all_dispatcher_paths_verified=False,all_entity_types_verified=False,
                 callbacks_are_contract_stubs=True,owner_and_sdk_chain_in_this_emulation=False,
                 real_callback_abi_verified=False,rollback_verified=False,
                 source_sha256={name:sha((PROJECT/name).read_bytes()) for name in paths},legacy_source_sha256=legacy,
                 reference_validation_sha256={name:sha((PROJECT/'evidence'/name).read_bytes()) for name in
                    ('native-departure-validation.json','native-getter-validation.json','native-remove-validation.json','native-mover-validation.json')},
                 artifacts={lib.path.name:dict(bytes=lib.path.stat().st_size,sha256=sha(lib.path.read_bytes()))},
                 game_access=False,native_execution_of_game_bodies=False,runtime_verified=False,multiplayer_verified=False)
    (PROJECT/'evidence/entity-remove-dispatch-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return {k:receipt[k] for k in ('passed','case_count','dispatcher_unique_instructions','dispatcher_total_instructions','caller_count_bound_counterexamples','game_access')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(validate(args.library.resolve())))
