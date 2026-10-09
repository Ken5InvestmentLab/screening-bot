// Evidence contract for newly generated Cloud forward snapshots only.
// This checks references and declared findings, not the truth of PDF contents.
const CAPITAL_RISK_REVIEW_VERSION = 1;
const DOCUMENT_KINDS = new Set(['financial_baseline', 'issuance', 'status', 'closure']);
const STATUSES = new Set(['outstanding', 'none_confirmed', 'unresolved']);
const INSTRUMENT_STATUSES = new Set(['outstanding', 'closed', 'unresolved']);

const CLOUD_CAPITAL_RISK_CONTRACT = [
  'Cloudでは足元の新材料と、過去に発行され今も残る資本政策リスクを別々に調査してください。直近45日の材料確認は維持しますが、残存リスクの調査に3か月・3年・5年などの年数上限を設けません。古い発行日だけを理由に除外しないでください。',
  '分析基準時点以前に公表された最新の公式決算資料・会社IR掲載の有価証券報告書/半期報告書から、新株予約権（ストックオプションを含む）・転換社債・その他の潜在株式を確認します。各回号の元の発行資料まで遡り、analysisCutoffまでの行使・条件変更・取得消却・失効と最新残高を照合してください。EDINET直接URLは使わず、会社IRまたはTDnet/JPXの一次資料本文を読みます。一部消却や一部行使を全数終了と扱わないでください。',
  '未行使の対象株数を、そのまま新株の発行数や希薄化率にしないでください。既行使分、自己株式の交付、株式分割・併合、残高の基準日と発行済株式数の分母時点を区別します。未公表・照合不能の数値は推定せずnullと理由を記録し、希薄化率の数字を出す場合は新株交付分と分母の根拠・時点が一致する場合だけにしてください。',
  '各レポートに内部capitalRiskReviewを追加します。公開7フィールドは維持し、残存リスクは注意点と必要な材料インパクトへ反映してください。capitalRiskReviewは{version:1, analysisCutoff:claimと同値, status:"outstanding"|"none_confirmed"|"unresolved", historyCheckedThrough:全期間を基準時点まで照合できた場合だけanalysisCutoff、できなければnull, documents:[], instruments:[], riskNote:"注意点へそのまま含める会社固有のリスク文"}です。',
  'documentsの各要素は{id,kind:"financial_baseline"|"issuance"|"status"|"closure",source:"official_ir"|"tdnet_jpx",title,url,publishedAt,contentReviewed:true,locator:"本文のページ/節",finding:"実際に確認した残高・条件・終了の記述"}。古い資料の公表時刻が未確認ならpublishedAtをYYYY-MM-DD、publishedAtPrecisionをdate_onlyとします（基準日当日は日時確認が必要）。補足資料を内部に多数持つことはできますが、本文で根拠に使う主要資料は通常のdisclosuresと開示リンクにも記載し、既存URL整合契約を守ります。',
  'instrumentsは回号ごとに{id,type:"warrant"|"convertible_bond"|"other_equity_financing",status:"outstanding"|"closed"|"unresolved",issueDocumentId,statusDocumentId,asOfDate:"YYYY-MM-DD",remainingUnderlyingShares:一次資料で確認した未行使対象株数またはnull,quantityUncertainty:nullなら未確認理由,summary:"確認した会社固有の条件と残存リスク"}。outstanding/closedの判定には発行原資料と残高/終了資料を必須とし、closedではremainingUnderlyingShares:0とclosureKind:"exercised"|"cancelled"|"expired"が必要です。発行原資料・最新状態のどちらかが確認できなければunresolvedにします。',
  'none_confirmedは、最新決算等のfinancial_baseline本文と資本政策履歴を基準時点まで確認し、未解決の回号がなく、全潜在株式の残存なしを明示する根拠がある場合だけ使います。そのときabsenceEvidence:{documentId,scope:"all_dilutive_instruments",statement:"本文で確認した残存なしの記述"}を付けます。最近の発行/行使IRが見つからないだけでは残存なしにしません。',
  '確認できない場合はstatus:unresolved、unresolvedReasonに具体的な不足根拠を記録し、riskNoteを注意点へそのまま入れて、希薄化リスクの有無を確認できなかったことを明示します。資料不足をリスクなし・残存ゼロへ置き換えず、検索や最新残高確認を省略しないでください。',
].join('\n');

