"""Pure JPX revision decision core; requires byte-verified independent evidence.

Only actual trading-day units are accepted. Evidence must be obtained from an
independently fetched official JPX daily report and reviewed extraction; the
caller must verify its bytes/hash before constructing an Evidence instance.
Never treats provider data, a URL alone or an afternoon open as daily evidence.
"""
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlparse

FIELDS = {'open', 'high', 'low', 'close', 'volume'}

class IntegrityError(ValueError):
    """Systemic malformed identity/basis/evidence. Caller must stop, not skip."""

@dataclass(frozen=True)
class Evidence:
    symbol: str
    session: str
    field: str
    value: str
    url: str
    pdf_sha256: str
    page: int
    units: str
    basis: str = 'actual_session_units'
    open_kind: str = ''
    verified_bytes: bool = False

    def check(self):
        if not re.fullmatch(r'[0-9A-Z]{4}', self.symbol):
            raise IntegrityError('invalid symbol')
        date.fromisoformat(self.session)
        if self.field not in FIELDS or self.basis != 'actual_session_units':
            raise IntegrityError('unknown field or adjustment basis')
        expected = f'/automation/markets/statistics-equities/daily/files/{self.session[:7].replace("-", "")}/stq_{self.session.replace("-", "")}.pdf'
        parsed = urlparse(self.url)
        if (parsed.scheme != 'https' or parsed.netloc != 'www.jpx.co.jp'
                or parsed.path != expected or parsed.query):
            raise IntegrityError('official JPX URL/date mismatch')
        if not self.verified_bytes or not re.fullmatch(r'[a-fA-F0-9]{64}', self.pdf_sha256):
            raise IntegrityError('unverified or malformed source hash')
        if isinstance(self.page, bool) or not isinstance(self.page, int) or self.page < 1:
            raise IntegrityError('invalid evidence page')
        if self.units != ('shares' if self.field == 'volume' else 'JPY'):
            raise IntegrityError('unit mismatch; do not infer thousands/shares')
        if self.field == 'open' and self.open_kind != 'morning_first_trade':
            raise IntegrityError('daily open requires morning first trade, not afternoon open')
        return number(self.value, self.field)

def number(value, field):
    try:
        n = Decimal(str(value))
    except InvalidOperation as exc:
        raise IntegrityError('invalid number') from exc
    if not n.is_finite() or n < 0 or (field != 'volume' and n == 0):
        raise IntegrityError('invalid value')
    return n

def decide(symbol, session, field, old, new, evidence=None, *, failure=None):
    """Pure decision. Does not edit prices or relax normalization/other gates."""
    if not re.fullmatch(r'[0-9A-Z]{4}', str(symbol)) or field not in FIELDS:
        raise IntegrityError('invalid requested identity')
    date.fromisoformat(session)
    before, after = number(old, field), number(new, field)
    result = dict(symbol=str(symbol), date=session, field=field, old=str(before),
                  new=str(after), evidence=None, held=False)
    if before == after:
        return dict(result, decision='unchanged', selected=str(after), reason='no revision')
    if evidence is None:
        return dict(result, decision='hold_symbol', selected=None, held=True,
                    reason=failure or 'independent evidence unavailable')
    official = evidence.check()
    if (evidence.symbol, evidence.session, evidence.field) != (str(symbol), session, field):
        raise IntegrityError('evidence does not identify requested cell')
    result['evidence'] = asdict(evidence)
    if official == after:
        return dict(result, decision='accept_new', selected=str(after), reason='JPX confirms new value')
    if official == before:
        return dict(result, decision='keep_old', selected=str(before), reason='JPX confirms prior value')
    return dict(result, decision='hold_symbol', selected=None, held=True,
                reason='JPX matches neither endpoint')

def plan(cells):
    """Plans entire symbol holds atomically; non-held symbols remain eligible.

    Integration must mask EVERY row/feature/entry for held symbols and preserve
    original corpus and complete action journals. This function does not assert
    that production supports that integration yet.
    """
    decisions = [decide(**cell) for cell in cells]
    held = sorted({r['symbol'] for r in decisions if r['held']})
    return dict(identity='CLOUD_JPX_REVISION_PLAN_V1', decisions=decisions,
                held_symbols=held,
                eligible_symbols=sorted({r['symbol'] for r in decisions} - set(held)),
                requires_detection=any(r['decision']=='accept_new' and r['symbol'] not in held for r in decisions))

