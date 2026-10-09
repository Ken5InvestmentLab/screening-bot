import { validatePrimaryDocuments, timestamp, date } from './weak-early-beta-capital-risk.mjs';

const LONG_TERM_MATERIAL_REVIEW_VERSION = 1;
const LONG_TERM_MATERIAL_CATEGORIES = [
  'alliances', 'orders_contracts', 'investment_capacity', 'products_services',
  'approvals_subsidies', 'restructuring', 'legal_regulatory', 'contract_changes',
];
const DOCUMENT_KINDS = new Set(['financial_baseline', 'original_announcement', 'progress']);
const ITEM_STATUSES = new Set(['planned', 'in_progress', 'contributing', 'delayed', 'ended', 'unresolved']);
const ACTIVE_STATUSES = new Set(['planned', 'in_progress', 'contributing', 'delayed']);

const CLOUD_LONG_TERM_MATERIAL_CONTRACT = [
  'Cloudの長期確認は新株予約権だけに限定しません。好材料・悪材料の両方について、過去の提携/大型受注/契約/設備投資/生産能力/新製品/許認可/補助金/事業再編/M&A/訴訟/規制/契約解除等が現在も事業や財務へ意味を持つかを調べます。年数上限は設けず、最新の公式決算と事業進捗を起点に原発表と、その後の進捗・開始・売上利益への反映・延期・撤回・終了をanalysisCutoffまで辿ってください。資本リスクのcapitalRiskReviewも別途維持します。',
  '会社が公表した開始/収益化予定と実際の売上・利益寄与を区別してください。「公表予定の時期に達しているが、寄与実績は未確認」は根拠とともに記載できます。年月が経過しただけで収益寄与を断定したり、未公表の将来業績を予測したりしません。受注額・補助金採択・許認可・提携合意・設備完成だけを売上/利益計上と扱わず、実績反映は会社の公表本文が確認できる場合だけcontributingにします。',
  '単なる古い開示の列挙で終えず、会社の当時/最新の公表タイムラインと開始・稼働等の確認から、分析基準時点における意味を説明してください。例えば「公表計画どおりなら今は収益化期に近い/到達しているが、直近の寄与実績は確認できない」という条件付きの見立ては記載できます。予定が年月/年度だけでも、その公表予定と現在の時期の関係を文で説明でき、架空の正確な日付や未公表業績予測を作る必要はありません。',
  '公開7フィールドは維持し、足元材料には今確認できた変化、ファンダ要点には長期案件の現在の事業/財務上の意味、注意点には延期や寄与未確認などを会社固有の記述で書き分けます。古い好材料も終了・取消・既反映ならその事実を確認し、現在の新材料として再掲しません。本文で重要な根拠に使う原発表/進捗資料は通常のdisclosuresと開示リンクにも記録します。',
  '内部longTermMaterialReviewを{version:1,analysisCutoff:claimと同値,conclusion:"active_materials"|"no_relevant_found"|"unresolved",historyCheckedThrough:基準時点まで照合完了ならanalysisCutoff、それ以外null,reviewedCategories:実際に確認したカテゴリの配列,reviewScopeNote:"確認した最新決算と会社固有の事業/開示履歴の範囲",documents:[],items:[]}として全レポートへ追加します。カテゴリはalliances,orders_contracts,investment_capacity,products_services,approvals_subsidies,restructuring,legal_regulatory,contract_changesです。全カテゴリを確認できなければconclusion:unresolvedとして不足理由を残してください。',
  'documentsはcapitalRiskReviewと同じ一次資料のid/source/title/url/publishedAt/contentReviewed:true/locator/finding形式、kindはfinancial_baseline（最新公式決算等）,original_announcement（原発表）,progress（続報）。公表日時と本文確認は同じcutoff規則です。別レビューの同じ資料をここに再記録して構いません。',
  'itemsは{id,category,direction:"positive"|"negative"|"mixed",status:"planned"|"in_progress"|"contributing"|"delayed"|"ended"|"unresolved",originalDocumentId,latestProgressDocumentId,currentAssessment:"現在の意味を公開本文にも含める一文"}。確認済み案件は原発表と最新続報の参照を必須にします。原発表だけで、その後の続報がない場合は最新決算と履歴を照合したうえでplannedに留め、latestProgressDocumentIdを原発表自身にできます。原発表・進捗のどちらかが確認できなければunresolvedとします。',
  '会社の公表予定は必要な案件でreportedTiming:{documentId,statement:"会社が述べた開始/収益化予定の原文内容",dueDate:"会社が明示したYYYY-MM-DDまたはnull"}を記録します。年月/年度だけの予定から日付を創作しません。timingReachedButContributionUnconfirmed:trueは、明示日付が基準日の前日以前に達しており実績反映が確認できない場合だけ付け、riskNoteを注意点へそのまま入れてください。予定が曖昧なら予定内容と実績未確認を本文に書き、到達フラグをtrueにしません。',
  'contributingにはactualContribution:{documentId,metric:"revenue"|"profit",basis:"reported_actual",statement:"会社が公表した売上/利益への実績反映"}が必須です。会社予想や売上反映予定は実績根拠にできません。確認できなければplanned/in_progressまたはunresolvedとし、actualContributionを入れません。unresolved案件はunresolvedReasonとriskNoteを持ち、riskNoteを注意点へそのまま含めます。',
  'no_relevant_foundは、全カテゴリと最新公式決算・事業進捗・開示履歴を基準時点まで確認して、現在の分析に関係する継続案件が見つからなかったという調査結果です。世の中に材料が全くないと断定する値ではありません。itemsは空でもよく、確認して終了済みの案件を記録できます。確認不足をこの値へ置き換えません。conclusion:unresolvedならunresolvedReasonとriskNoteを必須にし、注意点へ確認不足を明示してください。',
].join('\n');

