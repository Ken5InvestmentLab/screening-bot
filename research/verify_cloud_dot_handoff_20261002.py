"""Portable, stdlib-only verification of an extracted Cloud handoff or its ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('unsafe bundle path')
    return name


def digest(stream):
    h = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
        h.update(block)
        size += len(block)
    return size, h.hexdigest()


def verify(path):
    path = Path(path)
    z = zipfile.ZipFile(path) if path.is_file() else None
    def read(name):
        safe_name(name)
        return z.open(name) if z else (path / name).open('rb')
    try:
        with read('handoff/MANIFEST.json') as f:
            m = json.load(f)
        expected = {safe_name(row['path']) for row in m['files']}
        if len(expected) != len(m['files']):
            raise ValueError('duplicate manifest entries')
        if z:
            names = [safe_name(n) for n in z.namelist()]
            if len(names) != len(set(names)) or set(names) != expected | {'handoff/MANIFEST.json'}:
                raise ValueError('ZIP entry set differs from manifest')
        total = 0
        for row in m['files']:
            with read(row['path']) as f:
                size, sha = digest(f)
            if size != row['bytes'] or sha != row['sha256']:
                raise ValueError('hash mismatch: ' + row['path'])
            total += size
        return {'status': 'PASS', 'verified_files': len(expected), 'verified_bytes': total,
                'zip_crc_and_sha256': bool(z), 'code_snapshot_commit': m['code_snapshot_commit']}
    finally:
        if z:
            z.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('path', help='ZIP path or extracted repository root')
    args = p.parse_args()
    print(json.dumps(verify(args.path)))


if __name__ == '__main__':
    main()
