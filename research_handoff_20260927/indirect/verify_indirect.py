"""Independent byte pins and failure probes for the bounded indirect-path study.

This is an evidence verifier, not a Mod profile or runtime implementation.
"""
import argparse,copy,json,struct,tempfile,unittest
from pathlib import Path
from inspect_capture import Image,scan,require,sha

PINS={
    0xbb99f9:'e812d5fcff',
    0xb87102:'c744244801000100',
    0xb8718e:'4c8d442430',
    0xb871a7:'f6411401',
    0xb871ba:'8844244b',
    0xb871be:'e86d268200',
    0x13a9df0:'41385d1b',
    0x13a9dfc:'4188843794300000',
    0x13a8741:'c744993cffffffff',
    0x13a8794:'4380bc3c9430000000',
    0x13a87b5:'e8d6830000',
    0x13a87ba:'6645098c5f3c200000',
    0x13a87c8:'43c7843c743000009a99993e',
    0x13a87d7:'664121845f3c200000',
    0x13b0b9d:'6642838c413c20000001',
    0x13b0bb9:'f30f118c0874300000',
}
CALLS={0x5f5e3d,0x616612,0x64625c,0x681816,0x681835,0x6cb742,0x852e14,0x8a4d83,0x8a57eb,0xb871be,0x12a9e80,0x13a9796,0x13c2314}

def verify_pins(im,pins=PINS,pointer_rva=0x214d040):
    for rva,hexbytes in pins.items():
        require(im.read(rva,len(bytes.fromhex(hexbytes)))==bytes.fromhex(hexbytes),'instruction mismatch '+hex(rva))
    require(struct.unpack('<Q',im.read(pointer_rva,8))[0]==im.base+0xbb9950,'pointer mismatch')
    # Both readonly constructor literals are chained RUNTIME_FUNCTION entries.
    for unwind,at in [(0x25112a4,0x25112b4),(0x2511364,0x2511368)]:
        header=im.read(unwind,4);require((header[0]>>3)&4,'not CHAININFO')
        require(unwind+4+((header[2]+1)&~1)*2==at,'wrong unwind literal offset')
        require(struct.unpack('<III',im.read(at,12))==(0x13a9830,0x13a986d,0x251128c),'wrong chained function')
    return {hex(rva):{'bytes':hexbytes,'sha256':sha(bytes.fromhex(hexbytes))} for rva,hexbytes in pins.items()}

def verify_arithmetic(mask=0x7fff):
    require(all((((f|1|0x4000)&mask)&0x20)==(f&0x20) for f in range(65536)),'cleanup operations change source exclusion bit')

class Tests(unittest.TestCase):
    evidence=None
    @classmethod
    def setUpClass(cls): cls.im=Image(cls.evidence)
    def test_pinned_instruction_and_pointer_edges(self):verify_pins(self.im)
    def test_flag_preservation_all_65536_inputs(self):verify_arithmetic()
    def test_instruction_fault_rejected(self):
        pins=copy.deepcopy(PINS);pins[0x13a9df0]='41385d18'
        with self.assertRaisesRegex(ValueError,'instruction mismatch'):verify_pins(self.im,pins)
    def test_pointer_location_fault_rejected(self):
        with self.assertRaisesRegex(ValueError,'pointer mismatch'):verify_pins(self.im,pointer_rva=0x214d048)
    def test_arithmetic_fault_rejected(self):
        with self.assertRaisesRegex(ValueError,'change source'):verify_arithmetic(mask=0x7fdf)
    def test_source_fault_rejected_before_payload_read(self):
        with tempfile.TemporaryDirectory() as d:
            report=json.loads(self.im.files['capture-report.json']);report['build_id']=0
            (Path(d)/'capture-report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):Image(d)
    def test_constructor_scan_and_unwind_boundaries(self):
        result=scan(self.im,{0x13a9830})['targets']['0x13a9830']
        self.assertEqual({int(r['rva'],0) for r in result['branches']},CALLS)
        self.assertEqual(result['rip_references'],[])
        self.assertEqual(result['absolute_pointers'],[])
        self.assertEqual({r['rva'] for r in result['rva_literals']},{'0x25112b4','0x2511368','0x389f890'})
        self.assertIsNone(self.im.instruction(0x13a9df1))
        self.assertEqual(self.im.root(0xb871be)[0],0xb86f10)

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True);p.add_argument('--pins-output');p.add_argument('--inject-instruction-fault',action='store_true');a=p.parse_args()
    if a.inject_instruction_fault:PINS[0x13a9df0]='41385d18'
    if a.pins_output:
        out=Path(a.pins_output);require(not out.exists(),'refusing overwrite')
        im=Image(a.evidence);pins=verify_pins(im);verify_arithmetic();out.write_text(json.dumps({'capture_sha256':im.report['capture_sha256'],'source_sha256':{k:sha(v) for k,v in im.files.items()},'instruction_pins':pins,'pointer':{'rva':'0x214d040','bytes':im.read(0x214d040,8).hex(),'target_rva':'0xbb9950','consumer_unresolved':True},'cleanup_preserves_bit20_for_all_65536_inputs':True,'candidate_found':False,'runtime_verified':False},indent=2)+'\n')
    Tests.evidence=a.evidence
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
if __name__=='__main__':main()
