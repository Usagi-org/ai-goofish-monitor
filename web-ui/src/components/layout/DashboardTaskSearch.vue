<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { LoaderCircle, Search, Sparkles } from 'lucide-vue-next'
import Badge from '@/components/ui/badge/Badge.vue'
import * as taskApi from '@/api/tasks'
import { useWebSocket } from '@/composables/useWebSocket'
import type { Task } from '@/types/task.d.ts'

const MAX_RESULTS = 6

const router = useRouter()
const { t } = useI18n()
const { on } = useWebSocket()
const rootRef = ref<HTMLElement | null>(null)
const query = ref('')
const tasks = ref<Task[]>([])
const isLoading = ref(false)
const error = ref('')
const isOpen = ref(false)
const highlightedIndex = ref(0)

const normalizedQuery = computed(() => query.value.trim().toLowerCase())

const visibleTasks = computed(() => {
  const list = normalizedQuery.value
    ? tasks.value.filter((task) => matchesTask(task, normalizedQuery.value))
    : tasks.value
  return list.slice(0, MAX_RESULTS)
})

const panelTitle = computed(() => (
  normalizedQuery.value ? t('tasks.search.matchingTasks') : t('tasks.search.recentTasks')
))

const shouldShowPanel = computed(() => (
  isOpen.value && (
    isLoading.value ||
    Boolean(error.value) ||
    visibleTasks.value.length > 0 ||
    Boolean(normalizedQuery.value)
  )
))

function matchesTask(task: Task, value: string) {
  const fields = [
    task.task_name,
    task.keyword,
    task.description || '',
    task.region || '',
  ]
  return fields.some((field) => field.toLowerCase().includes(value))
}

function getTaskStatus(task: Task) {
  if (task.is_running) return t('common.running')
  if (task.enabled) return t('common.enabled')
  return t('common.disabled')
}

function getTaskMeta(task: Task) {
  const parts = [task.keyword]
  if (task.region) parts.push(task.region)
  parts.push(t('tasks.search.maxPages', { count: task.max_pages }))
  return parts.join(' · ')
}

async function fetchTasks() {
  isLoading.value = true
  error.value = ''
  try {
    tasks.value = await taskApi.getAllTasks()
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('tasks.search.loadFailed')
  } finally {
    isLoading.value = false
  }
}

function ensureLoaded() {
  if (tasks.value.length || isLoading.value) return
  fetchTasks()
}

function openPanel() {
  ensureLoaded()
  isOpen.value = true
}

function closePanel() {
  isOpen.value = false
  highlightedIndex.value = 0
}

function selectTask(task: Task) {
  closePanel()
  router.push({
    name: 'Tasks',
    query: { edit: String(task.id) },
  })
}

function moveHighlight(direction: 1 | -1) {
  if (!visibleTasks.value.length) return
  const lastIndex = visibleTasks.value.length - 1
  const nextIndex = highlightedIndex.value + direction
  if (nextIndex < 0) {
    highlightedIndex.value = lastIndex
    return
  }
  if (nextIndex > lastIndex) {
    highlightedIndex.value = 0
    return
  }
  highlightedIndex.value = nextIndex
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closePanel()
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    openPanel()
    moveHighlight(1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    openPanel()
    moveHighlight(-1)
    return
  }
  if (event.key === 'Enter' && visibleTasks.value.length) {
    event.preventDefault()
    const selectedTask = visibleTasks.value[highlightedIndex.value]
    if (selectedTask) {
      selectTask(selectedTask)
    }
  }
}

function handlePointerDown(event: MouseEvent) {
  if (!rootRef.value) return
  const target = event.target
  if (target instanceof Node && !rootRef.value.contains(target)) {
    closePanel()
  }
}

watch(normalizedQuery, () => {
  highlightedIndex.value = 0
  if (!query.value.trim()) return
  openPanel()
})

on('tasks_updated', fetchTasks)
on('task_status_changed', fetchTasks)

onMounted(() => {
  document.addEventListener('mousedown', handlePointerDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handlePointerDown)
})
</script>

