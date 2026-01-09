# Repository Guidelines

## Project Structure & Module Organization
- Backend lives in `src/` (FastAPI app entry at `src/app.py`, routes in `src/api/routes/`, services in `src/services/`, domain models in `src/domain/`, infrastructure in `src/infrastructure/`).
- Frontend lives in `web-ui/` (Vue 3 + Vite; views in `web-ui/src/views/`, components in `web-ui/src/components/`).
- Tests are in `tests/` and follow `test_*.py` naming.
- Runtime data and assets: `prompts/` (AI templates), `jsonl/` (results), `logs/`, `images/`, `dist/` (built frontend), plus `config.json` and `.env` at repo root.

## Build, Test, and Development Commands
- Backend dev: `python -m src.app` or `uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload`.
- Run spider tasks: `python spider_v2.py` (examples: `--task-name "MacBook Air M1"`, `--debug-limit 3`, `--config custom_config.json`).
- Frontend dev: `cd web-ui && npm install && npm run dev`.
- Frontend build: `cd web-ui && npm run build` (copies `dist/` to root in `start.sh`).
- Docker: `docker compose up --build -d` (see `docker-compose*.yaml`).
- One-shot local start: `bash start.sh` (builds frontend, installs deps, starts backend).

## Coding Style & Naming Conventions
- Python tests: files `tests/test_*.py` or `tests/*/test_*.py`, functions `test_*`, tests are sync-only and do not require pytest-asyncio.
- Keep modules small and layered (API → services → domain → infrastructure). Avoid cross-layer shortcuts.
- Use descriptive, task-focused names for spider jobs and config keys in `config.json`.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio`.
- Run all tests: `pytest`.
- Coverage: `pytest --cov=src` or `coverage run -m pytest`.
- Target specific tests: `pytest tests/test_utils.py::test_safe_get`.

## Commit & Pull Request Guidelines
- Commit style follows a Conventional Commits-like pattern (examples in history: `feat(...)`, `fix(...)`, `refactor(...)`, `chore(...)`, `docs(...)`).
- PRs should describe scope, list affected modules, and include screenshots for UI changes (see `web-ui/`).
- Link related issues when applicable and note any config or migration steps.

## Security & Configuration Tips
- Copy `.env` from `.env.example` and set required keys (e.g., `OPENAI_API_KEY`).
- Do not commit real credentials or cookies (`state.json`).
- Playwright requires a local browser; Docker installs Chromium automatically.