function nonempty(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function timestamp(value, label) {
  const match = String(value).match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$/);
  if (!match) throw new Error(`${label} requires a timestamp with seconds and timezone`);
  const seconds = Date.parse(`${match[1]}${match[3]}`);
  const offset = match[3] === 'Z' ? 0 : (match[3][0] === '+' ? 1 : -1) * (Number(match[3].slice(1, 3)) * 60 + Number(match[3].slice(4, 6)));
  if (!Number.isFinite(seconds) || new Date(seconds + offset * 60_000).toISOString().slice(0, 19) !== match[1]) {
    throw new Error(`${label} requires a valid calendar timestamp`);
  }
  return { nanoseconds: BigInt(seconds) * 1_000_000n + BigInt((match[2] || '').padEnd(9, '0')),
    day: new Date(seconds + 9 * 60 * 60_000).toISOString().slice(0, 10) };
}

function date(value, label) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value)) || !Number.isFinite(Date.parse(`${value}T00:00:00Z`)) ||
      new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) !== value) {
    throw new Error(`${label} requires a valid YYYY-MM-DD date`);
  }
  return value;
}

function validatePrimaryDocuments(rows, analysisCutoff, kinds, label) {
  const fail = message => { throw new Error(`${label}: ${message}`); };
  const cutoff = timestamp(analysisCutoff, `${label} analysisCutoff`);
  if (!Array.isArray(rows)) fail('documents must be an array');
  const documents = new Map();
  for (const document of rows) {
    if (!document || !nonempty(document.id) || documents.has(document.id) || !kinds.has(document.kind) ||
        !['official_ir', 'tdnet_jpx'].includes(document.source) || document.contentReviewed !== true ||
        !['title', 'locator', 'finding'].every(key => nonempty(document[key]))) fail('each document requires a unique id, primary source, reviewed body and located finding');
    let url;
    try { url = new URL(document.url); } catch { fail('document URL must be https'); }
    if (url.protocol !== 'https:' || /(^|\.)edinet-fsa\.go\.jp$/.test(url.hostname)) fail('use official IR or TDnet/JPX https documents, not direct EDINET');
    let publication;
    if (document.publishedAtPrecision === 'date_only') {
      const day = /^\d{4}-\d{2}-\d{2}$/.test(String(document.publishedAt))
        ? date(document.publishedAt, 'document publishedAt') : timestamp(document.publishedAt, 'document publishedAt').day;
      if (day >= cutoff.day) fail('date-only documents must predate the analysis-start JST date');
      publication = { day, nanoseconds: null };
    } else {
      publication = timestamp(document.publishedAt, 'document publishedAt');
      if (publication.nanoseconds > cutoff.nanoseconds) fail('post-cutoff document rejected');
    }
    documents.set(document.id, { ...document, publication });
  }
  return documents;
}

