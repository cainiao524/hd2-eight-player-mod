"""Find bounded player creation/spawn strings in the pinned readonly capture."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research_handoff_20260927" / "indirect"))
from inspect_capture import EXPECTED, Image, require  # noqa: E402

MATCH = re.compile(r"(?:player|helldiver|diver).{0,36}(?:spawn|create|entity|unit)|"
                   r"(?:spawn|create|entity|unit).{0,36}(?:player|helldiver|diver)", re.I)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    require(not args.output.exists(), "refusing overwrite")
    im = Image(args.evidence)
    rows = []
    for area in im.report["ranges"]:
        if not area["label"].startswith("readonly"):
            continue
        data = im.read(area["rva"], area["size"])
        for m in re.finditer(rb"[\x20-\x7e]{4,}\x00", data):
            value = m.group(0)[:-1].decode("ascii")
            if MATCH.search(value):
                rows.append({"rva": hex(area["rva"] + m.start()), "text": value})
    out = {"source_sha256": EXPECTED, "game_sha256": im.report["game_sha256"],
           "regex": MATCH.pattern, "strings": rows,
           "limits": ["String names alone do not prove reachable player creation code."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
