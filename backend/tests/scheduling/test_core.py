"""Scheduling core, adapters and CLI, using synthetic fixtures only."""

from __future__ import annotations

import itertools
import json
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pytest

from underway.scheduling.adapters import minutes_by_area, task_from_todoist
from underway.scheduling.cli import load_config, run
from underway.scheduling.config import SchedulerConfig, config_from_dict
from underway.scheduling.core import Block, Busy, Task, area_balance, is_weekend, schedule

FIX = Path(__file__).parent / "fixtures"
MON = date(2030, 3, 4)  # a Monday
TUE = date(2030, 3, 5)
THU = date(2030, 3, 7)
SAT = date(2030, 3, 9)
SUN = date(2030, 3, 10)


@pytest.fixture
def cfg() -> SchedulerConfig:
    raw: dict[str, Any] = json.loads((FIX / "config.test.json").read_text())
    return config_from_dict(raw)


def mk(
    tid: str,
    score: int,
    *,
    area: str = "Home",
    due: date | None = None,
    recurrence: str | None = None,
    minutes: int = 60,
    days: frozenset[int] | None = None,
    earliest: time | None = None,
    covered_by: tuple[str, ...] = (),
) -> Task:
    return Task(tid, f"[{score}] {tid}", score, area, due, recurrence, minutes, days, earliest, covered_by)


def many() -> list[Task]:
    return [mk(f"t{i}", 40 + i, minutes=60 + 30 * (i % 3)) for i in range(25)] + [
        mk("chore", 55, recurrence="every sat, sun", due=SAT, minutes=45, days=frozenset({5, 6}), earliest=time(9)),
        mk("gym", 70, recurrence="every! 3 days", due=TUE, minutes=60),
    ]


def test_no_task_scheduled_twice(cfg: SchedulerConfig) -> None:
    counts = Counter(b.task_id for b in schedule(many(), [], TUE, 7, cfg))
    for tid, n in counts.items():
        if tid not in {"chore", "gym"}:
            assert n == 1, f"{tid} scheduled {n} times"
        else:
            pass  # recurring tasks may repeat


def test_long_high_task_gets_one_block_not_fallback(cfg: SchedulerConfig) -> None:
    assert len(schedule([mk("release", 85, area="Work")], [], TUE, 7, cfg)) == 1


def test_recurring_gets_each_occurrence(cfg: SchedulerConfig) -> None:
    blocks = schedule(many(), [], TUE, 7, cfg)
    assert [b.start.date() for b in blocks if b.task_id == "chore"] == [SAT, SUN]
    gym = [b.start.date() for b in blocks if b.task_id == "gym"]
    assert len(gym) == len(set(gym)) >= 2


def test_no_overlaps_and_within_windows(cfg: SchedulerConfig) -> None:
    busy = [Busy(datetime(2030, 3, 6, 17), datetime(2030, 3, 6, 19), "appointment")]
    blocks = schedule(many(), busy, TUE, 7, cfg)
    spans = sorted([(b.start, b.end) for b in blocks] + [(x.start, x.end) for x in busy])
    for (_, e1), (s2, _) in itertools.pairwise(spans):
        assert e1 <= s2
    for b in blocks:
        if not is_weekend(b.start.date(), cfg):
            assert time(17) <= b.start.time()
            assert b.end.time() <= time(21, 30)
            assert not (b.start.time() < time(19, 30) and b.end.time() > time(18, 30))
        else:
            pass  # weekend windows checked elsewhere


def test_cooking_nights(cfg: SchedulerConfig) -> None:
    for b in schedule(many(), [], TUE, 7, cfg, cooking={TUE}):
        if b.start.weekday() in (1, 3, 4):
            assert b.start.time() >= time(20, 30)
        else:
            pass  # not a cooking night


def test_same_day_safety_goes_today(cfg: SchedulerConfig) -> None:
    blocks = schedule([*many(), mk("urgent", 80, due=TUE)], [], TUE, 7, cfg)
    assert next(b for b in blocks if b.task_id == "urgent").start.date() == TUE


