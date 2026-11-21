import { SHARED_TRIAL_DEFAULTS, validateTrial, validateView, type TrialPreferences, type ViewPreferences } from './new-a-preferences';
import { digest, type NewADatabase } from './new-a-private';
import type { MemberAdapters, ReadyPointer } from './new-a-member-services';
import type { MemberTier } from './new-a-role-facade';

type Settings = { revision: number; preferences: TrialPreferences; view_preferences: ViewPreferences };
type SettingsRow = { revision: number; trial_json: string; view_json: string };
const defaultView: ViewPreferences = { trial_preset: null, theme: 'dark', font_size: 'standard', page_size: 20 };
const encoder = new TextEncoder();
const maxBodySize = 8192;
const readSettingsSql = 'SELECT revision, trial_json, view_json FROM new_a_member_settings WHERE scope = ?';
const saveSettingsSql = `INSERT INTO new_a_member_settings (scope, revision, trial_json, view_json, requested_at)
  SELECT ?, ?, ?, ?, ? WHERE COALESCE((SELECT revision FROM new_a_member_settings WHERE scope = ?), 0) = ?
  ON CONFLICT(scope) DO UPDATE SET revision = excluded.revision, view_json = excluded.view_json,
    trial_json = CASE WHEN ? THEN excluded.trial_json ELSE new_a_member_settings.trial_json END,
    requested_at = CASE WHEN ? THEN excluded.requested_at ELSE new_a_member_settings.requested_at END
  RETURNING revision`;
const readResultSql = `SELECT r.metrics_json
  FROM new_a_member_settings s JOIN new_a_member_results r ON r.scope = s.scope AND r.settings_revision = s.revision
  WHERE s.scope = ? AND r.dataset_id = ? AND r.dataset_revision = ? AND r.as_of = ? AND r.source_version = ?
    AND json_extract(s.trial_json, '$.cost_percent') = 0`;

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function scopeFor(subject: string): Promise<string> {
  if (!/^\d{17,20}$/.test(subject)) throw new Error('unverified_member');
  return digest(JSON.stringify(['new-a-member-storage-v1', subject]));
}

function response(request: Request, status: number, body: unknown): Response {
  return new Response(request.method === 'HEAD' ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'private, no-store', vary: 'Cookie' },
  });
}

async function readSettings(db: NewADatabase, scope: string, tier: MemberTier): Promise<Settings> {
  const row = await db.prepare(readSettingsSql).bind(scope).first<SettingsRow>();
  if (!row) return { revision: 0, preferences: SHARED_TRIAL_DEFAULTS, view_preferences: defaultView };
  if (!Number.isSafeInteger(row.revision) || row.revision < 1) throw new Error('invalid_member_revision');
  return {
    revision: row.revision,
    preferences: tier === 'free' ? SHARED_TRIAL_DEFAULTS : validateTrial(JSON.parse(row.trial_json)),
    view_preferences: validateView(JSON.parse(row.view_json)),
  };
}

function bindingInput(scope: string, revision: number, tier: MemberTier): Uint8Array<ArrayBuffer> {
  const domain = tier === 'free' ? 'new-a-member-display-settings-v1' : 'new-a-member-settings-v1';
  return new Uint8Array(encoder.encode(JSON.stringify([domain, scope, revision])));
}

async function withBinding(key: CryptoKey, scope: string, state: Settings, tier: MemberTier) {
  const bytes = await crypto.subtle.sign('HMAC', key, bindingInput(scope, state.revision, tier));
  const save_binding = Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
  return { ...state, save_binding };
}

function requestState(value: unknown): { revision: number; binding: string } | null {
  if (!object(value) || Object.keys(value).sort().join(',') !== 'expected_revision,preferences,save_binding,view_preferences'
    || typeof value.expected_revision !== 'number' || !Number.isSafeInteger(value.expected_revision)
    || value.expected_revision < 0 || value.expected_revision >= Number.MAX_SAFE_INTEGER
    || typeof value.save_binding !== 'string' || !/^[a-f0-9]{64}$/.test(value.save_binding)) return null;
  return { revision: value.expected_revision, binding: value.save_binding };
}

