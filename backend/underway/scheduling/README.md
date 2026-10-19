# underway.scheduling

A deterministic weekly scheduler for a Todoist priority queue. It turns open tasks, existing calendar events and a time log into a list of calendar blocks tagged `pqm`.

[Phase 5](../../../docs/plans/06-phase5-schedule.md) plans an LLM schedule generator. This package is a deterministic alternative and a first step: the same task and calendar inputs, placed by a pure priority queue with no model call.

## Core rule
**A scheduled task is assumed done.** A non-recurring task gets at most one block across the whole horizon. There are never any fallback or "if still open" blocks. Recurring tasks get one block per occurrence that falls in the horizon. A test fails if any task is booked twice.

## Configuration
Personal settings (areas and their targets, project IDs, holidays, scheduling windows, per-task hints, skip labels and timezone) live in `config.local.json` in this folder, which is gitignored. Copy `config.example.json` to get started. Lookup order: `--config PATH`, then `$PQM_CONFIG`, then `config.local.json`, then `config.example.json`.

## Layout
- `core.py`: the pure scheduler (no I/O)
- `config.py`: the `SchedulerConfig` dataclass, parsed from a dict
- `adapters.py`: pure translation of Todoist and calendar payloads and time-log CSV text
- `cli.py`: a thin file-reading CLI

Stdlib only.

## Inputs
- `--tasks tasks.json`: open Todoist tasks. Titles carry a `[NN]` score, plus labels, `dueDate`, `recurring` and `projectId`.
- `--events events.json`: calendar events. Anything that isn't a `pqm` block counts as busy.
- `--timelog timelog.csv`: time log rows (`Entry ID, Date, Minutes, Task, Notes, Area > path`), used for the 4-week area balance.
- `--start YYYY-MM-DD --days N [--now ISO] [--cooking dates] [--keep-today]`

The caller fetches these from its connectors. Nothing here does network I/O.

## Scheduling
Tasks are placed highest effective score first (`[NN]` plus a boost for areas below their 4-week target), each into the earliest suitable slot inside the configured windows, on or before its due date where possible. Daily caps on booked minutes come from the config.

## Run
    cd backend && python -m underway.scheduling.cli --tasks tasks.json --events events.json --timelog timelog.csv --start 2030-03-04 --days 7

This prints the planned blocks as JSON.

## Tests
    cd backend && poetry run pytest tests/scheduling

The tests use the synthetic data in `tests/scheduling/fixtures/` and never read `config.local.json`.
