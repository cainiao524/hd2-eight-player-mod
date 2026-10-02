import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from platform_member_consumer_patch import build
from verify_platform_member_consumer_patch import verify


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "Native" / "SessionMembers" / "platform_member_consumer_disasm_20261002.json"


class PlatformMemberConsumerPatchTests(unittest.TestCase):
    def test_template_has_exact_site_and_unwind(self):
        artifact = build(EVIDENCE)
        self.assertFalse(artifact["verification"]["installable"])
        self.assertFalse(artifact["verification"]["multiplayer_verified"])
        self.assertEqual(artifact["entry"]["entry_patch_span"], 14)
        self.assertEqual(len(bytes.fromhex(artifact["stub"]["code_hex"])), artifact["stub"]["size_bytes"])
        self.assertEqual(bytes.fromhex(artifact["unwind"]["unwind_info_hex"])[:4], bytes([1, 17, 9, 0]))

    def test_static_verifier_accepts_generated_artifact(self):
        artifact = build(EVIDENCE)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            result = verify(EVIDENCE, path)
        self.assertEqual(result["status"], "passed_static_template_verification")
        self.assertGreater(result["stub_bytes"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
