const CONDITION_LABELS = {
  ema75: '終値が75日EMAより上',
  ema25: '終値が25日EMAより上',
  vol20: '出来高が20日平均の2.0倍以上',
  vol15: '出来高が20日平均の1.5倍以上',
  vol12: '出来高が20日平均の1.2倍以上',
  vol30: '出来高が20日平均の3.0倍以上',
  sbull: '陽線実体が0.5%以上',
  body1: '陽線実体が1.0%以上',
  body2: '陽線実体が2.0%以上',
  body_pullback10: '実体が10%以上（押し待ち警告）',
  body_overheat15: '実体が15%以上（過熱警告）',
  macdgc: 'MACDが3日以内にゴールデンクロス',
  macdpos: 'MACDヒストグラムがプラス',
  atr5: 'ATRが5%未満',
  atr3: 'ATRが3%未満',
  atr7: 'ATRが7%未満',
  hb20: '20日高値更新',
  lower_wick50: '下ヒゲ優位',
  pre_decline15: '20日高値から15%以上下落',
  stoch75: 'ストキャスが75以上',
  stoch60: 'ストキャスが60以上',
  rsi5070: 'RSIが50～70',
  rsi4060: 'RSIが40～60',
  bb80: 'ボリンジャーバンド位置が80%以上',
  ich_tk: '一目均衡表：転換線が基準線より上',
  ich_price_tenkan: '一目均衡表：終値が転換線より上',
  ich_price_kijun: '一目均衡表：終値が基準線より上',
  ich_cloud_above: '一目均衡表：終値が雲上限より上',
  ich_cloud_green: '一目均衡表：先行雲が陽転',
  ich_chikou: '一目均衡表：終値が26日前終値より上',
  ich_kumo_break: '一目均衡表：雲を上抜け',
  rci9_os: 'RCI（9日）が-50以下',
  rci26_os: 'RCI（26日）が-50以下',
  rci9_up: 'RCI（9日）が上向きに反転',
  pre_down3: '直近3日連続下落後',
  gap_up: 'ギャップアップ',
  bb_lower: 'ボリンジャーバンド位置が20%以下',
  cci_os: 'CCIが-100以下',
  smbull_seq2: '2連小陽線後',
  smbull_seq3: '3連小陽線後',
  vp_support: '価格帯別出来高：下値支持が優位',
  vp_no_overhead: '価格帯別出来高：上値のしこりが少ない',
  vp_near_poc: '価格帯別出来高：出来高集中価格（POC）付近',
};

function parseJson(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function parseList(value) {
  const parsed = parseJson(value);
  if (Array.isArray(parsed)) return parsed.map(item => String(item).trim()).filter(Boolean);
  if (Array.isArray(value)) return value.map(item => String(item).trim()).filter(Boolean);
  const text = String(value || '').trim();
  if (!text) return [];
  return text.split(/[,、+|]/).map(item => item.trim()).filter(Boolean);
}

function normalizeMode(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/^mode_/, '')
    .replace(/_mode$/, '');
}

function parseModes(value) {
  const parsed = parseJson(value);
  let values;
  if (Array.isArray(parsed)) {
    values = parsed;
  } else if (parsed && typeof parsed === 'object') {
    values = Object.entries(parsed).filter(([, enabled]) => Boolean(enabled)).map(([key]) => key);
  } else {
    values = parseList(value);
  }
  return new Set(values.map(normalizeMode).filter(Boolean));
}

function isSniperMode(mode) {
  const normalized = normalizeMode(mode);
  return normalized === 'sniper' || normalized.startsWith('sniper_');
}

function numericScore(value, maxScore = 6) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'string') {
    const match = value.match(/-?\d+(?:\.\d+)?/);
    value = match ? match[0] : Number.NaN;
  }
  const score = Number(value);
  if (!Number.isFinite(score)) return null;
  return Math.max(0, Math.min(maxScore, Math.trunc(score)));
}

function snapshotFilters(snapshot, key, features, conditions) {
  const explicit = snapshot && Array.isArray(snapshot[key]) ? snapshot[key] : [];
  const presenceKey = key === 'stableFilters' ? 'hasStableFilters' : 'hasSniperFilters';
  if ((snapshot && snapshot[presenceKey]) || explicit.length > 0) {
    return explicit.map(condition => CONDITION_LABELS[condition] || condition);
  }
  if (!features || typeof features !== 'object' || !Array.isArray(conditions)) return null;
  return conditions
    .filter(condition => Boolean(features[condition]))
    .map(condition => CONDITION_LABELS[condition] || condition);
}

function featureNumber(features, ...keys) {
  if (!features || typeof features !== 'object') return null;
  for (const key of keys) {
    const value = Number(features[key]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}

function applySignalSnapshot(result, snapshot, options = {}) {
  if (!snapshot) return result;
  const stableScore = numericScore(snapshot.stableScore, 6);
  if (!result) return null;

  const next = { ...result, signalSnapshotApplied: true };
  if (stableScore !== null) next.score = stableScore;

  const features = snapshot.features && typeof snapshot.features === 'object'
    ? snapshot.features
    : null;
  if (features) {
    next.indicators = { ...(next.indicators || {}), ...features };
    const atrPct = featureNumber(features, '_atr', 'atr_pct', 'atrPct');
    if (atrPct !== null) next.atrPct = atrPct;
  }

  const stableFilters = snapshotFilters(
    snapshot,
    'stableFilters',
    features,
    options.stableConditions,
  );
  if (stableFilters !== null) next.filters = stableFilters;

  const sniperMaxScore = Number(options.sniperMaxScore) || 6;
  if (snapshot.hasModes) {
    const sniperSelected = Array.from(snapshot.modes || []).some(isSniperMode);
    next.sniperEnabled = sniperSelected;
    next.sniperScore = sniperSelected ? sniperMaxScore : -1;
  } else if (numericScore(snapshot.sniperScore, sniperMaxScore) !== null) {
    next.sniperScore = numericScore(snapshot.sniperScore, sniperMaxScore);
    next.sniperEnabled = next.sniperScore === sniperMaxScore;
  }

  const sniperFilters = snapshotFilters(
    snapshot,
    'sniperFilters',
    features,
    options.sniperConditions,
  );
  if (sniperFilters !== null) next.sniperFilters = sniperFilters;
  return next;
}

function buildSnapshotOnlyResult(signal, snapshot, options = {}) {
  if (!signal || !snapshot || numericScore(snapshot.stableScore, 6) === null) return null;
  const features = snapshot.features && typeof snapshot.features === 'object'
    ? snapshot.features
    : {};
  const base = {
    symbol: signal.symbol,
    score: numericScore(snapshot.stableScore, 6),
    maxScore: 6,
    filters: [],
    sniperScore: -1,
    sniperFilters: [],
    sniperEnabled: false,
    indicators: features,
    atrPct: featureNumber(features, '_atr', 'atr_pct', 'atrPct'),
    signalDate: signal.date,
    signalPrice: signal.entry,
    futurePrice: signal.eval5bd !== null && Number.isFinite(Number(signal.eval5bd))
      ? Number(signal.eval5bd)
      : null,
    futureDiff: signal.perf5bd !== null && Number.isFinite(Number(signal.perf5bd))
      ? Number(signal.perf5bd).toFixed(2)
      : null,
    latestClose: null,
    change: '0.00',
    marketPhase: null,
  };
  return applySignalSnapshot(base, snapshot, options);
}

module.exports = {
  CONDITION_LABELS,
  applySignalSnapshot,
  buildSnapshotOnlyResult,
  isSniperMode,
  numericScore,
  parseJson,
  parseList,
  parseModes,
};
