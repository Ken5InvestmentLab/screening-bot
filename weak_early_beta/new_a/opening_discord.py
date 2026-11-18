"""Receipt-bound Cloud beta opening-price notices, with no network IO."""

import datetime
import json
import re
import sqlite3
from decimal import Decimal, InvalidOperation

from .files import digest, encode
from .outbox import ATTEMPTED

CANDIDATE_SCHEMA = "NEW_A_OPENING_DISCORD_CANDIDATES_V1"
OBSERVATION_SCHEMA = "NEW_A_FIRST_REGULAR_TRADE_OBSERVATION_V1"
SHARING_SCHEMA = "NEW_A_OPENING_DISCORD_SHARING_SCOPE_V1"
CANDIDATE_AUDIENCE = "CLOUD_BETA_GENERAL_CANDIDATES"
BATCH_SCHEMA = "NEW_A_OPENING_DISCORD_BATCH_V1"
FOOTER = "A_BASE | morning opening | "
JST = datetime.timezone(datetime.timedelta(hours=9))
SYMBOL = re.compile(r"[0-9A-Z]{4}")
IDENTIFIER = re.compile(r"[A-Za-z0-9:_-]{1,120}")
SHA256 = re.compile(r"[a-f0-9]{64}")
SNOWFLAKE = re.compile(r"[1-9][0-9]{16,19}")
OPEN_EVIDENCE = {"VENUE_OPEN_MARKER", "OFFICIAL_AM_OPEN", "GAP_FREE_REGULAR_STREAM"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _date(value):
    _require(isinstance(value, str), "market session date required")
    parsed = datetime.date.fromisoformat(value)
    _require(parsed.isoformat() == value, "market session date differs")
    return parsed


def _time(value):
    _require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ), "opening receipt timestamp required")
    return datetime.datetime.fromisoformat(value).astimezone(JST)


def _price(value):
    _require(type(value) in (int, float), "nominal opening price required")
    try:
        price = Decimal(str(value))
        _require(price.is_finite() and 0 < price <= 1_000_000_000
                 and price == price.quantize(Decimal("0.01")), "nominal opening price outside receipt bounds")
    except InvalidOperation as exc:
        raise ValueError("nominal opening price outside receipt bounds") from exc
    return format(price.normalize(), "f")


def _candidate_ids(receipt, target):
    _require(isinstance(receipt, dict) and receipt.get("schema") == CANDIDATE_SCHEMA
             and receipt.get("audience") == CANDIDATE_AUDIENCE
             and receipt.get("ordinary_publication_verified") is True
             and receipt.get("target_date") == target.isoformat()
             and _date(receipt.get("source_date")) < target
             and all(_matches(SHA256, receipt.get(key)) for key in (
                 "snapshot_sha256", "publication_sha256", "calendar_sha256"
             )), "ordinary evening candidate receipt required")
    values = receipt.get("candidates")
    _require(isinstance(values, list) and len(values) <= 500, "opening candidates are outside receipt bounds")
    candidates = {}
    for row in values:
        _require(isinstance(row, dict), "invalid evening candidate")
        symbol = row.get("symbol")
        _require(_matches(SYMBOL, symbol) and _matches(IDENTIFIER, row.get("security_id"))
                 and symbol not in candidates, "duplicate or invalid evening candidate")
        candidates[symbol] = row["security_id"]
    return candidates


def _destination(proof, observation_sha, candidate_sha, current):
    from ..notify import CHANNEL_ID, GUILD_ID

    _require(isinstance(proof, dict) and proof.get("schema") == SHARING_SCHEMA
             and proof.get("shared_market_data") is True
             and proof.get("guild_id") == GUILD_ID
             and proof.get("channel_id") == CHANNEL_ID
             and _matches(SNOWFLAKE, proof.get("webhook_id"))
             and _matches(IDENTIFIER, proof.get("provider_id"))
             and _matches(SHA256, proof.get("authority_receipt_sha256"))
             and proof.get("candidate_receipt_sha256") == candidate_sha
             and proof.get("observation_sha256") == observation_sha,
             "independent provider sharing and Cloud beta destination proof required")
    _require(_time(proof.get("observed_at")) <= current < _time(proof.get("not_after")),
             "opening sharing proof expired or not yet observed")
    allowed_sources = proof.get("source_ids")
    _require(isinstance(allowed_sources, list) and allowed_sources
             and all(_matches(IDENTIFIER, value) for value in allowed_sources)
             and len(set(allowed_sources)) == len(allowed_sources),
             "independent provider sharing has no exact source scope")
    return {key: proof[key] for key in ("guild_id", "channel_id", "webhook_id")}


