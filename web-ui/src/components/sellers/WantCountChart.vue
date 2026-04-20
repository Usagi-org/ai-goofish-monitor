<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getWantCountHistory } from '@/api/sellers'
import type { WantCountHistoryPoint } from '@/types/seller.d.ts'
import { TrendingUp, TrendingDown } from 'lucide-vue-next'

const props = defineProps<{
  itemId: string
  days?: number
}>()

const history = ref<WantCountHistoryPoint[]>([])
const loading = ref(false)

watch(
  () => props.itemId,
  async (newId) => {
    if (newId) {
      loading.value = true
      try {
        history.value = await getWantCountHistory(newId, props.days || 30)
      } catch (error) {
        console.error('加载想要数历史失败:', error)
      } finally {
        loading.value = false
      }
    }
  },
  { immediate: true }
)

const validPoints = computed(() =>
  history.value.filter((point) => point.want_count !== null && point.want_count !== undefined)
)

const wantCountChange = computed(() => {
  if (validPoints.value.length < 2) return null
  const current = validPoints.value[0]?.want_count as number | undefined
  const previous = validPoints.value[validPoints.value.length - 1]?.want_count as number | undefined
  if (current === undefined || previous === undefined) return null
  const change = current - previous
  return { current, change, isIncrease: change > 0 }
})

const chartWidth = 400
const chartHeight = 150
const padding = 30

const valueRange = computed(() => {
  if (validPoints.value.length === 0) {
    return { min: 0, max: 1 }
  }
  const values = validPoints.value.map((point) => point.want_count as number)
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    return { min: 0, max: max + 10 }
  }
  return { min: 0, max: max * 1.1 }
})

function resolveX(index: number) {
  if (validPoints.value.length <= 1) return chartWidth / 2
  const usableWidth = chartWidth - padding * 2
  return padding + (usableWidth / (validPoints.value.length - 1)) * index
}

function resolveY(value: number) {
  const usableHeight = chartHeight - padding * 2
  const ratio = (value - valueRange.value.min) / (valueRange.value.max - valueRange.value.min)
  return chartHeight - padding - ratio * usableHeight
}

function buildPath() {
  const commands = validPoints.value.map((point, index) => {
    const prefix = index === 0 ? 'M' : 'L'
    return `${prefix} ${resolveX(index)} ${resolveY(point.want_count as number)}`
  })
  return commands.join(' ')
}

const path = computed(() => buildPath())
</script>

<template>
  <Card>
    <CardHeader class="pb-2">
      <div class="flex items-center justify-between">
        <div>
          <CardTitle class="text-sm font-semibold">想要数趋势</CardTitle>
          <CardDescription class="text-xs">
            最近 {{ days }} 天
          </CardDescription>
        </div>
        <div v-if="wantCountChange" class="text-right">
          <div class="text-xs text-slate-500">当前</div>
          <div class="text-lg font-bold">{{ wantCountChange.current }}</div>
          <div
            class="flex items-center gap-1 text-xs font-bold"
            :class="wantCountChange.isIncrease ? 'text-rose-600' : 'text-emerald-600'"
          >
            <component
              :is="wantCountChange.isIncrease ? TrendingUp : TrendingDown"
              class="w-3 h-3"
            />
            {{ Math.abs(wantCountChange.change) }}
          </div>
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div v-if="loading" class="h-[150px] flex items-center justify-center text-sm text-slate-400">
        加载中...
      </div>
      <div v-else-if="validPoints.length === 0" class="h-[150px] flex items-center justify-center text-sm text-slate-400">
        暂无想要数数据
      </div>
      <svg v-else :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="h-[150px] w-full">
        <defs>
          <linearGradient id="want-area-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#f43f5e" stop-opacity="0.2" />
            <stop offset="100%" stop-color="#f43f5e" stop-opacity="0" />
          </linearGradient>
        </defs>

        <!-- 网格线 -->
        <g>
          <line
            v-for="index in 4"
            :key="index"
            :x1="padding"
            :x2="chartWidth - padding"
            :y1="padding + ((chartHeight - padding * 2) / 4) * (index - 1)"
            :y2="padding + ((chartHeight - padding * 2) / 4) * (index - 1)"
            stroke="#e5e5e5"
            stroke-dasharray="4 4"
          />
        </g>

        <!-- 面积区域 -->
        <path
          :d="`${path} L ${chartWidth - padding} ${chartHeight - padding} L ${padding} ${chartHeight - padding} Z`"
          fill="url(#want-area-fill)"
        />

        <!-- 折线 -->
        <path
          :d="path"
          fill="none"
          stroke="#f43f5e"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <!-- 数据点 -->
        <circle
          v-for="(point, index) in validPoints"
          :key="point.time"
          :cx="resolveX(index)"
          :cy="resolveY(point.want_count as number)"
          r="3"
          fill="#f43f5e"
        />

        <!-- 时间标签 -->
        <text
          x="padding"
          y="chartHeight - 8"
          text-anchor="middle"
          fill="#999"
          font-size="10"
        >
          {{ validPoints[0]?.time.slice(5, 10) }}
        </text>
        <text
          :x="chartWidth - padding"
          y="chartHeight - 8"
          text-anchor="middle"
          fill="#999"
          font-size="10"
        >
          {{ validPoints[validPoints.length - 1]?.time.slice(5, 10) }}
        </text>

        <!-- 当前值标签 -->
        <text
          :x="chartWidth - padding"
          :y="resolveY(validPoints[0]?.want_count as number) - 8"
          text-anchor="middle"
          fill="#f43f5e"
          font-size="11"
          font-weight="bold"
        >
          {{ validPoints[0]?.want_count }}
        </text>
      </svg>
    </CardContent>
  </Card>
</template>
