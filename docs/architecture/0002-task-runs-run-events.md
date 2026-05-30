# ADR 0002: task_runs and run_events for first-class run history

## Status

Proposed

## Context

The current task runtime model is intentionally small but has no durable run history.

Current runtime shape:

1. `src/api/routes/tasks.py` exposes `POST /api/tasks/start/{task_id}` and
   `POST /api/tasks/stop/{task_id}`.
2. `src/services/process_service.py` starts `spider_v2.py --task-name ...`, keeps
   in-memory maps keyed by task id (`processes`, `log_paths`, `log_handles`,
   `task_names`, `exit_watchers`), and invokes lifecycle hooks on start/stop.
3. `src/app.py` lifecycle hooks update `tasks.is_running` and broadcast the
   `task_status_changed` websocket event. On application startup, all stale
   `tasks.is_running` values are reset to false.
4. The dashboard and task list payloads read `tasks.is_running` directly via
   `TaskService` and `serialize_task` / dashboard summary builders.
5. `src/failure_guard.py` persists circuit-breaker state separately in
   `logs/task-failure-guard.json` and only answers whether a start should be
   skipped; it is not a task-run ledger.

This means the UI can answer "is this task running now?" but cannot answer
"when did it start, why did it stop, which process/log belonged to it, which
failure guard decision blocked it, or what happened across restarts?".

This ADR is design-only. It does not authorize database schema changes, data
migration, repository code changes, route changes, or UI changes. Any schema
change described below requires a separate approval before implementation.

## Decision

Introduce first-class run history with two append-friendly tables in a separate,
approved migration:

- `task_runs`: one row per attempted task run.
- `run_events`: ordered event stream for a run.

Keep `tasks.is_running` as a compatibility projection during the migration. New
code should eventually derive running state from the latest non-terminal
`task_runs` row, but existing API and UI semantics should remain stable until the
projection is retired in a later ADR or migration.

## Proposed schema

The schema below is the target design for a future migration, not a change made
by this ADR.

### `task_runs`

One row represents a single start attempt for one task.

Suggested columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `task_id INTEGER NOT NULL`
- `task_name TEXT NOT NULL`
- `status TEXT NOT NULL`
  - allowed values: `starting`, `running`, `stopping`, `succeeded`, `failed`,
    `stopped`, `skipped`, `lost`
- `trigger TEXT NOT NULL`
  - examples: `manual`, `schedule`, `startup-recovery`, `api`, `unknown`
- `pid INTEGER`
- `log_path TEXT`
- `started_at TEXT NOT NULL`
- `last_event_at TEXT NOT NULL`
- `ended_at TEXT`
- `exit_code INTEGER`
- `failure_reason TEXT`
- `skip_reason TEXT`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

Notes:

- Keep `task_name` as a denormalized snapshot so history remains readable if a
  task is renamed or deleted.
- `status='skipped'` records failure-guard or validation skips that never spawned
  a child process.
- `status='lost'` records process state that was active before app restart but no
  longer has an attached child process.
- `failure_reason` is for terminal errors or child-exit interpretation.
- `skip_reason` is for pre-start skips such as failure guard decisions.

### `run_events`

One row represents an ordered lifecycle event or notable decision for a run.

Suggested columns:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `run_id INTEGER NOT NULL`
- `task_id INTEGER NOT NULL`
- `event_type TEXT NOT NULL`
- `occurred_at TEXT NOT NULL`
- `message TEXT`
- `payload_json TEXT NOT NULL DEFAULT '{}'`

Suggested event types:

- `start_requested`
- `failure_guard_checked`
- `failure_guard_skipped`
- `process_spawned`
- `status_projected_running`
- `stop_requested`
- `terminate_sent`
- `kill_sent`
- `process_exited`
- `status_projected_stopped`
- `startup_reconciled_lost`
- `log_cleanup`

Notes:

- Store compact JSON only. Do not store secrets, full cookies, raw browser state,
  full stdout logs, or raw result payloads in `payload_json`.
- Keep long output in existing log files; reference with `task_runs.log_path`.

## Proposed indexes

The future migration should include indexes that match expected reads:

- `idx_task_runs_task_started ON task_runs(task_id, started_at DESC)`
  - task detail history and latest run lookup.
