"""Replay the original unwind snapshot against explicit, saved capture files."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import struct
import sys

import native_unwind_source as source

ROOT = source.PROJECT.parent


def replay(data, capture):
    reader = ROOT / data['capture_reader_path']
    source.require(source.sha(reader.read_bytes()) == data['capture_reader_sha256'], 'Changed capture reader')
    sys.path.insert(0, str(ROOT / 'eight_player_candidate_20260927/.native-test-deps'))
    import capstone
    source.require(capstone.__version__ == '5.0.7', 'Wrong decoder version')
    spec = importlib.util.spec_from_file_location('pinned_capture_reader', reader)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    source.require(module.EXPECTED == data['capture_source_sha256'], 'Changed capture pins')
    image = module.Image(capture)
    source.require(image.report['capture_sha256'] == data['capture_identity_sha256'], 'Wrong capture identity')
    table = data['captured_table']; header = data['header_directory']
    source.require((image.exception_rva, image.exception_size, len(image.functions)) ==
                   (int(table['rva'], 16), table['size'], table['entries']), 'Changed captured table')
    source.require((image.header_exception_rva, image.header_exception_size) ==
                   (int(header['rva'], 16), header['size']), 'Changed header directory')
    try:
        image.read(image.header_exception_rva, image.header_exception_size)
        directory_captured = True
    except ValueError:
        directory_captured = False
    source.require(directory_captured == header['fully_captured'], 'Changed runtime-directory coverage')
    checked_bytes = 0
    for function in data['functions'].values():
        start, end = int(function['entry'], 16), int(function['end_exclusive'], 16)
        source.require(source.sha(image.read(start, end - start)) == function['code_sha256'], 'Changed original code')
        source.require(source.sha((ROOT / function['evidence_path']).read_bytes()) == function['evidence_sha256'],
                       'Changed code evidence')
        entries = []
        for fragment in function['fragments']:
            rf = bytes.fromhex(fragment['runtime_function_hex']); entry = struct.unpack('<III', rf)
            unwind = bytes.fromhex(fragment['unwind_hex'])
            source.require(image.read(int(fragment['table_entry_rva'], 16), 12) == rf, 'Changed function entry')
            source.require(image.read(entry[2], len(unwind)) == unwind, 'Changed original unwind data')
            source.require(image.root(entry[0])[0] == start, 'Capture reader disagrees with chain root')
            entries.append(entry); checked_bytes += 12 + len(unwind)
        source.require(entries == [f for f in image.functions if f[0] < end and start < f[1]],
                       'Incomplete captured function coverage')
    return {'passed': True, 'functions': source.audit(data,schema=data['schema'],names=tuple(data['functions'])), 'metadata_bytes_replayed': checked_bytes,
              'header_exception_directory_captured': directory_captured, 'runtime_table_verified': False,
              'game_access': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    args = parser.parse_args()
    data = source.load_bytes(source.SNAPSHOT.read_bytes())
    result = replay(data,args.capture)
    paths = ('native-unwind-source.lock.json', 'tools/native_unwind_source.py',
             'tools/verify_native_unwind_source.py', 'tests/test_native_unwind_source.py')
    receipt = {'schema': 'hellforge_original_unwind_replay_v1',
               'verified_at_utc': datetime.now(timezone.utc).isoformat(), **result,
               'snapshot_sha256': source.SNAPSHOT_SHA256, 'capture_source_sha256': data['capture_source_sha256'],
               'source_sha256': {p: source.sha((source.PROJECT / p).read_bytes()) for p in paths}}
    (source.PROJECT / 'evidence/native-unwind-source-validation.json').write_text(
        json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
