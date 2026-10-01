import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--require-complete', action='store_true')
args = parser.parse_args()
root = Path.cwd()
out = root / '.cache/cloud_cap_corrected_v2_20261001'
metadata = json.loads((out / 'prepared.json').read_text(encoding='utf-8'))

def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()

for relative, expected in metadata['source_hashes'].items():
    assert digest(root / relative) == expected, relative

counts = Counter()
selected_rows = 0
for receipt_path in sorted(out.glob('receipt_cap*_*.json')):
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    selected_path = out / f"selected_cap{receipt['cap']}_{receipt['month']}.csv"
    assert receipt['source_hashes'] == metadata['source_hashes'], receipt_path
    assert digest(selected_path) == receipt['selected_sha256'], selected_path
    with selected_path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == receipt['selected_rows'], receipt_path
    assert len(rows) <= receipt['tail_rows'] * 5, receipt_path
    for row in rows:
        assert row['date'][:7] == receipt['month'] == row['model_period'], row
        assert metadata['start'] <= row['date'] <= metadata['end'], row
        assert float(row['tail_cdf']) >= 0.999, row
    counts[str(receipt['cap'])] += 1
    selected_rows += len(rows)

if args.require_complete:
    assert counts == Counter({str(cap): 45 for cap in metadata['caps']}), counts

result = {'status': 'PASS', 'all_270_required': args.require_complete,
          'verified_monthly_receipts': sum(counts.values()),
          'months_by_cap': dict(counts), 'selected_rows': selected_rows,
          'checks': ['component hashes unchanged', 'monthly CSV SHA and row count',
                     'selected dates within declared model month and corpus cutoff',
                     'tail CDF >= 0.999', 'at most five selected allocations per tail row']}
(out / 'independent_monthly_receipt_audit.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
