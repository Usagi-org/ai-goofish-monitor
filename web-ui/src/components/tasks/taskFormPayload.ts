import type { NotificationChannel, NotificationTarget, Task, TaskGenerateRequest } from '@/types/task.d.ts'

export type FormMode = 'create' | 'edit'
export type AccountStrategy = 'auto' | 'fixed' | 'rotate'
export type CronMode = 'preset' | 'custom'
export type EmittedTaskFormData = TaskGenerateRequest | Partial<Task>
export type TaskFormDefaults = Partial<TaskGenerateRequest & Partial<Task>>

export const AUTO_ACCOUNT_VALUE = '__auto__'
export const EMPTY_CRON_VALUE = '__manual__'
export const NONE_NEW_PUBLISH_OPTION = '__none__'

export const CRON_PRESET_VALUES = [
  EMPTY_CRON_VALUE,
  '*/5 * * * *',
  '*/15 * * * *',
  '*/30 * * * *',
  '0 * * * *',
  '0 */2 * * *',
  '0 */6 * * *',
  '0 8 * * *',
  '0 12 * * *',
  '0 18 * * *',
  '0 20 * * *',
  '0 8,12,18 * * *',
  '0 9 * * 1-5',
  '0 10 * * 6,0',
] as const

export interface BuildInitialTaskFormStateOptions {
  mode: FormMode
  initialData?: Task | null
  defaultValues?: TaskFormDefaults
  defaultAccount?: string
}

export interface InitialTaskFormState {
  form: Record<string, unknown>
  keywordRulesInput: string
  cronMode: CronMode
  accountStrategy: AccountStrategy
  selectedAccountStateFile: string
}

export interface BuildTaskSubmitPayloadOptions {
  form: Record<string, unknown>
  keywordRulesInput: string
  accountStrategy?: AccountStrategy
  selectedAccountStateFile?: string
}

export interface TaskSubmitPayloadResult {
  payload?: EmittedTaskFormData
  error?: 'fixed-account-required'
}

export function parseKeywordText(text: string): string[] {
  const values = String(text || '')
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

  const seen = new Set<string>()
  const deduped: string[] = []
  for (const value of values) {
    const key = value.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(value)
  }
  return deduped
}

export function normalizeNotificationTargets(value: unknown): NotificationTarget[] {
  if (!Array.isArray(value)) return []
  const seen = new Set<string>()
  const targets: NotificationTarget[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Partial<NotificationTarget>
    const channel = String(raw.channel || '').trim() as NotificationChannel
    const recipient = channel === 'default' ? '' : String(raw.recipient || '').trim()
    const label = String(raw.label || '').trim()
    if (!channel && !recipient) continue
    if (!['telegram', 'wecom_app', 'default'].includes(channel)) continue
    if (channel !== 'default' && !recipient) continue
    const key = `${channel}:${recipient}`
    if (seen.has(key)) continue
    seen.add(key)
    targets.push({ channel, recipient, ...(label ? { label } : {}) })
  }
  return targets
}

export function isPresetCronValue(value: string | null | undefined): boolean {
  if (!value) return true
  return CRON_PRESET_VALUES.some((preset) => preset === value)
}

export function toPresetCronModelValue(value: string | null | undefined): string {
  return isPresetCronValue(value) ? (value || EMPTY_CRON_VALUE) : EMPTY_CRON_VALUE
}

export function fromPresetCronModelValue(value: string): string {
  return value === EMPTY_CRON_VALUE ? '' : value
}

export function normalizeRegion(value: unknown): unknown {
  if (typeof value !== 'string') return value
  return value
    .trim()
    .split('/')
    .map((part) => part.trim().replace(/(省|市)$/u, ''))
    .filter((part) => part.length > 0)
    .join('/')
}

