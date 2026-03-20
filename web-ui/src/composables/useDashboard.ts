import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
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
  t: (key: string, params?: Record<string, unknown>) => string,
): DashboardSuggestion {
  if (!focusTask || focusTask.task_id === null) {
    return {
      title: t('dashboard.suggestion.firstTaskTitle'),
      description: t('dashboard.suggestion.firstTaskDescription'),
      actionLabel: t('dashboard.suggestion.firstTaskAction'),
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
    title: focusTask.recommended_items > 0
      ? t('dashboard.suggestion.improveValueTitle')
      : t('dashboard.suggestion.improveHitRateTitle'),
    description: focusTask.recommended_items > 0
      ? t('dashboard.suggestion.improveValueDescription', { task: focusTask.task_name })
      : t('dashboard.suggestion.improveHitRateDescription', { task: focusTask.task_name }),
    actionLabel: t('dashboard.suggestion.openTaskAction'),
    routeName: 'Tasks',
    query,
  }
}

export function useDashboard() {
  const { t } = useI18n()
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

  const suggestion = computed(() => buildSuggestion(focusTask.value, t))

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
