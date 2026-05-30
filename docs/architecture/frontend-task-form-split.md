# Frontend TaskForm split plan

`web-ui/src/components/tasks/TaskForm.vue` currently owns task create/edit UI,
form state, payload serialization, account strategy controls, cron presets,
keyword mode, AI mode, region selection, notification targets, and WeCom target
selection.

## Target components

- `TaskBasicFields.vue`: task name, keyword, pages, price, shipping, publish
  time, and region.
- `TaskDecisionMode.vue`: AI mode and keyword mode switching.
- `TaskKeywordRules.vue`: keyword rule editing.
- `TaskAiPrompt.vue`: AI prompt and image-analysis controls.
- `TaskScheduleFields.vue`: cron expression and presets.
- `TaskAccountStrategy.vue`: account strategy and account binding controls.
- `TaskNotificationTargets.vue`: notification target selection including
  WeCom app target picker.

## Data ownership

- `useTaskFormState` should own local editable state, defaults, and mode
  normalization.
- `taskFormPayload` should build API payloads for create and edit flows.
- Leaf components should receive focused props and emit field-level updates.

## Regression checklist

- Create task.
- Edit task.
- Account strategy and account binding.
- Cron presets and custom cron expression.
- Keyword mode and keyword rules.
- AI mode and generated criteria flow.
- Notification targets.
- WeCom picker.
