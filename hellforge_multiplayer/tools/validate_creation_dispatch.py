"""Replay saved creation dispatch with real C++ roster bytes in Unicorn only.

Other component providers, engine/resource APIs and container construction are
explicit contracts. Passing this test is not character creation or gameplay.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eight_player_candidate_20260927/.native-test-deps'))
sys.path.insert(0, str(ROOT / 'research_handoff_20260927/indirect'))
import unicorn
from inspect_capture import Image
import native_insert_image as insertion
import native_mover_image as mover
from native_property_library import Library

LOCK = ROOT / 'hellforge_multiplayer/native-creation-dispatch.lock.json'
LOCK_SHA = '914586a362d32b3b3c3f38d8f8bfdc38c4d673d10a09a121c5b852da74c45d1c'
COMPONENTS = [3, 33, 41, 43, 226, 238, 239, 250, 260]
CONTEXT = 0x18400000000
OWNER = CONTEXT + 0x40
OWNER8 = 0x18402000000
RESOURCE = 0x18403000000
HASH_TABLE = 0x18404000000
COMPONENT_LIST = 0x18405000000
API = 0x18406000000
META = 0x18407000000
MAPS = 0x18408000000
LIST = 0x18409000000
S33 = OWNER + 0x3CA0
COOKIE = 0x763912BADC0FFE
RESOURCE_HASH = 0xCDC1F82CE3337A82
u32 = lambda x: struct.pack('<I', x)
u64 = lambda x: struct.pack('<Q', x)
sha = lambda x: hashlib.sha256(x).hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def source():
    need(sha(LOCK.read_bytes()) == LOCK_SHA, 'creation lock changed')
    lock = json.loads(LOCK.read_bytes())
    for name, digest in lock['source_sha256'].items():
        need(sha((ROOT / name).read_bytes()) == digest, 'source changed: ' + name)
    image = Image(ROOT / lock['capture_directory'])
    need(image.report['capture_sha256'] == lock['capture_sha256'], 'capture changed')
    for f in lock['functions'].values():
        body = image.read(f['start'], f['end'] - f['start'])
        need(sha(body) == f['sha256'] and body.hex() == f['body_hex'], 'dispatch bytes changed')
        for row in f['fragments']:
            need(image.containing(row[0]) == tuple(row), 'unwind fragment changed')
            need(image.root(row[0])[0] == f['start'], 'unwind root changed')
    evidence = json.loads((ROOT / 'five_player_feasibility_20260927/component33_250_lifecycle_evidence_v2.json').read_bytes())
    f = evidence['code_bodies']['0x51ac70']
    component = b''.join(bytes.fromhex(i['bytes']) for i in f['instructions'])
    need(sha(component) == f['sha256'], 'component33 bytes changed')
    need(image.read(0x51AC70, len(component)) == component, 'component33 capture mismatch')
    row33 = next(r for r in evidence['callback_tables']['33'] if r['table'] == '0xf0c110')
    need(row33['target'] == '0x51ac70' and int(row33['slot'], 16) == 0xF0C110 + 33 * 8, 'component33 registration changed')
    for instruction in row33['assignment']['instructions']:
        body = bytes.fromhex(instruction['bytes'])
        need(image.read(int(instruction['rva'], 16), len(body)) == body and sha(body) == instruction['sha256'], 'component33 registration bytes changed')
    metadata = json.loads((ROOT / 'five_player_feasibility_20260927/spawn_resource_metadata_evidence.json').read_bytes())
    player = next(r for r in metadata['reference_metadata']['resources'] if int(r['resource_hash'], 16) == RESOURCE_HASH)
    need(player['indices'] == COMPONENTS and player['count'] == len(COMPONENTS), 'reference player component order changed')
    registration = json.loads((ROOT / 'five_player_feasibility_20260927/spawn_callback_registration_evidence_v2.json').read_bytes())
    row = next(r for r in registration['component_239'] if r['table_base_offset'] == '0xf0c110')
    need(row['target_rva'] == '0x540920' and int(row['destination_offset'], 16) == 0xF0C110 + 239 * 8, 'roster callback registration changed')
    for instruction in (row['lea'], row['store']):
        body = bytes.fromhex(instruction['bytes'])
        need(image.read(int(instruction['rva'], 16), len(body)) == body and sha(body) == instruction['sha256'], 'registration bytes changed')
    return lock, component


def validate(library, component_library=None):
    lock, component33 = source()
    p = insertion.load_fixture()
    p.native.build = insertion.emitter(library)
    mover.bind_insertion_fixture(p, library)
    visited = set()

    class Fixture(p.Fixture):
        def __init__(self, count, *, original=False, components=False, literal8=False,
                     resource_type=17, game=p.GAME, native33=False, initialize33=False):
            super().__init__('dense_registered', count, count, count, 1, original=original, game=game)
            self.native33 = native33
            self.initialize33=initialize33
            self.descriptor_base=None;self.descriptor_count_pointer=None
            self.side33 = 0x1840A000000
            self.entry33 = game+0x10300000
            self.move33 = game+0x10310000
            self.reject33 = game+0x10320000
            self.events = []
            self.invalid = []
            self.external = {}
            self.literal8 = literal8
            self.with_components = components
            self.resource_type = resource_type
            self.record = CONTEXT + 0xF32F18 + count * 24
            self.components = COMPONENTS if components else [239]
            self.member_count = count if native33 else min(count, 4)
            self.component_before = None
            self.handle = p.NEW_ID
            self.outer_initialized = False
            self.zero(CONTEXT, 0x100)
            self.write(CONTEXT + 8, u64(OWNER8))
            self.zero(CONTEXT + 0xF32F10, 0xC020)
            self.zero(CONTEXT + 0xF3EF00, 0xA00)
            self.write(CONTEXT + 0xF32F14, u32(count))
            for i in range(0x800):
                self.write(CONTEXT + 0xF32F20 + 24 * i, u32(0xFFFFFFFF))
            self.write(CONTEXT + 0xF3F820, u64(0x12345678))
            self.zero(OWNER8, 0xC000)
            self.write(OWNER8 + 0x18, u32(count + 3))
            self.zero(MAPS, 0x3000)
            self.init_map(CONTEXT + 0xF1AEB0, MAPS, 16)
            self.init_map(CONTEXT + 0xF22EC8, MAPS + 0x1000, 16)
            self.init_map(OWNER8 + 0xB020, MAPS + 0x2000, 16)
            for i in range(count + 3):
                self.seed_map(OWNER8 + 0xB020, 0x6000 + i, i)
                self.write(OWNER8 + 0x1C + 4 * i, u32(0x6000 + i))
            for i in range(count):
                old_record = CONTEXT + 0xF32F18 + 24 * i
                old_handle, old_ordinal = 1 + 8 * i, 0x6003 + i
                self.write(old_record, u64(RESOURCE_HASH) + u32(old_handle) + u32(0) + u32(old_ordinal) + u32(1))
                self.seed_map(CONTEXT + 0xF1AEB0, old_handle, i)
                self.seed_map(CONTEXT + 0xF22EC8, old_ordinal, i)
                self.write(self.slot('pointer', i), u64(old_record))
            self.zero(META, 0x1000)
            self.write(META, b'\x01')
            self.write(META + 4, u32(0x11223344))
            self.zero(RESOURCE + 0xF12EA0, 8)
            self.write(RESOURCE + 0xF12EA0, u64(HASH_TABLE))
            self.zero(HASH_TABLE, 0x20000)
            self.zero(COMPONENT_LIST, 0x1000)
            self.write(COMPONENT_LIST, struct.pack('<' + 'H' * len(self.components), *self.components))
            descriptor = u64(RESOURCE_HASH) + u64(COMPONENT_LIST) + u32(len(self.components)) + u32(0) + u32(resource_type) + u32(0)
            self.write(HASH_TABLE + (RESOURCE_HASH & 0xFFF) * 32, descriptor)
            self.zero(API, 0x1000)
            self.zero(LIST, 0x1000)
            self.write(LIST, u64(LIST))
            for rva, value in ((0x346BF98, RESOURCE), (0x33263E8, API), (0x3326368, API + 0x100),
                               (0x3326308, API + 0x200), (0x3326E68, API + 0x400),
                               (0x263C010, COOKIE), (0x33267B8, S33)):
                self.zero(game + rva, 8)
                self.write(game + rva, u64(value))
            for invalid_id_global in (0x348456C,0x3483C34):
                self.zero(game + invalid_id_global, 4)
                self.write(game + invalid_id_global, u32(0xFFFFFFFF))
            for f in lock['functions'].values():
                self.map(game + f['start'], f['end'] - f['start'])
                self.write(game + f['start'], bytes.fromhex(f['body_hex']))
            self.stub('list_init', game + 0x173B6F0)
            self.stub('copy', game + 0x20988F0)
            self.stub('resource_transform', game + 0x5740B0)
            self.stub('cookie', game + 0x2088770)
            self.stub('final_tag', game + 0xFDD750)
            self.write(API + 0x70, u64(self.stub('scope_enter')))
            self.write(API + 0x78, u64(self.stub('scope_exit')))
            self.write(API + 0x128, u64(self.stub('resource_retain')))
            self.write(API + 0x140, u64(self.stub('final_notify')))
            self.write(API + 0x238, u64(API + 0x300))
            self.write(API + 0x240, u64(API + 0x500))
            self.write(API + 0x308, u64(self.stub('world')))
            self.write(API + 0x588, u64(self.stub('create_resource')))
            # No optional observer of type 0x18 in this contract fixture.
            self.zero(API + 0x400 + 0xCB8, 4)
            self.zero(OWNER + 0xF0C110, 0x1D00)
            for phase, table in enumerate((0xF0C110, 0xF0CB30, 0xF0D550), 1):
                for component in self.components:
                    callback = (self.start if phase == 1 and component == 239 else
                                (self.entry33 if native33 else game + 0x51AC70) if phase == 1 and component == 33 else
                                game+(0x51ADB0 if phase==2 else 0x51ADE0) if initialize33 and component==33 and phase in (2,3) else
                                self.stub(f'component_{phase}_{component}'))
                    self.write(OWNER + table + component * 8, u64(callback))
            if components:
                self.zero(S33, 0x400)
                self.write(S33 + 4, u32(2))
                self.write(S33 + 8, u32(self.member_count) * 3)
                self.init_map(S33 + 0x58, S33 + 0x14, 8)
                for i in range(self.member_count):
                    self.write(S33 + 0x14 + 8 * ((1 + i) & 7), u32(1 + 8 * i) + u32(i))
                self.write(S33 + 0x70, b'\x68' * (0x2B8 - 0x70))
                for i in range(min(self.member_count,4)):
                    self.write(S33 + 0x70 + 8 * i, u64(CONTEXT + 0xF32F18 + 24 * i))
                self.component_before = self.read(S33, 0x400)
                code = bytearray(component33)
                if literal8:
                    need(code[0x1B] == 4, 'literal control offset changed')
                    code[0x1B] = 8
                self.map(game + 0x51AC70, len(code))
                self.write(game + 0x51AC70, bytes(code))
                if native33:
                    need(component_library is not None and not literal8,'component33 library required')
                    self.zero(self.side33-0x80,0x590);self.write(self.side33-0x80,b'\xb6'*0x590)
                    for i in range(count):self.write(self.side33+i*8,u64(CONTEXT+0xF32F18+24*i))
                    for kind,entry in (('dense',self.entry33),('mover',self.move33)):
                        image=component_library.candidate(kind,game_base=game,code_address=entry,component_address=S33,
                            storage_address=self.side33,move_code_address=self.move33,reject_address=self.reject33)['image']
                        self.map(entry,len(image));self.write(entry,image)
                    self.map(self.reject33,1);self.write(self.reject33,b'\xcc')
                    if initialize33:
                        import component33_initialization_fixture as initialization
                        import native_component33_image as component_image
                        self.initialization=initialization
                        def put(address,body):self.map(address,len(body));self.write(address,body)
                        self.expected_secondary=initialization.seed_inputs(put,game)
                        put(initialization.ALLOC-0x40,b'\xab'*0xC0)
                        self.stub('component33_allocate',game+0x173B8D0);self.stub('component33_clear',game+0x208AAA0)
                        for kind,entry in (('property',game+0x10330000),('reset',game+0x10340000)):
                            image=component_library.candidate(kind,game_base=game,code_address=entry,component_address=S33,
                                storage_address=self.side33,move_code_address=self.move33,reject_address=self.reject33)['image']
                            put(entry,image);w=component_image.profile()['initialization_callbacks'][kind];blob=bytearray.fromhex(w['body_hex'])
                            offset=0x19 if kind=='property' else 0xE;need(blob[offset]==0xE8,'callback call changed')
                            struct.pack_into('<i',blob,offset+1,entry-(game+w['entry']+offset+5));put(game+w['entry'],bytes(blob))
                        for rva,size in ((0x3797960,0x800),(0x3798180,0x20),(0x3797550,0x400),(0x348BA88,8)):put(game+rva,b'\x96'*size)
            self.uc.reg_write(p.reg('rcx'), CONTEXT)
            self.uc.reg_write(p.reg('rdx'), self.handle)
            self.uc.reg_write(p.reg('r8'), RESOURCE_HASH)
            self.uc.reg_write(p.reg('r9'), META)
            self.uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, self.on_invalid)
            self.outer_initialized = True

        def zero(self, address, size):
            self.map(address, size)
            self.write(address, bytes(size))

        def int32(self, address):
            return struct.unpack('<I', self.read(address, 4))[0]

        def int64(self, address):
            return struct.unpack('<Q', self.read(address, 8))[0]

        def counts(self):
            return [self.int32(p.S + i) for i in (0x80, 0x84, 0x88)]

        def init_map(self, header, data, capacity):
            self.zero(header, 20)
            self.zero(data, capacity * 8)
            self.write(header, u64(data) + u32(capacity) + u32(0) + u32(1))

        def seed_map(self, header, key, value):
            capacity, data = self.int32(header + 8), self.int64(header)
            for offset in range(capacity):
                bucket = (key + offset) & (capacity - 1)
                if self.int32(data + bucket * 8) == 0:
                    self.write(data + bucket * 8, u32(key) + u32(value))
                    return
            raise ValueError('invalid full seed map')

        def map_value(self, header, key):
            capacity, data = self.int32(header + 8), self.int64(header)
            matches = [self.int32(data + i * 8 + 4) for i in range(capacity) if self.int32(data + i * 8) == key]
            need(len(matches) == 1, 'missing or duplicated map key')
            return matches[0]

        def stub(self, name, address=None):
            address = address or self.game + 0x10200000 + len(self.external) * 0x20
            need(address not in self.external, 'duplicate contract address')
            self.map(address, 1)
            self.write(address, b'\xc3')
            self.external[address] = name
            return address

        def clobber(self, result=0):
            rsp = self.uc.reg_read(p.reg('rsp'))
            need(rsp % 16 == 8, 'contract call alignment')
            self.write(rsp + 8, b'\xc7' * 32)
            for i, name in enumerate(('rax', 'rcx', 'rdx', 'r8', 'r9', 'r10', 'r11')):
                self.uc.reg_write(p.reg(name), 0xCDCD000000000000 + i)
            for i in range(6):
                self.uc.reg_write(p.reg('xmm' + str(i)), (0xAACCDDEEFF000000 + i) * (1 + (1 << 64)))
            self.uc.reg_write(p.reg('rax'), result)

        def contract(self, name):
            args = {n: self.uc.reg_read(p.reg(n)) for n in ('rcx', 'rdx', 'r8', 'r9')}
            rsp = self.uc.reg_read(p.reg('rsp'))
            result = 0
            if name.startswith('component_'):
                _, phase, component = name.split('_')
                need(args['rcx'] == self.record and args['rdx'] == META, 'component ABI')
                if phase == '2':
                    count=4 if self.initialize33 and self.components.index(int(component))>self.components.index(33) else 0
                    need(args['r8'] % 16 == 0 and self.int32(args['r9']) == count, 'descriptor ABI')
                    need(self.int64(self.int64(rsp + 40)) == LIST, 'fifth callback argument')
            elif name in ('scope_enter', 'scope_exit'):
                need(args['rcx'] == 0x12345678, 'resource outer scope argument')
            elif name == 'resource_retain':
                need(args['rdx'] == RESOURCE_HASH, 'resource hash retain')
            elif name == 'list_init':
                self.write(args['rcx'], u64(LIST) * 3)
                result = args['rcx']
            elif name == 'copy':
                need(args['r8'] == 0, 'nonempty transform inputs are outside fixture')
                result = args['rcx']
            elif name == 'resource_transform':
                need(args['rcx'] == OWNER and args['rdx'] == self.record, 'transform ABI')
            elif name == 'world':
                result = 0x12340000
            elif name == 'create_resource':
                need(args['rcx'] == 0x12340000 and args['rdx'] == self.resource_type and args['r9'] == (4 if self.initialize33 else 0), 'resource create ABI')
                if self.initialize33:need(args['r8']==self.descriptor_base,'descriptor pointer not forwarded to resource API')
                result = 0x7000 + self.t
            elif name=='component33_allocate':
                need(args['rcx']==LIST and args['rdx']==56 and args['r8']==4,'creation property allocation ABI');result=self.initialization.ALLOC
            elif name=='component33_clear':
                need(args['rcx']==self.game+0x3797550 and args['rdx']==0 and args['r8']==0x400,'creation reset clear ABI')
                self.write(args['rcx'],bytes(0x400));result=args['rcx']
            elif name == 'cookie':
                need(args['rcx'] == COOKIE, 'stack cookie changed')
            elif name == 'final_tag':
                need(args['rcx'] == 0 and args['rdx'] == self.handle and args['r8'] == 0x8ED8CD89 and args['r9'] == 0, 'final tag ABI')
            elif name != 'final_notify':
                raise ValueError('unhandled contract ' + name)
            self.events.append({'role': name, 'roster_counts': self.counts()})
            self.clobber(result)

        def on_code(self, uc, address, size, data):
            self.trace.append(address)
            visited.add(address - self.game)
            if self.native33 and address==self.reject33:
                self.outcome="component33_reject";uc.emu_stop();return
            if self.native33 and address==self.entry33:
                self.events.append({"role":"native_component33_insert","roster_counts":self.counts()})
            if self.initialize33 and address in (self.game+0x51ADB0,self.game+0x51ADE0):
                phase=2 if address==self.game+0x51ADB0 else 3
                need(uc.reg_read(p.reg('rcx'))==self.record,'actual initialization callback entity')
                if phase==2:
                    self.descriptor_base=uc.reg_read(p.reg('r8'));self.descriptor_count_pointer=uc.reg_read(p.reg('r9'))
                    need(self.int32(self.descriptor_count_pointer)==0,'initial descriptor count')
                self.events.append({'role':f'component_{phase}_33','native_component33':True,'roster_counts':self.counts()})
            if address in (self.stop, self.reject, self.move_reject):
                self.outcome = 'return' if address == self.stop else 'roster_reject'
                uc.emu_stop()
                return
            if address == self.start:
                self.events.append({'role': 'native_roster_insert', 'roster_counts': self.counts()})
            if address == self.game + 0x51AC70:
                self.events.append({'role': 'original_component33_insert', 'roster_counts': self.counts()})
            if address == self.game + 0x172F790:
                self.events.append({'role': 'real_map_insert', 'header': hex(uc.reg_read(p.reg('rcx')))})
            if address in self.external:
                self.contract(self.external[address])

        def on_invalid(self, uc, access, address, size, value, data):
            self.invalid.append({'access': access, 'address': hex(address), 'size': size,
                                 'rva': hex(uc.reg_read(p.reg('rip')) - self.game)})
            self.outcome = 'invalid_memory'
            return False

        def execute(self, name):
            try:
                self.uc.emu_start(self.game + 0xFDC140, 0, count=100000)
            except unicorn.UcError as exc:
                if not self.invalid:
                    state = {n: hex(self.uc.reg_read(p.reg(n))) for n in ('rip', 'rsp', 'rax', 'rcx', 'rdx', 'r8', 'r9')}
                    raise ValueError(name + ' ' + json.dumps(state)) from exc
            need(self.outcome is not None, 'bounded dispatcher did not finish')
            allowed = [(p.STACK, 0x10000), (p.S, 0x600), (p.B, 0x780), (p.MAP, 0x100),
                       (CONTEXT + 0xF32F14, 0xC014), (CONTEXT + 0xF3F829, 1),
                       (META + 0x48, 16), (MAPS, 0x3000), (OWNER8, 0xC000), (LIST, 8)]
            if self.with_components:
                allowed.append((S33, 0x400))
                if self.native33:allowed.append((self.side33,0x490))
                if self.initialize33:allowed.extend([(self.initialization.ALLOC,56)]+[(self.game+rva,size) for rva,size in ((0x3797960,0x800),(0x3798180,0x20),(0x3797550,0x400),(0x348BA88,8))])
            for address, size in self.writes:
                # The intentional original guard faults before a null write can
                # commit. Unicorn records its attempted write as well.
                if address == 0 and self.invalid:
                    continue
                need(any(a <= address and address + size <= a + n for a, n in allowed), 'unexpected native write ' + hex(address))
            # These writes precede every selected callback, including rejection.
            need(self.int64(self.record) == RESOURCE_HASH and self.int32(self.record + 8) == self.handle, 'resource record registration')
            need(self.int32(self.record + 0x14) == 1, 'record classified flag')
            need(self.int32(CONTEXT + 0xF32F14) == self.t + 1, 'resource search cursor')
            need(self.int64(META + 0x48) == CONTEXT + 0xF3EF28 and self.int64(META + 0x50) == CONTEXT + 0xF3F7C8, 'metadata default writes')
            need(self.map_value(CONTEXT + 0xF1AEB0, self.handle) == self.t, 'outer real handle map insertion')
            for i in range(self.t):
                need(self.map_value(CONTEXT + 0xF1AEB0, 1 + 8 * i) == i, 'existing resource handle map changed')
                need(self.map_value(CONTEXT + 0xF22EC8, 0x6003 + i) == i, 'existing resource ordinal map changed')
            for i in range(self.t + 3):
                need(self.map_value(OWNER8 + 0xB020, 0x6000 + i) == i, 'existing owner ordinal map changed')
            need([e['role'] for e in self.events[:2]] == ['scope_enter', 'resource_retain'], 'outer callback order')
            if self.outcome != 'return':
                need(self.int32(self.record + 0x10) == 0x11223344 and self.int32(OWNER8 + 0x18) == self.t + 3, 'unexpected work after refusal')
                need(not any(e['role'] in ('scope_exit', 'create_resource', 'final_tag') for e in self.events), 'tail ran after refusal')
            if self.native33:
                need(self.read(S33+0x70,0x2B8-0x70)==self.component_before[0x70:0x2B8],'native33 changed original arrays')
                need(self.read(self.side33-0x80,0x80)==b'\xb6'*0x80 and self.read(self.side33+0x490,0x80)==b'\xb6'*0x80,'native33 sidecar overrun')
                if self.t==8:
                    need(self.outcome=='component33_reject' and self.uc.reg_read(p.reg('r10'))==2,'component33 ninth admission')
                    need(self.read(S33,0x400)==self.component_before and self.counts()==[8]*3,'component33 refusal wrote state')
                    need(not any(e['role']=='native_roster_insert' for e in self.events),'roster reached after component33 refusal')
                else:
                    need([self.int32(S33+i) for i in (8,12,16)]==[self.t+1]*3,'component33 count not inserted')
                    need(self.int64(self.side33+8*self.t)==self.record and self.map_value(S33+0x58,self.handle)==self.t,'component33 record/map mismatch')
                    primary=b'\xff'*44+bytes(36) if self.initialize33 else bytes(0x50)
                    need(self.read(self.side33+0x50+0x50*self.t,0x50)==primary,'component33 primary initialization')
                    secondary=bytearray(b'\xb6'*0x1C0)
                    if self.initialize33:
                        secondary[self.t*56:(self.t+1)*56]=self.expected_secondary
                        need(self.read(self.initialization.ALLOC,56)==self.expected_secondary,'creation property payload')
                        need(self.int32(self.descriptor_count_pointer)==4,'creation descriptor count')
                        descriptors=b''.join(struct.pack('<IIQ',h,t,self.initialization.ALLOC+off) for h,t,off in ((0xDFE49C6F,10,0),(0x64E318CE,10,24),(0xAE5166E8,10,32),(0xAA7E1B9E,1,52)))
                        need(self.read(self.descriptor_base,64)==descriptors,'creation descriptors')
                        need(self.read(self.game+0x3797960,0x800)==bytes(0x800) and self.read(self.game+0x3797550,0x400)==bytes(0x400) and self.read(self.game+0x348BA88,8)==bytes(8),'third callback global reset')
                    need(self.read(self.side33+0x40,8)==b'\xb6'*8 and self.read(self.side33+0x2D0,0x1C0)==secondary,'component33 byte/secondary changed')
            if self.native33 and self.t==8:
                pass
            elif self.with_components and self.t >= 4 and not self.literal8 and not self.native33:
                need(self.outcome == 'invalid_memory' and self.invalid == [{'access': unicorn.UC_MEM_WRITE_UNMAPPED, 'address': '0x0', 'size': 4, 'rva': '0x51ac8e'}], 'component33 four-slot boundary')
                need(self.counts() == [self.t] * 3 and self.read(S33, 0x400) == self.component_before, 'rejected component changed')
                need(not any(e['role'] == 'native_roster_insert' for e in self.events), 'roster reached after component33 refusal')
            elif self.t == 8:
                need(self.outcome == 'roster_reject' and self.uc.reg_read(p.reg('r10')) == 2, 'ninth roster admission')
                need(self.counts() == [8] * 3, 'ninth changed roster')
            elif self.original and self.t == 4:
                need(self.outcome == 'invalid_memory' and self.invalid[0]['address'] == '0x0', 'original roster four-slot boundary')
                need(self.counts() == [4] * 3, 'original refusal changed roster')
            else:
                need(self.outcome == 'return' and not self.invalid, 'normal dispatch did not return: ' + json.dumps(self.invalid))
                need(self.counts() == [self.t + 1] * 3, 'roster was not inserted exactly once')
                need(self.int64(self.slot('pointer', self.t)) == self.record, 'roster points to resource record')
                if self.resource_type == 0xFFFFFFFF:
                    need(self.int32(self.record + 0x10) == 0x7FFF and self.int32(OWNER8 + 0x18) == self.t + 3, 'missing resource type control')
                    need(not any(e['role'] == 'create_resource' for e in self.events), 'invalid type called provider')
                else:
                    ordinal = 0x7000 + self.t
                    need(self.int32(self.record + 0x10) == ordinal, 'resource ordinal result')
                    need(self.int32(OWNER8 + 0x18) == self.t + 4, 'real owner8 count')
                    need(self.int32(OWNER8 + 0x1C + 4 * (self.t + 3)) == ordinal, 'real owner8 ordinal array')
                    need(self.map_value(OWNER8 + 0xB020, ordinal) == self.t + 3, 'real owner8 ordinal map')
                    need(self.map_value(CONTEXT + 0xF22EC8, ordinal) == self.t, 'real outer ordinal map')
                need(self.read(CONTEXT + 0xF3F829, 1) == b'\0', 'dispatch in-progress flag left set')
                need(self.uc.reg_read(p.reg('rsp')) == p.RSP + 8, 'outer return stack')
                for n, value in p.SEEDS.items():
                    need(self.uc.reg_read(p.reg(n)) == value, 'outer nonvolatile ' + n)
                for i in range(6, 16):
                    need(self.uc.reg_read(p.reg('xmm' + str(i))) == (0x0102030405060708 + i) * (1 + (1 << 64)), 'outer nonvolatile XMM')
                phase2 = [e['role'] for e in self.events if e['role'].startswith('component_2_')]
                phase3 = [e['role'] for e in self.events if e['role'].startswith('component_3_')]
                need(phase2 == ['component_2_' + str(c) for c in self.components] and phase3 == ['component_3_' + str(c) for c in self.components], 'second/third dispatch order')
                phase1 = [e['role'] for e in self.events if e['role'].startswith('component_1_') or e['role'] in ('native_roster_insert', 'original_component33_insert','native_component33_insert')]
                expected = ['native_roster_insert' if c == 239 else ('native_component33_insert' if self.native33 else 'original_component33_insert') if c == 33 else 'component_1_' + str(c) for c in self.components]
                need(phase1 == expected and self.events[-1]['role'] == 'scope_exit', 'first dispatch or tail order')
                if self.literal8:
                    need(self.int32(S33 + 8) == 5, 'negative literal control did not reach fifth slot')
                    need(self.read(S33 + 0x1D8, 0x50) == bytes(0x50), 'fifth primary did not overwrite secondary')
                    need(self.int64(S33 + 0x90) == self.record, 'fifth pointer did not overwrite byte storage')
            return {'name': name, 'game_base': hex(self.game), 'initial_count': self.t,
                    'original_roster': self.original, 'native_component33':self.native33, 'native_component33_initialization':self.initialize33, 'component_list': self.components,
                    'negative_literal8_control': self.literal8, 'resource_type': self.resource_type,
                    'outcome': self.outcome, 'instructions': len(self.trace), 'roster_counts': self.counts(),
                    'resource_record_registered': True, 'resource_cursor_after': self.int32(CONTEXT + 0xF32F14),
                    'record_ordinal': self.int32(self.record + 0x10), 'invalid_access': self.invalid, 'events': self.events}

    runs = []
    for game in (p.GAME, p.GAME + 0x80000000):
        for count in range(9):
            runs.append(Fixture(count, game=game).execute('eight_roster_' + str(count)))
        for count in range(5):
            runs.append(Fixture(count, original=True, game=game).execute('original_roster_' + str(count)))
            runs.append(Fixture(count, components=True, game=game).execute('real_component33_' + str(count)))
        runs.append(Fixture(4, components=True, literal8=True, game=game).execute('negative_literal8_overwrites'))
        runs.append(Fixture(4, resource_type=0xFFFFFFFF, game=game).execute('missing_resource_type_keeps_insert'))
        if component_library:
            for count in range(9):runs.append(Fixture(count,components=True,native33=True,game=game).execute('native_component33_'+str(count)))
            for count in range(9):runs.append(Fixture(count,components=True,native33=True,initialize33=True,game=game).execute('native_component33_initialized_'+str(count)))
            runs.append(Fixture(7,components=True,native33=True,initialize33=True,resource_type=0xFFFFFFFF,game=game).execute('native_component33_initialized_missing_resource'))
    coverage = {}
    for name, f in lock['functions'].items():
        rows = list(p.decode(bytes.fromhex(f['body_hex']), f['start']))
        reached = [i.address for i in rows if i.address in visited]
        coverage[name] = {'reached': len(reached), 'total': len(rows), 'unreached_rvas': [hex(i.address) for i in rows if i.address not in visited]}
    return {'schema': 'hellforge_saved_player_creation_dispatch_validation_v1', 'passed': True,
            'lock_sha256': LOCK_SHA, 'source_sha256': {
                **lock['source_sha256'], 'tools/validate_creation_dispatch.py': sha(Path(__file__).read_bytes()),
                'native-creation-dispatch.lock.json': LOCK_SHA,
                **({name:sha((ROOT/'hellforge_multiplayer'/name).read_bytes()) for name in ('tools/component33_initialization_fixture.py','native-component33.lock.json')} if component_library else {})},
            'library_sha256': sha(Path(library.path).read_bytes()),
            'component33_library_sha256':sha(component_library.path.read_bytes()) if component_library else None,
            'component33_core_integration_runs':sum(r['native_component33'] and not r['native_component33_initialization'] for r in runs),
            'component33_initialization_integration_runs':sum(r['native_component33_initialization'] for r in runs),
            'artifacts': {Path(library.path).name: {'bytes': Path(library.path).stat().st_size, 'sha256': sha(Path(library.path).read_bytes())},
                **({component_library.path.name:{'bytes':component_library.path.stat().st_size,'sha256':sha(component_library.path.read_bytes())}} if component_library else {})},
            'reference_validation_sha256':{name:sha((ROOT/'hellforge_multiplayer/evidence'/name).read_bytes()) for name in ('native-component33-validation.json','native-component33-initialize-validation.json')} if component_library else {},
            'runs': runs, 'run_count': len(runs),
            'instruction_coverage': coverage, 'runtime_verified': False, 'game_access_performed': False,
            'remaining_capture_calls': 0, 'game_access': False, 'multiplayer_verified': False,
            'all_dispatcher_paths_verified': False, 'native_execution_of_game_bodies': False, 'limits': [
                'Only saved instructions and own C++ emitted roster bytes execute in Unicorn.',
                'Other component callbacks, resource/world APIs, transform and list setup are explicit hostile-volatile contract stubs.',
                'Reference player metadata is pinned; equivalence to installed assets and live component selection remains unverified.',
                'Only classified metadata and zero descriptor outputs are exercised; native property production and actual unit allocation are not executed.',
                'Component33 original dense insertion runs only with equal total/dense/prefix counts; its mover is not exercised.',
                'The literal8 run is a negative control confined to emulator RAM and demonstrates corrupting adjacent arrays.',
                'The resource type absent case returns with an inserted roster and ordinal 0x7fff; this is not successful character creation.',
                'Roster rejection does not roll back preceding dispatcher writes or unwind its callers.',
                'Optional C++ component33 dense/mover images run with synthetic sidecar and real map insertion; other component phases remain stubs. Full component33 lifecycle is not claimed.',
                'No creation scope, production binding, provider ABI implementation, gameplay or eight-player acceptance is claimed.'
            ]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--component33-library',type=Path)
    args = parser.parse_args()
    from native_component33_library import Library as ComponentLibrary
    result = validate(Library(args.library),ComponentLibrary(args.component33_library) if args.component33_library else None)
    args.out.write_bytes((json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps({'passed': True, 'runs': result['run_count'], 'component33_runs':result['component33_core_integration_runs'], 'coverage': {k: [v['reached'], v['total']] for k, v in result['instruction_coverage'].items()}, 'runtime_verified': False}))


if __name__ == '__main__':
    main()
