<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TaskGenerationJob } from '@/types/task.d.ts'
import TaskGenerationProgress from '@/components/tasks/TaskGenerationProgress.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
const { t } = useI18n()

const props = defineProps<{
  job: TaskGenerationJob | null
  open: boolean
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
}>()

const isRunning = computed(() => {
  if (!props.job) return false
  return props.job.status === 'queued' || props.job.status === 'running'
})

const helperText = computed(() => {
  if (!props.job) return ''
  if (props.job.status === 'failed') {
    return t('tasks.generation.helperFailed')
  }
  return t('tasks.generation.helperRunning')
})
</script>

<template>
  <Dialog :open="open" @update:open="(value) => emit('update:open', value)">
    <DialogContent class="sm:max-w-[560px]">
      <DialogHeader>
        <DialogTitle>{{ t('tasks.generation.title') }}</DialogTitle>
        <DialogDescription>
          {{ t('tasks.generation.description') }}
        </DialogDescription>
      </DialogHeader>

      <TaskGenerationProgress v-if="job" :job="job" />
      <p v-if="job" class="text-xs text-slate-500">
        {{ helperText }}
      </p>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          {{ isRunning ? t('tasks.generation.closeWindow') : t('common.close') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
