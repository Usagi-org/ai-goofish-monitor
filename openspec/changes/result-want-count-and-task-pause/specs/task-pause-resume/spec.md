## ADDED Requirements

### Requirement: 用户可以暂停启用的定时任务
系统必须允许用户暂停已启用但未运行的定时任务，暂停后任务不会自动执行。

#### Scenario: 成功暂停定时任务
- **WHEN** 用户点击暂停按钮且任务处于 enabled=true 且 is_running=false 状态
- **THEN** 系统将 is_paused 设置为 true，从调度器移除对应 Job，返回成功消息

#### Scenario: 暂停正在运行的任务
- **WHEN** 用户尝试暂停 is_running=true 的任务
- **THEN** 系统返回错误提示"请先停止正在运行的任务"

#### Scenario: 暂停已禁用的任务
- **WHEN** 用户尝试暂停 enabled=false 的任务
- **THEN** 系统返回错误提示"任务已禁用，无需暂停"

### Requirement: 用户可以恢复已暂停的定时任务
系统必须允许用户恢复已暂停的定时任务，恢复后任务按照原有 cron 表达式执行。

#### Scenario: 成功恢复定时任务
- **WHEN** 用户点击恢复按钮且任务处于 is_paused=true 状态
- **THEN** 系统将 is_paused 设置为 false，重新添加调度器 Job，返回成功消息

#### Scenario: 恢复未暂停的任务
- **WHEN** 用户尝试恢复 is_paused=false 的任务
- **THEN** 系统返回错误提示"任务未处于暂停状态"

### Requirement: 暂停的任务在系统重启后保持暂停状态
系统重启时，已暂停的任务不应自动恢复执行。

#### Scenario: 系统重启后暂停状态保持
- **WHEN** 系统重启并加载定时任务
- **THEN** is_paused=true 的任务不被添加到调度器，保持暂停状态
