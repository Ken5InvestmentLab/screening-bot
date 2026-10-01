"""Inspect saved Cloud lineage and cached inputs without fitting any model."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from weak_early_beta import model
from weak_early_beta.entry_feasibility import performance_eligible
from weak_early_beta.ledger import read_ledger
from weak_early_beta.metrics import combined_detections

CACHE = ROOT / '.cache/cloud_cap_corrected_v2_20261001'
PACK = ROOT / 'research/repro_packs/weak_early_exact_v1'
OLD_TAIL = ROOT / '.cache/recovery/artifact_10264251140/v7_causal_tail_cache_2023_2025.csv'
OLD_DAILY = ROOT / '.cache/recovery/artifact_10264205130/tse_daily.csv'
TAIL_2026 = PACK / 'output/full_period_2026/causal_tail_pool_2026_reporting_only.csv'


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def syntax_node(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if getattr(node, 'name', None) == name or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
        ):
            return ast.dump(node, include_attributes=False)
    raise ValueError(f'Missing source node: {path}/{name}')


def gate_reasons(row) -> str:
    reasons = []
    if not row['source_usable']:
        reasons.append('current_source_unusable')
    if not row['previous_source_usable']:
        reasons.append('previous_source_unusable')
    if not row['feature_complete']:
        reasons.append('incomplete_features')
    for column, operator, threshold, reason in [
        ('previous_actual_close', 'max', 1000, 'actual_previous_close_above_1000'),
        ('previous_actual_volume', 'min', 10000, 'actual_previous_volume_below_10000'),
        ('actual_volume', 'min', 5000, 'actual_volume_below_5000'),
        ('actual_close', 'min', 20, 'actual_close_below_20'),
    ]:
        value = row[column]
        if pd.isna(value):
            reasons.append(f'missing_{column}')
        elif (value > threshold if operator == 'max' else value < threshold):
            reasons.append(reason)
    return ';'.join(reasons)


def main() -> None:
    prepared = json.loads((CACHE / 'prepared.json').read_text(encoding='utf-8'))
    manifest = json.loads((PACK / 'output/manifest.json').read_text(encoding='utf-8'))
    full_period_path = PACK / 'output/full_period_2026/full_period_report.json'
    full_period = json.loads(full_period_path.read_text(encoding='utf-8'))
    daily = ROOT / Path(prepared['source_path'])
    state_paths = [ROOT / f'weak_early_beta/state/{name}' for name in
                   ('detections.csv', 'metrics.csv', 'entry_feasibility_exclusions.csv', 'jpx_restricted_symbols_latest.json')]
    sources = [*state_paths, OLD_TAIL, OLD_DAILY, TAIL_2026, full_period_path, CACHE / 'prepared.json',
               CACHE / 'rows.pkl', CACHE / 'features.npy', CACHE / 'trades_cap1000.csv', daily]
    sources += [Path(module.__file__) for module in (model, model.base, model.v7, model.shadow)]
    before = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    assert sha(OLD_TAIL) == manifest['inputs']['tail_cache']['sha256']
    assert sha(OLD_DAILY) == manifest['inputs']['daily_corpus']['sha256']
    assert sha(daily) == prepared['source_sha256']
    frozen = ROOT / 'research/cloud_cap_comparison_20261001/frozen'
    parity = {}
    for path, names in [
        (Path(model.base.__file__), ['FEATURES', 'build_features', 'eligible_rows']),
        (Path(model.v7.__file__), ['model', 'cdf']),
        (Path(model.shadow.__file__), ['RET10_MAX', 'G3_MED_RET1_MIN', 'choose_one', 'select_candidates']),
    ]:
        for name in names:
            parity[name] = syntax_node(path, name) == syntax_node(frozen / path.name, name)
    assert all(parity.values()), parity

    tails = [pd.read_csv(p, dtype={'symbol': str}, parse_dates=['date']) for p in (OLD_TAIL, TAIL_2026)]
    old_tail = pd.concat(tails, ignore_index=True)
    assert not old_tail.duplicated(['date', 'symbol']).any()
    replay = model.shadow.select_candidates(old_tail)
    ledger = read_ledger()
    canonical = ledger[ledger.source_scope.fillna('').str.startswith('EXACT_CANONICAL')]
    assert len(replay) == len(canonical) == 967
    assert set(replay.candidate_id) == set(canonical.detection_id)

    production = combined_detections(performance_eligible(ledger))
    production = production[production.gross_return.notna()].copy()
    research = pd.read_csv(CACHE / 'trades_cap1000.csv', dtype={'symbol': str}, parse_dates=['signal_date'])
    summary = json.loads((ROOT / 'research/cloud_cap_comparison_20261001/summary.json').read_text(encoding='utf-8'))
    research = performance_eligible(research)
    research = research[~research.comparison_restricted & ~research.signal_date.dt.strftime('%Y-%m-%d').isin(summary['common_day_excluded_calendar'])]
    research = combined_detections(research)
    research = research[research.gross_return.notna()].copy()
    key = ['signal_date', 'symbol']
    identities = production[key + ['gross_return']].merge(
        research[key + ['gross_return']], on=key, how='outer', indicator=True,
        suffixes=('_production', '_research'), validate='one_to_one')
    shared = identities[identities['_merge'].eq('both')]
    assert (shared.gross_return_production - shared.gross_return_research).abs().le(1e-8).all()
    assert identities['_merge'].value_counts().to_dict() == {'left_only': 132, 'right_only': 136, 'both': 116}

    # Saved input metadata; no feature regeneration or training takes place.
    rows = pd.read_pickle(CACHE / 'rows.pkl')
    lookup_keys = pd.concat([
        old_tail[['date', 'symbol']], identities[key].rename(columns={'signal_date': 'date'})
    ]).drop_duplicates()
    thin = rows[rows.date.isin(lookup_keys.date) & rows.symbol.isin(lookup_keys.symbol)].copy()
    thin['_cache_index'] = thin.index
    thin = thin.merge(lookup_keys, on=['date', 'symbol'], validate='one_to_one')
    assert len(thin) == len(lookup_keys)
    thin['gate_reasons'] = thin.apply(gate_reasons, axis=1)
    thin['current_gate_pass'] = thin.gate_reasons.eq('')

    # Independently invoke the real production gate on cached feature probes,
    # retaining each probe's immediate predecessor in its symbol series.
    probe_indices = thin['_cache_index'].astype(int).to_numpy()
    all_probe_indices = np.unique(np.concatenate([probe_indices, np.maximum(probe_indices - 1, 0)]))
    probe = rows.loc[all_probe_indices].copy()
    features = np.load(CACHE / 'features.npy', mmap_mode='r')
    assert len(features) == len(rows) and features.shape[1] == len(model.base.FEATURES) == 45
    probe[model.base.FEATURES] = features[all_probe_indices]
    actual_gate_indices = set(model.eligible_live_rows(probe).index)
    expected_gate_indices = set(thin.loc[thin.current_gate_pass, '_cache_index'])
    assert actual_gate_indices.intersection(probe_indices) == expected_gate_indices

    common = (rows.source_usable & rows.previous_source_usable & rows.feature_complete
              & rows.previous_actual_volume.ge(10000) & rows.actual_volume.ge(5000)
              & rows.actual_close.ge(20) & rows.previous_actual_close.le(1000))
    labeled = rows.loc[common & rows.target5_no.notna() & rows.target_end_date.notna(),
                       ['date', 'symbol', 'target5_no', 'target_end_date']].copy()
    labeled['future_rank_new'] = labeled.groupby('date').target5_no.rank(pct=True, method='average')
    labeled['y_top025_new'] = labeled.future_rank_new.ge(.9975).astype(int)
    label_probe = old_tail[['date', 'symbol', 'future_rank', 'y_top025']].merge(
        labeled[['date', 'symbol', 'future_rank_new', 'y_top025_new']], on=['date', 'symbol'],
        how='inner', validate='one_to_one')
    monthly_count_matches = []
    for receipt_path in sorted(CACHE.glob('receipt_cap1000_*.json')):
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        period = pd.Period(receipt['month'], freq='M')
        train_count = int(labeled.target_end_date.lt(period.start_time).sum())
        prediction_count = int((common & rows.date.between(period.start_time, period.end_time.normalize())
                                & rows.date.between(pd.Timestamp(prepared['start']), pd.Timestamp(prepared['end']))).sum())
        assert train_count == receipt['train_rows'] and prediction_count == receipt['prediction_rows']
        monthly_count_matches.append(period.strftime('%Y-%m'))
    assert len(monthly_count_matches) == 45

    gate_detail = replay[['date', 'symbol']].drop_duplicates().merge(
        thin, on=['date', 'symbol'], validate='one_to_one').merge(
        old_tail[['date', 'symbol', 'prev_close', 'prev_volume']], on=['date', 'symbol'], validate='one_to_one')
    identity_detail = identities.merge(
        thin[['date', 'symbol', 'current_gate_pass', 'gate_reasons', 'previous_actual_close']],
        left_on=key, right_on=['date', 'symbol'], validate='one_to_one').drop(columns=['date'])
    legacy_cutoff = pd.Timestamp(full_period['input_cutoff'])
    identity_detail['within_legacy_cutoff'] = identity_detail.signal_date.le(legacy_cutoff)
    identity_detail['membership'] = identity_detail['_merge'].astype(str).map(
        {'both': 'shared', 'left_only': 'production_only', 'right_only': 'research_only'})
    identity_detail = identity_detail.drop(columns=['_merge'])
    after = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    assert before == after, 'An input changed during the read-only audit'

    def count_reasons(frame):
        return {reason: int(frame.gate_reasons.str.split(';').apply(lambda reasons: reason in reasons).sum())
                for reason in sorted({part for text in frame.gate_reasons for part in text.split(';') if part})}

    result = {
        'status': 'PASS', 'scope': 'saved-artifact replay and cached-input diagnostic; no model fitting',
        'runtime': {'python': sys.version.split()[0], 'numpy': np.__version__, 'pandas': pd.__version__},
        'code_parity': parity,
        'canonical_selector_replay': {'rows': len(replay), 'all_detection_ids_match': True,
                                     'unique_signals': len(gate_detail), 'legacy_input_cutoff': str(legacy_cutoff.date()),
                                     'latest_legacy_tail_date': str(old_tail.date.max().date())},
        'canonical_current_gate': {'pass_unique_signals': int(gate_detail.current_gate_pass.sum()),
                                   'fail_unique_signals': int((~gate_detail.current_gate_pass).sum()),
                                   'failure_reasons_overlapping': count_reasons(gate_detail)},
        'completed_identity_comparison': identity_detail.groupby('membership').size().to_dict(),
        'production_only_gate': count_reasons(identity_detail[identity_detail.membership.eq('production_only')]),
        'production_only_still_gate_eligible': int(identity_detail.membership.eq('production_only').mul(identity_detail.current_gate_pass).sum()),
        'within_legacy_cutoff_membership': identity_detail[identity_detail.within_legacy_cutoff].groupby('membership').size().to_dict(),
        'research_only_after_legacy_cutoff': int((identity_detail.membership.eq('research_only') & ~identity_detail.within_legacy_cutoff).sum()),
        'production_gate_feature_probes': len(probe_indices), 'production_gate_matches_cached_contract': True,
        'teacher_probe': {'old_tail_rows': len(old_tail), 'rows_eligible_in_corrected_population': len(label_probe),
                          'changed_rank_rows': int((label_probe.future_rank - label_probe.future_rank_new).abs().gt(1e-12).sum()),
                          'changed_top025_label_rows': int(label_probe.y_top025.ne(label_probe.y_top025_new).sum()),
                          'scope_limit': 'Old Tail subset only; this is not a count of changes in the full training corpus.'},
        'cached_monthly_train_prediction_counts_verified': len(monthly_count_matches),
        'confirmed_changes': ['historical input snapshot', 'absolute price/volume gates use actual-session units',
                              'source-quality masks and market-breadth denominator', 'eligible population and teacher ranks',
                              'comparison cutoff and shared exclusion day'],
        'remaining': ['The contribution of each change to final model selection has not been isolated with controlled fitted-model replays.',
                      'Code/cache parity does not certify an exact replay from raw data through a fresh production model fit.',
                      'Future observed performance and cost/fill-sensitive results are not established by this historical diagnostic.'],
        'input_sha256': before, 'no_model_execution': True, 'no_production_mutations': True,
    }
    (HERE / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    identity_detail.sort_values(key).to_csv(HERE / 'identity_differences.csv', index=False, lineterminator='\n', date_format='%Y-%m-%d', float_format='%.12g')
    columns = ['date', 'symbol', 'prev_close', 'previous_actual_close', 'prev_volume', 'previous_actual_volume',
               'actual_close', 'actual_volume', 'current_gate_pass', 'gate_reasons']
    gate_detail.loc[~gate_detail.current_gate_pass, columns].sort_values(['date', 'symbol']).to_csv(
        HERE / 'canonical_gate_failures.csv', index=False, lineterminator='\n', date_format='%Y-%m-%d', float_format='%.12g')
    print(json.dumps({k: result[k] for k in ('status', 'canonical_selector_replay', 'canonical_current_gate',
                                             'production_only_gate', 'production_only_still_gate_eligible', 'teacher_probe')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
