<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTasks } from '@/composables/useTasks'
import type { Task, TaskUpdate } from '@/types/task.d.ts'
import { parseTaskFormDefaults } from '@/lib/taskFormQuery'
import { formatNextRunAbsolute } from '@/lib/taskSchedule'
import TaskCreateDialog from '@/components/tasks/TaskCreateDialog.vue'
import TasksTable from '@/components/tasks/TasksTable.vue'
import TaskForm from '@/components/tasks/TaskForm.vue'
import { listAccounts, type AccountItem } from '@/api/accounts'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
const { t } = useI18n()
const SKIP_CIRCUIT_CONFIRM_KEY = 'goofish_skip_circuit_confirm'

const {
  tasks,
  isLoading,
  error,
  fetchTasks,
  removeTask,
  updateTask,
  startTask,
  unpauseTask,
  stopTask,
  stoppingTaskIds,
  unpausingTaskIds,
} = useTasks()
const route = useRoute()

// State for dialogs
const isEditDialogOpen = ref(false)
const isCriteriaDialogOpen = ref(false)
const isEditSubmitting = ref(false)
const selectedTask = ref<Task | null>(null)
const criteriaTask = ref<Task | null>(null)
const criteriaDescription = ref('')
const isCriteriaSubmitting = ref(false)
const isDeleteDialogOpen = ref(false)
const taskToDeleteId = ref<number | null>(null)
const isCircuitDialogOpen = ref(false)
const taskToForceStartId = ref<number | null>(null)
const skipCircuitConfirmNextTime = ref(false)
const isForceStarting = ref(false)
const accountOptions = ref<AccountItem[]>([])

const taskToDelete = computed(() => {
  if (taskToDeleteId.value === null) return null
  return tasks.value.find((task) => task.id === taskToDeleteId.value) || null
})
const taskToForceStart = computed(() => {
  if (taskToForceStartId.value === null) return null
  return tasks.value.find((task) => task.id === taskToForceStartId.value) || null
})
const editDefaults = computed(() => parseTaskFormDefaults(route.query))

function handleDeleteTask(taskId: number) {
  taskToDeleteId.value = taskId
  isDeleteDialogOpen.value = true
}

