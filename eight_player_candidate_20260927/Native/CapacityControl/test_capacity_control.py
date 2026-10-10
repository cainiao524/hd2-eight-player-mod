"""Synthetic tests for the Lua/native capacity control boundary.

The fixture is an isolated DLL and never loads game.dll or touches a game
process. These tests prove request epochs, atomic commit, rollback and the
admission bound only.
"""
from __future__ import annotations
import ctypes
import pathlib
import subprocess
import unittest

ROOT=pathlib.Path(__file__).parent
DLL=ROOT/'build'/'test_control_fixture.dll'

class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DLL.exists(): subprocess.run(['cmd','/c','build_x64.bat'],cwd=ROOT,check=True)
        cls.dll=ctypes.CDLL(str(DLL))
        for name, restype, args in [
            ('fixture_start',ctypes.c_uint,[ ]),('fixture_stop',ctypes.c_uint,[]),
            ('fixture_boundary',ctypes.c_uint,[ctypes.c_uint]),
            ('fixture_submit',ctypes.c_uint,[ctypes.c_uint,ctypes.c_uint]),
            ('fixture_admit',ctypes.c_uint,[ctypes.c_uint]),
            ('fixture_value',ctypes.c_uint,[ctypes.c_uint]),
            ('fixture_flags',None,[ctypes.c_uint]*5),
            ('fixture_fail',None,[ctypes.c_uint,ctypes.c_uint]),
        ]:
            f=getattr(cls.dll,name);f.restype=restype;f.argtypes=args
    def setUp(self): self.assertEqual(self.dll.fixture_start(),0)
    def tearDown(self): self.assertEqual(self.dll.fixture_stop(),0)
    def test_dynamic_bound_and_epoch_guard(self):
        self.assertEqual(self.dll.fixture_admit(0),0)
        self.assertEqual(self.dll.fixture_submit(8,0),9) # pending
        self.assertEqual(self.dll.fixture_boundary(0),0)
        self.assertEqual(self.dll.fixture_value(0),8)
        self.assertEqual(self.dll.fixture_value(1),8)
        for index in range(1,8): self.assertEqual(self.dll.fixture_admit(index),0)
        self.assertNotEqual(self.dll.fixture_admit(8),0)
    def test_host_and_compatibility_gate(self):
        self.dll.fixture_flags(0,1,1,0,1)
        self.assertEqual(self.dll.fixture_submit(8,0),5) # host required
        self.dll.fixture_flags(1,0,1,0,1)
        self.assertEqual(self.dll.fixture_submit(8,0),4) # provider not ready
    def test_failed_commit_rolls_back_and_blocks_until_retry(self):
        self.assertEqual(self.dll.fixture_submit(8,0),9)
        self.dll.fixture_fail(1,0)
        self.assertEqual(self.dll.fixture_boundary(0),8) # commit fails; compensation succeeds
        self.assertEqual(self.dll.fixture_value(0),4)
        self.assertEqual(self.dll.fixture_value(3),1)

if __name__=='__main__': unittest.main()
