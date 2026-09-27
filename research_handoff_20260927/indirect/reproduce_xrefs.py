"""Reproduce constructor, two caller levels, manager and byte-displacement evidence.

Output is local evidence only, never a Mod profile or captured binary copy.
"""
import argparse,json
from pathlib import Path
from capstone.x86_const import X86_OP_MEM
from inspect_capture import Image,scan,row,require

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output);require(not out.exists(),'refusing overwrite');out.mkdir(parents=True)
    im=Image(a.evidence)
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    ctor=scan(im,{0x13a9830,0x33266d8});save('constructor-and-manager.json',ctor)
    roots={im.root(int(x['rva'],0))[0] for x in ctor['targets']['0x13a9830']['branches']}
    level1=scan(im,roots);save('caller-roots.json',level1)
    parents={im.root(int(x['rva'],0))[0] for v in level1['targets'].values() for x in v['branches']}
    level2=scan(im,parents);save('caller-parents.json',level2)
    code=next(r for r in im.report['ranges'] if r['label']=='code');b=im.read(code['rva'],code['size'])
    matches=[];start=0
    while True:
        pos=b.find(bytes.fromhex('94300000'),start)
        if pos<0:break
        address=code['rva']+pos;fn=im.containing(address)
        if fn:
            for ins in im.md.disasm(im.read(fn[0],fn[1]-fn[0]),fn[0]):
                if ins.address<=address<ins.address+ins.size:
                    matches.append(dict(row(ins),root=hex(im.root(ins.address)[0]),memory_displacement_match=any(o.type==X86_OP_MEM and o.mem.disp==0x3094 for o in ins.operands)))
                    break
        start=pos+1
    save('displacement-3094.json',matches)
    print(json.dumps({'caller_roots':len(roots),'parent_roots':len(parents),'manager_references':len(ctor['targets']['0x33266d8']['rip_references']),'displacement_matches':len(matches)},indent=2))
if __name__=='__main__':main()
