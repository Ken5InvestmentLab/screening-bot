"""Host orchestration for staging notices from an exact completed ordinary run.

This module accepts already-provisioned readers and a queue writer. It never opens
a production connection, starts the daily process, or invokes the push provider.
"""
from bisect import bisect_left
from datetime import datetime, time
import json
from pathlib import Path

from ..bank_calendar import is_bank_business_day
from .files import private_root, verify_bootstrap
from .owner_notice_queue import stage_notice_queue
from .planned_notice_delivery import (
    HOLDING, JST, MORNING, _clock, _day, _instant, _require,
)
from .publisher import hash_text


def _terminal_result(repo, run_path, now):
    runtime = (repo / ".cache/weak_early_beta/daily_runtime").resolve()
    path = Path(run_path)
    _require(runtime.is_relative_to(repo) and path.is_absolute() and path.resolve(strict=True) == path and
             path.name == "result.json" and path.parent.parent == runtime,
             "expected the canonical terminal runner result")
    with path.open("rb") as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    _require(len(raw) <= 4 * 1024 * 1024, "runner receipt exceeds its input bounds")
    result = json.loads(raw.decode("utf-8-sig"))
    started_at = result.get("startedAt")
    completed_at = result.get("completedAt")
    _require(isinstance(started_at, str) and isinstance(completed_at, str) and
             result.get("identity") == "WEAK_EARLY_CLOUD_DAILY_V1" and result.get("ok") is True and
             result.get("latestSession") == result.get("date") and
             result.get("new_a", {}).get("owner_publication_verified") is True and
             result.get("deployment", {}).get("reusedApprovedCodeOnly") is True and
             result.get("observationKind") != "DELAYED_SCHEDULED_OBSERVATION" and
             path.parent.name == "daily-" + started_at.replace(":", "-").replace(".", "-"),
             "terminal result is not a completed ordinary publication")
    published_day = _day(result["date"])
    started, completed = _instant(started_at), _instant(completed_at)
    _require(started.astimezone(JST).date() == published_day and
             started <= completed <= now,
             "ordinary publication timing differs from its runner receipt")
    return published_day


def _verified_calendar(repo):
    bootstrap, paths = verify_bootstrap(private_root(repo))
    with paths["calendar"].open("rb") as stream:
        raw = stream.read(256 * 1024 + 1)
    _require(len(raw) <= 256 * 1024 and
             hash_text(raw.decode("utf-8")) == bootstrap["files"]["calendar"]["sha256"],
             "verified JPX session calendar changed")
    values = json.loads(raw)
    _require(isinstance(values, list) and len(values) >= 2, "verified JPX session calendar unavailable")
    days = [_day(day) for day in values]
    _require(all(before < after for before, after in zip(days, days[1:])),
             "verified JPX sessions are not ordered and unique")
    return days


class OwnerNoticeProducer:
    """Connect the verified lifecycle planner to the queue writer after publication."""

    def __init__(self, repo, inputs, queue, *, read_release, read_recipient, clock=_clock):
        self.repo = Path(repo).resolve(strict=True)
        _require(inputs.repo == self.repo and callable(read_release) and
                 callable(read_recipient) and callable(clock), "trusted owner notice adapters required")
        self.inputs = inputs
        self.queue = queue
        self.read_release = read_release
        self.read_recipient = read_recipient
        self.clock = clock

    def _stage(self, run_path, kind, *, now, target, **timing):
        planner_args = {"target_date": target} if kind == HOLDING else timing
        prepared = self.inputs.prepare(kind, now=now, **planner_args)
        plan = prepared.plan
        _require(plan.get("target_date") == target, "prepared notice is for a different JST date")
        if plan.get("status") != "planned":
            _require(plan.get("notices") == [], "unplanned notice cannot enter the queue")
            return {"status": plan.get("status"), "kind": kind, "target_date": target, "staged": 0}
        writer_timing = timing if timing.get("advance") else {}
        return stage_notice_queue(
            self.queue, self.repo, run_path, plan, kind=kind,
            owner=prepared.owner_binding_sha256, read_source=lambda: self.inputs.read_source(prepared),
            read_release=self.read_release, read_recipient=self.read_recipient, now=self.clock, **writer_timing,
        )

    def after_publication(self, run_path):
        """Stage tonight's holding notices and the next JPX session's 08:00 notices."""
        now = _instant(self.clock())
        local = now.astimezone(JST)
        _require(local.hour >= 17, "notice preparation requires the evening JST window")
        source = _terminal_result(self.repo, run_path, now)
        _require(source == local.date(), "holding notices require this evening's ordinary publication")
        days = _verified_calendar(self.repo)
        index = bisect_left(days, source)
        _require(index + 1 < len(days) and days[index] == source and is_bank_business_day(days[index + 1]),
                 "next verified JPX notice session is unavailable")
        morning_at = datetime.combine(days[index + 1], time(8), JST)
        return {
            "source_date": source.isoformat(),
            "holding": self._stage(run_path, HOLDING, now=now, target=source.isoformat()),
            "morning": self._stage(run_path, MORNING, now=_instant(self.clock()),
                                   target=morning_at.date().isoformat(), scheduled_at=morning_at, advance=True),
        }

    def at_morning(self, run_path, scheduled_at):
        """Stage within the authenticated 08:00 slot using the preceding JPX publication."""
        now = _instant(self.clock())
        scheduled = _instant(scheduled_at).astimezone(JST)
        local = now.astimezone(JST)
        _require(scheduled.time() == time(8) and scheduled <= now and
                 local.date() == scheduled.date() and local.hour == 8,
                 "expected the current 08:00 JST evaluation slot")
        _require(is_bank_business_day(scheduled.date()), "no evaluation on a bank holiday")
        source = _terminal_result(self.repo, run_path, now)
        days = _verified_calendar(self.repo)
        index = bisect_left(days, scheduled.date())
        _require(0 < index < len(days) and days[index] == scheduled.date() and days[index - 1] == source,
                 "morning notice requires the immediately preceding JPX publication")
        return self._stage(run_path, MORNING, now=now, target=scheduled.date().isoformat(),
                           scheduled_at=scheduled)
