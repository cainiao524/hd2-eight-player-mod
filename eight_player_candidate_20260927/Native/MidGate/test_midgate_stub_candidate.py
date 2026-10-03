"""Tests for the exact-build mid-function stub candidate.

These tests exercise only deterministic bytes and a synthetic rollback buffer.
They never open, inject, or patch Helldivers 2.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import midgate_stub_candidate as candidate  # noqa: E402


class MidGateStubCandidateTests(unittest.TestCase):
    def test_static_receipt_matches_fresh_generation(self) -> None:
        receipt = json.loads((ROOT / "midgate_stub_candidate_20261002.json").read_text(encoding="utf-8"))
        fresh = candidate.verify()
        self.assertEqual(receipt, fresh)
        self.assertEqual(receipt["steam_build"], 25480438)
        self.assertFalse(receipt["status"]["executable"])
        self.assertFalse(receipt["status"]["multiplayer_verified"])

    def test_exact_site_boundaries_and_original_bytes(self) -> None:
        rows = candidate._load_instructions()
        capacity, allocator = candidate._make_sites(rows)
        self.assertEqual((capacity.rva, capacity.end_rva, capacity.span_length),
                         (0x108C18F, 0x108C1B5, 38))
        self.assertEqual((allocator.rva, allocator.end_rva, allocator.span_length),
                         (0x108C3D8, 0x108C3E7, 15))
        self.assertEqual(capacity.expected.hex(),
                         "418bc6493941580f95c0ffc04d39b1900000008d48010f44c84d39b1c80000008d41010f44c1")
        self.assertEqual(allocator.expected.hex(),
                         "443830740cffc148ffc083f90472f1")
        self.assertEqual(capacity.continuation, 0x108C1BA)
        self.assertEqual(allocator.continuation, 0x108C3F7)

    def test_patch_and_rollback_are_exact_on_synthetic_buffers(self) -> None:
        capacity, allocator = candidate._make_sites(candidate._load_instructions())
        for site in (capacity, allocator):
            synthetic = bytearray(site.expected)
            original = bytes(synthetic)
            synthetic[:] = site.patch
            self.assertEqual(len(synthetic), site.span_length)
            synthetic[:] = original
            self.assertEqual(bytes(synthetic), site.expected)
            self.assertEqual(site.patch[:6], b"\xff\x25\x00\x00\x00\x00")
            self.assertTrue(all(byte == 0x90 for byte in site.patch[14:]))

    def test_unwind_and_call_contract(self) -> None:
        capacity, allocator = candidate._make_sites(candidate._load_instructions())
        self.assertEqual(capacity.unwind[:4], bytes([1, 15, 7, 0]))
        self.assertEqual(allocator.unwind[:4], bytes([1, 7, 3, 0]))
        self.assertEqual((6 * 8 + 32) % 16, 0)
        self.assertEqual((2 * 8 + 32) % 16, 0)
        self.assertEqual(capacity.preserved_registers,
                         ("r9", "r12", "r13", "r14", "r15", "rbp"))
        self.assertEqual(allocator.preserved_registers, ("r9", "rdx"))
        self.assertIn(b"\x41\x8b\xd6", capacity.stub)
        self.assertIn(b"\x41\x8b\xd6", allocator.stub)
        self.assertNotIn(b"\x44\x8b\xd6", capacity.stub)
        self.assertNotIn(b"\x44\x8b\xd6", allocator.stub)
        self.assertIn(b"\x49\x8b\xc9", capacity.stub)
        self.assertIn(b"\x49\x8b\xc9", allocator.stub)
        self.assertNotIn(b"\x4c\x8b\xc9", capacity.stub)
        self.assertNotIn(b"\x4c\x8b\xc9", allocator.stub)
        self.assertLess(capacity.stub.index(b"\xb9\x08\x00\x00\x00"),
                        capacity.stub.index(b"\x83\xf8\x08"))
        self.assertNotIn(b"\xe8", capacity.stub)
        self.assertNotIn(b"\xe9", capacity.stub)
        self.assertNotIn(b"\xe8", allocator.stub)
        self.assertNotIn(b"\xe9", allocator.stub)


if __name__ == "__main__":
    unittest.main()
