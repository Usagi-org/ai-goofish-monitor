<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useDashboard } from '@/composables/useDashboard'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import Badge from '@/components/ui/badge/Badge.vue'
import PriceTrendChart from '@/components/results/PriceTrendChart.vue'
import { formatNumber, formatRelativeTimeFromNow } from '@/i18n'
import {
  Activity,
  ArrowRight,
  Compass,
  LayoutDashboard,
  Search,
  Sparkles,
  Target,
  Zap,
} from 'lucide-vue-next'

const router = useRouter()
const { t } = useI18n()
const {
  focusInsights,
  focusTask,
  suggestion,
  stats,
  activities,
  isLoading,
  error,
} = useDashboard()

const statCards = computed(() => [
  {
    label: t('dashboard.stats.activeTasks'),
    value: String(stats.value.enabledTasks),
    detail: t('dashboard.stats.runningCount', { count: stats.value.runningTasks }),
    icon: Activity,
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
  },
  {
    label: t('dashboard.stats.scannedItems'),
    value: formatNumber(stats.value.scannedItems),
    detail: t('dashboard.stats.resultFiles', { count: stats.value.resultFiles }),
    icon: Search,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
  },
  {
    label: t('dashboard.stats.recommendedItems'),
    value: String(stats.value.recommendedItems),
    detail: t('dashboard.stats.recommendedBreakdown', {
      ai: stats.value.aiRecommendedItems,
      keyword: stats.value.keywordRecommendedItems,
    }),
    icon: Target,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
  },
  {
    label: t('dashboard.stats.monitoredTasks'),
    value: String(stats.value.totalTasks),
    detail: t('dashboard.stats.showAllTasks'),
    icon: Compass,
    color: 'text-purple-500',
    bg: 'bg-purple-500/10',
  },
])

const focusTitle = computed(() => focusTask.value?.task_name || t('dashboard.focus.defaultTitle'))
const focusMeta = computed(() => {
  if (!focusTask.value) return t('dashboard.focus.empty')
  const keyword = focusTask.value.keyword || t('dashboard.focus.missingKeyword')
  const count = focusTask.value.total_items
  return t('dashboard.focus.meta', { keyword, count })
})

const insightCards = computed(() => {
  const market = focusInsights.value?.market_summary
  const history = focusInsights.value?.history_summary
  return [
    {
      label: t('results.insights.currentAvg'),
      value: market?.avg_price ? `¥${market.avg_price}` : '—',
      hint: market
        ? t('results.insights.sampleCount', { count: market.sample_count })
        : t('results.grid.empty'),
    },
    {
      label: t('results.insights.historyAvg'),
      value: history?.avg_price ? `¥${history.avg_price}` : '—',
      hint: history
        ? t('results.insights.uniqueItems', { count: history.unique_items })
        : t('results.insights.noSnapshot'),
    },
    {
      label: t('results.card.marketAvg'),
      value: market?.min_price ? `¥${market.min_price}` : '—',
      hint: market?.max_price
        ? t('results.insights.highestPrice', { price: market.max_price })
        : t('results.insights.noRange'),
    },
  ]
})

function goCreateTask() {
  router.push({
    name: 'Tasks',
    query: { create: '1' },
  })
}

function openSuggestion() {
  router.push({
    name: suggestion.value.routeName,
    query: suggestion.value.query,
  })
}

function openActivity(activity: { filename: string | null; type: string }) {
  if (activity.filename) {
    router.push({ name: 'Results', query: { file: activity.filename } })
    return
  }
  if (activity.type === 'task') {
    router.push({ name: 'Tasks' })
    return
  }
  router.push({ name: 'Dashboard' })
}
</script>

