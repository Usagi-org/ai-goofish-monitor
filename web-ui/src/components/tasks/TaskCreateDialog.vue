<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
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
const { t } = useI18n()

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
    toast({ title: t('tasks.toasts.created') })
    isFormOpen.value = false
  } catch (error) {
    toast({
      title: t('tasks.toasts.createFailed'),
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
      toast({ title: t('tasks.toasts.created') })
      isProgressOpen.value = false
      clearJob()
      return
    }
    if (status === 'failed') {
      isSubmitting.value = false
      toast({
        title: t('tasks.toasts.createFailed'),
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
    title: t('tasks.toasts.progressFailed'),
    description: value.message,
    variant: 'destructive',
  })
})
</script>

<template>
  <Dialog v-model:open="isFormOpen">
    <DialogTrigger as-child>
      <Button>{{ t('tasks.createDialog.trigger') }}</Button>
    </DialogTrigger>
    <DialogContent class="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>{{ t('tasks.createDialog.title') }}</DialogTitle>
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
          {{ isSubmitting ? t('tasks.createDialog.submitting') : t('tasks.createDialog.submit') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
  <TaskGenerationDialog
    v-model:open="isProgressOpen"
    :job="activeJob"
  />
</template>
