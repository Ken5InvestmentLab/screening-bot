"""Read-only inputs to the New A lifecycle planner.

The host must independently observe the production owner policy and active D1
identity. This adapter has no publisher, scheduler, credential output or sender.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess

from ..bank_calendar import is_bank_business_day
from .continuing_acceptance import target
from .files import digest, encode, private_root, read, verify_bootstrap
from .publisher import WranglerD1, hash_text, is_read_only_select, validate_manifest

JST = timezone(timedelta(hours=9))
OWNER_PROOF = "NEW_A_OWNER_NOTICE_INPUT_IDENTITY_V1"
SOURCE_PROOF = "NEW_A_OWNER_NOTICE_SOURCE_V1"
MORNING = "EVALUATION_DAY_MORNING"
HOLDING = "WATCH_TO_SIMULATED_HOLDING"
DATASET = re.compile(r"a-[a-f0-9]{24}")
HEX = re.compile(r"[a-f0-9]{64}")
MAX_PARTS_PER_QUERY = 8

ACTIVE_SQL = """
SELECT p.dataset_id, p.revision, d.status, d.source_version,
       d.manifest_sha256, d.manifest_json
FROM new_a_active_pointer AS p
JOIN new_a_private_datasets AS d ON d.dataset_id = p.dataset_id
WHERE p.pointer_key = 'owner'
"""
OWNER_SQL = """
SELECT trial.schema_version, trial.revision, trial.preferences_json,
       view.preferences_json AS view_preferences_json
