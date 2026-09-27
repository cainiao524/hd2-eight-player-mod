"""Finite integration checks for the offline producer/receiver byte builder."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT.parent/'five_player_feasibility_20260927'
PATH=ROOT/'Native/roster_property_pair.py'
spec=importlib.util.spec_from_file_location('pair_under_test',PATH)
pair=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pair)
P=pair.producer.load_source(RESEARCH/'roster_property_producer_native_evidence.json')
R=pair.receiver.load_source(RESEARCH/'roster_property_receive_evidence.json')
BASE=0x7FF800000000
PARAMETERS=dict(game_base=BASE,roster_address=0x20000000,property_address=0x30000000,
                producer_code_address=BASE+0x5000000,receiver_code_address=BASE+0x5001000,
                producer_reject_address=BASE+0x5010000,receiver_reject_address=BASE+0x5011000)


def build(**changes):
    args=dict(PARAMETERS); args.update(changes)
    return pair.build(P,R,**args)


class PairTests(unittest.TestCase):
    def test_01_shared_binding_and_exact_individual_outputs(self):
        a=build()
        for name in ('producer','receiver'):
            child=a[name]
            self.assertEqual(child['roster_address'],a['shared_binding']['roster_address'])
            self.assertEqual(child['property_address'],a['shared_binding']['property_address'])
            self.assertEqual(child['property_size_bytes'],0x100)
            self.assertEqual(child['target_profile'],a['target_profile'])
        common=dict(a['shared_binding'])
        self.assertEqual(a['producer'],pair.producer.build(P,**common,code_address=PARAMETERS['producer_code_address'],reject_address=PARAMETERS['producer_reject_address']))
        self.assertEqual(a['receiver'],pair.receiver.build(R,**common,code_address=PARAMETERS['receiver_code_address'],reject_address=PARAMETERS['receiver_reject_address']))
        for key in ('installable','game_execution','multiplayer_verified'): self.assertIs(a[key],False)

    def test_02_cross_code_and_reject_overlap(self):
        cases=[dict(receiver_code_address=PARAMETERS['producer_code_address']+16),
               dict(producer_reject_address=PARAMETERS['receiver_code_address']+300),
               dict(receiver_reject_address=PARAMETERS['producer_code_address']+600),
               dict(receiver_reject_address=PARAMETERS['producer_reject_address'])]
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(ValueError): build(**changes)
        # Nearest following aligned code leaves 10 padding bytes; it is disjoint.
        a=build(receiver_code_address=PARAMETERS['producer_code_address']+0x2A0)
        self.assertEqual(a['producer']['size_bytes'],662)

    def test_03_cross_original_and_transitive_global_overlap(self):
        for changes in [dict(producer_code_address=BASE+0x60C890),
                        dict(receiver_code_address=BASE+0x60C640),
                        dict(property_address=BASE+0x347CEF0),
                        dict(receiver_reject_address=BASE+0x3326468)]:
            with self.subTest(changes=changes),self.assertRaises(ValueError): build(**changes)

    def test_04_individual_source_and_address_checks_remain_required(self):
        for p,r in ((P[:-1],R),(P,R[:-1])):
            with self.assertRaises(ValueError): pair.build(p,r,**PARAMETERS)
        for changes in (dict(roster_address=1),dict(property_address=0),dict(receiver_code_address=1<<47)):
            with self.assertRaises(ValueError): build(**changes)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PairTests))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    value={'status':'passed' if result.wasSuccessful() else 'failed','test_methods_run':result.testsRun,
           'failure_count':len(result.failures),'error_count':len(result.errors),
           'failures':[{'test':str(t),'traceback':s} for t,s in result.failures],
           'errors':[{'test':str(t),'traceback':s} for t,s in result.errors],
           'source_sha256':{f'Native/{n}.py':sha(ROOT/f'Native/{n}.py') for n in ('roster_property_pair','roster_producer','roster_receiver')},
           'test_sha256':sha(Path(__file__)),
           'evidence_sha256':{str(p.relative_to(ROOT.parent)):sha(p) for p in [RESEARCH/'roster_property_producer_native_evidence.json',RESEARCH/'roster_property_receive_evidence.json']},
           'game_process_accessed':False,'game_execution':False,'multiplayer_verified':False,'installable':False,
           'scope':'Pure-byte composition, shared binding and finite cross-region collision checks; no new instruction execution, allocation or live proof.'}
    out=ROOT/'verification/native_roster_pair_tests.json'
    out.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':value['status'],'tests':result.testsRun,'report':str(out)}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
