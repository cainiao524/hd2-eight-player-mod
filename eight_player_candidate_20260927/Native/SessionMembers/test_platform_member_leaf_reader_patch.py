import json
import tempfile
import unittest
from pathlib import Path

from platform_member_leaf_reader_patch import build
from verify_platform_member_leaf_reader_patch import verify


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "Native" / "SessionMembers" / "platform_member_leaf_reader_disasm_20261002.json"


class PlatformMemberLeafReaderPatchTests(unittest.TestCase):
    def test_generated_candidate_is_template_only(self):
        artifact = build(EVIDENCE)
        self.assertFalse(artifact["verification"]["installable"])
        self.assertEqual(artifact["entry"]["entry_patch_span"], 14)
        self.assertEqual(artifact["stub"]["size_bytes"], len(bytes.fromhex(artifact["stub"]["code_hex"])))

    def test_static_verifier(self):
        artifact = build(EVIDENCE)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            result = verify(EVIDENCE, path)
        self.assertEqual(result["status"], "passed_static_template_verification")


if __name__ == "__main__":
    unittest.main(verbosity=2)

