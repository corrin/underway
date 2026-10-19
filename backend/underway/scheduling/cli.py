"""Thin CLI: read connector dumps and config from disk, print planned blocks as JSON.

    python -m underway.scheduling.cli --tasks tasks.json --events events.json \
        --timelog timelog.csv --start YYYY-MM-DD [--days 7] [--config cfg.json]

Config lookup: --config, then $PQM_CONFIG, then config.local.json beside this
file (gitignored), then config.example.json.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from underway.scheduling.adapters import (
    busy_from_payload,
    minutes_by_area,
    pinned_from_payload,
    tasks_from_payload,
    to_event,
    unwrap,
)
from underway.scheduling.config import SchedulerConfig, config_from_dict
from underway.scheduling.core import area_balance, schedule

_HERE = Path(__file__).resolve().parent


def load_config(path: str | None = None) -> SchedulerConfig:
    for p in (path, os.environ.get("PQM_CONFIG"), _HERE / "config.local.json", _HERE / "config.example.json"):
        if p and Path(p).exists():
            raw: dict[str, Any] = json.loads(Path(p).read_text())
            return config_from_dict(raw)
        else:
            pass  # try the next location
    raise FileNotFoundError("no scheduler config found")


def run(argv: list[str] | None = None) -> dict[str, Any]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--events", required=True)
    ap.add_argument("--timelog", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--now")
    ap.add_argument("--cooking", default="", help="extra cooking-night dates, comma separated")
    ap.add_argument("--keep-today", action="store_true", help="keep today's existing pqm blocks")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    start = date.fromisoformat(a.start)
    now = datetime.fromisoformat(a.now) if a.now else None
    mins = minutes_by_area(Path(a.timelog).read_text(), start - timedelta(days=28), start)
    boosts = area_balance(mins, cfg)
    cooking = {date.fromisoformat(x) for x in a.cooking.split(",") if x}
    events = unwrap(Path(a.events).read_text())
    pinned = pinned_from_payload(events, start) if a.keep_today else []
    tasks = tasks_from_payload(unwrap(Path(a.tasks).read_text()), cfg)
    blocks = schedule(tasks, busy_from_payload(events), start, a.days, cfg, boosts, cooking, now, pinned=pinned)
    keep = {(p.task_id, p.start) for p in pinned}
    return {
        "boosts": boosts,
        "minutes_by_area": mins,
        "kept": [[p.task_id, p.start.isoformat()] for p in pinned],
        "blocks": [to_event(b, cfg) | {"task_id": b.task_id} for b in blocks if (b.task_id, b.start) not in keep],
    }


def main(argv: list[str] | None = None) -> None:
    print(json.dumps(run(argv), indent=1, default=str))


if __name__ == "__main__":
    main()