def test_due_date_respected(cfg: SchedulerConfig) -> None:
    blocks = schedule([*many(), mk("due", 45, due=THU)], [], TUE, 7, cfg)
    assert next(b for b in blocks if b.task_id == "due").start.date() <= THU


def test_balance_boost(cfg: SchedulerConfig) -> None:
    boosts = area_balance({"Home": 900, "Fun": 0, "Work": 100}, cfg)
    assert boosts["Fun"] > 0
    assert boosts["Home"] == 0
    blocks = schedule([mk("p", 40, area="Home"), mk("c", 35, area="Fun")], [], THU, 1, cfg, boosts)
    assert blocks[0].task_id == "c"  # Thursday is a cooking night: one hour only


def test_pinned_task_not_rebooked(cfg: SchedulerConfig) -> None:
    pin = Block("release", "[85] release", datetime(2030, 3, 5, 20, 30), datetime(2030, 3, 5, 21, 30), "kept", 60)
    blocks = schedule([*many(), mk("release", 85)], [], TUE, 7, cfg, pinned=[pin])
    assert [b for b in blocks if b.task_id == "release"] == [pin]


def test_routine_first_in_window(cfg: SchedulerConfig) -> None:
    chore = [b for b in schedule(many(), [], TUE, 7, cfg) if b.task_id == "chore"]
    assert all(b.start.time() == time(9) for b in chore)


def test_low_score_not_promoted(cfg: SchedulerConfig) -> None:
    assert schedule([mk("low", 10)], [], TUE, 7, cfg) == []


def test_covered_by_own_event(cfg: SchedulerConfig) -> None:
    busy = [Busy(datetime(2030, 3, 7, 7, 45), datetime(2030, 3, 7, 8, 45), "Gym")]
    t = mk("w", 52, recurrence="every! 3 days", due=THU, covered_by=("gym",))
    assert THU not in [b.start.date() for b in schedule([t], busy, TUE, 7, cfg)]


def test_deterministic(cfg: SchedulerConfig) -> None:
    assert schedule(many(), [], TUE, 7, cfg) == schedule(list(reversed(many())), [], TUE, 7, cfg)


def test_todoist_adapter_skips(cfg: SchedulerConfig) -> None:
    assert task_from_todoist({"id": "x", "content": "* Header"}, cfg) is None
    assert task_from_todoist({"id": "x", "content": "Waiting: someone", "labels": ["waiting"]}, cfg) is None
    assert task_from_todoist({"id": "x", "content": "[30] Other", "labels": ["someone-else"]}, cfg) is None
    t = task_from_todoist({"id": "x", "content": "[30] Thing", "labels": [], "projectId": "proj-play"}, cfg)
    assert t is not None
    assert (t.score, t.area) == (30, "Fun")


def test_sheet_serial_dates() -> None:
    text = "h\n2030-03-01-03,47543,120,task:x,n,Work > a\n2030-03-02-01,,5,task:y,n,Fun\n"
    assert minutes_by_area(text, date(2030, 2, 25), MON) == {"Work": 120.0, "Fun": 5.0}


def test_example_config_loads() -> None:
    assert load_config(str(Path(__file__).parents[2] / "underway/scheduling/config.example.json")).areas


def test_cli_with_fixtures() -> None:
    out = run(
        [
            "--config", str(FIX / "config.test.json"),
            "--tasks", str(FIX / "tasks.json"),
            "--events", str(FIX / "events.json"),
            "--timelog", str(FIX / "timelog.csv"),
            "--start", MON.isoformat(),
        ]
    )  # fmt: skip
    ids = Counter(b["task_id"] for b in out["blocks"])
    assert ids["task-a"] == 1
    assert "task-c" not in ids  # skip label
    assert ids["task-chore"] == 2
    assert all(b["timeZone"] == "Etc/UTC" for b in out["blocks"])
