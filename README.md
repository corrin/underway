# Aligned

**Spend your time on what matters to you.**

Aligned is a decision engine for personal time. Most people know how they *want* to spend their days — health, relationships, meaningful work — but daily decisions drift away from those intentions. Aligned acts as an external executive function that continuously steers your day back toward your stated priorities.

It exists to answer one question:

> **"What should I do next?"**

If it can't give you a useful answer to that, the product is failing.

## How it works

Aligned runs a continuous control loop:

```
Priorities → Schedule → Behaviour → Feedback → Adjust
```

1. You define your priorities (e.g. *8 hours of fitness per week*, *call Joe every 30 days*, *ship the SMS gateway by Friday*).
2. Aligned schedules time against them.
3. You report what you actually did.
4. The schedule is rewritten.

There are two channels:

- **Chat (feedback in)** — report completed work, refine goals, resolve ambiguity. *"I spent 2 hours on the SMS gateway."*
- **Calendar (action out)** — Aligned writes 30-minute blocks to a dedicated calendar. The next block is always its current recommendation for what you should do next.

Aligned is not a task tracker. It's a decision engine for time. Every feature is judged on whether it improves the answer to *"what next?"*.

## Architecture

Three subsystems operate over shared state (goals, activity log, calendar):

- **Goal Engine** — stores priorities; tracks time-allocation progress and interval-goal expiry.
- **Priority Engine** — ranks candidate activities from goal state, deadlines, history, and calendar availability.
- **Scheduling Engine** — converts the ranked candidates into calendar blocks over a rolling ~7-day horizon, without overwriting existing events.

Goals come in two flavours for the MVP: *time allocation* (e.g. fitness, 8h/week) and *interval* (e.g. call Joe, every 30 days).

## Stack

- **Backend** — FastAPI + SQLAlchemy (async), Poetry-managed, Alembic migrations.
- **Frontend** — Vue 3 + Vite + Pinia.
- **Auth** — Google Identity Services, JWT.
- **Integrations** — Google Calendar, Todoist.

## Status

Early MVP. The goal of this stage is to validate three behavioural questions before broader work:

1. Will users accept a system that actively decides what they should do next?
2. Can users express their priorities clearly enough to be scheduled?
3. Will users keep the feedback loop alive by reporting what they did?

If any of these don't hold, the concept changes.

## Getting started

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, project conventions, and common gotchas.
