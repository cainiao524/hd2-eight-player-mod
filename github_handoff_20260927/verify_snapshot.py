"""Verify the frozen upload payload using Git objects only; never run research."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'github_handoff_20260927/SNAPSHOT_SHA256.json'
RECEIPT = 'github_handoff_20260927/UPLOAD_STATUS.json'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', help='Payload commit; defaults to HEAD receipt, then HEAD')
    args = parser.parse_args()
    revision = args.revision
    if revision is None:
        has_receipt = subprocess.run(
            ['git', '-C', str(ROOT), 'cat-file', '-e', 'HEAD:' + RECEIPT],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        revision = json.loads(git('show', 'HEAD:' + RECEIPT))['payload_commit'] if has_receipt else 'HEAD'
    commit = git('rev-parse', '--verify', '--end-of-options', revision + '^{commit}').decode().strip()
    manifest = json.loads(git('show', commit + ':' + MANIFEST))
    expected = {item['path']: item for item in manifest['files']}
    if len(expected) != len(manifest['files']):
        raise ValueError('Duplicate snapshot paths')
    actual = {}
    for record in git('ls-tree', '-r', '-z', commit).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if kind != b'blob' or mode not in (b'100644', b'100755'):
            raise ValueError('Unexpected non-file tree entry: ' + path.decode('utf-8'))
        actual[path.decode('utf-8')] = oid.decode('ascii')
    if set(actual) != set(expected) | {MANIFEST}:
        raise ValueError('Tree differs from manifest: ' + repr(sorted(set(actual) ^ (set(expected) | {MANIFEST}))))
    total = 0
    with subprocess.Popen(
        ['git', '-C', str(ROOT), 'cat-file', '--batch'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    ) as batch:
        for path, item in expected.items():
            batch.stdin.write((actual[path] + '\n').encode('ascii'))
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            if len(header) != 3 or header[1] != b'blob':
                raise ValueError('Invalid Git blob response for ' + path)
            size = int(header[2])
            content = batch.stdout.read(size)
            if len(content) != size or batch.stdout.read(1) != b'\n':
                raise ValueError('Truncated Git blob for ' + path)
            if size != item['size_bytes'] or hashlib.sha256(content).hexdigest() != item['sha256']:
                raise ValueError('Fingerprint mismatch: ' + path)
            total += size
        batch.stdin.close()
        if batch.wait() != 0:
            raise ValueError('git cat-file failed')
    if total != manifest['total_bytes'] or len(expected) != manifest['file_count']:
        raise ValueError('Manifest totals mismatch')
    print(json.dumps(dict(status='pass', payload_commit=commit, files_verified=len(expected),
                         source_bytes_verified=total, tree_files=len(actual)), indent=2))


if __name__ == '__main__':
    main()
