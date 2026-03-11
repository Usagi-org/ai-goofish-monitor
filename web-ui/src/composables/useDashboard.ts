import { computed, ref, watch } from 'vue'
import * as dashboardApi from '@/api/dashboard'
import * as resultsApi from '@/api/results'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  DashboardSnapshot,
  DashboardSuggestion,
  DashboardTaskSummary,
} from '@/types/dashboard.d.ts'
import type { ResultInsights } from '@/types/result.d.ts'

function buildSuggestion(
  focusTask: DashboardTaskSummary | undefined,
): DashboardSuggestion {
  if (!focusTask || focusTask.task_id === null) {
    return {
      title: '开始首个真实监测任务',
      description: '当前没有可优化的任务，先创建一个真实监测任务，再回来查看趋势和推荐。',
      actionLabel: '去任务页创建',
      routeName: 'Tasks',
      query: { create: '1' },
    }
  }

  const query: Record<string, string> = {
    edit: String(focusTask.task_id),
    taskName: focusTask.task_name,
    keyword: focusTask.keyword,
    maxPages: String(Math.max(3, focusTask.total_items > 80 ? 5 : 4)),
    newPublishOption: focusTask.recommended_items > 0 ? '1天内' : '最新',
    freeShipping: 'true',
    personalOnly: 'true',
  }

  return {
    title: focusTask.recommended_items > 0 ? '把高价值任务再压榨一点' : '先提高监测命中率',
    description: focusTask.recommended_items > 0
      ? `“${focusTask.task_name}”已经出现真实推荐，建议提高页数并聚焦新发布商品。`
      : `“${focusTask.task_name}”还没看到推荐结果，建议扩大搜索页数并优先抓最新发布。`,
    actionLabel: '带推荐参数去任务页',
    routeName: 'Tasks',
    query,
  }
}

export function useDashboard() {
  const { on } = useWebSocket()
  const snapshot = ref<DashboardSnapshot | null>(null)
  const focusInsights = ref<ResultInsights | null>(null)
  const isLoading = ref(false)
  const error = ref<Error | null>(null)

  async function fetchSummary() {
    isLoading.value = true
    error.value = null
    try {
      snapshot.value = await dashboardApi.getDashboardSummary()
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isLoading.value = false
    }
  }

  const taskSummaries = computed(() => snapshot.value?.task_summaries || [])
  const activities = computed(() => snapshot.value?.recent_activities || [])

  const stats = computed(() => {
    const summary = snapshot.value?.summary
    return {
      totalTasks: taskSummaries.value.length,
      enabledTasks: summary?.enabled_tasks || 0,
      runningTasks: summary?.running_tasks || 0,
      scannedItems: summary?.scanned_items || 0,
      recommendedItems: summary?.recommended_items || 0,
      aiRecommendedItems: summary?.ai_recommended_items || 0,
      keywordRecommendedItems: summary?.keyword_recommended_items || 0,
      resultFiles: summary?.result_files || 0,
    }
  })

  const focusTask = computed(() =>
    taskSummaries.value.find((item) => item.filename === snapshot.value?.focus_file) ||
    taskSummaries.value.find((item) => item.filename) ||
    taskSummaries.value[0]
  )

  async function fetchFocusInsights(filename: string | null | undefined) {
    if (!filename) {
      focusInsights.value = null
      return
    }
    try {
      focusInsights.value = await resultsApi.getResultInsights(filename)
    } catch {
      focusInsights.value = null
    }
  }

  watch(
    () => focusTask.value?.filename,
    (filename) => {
      fetchFocusInsights(filename)
    },
    { immediate: true }
  )

  const suggestion = computed(() => buildSuggestion(focusTask.value))

  on('tasks_updated', fetchSummary)
  on('results_updated', fetchSummary)
  on('task_status_changed', fetchSummary)

  fetchSummary()

  return {
    snapshot,
    focusInsights,
    stats,
    taskSummaries,
    activities,
    focusTask,
    suggestion,
    isLoading,
    error,
    fetchSummary,
  }
}
