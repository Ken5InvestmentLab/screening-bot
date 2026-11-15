"""New-A uses private D1. Preserve the existing dormant scheduler input verbatim."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

def main() -> None:
    gate = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    expected = (gate / 'src' / 'cloud-canonical-input.generated.ts').resolve()
    if output != expected:
        raise ValueError('canonical output must be the existing preserved scheduler module')
    contract = json.loads((gate / 'scripts' / 'new-a-code-contract.json').read_text(encoding='utf-8'))
    if not output.is_file() or hashlib.sha256(output.read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')).hexdigest() != contract['legacyCanonicalSha256']:
        raise ValueError('existing legacy scheduler input missing or changed; regeneration is prohibited')
    print(json.dumps({'new_a_private_d1': True, 'legacy_input_preserved': True, 'files_written': 0, 'ledger_read': False}))

if __name__ == '__main__':
    main()
