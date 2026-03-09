<script setup lang="ts">
import { computed } from 'vue'
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
    return '生成失败后会保留这个弹窗，方便你查看错误原因。'
  }
  return '任务已转入后台生成，你可以停留在这里查看步骤，也可以先关闭弹窗。'
})
</script>

<template>
  <Dialog :open="open" @update:open="(value) => emit('update:open', value)">
    <DialogContent class="sm:max-w-[560px]">
      <DialogHeader>
        <DialogTitle>任务生成进度</DialogTitle>
        <DialogDescription>
          AI 正在生成分析标准并创建任务。
        </DialogDescription>
      </DialogHeader>

      <TaskGenerationProgress v-if="job" :job="job" />
      <p v-if="job" class="text-xs text-slate-500">
        {{ helperText }}
      </p>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          {{ isRunning ? '关闭窗口' : '关闭' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