export function buildInitialTaskFormState(options: BuildInitialTaskFormStateOptions): InitialTaskFormState {
  const defaultValues = options.defaultValues || {}
  const defaultAccount = options.defaultAccount || ''
  let form: Record<string, unknown>
  let keywordRulesInput = ''
  let cronVal: string | null | undefined

  if (options.mode === 'edit' && options.initialData) {
    form = {
      ...options.initialData,
      ...defaultValues,
      account_strategy:
        defaultValues.account_strategy ||
        options.initialData.account_strategy ||
        (options.initialData.account_state_file ? 'fixed' : 'auto'),
      account_state_file:
        defaultValues.account_state_file ||
        options.initialData.account_state_file ||
        AUTO_ACCOUNT_VALUE,
      analyze_images: defaultValues.analyze_images ?? options.initialData.analyze_images ?? true,
      free_shipping: defaultValues.free_shipping ?? options.initialData.free_shipping ?? true,
      new_publish_option:
        defaultValues.new_publish_option || options.initialData.new_publish_option || NONE_NEW_PUBLISH_OPTION,
      region: defaultValues.region || options.initialData.region || '',
      decision_mode: defaultValues.decision_mode || options.initialData.decision_mode || 'ai',
      notification_targets: normalizeNotificationTargets(
        defaultValues.notification_targets || options.initialData.notification_targets || [],
      ),
    }
    keywordRulesInput = (defaultValues.keyword_rules || options.initialData.keyword_rules || []).join('\n')
    cronVal = defaultValues.cron ?? options.initialData.cron ?? ''
  } else {
    form = {
      task_name: '',
      keyword: '',
      description: '',
      analyze_images: true,
      max_pages: 3,
      personal_only: true,
      min_price: undefined,
      max_price: undefined,
      cron: '',
      account_strategy: defaultAccount ? 'fixed' : 'auto',
      account_state_file: defaultAccount || AUTO_ACCOUNT_VALUE,
      free_shipping: true,
      new_publish_option: NONE_NEW_PUBLISH_OPTION,
      region: '',
      decision_mode: 'ai',
      notification_targets: [],
      ...defaultValues,
    }
    if (!form.account_strategy) {
      form.account_strategy = defaultAccount ? 'fixed' : 'auto'
    }
    if (!form.account_state_file) {
      form.account_state_file = defaultAccount || AUTO_ACCOUNT_VALUE
    }
    if (!form.new_publish_option) {
      form.new_publish_option = NONE_NEW_PUBLISH_OPTION
    }
    if (defaultValues.keyword_rules && defaultValues.keyword_rules.length > 0) {
      keywordRulesInput = defaultValues.keyword_rules.join('\n')
    }
    cronVal = defaultValues.cron ?? ''
  }

  const accountStrategy = (form.account_strategy || (defaultAccount ? 'fixed' : 'auto')) as AccountStrategy
  const selectedAccountStateFile = String(form.account_state_file || defaultAccount || AUTO_ACCOUNT_VALUE)

  return {
    form,
    keywordRulesInput,
    cronMode: isPresetCronValue(cronVal) ? 'preset' : 'custom',
    accountStrategy,
    selectedAccountStateFile,
  }
}

export function buildTaskSubmitPayload(options: BuildTaskSubmitPayloadOptions): TaskSubmitPayloadResult {
  const { id: _id, is_running: _isRunning, next_run_at: _nextRunAt, ...submitData } = options.form
  const currentAccountStrategy = options.accountStrategy || 'auto'
  if (currentAccountStrategy === 'fixed') {
    const currentAccountStateFile = options.selectedAccountStateFile || AUTO_ACCOUNT_VALUE
    if (currentAccountStateFile === AUTO_ACCOUNT_VALUE) {
      return { error: 'fixed-account-required' }
    }
    submitData.account_state_file = currentAccountStateFile
  } else {
    submitData.account_state_file = null
  }

  submitData.region = normalizeRegion(submitData.region)

  if (submitData.new_publish_option === NONE_NEW_PUBLISH_OPTION) {
    submitData.new_publish_option = ''
  }

  const decisionMode = String(submitData.decision_mode || 'ai') as 'ai' | 'keyword'
  submitData.decision_mode = decisionMode
  submitData.account_strategy = currentAccountStrategy
  submitData.analyze_images = submitData.analyze_images !== false
  submitData.keyword_rules = decisionMode === 'keyword' ? parseKeywordText(options.keywordRulesInput) : []
  submitData.notification_targets = normalizeNotificationTargets(submitData.notification_targets)
  if (decisionMode === 'keyword' && !submitData.description) {
    submitData.description = ''
  }

  return { payload: submitData as EmittedTaskFormData }
}
