<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSettings } from '@/composables/useSettings'
import type { NotificationSettingsUpdate, NotificationTestResponse } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'
import { getPromptContent, listPrompts, updatePrompt } from '@/api/prompts'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import RotationSettingsPanel from '@/components/settings/RotationSettingsPanel.vue'

const {
  notificationSettings,
  aiSettings,
  rotationSettings,
  systemStatus,
  isLoading,
  isSaving,
  isReady,
  error,
  refreshStatus,
  saveNotificationSettings,
  testNotification,
  saveAiSettings,
  saveRotationSettings,
  testAiConnection
} = useSettings()

const activeTab = ref('ai')
const route = useRoute()
const validTabs = new Set(['notifications', 'ai', 'rotation', 'status', 'prompts'])

const promptFiles = ref<string[]>([])
const selectedPrompt = ref<string | null>(null)
const promptContent = ref('')
const isPromptLoading = ref(false)
const isPromptSaving = ref(false)
const promptError = ref<string | null>(null)

function notifySuccess(title: string, description?: string) {
  toast({ title, description })
}

function notifyError(title: string, description?: string) {
  toast({ title, description, variant: 'destructive' })
}

async function handleSaveNotifications(payload: NotificationSettingsUpdate) {
  try {
    await saveNotificationSettings(payload)
    notifySuccess('通知设置已保存')
  } catch (e) {
    notifyError('通知设置保存失败', (e as Error).message)
  }
}

async function handleTestNotification(payload: {
  channel?: string
  settings: NotificationSettingsUpdate
}): Promise<NotificationTestResponse> {
  try {
    const result = await testNotification(payload)
    return result
  } catch (e) {
    notifyError('通知测试失败', (e as Error).message)
    throw e
  }
}

async function handleSaveAi() {
  try {
    await saveAiSettings()
    notifySuccess('AI 设置已保存')
  } catch (e) {
    notifyError('AI 设置保存失败', (e as Error).message)
  }
}

async function handleSaveRotation() {
  try {
    await saveRotationSettings()
    notifySuccess('轮换设置已保存')
  } catch (e) {
    notifyError('轮换设置保存失败', (e as Error).message)
  }
}

async function handleTestAi() {
  try {
    const res = await testAiConnection()
    notifySuccess('AI 连接测试完成', res.message)
  } catch (e) {
    notifyError('AI 连接测试失败', (e as Error).message)
  }
}

async function fetchPrompts() {
  isPromptLoading.value = true
  promptError.value = null
  try {
    const files = await listPrompts()
    promptFiles.value = files

    if (selectedPrompt.value && files.includes(selectedPrompt.value)) {
      return
    }

    const lastSelected = localStorage.getItem('lastSelectedPrompt')
    if (lastSelected && files.includes(lastSelected)) {
      selectedPrompt.value = lastSelected
      return
    }

    selectedPrompt.value = files[0] || null
  } catch (e) {
    promptError.value = (e as Error).message || '加载 Prompt 列表失败'
  } finally {
    isPromptLoading.value = false
  }
}

async function handleSavePrompt() {
  if (!selectedPrompt.value) {
    notifyError('请选择 Prompt 文件')
    return
  }
  isPromptSaving.value = true
  try {
    const res = await updatePrompt(selectedPrompt.value, promptContent.value)
    notifySuccess('Prompt 保存成功', res.message)
  } catch (e) {
    notifyError('Prompt 保存失败', (e as Error).message)
  } finally {
    isPromptSaving.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'prompts') {
    fetchPrompts()
  }
})

watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && validTabs.has(tab)) {
      activeTab.value = tab
    }
  },
  { immediate: true }
)

