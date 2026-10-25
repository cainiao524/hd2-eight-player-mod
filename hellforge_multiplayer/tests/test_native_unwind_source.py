"""Reject handler/chaining changes before emitting a handler-free clone."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_unwind_source as source


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.data = source.load_bytes(source.SNAPSHOT.read_bytes())

    def fragment(self, name='receiver', index=0):
        return self.data['functions'][name]['fragments'][index]

    def test_saved_source(self):
        facts = source.audit(self.data)
        self.assertEqual(facts['producer']['flags'], [0])
        self.assertEqual(facts['receiver']['flags'], [0, 4, 4, 4])

    def test_exception_and_termination_handlers_refused(self):
        for flag in (1, 2, 3, 5, 6):
            data = copy.deepcopy(self.data)
            fragment = data['functions']['producer']['fragments'][0]
            raw = bytearray.fromhex(fragment['unwind_hex']); raw[0] = 1 | flag << 3
            fragment['unwind_hex'] = raw.hex()
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'language handler'):
                source.audit(data)

    def test_cycle_refused(self):
        f = self.fragment(index=1)
        f['unwind_hex'] = f['unwind_hex'][:-24] + f['runtime_function_hex']
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            source.audit(self.data)

    def test_missing_chain_refused(self):
        f = self.fragment(index=1)
        f['unwind_hex'] = f['unwind_hex'][:-8] + 'ffffffff'
        with self.assertRaisesRegex(ValueError, 'Uncaptured chained'):
            source.audit(self.data)

    def test_missing_fragment_refused(self):
        self.data['functions']['receiver']['fragments'].pop(1)
        with self.assertRaisesRegex(ValueError, 'Noncontiguous'):
            source.audit(self.data)

    def test_truncation_refused(self):
        f = self.fragment(); f['unwind_hex'] = f['unwind_hex'][:-4]
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            source.audit(self.data)

    def test_unknown_version_refused(self):
        f = self.fragment(); f['unwind_hex'] = '02' + f['unwind_hex'][2:]
        with self.assertRaisesRegex(ValueError, 'version'):
            source.audit(self.data)

    def test_snapshot_fingerprint_refused(self):
        with self.assertRaisesRegex(ValueError, 'Changed original'):
            source.load_bytes(source.SNAPSHOT.read_bytes() + b' ')

    def test_candidate_source_binding(self):
        f = self.data['functions']['receiver']
        c = {'target_profile': {'build': 25480438}, 'source_sha256': f['code_sha256'],
             'evidence_sha256': f['evidence_sha256']}
        self.assertEqual(source.verify_candidate('receiver', c)['captured_fragments'], 4)
        c['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'does not match'):
            source.verify_candidate('receiver', c)

    def test_both_emitters_refuse_unbound_source_before_emission(self):
        import native_producer_unwind
        import native_receiver_unwind
        for name, module in (('producer', native_producer_unwind), ('receiver', native_receiver_unwind)):
            f = self.data['functions'][name]
            candidate = {'target_profile': {'build': 25480438}, 'source_sha256': '0' * 64,
                         'evidence_sha256': f['evidence_sha256']}
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'does not match'):
                module.with_unwind(candidate)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceTests)
    result = unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print(json.dumps({'passed': True, 'tests': result.testsRun}))
