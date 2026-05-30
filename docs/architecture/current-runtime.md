# Current runtime

`xianyu-tools / 闲鱼工具箱` currently preserves the ai-goofish-monitor runtime
architecture.

## Flow

1. `src/app.py` creates the FastAPI application and wires API routes.
2. Task start requests flow through `src/services/process_service.py`.
3. `ProcessService` launches `spider_v2.py --task-name ...` as a task process.
4. `spider_v2.py` loads task configuration and calls
   `src.scraper.scrape_xianyu(task_config, debug_limit)`.
5. `src/scraper.py` drives Playwright browser/session setup, Xianyu search,
   pagination, item detail collection, seller profile collection, filtering,
   AI or keyword analysis, result persistence, and notification.
6. Search pagination helpers live in `src/services/search_pagination.py`.
7. AI analysis is split across `src/ai_handler.py`,
   `src/services/item_analysis_dispatcher.py`, and related compatibility code.
8. Results are stored through SQLite-backed services and legacy-compatible JSONL
   paths.
9. Notification delivery uses `src/services/notification_service.py` and
   clients under `src/infrastructure/external/notification_clients/`.

## Storage

- SQLite is the primary store for tasks, results, and price history.
- Legacy `config.json`, `jsonl/`, and `price_history/` data are still imported
  for compatibility.
- `state/`, `prompts/`, `logs/`, and `images/` remain filesystem-backed runtime
  directories.

## Hotspots

- `src/scraper.py`: browser/session setup, task normalization, scraping loop,
  data extraction, analysis dispatch, storage, and notifications are still in
  one module.
- Configuration is split across environment, task dictionaries, repository
  models, and runtime-only normalization.
- AI request and response handling has compatibility layers in multiple modules.
- `web-ui/src/components/tasks/TaskForm.vue` owns form state, validation,
  scheduling, account strategy, AI mode, keyword mode, region selection, and
  notification targets.