FROM new_a_finite_trial_preferences AS trial
LEFT JOIN new_a_finite_trial_preferences AS view ON view.member_id = ?
WHERE trial.member_id = ?
"""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _clock():
    return datetime.now(timezone.utc)


def _day(value):
    parsed = date.fromisoformat(value)
    _require(parsed.isoformat() == value, "JST date must be YYYY-MM-DD")
    return parsed


def _instant(value):
    parsed = datetime.fromisoformat(value)
    _require(parsed.tzinfo is not None, "timezone required")
    return parsed


@dataclass(frozen=True)
class PreparedLifecycleNotice:
    plan: dict
    owner_binding_sha256: str | None = None
    preference_row_sha256: str | None = None
    plan_sha256: str | None = None


class LifecycleNoticeInputs:
    def __init__(self, repo, database, read_verified_owner, *, node, clock=_clock):
        _require(callable(read_verified_owner), "verified production owner readback required")
        self.repo = Path(repo).resolve()
        self.root = private_root(self.repo)
        self.db = database
        self.read_verified_owner = read_verified_owner
        self.node = node
        self.clock = clock

    @classmethod
    def from_live(cls, repo, read_verified_owner, *, clock=_clock):
        """Use the approved host's fresh normal-origin owner-policy and D1 readback."""
        # The DB and binary use the existing production binding and runner config.
        _require(callable(read_verified_owner), "verified production owner readback required")
        repo = Path(repo).resolve()
        destination = target(repo)
        config = read(repo / ".cache/weak_early_beta/daily-runner.config.json")
        node = Path(config["nodePath"])
        _require(node.is_absolute() and node.is_file(), "existing runner Node runtime unavailable")
        database = WranglerD1(repo, private_root(repo) / "sql", execute=True, node=str(node))
        return cls(repo, database, lambda: read_verified_owner(destination),
                   node=str(node), clock=clock)

    def close(self):
        self.db.close()

    def _select(self, sql, values=()):
        _require(is_read_only_select(sql), "read-only lifecycle SELECT required")
        return self.db.query(sql, values)

    def _read_current(self):
        rows = self._select(ACTIVE_SQL)
        _require(len(rows) == 1, "exactly one active owner dataset required")
        row = rows[0]
        raw = row["manifest_json"]
        _require(isinstance(raw, str) and len(raw.encode("utf-8")) <= 256 * 1024 and
                 HEX.fullmatch(row["manifest_sha256"]) and hash_text(raw) == row["manifest_sha256"] and
                 DATASET.fullmatch(row["dataset_id"]) and type(row["revision"]) is int and
                 0 < row["revision"] <= (2**53 - 1) and row["status"] == "READY",
                 "active D1 readback differs")
        manifest = validate_manifest(json.loads(raw))
        publication = read(self.root / "latest-publication.json")
        _require(manifest["source_version"] == row["source_version"] and
                 publication.get("schema") == "NEW_A_PRIVATE_PUBLICATION_RECEIPT_V1" and
                 publication.get("published") is True and
                 publication.get("local_d1_emulation") is False and
                 publication.get("active_readback_verified") is True and
                 publication.get("existing_owner_gate_verified") is True and
                 publication.get("operational_gate_continuity_verified") is not True and
                 all(publication.get(key) == row[key] for key in
                     ("dataset_id", "revision", "source_version", "manifest_sha256")) and
                 publication.get("snapshot_sha256") == manifest["daily_snapshot_sha256"] and
                 publication.get("as_of") == manifest["as_of"],
                 "ordinary owner publication receipt differs")
        active_hash = digest(["NEW_A_ACTIVE_METADATA_V1", row["dataset_id"], row["revision"],
                              row["status"], row["source_version"], row["manifest_sha256"],
                              manifest["as_of"]])
        proof = self.read_verified_owner()
        _require(isinstance(proof, dict) and proof.get("schema") == OWNER_PROOF and
                 proof.get("normal_owner_policy_verified") is True and
                 proof.get("d1_active_sha256") == active_hash and
                 HEX.fullmatch(str(proof.get("owner_binding_sha256", ""))),
                 "production owner policy or D1 identity differs")
        observed, expires = _instant(proof["observed_at"]), _instant(proof["expires_at"])
        _require(observed <= self.clock() < expires <= observed + timedelta(minutes=2),
                 "production owner readback is stale")
        owner = proof["owner_binding_sha256"]
        member = "cloud_" + owner
        prefs = self._select(OWNER_SQL, ("new-a-view:v1:" + member, member))
        _require(len(prefs) == 1 and prefs[0]["schema_version"] == 1 and
                 type(prefs[0]["revision"]) is int and 0 < prefs[0]["revision"] <= (2**53 - 1),
                 "saved New A preferences unavailable for the verified owner")
        pointer = {key: row[key] for key in
                   ("dataset_id", "revision", "status", "source_version", "manifest_sha256")}
        return {"pointer": pointer, "manifestText": raw, "publication": publication}, manifest, owner, prefs[0]

    def _calendar(self):
        bootstrap, files = verify_bootstrap(self.root)
        raw = files["calendar"].read_bytes()
        expected = bootstrap["files"]["calendar"]["sha256"]
        _require(len(raw) <= 256 * 1024, "bootstrap calendar exceeds input limit")
        value = raw.decode("utf-8")
        _require(hash_text(value) == expected, "bootstrap calendar changed during read")
        return {"raw": value, "sha256": expected}

    def _read_parts(self, pointer, manifest):
        groups = {}
        collections = manifest["collections"]
        for parts in (collections["episodes"], collections["intents"], collections["watches"], manifest["quotes"]):
            for part in parts:
                dataset = part.get("dataset_id", pointer["dataset_id"])
                groups.setdefault(dataset, []).append(part)

        values = {}
        for dataset, parts in groups.items():
            for offset in range(0, len(parts), MAX_PARTS_PER_QUERY):
                batch = parts[offset:offset + MAX_PARTS_PER_QUERY]
                names = [item["name"] for item in batch]
                placeholders = ",".join("?" for _ in names)
                stored = self._select(
                    f"""SELECT p.name, p.payload_json, p.sha256, p.byte_length
                        FROM new_a_private_parts AS p
                        JOIN new_a_private_datasets AS d ON d.dataset_id = p.dataset_id
                        WHERE p.dataset_id = ? AND d.status = 'READY'
                          AND p.name IN ({placeholders})""",
                    (dataset, *names),
                )
                by_name = {item["name"]: item for item in stored}
                _require(len(stored) == len(batch) and set(by_name) == set(names),
                         "published replay part is unavailable")
                for item in batch:
                    part = by_name[item["name"]]
                    raw = part["payload_json"]
                    _require(isinstance(raw, str) and
                             len(raw.encode("utf-8")) == part["byte_length"] == item["bytes"] and
                             hash_text(raw) == part["sha256"] == item["sha256"],
                             "published replay part bytes differ")
                    values[dataset + "/" + item["name"]] = raw
        return values

    def prepare(self, kind, *, now, scheduled_at=None, target_date=None):
        _require(kind in (HOLDING, MORNING) and now.tzinfo is not None, "invalid lifecycle planning window")
        jst = now.astimezone(JST)
        morning = kind == MORNING
        if morning:
            _require(scheduled_at is not None and scheduled_at.tzinfo is not None, "scheduled time required")
            scheduled = scheduled_at.astimezone(JST)
            target_date = scheduled.date().isoformat()
            in_window = (scheduled <= jst and scheduled.date() == jst.date() and
                         scheduled.hour == jst.hour == 8 and scheduled.minute == 0)
        else:
            in_window = _day(target_date) == jst.date()
        if not in_window:
            return PreparedLifecycleNotice(
                {"status": "outside_reminder_window" if morning else "not_current_jst_day",
                 "target_date": target_date, "notices": []})
        if not is_bank_business_day(_day(target_date)):
            return PreparedLifecycleNotice(
                {"status": "bank_non_business_day", "target_date": target_date, "notices": []})

        active, manifest, owner, preferences = self._read_current()
        calendar = self._calendar() if morning else None
        payload = {
            "kind": kind, "now": int(now.timestamp() * 1000),
            "scheduledAt": int(scheduled_at.timestamp() * 1000) if morning else None,
            "targetDate": target_date, "active": active,
            "owner": owner, "preferences": preferences, "calendar": calendar,
            "parts": self._read_parts(active["pointer"], manifest),
        }
        completed = subprocess.run(
            [self.node, str(self.repo / "scripts/windows/new-a-lifecycle-notice-inputs.cjs")],
            cwd=self.repo, input=encode(payload), capture_output=True,
            encoding="utf-8", timeout=120,
        )
        _require(completed.returncode == 0, "New A lifecycle planner rejected the verified inputs")
        plan = json.loads(completed.stdout)
        latest, _, latest_owner, latest_preferences = self._read_current()
        _require(latest == active and latest_owner == owner and latest_preferences == preferences and
                 (not morning or self._calendar() == calendar),
                 "publication, owner preferences or calendar changed during lifecycle planning")
        return PreparedLifecycleNotice(plan, owner, digest(preferences), digest(plan))

    def read_source(self, prepared):
        """Fresh source proof for the existing outbox's pre-claim/pre-send check."""
        plan = prepared.plan
        _require(plan.get("status") == "planned" and digest(plan) == prepared.plan_sha256,
                 "verified lifecycle plan changed")
        active, manifest, owner, preferences = self._read_current()
        pointer = active["pointer"]
        basis = {key: pointer[key] for key in ("dataset_id", "revision", "source_version", "manifest_sha256")}
        basis["snapshot_sha256"] = manifest["daily_snapshot_sha256"]
        basis["preferences_revision"] = preferences["revision"]
        if "calendar_sha256" in plan["basis"]:
            basis["calendar_sha256"] = self._calendar()["sha256"]
        _require(owner == prepared.owner_binding_sha256 and
                 digest(preferences) == prepared.preference_row_sha256 and basis == plan["basis"],
                 "published inputs or saved owner preferences changed before delivery")
        observed = self.clock()
        return {"schema": SOURCE_PROOF, "current": True, "owner_binding_sha256": owner,
                "plan_sha256": digest(plan), "basis": basis,
                "observed_at": observed.isoformat(),
                "expires_at": (observed + timedelta(minutes=2)).isoformat()}
