<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useTasks } from '@/composables/useTasks'
import type { Task, TaskGenerateRequest, TaskUpdate } from '@/types/task.d.ts'
import TasksTable from '@/components/tasks/TasksTable.vue'
import TaskForm from '@/components/tasks/TaskForm.vue'
import { listAccounts, type AccountItem } from '@/api/accounts'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

const { tasks, isLoading, error, removeTask, createTask, updateTask, startTask, stopTask } = useTasks()

// State for dialogs
const isCreateDialogOpen = ref(false)
const isEditDialogOpen = ref(false)
const isCriteriaDialogOpen = ref(false)
const isSubmitting = ref(false)
const selectedTask = ref<Task | null>(null)
const criteriaTask = ref<Task | null>(null)
const criteriaDescription = ref('')
const isCriteriaSubmitting = ref(false)
const isDeleteDialogOpen = ref(false)
const taskToDeleteId = ref<number | null>(null)
const accountOptions = ref<AccountItem[]>([])
const defaultAccountPath = ref<string>('')
const route = useRoute()

const taskToDelete = computed(() => {
  if (taskToDeleteId.value === null) return null
  return tasks.value.find((task) => task.id === taskToDeleteId.value) || null
})

function handleDeleteTask(taskId: number) {
  taskToDeleteId.value = taskId
  isDeleteDialogOpen.value = true
}

async function handleConfirmDeleteTask() {
  if (!taskToDelete.value) {
    toast({ title: '未找到要删除的任务', variant: 'destructive' })
    isDeleteDialogOpen.value = false
    return
  }
  try {
    await removeTask(taskToDelete.value.id)
    toast({ title: '任务已删除' })
  } catch (e) {
    toast({
      title: '删除任务失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isDeleteDialogOpen.value = false
    taskToDeleteId.value = null
  }
}

function handleEditTask(task: Task) {
  selectedTask.value = task
  isEditDialogOpen.value = true
}

async function handleCreateTask(data: TaskGenerateRequest) {
  isSubmitting.value = true
  try {
    await createTask(data)
    isCreateDialogOpen.value = false
  }
  catch (e) {
    toast({
      title: '创建任务失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
  finally {
    isSubmitting.value = false
  }
}

async function handleUpdateTask(data: TaskUpdate) {
  if (!selectedTask.value) return
  isSubmitting.value = true
  try {
    await updateTask(selectedTask.value.id, data)
    isEditDialogOpen.value = false
  }
  catch (e) {
    toast({
      title: '更新任务失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
  finally {
    isSubmitting.value = false
  }
}

function handleOpenCriteriaDialog(task: Task) {
  criteriaTask.value = task
  criteriaDescription.value = task.description || ''
  isCriteriaDialogOpen.value = true
}

async function handleRefreshCriteria() {
  if (!criteriaTask.value) return
  if (!criteriaDescription.value.trim()) {
    toast({
      title: '详细需求不能为空',
      description: '请填写新的详细需求。',
      variant: 'destructive',
    })
    return
  }

  isCriteriaSubmitting.value = true
  try {
    await updateTask(criteriaTask.value.id, { description: criteriaDescription.value })
    isCriteriaDialogOpen.value = false
  } catch (e) {
    toast({
      title: '重新生成失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isCriteriaSubmitting.value = false
  }
}

async function handleStartTask(taskId: number) {
  try {
    await startTask(taskId)
  } catch (e) {
    toast({
      title: '启动任务失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleStopTask(taskId: number) {
  try {
    await stopTask(taskId)
  } catch (e) {
    toast({
      title: '停止任务失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleToggleEnabled(task: Task, enabled: boolean) {
  const previous = task.enabled
  task.enabled = enabled
  try {
    await updateTask(task.id, { enabled })
  } catch (e) {
    task.enabled = previous
    toast({
      title: '更新状态失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function fetchAccountOptions() {
  try {
    accountOptions.value = await listAccounts()
  } catch (e) {
    toast({
      title: '加载账号列表失败',
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

onMounted(fetchAccountOptions)

function resolveAccountPath(accountName: string) {
  const match = accountOptions.value.find((account) => account.name === accountName)
  return match ? match.path : ''
}

watch(
  () => [route.query.account, route.query.create, accountOptions.value],
  () => {
    const accountName = typeof route.query.account === 'string' ? route.query.account : ''
    if (accountName) {
      defaultAccountPath.value = resolveAccountPath(accountName)
    } else {
      defaultAccountPath.value = ''
    }
    if (route.query.create === '1') {
      isCreateDialogOpen.value = true
    }
  },
  { immediate: true }
)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-800">
        任务管理
      </h1>

      <!-- Create Task Dialog -->
      <Dialog v-model:open="isCreateDialogOpen">
        <DialogTrigger as-child>
          <Button>+ 创建新任务</Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>创建新监控任务 (AI驱动)</DialogTitle>
            <DialogDescription>
              请填写任务详情。AI将根据你的“详细需求”自动生成分析标准。
            </DialogDescription>
          </DialogHeader>
          <TaskForm
            mode="create"
            :account-options="accountOptions"
            :default-account="defaultAccountPath"
            @submit="(data) => handleCreateTask(data as TaskGenerateRequest)"
          />
          <DialogFooter>
            <Button type="submit" form="task-form" :disabled="isSubmitting">
              {{ isSubmitting ? '创建中...' : '创建任务' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>

    <!-- Edit Task Dialog -->
    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>编辑任务: {{ selectedTask?.task_name }}</DialogTitle>
        </DialogHeader>
        <TaskForm
          v-if="selectedTask"
          mode="edit"
          :initial-data="selectedTask"
          :account-options="accountOptions"
          @submit="(data) => handleUpdateTask(data as TaskUpdate)"
        />
        <DialogFooter>
          <Button type="submit" form="task-form" :disabled="isSubmitting">
            {{ isSubmitting ? '保存中...' : '保存更改' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Refresh Criteria Dialog -->
    <Dialog v-model:open="isCriteriaDialogOpen">
      <DialogContent class="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>重新生成 AI 标准</DialogTitle>
          <DialogDescription>
            修改详细需求后将重新生成 AI 分析标准。
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-3">
          <label class="text-sm font-medium text-gray-700">详细需求</label>
          <Textarea
            v-model="criteriaDescription"
            class="min-h-[140px]"
            placeholder="请用自然语言详细描述你的购买需求，AI将根据此描述生成分析标准..."
          />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isCriteriaDialogOpen = false">
            取消
          </Button>
          <Button :disabled="isCriteriaSubmitting" @click="handleRefreshCriteria">
            {{ isCriteriaSubmitting ? '生成中...' : '重新生成' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <div v-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
      <strong class="font-bold">出错了!</strong>
      <span class="block sm:inline">{{ error.message }}</span>
    </div>

    <TasksTable
      :tasks="tasks"
      :is-loading="isLoading"
      @delete-task="handleDeleteTask"
      @edit-task="handleEditTask"
      @run-task="handleStartTask"
      @stop-task="handleStopTask"
      @refresh-criteria="handleOpenCriteriaDialog"
      @toggle-enabled="handleToggleEnabled"
    />

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>删除任务</DialogTitle>
          <DialogDescription>
            {{ taskToDelete ? `确定删除任务「${taskToDelete.task_name}」吗？此操作不可恢复。` : '确定删除该任务吗？此操作不可恢复。' }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">取消</Button>
          <Button variant="destructive" @click="handleConfirmDeleteTask">确认删除</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
