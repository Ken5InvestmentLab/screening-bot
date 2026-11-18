(function (global) {
 'use strict';

 const statuses = {
  AWAITING_FIRST_TRADE: ['初約定待ち', 'watch-start'],
  FIRST_TRADE_VERIFIED: ['初約定を確認・保有判定待ち', 'watch-start'],
  PROVISIONAL_ELIGIBLE: ['仮判定：寄付価格の条件を満たす', 'hold-start'],
  PROVISIONAL_SKIPPED: ['仮判定：見送り', 'watch-end'],
  PENDING_PORTFOLIO: ['試算条件の確認待ち', 'watch-start'],
  RECONCILE: ['約定情報を再確認中', 'watch-end'],
 };
 const jst = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'short',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
 });
 const tradeTime = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
 });
 const yen = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 4 });
 const datePattern = /^\d{4}-\d{2}-\d{2}$/;
 const codePattern = /^[0-9A-Z]{4}$/;

 function marketClock(date) {
  const p = Object.fromEntries(jst.formatToParts(date).map(({ type, value }) => [type, value]));
  const hhmm = Number(p.hour) * 100 + Number(p.minute);
  return { date: p.year + '-' + p.month + '-' + p.day,
   poll: p.weekday !== 'Sat' && p.weekday !== 'Sun' && hhmm >= 845 && hhmm < 1800 };
 }

 function validResult(value, today) {
  if (value?.target_date !== today || !datePattern.test(value.target_date)) return false;
  if (value.state === 'empty') return true;
  return value.state === 'ready' && Number.isSafeInteger(value.revision) && value.revision > 0 &&
   typeof value.updated_at === 'string' && Number.isFinite(Date.parse(value.updated_at)) &&
   Array.isArray(value.rows) && value.rows.length <= 500 && value.rows.every(row =>
    row && typeof row.symbol === 'string' && codePattern.test(row.symbol) &&
    typeof row.candidate_date === 'string' && datePattern.test(row.candidate_date) &&
    Object.hasOwn(statuses, row.status) &&
    ((row.trade_at === undefined && row.actual_price_yen === undefined) ||
     (typeof row.trade_at === 'string' && Number.isFinite(Date.parse(row.trade_at)) &&
      Number.isFinite(row.actual_price_yen) && row.actual_price_yen > 0)));
 }

 if (typeof module !== 'undefined' && module.exports) {
  module.exports = { marketClock, validResult };
  return;
 }

 if (typeof document === 'undefined') return;
 const panel = document.getElementById('cloud-opening');
 if (!panel) return;
 const cards = document.getElementById('cloud-opening-cards');
 const status = document.getElementById('cloud-opening-status');
 let timer, request, latest, shown, older = false, active = false, lastRead = 0, onDenied;
 function renderSavedRows() {
  if (!latest?.rows.length) {
   panel.hidden = true;
   cards.replaceChildren();
   status.textContent = '';
   shown = null;
   return;
  }
  const names = new Map((global.AOwnerPageData?.rows ?? [])
   .filter(row => row.chartAllowed !== false && row.companyName)
   .map(row => [row.symbol + '|' + row.candidateDate, row.companyName]));
  const rows = latest.rows.map(row => ({ ...row, name: names.get(row.symbol + '|' + row.candidate_date) }));
  const next = JSON.stringify([latest.target_date, latest.revision, latest.updated_at, rows]);
  if (next !== shown) {
   cards.replaceChildren(...rows.map(row => {
    const card = document.createElement('article');
    const title = document.createElement('strong');
    title.textContent = row.name ? row.name + ' ' + row.symbol : row.symbol;
    const [label, tone] = statuses[row.status];
    const badge = document.createElement('span');
    badge.className = 'cloud-transition cloud-transition--' + tone;
    badge.textContent = label;
    card.append(title, badge);
    if (row.trade_at) {
     const trade = document.createElement('small');
     trade.textContent = '初約定 ' + yen.format(row.actual_price_yen) + '円 · ' +
      tradeTime.format(new Date(row.trade_at)) + ' JST';
     card.append(trade);
    }
    return card;
   }));
   shown = next;
  }
  const message = latest.target_date + ' · 更新 ' + tradeTime.format(new Date(latest.updated_at)) + ' JST' +
   (older ? ' · 最新情報を確認できませんでした' : '');
  if (status.textContent !== message) status.textContent = message;
  panel.hidden = false;
 }

 async function refresh(force = false) {
  if (!active || global.AFiniteRevoked || document.hidden || request) return;
  clearTimeout(timer);
  const clock = marketClock(new Date());
  if (latest?.target_date !== clock.date) {
   latest = null;
   renderSavedRows();
  }
  if ((!clock.poll && !force) || Date.now() - lastRead < 10000) {
   timer = setTimeout(refresh, 60000);
   return;
  }

  request = new AbortController();
  const timeout = setTimeout(() => request?.abort(), 12000);
  lastRead = Date.now();
  try {
   const response = await global.fetch('/api/cloud/new-a-finite/opening-observation', {
    credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: request.signal,
   });
   if (!active) return;
   if (response.status === 401 || response.status === 403) {
    clear();
    onDenied?.();
    return;
   }
   if (!response.ok) throw Error('opening_unavailable');
   const result = await response.json();
   if (!active) return;
   if (!validResult(result, marketClock(new Date()).date)) throw Error('opening_result');
   latest = result.state === 'ready' ? result : null;
   older = false;
  } catch {
   older = true;
  } finally {
   clearTimeout(timeout);
   request = null;
   if (active) {
    renderSavedRows();
    if (!document.hidden) timer = setTimeout(refresh, 60000);
   }
  }
 }

 function visibility() {
  if (document.hidden) clearTimeout(timer);
  else refresh(true);
 }

 function clear() {
  active = false;
  clearTimeout(timer);
  request?.abort();
  document.removeEventListener('visibilitychange', visibility);
  global.removeEventListener('pageshow', visibility);
  latest = null;
  renderSavedRows();
 }

 global.AOwnerOpening = {
  start(denied) {
   if (active) return;
   onDenied = denied;
   active = true;
   lastRead = 0;
   document.addEventListener('visibilitychange', visibility);
   global.addEventListener('pageshow', visibility);
   refresh(true);
  },
  clear,
  renderSavedRows,
 };
})(globalThis);
