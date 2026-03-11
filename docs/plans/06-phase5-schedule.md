# Phase 5: Schedule Generation

## Goal

Port the AI-driven schedule generation system that reads tasks + calendar, generates a daily schedule, and optionally adds events to the calendar.

## Source Files

| Original | New |
|----------|-----|
| `schedule/schedule_routes.py` | `underway/viewsets/schedule.py` |
| `ai/schedule_generator.py` | `underway/schedule/generator.py` |
| `ai/ai_manager.py` | `underway/providers/ai_manager.py` (already ported in Phase 3) |

## Steps

### 5.1 Schedule Generator Service

Port `schedule_generator.py` as an async service:

```python
# underway/schedule/generator.py

class ScheduleGenerator:
    """Generates a daily schedule using AI based on tasks and calendar events."""

    async def generate(
        self,
        user: User,
        tasks: list[Task],
        events: list[CalendarEvent],
        session: AsyncSession,
    ) -> ScheduleResult:
        """Generate a schedule by calling the LLM with task/calendar context."""
        # 1. Build prompt with tasks and existing calendar events
        # 2. Call LLM (litellm.acompletion) with user's API key and model
        # 3. Parse response into time slots
        # 4. Return structured schedule
        ...

    async def generate_and_add_to_calendar(
        self,
        user: User,
        tasks: list[Task],
        events: list[CalendarEvent],
        calendar_provider: CalendarProvider,
        session: AsyncSession,
    ) -> ScheduleResult:
        """Generate schedule and create calendar events for each slot."""
        schedule = await self.generate(user, tasks, events, session)
        # Create calendar events for each time slot
        for slot in schedule.slots:
            await calendar_provider.create_event(...)
        return schedule
```

### 5.2 Schedule Pydantic Models

```python
# underway/schedule/models.py

class TimeSlot(BaseModel):
    start: datetime
    end: datetime
    title: str
    task_id: UUID | None = None
    description: str | None = None

class ScheduleResult(BaseModel):
    date: date
    slots: list[TimeSlot]
    summary: str | None = None
```

### 5.3 Schedule Routes

```python
# underway/viewsets/schedule.py

@router.post("/api/schedule/generate")
async def generate_schedule(request: Request):
    """Generate a daily schedule from tasks + calendar."""
    # 1. Get user's tasks (prioritized first)
    # 2. Get today's calendar events
    # 3. Call ScheduleGenerator.generate()
    # 4. Return ScheduleResult
    ...

@router.post("/api/schedule/generate-and-add")
async def generate_and_add_to_calendar(request: Request):
    """Generate schedule and add time blocks to calendar."""
    # 1. Same as above but also creates calendar events
    ...
```

### 5.4 Vue Frontend — Schedule

`frontend/src/views/ScheduleView.vue`:
- "Generate Schedule" button
- Display generated schedule as a timeline/list of time slots
- Each slot shows time range, task title, description
- "Generate & Add to Calendar" button
- Loading state during AI generation
- User's slot duration preference (from settings)

`frontend/src/components/ScheduleTimeline.vue`:
- Visual timeline of the day
- Time slots color-coded by type (task, meeting, break)

### 5.5 API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/schedule/generate` | Generate daily schedule |
| POST | `/api/schedule/generate-and-add` | Generate and add to calendar |

### 5.6 Tests

**Unit tests:**
- ScheduleGenerator with mocked LLM response
- TimeSlot/ScheduleResult model validation
- Prompt building with various task/event combinations
- Slot duration configuration respected

**Integration tests:**
- Generate endpoint returns valid schedule (mocked LLM)
- Generate-and-add creates calendar events (mocked provider)
- Respects user's schedule_slot_duration setting
- Handles empty task list gracefully
- Handles no calendar configured gracefully

**E2E tests (Playwright):**
- Schedule page loads
- Generate button produces a schedule display
- Time slots render correctly
- Generate & add shows success feedback

## Acceptance Criteria

- [ ] Schedule generation calls LLM with tasks + calendar context
- [ ] Generated schedule respects user's slot duration preference
- [ ] Generate-and-add creates calendar events
- [ ] Vue schedule page functional
- [ ] Handles edge cases (no tasks, no calendar, LLM errors)
- [ ] All tests pass
- [ ] Full feature parity with virtual_assistant achieved
