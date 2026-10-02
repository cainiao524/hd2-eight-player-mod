import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_member_consumer import (
    INVALID_STATUS,
    MemberSidecar,
    OwnerState,
    evaluate,
    mode_predicate,
)


class PlatformMemberConsumerTests(unittest.TestCase):
    def test_mode_mapping_matches_captured_branches(self):
        self.assertTrue(mode_predicate(True, 99))
        self.assertFalse(mode_predicate(False, 0))
        self.assertFalse(mode_predicate(False, 1))
        self.assertFalse(mode_predicate(False, 2))
        self.assertFalse(mode_predicate(False, 3))
        self.assertFalse(mode_predicate(False, 4))
        self.assertFalse(mode_predicate(False, 5))

    def test_no_platform_object_returns_mode_predicate(self):
        owner = OwnerState(platform_object=0, ready=False)
        sidecar = MemberSidecar((11, 22, 33, 44, 55, 66, 77, 88))
        self.assertEqual(evaluate(owner, sidecar, local_id=11, flag_nonzero=True,
                                  mode_enum=0, lookup=lambda *_: None,
                                  validate=lambda _: 1), 1)
        self.assertEqual(evaluate(owner, sidecar, local_id=11, flag_nonzero=False,
                                  mode_enum=0, lookup=lambda *_: None,
                                  validate=lambda _: 1), 0)

    def test_not_ready_and_empty_are_fail_closed(self):
        lookup = lambda *_: 1
        validate = lambda _: 0
        self.assertEqual(evaluate(OwnerState(9, False), MemberSidecar((9,)),
                                  local_id=9, flag_nonzero=True, mode_enum=0,
                                  lookup=lookup, validate=validate), INVALID_STATUS)
        self.assertEqual(evaluate(OwnerState(9, True), MemberSidecar(()),
                                  local_id=9, flag_nonzero=True, mode_enum=0,
                                  lookup=lookup, validate=validate), INVALID_STATUS)

    def test_exactly_one_local_and_valid_nonlocals_succeeds_for_eight(self):
        ids = tuple(range(100, 108))
        calls = []

        def lookup(platform, member):
            calls.append((platform, member))
            return member + 1000

        owner = OwnerState(0x1234, True)
        result = evaluate(owner, MemberSidecar(ids), local_id=103,
                          flag_nonzero=True, mode_enum=0,
                          lookup=lookup, validate=lambda token: 0)
        self.assertEqual(result, 1)
        self.assertEqual([m for _, m in calls], [100, 101, 102, 104, 105, 106, 107])

    def test_missing_or_duplicate_local_is_invalid(self):
        owner = OwnerState(0x1234, True)
        common = dict(local_id=103, flag_nonzero=True, mode_enum=0,
                      lookup=lambda *_: 1, validate=lambda _: 0)
        self.assertEqual(evaluate(owner, MemberSidecar(tuple(range(100, 104))), **common), 1)
        self.assertEqual(evaluate(owner, MemberSidecar((100, 101, 102, 104)), **common), INVALID_STATUS)
        self.assertEqual(evaluate(owner, MemberSidecar((103, 103, 104, 105)), **common), INVALID_STATUS)

    def test_lookup_failure_does_not_count_as_member(self):
        owner = OwnerState(0x1234, True)
        ids = (100, 101, 102, 103)
        self.assertEqual(evaluate(owner, MemberSidecar(ids), local_id=100,
                                  flag_nonzero=True, mode_enum=0,
                                  lookup=lambda _, member: None if member == 102 else member,
                                  validate=lambda _: 0), INVALID_STATUS)

    def test_nine_slots_rejected(self):
        owner = OwnerState(0x1234, True)
        self.assertEqual(evaluate(owner, MemberSidecar(tuple(range(9))), local_id=0,
                                  flag_nonzero=True, mode_enum=0,
                                  lookup=lambda *_: 1, validate=lambda _: 0), INVALID_STATUS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
