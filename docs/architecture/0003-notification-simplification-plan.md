# ADR 0003: Notification channel simplification

Status: Accepted
Date: 2026-05-30
Task: `t_ac2ca2ed`

## Context

The fork previously carried upstream notification channels plus fork-local WeCom application messages and task-level routing. The final retained scope is intentionally smaller: keep the channels that are actively supported in this fork, keep the generic advanced webhook integration, and stop exposing or treating inherited legacy channels as runtime notification channels.

## Decision

Retain first-class notification support for:

- `wecom_app`
  - Env: `WECOM_APP_CORPID`, `WECOM_APP_SECRET`, `WECOM_APP_AGENTID`, optional `WECOM_APP_TOUSER`
  - Task recipients may be `@all` or `userid1|userid2`.
  - The Web UI contact picker remains backed by `/api/settings/notifications/wecom-app/departments` and `/users`.
- `telegram`
  - Env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional `TELEGRAM_API_BASE_URL`.
- Task-level `notification_targets`
  - Supported task target channels: `wecom_app`, `telegram`, and `default`.
  - Empty targets continue to mean global defaults.
  - `default` remains the sentinel that expands to globally configured channels.
- `webhook`
  - Env: `WEBHOOK_URL`, `WEBHOOK_METHOD`, `WEBHOOK_HEADERS`, `WEBHOOK_CONTENT_TYPE`, `WEBHOOK_QUERY_PARAMETERS`, `WEBHOOK_BODY`.
  - Retained as an advanced global compatibility channel only; it is not a task-level target.
- `PCURL_TO_MOBILE`
  - Still controls desktop-to-mobile Goofish URL conversion for notification messages.

Retire these channels from exposed runtime, UI, API channel metadata, tests, and docs:

- `ntfy` / `NTFY_TOPIC_URL`
- `bark` / `BARK_URL`
- `gotify` / `GOTIFY_URL`, `GOTIFY_TOKEN`
- legacy WeCom group robot `wecom` / `WX_BOT_URL`

Existing old env values are not deleted automatically. They may remain in `.env`, but runtime channel assembly, status/configured-channel reporting, channel-specific test requests, and task target validation no longer treat them as valid notification channels.

## Runtime Shape

Global default notification clients are now assembled from `wecom_app`, `telegram`, and `webhook` only. Task-level routing with explicit targets builds only `wecom_app` and `telegram` clients, with `default` expanding to the retained global defaults.

Failure-guard and task-failure notifications still use global defaults because they do not carry task-level targets. Operators should configure at least one retained global channel, preferably `wecom_app`.

## UI/API Shape

The settings UI exposes WeCom App and Telegram as normal channels, plus Webhook as advanced compatibility. It no longer renders cards or test buttons for `ntfy`, `bark`, `gotify`, or legacy `wecom`.

`GET /api/settings/notifications` returns retained notification fields and channel metadata only. `GET /api/settings/status` reports retained notification status flags only. `POST /api/settings/notifications/test` rejects retired channel names.

The task form keeps its existing field order and WeCom App picker behavior, but task-level channel options are limited to `telegram`, `wecom_app`, and `default`.

## Compatibility Notes

No database or schema migration is required for this change. Persisted task targets using retired channels are invalid under the current domain model and must be edited manually if encountered. Empty `notification_targets` remain compatible and use retained global defaults.

The old function name `send_ntfy_notification()` remains as an internal compatibility alias for the broader product-notification path; it does not imply ntfy channel support.
