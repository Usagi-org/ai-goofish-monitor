<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSettings } from '@/composables/useSettings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { toast } from '@/components/ui/toast'
import { deleteLoginState, updateLoginState } from '@/api/settings'
import { getPromptContent, listPrompts, updatePrompt } from '@/api/prompts'

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
  saveAiSettings,
  saveRotationSettings,
  testAiConnection
} = useSettings()

const activeTab = ref('ai')
const route = useRoute()
const validTabs = new Set(['notifications', 'ai', 'rotation', 'status', 'prompts'])
const isLoginDialogOpen = ref(false)
const loginStateContent = ref('')
const isLoginStateSaving = ref(false)
const isLoginStateDeleting = ref(false)
const isDeleteLoginDialogOpen = ref(false)

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

async function handleSaveNotifications() {
  try {
    await saveNotificationSettings()
    notifySuccess('通知设置已保存')
  } catch (e) {
    notifyError('通知设置保存失败', (e as Error).message)
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

async function handleSaveLoginState() {
  const content = loginStateContent.value.trim()
  if (!content) {
    notifyError('缺少登录内容', '请粘贴从浏览器获取的 JSON 内容。')
    return
  }
  isLoginStateSaving.value = true
  try {
    const res = await updateLoginState(content)
    notifySuccess('登录状态更新成功', res.message)
    loginStateContent.value = ''
    isLoginDialogOpen.value = false
    await refreshStatus()
    window.dispatchEvent(new Event('login-state-changed'))
  } catch (e) {
    notifyError('登录状态更新失败', (e as Error).message)
  } finally {
    isLoginStateSaving.value = false
  }
}

async function handleDeleteLoginState() {
  isLoginStateDeleting.value = true
  try {
    const res = await deleteLoginState()
    notifySuccess('登录凭证已删除', res.message)
    await refreshStatus()
    window.dispatchEvent(new Event('login-state-changed'))
    isDeleteLoginDialogOpen.value = false
  } catch (e) {
    notifyError('删除登录凭证失败', (e as Error).message)
  } finally {
    isLoginStateDeleting.value = false
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
        <Card>
          <CardHeader>
            <CardTitle>IP 代理轮换</CardTitle>
            <CardDescription>配置代理池与轮换策略。</CardDescription>
          </CardHeader>
          <CardContent v-if="isReady" class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="font-medium">代理轮换</h3>
                <p class="text-sm text-gray-500">使用代理池进行 IP 轮换。</p>
              </div>
              <Switch v-model:checked="rotationSettings.PROXY_ROTATION_ENABLED" />
            </div>
            <div class="grid gap-2">
              <Label>轮换模式</Label>
              <Select v-model="rotationSettings.PROXY_ROTATION_MODE">
                <SelectTrigger>
                  <SelectValue placeholder="请选择轮换模式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per_task">按任务固定</SelectItem>
                  <SelectItem value="on_failure">失败后轮换</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="grid gap-2">
              <Label>代理池 (逗号分隔)</Label>
              <Textarea
                v-model="rotationSettings.PROXY_POOL"
                class="min-h-[120px]"
                placeholder="http://127.0.0.1:7890,socks5://127.0.0.1:1080"
              />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="grid gap-2">
                <Label>重试上限</Label>
                <Input v-model.number="rotationSettings.PROXY_ROTATION_RETRY_LIMIT" type="number" min="1" />
              </div>
              <div class="grid gap-2">
                <Label>黑名单 TTL (秒)</Label>
                <Input v-model.number="rotationSettings.PROXY_BLACKLIST_TTL" type="number" min="0" />
              </div>
            </div>
          </CardContent>
          <CardContent v-else class="py-8 text-sm text-gray-500">
            正在加载轮换配置...
          </CardContent>
          <CardFooter v-if="isReady" class="flex gap-2">
            <Button @click="handleSaveRotation" :disabled="isSaving">保存轮换设置</Button>
          </CardFooter>
        </Card>
      </TabsContent>

      <!-- Notifications Tab -->
      <TabsContent value="notifications">
        <Card>
          <CardHeader>
            <CardTitle>通知推送设置</CardTitle>
            <CardDescription>配置爬虫任务完成后的消息推送渠道。</CardDescription>
          </CardHeader>
          <CardContent class="space-y-4">
            <div class="grid gap-2">
              <Label>Bark URL (iOS)</Label>
              <Input v-model="notificationSettings.BARK_URL" placeholder="https://api.day.app/YOUR_KEY/" />
            </div>
            <div class="grid gap-2">
              <Label>Ntfy Topic URL</Label>
              <Input v-model="notificationSettings.NTFY_TOPIC_URL" placeholder="https://ntfy.sh/topic" />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="grid gap-2">
                <Label>Gotify URL</Label>
                <Input v-model="notificationSettings.GOTIFY_URL" placeholder="https://gotify.example.com" />
              </div>
              <div class="grid gap-2">
                <Label>Gotify Token</Label>
                <Input v-model="notificationSettings.GOTIFY_TOKEN" placeholder="Token" />
              </div>
            </div>
            <div class="grid gap-2">
              <Label>企业微信 Bot URL</Label>
              <Input v-model="notificationSettings.WX_BOT_URL" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div class="grid gap-2">
                <Label>Telegram Bot Token</Label>
                <Input v-model="notificationSettings.TELEGRAM_BOT_TOKEN" />
              </div>
              <div class="grid gap-2">
                <Label>Telegram Chat ID</Label>
                <Input v-model="notificationSettings.TELEGRAM_CHAT_ID" />
              </div>
            </div>
            <div class="border-t pt-4 space-y-4">
              <div class="grid gap-2">
                <Label>通用 Webhook URL</Label>
                <Input v-model="notificationSettings.WEBHOOK_URL" placeholder="https://your-webhook-url.com/endpoint" />
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div class="grid gap-2">
                  <Label>Webhook 方法</Label>
                  <Select
                    :model-value="notificationSettings.WEBHOOK_METHOD || 'POST'"
                    @update:model-value="(value) => notificationSettings.WEBHOOK_METHOD = value as string"
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="POST">POST</SelectItem>
                      <SelectItem value="GET">GET</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div class="grid gap-2">
                  <Label>Webhook 内容类型</Label>
                  <Select
                    :model-value="notificationSettings.WEBHOOK_CONTENT_TYPE || 'JSON'"
                    @update:model-value="(value) => notificationSettings.WEBHOOK_CONTENT_TYPE = value as string"
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="JSON">JSON</SelectItem>
                      <SelectItem value="FORM">FORM</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div class="grid gap-2">
                <Label>Webhook 请求头 (JSON)</Label>
                <Textarea v-model="notificationSettings.WEBHOOK_HEADERS" placeholder='例如: {"Authorization": "Bearer token"}' />
              </div>
              <div class="grid gap-2">
                <Label>Webhook Query 参数 (JSON)</Label>
                <Textarea v-model="notificationSettings.WEBHOOK_QUERY_PARAMETERS" placeholder='例如: {"param1": "value1"}' />
              </div>
              <div class="grid gap-2">
                <Label>Webhook Body (支持变量)</Label>
                <Textarea v-model="notificationSettings.WEBHOOK_BODY" placeholder='例如: {"message": "${content}"}' />
              </div>
            </div>
             <div class="flex items-center space-x-2 mt-2">
              <Switch id="pcurl" v-model="notificationSettings.PCURL_TO_MOBILE" />
              <Label for="pcurl">将商品链接转换为手机端链接</Label>
            </div>
          </CardContent>
          <CardFooter>
            <Button @click="handleSaveNotifications" :disabled="isSaving">保存通知设置</Button>
          </CardFooter>
        </Card>
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

              <!-- Login State Status -->
              <div class="border-b pb-4">
                <div class="flex items-center justify-between mb-2">
                    <div>
                        <h3 class="font-medium">闲鱼登录凭证</h3>
                        <p class="text-sm text-gray-500">用于访问闲鱼数据的 Cookie 文件 (xianyu_state.json)</p>
                    </div>
                    <span :class="systemStatus.login_state_file.exists ? 'text-green-600 font-bold bg-green-50 px-3 py-1 rounded-full' : 'text-red-600 font-bold bg-red-50 px-3 py-1 rounded-full'">
                        {{ systemStatus.login_state_file.exists ? '有效' : '缺失' }}
                    </span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" @click="isLoginDialogOpen = true">
                    手动更新
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    :disabled="isLoginStateDeleting || !systemStatus.login_state_file.exists"
                    @click="isDeleteLoginDialogOpen = true"
                  >
                    {{ isLoginStateDeleting ? '删除中...' : '删除凭证' }}
                  </Button>
                </div>
                
                <!-- Login Guide -->
                <div v-if="!systemStatus.login_state_file.exists" class="mt-4 bg-amber-50 border border-amber-200 rounded-md p-4 text-sm text-amber-800">
                    <h4 class="font-bold flex items-center gap-2 mb-2">
                        ⚠️ 检测到未登录，请按以下步骤操作：
                    </h4>
                    <ol class="list-decimal list-inside space-y-1 ml-1">
                        <li>在服务器/本机终端执行命令进入容器：
                            <code class="bg-black/10 px-1 rounded select-all">docker exec -it ai-goofish-monitor-app bash</code>
                        </li>
                        <li>在容器内执行登录脚本：
                            <code class="bg-black/10 px-1 rounded select-all">python login.py</code>
                        </li>
                        <li>终端会显示一个二维码，使用闲鱼APP扫码确认登录。</li>
                        <li>登录成功后，点击上方的 <span class="font-semibold">“刷新状态”</span> 按钮。</li>
                    </ol>
                </div>
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
                    
                    <div class="p-3 border rounded-lg" :class="(systemStatus.env_file.ntfy_topic_url_set || systemStatus.env_file.gotify_url_set || systemStatus.env_file.bark_url_set) ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'">
                         <div class="flex justify-between items-center">
                            <span class="font-medium text-sm">通知渠道</span>
                             <span class="text-xs font-bold" :class="(systemStatus.env_file.ntfy_topic_url_set || systemStatus.env_file.gotify_url_set || systemStatus.env_file.bark_url_set) ? 'text-green-700' : 'text-gray-500'">
                                {{ (systemStatus.env_file.ntfy_topic_url_set || systemStatus.env_file.gotify_url_set || systemStatus.env_file.bark_url_set) ? '已配置' : '未配置' }}
                            </span>
                        </div>
                         <div class="text-xs text-gray-500 mt-1">
                            {{ [
                                systemStatus.env_file.ntfy_topic_url_set ? 'Ntfy' : '',
                                systemStatus.env_file.gotify_url_set ? 'Gotify' : '',
                                systemStatus.env_file.bark_url_set ? 'Bark' : ''
                            ].filter(Boolean).join(', ') || '无' }}
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

    <!-- Login State Dialog -->
    <Dialog v-model:open="isLoginDialogOpen">
      <DialogContent class="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>手动更新登录状态 (Cookie)</DialogTitle>
          <DialogDescription>
            用于在无法运行图形化浏览器的服务器上更新闲鱼登录凭证。
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 text-sm text-gray-600">
          <div>
            <h4 class="font-medium text-gray-800 mb-2">使用 Chrome 扩展（推荐）</h4>
            <ol class="list-decimal list-inside space-y-1">
              <li>安装 <a class="text-blue-600 hover:underline" href="https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa" target="_blank" rel="noopener noreferrer">闲鱼登录状态提取扩展</a></li>
              <li>打开并登录 <a class="text-blue-600 hover:underline" href="https://www.goofish.com" target="_blank" rel="noopener noreferrer">闲鱼官网</a></li>
              <li>点击扩展图标，选择“提取登录状态”，再点击“复制到剪贴板”</li>
              <li>将内容粘贴到下方文本框并保存</li>
            </ol>
          </div>
          <div class="grid gap-2">
            <Label>粘贴 JSON 内容</Label>
            <Textarea v-model="loginStateContent" class="min-h-[160px]" placeholder="请在此处粘贴从浏览器扩展复制的 JSON 文本..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isLoginDialogOpen = false">取消</Button>
          <Button :disabled="isLoginStateSaving" @click="handleSaveLoginState">
            {{ isLoginStateSaving ? '保存中...' : '保存' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Delete Login State Dialog -->
    <Dialog v-model:open="isDeleteLoginDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>删除登录凭证</DialogTitle>
          <DialogDescription>
            删除后需要重新设置才能运行任务，确定要继续吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteLoginDialogOpen = false">取消</Button>
          <Button variant="destructive" :disabled="isLoginStateDeleting" @click="handleDeleteLoginState">
            {{ isLoginStateDeleting ? '删除中...' : '确认删除' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
