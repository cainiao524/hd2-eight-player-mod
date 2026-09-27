"""Local-only bounded static xrefs of the existing, pinned HD2 code capture."""
import argparse, bisect, hashlib, json, struct
from pathlib import Path
import capstone

EXPECTED = {
    'capture-report.json':'132c49c2189e311f366a3a2f0ed3e67051ca4b30a4543420e49c53632671ffd5',
    'captured-data.bin':'31b014a13f219a8e25843c5acb7e4b73db44fccca5c952fbf93d77694e3b625d',
}
def require(ok, text):
    if not ok: raise ValueError(text)
def sha(b): return hashlib.sha256(b).hexdigest()
class Image:
    def __init__(self, directory):
        self.files = {}
        for name, digest in EXPECTED.items():
            content = (Path(directory)/name).read_bytes()
            require(sha(content)==digest, 'fingerprint mismatch: '+name)
            self.files[name]=content
        self.report=json.loads(self.files['capture-report.json'])
        require(self.report['capture_sha256']=='5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8','capture identity mismatch')
        self.raw=self.files['captured-data.bin']
        self.chunks=self.report['chunks']
        self.starts=[x['rva'] for x in self.chunks]
        self.base=int(self.report['base_address'],0)
        self.md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
        self.md.detail=True
        nt=struct.unpack_from('<I',self.read(0,0x100),0x3c)[0]
        self.header_exception_rva,self.header_exception_size=struct.unpack_from('<II',self.read(nt,0x110),24+112+3*8)
        # Loaded PE directory points outside this bounded capture. Use the separately
        # captured, labelled unwind table; disclose both locations in results.
        unwind=next(x for x in self.report['ranges'] if x['label']=='unwind')
        self.exception_rva,self.exception_size=unwind['rva'],unwind['size']
        self.functions=list(struct.iter_unpack('<III',self.read(self.exception_rva,self.exception_size)))
        require(all(a<b and 0x1000<=a<b<=0x2110a93 for a,b,_ in self.functions),'invalid captured unwind entries')
        require(all(x[0]<y[0] for x,y in zip(self.functions,self.functions[1:])),'unsorted captured unwind entries')
        self.fn_starts=[f[0] for f in self.functions]
    def read(self, rva, size):
        out=bytearray()
        while size:
            i=bisect.bisect_right(self.starts,rva)-1
            require(i>=0,'unmapped RVA')
            row=self.chunks[i]
            require(row['kind']=='DATA' and row['rva']<=rva<row['rva']+row['size'],'uncaptured RVA '+hex(rva))
            n=min(size,row['rva']+row['size']-rva)
            at=row['file_offset']+rva-row['rva']
            out+=self.raw[at:at+n]; rva+=n; size-=n
        return bytes(out)
    def containing(self,rva):
        i=bisect.bisect_right(self.fn_starts,rva)-1
        return self.functions[i] if i>=0 and self.functions[i][0]<=rva<self.functions[i][1] else None
    def root(self,rva):
        fn=self.containing(rva)
        require(fn is not None,'no captured unwind fragment')
        seen=set()
        while True:
            require(fn not in seen,'cyclic unwind chain');seen.add(fn)
            h=self.read(fn[2],4)
            if not (h[0]>>3)&4:return fn
            off=4+((h[2]+1)&~1)*2
            fn=struct.unpack('<III',self.read(fn[2]+off,12))
    def instruction(self,rva):
        fn=self.containing(rva)
        if fn is None: return None
        # Validate boundaries from the exception-table fragment, never by decoding a random byte.
        for ins in self.md.disasm(self.read(fn[0],fn[1]-fn[0]),fn[0]):
            if ins.address==rva: return ins
            if ins.address>rva: return None
        return None
def row(ins):
    return {'rva':hex(ins.address),'bytes':ins.bytes.hex(),'sha256':sha(ins.bytes),'asm':ins.mnemonic+' '+ins.op_str}
def scan(im,targets):
    results={hex(t):{'branches':[],'rip_references':[],'absolute_pointers':[],'rva_literals':[]} for t in targets}
    code=next(x for x in im.report['ranges'] if x['label']=='code')
    b=im.read(code['rva'],code['size'])
    for pos in range(len(b)-7):
        rva=code['rva']+pos
        if b[pos] in (0xe8,0xe9):
            target=rva+5+struct.unpack_from('<i',b,pos+1)[0]
            if target in targets:
                ins=im.instruction(rva)
                if ins and ins.mnemonic in ('call','jmp'):
                    out=row(ins);out['fragment']=[hex(x) for x in im.containing(rva)];out['root']=[hex(x) for x in im.root(rva)]
                    results[hex(target)]['branches'].append(out)
        # RIP-relative LEA/MOV with or without REX. Candidate bytes then boundary validation.
        skip=1 if 0x40<=b[pos]<=0x4f else 0
        if b[pos+skip] in (0x8d,0x8b,0x89) and b[pos+skip+1]&0xc7==0x05:
            size=6+skip
            target=rva+size+struct.unpack_from('<i',b,pos+skip+2)[0]
            if target in targets:
                ins=im.instruction(rva)
                if ins:
                    out=row(ins);out['fragment']=[hex(x) for x in im.containing(rva)];out['root']=[hex(x) for x in im.root(rva)]
                    results[hex(target)]['rip_references'].append(out)
    for area in im.report['ranges']:
        data=im.read(area['rva'],area['size'])
        for t in targets:
            for kind,pattern in [('absolute_pointers',struct.pack('<Q',im.base+t)),('rva_literals',struct.pack('<I',t))]:
                start=0
                while True:
                    pos=data.find(pattern,start)
                    if pos<0:break
                    results[hex(t)][kind].append({'rva':hex(area['rva']+pos),'range':area['label'],'bytes':pattern.hex(),'aligned':(area['rva']+pos)%len(pattern)==0})
                    start=pos+1
    return {'capture_sha256':im.report['capture_sha256'],'source_sha256':EXPECTED,'code_range':code,'captured_unwind_table':{'rva':hex(im.exception_rva),'size':im.exception_size,'fragments':len(im.functions)},'header_exception_directory_uncaptured':{'rva':hex(im.header_exception_rva),'size':im.header_exception_size},'targets':results,'limits':['No heap or writable-data capture.','RIP reference scan recognizes REX/non-REX MOV/LEA with disp32; it does not solve arbitrary address arithmetic.','Exception-table boundary validation omits leaf or uncovered code.','Pointer/RVA literal matches alone are data occurrences, not execution edges.','No gameplay, ownership, or lifecycle inference.']}
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--output',required=True)
    p.add_argument('--target',action='append',type=lambda s:int(s,0));p.add_argument('--dump',nargs=2,type=lambda s:int(s,0));p.add_argument('--function',type=lambda s:int(s,0));a=p.parse_args()
    im=Image(a.evidence)
    if a.dump or a.function:
        if a.function:
            fn=im.containing(a.function);require(fn is not None,'no unwind fragment');start,end,_=fn
        else:start,size=a.dump;end=start+size
        out={'range':[hex(start),hex(end)],'sha256':sha(im.read(start,end-start)),'instructions':[row(x) for x in im.md.disasm(im.read(start,end-start),start)]}
    else:out=scan(im,set(a.target or [0x13a9830]))
    path=Path(a.output);require(not path.exists(),'refusing overwrite');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(str(path))
if __name__=='__main__':main()