- `idx_task_runs_status_started ON task_runs(status, started_at DESC)`
  - current running/stopping scans and operator views.
- `idx_task_runs_task_status_started ON task_runs(task_id, status, started_at DESC)`
  - latest active run per task.
- `idx_task_runs_log_path ON task_runs(log_path)`
  - log-to-run lookup where useful.
- `idx_run_events_run_time ON run_events(run_id, occurred_at ASC, id ASC)`
  - timeline rendering.
- `idx_run_events_task_time ON run_events(task_id, occurred_at DESC)`
  - recent task activity.
- `idx_run_events_type_time ON run_events(event_type, occurred_at DESC)`
  - diagnostics by event type, especially failure-guard and lost-run events.

No foreign-key cascade should be introduced until task deletion semantics are
explicitly decided. If foreign keys are used later, prefer preserving historical
runs for deleted tasks by keeping denormalized `task_name` and avoiding automatic
cascade delete.

## Lifecycle model

### Manual or scheduled start

1. API or scheduler emits `start_requested`.
2. A `task_runs` row is inserted with `status='starting'`, `trigger`, `task_id`,
   `task_name`, and timestamps.
3. `FailureGuard.should_skip_start()` is checked and logged as
   `failure_guard_checked`.
4. If the guard skips execution, update the run to `status='skipped'`, set
   `skip_reason`, emit `failure_guard_skipped`, and do not create a process.
5. If process spawn fails, update the run to `status='failed'`, set
   `failure_reason`, emit a failure event, and keep `tasks.is_running=false`.
6. If spawn succeeds, update the run to `status='running'`, set `pid` and
   `log_path`, emit `process_spawned`, and project `tasks.is_running=true`.

### Stop request

1. API emits `stop_requested` for the active run.
2. Update the active run to `status='stopping'`.
3. Emit `terminate_sent` when SIGTERM / `process.terminate()` is sent.
4. If the process does not exit before `STOP_TIMEOUT_SECONDS`, emit `kill_sent`.
5. When the watcher observes process exit, update the run to `status='stopped'`
   for user stop, `succeeded` for a clean natural exit, or `failed` for non-zero
   exit / interpreted scraper failure once that interpretation exists.
6. Emit `process_exited` with `exit_code`, then project `tasks.is_running=false`.

### Natural process exit

`ProcessService._watch_process_exit()` should own terminalization for spawned
processes:

1. Observe `returncode`.
2. Update the active run terminal status.
3. Emit `process_exited`.
4. Clean runtime maps.
5. Invoke existing stop hook so current websocket and `tasks.is_running`
   behavior remains unchanged.

### Startup reconciliation

On application startup, current code resets every stale `tasks.is_running` to
false. With first-class runs, startup should also:

1. Find runs with non-terminal statuses (`starting`, `running`, `stopping`).
2. Mark them `lost` with `ended_at` set to startup time because the previous
   child process handle is gone.
3. Emit `startup_reconciled_lost` for each run.
4. Preserve the existing compatibility projection by resetting
   `tasks.is_running=false`.

## Migration from `tasks.is_running` and ProcessService maps

Migration should be strangler-style:

1. Add repositories for `task_runs` and `run_events` while leaving
   `TaskService`, `ProcessService`, and current task payloads compatible.
2. Add a small run-history service that `ProcessService` can call at lifecycle
   boundaries. Avoid making `ProcessService` own raw SQL.
3. Continue to write `tasks.is_running` through the existing lifecycle hooks in
   `src/app.py`.
4. Store `pid` and `log_path` in `task_runs`, but keep the in-memory process maps
   as the source of process control while the process is alive.
5. Replace reads gradually:
   - Task list keeps `is_running` from the existing task payload at first.
   - Dashboard may add optional latest-run fields after API compatibility is
     established.
   - Later, `is_running` can become a derived projection from active runs.
6. Only after UI, API, and scheduler behavior are verified should a later change
   consider removing or deprecating direct writes to `tasks.is_running`.

`ProcessService.reindex_after_delete()` is a warning sign that runtime maps are
keyed by mutable task ids. The run-history design should not add new mutable-map
state; durable rows should keep their original `task_id` and `task_name`
snapshot. A future task deletion design should decide whether task ids remain
stable forever or whether task reindexing is retired.