const nonempty = value => typeof value === 'string' && value.trim().length > 0;

function validateLongTermMaterialReview(report, alert) {
  const review = report.longTermMaterialReview;
  const fail = message => { throw new Error(`longTermMaterialReview ${alert.alertId}: ${message}`); };
  if (!review || review.version !== LONG_TERM_MATERIAL_REVIEW_VERSION ||
      !['active_materials', 'no_relevant_found', 'unresolved'].includes(review.conclusion)) fail('requires version 1 and a supported conclusion');
  if (review.analysisCutoff !== alert.analysisCutoff || review.analysisCutoff !== report.analysisCutoff) fail('analysisCutoff must match claim and report');
  const cutoff = timestamp(review.analysisCutoff, 'longTermMaterialReview analysisCutoff');
  if (review.historyCheckedThrough !== null && review.historyCheckedThrough !== review.analysisCutoff) fail('historyCheckedThrough must equal analysisCutoff or null');
  if (!Array.isArray(review.items) || !Array.isArray(review.reviewedCategories) || !nonempty(review.reviewScopeNote)) fail('requires items, reviewedCategories and a company-specific reviewScopeNote');
  const categories = new Set(review.reviewedCategories);
  if (categories.size !== review.reviewedCategories.length || [...categories].some(category => !LONG_TERM_MATERIAL_CATEGORIES.includes(category))) fail('reviewedCategories must be distinct supported categories');
  const documents = validatePrimaryDocuments(review.documents, review.analysisCutoff, DOCUMENT_KINDS, `longTermMaterialReview ${alert.alertId}`);
  const fields = new Map((report.fields || []).map(field => [field.name, field.value]));
  const notes = fields.get('注意点');
  const publicText = ['足元材料', 'ファンダ要点', '注意点'].map(name => fields.get(name) || '').join('\n');
  const requireRiskNote = (riskNote, label) => {
    if (!nonempty(riskNote) || typeof notes !== 'string' || !notes.includes(riskNote)) fail(`${label} must appear in 注意点`);
  };
  const ids = new Set();
  for (const item of review.items) {
    if (!item || !nonempty(item.id) || ids.has(item.id) || !categories.has(item.category) ||
        !['positive', 'negative', 'mixed'].includes(item.direction) || !ITEM_STATUSES.has(item.status) || !nonempty(item.currentAssessment)) fail('each item requires a unique id, reviewed category, direction, status and currentAssessment');
    ids.add(item.id);
    const original = documents.get(item.originalDocumentId);
    const progress = documents.get(item.latestProgressDocumentId);
    if (item.status === 'unresolved') {
      if (!nonempty(item.unresolvedReason)) fail('unresolved item requires its missing-evidence reason');
      requireRiskNote(item.riskNote, 'unresolved item risk');
    } else {
      if (!original || original.kind !== 'original_announcement' || !progress ||
          !['financial_baseline', 'progress'].includes(progress.kind) && !(item.status === 'planned' && progress.id === original.id)) fail('resolved items require original and latest progress references');
      if (progress.publication.day < original.publication.day ||
          progress.publication.nanoseconds !== null && original.publication.nanoseconds !== null && progress.publication.nanoseconds < original.publication.nanoseconds) fail('progress cannot precede original announcement');
    }
    if (item.status !== 'ended' && !publicText.includes(item.currentAssessment)) fail('active or unresolved currentAssessment must appear in the public analysis');
    if (item.reportedTiming !== undefined) {
      const timing = item.reportedTiming;
      const timingDocument = documents.get(timing?.documentId);
      if (!timing || !timingDocument || !nonempty(timing.statement)) fail('reported timing requires a reviewed document reference and company statement');
      if (original && (timingDocument.publication.day < original.publication.day ||
          timingDocument.publication.nanoseconds !== null && original.publication.nanoseconds !== null && timingDocument.publication.nanoseconds < original.publication.nanoseconds)) fail('reported timing evidence cannot predate the original announcement');
      if (timing.dueDate !== null) date(timing.dueDate, 'reportedTiming dueDate');
    }
    if (item.actualContribution !== undefined && item.status !== 'contributing') fail('unconfirmed statuses cannot carry actualContribution');
    if (item.status === 'contributing') {
      const actual = item.actualContribution;
      const evidence = documents.get(actual?.documentId);
      if (!actual || actual.basis !== 'reported_actual' || !['revenue', 'profit'].includes(actual.metric) || !nonempty(actual.statement) ||
          !evidence || !['financial_baseline', 'progress'].includes(evidence.kind)) fail('contributing requires reported actual revenue/profit evidence, not a schedule or original promise');
      if (evidence.publication.day < original.publication.day ||
          evidence.publication.nanoseconds !== null && original.publication.nanoseconds !== null && evidence.publication.nanoseconds < original.publication.nanoseconds) fail('contribution evidence cannot predate the original announcement');
    }
    if (item.timingReachedButContributionUnconfirmed !== undefined && typeof item.timingReachedButContributionUnconfirmed !== 'boolean') fail('timingReachedButContributionUnconfirmed must be boolean');
    if (item.timingReachedButContributionUnconfirmed === true) {
      if (!item.reportedTiming?.dueDate || item.reportedTiming.dueDate >= cutoff.day || item.status === 'contributing' || item.status === 'ended') fail('elapsed timing requires a disclosed past due date and no confirmed contribution');
      requireRiskNote(item.riskNote, 'unconfirmed contribution risk');
    }
  }
  if (review.conclusion === 'unresolved') {
    if (!nonempty(review.unresolvedReason)) fail('unresolved review requires a missing-evidence reason');
    requireRiskNote(review.riskNote, 'unresolved review risk');
  } else {
    if (review.historyCheckedThrough !== review.analysisCutoff || categories.size !== LONG_TERM_MATERIAL_CATEGORIES.length ||
        ![...documents.values()].some(document => document.kind === 'financial_baseline')) fail('a completed review requires all categories, latest official financial baseline and history through cutoff');
    if (review.items.some(item => item.status === 'unresolved')) fail('unresolved items prohibit a completed conclusion');
    if ([...documents.values()].some(document => document.kind === 'original_announcement' &&
        !review.items.some(item => item.originalDocumentId === document.id))) fail('every reviewed original announcement must be accounted for in items');
    const active = review.items.some(item => ACTIVE_STATUSES.has(item.status));
    if (review.conclusion === 'active_materials' && !active) fail('active_materials requires a continuing item');
    if (review.conclusion === 'no_relevant_found' && active) fail('continuing items prohibit no_relevant_found');
  }
  return review.conclusion;
}

