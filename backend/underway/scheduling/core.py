"""Pure scheduling core: no I/O.

Rules:
  * Scheduled means assumed done: a non-recurring task gets at most ONE block
    across the whole horizon. No fallback / "if still open" blocks, ever.
  * Recurring tasks get one block per occurrence that falls in the horizon.
  * Highest effective score first, earliest suitable slot; tasks with a due
    date land on/before it when any slot allows; same-day items (due today,
    score >= same_day_score) go today.
  * Effective score = [NN] + balance boost for areas below their target.
  * Windows (weekday / cooking night / weekend+holiday) come from config.
    Every non-pqm calendar event is busy.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from underway.scheduling.config import SchedulerConfig

_EVERY_RE = re.compile(r"every!?\s+(\d+)?\s*(day|week|month|year)")
_EVERY_DAY_RE = re.compile(r"every!?\s+(\d+)?\s*day")
_WEEKEND_RE = re.compile(r"\b(sat|sun)")


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    score: int
    area: str
    due: date | None = None
    recurrence: str | None = None
    minutes: int = 60
    days: frozenset[int] | None = None
    earliest: time | None = None
    covered_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class Busy:
    start: datetime
    end: datetime
    title: str = ""


@dataclass(frozen=True)
class Block:
    task_id: str
    title: str
    start: datetime
    end: datetime
    reason: str
    minutes: int


@dataclass
class Window:
    start: datetime
    end: datetime
    weekend: bool
    cursor: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.cursor = self.start


@dataclass(frozen=True, order=True)
class _Job:
    tier: int
    neg_score: int
    deadline: date
    task_id: str
    task: Task = field(compare=False)
    occ: date | None = field(compare=False)
    eff: int = field(compare=False)


def is_weekend(d: date, cfg: SchedulerConfig) -> bool:
    return d.weekday() >= 5 or d in cfg.public_holidays


def build_windows(
    start: date,
    days: int,
    cfg: SchedulerConfig,
    cooking: Iterable[date] = (),
    now: datetime | None = None,
) -> list[Window]:
    cooking_days = set(cooking)
    out: list[Window] = []
    for i in range(days):
        d = start + timedelta(days=i)
        weekend = is_weekend(d, cfg)
        if weekend:
            spans = cfg.weekend_windows
        elif d.weekday() in cfg.cooking_weekdays or d in cooking_days:
            spans = cfg.cooking_windows
        else:
            spans = cfg.weekday_windows
        for a, b in spans:
            s, e = datetime.combine(d, a), datetime.combine(d, b)
            if now is not None and e <= now:
                continue
            elif now is not None and s < now:
                s = now
            else:
                pass  # window wholly in the future
            out.append(Window(s, e, weekend))
    return out


def area_balance(minutes_by_area: dict[str, float], cfg: SchedulerConfig) -> dict[str, int]:
    """Boost per area = half the percentage-point shortfall, capped."""
    total = sum(minutes_by_area.values()) or 1.0
    boosts: dict[str, int] = {}
    for area, target in cfg.areas.values():
        actual = minutes_by_area.get(area, 0.0) / total
        boosts[area] = int(min(cfg.max_boost, max(0.0, (target - actual) * 100 / 2)))
    return boosts


def occurrences(t: Task, start: date, end: date) -> list[date | None]:
    """Deadlines needing a block in [start, end]; [None] means once, no deadline."""
    if not t.recurrence:
        if t.due is not None and t.due > end:
            return []
        else:
            return [t.due]
    elif t.due is None or t.due > end:
        return []
    else:
        pass  # recurring and due inside the horizon
    rec = t.recurrence.lower()
    span = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if "sat" in rec or "sun" in rec:
        wanted = {5} if "sat" in rec else set()
        if "sun" in rec:
            wanted.add(6)
        else:
            pass  # Saturday only
        due = t.due
        return [d for d in span if d.weekday() in wanted and d >= due]
    else:
        pass  # interval recurrence
    m = _EVERY_RE.search(rec)
    if m and m.group(2) == "day":
        n = int(m.group(1) or 1)
        out: list[date | None] = []
        d = max(t.due, start)
        while d <= end:
            out.append(d)
            d += timedelta(days=n)
        return out
    else:
        return [max(t.due, start)]  # week/month/year: one occurrence per horizon


def period_days(t: Task) -> int:
    m = _EVERY_DAY_RE.search((t.recurrence or "").lower())
    return int(m.group(1) or 1) if m else 7


def _covered(t: Task, d: date | None, busy: list[Busy]) -> bool:
    if not t.covered_by or d is None:
        return False
    else:
        return any(b.start.date() == d and any(k in b.title.lower() for k in t.covered_by) for b in busy)


def _fits(
    t: Task,
    w: Window,
    busy: list[Busy],
    placed: list[Block],
    used: dict[date, int],
    cfg: SchedulerConfig,
) -> datetime | None:
    d = w.start.date()
    if t.days is not None and d.weekday() not in t.days:
        return None
    else:
        pass  # any day allowed
    s = w.cursor
    if t.earliest is not None and s.time() < t.earliest:
        s = datetime.combine(d, t.earliest)
    else:
        pass  # no earliest-start constraint
    cap = cfg.max_weekend_minutes if w.weekend else cfg.max_weekday_minutes
    if used.get(d, 0) + t.minutes > cap:
        return None
    else:
        pass  # daily cap has room
    taken = busy + [Busy(p.start, p.end) for p in placed]
    while s + timedelta(minutes=t.minutes) <= w.end:
        e = s + timedelta(minutes=t.minutes)
        clash = [b for b in taken if b.start < e and b.end > s]
        if not clash:
            return s
        else:
            s = max(b.end for b in clash)
    return None


def _jobs(
    tasks: Iterable[Task],
    busy: list[Busy],
    start: date,
    end: date,
    today: date,
    boosts: dict[str, int],
    cfg: SchedulerConfig,
) -> list[_Job]:
    jobs: list[_Job] = []
    for t in tasks:
        eff = t.score + boosts.get(t.area, 0)
        routine = bool(t.recurrence and t.days)  # fixed-window routine
        if eff < cfg.min_score and not routine:
            continue
        else:
            pass  # eligible
        for occ in occurrences(t, start, end):
            if _covered(t, occ, busy):
                continue
            else:
                pass  # needs a block
            same_day = occ is not None and occ <= today and t.score >= cfg.same_day_score
            # same-day safety, routines, in-horizon deadlines, then the rest
            if same_day:
                tier = 0
            elif routine:
                tier = 1
            elif occ is not None and not t.recurrence:
                tier = 2
            else:
                tier = 3
            jobs.append(_Job(tier, -eff, occ or date.max, t.id, t, occ, eff))
    return sorted(jobs)


def _candidates(t: Task, occ: date | None, windows: list[Window]) -> list[Window]:
    if t.recurrence and occ is not None:
        # keep each occurrence inside its own period
        cands = [w for w in windows if 0 <= (w.start.date() - occ).days < period_days(t)]
        if _WEEKEND_RE.search(t.recurrence.lower()):
            return [w for w in cands if w.start.date() == occ]
        else:
            return cands
    elif occ is not None:
        on_time = [w for w in windows if w.start.date() <= occ]
        return on_time + [w for w in windows if w.start.date() > occ]
    else:
        return list(windows)


def schedule(
    tasks: Iterable[Task],
    busy: list[Busy],
    start: date,
    days: int,
    cfg: SchedulerConfig,
    boosts: dict[str, int] | None = None,
    cooking: Iterable[date] = (),
    now: datetime | None = None,
    today: date | None = None,
    pinned: Iterable[Block] = (),
) -> list[Block]:
    """Plan blocks. ``pinned`` blocks are kept as-is and their tasks count as scheduled."""
    pins = list(pinned)
    end = start + timedelta(days=days - 1)
    windows = build_windows(start, days, cfg, cooking, now)
    placed: list[Block] = list(pins)
    used: dict[date, int] = {}
    for p in pins:
        used[p.start.date()] = used.get(p.start.date(), 0) + p.minutes
    once_done = {p.task_id for p in pins}
    pinned_occ = {(p.task_id, p.start.date()) for p in pins}
    for job in _jobs(tasks, busy, start, end, today or start, boosts or {}, cfg):
        t, occ = job.task, job.occ
        if not t.recurrence and t.id in once_done:
            continue  # scheduled means assumed done
        elif (
            t.recurrence
            and occ is not None
            and any(tid == t.id and occ <= d < occ + timedelta(days=period_days(t)) for tid, d in pinned_occ)
        ):
            continue  # this occurrence is already pinned
        else:
            pass  # needs placing
        for w in _candidates(t, occ, windows):
            s = _fits(t, w, busy, placed, used, cfg)
            if s is None:
                continue
            else:
                pass  # slot found
            e = s + timedelta(minutes=t.minutes)
            reason = f"score {t.score}"
            if job.eff > t.score:
                reason += f" +{job.eff - t.score} {t.area} below target"
            else:
                pass  # no boost
            if occ is not None and not t.recurrence:
                reason += f"; due {occ.isoformat()}"
            else:
                pass  # no deadline
            placed.append(Block(t.id, t.title, s, e, reason, t.minutes))
            used[s.date()] = used.get(s.date(), 0) + t.minutes
            once_done.add(t.id)
            break
    return sorted(placed, key=lambda b: (b.start, b.task_id))
