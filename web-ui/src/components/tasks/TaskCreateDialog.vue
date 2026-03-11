<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { createTaskWithAI } from '@/api/tasks'
import { useTaskGenerationJob } from '@/composables/useTaskGenerationJob'
import type { TaskGenerateRequest } from '@/types/task.d.ts'
import { parseTaskFormDefaults } from '@/lib/taskFormQuery'
import TaskForm from '@/components/tasks/TaskForm.vue'
import TaskGenerationDialog from '@/components/tasks/TaskGenerationDialog.vue'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

const props = defineProps<{
  accountOptions?: { name: string; path: string }[]
}>()

const emit = defineEmits<{
  (event: 'created'): void
}>()

const route = useRoute()
const isFormOpen = ref(false)
const isProgressOpen = ref(false)
const isSubmitting = ref(false)
const defaultAccountPath = ref('')
const defaultValues = ref({})
const {
  activeJob,
  pollingError,
  beginPolling,
  clearJob,
} = useTaskGenerationJob()

function resolveAccountPath(accountName: string) {
  const match = (props.accountOptions || []).find((account) => account.name === accountName)
  return match ? match.path : ''
}

async function handleCreateTask(data: TaskGenerateRequest) {
  isSubmitting.value = true
  clearJob()
  try {
    const result = await createTaskWithAI(data)
    if (result.job) {
      isFormOpen.value = false
      isProgressOpen.value = true
      beginPolling(result.job)
      isSubmitting.value = false
      return
    }
    emit('created')
    toast({ title: '任务创建成功' })
    isFormOpen.value = false
  } catch (error) {
    toast({
      title: '创建任务失败',
      description: (error as Error).message,
      variant: 'destructive',
    })
  } finally {
    if (!isProgressOpen.value) {
      isSubmitting.value = false
    }
  }
}

watch(
  () => [route.query, props.accountOptions],
  () => {
    const accountName = typeof route.query.account === 'string' ? route.query.account : ''
    defaultAccountPath.value = accountName ? resolveAccountPath(accountName) : ''
    defaultValues.value = parseTaskFormDefaults(route.query)
    if (route.query.create === '1') {
      isFormOpen.value = true
    }
  },
  { immediate: true }
)

watch(
  () => activeJob.value?.status,
  (status, previousStatus) => {
    if (!status || status === previousStatus) return
    if (status === 'completed') {
      isSubmitting.value = false
      emit('created')
      toast({ title: '任务创建成功' })
      isProgressOpen.value = false
      clearJob()
      return
    }
    if (status === 'failed') {
      isSubmitting.value = false
      toast({
        title: '任务创建失败',
        description: activeJob.value?.error || activeJob.value?.message,
        variant: 'destructive',
      })
    }
  }
)

watch(pollingError, (value) => {
  if (!value) return
  isSubmitting.value = false
  toast({
    title: '任务进度获取失败',
    description: value.message,
    variant: 'destructive',
  })
})
</script>

<template>
  <Dialog v-model:open="isFormOpen">
    <DialogTrigger as-child>
      <Button>+ 创建新任务</Button>
    </DialogTrigger>
    <DialogContent class="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>创建新监控任务（AI或KeyWord）</DialogTitle>
      </DialogHeader>
      <TaskForm
        mode="create"
        :account-options="accountOptions"
        :default-account="defaultAccountPath"
        :default-values="defaultValues"
        @submit="(data) => handleCreateTask(data as TaskGenerateRequest)"
      />
      <DialogFooter>
        <Button type="submit" form="task-form" :disabled="isSubmitting">
          {{ isSubmitting ? '提交中...' : '创建任务' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
  <TaskGenerationDialog
    v-model:open="isProgressOpen"
    :job="activeJob"
  />
</template>
