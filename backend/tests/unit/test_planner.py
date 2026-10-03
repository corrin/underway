"""Behavioural checks for the disposable weekly queue."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from pydantic import ValidationError

from underway.scheduling.planner import build_week, candidates, free_slots, rollups
from underway.scheduling.schemas import (
    ActivityReport,
    CalendarBlock,
    IntentionNode,
    Intentions,
    Snapshot,
    SourceActivity,
    SourceRef,
    Window,
)

NOW = datetime(2026, 10, 5, 8, tzinfo=UTC)


def snapshot(*nodes: IntentionNode) -> Snapshot:
    return Snapshot(
        intentions=Intentions(
            timezone="UTC",
            nodes=list(nodes),
            allowed_windows=[Window(weekdays=list(range(7)), start=time(9), end=time(12))],
        )
    )


def test_balance_uses_fraction_and_continues_after_target() -> None:
    state = snapshot(
        IntentionNode(id="a", title="A", weekly_minutes=60), IntentionNode(id="b", title="B", weekly_minutes=120)
    )
    plan = build_week(state, NOW)
    assert len(plan.blocks) == 21
    assert [block.node_id for block in plan.blocks[:3]] == ["a", "b", "b"]
    assert sum(block.node_id == "b" for block in plan.blocks) == 14
    assert all(row.minutes == 0 for row in rollups(state, NOW.date()))


def test_parent_report_rolls_up_never_down() -> None:
    state = snapshot(
        IntentionNode(id="root", title="Life"),
        IntentionNode(id="friends", parent_id="root", title="Friends"),
        IntentionNode(id="sam", parent_id="friends", title="Sam"),
    )
    state.reports = [ActivityReport(node_id="friends", date=NOW.date(), minutes=90)]
    totals = {row.node_id: row for row in rollups(state, NOW.date())}
    assert totals["root"].minutes == totals["friends"].minutes == 90
    assert totals["sam"].minutes == 0
    assert totals["friends"].percentage_of_recorded_time == 100


def test_overdue_descendant_raises_branch_then_any_friend_can_satisfy() -> None:
    state = snapshot(
        IntentionNode(id="work", title="Work", weekly_minutes=600),
        IntentionNode(id="life", title="Life"),
        IntentionNode(id="friends", parent_id="life", title="Friends", interval_days=7),
        IntentionNode(id="sam", parent_id="friends", title="Sam"),
        IntentionNode(id="pat", parent_id="friends", title="Pat"),
    )
    state.reports = [
        ActivityReport(node_id="friends", date=NOW.date() - timedelta(days=14), fulfilled_intentions=["friends"])
    ]
    plan = build_week(state, NOW)
    assert plan.blocks[0].node_id in {"sam", "pat"}
    assert plan.blocks[0].fulfilled_intentions == ["friends"]
    assert plan.blocks[1].node_id == "work"
    assert state.reports[0].date == NOW.date() - timedelta(days=14)


def test_unqualified_minutes_do_not_reset_cadence() -> None:
    state = snapshot(
        IntentionNode(id="friends", title="Friends", interval_days=7),
        IntentionNode(id="work", title="Work", weekly_minutes=600),
    )
    state.reports = [ActivityReport(node_id="friends", date=NOW.date(), minutes=60)]
    assert build_week(state, NOW).blocks[0].node_id == "friends"


def test_week_is_local_monday_to_sunday() -> None:
    state = snapshot(IntentionNode(id="a", title="A", weekly_minutes=60))
    state.reports = [
        ActivityReport(node_id="a", date=date(2026, 10, 4), minutes=120),
        ActivityReport(node_id="a", date=date(2026, 10, 5), minutes=30),
    ]
    assert rollups(state, NOW.date())[0].minutes == 30
    assert rollups(state, NOW.date())[0].target_percentage == 50


def test_busy_and_preserved_blocks_are_hard_constraints() -> None:
    state = snapshot(IntentionNode(id="a", title="A"))
    state.busy = [CalendarBlock(id="meeting", start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=2))]
    kept = CalendarBlock(
        id="kept",
        title="Chosen",
        node_id="a",
        start=NOW + timedelta(hours=2),
        end=NOW + timedelta(hours=3),
        protected=True,
    )
    state.preserved = [kept]
    blocks = build_week(state, NOW).blocks
    assert kept in blocks
    assert not any(b.start < state.busy[0].end and b.end > state.busy[0].start for b in blocks)
    assert len({b.start for b in blocks}) == len(blocks)


def test_preferred_hours_are_soft_and_inherited() -> None:
    state = snapshot(
        IntentionNode(id="a", title="A", preferred_windows=[Window(weekdays=[6], start=time(19), end=time(20))]),
        IntentionNode(id="child", parent_id="a", title="Child", weekly_minutes=60),
    )
    assert len(build_week(state, NOW).blocks) == 21


def test_firm_deadline_reserves_effort_but_due_date_does_not() -> None:
    state = snapshot(
        IntentionNode(
            id="project",
            title="Project",
            repeatable=False,
            sources=[SourceRef(provider="todoist", account="me", container_id="p")],
        )
    )
    source = SourceRef(provider="todoist", account="me", container_id="p", task_id="task")
    state.activities = [
        SourceActivity(
            source=source, title="Delivery", deadline=NOW + timedelta(days=2, hours=4), estimated_minutes=120
        )
    ]
    plan = build_week(state, NOW)
    assert len(plan.blocks) == 2
    assert all(b.end <= NOW + timedelta(days=1, hours=4) for b in plan.blocks)
    assert all("Firm deadline" in b.reason for b in plan.blocks)
    state.activities[0].due = state.activities[0].deadline
    state.activities[0].deadline = None
    assert all("Firm deadline" not in b.reason for b in build_week(state, NOW).blocks)


def test_unachievable_deadline_warns() -> None:
    state = snapshot(
        IntentionNode(
            id="finite", title="Delivery", repeatable=False, deadline=NOW + timedelta(hours=2), estimated_minutes=180
        ),
        IntentionNode(id="other", title="Other"),
    )
    plan = build_week(state, NOW)
    assert any("insufficient capacity" in w for w in plan.warnings)
    assert any(b.node_id == "other" for b in plan.blocks)


def test_far_deadline_uses_capacity_beyond_visible_week() -> None:
    state = snapshot(
        IntentionNode(
            id="finite", title="Delivery", repeatable=False, deadline=NOW + timedelta(days=9), estimated_minutes=600
        ),
        IntentionNode(id="other", title="Other"),
    )
    plan = build_week(state, NOW)
    assert any(b.node_id == "finite" for b in plan.blocks)
    assert all(row.minutes == 0 for row in rollups(state, NOW.date()))


def test_source_descendants_and_account_identity() -> None:
    binding = SourceRef(provider="todoist", account="me", container_id="p", task_id="parent")
    state = snapshot(IntentionNode(id="project", title="Project", sources=[binding], repeatable=False))
    state.activities = [
        SourceActivity(source=binding, title="Parent"),
        SourceActivity(source=binding.model_copy(update={"task_id": "child"}), title="Child", parent_task_id="parent"),
        SourceActivity(source=binding.model_copy(update={"account": "other"}), title="Other account"),
    ]
    choices = candidates(state, [])
    assert {c.title for c in choices} == {"Parent", "Child"}
    assert choices[1].path[-2:] == [binding.key, state.activities[1].source.key]
    assert len(build_week(state, NOW).blocks) == 2


def test_reported_effort_reduces_budget_without_inventing_completion() -> None:
    binding = SourceRef(provider="todoist", account="me", container_id="p", task_id="t")
    state = snapshot(IntentionNode(id="p", title="Project", sources=[binding], repeatable=False))
    state.activities = [SourceActivity(source=binding, title="Task", estimated_minutes=180)]
    state.reports = [ActivityReport(node_id="p", source=binding, date=NOW.date(), minutes=120)]
    assert len(build_week(state, NOW).blocks) == 1
    state.reports[0].minutes = 180
    assert any("confirm completion" in w for w in build_week(state, NOW).warnings)
    assert len(build_week(state, NOW).blocks) == 1


def test_dst_slots_use_elapsed_minutes() -> None:
    state = snapshot(IntentionNode(id="a", title="A"))
    state.intentions.timezone = "Pacific/Auckland"
    state.intentions.allowed_windows = [Window(weekdays=[6], start=time(1), end=time(4))]
    start = datetime(2026, 9, 26, 12, tzinfo=UTC)
    slots = free_slots(state, start, start + timedelta(days=1))
    assert len(slots) == 2
    assert all((end - begin).total_seconds() == 3600 for begin, end in slots)


def test_deadline_without_estimate_is_visible_as_review_work() -> None:
    state = snapshot(IntentionNode(id="delivery", title="Delivery", deadline=NOW + timedelta(days=2)))
    plan = build_week(state, NOW)
    assert len(plan.blocks) == 1
    assert any("effort estimate" in warning for warning in plan.warnings)


def test_finite_node_reports_reduce_remaining_effort() -> None:
    state = snapshot(IntentionNode(id="delivery", title="Delivery", repeatable=False, estimated_minutes=120))
    state.reports = [ActivityReport(node_id="delivery", date=NOW.date(), minutes=60)]
    assert len(build_week(state, NOW).blocks) == 1


@pytest.mark.parametrize(
    "document",
    [
        {"timezone": "not/a/zone"},
        {"nodes": [{"id": "a", "title": "A", "parent_id": "a"}]},
        {"nodes": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]},
        {"enabled": True},
        {"allowed_windows": [{"weekdays": [7], "start": "09:00", "end": "10:00"}]},
    ],
)
def test_invalid_intentions_fail_before_planning(document: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Intentions.model_validate(document)


def test_completed_bound_action_does_not_return_as_standalone_work() -> None:
    ref = SourceRef(provider="todoist", account="me", container_id="p", task_id="done")
    state = snapshot(
        IntentionNode(
            id="done",
            title="Completed source",
            repeatable=False,
            sources=[ref],
            estimated_minutes=120,
            deadline=NOW + timedelta(days=2),
        )
    )
    assert build_week(state, NOW).blocks == []


def test_preserved_work_after_deadline_does_not_discharge_deadline() -> None:
    state = snapshot(
        IntentionNode(
            id="delivery",
            title="Delivery",
            repeatable=False,
            estimated_minutes=60,
            deadline=NOW + timedelta(days=1, hours=4),
        )
    )
    state.preserved = [
        CalendarBlock(
            id="late",
            node_id="delivery",
            start=NOW + timedelta(days=2),
            end=NOW + timedelta(days=2, hours=1),
            protected=True,
        )
    ]
    plan = build_week(state, NOW)
    assert any(block.node_id == "delivery" and block.end <= state.intentions.nodes[0].deadline for block in plan.blocks)
    assert any(block.id == "late" for block in plan.blocks)


def test_task_effort_override_does_not_multiply_across_descendants() -> None:
    ref = SourceRef(provider="todoist", account="me", container_id="p", task_id="parent")
    state = snapshot(IntentionNode(id="project", title="Project", sources=[ref], estimated_minutes=300))
    state.activities = [
        SourceActivity(source=ref, title="Parent"),
        SourceActivity(
            source=ref.model_copy(update={"task_id": "child"}),
            title="Child",
            parent_task_id="parent",
            estimated_minutes=60,
        ),
    ]
    choices = candidates(state, [])
    assert next(choice for choice in choices if choice.title == "Child").remaining == 60
