"""Evidence-verifier checks. These are not candidate lifecycle/gameplay tests."""
import copy
import unittest
from inspect_entity import load
from replay_entity import replay, EXPECTED

class MutatedImage:
    def __init__(self,image,at): self.image,self.at=image,at
    def read(self,at,size):
        b=bytearray(self.image.read(at,size))
        if at<=self.at<at+size: b[self.at-at]^=1
        return bytes(b)

class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.image,cls.evidence,cls.report=load()

    def test_exact_evidence_replays(self):
        result=replay(self.image,self.evidence,self.report)
        self.assertEqual(result['verified_instruction_count'],81)
        self.assertEqual(len(result['instructions']),len(EXPECTED))
        self.assertEqual(result['status'],'UNBOUND')
        self.assertIsNone(result['field_binding'])
        self.assertFalse(result['common_solution_found'])
        self.assertFalse(result['mod_zip_built'])
        self.assertFalse(result['runtime_dispatch_observed'])

    def test_source_faults_are_rejected(self):
        for key,bad in [('capture_sha256','0'*64),('game_sha256','0'*64),('build_id',25480439)]:
            with self.subTest(key=key):
                evidence=copy.deepcopy(self.evidence);evidence[key]=bad
                with self.assertRaisesRegex(ValueError,'source'):
                    replay(self.image,evidence,self.report)

    def test_instruction_faults_are_rejected(self):
        for at in (0x13ac65a,0x13ac68f,0x13ac697,0x55ae73,0x55ae9d,
                   0x581a3b,0x175c626,0x175b8da,0x6461b8):
            with self.subTest(rva=hex(at)):
                with self.assertRaisesRegex(ValueError,'instruction|boundary'):
                    replay(MutatedImage(self.image,at),self.evidence,self.report)

    def test_wrong_component_phase_index_rejected(self):
        with self.assertRaisesRegex(ValueError,'component index'):
            replay(self.image,self.evidence,self.report,component_index=195)

    def test_wrong_hit_field_rejected(self):
        with self.assertRaisesRegex(ValueError,'flag offset'):
            replay(self.image,self.evidence,self.report,hit_flag_offset=0x18)

    def test_captured_api_claim_requires_re_review(self):
        report=copy.deepcopy(self.report)
        report['chunks'].append({'rva':0x3326328,'size':8,'kind':'DATA'})
        with self.assertRaisesRegex(ValueError,'expected gap is now captured'):
            replay(self.image,self.evidence,report)

if __name__=='__main__': unittest.main(verbosity=2)
