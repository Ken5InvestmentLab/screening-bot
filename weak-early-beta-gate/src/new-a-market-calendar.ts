// JPX cash-market closures for the published 2026 and 2027 schedules.
// https://www.jpx.co.jp/corporate/about-jpx/calendar/index.html
const firstCovered = Date.UTC(2026, 0, 1);
const endCovered = Date.UTC(2028, 0, 1);
const dayMs = 86_400_000;
const closures = new Set([
  '2026-01-01', '2026-01-02', '2026-01-03', '2026-01-12', '2026-02-11', '2026-02-23',
  '2026-03-20', '2026-04-29', '2026-05-03', '2026-05-04', '2026-05-05', '2026-05-06',
  '2026-07-20', '2026-08-11', '2026-09-21', '2026-09-22', '2026-09-23', '2026-10-12',
  '2026-11-03', '2026-11-23', '2026-12-31',
  '2027-01-01', '2027-01-02', '2027-01-03', '2027-01-11', '2027-02-11', '2027-02-23',
  '2027-03-21', '2027-03-22', '2027-04-29', '2027-05-03', '2027-05-04', '2027-05-05',
  '2027-07-19', '2027-08-11', '2027-09-20', '2027-09-23', '2027-10-11',
  '2027-11-03', '2027-11-23', '2027-12-31',
]);

function marketSession(day: number): string | null {
  if (!Number.isFinite(day) || day < firstCovered || day >= endCovered) return null;
  const date = new Date(day);
  const weekday = date.getUTCDay();
  const iso = date.toISOString().slice(0, 10);
  return weekday !== 0 && weekday !== 6 && !closures.has(iso) ? iso : null;
}

/** Display schedule for a still-open virtual holding. The purchase session is day one. */
export function plannedHoldingExit(entry: string, asOf: string, sessions: number): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(entry) || !/^\d{4}-\d{2}-\d{2}$/.test(asOf)
    || !Number.isSafeInteger(sessions) || sessions < 1) return null;
  const start = Date.parse(entry + 'T00:00:00Z');
  const observed = Date.parse(asOf + 'T00:00:00Z');
  if (start > observed || marketSession(start) !== entry || marketSession(observed) !== asOf) return null;
  let remaining = sessions;
  for (let day = start; day < endCovered; day += dayMs) {
    const session = marketSession(day);
    if (session && --remaining === 0) return day > observed ? session : null;
  }
  return null;
}