<template>
  <div class="space-y-8 animate-fade-in">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <h1 class="text-3xl font-black text-slate-800 tracking-tight flex items-center gap-3">
          <LayoutDashboard class="w-8 h-8 text-primary" />
          {{ t('dashboard.title') }}
        </h1>
        <p class="text-slate-500 mt-1 font-medium">
          {{ t('dashboard.description') }}
        </p>
      </div>
      <div class="flex items-center gap-3">
        <Button class="shadow-md shadow-primary/20" @click="goCreateTask">
          {{ t('dashboard.createTask') }}
        </Button>
      </div>
    </div>
    <div v-if="error" class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {{ error.message }}
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      <Card
        v-for="stat in statCards"
        :key="stat.label"
        class="border-none shadow-glass bg-white/60 backdrop-blur-md transition-all hover:scale-[1.02]"
      >
        <CardContent class="p-6">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-bold text-slate-400 uppercase tracking-wider">{{ stat.label }}</p>
              <h3 class="text-2xl font-black text-slate-800 mt-1">{{ stat.value }}</h3>
            </div>
            <div :class="[stat.bg, 'p-3 rounded-2xl']">
              <component :is="stat.icon" :class="['w-6 h-6', stat.color]" />
            </div>
          </div>
          <div class="mt-4 text-xs font-bold text-slate-500">
            {{ stat.detail }}
          </div>
        </CardContent>
      </Card>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <Card class="lg:col-span-2 border-none shadow-glass bg-white/60 backdrop-blur-md">
        <CardHeader class="flex flex-col gap-4 border-b border-slate-100/60 pb-5 md:flex-row md:items-start md:justify-between">
          <div class="space-y-2">
            <CardTitle class="text-lg font-bold text-slate-800">
              {{ focusTitle }}
            </CardTitle>
            <p class="text-sm text-slate-500">{{ focusMeta }}</p>
          </div>
          <Badge variant="secondary" class="w-fit bg-blue-100 text-blue-600">
            {{ focusTask?.latest_crawl_time ? t('dashboard.focus.latestUpdate', { time: formatRelativeTimeFromNow(focusTask.latest_crawl_time) }) : t('dashboard.focus.waiting') }}
          </Badge>
        </CardHeader>
        <CardContent class="space-y-6 p-6">
          <div v-if="isLoading" class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-4 py-10 text-center text-sm text-slate-500">
            {{ t('dashboard.focus.loading') }}
          </div>
          <div v-else-if="!focusTask?.filename" class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-4 py-10 text-center text-sm text-slate-500">
            {{ t('dashboard.focus.noResults') }}
          </div>
          <template v-else>
            <div class="grid gap-4 md:grid-cols-3">
              <article
                v-for="card in insightCards"
                :key="card.label"
                class="rounded-[24px] border border-white/70 bg-white/70 p-4 shadow-[0_12px_30px_rgba(92,68,36,0.06)] backdrop-blur"
              >
                <p class="text-xs uppercase tracking-[0.22em] text-[#9b7a5b]">{{ card.label }}</p>
                <p class="mt-3 text-2xl font-semibold text-[#231d18]">{{ card.value }}</p>
                <p class="mt-2 text-xs text-[#7a6855]">{{ card.hint }}</p>
              </article>
            </div>
            <PriceTrendChart :points="focusInsights?.daily_trend || []" />
            <div class="grid gap-3 rounded-[28px] border border-[#d8c7b5] bg-white/80 p-5 shadow-[0_12px_30px_rgba(92,68,36,0.06)] md:grid-cols-3">
              <div class="rounded-2xl bg-[#f8f1e5] px-4 py-3 text-sm text-[#5e5043]">
                {{ t('dashboard.focus.currentMedian') }}
                <span class="font-semibold text-[#2d261f]">
                  {{ focusInsights?.market_summary.median_price ? `¥${focusInsights.market_summary.median_price}` : '—' }}
                </span>
              </div>
              <div class="rounded-2xl bg-[#f4ece2] px-4 py-3 text-sm text-[#5e5043]">
                {{ t('dashboard.focus.historyMin') }}
                <span class="font-semibold text-[#2d261f]">
                  {{ focusInsights?.history_summary.min_price ? `¥${focusInsights.history_summary.min_price}` : '—' }}
                </span>
              </div>
              <div class="rounded-2xl bg-[#eee4d7] px-4 py-3 text-sm text-[#5e5043]">
                {{ t('dashboard.focus.historyMax') }}
                <span class="font-semibold text-[#2d261f]">
                  {{ focusInsights?.history_summary.max_price ? `¥${focusInsights.history_summary.max_price}` : '—' }}
                </span>
              </div>
            </div>
          </template>
        </CardContent>
      </Card>
      <div class="space-y-8">
        <Card class="border-none shadow-glass bg-white/60 backdrop-blur-md">
          <CardHeader>
            <CardTitle class="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Activity class="w-5 h-5 text-rose-500" />
              {{ t('dashboard.activity.title') }}
            </CardTitle>
          </CardHeader>
          <CardContent class="p-0">
            <div v-if="activities.length === 0" class="px-4 pb-4 text-sm text-slate-500">
              {{ t('dashboard.activity.empty') }}
            </div>
            <div v-else class="divide-y divide-slate-100/50">
              <button
                v-for="activity in activities"
                :key="activity.id"
                class="w-full p-4 text-left hover:bg-slate-50/50 transition-colors"
                @click="openActivity(activity)"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3 min-w-0">
                    <div class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0"></div>
                    <div class="min-w-0">
                      <p class="text-sm font-bold text-slate-700 truncate">{{ activity.title }}</p>
                      <p class="text-[11px] text-slate-400">
                        {{ activity.task_name }} · {{ formatRelativeTimeFromNow(activity.timestamp) }}
                      </p>
                      <p v-if="activity.detail" class="mt-1 text-xs text-slate-500 truncate">{{ activity.detail }}</p>
                    </div>
                  </div>
                  <Badge variant="outline" class="text-[10px] border-slate-200 shrink-0">
                    {{ activity.status }}
                  </Badge>
                </div>
              </button>
            </div>
            <button
              class="w-full py-3 text-xs font-bold text-primary hover:bg-slate-50 transition-colors flex items-center justify-center gap-2 border-t border-slate-100/50"
              @click="router.push({ name: 'Logs' })"
            >
              {{ t('dashboard.activity.viewAllLogs') }}
              <ArrowRight class="w-3 h-3" />
            </button>
          </CardContent>
        </Card>
        <div class="bg-gradient-to-br from-indigo-600 to-blue-700 rounded-2xl p-6 text-white shadow-lg shadow-indigo-200">
          <div class="flex items-center gap-2 mb-4">
            <Zap class="w-6 h-6 text-amber-300" />
            <h4 class="font-bold text-lg">{{ t('dashboard.suggestion.sectionTitle') }}</h4>
          </div>
          <p class="text-indigo-100 text-sm leading-relaxed mb-2">{{ suggestion.title }}</p>
          <p class="text-indigo-100/90 text-sm leading-relaxed mb-6">{{ suggestion.description }}</p>
          <Button variant="secondary" class="w-full bg-white text-indigo-700 font-bold hover:bg-indigo-50" @click="openSuggestion">
            <Sparkles class="mr-2 h-4 w-4" />
            {{ suggestion.actionLabel }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