async function handleConfirmDeleteTask() {
  if (!taskToDelete.value) {
    toast({ title: t('tasks.toasts.notFound'), variant: 'destructive' })
    isDeleteDialogOpen.value = false
    return
  }
  try {
    await removeTask(taskToDelete.value.id)
    toast({ title: t('tasks.toasts.deleted') })
  } catch (e) {
    toast({
      title: t('tasks.toasts.deleteFailed'),
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

watch(
  () => [route.query.edit, tasks.value],
  () => {
    const editTaskId = typeof route.query.edit === 'string' ? Number(route.query.edit) : NaN
    if (!Number.isFinite(editTaskId)) return
    const match = tasks.value.find((task) => task.id === editTaskId)
    if (!match) return
    selectedTask.value = match
    isEditDialogOpen.value = true
  },
  { immediate: true }
)

async function handleUpdateTask(data: TaskUpdate) {
  if (!selectedTask.value) return
  isEditSubmitting.value = true
  try {
    await updateTask(selectedTask.value.id, data)
    isEditDialogOpen.value = false
  }
  catch (e) {
    toast({
      title: t('tasks.toasts.updateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
  finally {
    isEditSubmitting.value = false
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
      title: t('tasks.toasts.descriptionRequired'),
      description: t('tasks.criteria.descriptionRequired'),
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
      title: t('tasks.toasts.regenerateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isCriteriaSubmitting.value = false
  }
}

function shouldSkipCircuitConfirm(): boolean {
  try {
    return localStorage.getItem(SKIP_CIRCUIT_CONFIRM_KEY) === '1'
  } catch {
    return false
  }
}

function formatCircuitRecoverTime(task: Task | null): string {
  const pausedUntil = task?.failure_guard?.paused_until
  if (!pausedUntil) return t('tasks.circuit.unknownTime')
  return formatNextRunAbsolute(pausedUntil)
}

async function executeStartTask(taskId: number, forceUnpause = false) {
  try {
    await startTask(taskId, forceUnpause)
  } catch (e) {
    if (!forceUnpause && (e as { status?: number })?.status === 409) {
      await fetchTasks({ silent: true })
      const refreshedTask = tasks.value.find((item) => item.id === taskId)
      if (refreshedTask) {
        if (shouldSkipCircuitConfirm()) {
          try {
            await startTask(taskId, true)
          } catch (retryError) {
            toast({
              title: t('tasks.toasts.startFailed'),
              description: (retryError as Error).message,
              variant: 'destructive',
            })
          }
          return
        }
        taskToForceStartId.value = taskId
        skipCircuitConfirmNextTime.value = false
        isCircuitDialogOpen.value = true
        return
      }
    }
    toast({
      title: t('tasks.toasts.startFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleStartTask(taskId: number) {
  const task = tasks.value.find((item) => item.id === taskId)
  if (task?.failure_guard?.paused) {
    if (shouldSkipCircuitConfirm()) {
      await executeStartTask(taskId, true)
      return
    }
    taskToForceStartId.value = taskId
    skipCircuitConfirmNextTime.value = false
    isCircuitDialogOpen.value = true
    return
  }
  await executeStartTask(taskId, false)
}

async function handleConfirmForceStart() {
  const target = taskToForceStart.value
  if (!target) {
    isCircuitDialogOpen.value = false
    return
  }
  if (skipCircuitConfirmNextTime.value) {
    try {
      localStorage.setItem(SKIP_CIRCUIT_CONFIRM_KEY, '1')
    } catch {
      // ignore storage failure
    }
  }
  isForceStarting.value = true
  try {
    await startTask(target.id, true)
    isCircuitDialogOpen.value = false
    taskToForceStartId.value = null
  } catch (e) {
    toast({
      title: t('tasks.toasts.startFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isForceStarting.value = false
  }
}

async function handleUnpauseTask(taskId: number) {
  try {
    await unpauseTask(taskId)
    toast({ title: t('tasks.toasts.unpaused') })
  } catch (e) {
    toast({
      title: t('tasks.toasts.unpauseFailed'),
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
      title: t('tasks.toasts.stopFailed'),
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
      title: t('tasks.toasts.toggleFailed'),
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
      title: t('tasks.toasts.loadAccountsFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

onMounted(fetchAccountOptions)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-800">
        {{ t('tasks.title') }}
      </h1>
      <TaskCreateDialog :account-options="accountOptions" @created="fetchTasks" />
    </div>

    <!-- Edit Task Dialog -->
    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.editDialog.title', { task: selectedTask?.task_name || "" }) }}</DialogTitle>
        </DialogHeader>
        <TaskForm
          v-if="selectedTask"
          mode="edit"
          :initial-data="selectedTask"
          :account-options="accountOptions"
          :default-values="editDefaults"
          @submit="(data) => handleUpdateTask(data as TaskUpdate)"
        />
        <DialogFooter>
          <Button type="submit" form="task-form" :disabled="isEditSubmitting">
            {{ isEditSubmitting ? t('common.saving') : t('tasks.editDialog.save') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Refresh Criteria Dialog -->
    <Dialog v-model:open="isCriteriaDialogOpen">
      <DialogContent class="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.criteria.title') }}</DialogTitle>
          <DialogDescription>
            {{ t('tasks.criteria.description') }}
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-3">
          <label class="text-sm font-medium text-gray-700">{{ t('tasks.form.description') }}</label>
          <Textarea
            v-model="criteriaDescription"
            class="min-h-[140px]"
            :placeholder="t('tasks.form.descriptionPlaceholder')"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isCriteriaDialogOpen = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="isCriteriaSubmitting" @click="handleRefreshCriteria">
            {{ isCriteriaSubmitting ? t('tasks.criteria.generating') : t('tasks.criteria.action') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <div v-if="error" class="app-alert-error mb-4" role="alert">
      <strong class="font-bold">{{ t('common.error') }}</strong>
      <span class="block sm:inline">{{ error.message }}</span>
    </div>

    <TasksTable
      :tasks="tasks"
      :is-loading="isLoading"
      :stopping-ids="stoppingTaskIds"
      :unpausing-ids="unpausingTaskIds"
      @delete-task="handleDeleteTask"
      @edit-task="handleEditTask"
      @run-task="handleStartTask"
      @unpause-task="handleUnpauseTask"
      @stop-task="handleStopTask"
      @refresh-criteria="handleOpenCriteriaDialog"
      @toggle-enabled="handleToggleEnabled"
    />

    <Dialog v-model:open="isCircuitDialogOpen">
      <DialogContent class="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.circuit.confirmTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('tasks.circuit.confirmDescription') }}
          </DialogDescription>
        </DialogHeader>

        <div v-if="taskToForceStart" class="space-y-3 rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-sm">
          <div class="flex items-center justify-between gap-3">
            <span class="text-slate-500">{{ t('tasks.circuit.taskNameLabel') }}</span>
            <span class="font-bold text-slate-900">{{ taskToForceStart.task_name }}</span>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-slate-500">{{ t('tasks.circuit.consecutiveFailuresLabel') }}</span>
            <span class="font-bold text-rose-700">
              {{ taskToForceStart.failure_guard?.consecutive_failures || 0 }} / {{ taskToForceStart.failure_guard?.threshold || 3 }}
            </span>
          </div>
          <div class="space-y-1">
            <span class="text-slate-500">{{ t('tasks.circuit.failureReasonLabel') }}</span>
            <p class="rounded-lg bg-white/80 px-3 py-2 text-xs font-medium text-amber-950 break-words">
              {{ taskToForceStart.failure_guard?.reason || t('tasks.circuit.unknownReason') }}
            </p>
          </div>
          <div class="flex items-center justify-between gap-3">
            <span class="text-slate-500">{{ t('tasks.circuit.autoRecoverTimeLabel') }}</span>
            <span class="font-semibold text-amber-900">{{ formatCircuitRecoverTime(taskToForceStart) }}</span>
          </div>
        </div>

        <label
          for="skip-circuit-confirm-checkbox"
          class="flex cursor-pointer items-start gap-2.5 rounded-lg border border-slate-200/80 bg-slate-50/70 p-3 text-sm text-slate-700"
        >
          <Checkbox
            id="skip-circuit-confirm-checkbox"
            class="mt-0.5"
            :model-value="skipCircuitConfirmNextTime"
            @update:model-value="(val: boolean | 'indeterminate') => { skipCircuitConfirmNextTime = val === true }"
          />
          <span class="leading-snug">{{ t('tasks.circuit.dontAskAgain') }}</span>
        </label>

        <DialogFooter>
          <Button variant="outline" :disabled="isForceStarting" @click="isCircuitDialogOpen = false">
            {{ t('common.cancel') }}
          </Button>
          <Button :disabled="isForceStarting" @click="handleConfirmForceStart">
            {{ t('tasks.circuit.confirmAndStart') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('tasks.deleteDialog.title') }}</DialogTitle>
          <DialogDescription>
            {{ taskToDelete ? t('tasks.deleteDialog.descriptionWithTask', { task: taskToDelete.task_name }) : t('tasks.deleteDialog.descriptionFallback') }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button variant="destructive" @click="handleConfirmDeleteTask">{{ t('tasks.deleteDialog.confirm') }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
