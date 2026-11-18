import {isObject} from './cloud-membership';
import {DATASET_ID,digest,validateManifest,type NewADatabase} from './new-a-private';
import {validateTrial,validateView} from './new-a-preferences';

export const OPENING_OBSERVATION_PATH = '/api/cloud/new-a-finite/opening-observation';
const hash = /^[a-f0-9]{64}$/;
const memberId = /^cloud_[a-f0-9]{64}$/;
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const instantPattern = /^(\d{4}-\d{2}-\d{2})T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,9})?(?:Z|[+-]\d{2}:[0-5]\d)$/;
const jstOffset = 9 * 60 * 60 * 1000;
const maxRows = 500;
const maxBytes = 96 * 1024;
const encoder = new TextEncoder();

const openingStatuses = [
 'AWAITING_FIRST_TRADE', 'FIRST_TRADE_VERIFIED', 'PROVISIONAL_ELIGIBLE',
 'PROVISIONAL_SKIPPED', 'PENDING_PORTFOLIO', 'RECONCILE',
] as const;
type OpeningStatus = typeof openingStatuses[number];
type PublicRow = {
 symbol: string;
 candidate_date: string;
 status: OpeningStatus;
 trade_at?: string;
 actual_price_yen?: number;
};
type StoredRow = PublicRow & {episode_id: number};
type OpeningBasis = {
 target_date: string;
 dataset_id: string;
 pointer_revision: number;
 manifest_sha256: string;
 preferences_revision: number;
};
type ObservationInput = OpeningBasis & {
 expected_revision: number;
 source_receipt_sha256: string;
 rows: StoredRow[];
};
type BasisRow = Omit<OpeningBasis,'target_date'> & {
 source_version: string;
 manifest_json: string;
 preferences_json: string;
 view_preferences_json: string|null;
 view_revision: number|null;
 revision: number|null;
 updated_at: string|null;
 source_receipt_sha256: string|null;
 rows_json: string|null;
 rows_sha256: string|null;
};
type OpeningObservation = {state: 'empty'; target_date: string} |
 {state: 'ready'; target_date: string; updated_at: string; revision: number; rows: PublicRow[]};

