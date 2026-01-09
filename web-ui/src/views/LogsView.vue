<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useLogs } from '@/composables/useLogs'
import { useTasks } from '@/composables/useTasks'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/components/ui/toast'

const { tasks } = useTasks()
const { logs, isAutoRefresh, clearLogs, toggleAutoRefresh, fetchLogs, setTaskId, loadLatest, loadPrevious, isFetchingHistory, hasMoreHistory } = useLogs()
const logContainer = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const isClearDialogOpen = ref(false)
const selectedTaskId = ref('')
const isPrepending = ref(false)
const lastScrollTop = ref(0)
const lastScrollHeight = ref(0)

// Auto-scroll logic
watch(logs, async () => {
  if (isPrepending.value) {
    await nextTick()
    if (logContainer.value) {
      const delta = logContainer.value.scrollHeight - lastScrollHeight.value
      logContainer.value.scrollTop = lastScrollTop.value + delta
    }
    isPrepending.value = false
    return
  }
  if (autoScroll.value) {
    await nextTick()
    scrollToBottom()
  }
})

watch(tasks, (list) => {
  if (!list.length) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  if (selectedTaskId.value && list.some((task) => String(task.id) === selectedTaskId.value)) {
    return
  }
  const running = list.find((task) => task.is_running)
  const fallback = list[0]
  if (!fallback) {
    selectedTaskId.value = ''
    setTaskId(null)
    return
  }
  selectedTaskId.value = String(running ? running.id : fallback.id)
}, { immediate: true })

watch(selectedTaskId, (taskId) => {
  const resolvedTaskId = taskId ? Number(taskId) : null
  setTaskId(resolvedTaskId)
  if (resolvedTaskId) {
    loadLatest(50)
  }
})

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

async function handleScroll() {
  if (!logContainer.value) return
  if (!hasMoreHistory.value || isFetchingHistory.value) return
  if (logContainer.value.scrollTop > 120) return
  lastScrollTop.value = logContainer.value.scrollTop
  lastScrollHeight.value = logContainer.value.scrollHeight
  isPrepending.value = true
  await loadPrevious(50)
}

function openClearDialog() {
  isClearDialogOpen.value = true
}

async function handleClearLogs() {
  try {
    await clearLogs()
    toast({ title: '日志已清空' })
  } catch (e) {
    toast({
      title: '清空日志失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isClearDialogOpen.value = false
  }
}
</script>

<template>
  <div class="h-[calc(100vh-100px)] flex flex-col">
    <div class="flex justify-between items-center mb-4">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold text-gray-800">运行日志</h1>
        <div class="flex items-center gap-2">
          <Label class="text-sm text-gray-600">任务</Label>
          <Select v-model="selectedTaskId">
            <SelectTrigger class="w-[240px]">
              <SelectValue placeholder="请选择任务" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="task in tasks" :key="task.id" :value="String(task.id)">
                {{ task.task_name }}{{ task.is_running ? '（运行中）' : '' }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      
      <div class="flex items-center gap-4">
        <Button variant="outline" size="sm" :disabled="!selectedTaskId" @click="fetchLogs">
          刷新
        </Button>

        <div class="flex items-center space-x-2">
          <Switch id="auto-refresh" :model-value="isAutoRefresh" @update:model-value="toggleAutoRefresh" />
          <Label for="auto-refresh">自动刷新</Label>
        </div>

        <div class="flex items-center space-x-2">
          <Switch id="auto-scroll" v-model="autoScroll" />
          <Label for="auto-scroll">自动滚动</Label>
        </div>

        <Button variant="destructive" size="sm" :disabled="!selectedTaskId" @click="openClearDialog">
          清空日志
        </Button>
      </div>
    </div>

    <Card class="flex-1 overflow-hidden flex flex-col">
      <CardContent class="flex-1 p-0 relative">
        <pre
          ref="logContainer"
          @scroll="handleScroll"
          class="absolute inset-0 p-4 bg-gray-950 text-gray-100 font-mono text-sm overflow-auto whitespace-pre-wrap break-all"
        >{{ logs }}</pre>
      </CardContent>
    </Card>

    <Dialog v-model:open="isClearDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>清空任务日志</DialogTitle>
          <DialogDescription>
            此操作不可恢复，确定要清空当前任务日志吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isClearDialogOpen = false">取消</Button>
          <Button variant="destructive" @click="handleClearLogs">确认清空</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