export function createMemberSettings(db: NewADatabase, secret: string): MemberAdapters['preferences'] {
  return async (request, subject, tier) => {
    const reply = (status: number, value: unknown) => response(request, status, value);
    const fail = (status: number, error: string) => reply(status, { error });
    if (new URL(request.url).search) return fail(404, 'not_found');
    if (!['GET', 'HEAD', 'PUT'].includes(request.method)) return fail(405, 'method_not_allowed');
    if (!/^\d{17,20}$/.test(subject)) return fail(401, 'login_required');
    if (!secret.trim()) return fail(503, 'settings_unavailable');
    const scope = await scopeFor(subject);
    const key = await crypto.subtle.importKey('raw', encoder.encode(secret),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
    if (request.method !== 'PUT') {
      const state = await readSettings(db, scope, tier);
      return reply(200, await withBinding(key, scope, state, tier));
    }

    if (request.headers.get('origin') !== new URL(request.url).origin || request.headers.get('sec-fetch-site') === 'cross-site') {
      return fail(403, 'origin_required');
    }
    if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') ?? '')) return fail(415, 'json_required');
    if (Number(request.headers.get('content-length')) > maxBodySize) return fail(413, 'request_too_large');
    const raw = await request.text();
    if (encoder.encode(raw).byteLength > maxBodySize) return fail(413, 'request_too_large');
    let body: unknown;
    try { body = JSON.parse(raw); } catch { return fail(400, 'invalid_json'); }
    const state = requestState(body);
    if (!state || !object(body)) return fail(400, 'request_fields');
    const signature = Uint8Array.from({ length: 32 }, (_, index) => parseInt(state.binding.slice(index * 2, index * 2 + 2), 16));
    if (!await crypto.subtle.verify('HMAC', key, signature, bindingInput(scope, state.revision, tier))) {
      return fail(409, 'settings_session_changed');
    }
    const trialEditable = tier === 'premium';
    let next: Settings;
    try {
      const preferences = validateTrial(body.preferences);
      if (!trialEditable && object(body.preferences) && Object.entries(body.preferences).some(([key, value]) =>
        SHARED_TRIAL_DEFAULTS[key as keyof TrialPreferences] !== value)) return fail(400, 'invalid_preferences');
      next = {
        revision: state.revision + 1,
        preferences: trialEditable ? preferences : SHARED_TRIAL_DEFAULTS,
        view_preferences: validateView(body.view_preferences),
      };
    } catch {
      return fail(400, 'invalid_preferences');
    }
    // Only Premium saves may update a stored trial request. Free saves share the display revision.
    // Preparing the receipt first avoids hiding a successful write behind a signing error.
    const payload = await withBinding(key, scope, next, tier);
    const saved = await db.prepare(saveSettingsSql).bind(scope, next.revision, JSON.stringify(next.preferences),
      JSON.stringify(next.view_preferences), new Date().toISOString(), scope, state.revision,
      Number(trialEditable), Number(trialEditable)).first<{ revision: number }>();
    if (!saved) return fail(409, 'revision_conflict');
    if (saved.revision !== next.revision) throw new Error('member_save_revision');
    return reply(200, payload);
  };
}

function checkedMetrics(value: unknown): unknown | null {
  if (!object(value) || Object.keys(value).sort().join(',') !== 'max_drawdown_pct,net_profit,trade_count,win_rate_pct') return null;
  const { net_profit, max_drawdown_pct, trade_count, win_rate_pct } = value;
  if (typeof net_profit !== 'number' || !Number.isFinite(net_profit) || Math.abs(net_profit) >= 1e12
    || typeof max_drawdown_pct !== 'number' || !Number.isFinite(max_drawdown_pct) || max_drawdown_pct < -100 || max_drawdown_pct > 0
    || typeof trade_count !== 'number' || !Number.isSafeInteger(trade_count) || trade_count < 0
    || (trade_count === 0 ? win_rate_pct !== null : typeof win_rate_pct !== 'number'
      || !Number.isFinite(win_rate_pct) || win_rate_pct < 0 || win_rate_pct > 100)) return null;
  return { net_profit, max_drawdown_pct, trade_count, win_rate_pct };
}

export function createMemberPersonalReader(db: NewADatabase): MemberAdapters['personal'] {
  return async (subject: string, source: ReadyPointer) => {
    if (source.status !== 'READY') return null;
    const row = await db.prepare(readResultSql).bind(await scopeFor(subject), source.dataset_id,
      source.revision, source.as_of, source.source_version).first<{ metrics_json: string }>();
    if (!row) return null;
    try { return checkedMetrics(JSON.parse(row.metrics_json)); } catch { return null; }
  };
}
