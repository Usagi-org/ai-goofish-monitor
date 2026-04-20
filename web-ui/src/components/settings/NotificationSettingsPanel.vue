<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { BellRing, Send, TestTube2, Trash2 } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import type { NotificationSettings, NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'

type ChannelKey = 'feishu'

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
const mutableForm = form as Record<string, string | boolean | null | undefined>
const mutableClearedFields = clearedFields as Record<string, boolean>

const secretFields = ['FEISHU_WEBHOOK_URL'] as const
const channelFields: Record<ChannelKey, (keyof NotificationSettingsUpdate)[]> = {
  feishu: ['FEISHU_WEBHOOK_URL'],
}

function syncFromSettings(settings: NotificationSettings) {
  initialValues.PCURL_TO_MOBILE = settings.PCURL_TO_MOBILE ?? true

  Object.assign(form, initialValues, {})

  secretConfigured.FEISHU_WEBHOOK_URL = !!settings.FEISHU_WEBHOOK_URL_SET

  for (const field of Object.keys(clearedFields)) {
    clearedFields[field] = false
  }
}

watch(() => props.settings, syncFromSettings, { immediate: true, deep: true })

const activeChannels = computed(() => props.settings.CONFIGURED_CHANNELS ?? [])
const summaryText = computed(() => (
  activeChannels.value.length ? activeChannels.value.join(' / ') : t('notifyPanel.noActiveChannels')
))

function updateSecretField(field: keyof NotificationSettingsUpdate, value: string) {
  mutableForm[field as string] = value
  mutableClearedFields[field as string] = false
}

function clearChannel(channel: ChannelKey) {
  for (const field of channelFields[channel]) {
    const key = field as string
    mutableForm[key] = ''
    mutableClearedFields[key] = true
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
          <Badge variant="outline" class="border-sky-200 bg-sky-50 text-sky-700">{{ t('notifyPanel.enabledChannels', { channels: summaryText }) }}</Badge>
        </div>
      </CardHeader>
      <CardContent class="grid gap-4">
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
      </CardContent>
    </Card>

    <div v-if="!isReady" class="app-surface py-10 text-center text-sm text-slate-500">
      {{ t('notifyPanel.loading') }}
    </div>

    <div v-else class="grid gap-4">
      <Card class="app-surface-subtle overflow-hidden border-l-4 border-l-blue-500">
        <CardHeader><CardTitle>飞书 (Feishu)</CardTitle><CardDescription>{{ t('notifyPanel.feishu.description') }}</CardDescription></CardHeader>
        <CardContent class="space-y-2">
          <Label>Webhook URL</Label>
          <Input :model-value="form.FEISHU_WEBHOOK_URL ?? ''" :placeholder="t('notifyPanel.secretPlaceholder')" @update:model-value="(value) => updateSecretField('FEISHU_WEBHOOK_URL', String(value))" />
          <p class="text-xs text-slate-500">{{ secretConfigured.FEISHU_WEBHOOK_URL ? t('notifyPanel.feishu.configuredHint') : t('notifyPanel.notConfigured') }}</p>
        </CardContent>
        <CardFooter class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Badge :variant="isChannelConfigured('feishu') ? 'default' : 'outline'">{{ resolveChannelBadge('feishu') }}</Badge>
          <div class="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('feishu')">
              <Trash2 class="h-4 w-4" />{{ t('notifyPanel.clear') }}
            </Button>
            <Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('feishu')">
              <TestTube2 class="h-4 w-4" />{{ t('notifyPanel.test') }}
            </Button>
          </div>
        </CardFooter>
      </Card>

      <div v-for="channel in ['feishu']" :key="channel">
        <div v-if="testResults[channel]" class="rounded-2xl border px-4 py-3 text-sm" :class="resultClass(channel as ChannelKey)">
          {{ testResults[channel].label }}: {{ testResults[channel].message }}
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