function validDay(value: unknown): value is string {
 if (typeof value !== 'string' || !datePattern.test(value)) return false;
 const date = new Date(value + 'T00:00:00.000Z');
 return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function jstDay(now: number): string {
 return new Date(now + jstOffset).toISOString().slice(0, 10);
}

function positive(value: unknown): value is number {
 return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

function instant(value: unknown): number | null {
 if (typeof value !== 'string') return null;
 const match = instantPattern.exec(value);
 if (!match || !validDay(match[1])) return null;
 const time = Date.parse(value);
 return Number.isFinite(time) ? time : null;
}

function validMorningTrade(value: unknown, target: string, updated: number): value is string {
 const time = instant(value);
 if (time === null || time > updated || jstDay(time) !== target) return false;
 const local = new Date(time + jstOffset).toISOString().slice(11, 23);
 return local >= '09:00:00.000' && local <= '11:30:00.000';
}

function validateRows(value: unknown, asOf: string, target: string, updated: number): StoredRow[] {
 if (!Array.isArray(value) || value.length > maxRows) throw Error('opening_rows');
 const pairs = new Set<string>();
 return value.map(row => {
  if (!isObject(row) || Object.keys(row).some(key =>
   !['symbol','candidate_date','episode_id','status','trade_at','actual_price_yen'].includes(key)) ||
   typeof row.symbol !== 'string' || !/^[0-9A-Z]{4}$/.test(row.symbol) ||
   !validDay(row.candidate_date) || row.candidate_date > asOf || !positive(row.episode_id) ||
   !openingStatuses.includes(row.status as OpeningStatus)) throw Error('opening_row');
  const status = row.status as OpeningStatus;
  const pair = row.symbol + '|' + row.candidate_date;
  if (pairs.has(pair)) throw Error('opening_row_duplicate');
  pairs.add(pair);
  const result = {symbol: row.symbol, candidate_date: row.candidate_date, episode_id: row.episode_id, status};
  const hasTrade = Object.hasOwn(row, 'trade_at') || Object.hasOwn(row, 'actual_price_yen');
  if (hasTrade) {
   if (status === 'AWAITING_FIRST_TRADE' || !validMorningTrade(row.trade_at, target, updated) ||
    typeof row.actual_price_yen !== 'number' || row.actual_price_yen <= 0 || row.actual_price_yen > 1e9 ||
    !/^\d+(?:\.\d{1,2})?$/.test(String(row.actual_price_yen))) throw Error('opening_trade');
   return {...result, trade_at: row.trade_at, actual_price_yen: row.actual_price_yen};
  }
  if (status === 'FIRST_TRADE_VERIFIED' || status === 'PROVISIONAL_ELIGIBLE') throw Error('opening_trade_required');
  return result;
 });
}

// A single read binds the displayed observation to the active publication and current saved revision.
async function basisRow(db: NewADatabase, member: string, target: string, observationRequired: boolean): Promise<BasisRow|null> {
 const observationJoin = observationRequired ? 'JOIN' : 'LEFT JOIN';
 return db.prepare(`
  SELECT d.dataset_id,d.source_version,d.manifest_json,d.manifest_sha256,
   p.revision AS pointer_revision,t.revision AS preferences_revision,t.preferences_json,
   v.preferences_json AS view_preferences_json,v.revision AS view_revision,
   o.revision,o.updated_at,o.source_receipt_sha256,o.rows_json,o.rows_sha256
  FROM new_a_active_pointer p
  JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id AND d.status='READY'
  JOIN new_a_finite_trial_preferences t ON t.member_id=? AND t.schema_version=1
  ${observationJoin} new_a_opening_observations o ON o.member_id=t.member_id AND o.target_date=?
   AND o.dataset_id=d.dataset_id AND o.pointer_revision=p.revision
   AND o.manifest_sha256=d.manifest_sha256 AND o.preferences_revision=t.revision
  LEFT JOIN new_a_finite_trial_preferences v ON v.member_id='new-a-view:v1:' || t.member_id
  WHERE p.pointer_key='owner'
 `).bind(member, target).first<BasisRow>();
}

async function previousMarketDay(row: BasisRow, target: string): Promise<string|null> {
 if (!DATASET_ID.test(row.dataset_id) || !positive(row.pointer_revision) || !positive(row.preferences_revision) ||
  !hash.test(row.manifest_sha256) || await digest(row.manifest_json) !== row.manifest_sha256)
  throw Error('opening_basis_integrity');
 const manifest = validateManifest(JSON.parse(row.manifest_json));
 validateTrial(JSON.parse(row.preferences_json));
 if (row.view_preferences_json !== null) {
  if (!positive(row.view_revision) || row.view_revision > row.preferences_revision) throw Error('opening_view_revision');
  validateView(JSON.parse(row.view_preferences_json));
 }
 if (!validDay(manifest.as_of) || manifest.source_version !== row.source_version)
  throw Error('opening_manifest_integrity');
 const limits = manifest.input_header.limits;
 return manifest.live === true && manifest.as_of < target && isObject(limits) &&
  limits.completeThrough === manifest.as_of && limits.nextPlannedSession === target ? manifest.as_of : null;
}

export async function readOpeningObservation(db: NewADatabase, member: string, now = Date.now()): Promise<OpeningObservation> {
 if (!memberId.test(member)) throw Error('opening_member');
 const target_date = jstDay(now);
 const empty = {state: 'empty', target_date} as const;
 const row = await basisRow(db, member, target_date, true);
 if (row?.revision == null) return empty;
 const asOf = await previousMarketDay(row, target_date);
 if (!asOf) return empty;
 const updated = instant(row.updated_at);
 if (!positive(row.revision) || !row.updated_at || updated === null || updated > now ||
  jstDay(updated) !== target_date || !row.source_receipt_sha256 || !hash.test(row.source_receipt_sha256) ||
  !row.rows_json || encoder.encode(row.rows_json).byteLength > maxBytes || !row.rows_sha256 ||
  !hash.test(row.rows_sha256) || await digest(row.rows_json) !== row.rows_sha256) throw Error('opening_observation_integrity');
 const rows = validateRows(JSON.parse(row.rows_json), asOf, target_date, updated)
  .map(({symbol,candidate_date,status,trade_at,actual_price_yen}): PublicRow =>
   trade_at === undefined ? {symbol,candidate_date,status} : {symbol,candidate_date,status,trade_at,actual_price_yen});
 return {state: 'ready', target_date, updated_at: row.updated_at, revision: row.revision, rows};
}

// Internal persistence entry point. The operator must have verified receipt provenance
// and resolved member from the fixed Cloud owner before supplying an observation.
// No Worker HTTP route accepts writes or an alternate member.
export async function saveOpeningObservation(
 db: NewADatabase, member: string, input: ObservationInput, now = Date.now(),
): Promise<{revision: number}|null> {
 if (!memberId.test(member) || input.target_date !== jstDay(now) || !DATASET_ID.test(input.dataset_id) ||
  !positive(input.pointer_revision) || !hash.test(input.manifest_sha256) || !positive(input.preferences_revision) ||
  !Number.isSafeInteger(input.expected_revision) || input.expected_revision < 0 ||
  input.expected_revision >= Number.MAX_SAFE_INTEGER || !hash.test(input.source_receipt_sha256))
  throw Error('opening_input');
 const current = await basisRow(db, member, input.target_date, false);
 if (!current || current.dataset_id !== input.dataset_id || current.pointer_revision !== input.pointer_revision ||
  current.manifest_sha256 !== input.manifest_sha256 || current.preferences_revision !== input.preferences_revision ||
  (current.revision ?? 0) !== input.expected_revision) return null;
 const asOf = await previousMarketDay(current, input.target_date);
 if (!asOf) return null;
 const updatedAt = new Date(now).toISOString();
 const rowsJson = JSON.stringify(validateRows(input.rows, asOf, input.target_date, now));
 if (encoder.encode(rowsJson).byteLength > maxBytes) throw Error('opening_rows_size');
 const rowsSha = await digest(rowsJson);
 // Recheck every revocable basis in the same statement as the revision CAS.
 return db.prepare(`
  WITH next(member_id,target_date,dataset_id,pointer_revision,manifest_sha256,preferences_revision,
   expected_revision,updated_at,source_receipt_sha256,rows_json,rows_sha256) AS (
   VALUES(?,?,?,?,?,?,?,?,?,?,?)
  )
  INSERT INTO new_a_opening_observations(member_id,target_date,dataset_id,pointer_revision,manifest_sha256,
   preferences_revision,revision,updated_at,source_receipt_sha256,rows_json,rows_sha256)
  SELECT n.member_id,n.target_date,n.dataset_id,n.pointer_revision,n.manifest_sha256,n.preferences_revision,
   n.expected_revision+1,n.updated_at,n.source_receipt_sha256,n.rows_json,n.rows_sha256
  FROM next n
  JOIN new_a_active_pointer p ON p.pointer_key='owner' AND p.dataset_id=n.dataset_id AND p.revision=n.pointer_revision
  JOIN new_a_private_datasets d ON d.dataset_id=p.dataset_id AND d.status='READY'
   AND d.manifest_sha256=n.manifest_sha256 AND d.manifest_json=?
  JOIN new_a_finite_trial_preferences t ON t.member_id=n.member_id
   AND t.schema_version=1 AND t.revision=n.preferences_revision AND t.preferences_json=?
  LEFT JOIN new_a_finite_trial_preferences v ON v.member_id='new-a-view:v1:' || t.member_id
  LEFT JOIN new_a_opening_observations o ON o.member_id=n.member_id AND o.target_date=n.target_date
   AND o.dataset_id=n.dataset_id AND o.pointer_revision=n.pointer_revision
   AND o.manifest_sha256=n.manifest_sha256 AND o.preferences_revision=n.preferences_revision
  WHERE v.preferences_json IS ? AND v.revision IS ? AND COALESCE(o.revision,0)=n.expected_revision
   AND (o.updated_at IS NULL OR o.updated_at<=n.updated_at)
  ON CONFLICT(member_id,target_date,dataset_id,pointer_revision,manifest_sha256,preferences_revision) DO UPDATE SET
   revision=excluded.revision,updated_at=excluded.updated_at,source_receipt_sha256=excluded.source_receipt_sha256,
   rows_json=excluded.rows_json,rows_sha256=excluded.rows_sha256
  RETURNING revision
 `).bind(member, input.target_date, input.dataset_id, input.pointer_revision, input.manifest_sha256,
  input.preferences_revision, input.expected_revision, updatedAt, input.source_receipt_sha256,
  rowsJson, rowsSha, current.manifest_json, current.preferences_json,
  current.view_preferences_json, current.view_revision).first<{revision: number}>();
}
