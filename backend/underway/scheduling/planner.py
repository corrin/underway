"""Pure root-down activity selection. No database, network, or persistent queue."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from underway.scheduling.schemas import (
    CalendarBlock,
    IntentionNode,
    NodeProgress,
    Snapshot,
    SourceActivity,
    SourceRef,
    WeeklyPlan,
    Window,
)


def ancestors(nodes: dict[str, IntentionNode], node_id: str) -> list[str]:
    path: list[str] = []
    while node_id in nodes:
        path.append(node_id)
        parent = nodes[node_id].parent_id
        if parent is None:
            break
        else:
            node_id = parent
    return list(reversed(path))


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def rollups(snapshot: Snapshot, day: date) -> list[NodeProgress]:
    nodes = {node.id: node for node in snapshot.intentions.nodes}
    totals: dict[str, int] = defaultdict(int)
    total = 0
    for report in snapshot.reports:
        if week_start(report.date) != week_start(day):
            continue
        else:
            minutes = report.minutes or 0
            total += minutes
            for node_id in ancestors(nodes, report.node_id):
                totals[node_id] += minutes
    return [
        NodeProgress(
            node_id=node.id,
            minutes=totals[node.id],
            percentage_of_recorded_time=100 * totals[node.id] / total if total else 0,
            target_percentage=100 * totals[node.id] / node.weekly_minutes if node.weekly_minutes else None,
        )
        for node in nodes.values()
    ]


@dataclass
class Candidate:
    key: str
    node_id: str
    title: str
    path: list[str]
    source: SourceRef | None
    priority: int
    due: datetime | None
    deadline: datetime | None
    remaining: int | None
    windows: list[Window]


def _matches(binding: SourceRef, activity: SourceActivity) -> bool:
    source = activity.source
    return (
        binding.provider == source.provider
        and binding.account == source.account
        and (
            binding.task_id == source.task_id
            if binding.task_id is not None
            else binding.container_id == source.container_id
        )
    )


def candidates(snapshot: Snapshot, warnings: list[str]) -> list[Candidate]:
    nodes = {node.id: node for node in snapshot.intentions.nodes}
    parents = {node.parent_id for node in nodes.values()}
    result: list[Candidate] = []
    assigned: dict[str, list[SourceActivity]] = defaultdict(list)
    source_index = {activity.source.key: activity for activity in snapshot.activities}
    if len(source_index) != len(snapshot.activities):
        raise ValueError("Duplicate task identity in the source snapshot.")
    else:
        pass

    def source_path(activity: SourceActivity) -> list[str]:
        keys = [activity.source.key]
        while activity.parent_task_id:
            parent_key = activity.source.model_copy(update={"task_id": activity.parent_task_id}).key
            if parent_key in keys:
                raise ValueError("Source task hierarchy contains a cycle.")
            elif parent_key not in source_index:
                break
            else:
                keys.insert(0, parent_key)
                activity = source_index[parent_key]
        return keys

    for activity in snapshot.activities:
        lineage = source_path(activity)
        matches = [
            node
            for node in nodes.values()
            if any(_matches(ref, activity) or ref.key in lineage for ref in node.sources)
        ]
        if not matches:
            if activity.deadline:
                warnings.append(
                    f"{activity.title}: firm deadline cannot be scheduled until its source is bound to the tree."
                )
            else:
                pass
            continue
        else:
            # Explicit task bindings beat project bindings; otherwise the deepest binding wins.
            matches.sort(
                key=lambda node: (
                    max((lineage.index(ref.key) + 1 for ref in node.sources if ref.key in lineage), default=0),
                    len(ancestors(nodes, node.id)),
                    node.id,
                ),
                reverse=True,
            )
            assigned[matches[0].id].append(activity)
    for node in nodes.values():
        path = ancestors(nodes, node.id)
        windows: list[Window] = []
        for ancestor in path:
            if nodes[ancestor].preferred_windows:
                windows = nodes[ancestor].preferred_windows
            else:
                pass
        for activity in assigned[node.id]:
            override = node.estimated_minutes if any(ref.key == activity.source.key for ref in node.sources) else None
            effort = override or activity.estimated_minutes or snapshot.intentions.slot_minutes
            spent = sum(
                report.minutes or 0
                for report in snapshot.reports
                if report.source is not None and report.source.key == activity.source.key
            )
            deadline = node.deadline or activity.deadline
            if deadline and not (override or activity.estimated_minutes):
                warnings.append(f"{activity.title}: deadline needs an effort estimate; reserving one review slot.")
            else:
                pass
            if spent >= effort:
                warnings.append(
                    f"{activity.title}: recorded effort exceeds its estimate; confirm completion or revise it."
                )
            else:
                pass
            result.append(
                Candidate(
                    key=activity.source.key,
                    node_id=node.id,
                    title=activity.title,
                    path=[*path, *source_path(activity)],
                    source=activity.source,
                    priority=activity.priority,
                    due=activity.due,
                    deadline=deadline,
                    remaining=max(snapshot.intentions.slot_minutes if spent >= effort else effort - spent, 1),
                    windows=windows,
                )
            )
        if node.id not in parents and node.repeatable and node.deadline is None:
            result.append(Candidate(node.id, node.id, node.title, path, None, 0, None, None, None, windows))
        elif node.id not in parents and not node.sources and (node.estimated_minutes or node.deadline):
            effort = node.estimated_minutes or snapshot.intentions.slot_minutes
            spent = sum(
                report.minutes or 0
                for report in snapshot.reports
                if report.node_id == node.id and report.source is None
            )
            if not node.estimated_minutes:
                warnings.append(f"{node.title}: deadline needs an effort estimate; reserving one review slot.")
            elif spent >= effort:
                warnings.append(f"{node.title}: recorded effort exceeds its estimate; revise the intention.")
            else:
                pass
            result.append(
                Candidate(
                    node.id,
                    node.id,
                    node.title,
                    path,
                    None,
                    0,
                    None,
                    node.deadline,
                    snapshot.intentions.slot_minutes if spent >= effort else effort - spent,
                    windows,
                )
            )
        else:
            pass
    return result


def in_window(windows: list[Window], start: datetime, end: datetime, zone: ZoneInfo) -> bool:
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    return not windows or any(
        local_start.weekday() in window.weekdays
        and local_start.date() == local_end.date()
        and window.start <= local_start.time()
        and local_end.time() <= window.end
        for window in windows
    )


def free_slots(snapshot: Snapshot, now: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    zone = ZoneInfo(snapshot.intentions.timezone)
    step = timedelta(minutes=snapshot.intentions.slot_minutes)
    busy = sorted([*snapshot.busy, *snapshot.preserved], key=lambda block: block.start)
    result: list[tuple[datetime, datetime]] = []
    day = now.astimezone(zone).date()
    while day <= end.astimezone(zone).date():
        for window in snapshot.intentions.allowed_windows:
            if day.weekday() not in window.weekdays:
                continue
            else:
                start = datetime.combine(day, window.start, zone).astimezone(UTC)
                stop = min(datetime.combine(day, window.end, zone).astimezone(UTC), end)
            while start + step <= stop:
                finish = start + step
                if start < now:
                    start += step
                    continue
                else:
                    pass
                overlaps = [block for block in busy if block.start < finish and start < block.end]
                if overlaps:
                    start = max(block.end.astimezone(UTC) for block in overlaps)
                else:
                    if not any(a < finish and start < b for a, b in result):
                        result.append((start, finish))
                    else:
                        pass
                    start = finish
        day += timedelta(days=1)
    return sorted(result)


class PlannerState:
    def __init__(self, snapshot: Snapshot, choices: list[Candidate], now: datetime) -> None:
        self.nodes = {node.id: node for node in snapshot.intentions.nodes}
        self.zone = ZoneInfo(snapshot.intentions.timezone)
        self.minutes: dict[tuple[str, date], float] = defaultdict(float)
        self.last_occurrence: dict[str, date] = {}
        self.last_selected: dict[str, datetime] = {}
        self.remaining = {choice.key: choice.remaining for choice in choices}
        for report in snapshot.reports:
            self.credit(report.node_id, report.date, report.minutes or 0)
            at = datetime.combine(report.date, time.min, self.zone)
            keys = ancestors(self.nodes, report.node_id)
            if report.source:
                keys.append(report.source.key)
            else:
                pass
            for key in keys:
                self.last_selected[key] = max(at, self.last_selected.get(key, at))
            for node_id in report.fulfilled_intentions:
                self.last_occurrence[node_id] = max(report.date, self.last_occurrence.get(node_id, report.date))
        for block in snapshot.preserved:
            if block.node_id and block.end > now:
                minutes = (block.end - max(now, block.start)).total_seconds() / 60
                self.allocate(block, minutes)
            else:
                pass

    def credit(self, node_id: str, day: date, minutes: float) -> None:
        for ancestor in ancestors(self.nodes, node_id):
            self.minutes[ancestor, week_start(day)] += minutes

    def allocate(self, block: CalendarBlock, minutes: float) -> None:
        if block.node_id is None:
            return
        else:
            day = block.start.astimezone(self.zone).date()
        self.credit(block.node_id, day, minutes)
        key = block.source.key if block.source else block.node_id
        remaining = self.remaining.get(key)
        if remaining is not None:
            self.remaining[key] = max(0, remaining - math.ceil(minutes))
        else:
            pass
        for node_id in [*ancestors(self.nodes, block.node_id), key]:
            self.last_selected[node_id] = max(block.start, self.last_selected.get(node_id, block.start))
        for node_id in block.fulfilled_intentions:
            self.last_occurrence[node_id] = max(day, self.last_occurrence.get(node_id, day))


class ChildSelectionPolicy(Protocol):
    def choose(
        self,
        groups: dict[str, list[Candidate]],
        state: PlannerState,
        start: datetime,
        end: datetime,
    ) -> tuple[str, str]: ...


class TargetProgressPolicy:
    """Compare intentions in each subtree, not the number of candidate tasks."""

    def choose(
        self,
        groups: dict[str, list[Candidate]],
        state: PlannerState,
        start: datetime,
        end: datetime,
    ) -> tuple[str, str]:
        ranked: list[tuple[tuple[float, float, int, float, float, str], str]] = []
        day = start.astimezone(state.zone).date()
        for key, choices in groups.items():
            goals = {
                node_id
                for choice in choices
                for node_id in choice.path[choice.path.index(key) :]
                if node_id in state.nodes
            }
            scores: list[tuple[float, float, str]] = []
            preferred = any(in_window(choice.windows, start, end, state.zone) for choice in choices)
            for node_id in goals:
                node = state.nodes[node_id]
                if node.interval_days:
                    last = state.last_occurrence.get(node_id)
                    elapsed = (day - last).days if last else node.interval_days
                    if elapsed >= node.interval_days:
                        scores.append((1, -elapsed / node.interval_days, f"{node.title}: catch-up interval is due"))
                    else:
                        pass
                else:
                    pass
                if node.weekly_minutes:
                    ratio = state.minutes[node_id, week_start(day)] / node.weekly_minutes
                    scores.append(
                        (2, ratio + (0 if preferred else 0.25), f"{node.title}: {ratio:.0%} of weekly target")
                    )
                else:
                    pass
            tier, score, reason = (
                min(scores) if scores else (3, 0 if preferred else 0.25, "Source priority and recency")
            )
            priority = max(choice.priority for choice in choices)
            due = (
                min(
                    (choice.due.replace(tzinfo=state.zone) if choice.due.tzinfo is None else choice.due).timestamp()
                    for choice in choices
                    if choice.due is not None
                )
                if any(choice.due is not None for choice in choices)
                else math.inf
            )
            last_selected = state.last_selected.get(key, datetime(1970, 1, 1, tzinfo=UTC)).timestamp()
            ranked.append(((tier, score, -priority, due, last_selected, key), reason))
        rank, reason = min(ranked)
        return rank[-1], reason


def select_activity(
    choices: list[Candidate], state: PlannerState, start: datetime, end: datetime, policy: ChildSelectionPolicy
) -> tuple[Candidate, str]:
    depth = 0
    reason = "Available activity"
    while len(choices) > 1 or depth < len(choices[0].path):
        groups: dict[str, list[Candidate]] = defaultdict(list)
        for choice in choices:
            key = choice.path[min(depth, len(choice.path) - 1)]
            groups[key].append(choice)
        key, explanation = policy.choose(groups, state, start, end)
        if explanation != "Source priority and recency":
            reason = explanation
        else:
            pass
        choices = groups[key]
        depth += 1
        if len(choices) == 1 and depth >= len(choices[0].path):
            break
        else:
            pass
    return choices[0], reason


def make_block(choice: Candidate, start: datetime, end: datetime, state: PlannerState, reason: str) -> CalendarBlock:
    identifier = hashlib.sha256(start.isoformat().encode()).hexdigest()[:32]
    return CalendarBlock(
        id=identifier,
        start=start,
        end=end,
        title=choice.title,
        node_id=choice.node_id,
        source=choice.source,
        fulfilled_intentions=[
            node_id for node_id in ancestors(state.nodes, choice.node_id) if state.nodes[node_id].interval_days
        ],
        reason=reason,
    )


def build_week(snapshot: Snapshot, now: datetime, policy: ChildSelectionPolicy | None = None) -> WeeklyPlan:
    """Build seven local days. Retained reservations influence projected allocation only."""
    if now.tzinfo is None:
        raise ValueError("The planner requires an aware current timestamp.")
    else:
        now = now.astimezone(UTC)
    zone = ZoneInfo(snapshot.intentions.timezone)
    end = (now.astimezone(zone) + timedelta(days=7)).astimezone(UTC)
    plan = WeeklyPlan(blocks=[block for block in snapshot.preserved if block.end > now and block.start < end])
    choices = candidates(snapshot, plan.warnings)
    state = PlannerState(snapshot, choices, now)
    dated = sorted((choice for choice in choices if choice.deadline), key=lambda choice: (choice.deadline, choice.key))
    horizon = max([end, *(choice.deadline for choice in dated if choice.deadline is not None)])
    slots = free_slots(snapshot, now, horizon)
    reserved: dict[datetime, tuple[Candidate, str]] = {}
    step = snapshot.intentions.slot_minutes
    for choice in dated:
        assert choice.deadline is not None
        # A protected reservation after the deadline cannot discharge work due before it.
        timely_credit = sum(
            max(0, (block.end - max(now, block.start)).total_seconds() / 60)
            for block in snapshot.preserved
            if (block.source.key if block.source else block.node_id) == choice.key and block.end <= choice.deadline
        )
        deadline_remaining = max(0, (choice.remaining or snapshot.intentions.slot_minutes) - timely_credit)
        if deadline_remaining == 0:
            continue
        else:
            effort = deadline_remaining or snapshot.intentions.slot_minutes
        needed = math.ceil(effort / step)
        before = [(start, stop) for start, stop in slots if stop <= choice.deadline and start not in reserved]
        margin = [(start, stop) for start, stop in before if stop <= choice.deadline - timedelta(hours=24)]
        available = margin if len(margin) >= needed else before
        if len(margin) < needed:
            plan.warnings.append(f"{choice.title}: less than 24 hours of deadline margin available.")
        else:
            pass
        available.sort(key=lambda slot: (in_window(choice.windows, slot[0], slot[1], zone), slot[0]), reverse=True)
        for start, _ in available[:needed]:
            reserved[start] = (choice, f"Firm deadline: {choice.deadline.isoformat()}")
        if len(available) < needed:
            plan.warnings.append(f"{choice.title}: insufficient capacity before its firm deadline.")
        else:
            pass
    # Credit all future deadline reservations before ordinary allocation, including
    # reservations beyond the visible horizon. They are never treated as actuals.
    deadline_blocks: dict[datetime, CalendarBlock] = {}
    for start, stop in slots:
        if start in reserved:
            choice, reason = reserved[start]
            block = make_block(choice, start, stop, state, reason)
            deadline_blocks[start] = block
            state.allocate(block, step)
        else:
            pass
    selector = policy or TargetProgressPolicy()
    for start, stop in slots:
        if start >= end:
            continue
        elif start in deadline_blocks:
            plan.blocks.append(deadline_blocks[start])
            continue
        else:
            pass
        available_choices = [
            choice for choice in choices if (remaining := state.remaining[choice.key]) is None or remaining > 0
        ]
        if not available_choices:
            continue
        else:
            choice, reason = select_activity(available_choices, state, start, stop, selector)
        block = make_block(choice, start, stop, state, reason)
        plan.blocks.append(block)
        state.allocate(block, step)
    week = week_start(now.astimezone(zone).date())
    for node in state.nodes.values():
        if node.weekly_minutes and state.minutes[node.id, week] < node.weekly_minutes:
            plan.warnings.append(f"{node.title}: available slots do not cover this week's minimum.")
        else:
            pass
    plan.blocks.sort(key=lambda block: block.start)
    plan.warnings = list(dict.fromkeys(plan.warnings))
    return plan
