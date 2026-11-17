<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PopoverAnchor, PopoverClose, PopoverContent, PopoverPortal, PopoverRoot } from 'reka-ui'
import { History, TrendingDown, X } from 'lucide-vue-next'
import type { PriceInsight } from '@/types/result.d.ts'
import { formatDateTime, formatNumber } from '@/i18n'

const props = defineProps<{ insight: PriceInsight }>()
const { t } = useI18n()
const open = ref(false)
let closeTimer: ReturnType<typeof setTimeout> | undefined
const history = computed(() => props.insight.price_history ?? [])
const hasDrop = computed(() => (props.insight.price_drop_count ?? 0) > 0)
const latestDrop = computed(() => props.insight.latest_price_drop)
const money = (price: number) => `¥${formatNumber(price, { maximumFractionDigits: 2 })}`
const time = (value: string) => formatDateTime(value, {
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
})
const shortDate = (value: string) => formatDateTime(value, { month: '2-digit', day: '2-digit' })

function keepOpen() {
  clearTimeout(closeTimer)
}

function showHistory() {
  keepOpen()
  open.value = true
}

function leaveHistory(event: PointerEvent) {
  if (event.pointerType !== 'mouse') return
  keepOpen()
  closeTimer = setTimeout(() => { open.value = false }, 220)
}

onBeforeUnmount(keepOpen)

const plot = computed(() => {
  if (!history.value.length) return []
  const prices = history.value.map(point => point.price)
  const times = history.value.map(point => new Date(point.observed_at).getTime())
  const firstTime = times[0]!
  const duration = times[times.length - 1]! - firstTime
  const minimum = Math.min(...prices)
  const maximum = Math.max(...prices)
  return history.value.map((point, index) => ({
    ...point,
    x: duration ? 14 + ((times[index]! - firstTime) / duration) * 280 : 154,
    y: maximum === minimum ? 62 : 108 - ((point.price - minimum) / (maximum - minimum)) * 92,
  }))
})
const chartPath = computed(() => plot.value.map((point, index) =>
  index === 0 ? `M ${point.x} ${point.y}` : `H ${point.x} V ${point.y}`,
).join(' '))
const rows = computed(() => history.value.map((point, index) => ({
  ...point,
  change: index ? Math.round((point.price - history.value[index - 1]!.price) * 100) / 100 : null,
})).reverse())
</script>

<template>
  <PopoverRoot v-model:open="open">
    <PopoverAnchor as-child>
      <button
        type="button"
        class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        :class="hasDrop ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100'"
        aria-haspopup="dialog"
        :aria-expanded="open"
        :aria-label="t(hasDrop ? 'results.card.priceDropHistory' : 'results.card.priceHistory')"
        @pointerenter="event => { if (event.pointerType === 'mouse') showHistory() }"
        @pointerleave="leaveHistory"
        @focus="showHistory"
        @keydown.esc.stop.prevent="open = false"
        @click="showHistory"
      >
        <TrendingDown v-if="hasDrop" class="h-3.5 w-3.5" aria-hidden="true" />
        <History v-else class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t(hasDrop ? 'results.card.priceDropped' : 'results.card.priceHistory') }}
      </button>
    </PopoverAnchor>
    <PopoverPortal>
      <PopoverContent
        :aria-label="t('results.card.priceHistory')"
        side="bottom"
        align="start"
        :side-offset="8"
        :collision-padding="12"
        class="z-50 max-h-[var(--reka-popover-content-available-height)] w-[340px] max-w-[calc(100vw-24px)] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 text-slate-700 shadow-xl outline-none"
        @pointerenter="keepOpen"
        @pointerleave="leaveHistory"
        @focusin="keepOpen"
        @open-auto-focus.prevent
        @close-auto-focus.prevent
      >
        <div class="mb-3 flex items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-900">{{ t('results.card.priceHistory') }}</h3>
            <p class="mt-1 text-xs text-slate-500">{{ t('results.card.priceObservations', { count: history.length }) }}</p>
          </div>
          <PopoverClose :aria-label="t('results.card.closeHistory')" class="rounded-full p-1 text-slate-400 hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-sky-500">
            <X class="h-4 w-4" />
          </PopoverClose>
        </div>
        <div v-if="latestDrop" class="mb-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <div class="font-semibold">{{ t('results.card.latestPriceDrop', { amount: money(latestDrop.from_price - latestDrop.to_price) }) }}</div>
          <div class="mt-1">{{ money(latestDrop.from_price) }} → {{ money(latestDrop.to_price) }}</div>
          <div class="mt-1 text-[11px] text-emerald-700">{{ time(latestDrop.observed_at) }}</div>
        </div>
        <div class="flex justify-between text-[11px] text-slate-500">
          <span>{{ t('results.card.historicalLow') }} {{ money(insight.min_price ?? 0) }}</span>
          <span>{{ t('results.card.historicalHigh') }} {{ money(insight.max_price ?? 0) }}</span>
        </div>
        <svg viewBox="0 0 308 124" class="my-1 w-full text-emerald-600" role="img" :aria-label="t('results.card.priceHistory')">
          <path d="M 14 16 H 294 M 14 62 H 294 M 14 108 H 294" stroke="#e2e8f0" stroke-dasharray="3 4" fill="none" />
          <path :d="chartPath" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round" />
          <circle v-for="(point, index) in plot" :key="index" :cx="point.x" :cy="point.y" r="3" fill="currentColor" stroke="white" stroke-width="1">
            <title>{{ time(point.observed_at) }} · {{ money(point.price) }}</title>
          </circle>
        </svg>
        <div v-if="history.length" class="mb-3 flex justify-between text-[10px] text-slate-400">
          <span>{{ shortDate(history[0]!.observed_at) }}</span>
          <span>{{ shortDate(history[history.length - 1]!.observed_at) }}</span>
        </div>
        <p v-if="history.length === 1" class="mb-3 text-xs text-slate-500">{{ t('results.card.singlePriceObservation') }}</p>
        <div class="max-h-40 overflow-y-auto rounded-lg border border-slate-100">
          <table class="w-full text-[11px] tabular-nums">
            <thead class="sticky top-0 bg-slate-50 text-slate-500">
              <tr><th class="px-2 py-2 text-left font-medium">{{ t('results.card.observedAt') }}</th><th class="px-2 py-2 text-right font-medium">{{ t('results.card.observedPrice') }}</th><th class="px-2 py-2 text-right font-medium">{{ t('results.card.priceChange') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="(point, index) in rows" :key="index" class="border-t border-slate-100">
                <td class="whitespace-nowrap px-2 py-2">{{ time(point.observed_at) }}</td>
                <td class="px-2 py-2 text-right font-medium">{{ money(point.price) }}</td>
                <td class="whitespace-nowrap px-2 py-2 text-right" :class="point.change !== null && point.change < 0 ? 'text-emerald-600' : 'text-slate-500'">
                  {{ point.change ? `${point.change > 0 ? '+' : '−'}${money(Math.abs(point.change))}` : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-3 text-[10px] leading-relaxed text-slate-400">{{ t('results.card.priceHistoryNote') }}</p>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>
