"""Reproduce the additional captured indirect-dispatch registration edge."""
import argparse,json,struct
from pathlib import Path
from inspect_capture import Image,row,require,sha
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--output',required=True);a=p.parse_args();im=Image(a.evidence)
    code=next(r for r in im.report['ranges'] if r['label']=='code');b=im.read(code['rva'],code['size']);out=[]
    for pos in range(len(b)-7):
        skip=1 if 0x40<=b[pos]<=0x4f else 0
        if b[pos+skip] in (0x8d,0x8b,0x89,0xff) and b[pos+skip+1]&0xc7==0x05:
            size=6+skip;rva=code['rva']+pos;target=rva+size+struct.unpack_from('<i',b,pos+skip+2)[0]
            if 0x214c000<=target<0x214d600:
                ins=im.instruction(rva)
                if ins:out.append(dict(row(ins),target=hex(target),root=[hex(n) for n in im.root(rva)]))
    path=Path(a.output);require(not path.exists(),'refusing overwrite');path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
