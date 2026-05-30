<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { BellRing, Building2, ShieldCheck, Send, TestTube2, Trash2, Webhook } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { NotificationSettings, NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'

type ChannelKey = 'wecom_app' | 'telegram' | 'webhook'

const props = defineProps<{
  settings: NotificationSettings
  isReady: boolean
  isSaving: boolean
  saveSettings: (payload: NotificationSettingsUpdate) => Promise<void>
  testSettings: (payload: { channel?: string; settings: NotificationSettingsUpdate }) => Promise<NotificationTestResponse>
}>()
const { t } = useI18n()

const initialValues = reactive<NotificationSettingsUpdate>({})
const form = reactive<NotificationSettingsUpdate>({})
const secretConfigured = reactive<Record<string, boolean>>({})
const clearedFields = reactive<Record<string, boolean>>({})
const testResults = reactive<Record<string, { success: boolean; message: string; label: string }>>({})
const testingChannel = ref<string | null>(null)
const WEBHOOK_HEADERS_EXAMPLE = '{"Authorization":"Bearer token"}'
const WEBHOOK_QUERY_EXAMPLE = '{"task":"{{title}}"}'
const WEBHOOK_BODY_EXAMPLE = '{"message":"{{content}}","price":"{{price}}"}'
const WEBHOOK_TEMPLATE_VARIABLES = '{{title}}, {{content}}, {{price}}, {{reason}}, {{desktop_link}}, {{mobile_link}}'
const mutableInitialValues = initialValues as Record<string, string | boolean | null | undefined>
const mutableForm = form as Record<string, string | boolean | null | undefined>
const mutableClearedFields = clearedFields as Record<string, boolean>

const secretFields = ['WECOM_APP_SECRET', 'TELEGRAM_BOT_TOKEN', 'WEBHOOK_URL', 'WEBHOOK_HEADERS'] as const
const channelFields: Record<ChannelKey, (keyof NotificationSettingsUpdate)[]> = {
  wecom_app: ['WECOM_APP_CORPID', 'WECOM_APP_SECRET', 'WECOM_APP_AGENTID', 'WECOM_APP_TOUSER'],
  telegram: ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL'],
  webhook: ['WEBHOOK_URL', 'WEBHOOK_METHOD', 'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_HEADERS', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY'],
}

function syncFromSettings(settings: NotificationSettings) {
  initialValues.WECOM_APP_CORPID = settings.WECOM_APP_CORPID ?? ''
  initialValues.WECOM_APP_AGENTID = settings.WECOM_APP_AGENTID ?? ''
  initialValues.WECOM_APP_TOUSER = settings.WECOM_APP_TOUSER ?? ''
  initialValues.TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID ?? ''
  initialValues.TELEGRAM_API_BASE_URL = settings.TELEGRAM_API_BASE_URL ?? 'https://api.telegram.org'
  initialValues.WEBHOOK_METHOD = settings.WEBHOOK_METHOD ?? 'POST'
  initialValues.WEBHOOK_CONTENT_TYPE = settings.WEBHOOK_CONTENT_TYPE ?? 'JSON'
  initialValues.WEBHOOK_QUERY_PARAMETERS = settings.WEBHOOK_QUERY_PARAMETERS ?? ''
  initialValues.WEBHOOK_BODY = settings.WEBHOOK_BODY ?? ''
  initialValues.PCURL_TO_MOBILE = settings.PCURL_TO_MOBILE ?? true

  Object.assign(form, initialValues, {
    WECOM_APP_SECRET: '',
    TELEGRAM_BOT_TOKEN: '',
    WEBHOOK_URL: '',
    WEBHOOK_HEADERS: '',
  })

  secretConfigured.WECOM_APP_SECRET = !!settings.WECOM_APP_SECRET_SET
  secretConfigured.TELEGRAM_BOT_TOKEN = !!settings.TELEGRAM_BOT_TOKEN_SET
  secretConfigured.WEBHOOK_URL = !!settings.WEBHOOK_URL_SET
  secretConfigured.WEBHOOK_HEADERS = !!settings.WEBHOOK_HEADERS_SET

  for (const field of Object.keys(clearedFields)) {
    clearedFields[field] = false
  }
}

watch(() => props.settings, syncFromSettings, { immediate: true, deep: true })

const activeChannels = computed(() => props.settings.CONFIGURED_CHANNELS ?? [])
const advancedCompatChannels = computed(() => props.settings.ADVANCED_COMPAT_CHANNELS ?? ['webhook'])
const summaryText = computed(() => (
  activeChannels.value.length ? activeChannels.value.join(' / ') : t('notifyPanel.noActiveChannels')
))
const webhookHeadersPlaceholder = computed(() => `${t('notifyPanel.webhook.headersPlaceholder')}${WEBHOOK_HEADERS_EXAMPLE}`)
const webhookQueryPlaceholder = computed(() => `${t('notifyPanel.webhook.queryPlaceholder')}${WEBHOOK_QUERY_EXAMPLE}`)
const webhookBodyPlaceholder = computed(() => `${t('notifyPanel.webhook.bodyPlaceholder')}${WEBHOOK_BODY_EXAMPLE}`)
const webhookTemplateVariables = WEBHOOK_TEMPLATE_VARIABLES

function updateSecretField(field: keyof NotificationSettingsUpdate, value: string) {
  mutableForm[field as string] = value
  mutableClearedFields[field as string] = false
}

function updateField(field: keyof NotificationSettingsUpdate, value: string) {
  mutableForm[field as string] = value
  mutableClearedFields[field as string] = false
}

function clearChannel(channel: ChannelKey) {
  for (const field of channelFields[channel]) {
    const key = field as string
    mutableForm[key] = typeof mutableForm[key] === 'boolean' ? false : ''
    mutableClearedFields[key] = true
  }
  if (channel === 'webhook') {
    form.WEBHOOK_METHOD = 'POST'
    form.WEBHOOK_CONTENT_TYPE = 'JSON'
  }
}

function buildPayload(): NotificationSettingsUpdate {
  return buildScopedPayload()
}

function buildScopedPayload(channel?: ChannelKey): NotificationSettingsUpdate {
  const payload: NotificationSettingsUpdate = {}
  const mutablePayload = payload as Record<string, string | boolean | null | undefined>
  const includedFields = channel
    ? new Set<string>([...channelFields[channel].map((field) => field as string), 'PCURL_TO_MOBILE'])
    : null
  const textFields: (keyof NotificationSettingsUpdate)[] = [
    'WECOM_APP_CORPID', 'WECOM_APP_AGENTID', 'WECOM_APP_TOUSER',
    'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL', 'WEBHOOK_METHOD',
    'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY',
  ]

  for (const field of textFields) {
    if (includedFields && !includedFields.has(field as string)) {
      continue
    }
    if (mutableClearedFields[field as string]) {
      mutablePayload[field as string] = null
      continue
    }
    const current = String(mutableForm[field as string] ?? '').trim()
    const initial = String(mutableInitialValues[field as string] ?? '').trim()
    if (current !== initial) {
      mutablePayload[field as string] = current || null
    }
  }

  for (const field of secretFields) {
    if (includedFields && !includedFields.has(field as string)) {
      continue
    }
    if (mutableClearedFields[field as string]) {
      mutablePayload[field as string] = null
      continue
    }
    const value = String(mutableForm[field as string] ?? '').trim()
    if (value) {
      mutablePayload[field as string] = value
    }
  }

  if ((!includedFields || includedFields.has('PCURL_TO_MOBILE')) && form.PCURL_TO_MOBILE !== initialValues.PCURL_TO_MOBILE) {
    payload.PCURL_TO_MOBILE = !!form.PCURL_TO_MOBILE
  }
  return payload
}

function isChannelConfigured(channel: ChannelKey) {
  return activeChannels.value.includes(channel)
}

async function handleSave() {
  await props.saveSettings(buildPayload())
}

async function handleTest(channel?: ChannelKey) {
  testingChannel.value = channel ?? 'all'
  try {
    const response = await props.testSettings({ channel, settings: buildScopedPayload(channel) })
    Object.assign(testResults, response.results)
  } finally {
    testingChannel.value = null
  }
}

function resultClass(channel: ChannelKey) {
  return testResults[channel]?.success
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
    : 'border-red-200 bg-red-50 text-red-700'
}

function resolveChannelBadge(channel: ChannelKey) {
  return isChannelConfigured(channel) ? t('common.active') : t('common.inactive')
}
</script>

<template>
  <div class="space-y-4">
    <Card class="app-surface overflow-hidden border-none">
      <CardHeader>
        <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div class="space-y-2">
            <div class="flex items-center gap-2 text-slate-800">
              <BellRing class="h-5 w-5 text-sky-600" />
              <CardTitle>{{ t('notifyPanel.title') }}</CardTitle>
            </div>
            <CardDescription>{{ t('notifyPanel.description') }}</CardDescription>
          </div>
          <div class="flex flex-wrap gap-2">
            <Badge variant="outline" class="border-sky-200 bg-sky-50 text-sky-700">{{ t('notifyPanel.enabledChannels', { channels: summaryText }) }}</Badge>
            <Badge variant="outline" class="border-slate-200 bg-white text-slate-600">{{ t('notifyPanel.supportedVariables') }}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <div class="app-surface-subtle p-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-900">{{ t('notifyPanel.globalBehavior') }}</p>
              <p class="text-sm text-slate-500">{{ t('notifyPanel.globalBehaviorDescription') }}</p>
            </div>
            <div class="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
              <Switch id="pcurl" :model-value="!!form.PCURL_TO_MOBILE" @update:model-value="(value) => form.PCURL_TO_MOBILE = !!value" />
              <Label for="pcurl" class="text-sm text-slate-700">{{ t('notifyPanel.preferMobileLink') }}</Label>
            </div>
          </div>
        </div>
        <div class="app-surface-subtle bg-slate-900/95 p-4 text-slate-100">
          <div class="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck class="h-4 w-4 text-emerald-300" />
            {{ t('notifyPanel.configurationNotes') }}
          </div>
          <p class="mt-2 text-sm leading-6 text-slate-300">{{ t('notifyPanel.configurationNotesDescription') }}</p>
        </div>
      </CardContent>
    </Card>

    <div v-if="!isReady" class="app-surface py-10 text-center text-sm text-slate-500">
      {{ t('notifyPanel.loading') }}
    </div>

    <div v-else class="grid gap-4">
      <section class="grid gap-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-base font-semibold text-slate-900">{{ t('notifyPanel.preferredSectionTitle') }}</h3>
            <p class="text-sm text-slate-500">{{ t('notifyPanel.preferredSectionDescription') }}</p>
          </div>
          <Badge variant="outline" class="border-lime-200 bg-lime-50 text-lime-700">{{ t('notifyPanel.preferredBadge') }}</Badge>
        </div>
        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-lime-500">
          <CardHeader><CardTitle class="flex items-center gap-2"><Building2 class="h-4 w-4 text-lime-600" /> {{ t('notifyPanel.wecomApp.title') }}</CardTitle><CardDescription>{{ t('notifyPanel.wecomApp.description') }}</CardDescription></CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Corp ID</Label><Input :model-value="form.WECOM_APP_CORPID ?? ''" :placeholder="t('notifyPanel.wecomApp.corpidPlaceholder')" @update:model-value="(value) => updateField('WECOM_APP_CORPID', String(value))" /></div>
            <div class="grid gap-2"><Label>Agent ID</Label><Input :model-value="form.WECOM_APP_AGENTID ?? ''" placeholder="1000001" @update:model-value="(value) => updateField('WECOM_APP_AGENTID', String(value))" /></div>
            <div class="grid gap-2"><Label>Corp Secret</Label><Input type="password" :model-value="form.WECOM_APP_SECRET ?? ''" :placeholder="t('notifyPanel.secretKeepPlaceholder')" @update:model-value="(value) => updateSecretField('WECOM_APP_SECRET', String(value))" /><p class="text-xs text-slate-500">{{ secretConfigured.WECOM_APP_SECRET ? t('notifyPanel.wecomApp.configuredHint') : t('notifyPanel.notConfigured') }}</p></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.wecomApp.touserLabel') }}</Label><Input :model-value="form.WECOM_APP_TOUSER ?? ''" placeholder="@all" @update:model-value="(value) => updateField('WECOM_APP_TOUSER', String(value))" /></div>
          </CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('wecom_app') ? 'default' : 'outline'">{{ resolveChannelBadge('wecom_app') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('wecom_app')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('wecom_app')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>
      </section>

      <section class="grid gap-3">
        <div>
          <h3 class="text-base font-semibold text-slate-900">{{ t('notifyPanel.advancedSectionTitle') }}</h3>
          <p class="text-sm text-slate-500">{{ t('notifyPanel.advancedSectionDescription', { channels: advancedCompatChannels.join(' / ') }) }}</p>
        </div>
        <div class="grid gap-4 xl:grid-cols-2">
        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-cyan-500">
          <CardHeader><CardTitle>Telegram</CardTitle><CardDescription>{{ t('notifyPanel.telegram.description') }}</CardDescription></CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-3">
            <div class="grid gap-2"><Label>Bot Token</Label><Input type="password" :model-value="form.TELEGRAM_BOT_TOKEN ?? ''" :placeholder="t('notifyPanel.secretKeepPlaceholder')" @update:model-value="(value) => updateSecretField('TELEGRAM_BOT_TOKEN', String(value))" /></div>
            <div class="grid gap-2"><Label>Chat ID</Label><Input :model-value="form.TELEGRAM_CHAT_ID ?? ''" :placeholder="t('notifyPanel.telegram.chatIdPlaceholder')" @update:model-value="(value) => updateField('TELEGRAM_CHAT_ID', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.telegram.apiBaseUrl') }}</Label><Input :model-value="form.TELEGRAM_API_BASE_URL ?? ''" placeholder="https://api.telegram.org" @update:model-value="(value) => updateField('TELEGRAM_API_BASE_URL', String(value))" /></div>
          </CardContent>
          <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('telegram') ? 'default' : 'outline'">{{ resolveChannelBadge('telegram') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('telegram')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('telegram')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>

        <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-rose-500">
        <CardHeader><CardTitle class="flex items-center gap-2"><Webhook class="h-4 w-4 text-rose-500" /> {{ t('notifyPanel.webhook.title') }}</CardTitle><CardDescription>{{ t('notifyPanel.webhook.description') }}</CardDescription></CardHeader>
        <CardContent class="grid gap-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.urlLabel') }}</Label><Input :model-value="form.WEBHOOK_URL ?? ''" :placeholder="t('notifyPanel.secretPlaceholder')" @update:model-value="(value) => updateSecretField('WEBHOOK_URL', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.headersLabel') }}</Label><Textarea :model-value="form.WEBHOOK_HEADERS ?? ''" :placeholder="webhookHeadersPlaceholder" @update:model-value="(value) => updateSecretField('WEBHOOK_HEADERS', String(value))" /></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.methodLabel') }}</Label><Select :model-value="form.WEBHOOK_METHOD || 'POST'" @update:model-value="(value) => updateField('WEBHOOK_METHOD', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="POST">POST</SelectItem><SelectItem value="GET">GET</SelectItem></SelectContent></Select></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.contentTypeLabel') }}</Label><Select :model-value="form.WEBHOOK_CONTENT_TYPE || 'JSON'" @update:model-value="(value) => updateField('WEBHOOK_CONTENT_TYPE', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="JSON">JSON</SelectItem><SelectItem value="FORM">FORM</SelectItem></SelectContent></Select></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.queryLabel') }}</Label><Textarea :model-value="form.WEBHOOK_QUERY_PARAMETERS ?? ''" :placeholder="webhookQueryPlaceholder" @update:model-value="(value) => updateField('WEBHOOK_QUERY_PARAMETERS', String(value))" /></div>
            <div class="grid gap-2"><Label>{{ t('notifyPanel.webhook.bodyLabel') }}</Label><Textarea :model-value="form.WEBHOOK_BODY ?? ''" :placeholder="webhookBodyPlaceholder" @update:model-value="(value) => updateField('WEBHOOK_BODY', String(value))" /></div>
          </div>
          <div class="rounded-2xl border border-dashed border-rose-200 bg-rose-50/70 px-4 py-3 text-sm text-rose-700">
            <p>{{ t('notifyPanel.webhook.variablesHelp') }}</p>
            <p class="mt-2 break-all font-mono text-xs text-rose-900">{{ webhookTemplateVariables }}</p>
          </div>
        </CardContent>
        <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><Badge :variant="isChannelConfigured('webhook') ? 'default' : 'outline'">{{ resolveChannelBadge('webhook') }}</Badge><div class="flex flex-wrap gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('webhook')"><Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('webhook')"><TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}</Button></div></CardFooter>
        </Card>
        </div>
      </section>

      <div v-for="channel in ['wecom_app', 'telegram', 'webhook']" :key="channel">
        <div v-if="testResults[channel]" class="rounded-2xl border px-4 py-3 text-sm" :class="resultClass(channel as ChannelKey)">
          {{ testResults[channel].label }}：{{ testResults[channel].message }}
        </div>
      </div>
    </div>

    <div class="app-surface sticky bottom-0 z-10 flex flex-col gap-3 p-4 shadow-lg md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-2 text-sm text-slate-600"><Send class="h-4 w-4 text-slate-400" />{{ t('notifyPanel.footerHint') }}</div>
      <div class="flex flex-col gap-2 sm:flex-row">
        <Button variant="outline" :disabled="props.isSaving" @click="handleTest()"><TestTube2 class="h-4 w-4" />{{ testingChannel === 'all' ? t('common.testing') : t('notifyPanel.testAll') }}</Button>
        <Button :disabled="props.isSaving" @click="handleSave"><Send class="h-4 w-4" />{{ t('notifyPanel.save') }}</Button>
      </div>
    </div>
  </div>
</template>
