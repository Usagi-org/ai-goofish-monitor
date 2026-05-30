# xianyu-tools execution checklist

Generated from audit task `t_26e7100b` on branch `feat/wecom-app-notification`.

## Current state

- Git branch: `feat/wecom-app-notification`.
- Local branch is clean and ahead of `origin/feat/wecom-app-notification` by 2 commits:
  - `f24f4c7 refactor: initialize xianyu-tools architecture seams`
  - `197b3b8 refactor: extract xianyu filter and guard helpers`
- Runtime shape is still compatible with the original ai-goofish-monitor flow:
  FastAPI -> `ProcessService` -> `spider_v2.py` -> `src.scraper.scrape_xianyu()` -> Playwright -> AI/keyword analysis -> SQLite/result storage -> notification.
- Existing architecture notes are under `docs/architecture/` and should remain the control plane for the refactor.
- Important fork behavior is present in code and tests: WeCom app notification channel plus task-level notification targets.

## Verification baseline

The following commands pass in the current checkout:

```bash
.venv/bin/python -m compileall src spider_v2.py
.venv/bin/python -m pytest tests/unit tests/integration -q
cd web-ui && npm run build
```

Observed results:

- `compileall`: passed.
- `pytest tests/unit tests/integration -q`: `150 passed, 1 warning`.
- `npm run build`: passed with Vite production output in `dist/`.

The pytest warning is from FastAPI/Starlette TestClient using deprecated `httpx`; this is not blocking but should be tracked separately when dependencies are refreshed.

## Findings

### README and product identity

- `README.md` and `README_EN.md` already use the `xianyu-tools / 闲鱼工具箱` identity.
- Docker quick-start commands still clone `Usagi-org/ai-goofish-monitor` into `xianyu-tools`, and the compose file still defaults to the upstream GHCR image. That is acceptable for upstream-compatible deployment, but it is confusing for this fork because fork-only behavior such as `wecom_app` is not guaranteed in the upstream image.
- README notification feature list says WeChat Work is supported, but it does not explicitly distinguish group bot (`wecom`) from WeCom application (`wecom_app`) or explain task-level recipients.

### Docker and local run shape

- `docker-compose.yaml` uses container name `xianyu-tools-app`, persists the expected runtime directories, and sets `APP_DATABASE_FILE=/app/data/app.sqlite3`.
- `docker-compose.yaml` defaults to `image: ${APP_IMAGE:-ghcr.io/usagi-org/ai-goofish:latest}` and `pull_policy: always`; this can accidentally deploy upstream instead of the fork-local image.
- `docker-compose.dev.yaml` still uses container name `ai-goofish-monitor-app`, which is inconsistent with the visible project identity.
- Runtime directories and secrets are present in the working tree; implementation tasks must not touch `.env`, `state/`, production data, NAS deployment files, or secrets.

### Tests

- Unit and integration coverage is healthy for the current seams: task models, notification config, WeCom app client, task-level targets, scraper helper extraction, SQLite repositories, AI compatibility, API routes, and CLI spider behavior.
- There are live smoke tests under `tests/live/`, but they require credentials/external services and were intentionally not part of this audit baseline.
- Regression commands should stay fixed for subsequent refactor tasks: compileall, unit+integration pytest, and frontend build.

### Frontend

- Frontend build passes.
- Main hotspot remains `web-ui/src/components/tasks/TaskForm.vue` at roughly 759 lines. It still owns task form state, payload normalization, cron/account strategy, AI/keyword mode, notification targets, and WeCom recipient picker.
- The existing `docs/architecture/frontend-task-form-split.md` is the right split plan; do not rewrite the UI before preserving create/edit regressions.

### Scraper and backend hotspots

Largest current hotspots:

- `src/scraper.py` (~987 lines): still owns browser/session setup, task normalization, seller profile scraping, main scraping loop, detail capture, filtering, AI/keyword dispatch, storage, and notification.
- `src/ai_handler.py` (~483 lines): still carries compatibility notification and AI analysis responsibilities.
- `src/services/result_storage_service.py`, `src/api/routes/settings.py`, `src/services/notification_config_service.py`, and `src/domain/models/task.py` are also relatively large but covered by tests.

