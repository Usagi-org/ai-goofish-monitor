import {
  AUTO_ACCOUNT_VALUE,
  EMPTY_CRON_VALUE,
  buildInitialTaskFormState,
  buildTaskSubmitPayload,
  fromPresetCronModelValue,
  isPresetCronValue,
  normalizeNotificationTargets,
  parseKeywordText,
  toPresetCronModelValue,
} from './taskFormPayload'

function assert(condition: unknown, message: string): void {
  if (!condition) throw new Error(message)
}

function assertJsonEqual(actual: unknown, expected: unknown, message: string): void {
  const actualJson = JSON.stringify(actual)
  const expectedJson = JSON.stringify(expected)
  if (actualJson !== expectedJson) {
    throw new Error(`${message}: expected ${expectedJson}, got ${actualJson}`)
  }
}

assertJsonEqual(parseKeywordText('  Foo\nfoo, Bar ,,bar\nBaz '), ['Foo', 'Bar', 'Baz'], 'keywords are trimmed and case-deduped')

assertJsonEqual(
  normalizeNotificationTargets([
    { channel: 'wecom_app', recipient: ' @all ', label: ' all ' },
    { channel: 'wecom_app', recipient: '@all', label: 'dupe ignored' },
    { channel: 'wecom_app', recipient: ' user_a | user_b ' },
    { channel: 'telegram', recipient: ' 123 ' },
    { channel: 'default', recipient: ' ignored ' },
    { channel: 'email', recipient: 'bad' },
    { channel: 'wecom', recipient: 'retired' },
  ]),
  [
    { channel: 'wecom_app', recipient: '@all', label: 'all' },
    { channel: 'wecom_app', recipient: 'user_a | user_b' },
    { channel: 'telegram', recipient: '123' },
    { channel: 'default', recipient: '' },
  ],
  'notification targets preserve WeCom app recipients and drop invalid rows',
)

assert(isPresetCronValue(''), 'empty cron is a preset value')
assert(isPresetCronValue('*/5 * * * *'), 'known cron preset is detected')
assert(!isPresetCronValue('7 8 9 * *'), 'custom cron is not detected as preset')
assert(toPresetCronModelValue('') === EMPTY_CRON_VALUE, 'empty cron maps to manual preset model value')
assert(toPresetCronModelValue('7 8 9 * *') === EMPTY_CRON_VALUE, 'custom cron maps to manual preset model value')
assert(fromPresetCronModelValue(EMPTY_CRON_VALUE) === '', 'manual preset maps back to empty cron')

const createState = buildInitialTaskFormState({
  mode: 'create',
  defaultAccount: 'state/account.json',
  defaultValues: {
    cron: '7 8 9 * *',
    keyword_rules: ['M1', 'M2'],
    notification_targets: [{ channel: 'wecom_app', recipient: 'user_a|user_b' }],
  },
})
assert(createState.accountStrategy === 'fixed', 'default account selects fixed strategy')
assert(createState.selectedAccountStateFile === 'state/account.json', 'default account becomes selected account')
assert(createState.cronMode === 'custom', 'custom default cron selects custom mode')
assert(createState.keywordRulesInput === 'M1\nM2', 'default keyword rules populate textarea input')

const fixedMissing = buildTaskSubmitPayload({
  form: {
    task_name: 't',
    keyword: 'k',
    decision_mode: 'ai',
    description: 'details',
  },
  keywordRulesInput: '',
  accountStrategy: 'fixed',
  selectedAccountStateFile: AUTO_ACCOUNT_VALUE,
})
assert(fixedMissing.error === 'fixed-account-required', 'fixed strategy requires a selected account')

const aiPayload = buildTaskSubmitPayload({
  form: {
    id: 1,
    is_running: true,
    next_run_at: 'soon',
    task_name: 't',
    keyword: 'k',
    decision_mode: 'ai',
    description: 'details',
    analyze_images: undefined,
    account_state_file: 'old',
    new_publish_option: '__none__',
    region: '广东省 / 深圳市 / 南山区',
    notification_targets: [
      { channel: 'wecom_app', recipient: ' user_a|user_b ' },
      { channel: 'wecom_app', recipient: 'user_a|user_b' },
    ],
  },
  keywordRulesInput: 'ignored',
  accountStrategy: 'rotate',
})
assert(aiPayload.payload !== undefined, 'AI payload is built')
assertJsonEqual(
  aiPayload.payload,
  {
    task_name: 't',
    keyword: 'k',
    decision_mode: 'ai',
    description: 'details',
    analyze_images: true,
    account_state_file: null,
    new_publish_option: '',
    region: '广东/深圳/南山区',
    notification_targets: [{ channel: 'wecom_app', recipient: 'user_a|user_b' }],
    account_strategy: 'rotate',
    keyword_rules: [],
  },
  'AI payload normalization preserves existing semantics',
)

const keywordPayload = buildTaskSubmitPayload({
  form: {
    task_name: 't',
    keyword: 'k',
    decision_mode: 'keyword',
    analyze_images: false,
    new_publish_option: '1h',
    notification_targets: [{ channel: 'default', recipient: 'ignored' }],
  },
  keywordRulesInput: 'foo\nFoo\nbar',
  accountStrategy: 'fixed',
  selectedAccountStateFile: 'state/account.json',
})
assertJsonEqual(
  keywordPayload.payload,
  {
    task_name: 't',
    keyword: 'k',
    decision_mode: 'keyword',
    analyze_images: false,
    new_publish_option: '1h',
    notification_targets: [{ channel: 'default', recipient: '' }],
    account_state_file: 'state/account.json',
    region: undefined,
    account_strategy: 'fixed',
    keyword_rules: ['foo', 'bar'],
    description: '',
  },
  'keyword payload keeps explicit false analyze_images and defaults description',
)
