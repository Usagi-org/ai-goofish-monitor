<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getPriceHistory } from '@/api/sellers'
import type { PriceHistoryPoint } from '@/types/seller.d.ts'
import { TrendingUp, TrendingDown } from 'lucide-vue-next'

const props = defineProps<{
  itemId: string
  days?: number
}>()

const history = ref<PriceHistoryPoint[]>([])
const loading = ref(false)

watch(
  () => props.itemId,
  async (newId) => {
    if (newId) {
      loading.value = true
      try {
        history.value = await getPriceHistory(newId, props.days || 30)
      } catch (error) {
        console.error('加载价格历史失败:', error)
      } finally {
        loading.value = false
      }
    }
  },
  { immediate: true }
)

const chartWidth = 400
const chartHeight = 150
const padding = 30

const validPoints = computed(() =>
  history.value.filter((point) => point.price !== null && point.price !== undefined)
)

const valueRange = computed(() => {
  if (validPoints.value.length === 0) {
    return { min: 0, max: 1 }
  }
  const values = validPoints.value.map((point) => point.price as number)
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) {
    return { min: min - 1, max: max + 1 }
  }
  return { min: min * 0.95, max: max * 1.05 }
})

const priceChange = computed(() => {
  if (validPoints.value.length < 2) return null
  const current = validPoints.value[0]?.price as number | undefined
  const previous = validPoints.value[validPoints.value.length - 1]?.price as number | undefined
  if (current === undefined || previous === undefined) return null
  const change = current - previous
  const percent = (change / previous) * 100
  return { change, percent, isDrop: change < 0 }
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
    return `${prefix} ${resolveX(index)} ${resolveY(point.price as number)}`
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
          <CardTitle class="text-sm font-semibold">价格趋势</CardTitle>
          <CardDescription class="text-xs">
            最近 {{ days }} 天
          </CardDescription>
        </div>
        <div v-if="priceChange" class="text-right">
          <div
            class="flex items-center gap-1 text-sm font-bold"
            :class="priceChange.isDrop ? 'text-emerald-600' : 'text-rose-600'"
          >
            <component
              :is="priceChange.isDrop ? TrendingDown : TrendingUp"
              class="w-4 h-4"
            />
            {{ Math.abs(priceChange.change).toFixed(2) }}
          </div>
          <div
            class="text-xs"
            :class="priceChange.isDrop ? 'text-emerald-600' : 'text-rose-600'"
          >
            {{ Math.abs(priceChange.percent).toFixed(1) }}%
          </div>
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div v-if="loading" class="h-[150px] flex items-center justify-center text-sm text-slate-400">
        加载中...
      </div>
      <div v-else-if="validPoints.length === 0" class="h-[150px] flex items-center justify-center text-sm text-slate-400">
        暂无价格数据
      </div>
      <svg v-else :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="h-[150px] w-full">
        <defs>
          <linearGradient id="price-area-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#1890ff" stop-opacity="0.2" />
            <stop offset="100%" stop-color="#1890ff" stop-opacity="0" />
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
          fill="url(#price-area-fill)"
        />

        <!-- 折线 -->
        <path
          :d="path"
          fill="none"
          stroke="#1890ff"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <!-- 数据点 -->
        <circle
          v-for="(point, index) in validPoints"
          :key="point.time"
          :cx="resolveX(index)"
          :cy="resolveY(point.price as number)"
          r="3"
          fill="#1890ff"
        />

        <!-- 时间标签 (只显示首尾) -->
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

        <!-- 当前价格标签 -->
        <text
          :x="chartWidth - padding"
          :y="resolveY(validPoints[0]?.price as number) - 8"
          text-anchor="middle"
          fill="#1890ff"
          font-size="11"
          font-weight="bold"
        >
          ¥{{ validPoints[0]?.price }}
        </text>
      </svg>
    </CardContent>
  </Card>
</template>
