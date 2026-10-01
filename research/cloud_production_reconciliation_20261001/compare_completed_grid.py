"""Inventory the completed grid; compare to reference values, never adopt it."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METRICS = ROOT / 'research/comparisons/cloud_exit_20261001/metrics.csv'
REFERENCE = ROOT / 'research/cloud_comparison_dashboard_20261001/production_reference.json'
LABELS = {
    'all_conditions_unique': '銘柄均等', 'all_conditions_stacked': 'モード別積上げ',
    'volr20_low': 'Silence', 'body_pct_low': 'Dive',
    'mean_rank_volr20_body_pct': 'Shadow', 'dual_top1_agreement': 'Fusion',
    'dual_top1_agreement_g3_no_acute_selloff': 'Balance',
}


def main() -> None:
    before = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for p in (METRICS, REFERENCE)}
    with METRICS.open(encoding='utf-8-sig', newline='') as handle:
        rows = [r for r in csv.DictReader(handle) if r['period'] == 'ALL_DESCRIPTIVE']
    expected = set(itertools.product(LABELS, ['cap1000', 'cap1500', 'cap2000', 'cap3000', 'cap5000', 'nocap'],
                                    [f'd{day}_{side}' for day in range(1, 11) for side in ('open', 'close')]))
    assert len(rows) == len(expected) == 840
    assert {(r['selector'], r['arm'], r['endpoint']) for r in rows} == expected
    reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
    refs = {r['mode']: r for r in reference['metrics'] if r['period'] == 'ALL'}
    results = []
    for selector, label in LABELS.items():
        group = [r for r in rows if r['selector'] == selector]
        best = max(group, key=lambda r: float(r['mean_pct']))
        ref = refs[selector]
        passing = [r for r in group if float(r['mean_pct']) >= ref['mean_pct']
                   and float(r['win_pct']) >= ref['win_pct']]
        results.append({
            'selector': selector, 'label': label, 'grid_count': len(group),
            'mean_max_arm': best['arm'], 'mean_max_endpoint': best['endpoint'],
            **{k: int(best[k]) if k == 'n' else float(best[k]) for k in
               ('n', 'mean_pct', 'win_pct', 'median_pct', 'loss10_pct', 'top3_ex_mean_pct')},
            'published_reference_mean_pct': ref['mean_pct'],
            'published_reference_win_pct': ref['win_pct'],
            'reference_mean_and_win_at_least_equal_count': len(passing),
        })
    global_mean = max(results, key=lambda r: r['mean_pct'])
    after = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
             for p in (METRICS, REFERENCE)}
    assert before == after
    output = {
        'status': 'PASS', 'completed_all_period_combinations': len(rows),
        'single_mode_combinations': 600, 'combined_allocation_combinations': 240,
        'scope': 'Fixed features/model/Tail/selector conditions; six price caps and twenty exit times.',
        'objective_of_reported_maxima': 'post-hoc all-period arithmetic mean only',
        'same_mode_published_reference_screen_count': sum(r['reference_mean_and_win_at_least_equal_count'] for r in results),
        'best_mean_single_mode': global_mean, 'per_allocation_or_mode': results,
        'full_model_and_detection_condition_search_completed': False,
        'exact_production_replay_confirmed': False, 'candidate_adopted': False,
        'limits': [
            'Reference screening uses the published historical cohort; it is not a like-for-like causal comparison.',
            'The all-period maximum was chosen retrospectively and cannot establish future optimality.',
            'Seven groups include different allocations and overlapping modes, not 840 independent strategies.',
            'Zero costs; no proof of fills; held-out future observations are not available.',
        ],
        'input_sha256_lf': before, 'no_model_execution': True, 'no_production_mutations': True,
    }
    (HERE / 'completed_grid_audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n',
                                                   encoding='utf-8', newline='\n')
    with (HERE / 'completed_grid_best.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(results)
    print(json.dumps({'status': output['status'], 'completed_combinations': len(rows),
                      'reference_screen_passes': output['same_mode_published_reference_screen_count'],
                      'best_mean': global_mean}, ensure_ascii=False))


if __name__ == '__main__':
    main()
