"""Gate handler-free clones on the pinned, saved original unwind records.

This module reads the small repository snapshot only. It does not query an
installed image or assume the captured table is the current runtime table.
"""
import hashlib
import json
from pathlib import Path
import struct

PROJECT = Path(__file__).resolve().parents[1]
SNAPSHOT = PROJECT / 'native-unwind-source.lock.json'
SNAPSHOT_SHA256 = 'bfefac86c12f8a761b563d4da814ed1195eb7967f024fe218b9e6d6c5a896680'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def load_bytes(raw):
    require(sha(raw) == SNAPSHOT_SHA256, 'Changed original unwind snapshot')
    data = json.loads(raw)
    audit(data)
    return data


def audit(data, *, schema='hellforge_captured_property_unwind_v1', names=('producer','receiver'), gs_functions=()):
    """Decode the no-handler/chaining property; not an exception dispatcher."""
    require(data['schema'] == schema and data['build'] == 25480438,
            'Unsupported original unwind profile')
    require(set(data['functions']) == set(names), 'Incomplete function set')
    table = data['captured_table']; table_rva = int(table['rva'], 16)
    require(table['size'] == table['entries'] * 12, 'Invalid table size')
    summaries = {}
    for name, function in data['functions'].items():
        start, end = int(function['entry'], 16), int(function['end_exclusive'], 16)
        cursor, records, flags_seen = start, {}, []
        for fragment in function['fragments']:
            rf = bytes.fromhex(fragment['runtime_function_hex'])
            require(len(rf) == 12, 'Truncated function entry')
            entry = struct.unpack('<III', rf); a, b, u = entry
            slot = int(fragment['table_entry_rva'], 16) - table_rva
            require(0 <= slot <= table['size'] - 12 and slot % 12 == 0, 'Entry outside captured table')
            require(a == cursor and a < b <= end and u % 4 == 0, 'Noncontiguous function coverage')
            cursor = b
            raw = bytes.fromhex(fragment['unwind_hex'])
            require(len(raw) >= 4 and raw[0] & 7 == 1, 'Unsupported unwind version/header')
            flags = raw[0] >> 3
            gs = name in gs_functions and flags == 3
            require(not flags & 3 or gs, 'Original language handler requires explicit preservation')
            require((flags in (0, 4) or gs) and raw[3] == 0, 'Unsupported flags/frame register')
            body = 4 + ((raw[2] + 1) & ~1) * 2
            require(len(raw) == body + (12 if flags == 4 else 8 if gs else 0), 'Truncated or surplus unwind data')
            if gs:
                require(struct.unpack('<II', raw[body:]) == (0x21044a0, 96), 'Unknown GS handler contract')
            require(raw[1] <= b - a, 'Prologue exceeds fragment')
            parent = struct.unpack('<III', raw[body:]) if flags == 4 else None
            records[entry] = parent
            flags_seen.append(flags)
        require(cursor == end and records, 'Incomplete function coverage')
        for entry in records:
            seen = set(); node = entry
            while True:
                require(node in records, 'Uncaptured chained record')
                require(node not in seen, 'Cyclic unwind chain')
                seen.add(node)
                parent = records[node]
                if parent is None:
                    require(node[0] == start, 'Wrong primary unwind entry')
                    break
                node = parent
        summaries[name] = {'fragments': len(records), 'flags': flags_seen,
                           'chained_fragments': flags_seen.count(4), 'language_handlers': any(f & 3 for f in flags_seen)}
    return summaries


def verify_candidate(name, candidate):
    data = load_bytes(SNAPSHOT.read_bytes()); function = data['functions'][name]
    require(candidate['target_profile']['build'] == data['build'] and
            candidate['source_sha256'] == function['code_sha256'] and
            candidate['evidence_sha256'] == function['evidence_sha256'],
            'Candidate does not match original unwind source')
    return {'snapshot_sha256': SNAPSHOT_SHA256,
            'captured_fragments': len(function['fragments']),
            'captured_language_handlers': False, 'runtime_table_verified': False}