Low-risk helpers already extracted and tested:

- `src/xianyu/browser_session.py`
- `src/xianyu/search.py`
- `src/xianyu/detail.py`
- `src/xianyu/filters.py`
- `src/xianyu/guards.py`
- `src/pipeline/task_runtime.py`
- `src/pipeline/scan_state.py`
- `src/pipeline/records.py`

Remaining near-term scraper extraction candidates:

1. Move seller profile scraping/cache orchestration out of `src/scraper.py` while keeping Playwright selectors and timing unchanged.
2. Move analysis job construction for `ItemAnalysisJob` into a helper module, preserving `notification_targets` propagation.
3. Move item candidate normalization/detail merge into a pipeline helper, preserving `FAIL_SYS_USER_VALIDATE` and login-required behavior.
4. Move browser lifecycle orchestration only after helper-level tests cover the exact launch/context/snapshot behavior.
5. Do not introduce schema changes or notification routing changes in the same task as scraper extraction.

## Execution checklist for subsequent implementation tasks

### T2: deployment/docs consistency

Acceptance criteria:

- README and README_EN clearly state when the upstream image is sufficient and when the fork/local image is required for fork-only channels such as `wecom_app`.
- README documents task-level notification target semantics:
  - empty targets means use globally enabled channels;
  - target entries route to the selected channel/recipient;
  - `wecom_app` recipient uses `@all` or `userid1|userid2`.
- `.env.example` includes the WeCom application variables:
  - `WECOM_APP_CORPID`
  - `WECOM_APP_SECRET`
  - `WECOM_APP_AGENTID`
  - `WECOM_APP_TOUSER`
- `docker-compose.dev.yaml` uses the `xianyu-tools` visible identity.
- No secrets, `.env`, `state/`, runtime data, or NAS deployment files are modified.
- Verification passes: compileall, unit+integration pytest, frontend build.

### T3: scraper extraction - seller profile and analysis job seams

Acceptance criteria:

- Public entry points remain compatible:
  - `spider_v2.py`
  - `src.scraper.scrape_xianyu(task_config, debug_limit)`
- Seller profile scraping/cache logic is moved into a focused helper with unit tests or integration coverage.
- `ItemAnalysisJob` construction is moved into a focused helper with tests proving `notification_targets` are preserved.
- No Playwright selector, anti-bot wait, pagination, login-state, account rotation, proxy rotation, SQLite schema, or notification semantics are changed.
- Verification passes: compileall, unit+integration pytest, frontend build.

### T4: frontend TaskForm split preparation

Acceptance criteria:

- Extract only pure form-state/payload helpers first, before visual component decomposition.
- Tests or build-time checks cover create/edit payload preservation for:
  - AI mode;
  - keyword mode;
  - cron settings;
  - account strategy/account binding;
  - task-level notification targets;
  - WeCom app recipient picker values.
- `TaskForm.vue` behavior remains unchanged from the user's perspective.
- Verification passes: compileall, unit+integration pytest, frontend build.

### T5: first-class run history planning only

Acceptance criteria:

- Produce a schema/API/UI plan for `task_runs` and `run_events` without applying DB migrations yet.
- Plan covers migration from current `tasks.is_running` and process map behavior.
- Plan includes how to show last success, last failure, next run, scanned count, new item count, AI-analyzed count, recommendation count, account/proxy used, and failure reason.
- No database write or schema migration is executed without separate user approval.

## Non-goals for the next tasks

- Do not rewrite the scraper wholesale.
- Do not rename Python import packages away from `src.*` yet.
- Do not change SQLite schema during helper extraction tasks.
- Do not alter anti-bot timing, selectors, account/proxy rotation, or notification routing semantics unless the task explicitly targets that behavior.
- Do not run live Xianyu smoke tests unless credentials/login state and scope are explicitly provided.