watch(selectedPrompt, async (value) => {
  if (!value) {
    promptContent.value = ''
    return
  }
  localStorage.setItem('lastSelectedPrompt', value)
  isPromptLoading.value = true
  promptError.value = null
  try {
    const data = await getPromptContent(value)
    promptContent.value = data.content
  } catch (e) {
    promptError.value = (e as Error).message || '加载 Prompt 内容失败'
  } finally {
    isPromptLoading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">系统设置</h1>
    
    <div v-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4">
      {{ error.message }}
    </div>

    <Tabs v-model="activeTab" class="w-full">
      <TabsList class="mb-4">
        <TabsTrigger value="ai">AI 模型</TabsTrigger>
        <TabsTrigger value="rotation">IP 轮换</TabsTrigger>
        <TabsTrigger value="notifications">通知推送</TabsTrigger>
        <TabsTrigger value="status">系统状态</TabsTrigger>
        <TabsTrigger value="prompts">Prompt 管理</TabsTrigger>
      </TabsList>

      <!-- AI Tab -->
      <TabsContent value="ai">
        <Card>
          <CardHeader>
            <CardTitle>AI 模型设置</CardTitle>
            <CardDescription>配置用于商品分析的大语言模型。</CardDescription>
          </CardHeader>
          <CardContent v-if="isReady" class="space-y-4">
            <div class="grid gap-2">
              <Label>API Base URL</Label>
              <Input v-model="aiSettings.OPENAI_BASE_URL" placeholder="https://api.openai.com/v1" />
            </div>
            <div class="grid gap-2">
              <Label>API Key</Label>
              <Input
                v-model="aiSettings.OPENAI_API_KEY"
                type="password"
                placeholder="留空表示不修改"
              />
              <p class="text-xs text-gray-500">
                {{ systemStatus?.env_file.openai_api_key_set ? '已配置' : '未配置' }}，为安全起见不回显。
              </p>
            </div>
            <div class="grid gap-2">
              <Label>模型名称</Label>
              <Input v-model="aiSettings.OPENAI_MODEL_NAME" placeholder="gpt-3.5-turbo" />
            </div>
            <div class="grid gap-2">
              <Label>代理地址 (可选)</Label>
              <Input v-model="aiSettings.PROXY_URL" placeholder="http://127.0.0.1:7890" />
            </div>
          </CardContent>
          <CardContent v-else class="py-8 text-sm text-gray-500">
            正在加载 AI 配置...
          </CardContent>
          <CardFooter v-if="isReady" class="flex gap-2">
            <Button variant="outline" @click="handleTestAi" :disabled="isSaving">测试连接</Button>
            <Button @click="handleSaveAi" :disabled="isSaving">保存 AI 设置</Button>
          </CardFooter>
        </Card>
      </TabsContent>

      <!-- Rotation Tab -->
      <TabsContent value="rotation">
        <RotationSettingsPanel
          :settings="rotationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          @save="handleSaveRotation"
        />
      </TabsContent>

      <!-- Notifications Tab -->
      <TabsContent value="notifications">
        <NotificationSettingsPanel
          :settings="notificationSettings"
          :is-ready="isReady"
          :is-saving="isSaving"
          :save-settings="handleSaveNotifications"
          :test-settings="handleTestNotification"
        />
      </TabsContent>

      <!-- Status Tab -->
      <TabsContent value="status">
        <Card>
          <CardHeader>
            <CardTitle>系统运行状态</CardTitle>
            <div class="flex justify-end">
                <Button variant="outline" size="sm" @click="refreshStatus" :disabled="isLoading">刷新状态</Button>
            </div>
          </CardHeader>
          <CardContent>
            <div v-if="systemStatus" class="space-y-6">
              <!-- Scraper Process Status -->
              <div class="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 class="font-medium">爬虫进程</h3>
                  <p class="text-sm text-gray-500">当前是否有任务正在执行抓取</p>
                </div>
                <span :class="systemStatus.scraper_running ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-gray-500 bg-gray-100 px-3 py-1 rounded-full'">
                  {{ systemStatus.scraper_running ? '运行中' : '空闲' }}
                </span>
              </div>

              <!-- Env Config Status -->
              <div>
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="font-medium">环境变量配置</h3>
                        <p class="text-sm text-gray-500">检查 .env 配置文件中的关键项</p>
                    </div>
                    <span :class="systemStatus.env_file.exists ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-red-600 font-bold bg-red-50 px-3 py-1 rounded-full'">
                        {{ systemStatus.env_file.exists ? '已加载' : '缺失' }}
                    </span>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="p-3 border rounded-lg" :class="systemStatus.env_file.openai_api_key_set ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'">
                        <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">OpenAI API Key</span>
                            <span class="text-xs font-bold" :class="systemStatus.env_file.openai_api_key_set ? 'text-green-700' : 'text-yellow-700'">
                                {{ systemStatus.env_file.openai_api_key_set ? '已配置' : '未配置' }}
                            </span>
                        </div>
                    </div>
                    
                    <div class="p-3 border rounded-lg" :class="systemStatus.configured_notification_channels?.length ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'">
                         <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">通知渠道</span>
                             <span class="text-xs font-bold" :class="systemStatus.configured_notification_channels?.length ? 'text-green-700' : 'text-gray-500'">
                                {{ systemStatus.configured_notification_channels?.length ? '已配置' : '未配置' }}
                            </span>
                        </div>
                         <div class="text-xs text-gray-500 mt-1">
                            {{ systemStatus.configured_notification_channels?.join(', ') || '无' }}
                        </div>
                    </div>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 text-gray-500">
                正在获取系统状态...
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- Prompt Tab -->
      <TabsContent value="prompts">
        <Card>
          <CardHeader>
            <CardTitle>Prompt 管理</CardTitle>
            <CardDescription>在线编辑 prompts 目录下的 Prompt 文件。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div v-if="promptError" class="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded">
              {{ promptError }}
            </div>

            <div class="grid gap-2">
              <Label>选择 Prompt 文件</Label>
              <Select
                :model-value="selectedPrompt || undefined"
                @update:model-value="(value) => selectedPrompt = value as string"
              >
                <SelectTrigger>
                  <SelectValue placeholder="请选择一个 Prompt 文件..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="file in promptFiles" :key="file" :value="file">
                    {{ file }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <p v-if="!promptFiles.length && !isPromptLoading" class="text-sm text-gray-500">
                没有找到 Prompt 文件。
              </p>
            </div>

            <div class="grid gap-2">
              <Label>Prompt 内容</Label>
              <Textarea
                v-model="promptContent"
                class="min-h-[240px]"
                :disabled="!selectedPrompt || isPromptLoading"
                placeholder="请选择一个 Prompt 文件进行编辑..."
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button :disabled="isPromptSaving || !selectedPrompt" @click="handleSavePrompt">
              {{ isPromptSaving ? '保存中...' : '保存更改' }}
            </Button>
          </CardFooter>
        </Card>
      </TabsContent>
    </Tabs>
  </div>
</template>