<template>
  <div ref="rootRef" class="relative w-full">
    <Search class="absolute left-3 top-1/2 z-10 -translate-y-1/2 w-4 h-4 text-slate-400 transition-colors" />
    <input
      v-model="query"
      type="text"
      :placeholder="t('tasks.search.placeholder')"
      class="w-full h-10 rounded-xl border border-slate-200/60 bg-slate-100/60 pl-10 pr-16 text-sm text-slate-700 transition-all outline-none focus:border-primary/40 focus:bg-white focus:ring-2 focus:ring-primary/15"
      @focus="openPanel"
      @keydown="handleKeydown"
    />
    <kbd class="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 shadow-sm">
      ESC
    </kbd>

    <transition name="search-panel">
      <div
        v-if="shouldShowPanel"
        class="absolute inset-x-0 top-[calc(100%+0.75rem)] overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/95 shadow-[0_28px_70px_rgba(15,23,42,0.16)] backdrop-blur-xl"
      >
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <div>
            <p class="text-xs font-black uppercase tracking-[0.24em] text-slate-400">{{ panelTitle }}</p>
            <p class="mt-1 text-xs text-slate-500">
              {{ normalizedQuery ? t('tasks.search.resultCount', { count: visibleTasks.length }) : t('tasks.search.enterHint') }}
            </p>
          </div>
          <Badge variant="outline" class="border-slate-200 bg-slate-50 text-[10px] text-slate-500">
            {{ t('routes.tasks') }}
          </Badge>
        </div>

        <div v-if="isLoading" class="flex items-center gap-2 px-4 py-6 text-sm text-slate-500">
          <LoaderCircle class="h-4 w-4 animate-spin text-primary" />
          {{ t('tasks.search.loading') }}
        </div>

        <div v-else-if="error" class="px-4 py-6 text-sm text-rose-600">
          {{ error }}
        </div>

        <div v-else-if="visibleTasks.length === 0" class="px-4 py-6">
          <p class="text-sm font-semibold text-slate-700">{{ t('tasks.search.emptyTitle') }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ t('tasks.search.emptyDescription') }}</p>
        </div>

        <div v-else class="divide-y divide-slate-100">
          <button
            v-for="(task, index) in visibleTasks"
            :key="task.id"
            class="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors"
            :class="index === highlightedIndex ? 'bg-slate-900 text-white' : 'hover:bg-slate-50 text-slate-800'"
            @mouseenter="highlightedIndex = index"
            @click="selectTask(task)"
          >
            <div
              class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
              :class="task.is_running ? 'bg-emerald-400' : task.enabled ? 'bg-sky-400' : 'bg-slate-300'"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between gap-3">
                <p class="truncate text-sm font-bold">{{ task.task_name }}</p>
                <Badge
                  variant="outline"
                  class="shrink-0 text-[10px]"
                  :class="index === highlightedIndex ? 'border-white/20 bg-white/10 text-white' : 'border-slate-200 text-slate-500'"
                >
                  {{ getTaskStatus(task) }}
                </Badge>
              </div>
              <p
                class="mt-1 truncate text-xs"
                :class="index === highlightedIndex ? 'text-white/70' : 'text-slate-500'"
              >
                {{ getTaskMeta(task) }}
              </p>
              <p
                v-if="task.description"
                class="mt-1 truncate text-xs"
                :class="index === highlightedIndex ? 'text-white/70' : 'text-slate-400'"
              >
                {{ task.description }}
              </p>
            </div>
          </button>
        </div>

        <div class="flex items-center justify-between border-t border-slate-100 bg-slate-50/80 px-4 py-3 text-[11px] text-slate-500">
          <div class="flex items-center gap-2">
            <Sparkles class="h-3.5 w-3.5 text-primary" />
            {{ t('tasks.search.footerHint') }}
          </div>
          <div class="hidden items-center gap-2 md:flex">
            <span>{{ t('tasks.search.keyboardUpDown') }}</span>
            <span>{{ t('tasks.search.keyboardEnter') }}</span>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.search-panel-enter-active,
.search-panel-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.search-panel-enter-from,
.search-panel-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
