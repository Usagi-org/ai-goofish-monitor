import { ref, onMounted, onUnmounted } from 'vue'
import * as logsApi from '@/api/logs'

export function useLogs() {
  const logs = ref('')
  const currentPos = ref(0)
  const currentTaskId = ref<number | null>(null)
  const historyOffset = ref(0)
  const hasMoreHistory = ref(false)
  const isFetchingHistory = ref(false)
  const isAutoRefresh = ref(true)
  const isLoading = ref(false)
  const error = ref<Error | null>(null)
  
  let refreshInterval: number | null = null
  const MAX_LOG_CHARS = 200_000
  const TRIM_LOG_CHARS = 150_000
  const TRIM_NOTICE = '...日志过长已截断，仅保留最新内容...'

  function appendLogs(content: string) {
    if (!content) return
    logs.value += content
    // Prevent unbounded growth that can freeze the UI.
    if (logs.value.length > MAX_LOG_CHARS) {
      const tail = logs.value.slice(-TRIM_LOG_CHARS)
      logs.value = `${TRIM_NOTICE}\n${tail}`
    }
  }

  async function fetchLogs() {
    if (isLoading.value) return
    if (currentTaskId.value === null) return
    isLoading.value = true
    try {
      const data = await logsApi.getLogs(currentPos.value, currentTaskId.value)
      if (data.new_pos < currentPos.value) {
        // Log file rotated or cleared.
        logs.value = ''
      }
      if (data.new_content) {
        appendLogs(data.new_content)
      }
      currentPos.value = data.new_pos
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isLoading.value = false
    }
  }

  async function loadLatest(limitLines: number = 50) {
    if (isFetchingHistory.value) return
    if (currentTaskId.value === null) return
    isFetchingHistory.value = true
    try {
      const data = await logsApi.getLogTail(currentTaskId.value, 0, limitLines)
      logs.value = data.content || ''
      historyOffset.value = data.next_offset
      hasMoreHistory.value = data.has_more
      currentPos.value = data.new_pos
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isFetchingHistory.value = false
    }
  }

  async function loadPrevious(limitLines: number = 50) {
    if (isFetchingHistory.value) return
    if (!hasMoreHistory.value) return
    if (currentTaskId.value === null) return
    isFetchingHistory.value = true
    try {
      const data = await logsApi.getLogTail(currentTaskId.value, historyOffset.value, limitLines)
      if (data.content) {
        logs.value = logs.value ? `${data.content}\n${logs.value}` : data.content
      }
      historyOffset.value = data.next_offset
      hasMoreHistory.value = data.has_more
      currentPos.value = data.new_pos
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isFetchingHistory.value = false
    }
  }

  async function clearLogs() {
    try {
      if (currentTaskId.value === null) return
      await logsApi.clearLogs(currentTaskId.value)
      logs.value = ''
      currentPos.value = 0
      historyOffset.value = 0
      hasMoreHistory.value = false
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    }
  }

  function startAutoRefresh() {
    if (refreshInterval) return
    fetchLogs() // Fetch immediately
    refreshInterval = window.setInterval(fetchLogs, 2000)
    isAutoRefresh.value = true
  }

  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
    isAutoRefresh.value = false
  }

  function toggleAutoRefresh() {
    if (isAutoRefresh.value) {
      stopAutoRefresh()
    } else {
      startAutoRefresh()
    }
  }

  function setTaskId(taskId: number | null) {
    if (currentTaskId.value === taskId) return
    currentTaskId.value = taskId
    logs.value = ''
    currentPos.value = 0
    historyOffset.value = 0
    hasMoreHistory.value = false
  }

  onMounted(() => {
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    logs,
    isAutoRefresh,
    isLoading, // Not strictly used for polling to avoid flickering
    isFetchingHistory,
    hasMoreHistory,
    error,
    fetchLogs,
    clearLogs,
    toggleAutoRefresh,
    setTaskId,
    loadLatest,
    loadPrevious
  }
}