function validateCapitalRiskReview(report, alert) {
  const review = report.capitalRiskReview;
  const fail = message => { throw new Error(`capitalRiskReview ${alert.alertId}: ${message}`); };
  if (!review || review.version !== CAPITAL_RISK_REVIEW_VERSION || !STATUSES.has(review.status)) fail('requires version 1 and a supported status');
  if (review.analysisCutoff !== alert.analysisCutoff || review.analysisCutoff !== report.analysisCutoff) fail('analysisCutoff must match claim and report');
  const cutoff = timestamp(review.analysisCutoff, 'capitalRiskReview analysisCutoff');
  if (!Array.isArray(review.documents) || !Array.isArray(review.instruments)) fail('documents and instruments must be arrays');
  if (review.historyCheckedThrough !== null && review.historyCheckedThrough !== review.analysisCutoff) fail('historyCheckedThrough must equal analysisCutoff or null');
  const documents = validatePrimaryDocuments(review.documents, review.analysisCutoff, DOCUMENT_KINDS, `capitalRiskReview ${alert.alertId}`);
  const ids = new Set();
  for (const instrument of review.instruments) {
    if (!instrument || !nonempty(instrument.id) || ids.has(instrument.id) ||
        !['warrant', 'convertible_bond', 'other_equity_financing'].includes(instrument.type) ||
        !INSTRUMENT_STATUSES.has(instrument.status) || !nonempty(instrument.summary)) fail('each instrument requires a unique id, type, status and company-specific summary');
    ids.add(instrument.id);
    const quantity = instrument.remainingUnderlyingShares;
    if (quantity !== null && (!Number.isSafeInteger(quantity) || quantity < 0)) fail('remainingUnderlyingShares must be a nonnegative integer or null');
    if (quantity === null && !nonempty(instrument.quantityUncertainty)) fail('unknown remaining quantity requires quantityUncertainty');
    const issue = documents.get(instrument.issueDocumentId);
    const state = documents.get(instrument.statusDocumentId);
    if (instrument.status === 'unresolved') {
      if (!nonempty(instrument.unresolvedReason)) fail('an unresolved instrument requires its missing-evidence reason');
      continue;
    }
    if (!issue || issue.kind !== 'issuance' || !state || !['financial_baseline', 'status', 'closure'].includes(state.kind)) fail('resolved instruments require issuance and current-status document references');
    if (state.publication.day < issue.publication.day ||
        (state.publication.nanoseconds !== null && issue.publication.nanoseconds !== null && state.publication.nanoseconds < issue.publication.nanoseconds)) fail('status document cannot precede issuance');
    const asOfDate = date(instrument.asOfDate, 'instrument asOfDate');
    if (asOfDate > cutoff.day || asOfDate > state.publication.day || asOfDate < issue.publication.day) fail('instrument balance date must be between issuance and the pre-cutoff status document');
    if (instrument.status === 'outstanding' && (quantity === 0 || state.kind === 'closure')) fail('outstanding instruments cannot have zero balance or only closure evidence');
    if (instrument.status === 'closed' && (quantity !== 0 || state.kind !== 'closure' || !['exercised', 'cancelled', 'expired'].includes(instrument.closureKind))) fail('closed instruments require explicit full closure evidence and zero remaining balance');
  }
  if (review.status !== 'unresolved') {
    if (review.historyCheckedThrough !== review.analysisCutoff || ![...documents.values()].some(document => document.kind === 'financial_baseline')) fail('a resolved verdict requires latest official financial baseline and history checked through cutoff');
    if (review.instruments.some(instrument => instrument.status === 'unresolved')) fail('unresolved instruments prohibit a resolved verdict');
    if ([...documents.values()].some(document => document.kind === 'issuance' &&
        !review.instruments.some(instrument => instrument.issueDocumentId === document.id))) fail('every reviewed issuance must be accounted for in instruments');
  }
  if (review.status === 'none_confirmed') {
    const absence = review.absenceEvidence;
    const document = documents.get(absence?.documentId);
    if (review.instruments.some(instrument => instrument.status !== 'closed') || !document ||
        !['financial_baseline', 'status'].includes(document.kind) || absence.scope !== 'all_dilutive_instruments' || !nonempty(absence.statement)) fail('none_confirmed requires explicit all-instrument absence evidence; no recent IR is insufficient');
  } else {
    if (review.status === 'outstanding' && !review.instruments.some(instrument => instrument.status === 'outstanding')) fail('outstanding verdict requires a remaining instrument');
    if (review.status === 'unresolved' && !nonempty(review.unresolvedReason)) fail('unresolved verdict requires missing-evidence reason');
    const notes = (report.fields || []).find(field => field.name === '注意点')?.value;
    if (!nonempty(review.riskNote) || typeof notes !== 'string' || !notes.includes(review.riskNote)) fail('remaining or unresolved capital risk must appear in 注意点');
  }
  return review.status;
}

function validateClaimCapitalRiskReviews(claim, reports, state = {}) {
  // Only new analysis stamps opt into this contract. Legacy import retries and
  // historical reports remain governed by their original validated contract.
  const required = (claim.alerts || []).filter(alert => {
    const versions = [claim.capitalRiskReviewVersion, alert.capitalRiskReviewVersion, state.claims?.[alert.alertId]?.capitalRiskReviewVersion].filter(version => version !== undefined);
    if (versions.some(version => version !== CAPITAL_RISK_REVIEW_VERSION)) throw new Error('unsupported capitalRiskReviewVersion');
    return versions.includes(CAPITAL_RISK_REVIEW_VERSION);
  });
  for (const alert of required) {
    if (alert.signalType !== 'WEAK_EARLY_BETA') throw new Error('capital risk contract applies to Cloud forward claims only');
    const matches = reports.filter(report => report.alertId === alert.alertId);
    if (matches.length !== 1) throw new Error(`capitalRiskReview requires one report for ${alert.alertId}`);
    validateCapitalRiskReview(matches[0], alert);
  }
  return required.length;
}

export { CAPITAL_RISK_REVIEW_VERSION, CLOUD_CAPITAL_RISK_CONTRACT, validateCapitalRiskReview, validateClaimCapitalRiskReviews,
  validatePrimaryDocuments, timestamp, date };
