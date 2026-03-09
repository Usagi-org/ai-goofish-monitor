import { computed, onScopeDispose, ref } from 'vue'
import { getTaskGenerationJob } from '@/api/tasks'
import type { TaskGenerationJob } from '@/types/task.d.ts'

const POLL_INTERVAL_MS = 800

function isTerminalStatus(status: TaskGenerationJob['status']) {
  return status === 'completed' || status === 'failed'
}

export function useTaskGenerationJob() {
  const activeJob = ref<TaskGenerationJob | null>(null)
  const pollingError = ref<Error | null>(null)
  const isPolling = ref(false)
  let pollTimer: ReturnType<typeof window.setTimeout> | null = null

  function clearTimer() {
    if (pollTimer === null) return
    window.clearTimeout(pollTimer)
    pollTimer = null
  }

  async function refreshJob() {
    if (!activeJob.value) return
    try {
      const nextJob = await getTaskGenerationJob(activeJob.value.job_id)
      activeJob.value = nextJob
      pollingError.value = null
      if (isTerminalStatus(nextJob.status)) {
        isPolling.value = false
        clearTimer()
        return
      }
      scheduleNextPoll()
    } catch (error) {
      isPolling.value = false
      clearTimer()
      pollingError.value = error as Error
    }
  }

  function scheduleNextPoll() {
    clearTimer()
    pollTimer = window.setTimeout(() => {
      void refreshJob()
    }, POLL_INTERVAL_MS)
  }

  function beginPolling(job: TaskGenerationJob) {
    activeJob.value = job
    pollingError.value = null
    if (isTerminalStatus(job.status)) {
      isPolling.value = false
      clearTimer()
      return
    }
    isPolling.value = true
    scheduleNextPoll()
  }

  function clearJob() {
    activeJob.value = null
    pollingError.value = null
    isPolling.value = false
    clearTimer()
  }

  onScopeDispose(clearJob)

  return {
    activeJob,
    pollingError,
    isGenerating: computed(() => isPolling.value),
    beginPolling,
    clearJob,
    refreshJob,
  }
}
