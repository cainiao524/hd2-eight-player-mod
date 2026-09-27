"""Pin only the saved FD9D40 body and 23C6D70 literal for departure tests."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'eight_player_candidate_20260927/.native-test-deps'),str(ROOT/'research_handoff_20260927/indirect')]
from inspect_capture import Image
sha=lambda b:hashlib.sha256(b).hexdigest()
BODY_SHA='27627b0418666a4ce50917587d9dd779c3736a8af2272a3a3c955f94cb3701ed'

def build(capture:Path):
    im=Image(capture)
    body=im.read(0xFD9D40,0xB2);literal=im.read(0x23C6D70,4)
    assert sha(body)==BODY_SHA and literal==bytes.fromhex('0000803f')
    return dict(schema='roster_departure_aux_v1',
                capture_identity_sha256=im.report['capture_sha256'],
                capture_report_sha256=sha((capture/'capture-report.json').read_bytes()),
                captured_data_sha256=sha((capture/'captured-data.bin').read_bytes()),
                replay_sha256=sha(Path(__file__).read_bytes()),
                bodies={'0xfd9d40':dict(start='0xfd9d40',end_exclusive='0xfd9df2',size_bytes=len(body),sha256=sha(body),bytes_hex=body.hex())},
                literals={'0x23c6d70':dict(size_bytes=4,sha256=sha(literal),bytes_hex=literal.hex())},
                limits=['Only saved capture code and readonly data; no process access or new capture','Not runtime assets, manager state, resource success or callback noninterference proof'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();assert not a.output.exists(),'refusing to overwrite output'
    result=build(a.capture);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),body_sha256=result['bodies']['0xfd9d40']['sha256'],literal=result['literals']['0x23c6d70']['bytes_hex'])))

if __name__=='__main__':main()