## API impact

Initial API compatibility should be no-op for existing clients:

- `GET /api/tasks` continues returning existing task fields, including
  `is_running` and `next_run_at`.
- `POST /api/tasks/start/{task_id}` and `POST /api/tasks/stop/{task_id}` keep
  their current response shape.
- websocket `task_status_changed` remains unchanged.

Additive future endpoints can be introduced after the schema is approved:

- `GET /api/tasks/{task_id}/runs?limit=...` returns recent `task_runs` summaries.
- `GET /api/task-runs/{run_id}` returns one run plus ordered `run_events`.
- `GET /api/task-runs/active` returns active runs for operational views.

Any new response fields should be optional until the Web UI consumes them.

## UI and dashboard impact

Initial UI should keep current behavior:

- Task cards, task search, logs task selector, and dashboard summary continue to
  use `is_running`.
- Start remains optimistic in `web-ui/src/composables/useTasks.ts` and is corrected
  by websocket/refetch.
- Stop still tracks local `stoppingTaskIds`.

Additive future UI can show:

- Latest run started/ended time.
- Last terminal status (`succeeded`, `failed`, `stopped`, `skipped`, `lost`).
- A run-history drawer or tab per task.
- Failure-guard skip reason and pause-until details if explicitly exposed.
- Link from a run to its existing log file view via `log_path`.

Dashboard recent activity can later consume `run_events` instead of synthesizing
only current task state and result activity.

## Failure guard impact

The current failure guard remains the circuit-breaker authority and keeps its
existing JSON state file unless a separate design moves it into SQLite.

Run history should record guard decisions as events:

- `failure_guard_checked` with compact payload such as threshold and consecutive
  failure count.
- `failure_guard_skipped` with skip reason and paused-until timestamp.

Do not duplicate the full failure-guard JSON state into `run_events`.

## Retention

Recommended default retention:

- Keep terminal `task_runs` and their `run_events` for 30 days by default.
- Keep at least the latest 100 terminal runs per task, even if older than 30 days,
  to preserve low-frequency task history.
- Keep active/non-terminal runs until they are terminalized or reconciled as
  `lost`.
- Keep `skipped` runs for the same retention window because they explain why a
  schedule did not spawn work.
- Never delete the only run that references an existing log file if the UI still
  links to that log and the log-retention policy has not removed the file.

Retention should be implemented as an explicit cleanup service, not hidden inside
normal read paths. It should be separately configurable and covered by tests.

## Rollback and no-op plan

Safe rollback path for the future implementation:

1. Stop writing new run-history rows via a feature flag or by disabling the
   run-history service.
2. Keep `tasks.is_running` lifecycle hooks active, preserving current API/UI
   behavior.
3. Leave `task_runs` and `run_events` tables in place; they are append-only
   operational history and should not block app startup if unused.
4. If a migration must be reverted in a development database, drop only the new
   run-history tables and indexes after backing up the SQLite file. Production
   drops require separate operator approval.

No-op behavior if the approved migration has not run:

- The application should continue exactly as it does today.
- Run-history reads should return empty history or 404 for run-specific endpoints.
- Start/stop should not fail solely because run-history writes are unavailable;
  at most they should log a non-fatal warning after explicit implementation.

## Consequences

Positive:

- Operators can inspect durable task-run timelines across restarts.
- Failure guard skips become visible without changing guard authority.
- Dashboard and logs can link activity to a concrete run.
- The migration can be incremental because `tasks.is_running` remains a
  compatibility projection.

Costs and risks:

- Additional SQLite writes at task lifecycle boundaries.
- More retention and cleanup responsibility.
- Need careful payload filtering to avoid storing secrets or large logs.
- Active-run reconstruction after restart is still best-effort because the child
  process handle is not recoverable from SQLite alone.

## Explicit approval gate

This ADR is documentation only. It intentionally does not modify schema or code.
Creating `task_runs`, creating `run_events`, adding indexes, migrating existing
state, changing task start/stop semantics, or changing API/UI payloads requires a
separate approved implementation task and database schema approval before any
write is executed.
