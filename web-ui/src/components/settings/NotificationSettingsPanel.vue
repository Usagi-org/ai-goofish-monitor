<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { BellRing, Radio, ShieldCheck, Send, TestTube2, Trash2, Webhook } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { NotificationSettings, NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'

type ChannelKey = 'ntfy' | 'bark' | 'gotify' | 'wecom' | 'telegram' | 'webhook'

const props = defineProps<{
  settings: NotificationSettings
  isReady: boolean
  isSaving: boolean
  saveSettings: (payload: NotificationSettingsUpdate) => Promise<void>
  testSettings: (payload: { channel?: string; settings: NotificationSettingsUpdate }) => Promise<NotificationTestResponse>
}>()

const initialValues = reactive<NotificationSettingsUpdate>({})
const form = reactive<NotificationSettingsUpdate>({})
const secretConfigured = reactive<Record<string, boolean>>({})
const clearedFields = reactive<Record<string, boolean>>({})
const testResults = reactive<Record<string, { success: boolean; message: string; label: string }>>({})
const testingChannel = ref<string | null>(null)
const mutableInitialValues = initialValues as Record<string, string | boolean | null | undefined>
const mutableForm = form as Record<string, string | boolean | null | undefined>
const mutableClearedFields = clearedFields as Record<string, boolean>

const secretFields = ['BARK_URL', 'GOTIFY_TOKEN', 'WX_BOT_URL', 'TELEGRAM_BOT_TOKEN', 'WEBHOOK_URL', 'WEBHOOK_HEADERS'] as const
const channelFields: Record<ChannelKey, (keyof NotificationSettingsUpdate)[]> = {
  ntfy: ['NTFY_TOPIC_URL'],
  bark: ['BARK_URL'],
  gotify: ['GOTIFY_URL', 'GOTIFY_TOKEN'],
  wecom: ['WX_BOT_URL'],
  telegram: ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL'],
  webhook: ['WEBHOOK_URL', 'WEBHOOK_METHOD', 'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_HEADERS', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY'],
}

function syncFromSettings(settings: NotificationSettings) {
  initialValues.NTFY_TOPIC_URL = settings.NTFY_TOPIC_URL ?? ''
  initialValues.GOTIFY_URL = settings.GOTIFY_URL ?? ''
  initialValues.TELEGRAM_CHAT_ID = settings.TELEGRAM_CHAT_ID ?? ''
  initialValues.TELEGRAM_API_BASE_URL = settings.TELEGRAM_API_BASE_URL ?? 'https://api.telegram.org'
  initialValues.WEBHOOK_METHOD = settings.WEBHOOK_METHOD ?? 'POST'
  initialValues.WEBHOOK_CONTENT_TYPE = settings.WEBHOOK_CONTENT_TYPE ?? 'JSON'
  initialValues.WEBHOOK_QUERY_PARAMETERS = settings.WEBHOOK_QUERY_PARAMETERS ?? ''
  initialValues.WEBHOOK_BODY = settings.WEBHOOK_BODY ?? ''
  initialValues.PCURL_TO_MOBILE = settings.PCURL_TO_MOBILE ?? true

  Object.assign(form, initialValues, {
    BARK_URL: '',
    GOTIFY_TOKEN: '',
    WX_BOT_URL: '',
    TELEGRAM_BOT_TOKEN: '',
    WEBHOOK_URL: '',
    WEBHOOK_HEADERS: '',
  })

  secretConfigured.BARK_URL = !!settings.BARK_URL_SET
  secretConfigured.GOTIFY_TOKEN = !!settings.GOTIFY_TOKEN_SET
  secretConfigured.WX_BOT_URL = !!settings.WX_BOT_URL_SET
  secretConfigured.TELEGRAM_BOT_TOKEN = !!settings.TELEGRAM_BOT_TOKEN_SET
  secretConfigured.WEBHOOK_URL = !!settings.WEBHOOK_URL_SET
  secretConfigured.WEBHOOK_HEADERS = !!settings.WEBHOOK_HEADERS_SET

  for (const field of Object.keys(clearedFields)) {
    clearedFields[field] = false
  }
}

watch(() => props.settings, syncFromSettings, { immediate: true, deep: true })

const activeChannels = computed(() => props.settings.CONFIGURED_CHANNELS ?? [])
const summaryText = computed(() => activeChannels.value.length ? activeChannels.value.join(' / ') : '尚未配置可用通知渠道')

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
  const payload: NotificationSettingsUpdate = {}
  const mutablePayload = payload as Record<string, string | boolean | null | undefined>
  const textFields: (keyof NotificationSettingsUpdate)[] = [
    'NTFY_TOPIC_URL', 'GOTIFY_URL', 'TELEGRAM_CHAT_ID', 'TELEGRAM_API_BASE_URL', 'WEBHOOK_METHOD',
    'WEBHOOK_CONTENT_TYPE', 'WEBHOOK_QUERY_PARAMETERS', 'WEBHOOK_BODY',
  ]

  for (const field of textFields) {
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
    if (mutableClearedFields[field as string]) {
      mutablePayload[field as string] = null
      continue
    }
    const value = String(mutableForm[field as string] ?? '').trim()
    if (value) {
      mutablePayload[field as string] = value
    }
  }

  if (form.PCURL_TO_MOBILE !== initialValues.PCURL_TO_MOBILE) {
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
    const response = await props.testSettings({ channel, settings: buildPayload() })
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
</script>

<template>
  <div class="space-y-4">
    <Card class="overflow-hidden border-slate-200 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.12),_transparent_35%),linear-gradient(135deg,_#ffffff,_#f8fafc)]">
      <CardHeader>
        <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div class="space-y-2">
            <div class="flex items-center gap-2 text-slate-800">
              <BellRing class="h-5 w-5 text-sky-600" />
              <CardTitle>通知推送设置</CardTitle>
            </div>
            <CardDescription>按渠道单独配置、测试和清空。敏感字段不会回显，留空表示保留现有值。</CardDescription>
          </div>
          <div class="flex flex-wrap gap-2">
            <Badge variant="outline" class="border-sky-200 bg-sky-50 text-sky-700">已启用：{{ summaryText }}</Badge>
            <Badge variant="outline" class="border-slate-200 bg-white text-slate-600">支持变量：title / content / price / reason / desktop_link / mobile_link</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <div class="rounded-2xl border border-slate-200 bg-white/80 p-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-slate-900">全局行为</p>
              <p class="text-sm text-slate-500">统一控制所有渠道中的商品链接展示方式。</p>
            </div>
            <div class="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
              <Switch id="pcurl" :model-value="!!form.PCURL_TO_MOBILE" @update:model-value="(value) => form.PCURL_TO_MOBILE = !!value" />
              <Label for="pcurl" class="text-sm text-slate-700">优先附带手机端链接</Label>
            </div>
          </div>
        </div>
        <div class="rounded-2xl border border-slate-200 bg-slate-900 p-4 text-slate-100">
          <div class="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck class="h-4 w-4 text-emerald-300" />
            配置说明
          </div>
          <p class="mt-2 text-sm leading-6 text-slate-300">Webhook 的 Query / Body 支持 JSON 模板，测试按钮会直接调用后端真实发送逻辑，能提前发现 token、URL、JSON 格式问题。</p>
        </div>
      </CardContent>
    </Card>

    <div v-if="!isReady" class="rounded-2xl border border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-500">
      正在加载通知配置...
    </div>

    <div v-else class="grid gap-4">
      <Card class="border-l-4 border-l-sky-500">
        <CardHeader><CardTitle class="flex items-center gap-2"><Radio class="h-4 w-4 text-sky-600" /> Ntfy</CardTitle><CardDescription>适合轻量推送，URL 非敏感，可直接回显和修改。</CardDescription></CardHeader>
        <CardContent><Label>Ntfy Topic URL</Label><Input :model-value="form.NTFY_TOPIC_URL ?? ''" placeholder="https://ntfy.sh/topic" @update:model-value="(value) => updateField('NTFY_TOPIC_URL', String(value))" /></CardContent>
        <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('ntfy') ? 'default' : 'outline'">{{ isChannelConfigured('ntfy') ? '已启用' : '未启用' }}</Badge><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('ntfy')"><TestTube2 class="h-4 w-4" />测试此渠道</Button></CardFooter>
      </Card>

      <div class="grid gap-4 xl:grid-cols-2">
        <Card class="border-l-4 border-l-amber-500">
          <CardHeader><CardTitle>Bark</CardTitle><CardDescription>URL 含设备 key，已改为不回显模式。</CardDescription></CardHeader>
          <CardContent class="space-y-2"><Label>Bark URL</Label><Input :model-value="form.BARK_URL ?? ''" placeholder="已配置则留空保留，输入新值覆盖" @update:model-value="(value) => updateSecretField('BARK_URL', String(value))" /><p class="text-xs text-slate-500">{{ secretConfigured.BARK_URL ? '已配置敏感值，当前页面不回显。' : '尚未配置。' }}</p></CardContent>
          <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('bark') ? 'default' : 'outline'">{{ isChannelConfigured('bark') ? '已启用' : '未启用' }}</Badge><div class="flex gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('bark')"><Trash2 class="h-4 w-4" />清空</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('bark')"><TestTube2 class="h-4 w-4" />测试</Button></div></CardFooter>
        </Card>

        <Card class="border-l-4 border-l-violet-500">
          <CardHeader><CardTitle>Gotify</CardTitle><CardDescription>URL 与 Token 必须成对配置。</CardDescription></CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Gotify URL</Label><Input :model-value="form.GOTIFY_URL ?? ''" placeholder="https://gotify.example.com" @update:model-value="(value) => updateField('GOTIFY_URL', String(value))" /></div>
            <div class="grid gap-2"><Label>Gotify Token</Label><Input type="password" :model-value="form.GOTIFY_TOKEN ?? ''" placeholder="已配置则留空保留" @update:model-value="(value) => updateSecretField('GOTIFY_TOKEN', String(value))" /></div>
          </CardContent>
          <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('gotify') ? 'default' : 'outline'">{{ isChannelConfigured('gotify') ? '已启用' : '未启用' }}</Badge><div class="flex gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('gotify')"><Trash2 class="h-4 w-4" />清空</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('gotify')"><TestTube2 class="h-4 w-4" />测试</Button></div></CardFooter>
        </Card>
      </div>

      <div class="grid gap-4 xl:grid-cols-2">
        <Card class="border-l-4 border-l-emerald-500">
          <CardHeader><CardTitle>企业微信机器人</CardTitle><CardDescription>Bot URL 含 key，不回显，仅支持更新或清空。</CardDescription></CardHeader>
          <CardContent class="space-y-2"><Label>企业微信 Bot URL</Label><Input :model-value="form.WX_BOT_URL ?? ''" placeholder="已配置则留空保留，输入新值覆盖" @update:model-value="(value) => updateSecretField('WX_BOT_URL', String(value))" /><p class="text-xs text-slate-500">{{ secretConfigured.WX_BOT_URL ? '已保存机器人地址。' : '尚未配置。' }}</p></CardContent>
          <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('wecom') ? 'default' : 'outline'">{{ isChannelConfigured('wecom') ? '已启用' : '未启用' }}</Badge><div class="flex gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('wecom')"><Trash2 class="h-4 w-4" />清空</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('wecom')"><TestTube2 class="h-4 w-4" />测试</Button></div></CardFooter>
        </Card>

        <Card class="border-l-4 border-l-cyan-500">
          <CardHeader><CardTitle>Telegram</CardTitle><CardDescription>Bot Token 属于敏感字段，Chat ID 与反代地址可直接查看和修改。</CardDescription></CardHeader>
          <CardContent class="grid gap-4 md:grid-cols-3">
            <div class="grid gap-2"><Label>Bot Token</Label><Input type="password" :model-value="form.TELEGRAM_BOT_TOKEN ?? ''" placeholder="已配置则留空保留" @update:model-value="(value) => updateSecretField('TELEGRAM_BOT_TOKEN', String(value))" /></div>
            <div class="grid gap-2"><Label>Chat ID</Label><Input :model-value="form.TELEGRAM_CHAT_ID ?? ''" placeholder="例如：123456789" @update:model-value="(value) => updateField('TELEGRAM_CHAT_ID', String(value))" /></div>
            <div class="grid gap-2"><Label>API / 反代地址</Label><Input :model-value="form.TELEGRAM_API_BASE_URL ?? ''" placeholder="https://api.telegram.org" @update:model-value="(value) => updateField('TELEGRAM_API_BASE_URL', String(value))" /></div>
          </CardContent>
          <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('telegram') ? 'default' : 'outline'">{{ isChannelConfigured('telegram') ? '已启用' : '未启用' }}</Badge><div class="flex gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('telegram')"><Trash2 class="h-4 w-4" />清空</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('telegram')"><TestTube2 class="h-4 w-4" />测试</Button></div></CardFooter>
        </Card>
      </div>

      <Card class="border-l-4 border-l-rose-500">
        <CardHeader><CardTitle class="flex items-center gap-2"><Webhook class="h-4 w-4 text-rose-500" /> 通用 Webhook</CardTitle><CardDescription>支持 JSON 模板变量；URL 和 Headers 作为敏感字段不回显。</CardDescription></CardHeader>
        <CardContent class="grid gap-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Webhook URL</Label><Input :model-value="form.WEBHOOK_URL ?? ''" placeholder="已配置则留空保留，输入新值覆盖" @update:model-value="(value) => updateSecretField('WEBHOOK_URL', String(value))" /></div>
            <div class="grid gap-2"><Label>Webhook Headers (JSON)</Label><Textarea :model-value="form.WEBHOOK_HEADERS ?? ''" placeholder='已配置则留空保留，例如：{"Authorization":"Bearer token"}' @update:model-value="(value) => updateSecretField('WEBHOOK_HEADERS', String(value))" /></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Webhook 方法</Label><Select :model-value="form.WEBHOOK_METHOD || 'POST'" @update:model-value="(value) => updateField('WEBHOOK_METHOD', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="POST">POST</SelectItem><SelectItem value="GET">GET</SelectItem></SelectContent></Select></div>
            <div class="grid gap-2"><Label>Webhook 内容类型</Label><Select :model-value="form.WEBHOOK_CONTENT_TYPE || 'JSON'" @update:model-value="(value) => updateField('WEBHOOK_CONTENT_TYPE', String(value))"><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="JSON">JSON</SelectItem><SelectItem value="FORM">FORM</SelectItem></SelectContent></Select></div>
          </div>
          <div class="grid gap-4 md:grid-cols-2">
            <div class="grid gap-2"><Label>Webhook Query 参数 (JSON)</Label><Textarea :model-value="form.WEBHOOK_QUERY_PARAMETERS ?? ''" placeholder='例如：{"task":"{{title}}"}' @update:model-value="(value) => updateField('WEBHOOK_QUERY_PARAMETERS', String(value))" /></div>
            <div class="grid gap-2"><Label>Webhook Body (JSON 模板)</Label><Textarea :model-value="form.WEBHOOK_BODY ?? ''" placeholder='例如：{"message":"{{content}}","price":"{{price}}"}' @update:model-value="(value) => updateField('WEBHOOK_BODY', String(value))" /></div>
          </div>
          <div v-pre class="rounded-2xl border border-dashed border-rose-200 bg-rose-50/70 px-4 py-3 text-sm text-rose-700">变量说明：{{title}} 是通知标题，{{content}} 是完整正文，另外支持 {{price}}、{{reason}}、{{desktop_link}}、{{mobile_link}}。</div>
        </CardContent>
        <CardFooter class="justify-between"><Badge :variant="isChannelConfigured('webhook') ? 'default' : 'outline'">{{ isChannelConfigured('webhook') ? '已启用' : '未启用' }}</Badge><div class="flex gap-2"><Button variant="ghost" size="sm" :disabled="props.isSaving" @click="clearChannel('webhook')"><Trash2 class="h-4 w-4" />清空</Button><Button variant="outline" size="sm" :disabled="props.isSaving" @click="handleTest('webhook')"><TestTube2 class="h-4 w-4" />测试</Button></div></CardFooter>
      </Card>

      <div v-for="channel in ['ntfy', 'bark', 'gotify', 'wecom', 'telegram', 'webhook']" :key="channel">
        <div v-if="testResults[channel]" class="rounded-2xl border px-4 py-3 text-sm" :class="resultClass(channel as ChannelKey)">
          {{ testResults[channel].label }}：{{ testResults[channel].message }}
        </div>
      </div>
    </div>

    <div class="sticky bottom-0 z-10 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-2 text-sm text-slate-600"><Send class="h-4 w-4 text-slate-400" />保存会只提交改动字段；清空操作会显式删除对应渠道配置。</div>
      <div class="flex flex-col gap-2 sm:flex-row">
        <Button variant="outline" :disabled="props.isSaving" @click="handleTest()"><TestTube2 class="h-4 w-4" />{{ testingChannel === 'all' ? '测试中...' : '测试全部已启用渠道' }}</Button>
        <Button :disabled="props.isSaving" @click="handleSave"><Send class="h-4 w-4" />保存通知设置</Button>
      </div>
    </div>
  </div>
</template>
