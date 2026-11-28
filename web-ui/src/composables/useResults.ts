import { ref, reactive, watch, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type {
  CheckItemStatusResponse,
  ItemStatus,
  ResultInsights,
  ResultItem,
} from '@/types/result.d.ts'
import * as resultsApi from '@/api/results'
import type { GetResultContentParams } from '@/api/results'
import { useWebSocket } from '@/composables/useWebSocket'
import * as tasksApi from '@/api/tasks'

export interface ResultFilterState {
  recommended_only: boolean
  ai_recommended_only: boolean
  keyword_recommended_only: boolean
  include_hidden: boolean
  hide_sold: boolean
  sort_by: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count'
  sort_order: 'asc' | 'desc'
}

export function useResults() {
  const { t } = useI18n()
  const route = useRoute()
  // State
  const files = ref<string[]>([])
  const selectedFile = ref<string | null>(null)
  const results = ref<ResultItem[]>([])
  const insights = ref<ResultInsights | null>(null)
  const totalItems = ref(0)
  const page = ref(1)
  const limit = ref(100)
  const blacklistKeywords = ref<string[]>([])
  const taskNameByKeyword = ref<Record<string, string>>({})
  const isFileOptionsReady = ref(false)
  const hasFetchedFiles = ref(false)
  const hasFetchedTasks = ref(false)
  const isSavingBlacklist = ref(false)
  const isCheckingStatus = ref(false)
  const checkingItemIds = ref<string[]>([])
  const readyDelayMs = 200
  let readyTimer: ReturnType<typeof setTimeout> | null = null

  const STORAGE_KEY_FILTERS = 'resultFilters'

  function loadPersistedFilters(): ResultFilterState {
    const defaults: ResultFilterState = {
      recommended_only: false,
      ai_recommended_only: false,
      keyword_recommended_only: false,
      include_hidden: false,
      hide_sold: false,
      sort_by: 'crawl_time',
      sort_order: 'desc',
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEY_FILTERS)
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<ResultFilterState>
        return {
          recommended_only: Boolean(parsed.recommended_only ?? defaults.recommended_only),
          ai_recommended_only: Boolean(parsed.ai_recommended_only ?? defaults.ai_recommended_only),
          keyword_recommended_only: Boolean(parsed.keyword_recommended_only ?? defaults.keyword_recommended_only),
          include_hidden: Boolean(parsed.include_hidden ?? defaults.include_hidden),
          hide_sold: Boolean(parsed.hide_sold ?? defaults.hide_sold),
          sort_by: parsed.sort_by ?? defaults.sort_by,
          sort_order: parsed.sort_order ?? defaults.sort_order,
        }
      }
    } catch { /* ignore */ }
    return defaults
  }

  const filters = reactive<ResultFilterState>(loadPersistedFilters())

  const isLoading = ref(false)
  const error = ref<Error | null>(null)
  const { on } = useWebSocket()

  function buildResultQueryParams(): Omit<GetResultContentParams, 'page' | 'limit'> {
    return {
      recommended_only: filters.recommended_only,
      ai_recommended_only: filters.ai_recommended_only,
      keyword_recommended_only: filters.keyword_recommended_only,
      include_hidden: filters.include_hidden,
      include_sold: !filters.hide_sold,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
    }
  }

  function normalizeKeyword(value: string) {
    return value.trim().toLowerCase().replace(/\s+/g, '_')
  }

  function getKeywordFromFilename(filename: string) {
    return filename.replace(/_full_data\.jsonl$/i, '').toLowerCase()
  }

  // Methods
  async function fetchFiles() {
    try {
      const fileList = await resultsApi.getResultFiles()
      files.value = fileList
      if (selectedFile.value && fileList.includes(selectedFile.value)) {
        return
      }

      const lastSelected = localStorage.getItem('lastSelectedResultFile')
      if (lastSelected && fileList.includes(lastSelected)) {
        selectedFile.value = lastSelected
        return
      }

      selectedFile.value = fileList[0] || null
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      hasFetchedFiles.value = true
      scheduleFileOptionsReady()
    }
  }

  async function fetchResults() {
    if (!selectedFile.value) {
      results.value = []
      totalItems.value = 0
      return
    }

    isLoading.value = true
    error.value = null
    try {
      const data = await resultsApi.getResultContent(selectedFile.value, {
        ...buildResultQueryParams(),
        page: page.value,
        limit: limit.value,
      })
      results.value = data.items
      totalItems.value = data.total_items
    } catch (e) {
      if (e instanceof Error) error.value = e
      results.value = []
      totalItems.value = 0
    } finally {
      isLoading.value = false
    }
  }

  async function fetchInsights() {
    if (!selectedFile.value) {
      insights.value = null
      return
    }

    try {
      insights.value = await resultsApi.getResultInsights(selectedFile.value)
    } catch (e) {
      if (e instanceof Error) error.value = e
      insights.value = null
    }
  }

  async function fetchBlacklistRules() {
    if (!selectedFile.value) {
      blacklistKeywords.value = []
      return
    }

    try {
      const data = await resultsApi.getResultBlacklistRules(selectedFile.value)
      blacklistKeywords.value = data.keywords || []
    } catch (e) {
      if (e instanceof Error) error.value = e
      blacklistKeywords.value = []
    }
  }

  async function fetchTaskNameMap() {
    try {
      const tasks = await tasksApi.getAllTasks()
      const mapping: Record<string, string> = {}
      tasks.forEach((task) => {
        if (task.keyword) {
          mapping[normalizeKeyword(task.keyword)] = task.task_name
        }
      })
      taskNameByKeyword.value = mapping
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      hasFetchedTasks.value = true
      scheduleFileOptionsReady()
    }
  }

  function scheduleFileOptionsReady() {
    if (isFileOptionsReady.value || !hasFetchedFiles.value || !hasFetchedTasks.value) return
    if (readyTimer) return
    readyTimer = setTimeout(() => {
      isFileOptionsReady.value = true
      readyTimer = null
    }, readyDelayMs)
  }

  // Real-time updates
  on('results_updated', async () => {
    const oldFile = selectedFile.value
    await fetchFiles()
    if (selectedFile.value && selectedFile.value === oldFile) {
      fetchResults()
      fetchInsights()
    }
  })

  on('tasks_updated', () => {
    fetchTaskNameMap()
  })

  async function refreshResults() {
    const current = selectedFile.value
    await fetchFiles()
    if (selectedFile.value && selectedFile.value === current) {
      await fetchResults()
      await fetchInsights()
      await fetchBlacklistRules()
    }
  }

  function exportSelectedResults() {
    if (!selectedFile.value) return
    resultsApi.downloadResultExport(selectedFile.value, buildResultQueryParams())
  }

  async function deleteSelectedFile(filename?: string) {
    const target = filename || selectedFile.value
    if (!target) return
    isLoading.value = true
    error.value = null
    try {
      await resultsApi.deleteResultFile(target)
      if (selectedFile.value === target) {
        const lastSelected = localStorage.getItem('lastSelectedResultFile')
        if (lastSelected === target) {
          localStorage.removeItem('lastSelectedResultFile')
        }
      }
      await fetchFiles()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function toggleItemBlock(item: ResultItem): Promise<ItemStatus | null> {
    if (!selectedFile.value) return null
    const itemId = item.商品信息?.商品ID
    if (!itemId) return null
    const newStatus: ItemStatus = item._status === 'hidden' ? 'active' : 'hidden'
    try {
      await resultsApi.updateItemStatus(selectedFile.value, itemId, newStatus)
      await Promise.all([fetchResults(), fetchInsights()])
      return newStatus
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    }
  }

  async function toggleItemSold(item: ResultItem): Promise<ItemStatus | null> {
    if (!selectedFile.value) return null
    const itemId = item.商品信息?.商品ID
    if (!itemId) return null
    const isSold = item._status === 'sold' || item._is_sold === true
    const newStatus: ItemStatus = isSold ? 'active' : 'sold'
    try {
      await resultsApi.updateItemStatus(selectedFile.value, itemId, newStatus)
      await Promise.all([fetchResults(), fetchInsights()])
      return newStatus
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    }
  }

  async function checkAllActiveStatus(batchLimit?: number): Promise<CheckItemStatusResponse | null> {
    if (!selectedFile.value || isCheckingStatus.value) return null
    isCheckingStatus.value = true
    error.value = null
    try {
      const payload = batchLimit ? { limit: batchLimit } : {}
      const response = await resultsApi.checkResultStatus(selectedFile.value, payload)
      await Promise.all([fetchResults(), fetchInsights()])
      return response
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isCheckingStatus.value = false
    }
  }

  async function checkSingleItemStatus(item: ResultItem): Promise<CheckItemStatusResponse | null> {
    if (!selectedFile.value) return null
    const itemId = item.商品信息?.商品ID
    if (!itemId || checkingItemIds.value.includes(itemId)) return null
    checkingItemIds.value = [...checkingItemIds.value, itemId]
    error.value = null
    try {
      const response = await resultsApi.checkResultStatus(selectedFile.value, {
        item_ids: [itemId],
        limit: 1,
      })
      await Promise.all([fetchResults(), fetchInsights()])
      return response
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      checkingItemIds.value = checkingItemIds.value.filter((id) => id !== itemId)
    }
  }

  async function saveBlacklistRules(keywords: string[]) {
    if (!selectedFile.value) return
    isSavingBlacklist.value = true
    error.value = null
    try {
      const data = await resultsApi.updateResultBlacklistRules(selectedFile.value, keywords)
      blacklistKeywords.value = data.keywords || []
      await fetchResults()
      await fetchInsights()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSavingBlacklist.value = false
    }
  }

  // Watchers
  watch(filters, (val) => {
    localStorage.setItem(STORAGE_KEY_FILTERS, JSON.stringify(val))
  }, { deep: true })
  watch([selectedFile, filters], fetchResults, { deep: true })
  watch(selectedFile, () => {
    fetchInsights()
    fetchBlacklistRules()
  })
  watch(selectedFile, (value) => {
    if (value) localStorage.setItem('lastSelectedResultFile', value)
  })
  watch(
    [() => route.query.file, files],
    ([routeFile, currentFiles]) => {
      if (typeof routeFile !== 'string') return
      if (currentFiles.includes(routeFile)) {
        selectedFile.value = routeFile
      }
    },
    { immediate: true }
  )

  const fileOptions = computed(() =>
    files.value.map((file) => {
      const keyword = getKeywordFromFilename(file)
      const taskName = taskNameByKeyword.value[keyword]
      return {
        value: file,
        taskName: taskName || t('common.unnamed'),
        label: t('results.filters.taskNameLabel', {
          task: taskName || t('common.unnamed'),
        }),
      }
    })
  )

  // Lifecycle
  onMounted(() => {
    fetchFiles()
    fetchTaskNameMap()
  })

  return {
    files,
    selectedFile,
    results,
    insights,
    totalItems,
    filters,
    isLoading,
    error,
    fetchFiles,
    refreshResults,
    exportSelectedResults,
    deleteSelectedFile,
    toggleItemBlock,
    toggleItemSold,
    isCheckingStatus,
    checkingItemIds,
    checkAllActiveStatus,
    checkSingleItemStatus,
    blacklistKeywords,
    isSavingBlacklist,
    saveBlacklistRules,
    fileOptions,
    isFileOptionsReady,
  }
}
