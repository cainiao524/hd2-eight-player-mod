"""Synthetic inputs for the saved component33 property/reset callbacks."""
import struct
import native_component33_image as n
import validate_component33_images as core
INPUT=0x18500500000;DESCRIPTORS=0x18500600000;ALLOC=0x18500700000
COUNT=DESCRIPTORS+0x900;LIST=DESCRIPTORS+0x920;COOKIE=0x763912BADC0FFE
TABLES=((0x32F6908,4,40),(0x32E50D8,5,40),(0x32EC0E8,4,40),(0x32EB4F8,3,32),(0x32E5BC8,2,32))
def addresses(kind,game=core.G):
    return {**core.addresses('mover',game),'code_address':game+0x10700000+n.INITIALIZE_KINDS.index(kind)*0x10000}
def values(mode):
    keys=[[0x10000*(j+1)+i+1 for i in range(count)] for j,(_,count,_) in enumerate(TABLES)]
    tables=[0,1,0,0,2,3,4,4,4,4]
    if mode=='zero':data=[0]*10
    elif mode=='known':data=[keys[t][-1] for t in tables]
    elif mode=='unknown':data=[0xBAD0CAFE]*10
    else:data=[0,keys[1][2],keys[0][1],0xBAD0CAFE,keys[2][3],keys[3][1],keys[4][0],0xBAD0CAFE,0,keys[4][1]]
    indices=[]
    for index,(v,t) in enumerate(zip(data,tables)):
        indices.append(0 if not v else keys[t].index(v) if v in keys[t] else 0 if index<5 else 0xFFFFFFFF)
    return keys,data+[0x87654321],[5,*indices[:5],1,indices[5],4,*indices[6:],0x87654321]
def seed_inputs(write,game,mode='mixed'):
    keys,data,result=values(mode);write(INPUT,bytes(0x1000));write(INPUT+0xB78,struct.pack('<11I',*data))
    write(game+0x347CDD8,core.u64(INPUT));write(game+0x3483C34,core.u32(0xFFFFFFFF));write(game+0x263C010,core.u64(COOKIE))
    for (rva,count,stride),rows in zip(TABLES,keys):
        write(game+rva,bytes(count*stride))
        for i,value in enumerate(rows):write(game+rva+i*stride,core.u32(value))
    return struct.pack('<14I',*result)

