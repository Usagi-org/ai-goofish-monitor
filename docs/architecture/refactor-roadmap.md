# Refactor roadmap

The refactor uses a strangler pattern: extract pure helpers and narrowly scoped
runtime modules first, then move ownership once tests cover the behavior.

## Phase 0/1 baseline

- Keep `spider_v2.py` and `src.scraper.scrape_xianyu(task_config, debug_limit)`
  compatible.
- Rename visible project identity to `xianyu-tools / 闲鱼工具箱`.
- Document the current FastAPI -> `ProcessService` -> `spider_v2.py` ->
  `src.scraper.scrape_xianyu` -> Playwright -> AI/keyword analysis ->
  SQLite/result storage -> notification flow.
- Extract browser/session helpers to `src/xianyu/browser_session.py`.
- Extract search URL construction to `src/xianyu/search.py` while reusing
  `src/services/search_pagination.py`.
- Introduce `src/pipeline/task_runtime.py` for pure task config normalization.

## Later phases

- Continue scraper extraction around browser lifecycle, item parsing, seller
  profile loading, and analysis dispatch without changing Playwright selectors
  or anti-bot timing.
- Unify task config, environment config, and AI runtime config behind explicit
  models.
- Move task run status and history into a first-class `task_runs` storage model.
- Decompose `web-ui/src/components/tasks/TaskForm.vue` into focused components
  and composables.
