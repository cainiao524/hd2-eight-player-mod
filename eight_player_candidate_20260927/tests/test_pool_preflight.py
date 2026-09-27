"""Execute the actual candidate Lua module in a separate LuaJIT 2.1 runtime.

Only synthetic snapshots and pinned offline evidence are used. No game process,
Windows API, loader callback, native game function, or mod installation is used.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.test-deps'))
from lupa.luajit21 import LuaRuntime
import lupa

SOURCE = ROOT / 'Source' / 'pool_preflight.lua'
EVIDENCE = ROOT.parent / 'five_player_feasibility_20260927' / 'indexed_float_pool_triple_members_evidence_v3.json'
EVIDENCE_SHA = '7a5b7ef002c671d698edd6c663b791a7306eda2b09a238b5d8f187393c04bd60'


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = EVIDENCE.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == EVIDENCE_SHA
        cls.evidence = json.loads(raw)
        cls.counts = {int(k, 16): v['nodes'] for k, v in cls.evidence['template_emissions'].items()}
        cls.counts[0x1B] = 1

    def setUp(self):
        self.rt = LuaRuntime(unpack_returned_tuples=True)
        self.module = self.rt.execute(SOURCE.read_text())

    def lua(self, v):
        if isinstance(v, dict):
            return self.rt.table_from({k: self.lua(x) for k, x in v.items()})
        if isinstance(v, list):
            return self.rt.table_from([self.lua(x) for x in v])
        return v

    def snapshot(self, capacity=6, reverse=False, other=0):
        ids = [0x28, 0x1C, 0x2E] if reverse else [0x24, 0x1B, 0x2D]
        return dict(version=dict(self.module.target().items()), capacity=capacity, used=5+other,
            owners=[dict(key=k, requested_id=i, allocated=self.counts[i]) for k, i in zip(('main','second','third'), ids)])

    def ops(self, reverse=False):
        pairs = [('main',0x24),('third',0x2D),('second',0x1B),('third',0x2D),('main',0x24)] if reverse else [
            ('second',0x1C),('third',0x2E),('main',0x28)]
        return [dict(owner=k, template_id=t) for k,t in pairs]

    def plan(self, snapshot, operations, counts=None):
        return self.module.plan(self.lua(snapshot), self.lua(self.counts if counts is None else counts), self.lua(operations))

    def test_01_both_verified_transition_orders_need_six(self):
        for reverse, first_shortage in ((False,2),(True,1)):
            with self.subTest(reverse=reverse):
                short = self.plan(self.snapshot(5,reverse),self.ops(reverse))
                self.assertEqual(short['status'],'insufficient_capacity')
                self.assertEqual(short['peak_required'],6)
                self.assertEqual(short['final_used'],5)
                self.assertEqual(short['first_shortage_step'],first_shortage)
                self.assertEqual(short['additional_capacity_required'],1)
                fits = self.plan(self.snapshot(6,reverse),self.ops(reverse))
                self.assertEqual(fits['status'],'fits')
                self.assertFalse(fits['executable'])

    def test_02_other_pool_owners_are_not_forgotten(self):
        r = self.plan(self.snapshot(256,other=251),self.ops())
        self.assertEqual((r['status'],r['peak_required'],r['unlisted_owner_nodes']),('insufficient_capacity',257,251))

    def test_03_same_id_partial_is_not_reported_as_fixed(self):
        s=self.snapshot();s['owners'][0]['allocated']=2;s['used']=4
        r=self.plan(s,[dict(owner='main',template_id=0x24)])
        self.assertEqual(r['status'],'partial_same_id_requires_recovery')
        # Changing the ID can release the actual two nodes, not an assumed three.
        r=self.plan(s,[dict(owner='main',template_id=0x28)])
        self.assertEqual((r['status'],r['steps'][1]['released'],r['final_used']),('fits',2,4))

    def test_04_version_fields_each_reject_mismatch(self):
        for key in ('build','exe_sha256','game_dll_sha256'):
            s=self.snapshot();s['version'][key]='wrong'
            r=self.plan(s,self.ops());self.assertEqual((r['status'],r['field']),('version_mismatch',key))

    def test_05_invalid_counts_ownership_and_aliases_rejected(self):
        cases=[]
        s=self.snapshot();s['capacity']=0;cases.append((s,'invalid_input'))
        s=self.snapshot();s['used']=7;cases.append((s,'invalid_input'))
        s=self.snapshot();s['used']=4;cases.append((s,'inconsistent_ownership'))
        s=self.snapshot();s['owners'][0]['key']='second';cases.append((s,'duplicate_owner'))
        s=self.snapshot();s['owners'][0]['requested_id']=0;cases.append((s,'inconsistent_ownership'))
        s=self.snapshot();s['owners'][0]['allocated']=4;s['used']=6;cases.append((s,'inconsistent_ownership'))
        for s,status in cases:
            with self.subTest(status=status,s=s):self.assertEqual(self.plan(s,self.ops())['status'],status)

    def test_06_unknown_inputs_do_not_become_zero_cost(self):
        r=self.plan(self.snapshot(),[dict(owner='missing',template_id=0x28)])
        self.assertEqual(r['status'],'unknown_owner')
        r=self.plan(self.snapshot(),[dict(owner='main',template_id=0)])
        self.assertEqual(r['status'],'unknown_template')
        bad=dict(self.counts);bad[0x28]=13
        self.assertEqual(self.plan(self.snapshot(),self.ops(),bad)['status'],'invalid_input')
        bad=dict(self.counts);bad[0]=1
        self.assertEqual(self.plan(self.snapshot(),self.ops(),bad)['status'],'invalid_input')

    def test_07_sparse_or_metatable_arrays_rejected(self):
        s=self.lua(self.snapshot());ops=self.lua(self.ops());ops[2]=None
        self.assertEqual(self.module.plan(s,self.lua(self.counts),ops)['status'],'invalid_input')
        self.rt.eval('setmetatable')(s,self.rt.table())
        self.assertEqual(self.module.plan(s,self.lua(self.counts),self.lua(self.ops()))['status'],'invalid_input')

    def test_08_repeated_owner_uses_latest_planned_state(self):
        s=self.snapshot();ops=[dict(owner='main',template_id=0x29),dict(owner='main',template_id=0x28)]
        r=self.plan(s,ops)
        self.assertEqual((r['steps'][1]['released'],r['steps'][2]['released'],r['final_used']),(3,1,4))

    def test_09_u32_capacity_arithmetic_does_not_wrap(self):
        s=self.snapshot(4294967295);s['used']=4294967295
        r=self.plan(s,self.ops())
        self.assertEqual((r['status'],r['peak_required']),('insufficient_capacity',4294967296))

    def test_10_input_snapshot_and_operation_order_preserved(self):
        s=self.lua(self.snapshot());ops=self.lua(self.ops());counts=self.lua(self.counts)
        before=self.rt.eval('function(t) return t.owners[1].requested_id,t.owners[1].allocated,t.used end')(s)
        r=self.module.plan(s,counts,ops)
        after=self.rt.eval('function(t) return t.owners[1].requested_id,t.owners[1].allocated,t.used end')(s)
        self.assertEqual(before,after)
        self.assertEqual([r['steps'][i]['owner'] for i in range(1,4)],['second','third','main'])
        r['final_owners'][1]['allocated']=99
        self.assertEqual(s['owners'][1]['allocated'],3)

    def test_11_complete_same_id_is_a_noop(self):
        r=self.plan(self.snapshot(),[dict(owner='main',template_id=0x24)])
        self.assertTrue(r['steps'][1]['same_id_skip'])
        self.assertEqual((r['steps'][1]['added'],r['steps'][1]['released'],r['final_used']),(0,0,5))


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PreflightTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(status='passed' if result.wasSuccessful() else 'failed',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),python=sys.version,python_executable=sys.executable,
        lupa_version=lupa.__version__,lua_runtime=LuaRuntime().lua_implementation,
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),evidence_sha256=EVIDENCE_SHA,
        game_process_access=False,game_execution=False,mod_installed=False)
    folder=ROOT/'verification';folder.mkdir(exist_ok=True)
    (folder/'pool_preflight_tests.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