class Fixture(core.Fixture):
    def __init__(self,lib,kind,t,ordinal,*,original=False,game=core.G,mode='mixed',descriptor_count=0,callback=False,null_allocate=False):
        super().__init__(lib,'mover',t,t,t,original=original,game=game,ordinal=ordinal)
        self.kind=kind;self.artifact=lib.candidate(kind,**addresses(kind,game));f=n.profile()['functions'][kind]
        self.start=game+f['start'] if original else addresses(kind,game)['code_address']
        self.put(self.start,bytes.fromhex(f['body_hex']) if original else self.artifact['image'])
        self.expected_secondary=seed_inputs(self.put,game,mode);self.put(DESCRIPTORS-0x40,b'\xa9'*0xA40)
        self.put(COUNT,core.u32(descriptor_count));self.put(LIST,core.u64(LIST));self.put(ALLOC-0x40,b'\xab'*0xC0)
        self.descriptor_count=descriptor_count;self.events=[];self.null_allocate=null_allocate
        self.extra_writable=[(ALLOC,56),(DESCRIPTORS+16*descriptor_count,64),(COUNT,4)]
        self.helpers={game+0x173B8D0:'allocate',game+0x2088770:'cookie',game+0x208AAA0:'clear'}
        for address in self.helpers:self.put(address,b'\xc3')
        self.entry=self.start;self.helper_rsp=core.RSP
        self.uc.reg_write(core.reg('rcx'),core.S);self.uc.reg_write(core.reg('rdx'),core.E+ordinal*0x40)
        self.uc.reg_write(core.reg('r9'),DESCRIPTORS);self.put(core.RSP+40,core.u64(COUNT));self.put(core.RSP+48,core.u64(LIST))
        self.callback=callback
        if callback:
            w=n.profile()['initialization_callbacks'][kind];blob=bytearray.fromhex(w['body_hex'])
            at=0x19 if kind=='property' else 0xE;assert blob[at]==0xE8
            struct.pack_into('<i',blob,at+1,self.start-(game+w['entry']+at+5))
            self.entry=game+w['entry'];self.put(self.entry,bytes(blob));self.uc.reg_write(core.reg('rcx'),core.E+ordinal*0x40)
            if kind=='property':
                self.helper_rsp=core.RSP-64;self.uc.reg_write(core.reg('r8'),DESCRIPTORS);self.uc.reg_write(core.reg('r9'),COUNT);self.put(core.RSP+40,core.u64(LIST))
            else:
                self.helper_rsp=core.RSP-48
                for a,size in ((0x3797960,0x800),(0x3798180,0x20),(0x3797550,0x400),(0x348BA88,8)):
                    self.put(game+a,b'\x96'*size);self.extra_writable.append((game+a,size))
    def on_code(self,uc,pc,size,data):
        self.trace.append(pc)
        if pc in (self.stop,self.reject):self.outcome='return' if pc==self.stop else 'reject';uc.emu_stop();return
        if pc in self.helpers:
            role=self.helpers[pc];rsp=uc.reg_read(core.reg('rsp'));a={k:uc.reg_read(core.reg(k)) for k in ('rcx','rdx','r8')};result=0
            n.need(rsp%16==8,'initialization helper alignment')
            if role=='allocate':
                n.need(a==dict(rcx=LIST,rdx=56,r8=4),'property allocation ABI');result=0 if self.null_allocate else ALLOC
            elif role=='cookie':n.need(a['rcx']==COOKIE,'property stack cookie')
            else:
                n.need(a==dict(rcx=self.game+0x3797550,rdx=0,r8=0x400),'third callback clear ABI');self.put(a['rcx'],bytes(0x400));result=a['rcx']
            self.events.append(role);self.put(rsp+8,b'\xc7'*32)
            for i,key in enumerate(('rax','rcx','rdx','r8','r9','r10','r11')):uc.reg_write(core.reg(key),0xCDCD000000000000+i)
            for i in range(6):uc.reg_write(core.reg('xmm'+str(i)),(0x123456789ABC0000+i)*(1+(1<<64)))
            uc.reg_write(core.reg('rax'),result)
        if not self.original and self.start<=pc<self.start+self.artifact['code_bytes']:
            stack=bytearray(self.read(self.helper_rsp-128,256));struct.pack_into('<Q',stack,128,core.G+0x10500000)
            self.contexts.add(struct.pack('<IiI8Q',pc-self.start,uc.reg_read(core.reg('rsp'))-self.helper_rsp,0,*(uc.reg_read(core.reg(k)) for k in core.NAMES))+stack)
    def execute(self,expected='return'):
        # Direct helper refusals are stackless; a saved wrapper has already
        # allocated its own frame, so refusal-through-wrapper is tested separately.
        return super().execute(expected)
    def check_model(self):
        expected=dict(self.records)
        if self.kind=='property':
            expected['secondary',self.ordinal]=self.expected_secondary
            n.need(self.read(ALLOC,56)==self.expected_secondary,'property payload')
            n.need(self.int32(COUNT)==self.descriptor_count+4,'descriptor count')
            descriptors=b''.join(struct.pack('<IIQ',h,t,ALLOC+off) for h,t,off in ((0xDFE49C6F,10,0),(0x64E318CE,10,24),(0xAE5166E8,10,32),(0xAA7E1B9E,1,52)))
            n.need(self.read(DESCRIPTORS+self.descriptor_count*16,64)==descriptors,'descriptor records')
            n.need(self.events==['allocate','cookie'],'property helper order')
            n.need(self.read(DESCRIPTORS-0x40,0x40+self.descriptor_count*16)==b'\xa9'*(0x40+self.descriptor_count*16),'prior descriptors changed')
            end=16*(self.descriptor_count+4);n.need(self.read(DESCRIPTORS+end,0x800-end)==b'\xa9'*(0x800-end),'descriptor trailing data changed')
        else:
            expected['primary',self.ordinal]=b'\xff'*44+expected['primary',self.ordinal][44:]
            n.need(self.events==(['clear'] if self.callback else []),'reset helper order')
            if self.callback:
                n.need(self.read(self.game+0x3797960,0x800)==bytes(0x800),'callback global map clear')
                n.need(self.read(self.game+0x3797550,0x400)==bytes(0x400),'callback secondary clear')
                n.need(self.read(self.game+0x348BA88,8)==bytes(8),'callback global reset')
                n.need(self.read(self.game+0x3798180,28)==core.u64(self.game+0x3797960)+core.u32(128)+b'\x96'*4+core.u64(0)+core.u32(2),'callback map header')
        n.need([self.int32(core.S+off) for off in (4,8,12,16)]==[2,self.t,self.d,self.p],'initialization changed counts')
        for (name,i),value in expected.items():n.need(self.read(self.slot(name,i),len(value))==value,'initializer array mismatch '+str((self.kind,self.t,self.ordinal,name,i)))
        n.need(self.read(core.S+0x14,64)==b''.join(core.u32(k)+core.u32(v) for k,v in self.table),'initialization changed map')
        if not self.original:n.need(self.read(core.S+0x70,0x248)==b'\xa5'*0x248,'initializer wrote old arrays')
        n.need(self.read(core.B-0x80,0x80)==b'\xb6'*0x80 and self.read(core.B+0x490,0x80)==b'\xb6'*0x80,'initializer storage canary')
        n.need(self.read(ALLOC-0x40,0x40)==b'\xab'*0x40 and self.read(ALLOC+56,0x40)==b'\xab'*0x40,'allocator canary')