def prepare(observation, *, read_candidates, read_sharing_scope, now):
    """The host readers must verify their source and can reject either request."""
    _require(isinstance(now, datetime.datetime) and now.tzinfo is not None, "trusted clock required")
    current = now.astimezone(JST)
    target = _date(observation.get("target_date"))
    rows = observation.get("rows")
    _require(observation.get("schema") == OBSERVATION_SCHEMA
             and target == current.date() and isinstance(rows, list) and len(rows) <= 500,
             "current market session opening observation required")
    candidates_receipt = read_candidates(target.isoformat())
    candidates = _candidate_ids(candidates_receipt, target)
    observation_sha = digest(observation)
    candidate_sha = digest(candidates_receipt)
    proof = read_sharing_scope(observation_sha, candidate_sha)
    destination = _destination(proof, observation_sha, candidate_sha, current)

    trades = []
    seen = set()
    for row in rows:
        _require(isinstance(row, dict), "ambiguous opening observation")
        symbol = row.get("symbol")
        _require(_matches(SYMBOL, symbol) and symbol not in seen, "ambiguous opening observation")
        seen.add(symbol)
        if symbol not in candidates or row.get("status") != "FIRST_REGULAR_TRADE_VERIFIED":
            continue
        traded, observed = _time(row.get("trade_at")), _time(row.get("observed_at"))
        _require(row.get("security_id") == candidates[symbol]
                 and row.get("exchange") == "XTKS" and row.get("market") == "REGULAR"
                 and row.get("session") == "MORNING" and row.get("price_basis") == "ACTUAL_JPY"
                 and row.get("first_trade_evidence") in OPEN_EVIDENCE
                 and row.get("source_id") in proof["source_ids"]
                 and _matches(SHA256, row.get("source_sha256"))
                 and type(row.get("trade_size")) is int and row["trade_size"] > 0
                 and traded.date() == observed.date() == target
                 and datetime.time(9) <= traded.time() <= datetime.time(11, 30)
                 and traded <= observed <= current,
                 "verified first regular morning trade required")
        price = _price(row.get("actual_price_yen"))
        trade_at = traded.isoformat(timespec="milliseconds")
        trades.append({
            "symbol": symbol, "trade_at": trade_at, "price_yen": price,
            "trade_id": digest([BATCH_SCHEMA, target.isoformat(), symbol, candidates[symbol], trade_at, price]),
        })
    return {
        "target_date": target.isoformat(), "destination": destination,
        "observation_sha256": observation_sha, "candidate_receipt_sha256": candidate_sha,
        "sharing_scope_sha256": digest(proof),
        "trades": sorted(trades, key=lambda row: (row["trade_at"], row["symbol"])),
    }


def _batch(plan, trades):
    date = plan["target_date"]
    destination = plan["destination"]
    batch_id = digest([BATCH_SCHEMA, date, destination, [row["trade_id"] for row in trades]])
    lines = [
        f"{trade['symbol']} ｜ {trade['trade_at'][11:23].removesuffix('.000')} JST ｜ {trade['price_yen']}円"
        for trade in trades
    ]
    embed = {
        "title": f"Cloud 新A 寄付の確認（{date}）",
        "description": "前場の最初の約定価格\n" + "\n".join(lines) + "\n\n仮想保有判定待ち",
        "color": 0x5B8DEF, "footer": {"text": FOOTER + batch_id},
    }
    return {
        **{key: value for key, value in plan.items() if key != "trades"},
        "schema": BATCH_SCHEMA, "batch_id": batch_id, "trades": trades,
        "payload": {"content": "", "embeds": [embed], "allowed_mentions": {"parse": []}},
    }


