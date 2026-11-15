"""Build the same data-free Cloud frame as CI. Private data is delivered by D1."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-root', type=Path, help='Isolated review only; every existing asset must match the pinned code hash')
    # No ledger argument or fallback. A legacy caller fails instead of publishing prices.
    args = parser.parse_args()
    output = args.output.resolve()
    state = (ROOT / 'weak_early_beta' / 'state').resolve()
    if output == state or state in output.parents:
        raise ValueError('preview cannot overwrite state')
    gate = ROOT / 'weak-early-beta-gate'
    command = ['node', str(gate / 'scripts' / 'sync-report.mjs')]
    if args.baseline_root:
        command += ['--baseline-root', str(args.baseline_root.resolve())]
    subprocess.run(command, check=True, cwd=gate)
    output.mkdir(parents=True, exist_ok=True)
    source = gate / 'public'
    if output != source.resolve():
        for file in source.glob('weak_early_beta_*.html'):
            shutil.copyfile(file, output / file.name)
        shutil.copytree(source / 'new-a-assets', output / 'new-a-assets', dirs_exist_ok=True)
    print(json.dumps({'data_free_frame': True, 'private_inputs_read': 0, 'source_rows_embedded': 0, 'notifications_sent': 0, 'deployed': False}))

if __name__ == '__main__':
    main()
