# ADR 0001: xianyu-tools fork identity and refactor path

## Status

Accepted

## Context

This repository is a fork of `chqchshj/ai-goofish-monitor` with local work for
WeCom app notification and task-level notification targets. The current runtime
shape is still FastAPI, Vue, SQLite, and a subprocess scraper runner.

The largest refactor targets are `src/scraper.py` and
`web-ui/src/components/tasks/TaskForm.vue`. Both files carry several
responsibilities, but they also sit on hot user-facing paths.

## Decision

The visible project identity is `xianyu-tools / 闲鱼工具箱`.

Python package paths remain under `src.*` for now. The public CLI
`spider_v2.py` and `src.scraper.scrape_xianyu(task_config, debug_limit)` remain
compatible. New code may be introduced under `src/xianyu/` and `src/pipeline/`
as extracted helpers, with existing code routed through those helpers
incrementally.

## Consequences

- Deployment compatibility is preserved by leaving the image default unchanged.
- Import compatibility is preserved by deferring Python package renames.
- Future refactors should be small, behavior-compatible extractions rather than
  rewrites of the scraper or task form.