def _matches_message(message, batch):
    if not isinstance(message, dict):
        return False
    destination = batch["destination"]
    embeds = message.get("embeds")
    expected = batch["payload"]["embeds"][0]
    return (
        _matches(SNOWFLAKE, message.get("id"))
        and message.get("guild_id", destination["guild_id"]) == destination["guild_id"]
        and message.get("channel_id") == destination["channel_id"]
        and message.get("webhook_id") == destination["webhook_id"]
        and message.get("content") == "" and not message.get("attachments")
        and isinstance(embeds, list) and len(embeds) == 1 and isinstance(embeds[0], dict)
        and all(embeds[0].get(key) == expected[key] for key in ("title", "description", "color"))
        and not any(embeds[0].get(key) for key in ("fields", "url", "image", "thumbnail", "author", "timestamp"))
        and isinstance(embeds[0].get("footer"), dict)
        and embeds[0]["footer"].get("text") == expected["footer"]["text"]
    )


class OpeningDiscordOutbox:
    """A local ledger. A claim precedes any host-managed POST."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS opening_discord_batches (
                batch_id TEXT PRIMARY KEY, target_date TEXT NOT NULL, data TEXT NOT NULL,
                status TEXT NOT NULL, message_id TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS opening_discord_unknown_per_day
            ON opening_discord_batches(target_date) WHERE status = 'ATTEMPTED_UNCONFIRMED';
            CREATE TABLE IF NOT EXISTS opening_discord_members (
                target_date TEXT NOT NULL, symbol TEXT NOT NULL, trade_id TEXT NOT NULL,
                batch_id TEXT NOT NULL REFERENCES opening_discord_batches(batch_id),
                PRIMARY KEY(target_date, symbol)
            );
        """)

    def close(self):
        self.db.close()

    def _unknown(self, date):
        saved = self.db.execute(
            "SELECT data FROM opening_discord_batches WHERE target_date=? AND status=?",
            (date, ATTEMPTED),
        ).fetchone()
        return json.loads(saved[0]) if saved else None

    def claim(self, observation, *, read_candidates, read_sharing_scope, now):
        """Validate independent proofs and atomically record the exact planned message."""
        plan = prepare(observation, read_candidates=read_candidates, read_sharing_scope=read_sharing_scope, now=now)
        target = plan["target_date"]
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self._unknown(target):
                return {"status": "reconciliation_required"}
            sent = dict(self.db.execute(
                "SELECT symbol,trade_id FROM opening_discord_members WHERE target_date=?", (target,),
            ))
            pending = []
            for trade in plan["trades"]:
                previous = sent.get(trade["symbol"])
                if previous is None:
                    pending.append(trade)
                elif previous != trade["trade_id"]:
                    raise ValueError("verified opening trade changed after its notification claim")
            if not pending:
                return {"status": "nothing_to_send"}
            batch = _batch(plan, pending[:40])
            self.db.execute(
                "INSERT INTO opening_discord_batches VALUES (?, ?, ?, ?, NULL)",
                (batch["batch_id"], target, encode(batch), ATTEMPTED),
            )
            self.db.executemany("INSERT INTO opening_discord_members VALUES (?, ?, ?, ?)", [
                (target, trade["symbol"], trade["trade_id"], batch["batch_id"]) for trade in batch["trades"]
            ])
            return {"status": "claimed", "batch": batch}

    def verify_claim(self, batch, observation, *, read_candidates, read_sharing_scope, now):
        """Recheck the exact saved batch and live proof immediately before a host sends it."""
        plan = prepare(observation, read_candidates=read_candidates, read_sharing_scope=read_sharing_scope, now=now)
        saved = self._unknown(plan["target_date"])
        _require(saved is not None and saved == batch, "opening notification claim differs")
        fresh = {row["trade_id"]: row for row in plan["trades"]}
        rows = [fresh.get(row["trade_id"]) for row in saved["trades"]]
        _require(all(rows) and _batch(plan, rows) == saved, "opening notification proofs or payload changed")
        return saved["payload"]

    def reconcile(self, date, messages):
        """Confirm exactly one matching readback. Absent or ambiguous readbacks leave the claim."""
        _date(date)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            batch = self._unknown(date)
            if not batch:
                return {"status": "nothing_to_reconcile"}
            matches = [message["id"] for message in messages if _matches_message(message, batch)]
            if len(matches) != 1:
                return {"status": "reconciliation_required"}
            self.db.execute(
                "UPDATE opening_discord_batches SET status='SENT', message_id=? WHERE batch_id=? AND status=?",
                (matches[0], batch["batch_id"], ATTEMPTED),
            )
            return {"status": "confirmed", "count": len(batch["trades"]), "message_id": matches[0]}