function validateClaimLongTermMaterialReviews(claim, reports, state = {}) {
  const required = (claim.alerts || []).filter(alert => {
    const versions = [claim.longTermMaterialReviewVersion, alert.longTermMaterialReviewVersion,
      state.claims?.[alert.alertId]?.longTermMaterialReviewVersion].filter(version => version !== undefined);
    if (versions.some(version => version !== LONG_TERM_MATERIAL_REVIEW_VERSION)) throw new Error('unsupported longTermMaterialReviewVersion');
    return versions.includes(LONG_TERM_MATERIAL_REVIEW_VERSION);
  });
  for (const alert of required) {
    if (alert.signalType !== 'WEAK_EARLY_BETA') throw new Error('long-term material contract applies to Cloud forward claims only');
    const matches = reports.filter(report => report.alertId === alert.alertId);
    if (matches.length !== 1) throw new Error(`longTermMaterialReview requires one report for ${alert.alertId}`);
    validateLongTermMaterialReview(matches[0], alert);
  }
  return required.length;
}

export { LONG_TERM_MATERIAL_REVIEW_VERSION, LONG_TERM_MATERIAL_CATEGORIES, CLOUD_LONG_TERM_MATERIAL_CONTRACT,
  validateLongTermMaterialReview, validateClaimLongTermMaterialReviews };
