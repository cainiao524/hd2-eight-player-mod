"""Replay bounded entity and collision-query evidence from the pinned capture.

This is an offline research verifier, not a mod, candidate binding, or gameplay
test. It opens only the existing capture and writes optional derived JSON.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import capstone
from inspect_entity import load, read_large, fragments

CAPTURE_SHA = '5888cbfe7abe46965b752715414b550a8d09bed968c0c55109a22c30cdbeb4d8'
GAME_SHA = '2e2c3b7c2500646dadd5f2b4c6e0504dbb7e7896139f64cddc0d1813c718f51e'
EXPECTED = {
    0x616565:'8b4008', 0x616570:'8945f8',
    0x13aa4ea:'418b4618', 0x13aa4ee:'8984964cb00300',
    0x13ac5ff:'f30f114018',
    0x13ac4bd:'4a8b940a08a69307', 0x13ac4cf:'4c6bc02c', 0x13ac4d3:'e818c4ce00',
    0x13ac4f4:'48c1e207', 0x13ac4fc:'0fb74276',
    0x13ac542:'488b12', 0x13ac548:'4c6bc02c', 0x13ac55d:'e88ec3ce00',
    0x13ac65a:'42f78425e006000000008000', 0x13ac666:'428b9425dc060000',
    0x13ac66e:'0f85a4000000', 0x13ac67b:'e800d3c2ff',
    0x13ac68f:'433b9c874cb00300', 0x13ac697:'0f84c1070000',
    0x13ac6a1:'41f684473c20000020',
    0x13ace69:'48ffc0', 0x13ace76:'e9d5f7ffff',
    0x13abe24:'e8370c3b00', 0x13abe33:'89841948700e00',
    0x13ac197:'e8a4f93a00',
    0x175cb99:'48895c2e08', 0x175cba3:'894c2e38',
    0x175cbac:'c7442e4000000000',
    0x175c604:'837c3b4000', 0x175c615:'488b050c9dbc01',
    0x175c61c:'4c8b4c3b08', 0x175c626:'4c8b5868', 0x175c63c:'41ffd3',
    0x175c641:'488b05f09cbc01', 0x175c648:'4c8b8828010000',
    0x175c659:'41ffd1', 0x175c66b:'894c3b30',
    0x175bbe4:'488903', 0x175be23:'66897374',
    0x175b8d3:'488b054eaabc01', 0x175b8da:'4c8b9080000000',
    0x175b8e9:'488b03', 0x175b8ec:'4889442430',
    0x175b902:'41ffd2', 0x175b920:'66894b76',
    0x4edbcf:'b92bb8264c', 0x4edbd4:'ffd0', 0x4edbd6:'4889054b87e302',
    0x4edc0b:'b9997695f3', 0x4edc10:'ffd0', 0x4edc12:'4889051f87e302',
    0xfdc1c3:'49893e', 0xfdc257:'498bd6', 0xfdc25a:'e8c1505aff',
    0xfdc2b1:'e8ca545aff',
    0x581377:'498b07', 0x58138b:'4c8b99a02ef100',
    0x5813a3:'49c1e005', 0x58140a:'0fb70c48',
    0x58140e:'498b84cc10c1f000', 0x581421:'ffd0',
    0x55ae6c:'488d055dccfdff', 0x55ae73:'48898130c7f000',
    0x55ae96:'488d05d3cdfdff', 0x55ae9d:'48898170dbf000',
    0x581a37:'0fb70c48', 0x581a3b:'488b84cf50d5f000', 0x581a4e:'ffd0',
    0x537c76:'488b0d73f1de02', 0x537c7d:'e9ce931000',
    0x641143:'e8d835ecff', 0x641157:'4889442458',
    0x641d75:'488b442458', 0x641d7a:'80b8ad00000000',
    0x641d81:'0f8471010000', 0x641dfd:'e82e420000',
    0x6461b8:'66c745970100', 0x64623c:'4c8d442430',
    0x64624c:'0fb64114', 0x646259:'88459a', 0x64625c:'e8cf35d600',
}

# Stackless callback-table initializer and tail wrapper have no pdata entries.
# The initializer begins directly after INT3 padding at 0x556d8f.
LEAF_STARTS = {0x55ae6c:0x556d90,0x55ae73:0x556d90,
               0x55ae96:0x556d90,0x55ae9d:0x556d90,
               0x537c76:0x537c70,0x537c7d:0x537c70}
API_GAPS = (0x3326328,0x3326338,0x347bf98,0x3326df0)

def require(ok,message):
    if not ok: raise ValueError(message)

def replay(image,evidence,report, *, component_index=196, hit_flag_offset=0x20):
    require(evidence['capture_sha256']==CAPTURE_SHA,'source capture fingerprint mismatch')
    require(evidence['game_sha256']==GAME_SHA,'source game fingerprint mismatch')
    require(evidence['build_id']==25480438,'source build mismatch')
    require(component_index==196,'component index mismatch')
    require(hit_flag_offset==0x20,'hit result flag offset mismatch')
    require(0xf0c110+component_index*8==0xf0c730,'initial component binding mismatch')
    require(0xf0d550+component_index*8==0xf0db70,'second component binding mismatch')
    require(0x6e0-0x6c0==hit_flag_offset,'result-local field mismatch')
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
    pdata=fragments(image,report)
    decoded={}
    verified=[]
    for at,expected in sorted(EXPECTED.items()):
        b=bytes.fromhex(expected)
        require(image.read(at,len(b))==b,f'instruction mismatch at {at:#x}')
        fragment=next((x for x in pdata if x[0]<=at<x[1]),None)
        if fragment:
            start=fragment[0]
            end=fragment[1]
        else:
            require(at in LEAF_STARTS,f'no reviewed instruction boundary at {at:#x}')
            start=LEAF_STARTS[at]
            end=max(k+len(bytes.fromhex(v)) for k,v in EXPECTED.items()
                    if LEAF_STARTS.get(k)==start)
        key=(start,end)
        if key not in decoded:
            decoded[key]={i.address:i for i in md.disasm(read_large(image,start,end-start),start)}
        ins=decoded[key].get(at)
        require(ins is not None and bytes(ins.bytes)==b,f'instruction boundary mismatch at {at:#x}')
        verified.append({'rva':hex(at),'bytes':expected,'size':len(b),
                         'instruction':ins.mnemonic+' '+ins.op_str,
                         'sha256':hashlib.sha256(b).hexdigest(),
                         'linear_decode_start':hex(start),
                         'boundary_source':'captured_unwind' if fragment else 'reviewed_leaf_entry'})
    holes=[]
    for at in API_GAPS:
        available=any(x['rva']<=at and at+8<=x['rva']+x['size'] and x['kind']=='DATA'
                      for x in report['chunks'])
        require(not available,f'expected gap is now captured; re-review {at:#x}')
        holes.append({'rva':hex(at),'size':8,'captured':False})
    return {
        'schema':'entity-collision-continuation-20260927-v1',
        'source':{'build_id':25480438,'game_sha256':GAME_SHA,
                  'capture_sha256':CAPTURE_SHA,'files':evidence['fingerprints']},
        'verified_instruction_count':len(verified),'instructions':verified,
        'static_component196_initial_callback':'0x537ad0',
        'static_component196_second_callback':'0x537c70',
        'second_dispatch_call_rva':'0x581a4e',
        'hit_result_stride':44,'hit_flags_offset':32,'branch_mask':8388608,
        'query_api_provider_id':'0x4c26b82b',
        'query_api_slots':{'ordinary':104,'second_query':128},
        'uncaptured_pointer_slots':holes,
        'field_binding':None,'status':'UNBOUND',
        'runtime_dispatch_observed':False,'hit_flag_producer_resolved':False,
        'local_weapon_persistent_field_found':False,'common_solution_found':False,
        'gameplay_verified':False,'mod_zip_built':False,
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=replay(*load())
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(encoded,encoding='utf-8',newline='\n')
    print(json.dumps({'verified_instruction_count':result['verified_instruction_count'],
                      'status':result['status'],'common_solution_found':False,
                      'result_sha256':hashlib.sha256(encoded.encode()).hexdigest()}))
if __name__=='__main__':main()
