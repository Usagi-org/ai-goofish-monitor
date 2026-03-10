<script setup lang="ts">
import { computed } from 'vue'
import type { ResultInsights } from '@/types/result.d.ts'
import PriceTrendChart from './PriceTrendChart.vue'

const props = defineProps<{
  insights: ResultInsights | null
  selectedTaskLabel?: string | null
}>()

const summaryCards = computed(() => {
  if (!props.insights) return []
  const market = props.insights.market_summary
  const history = props.insights.history_summary
  return [
    {
      label: '当前样本均价',
      value: market.avg_price ? `¥${market.avg_price}` : '—',
      hint: `样本 ${market.sample_count || 0} 条`,
    },
    {
      label: '历史均价',
      value: history.avg_price ? `¥${history.avg_price}` : '—',
      hint: `唯一商品 ${history.unique_items || 0} 个`,
    },
    {
      label: '当前最低价',
      value: market.min_price ? `¥${market.min_price}` : '—',
      hint: market.max_price ? `最高 ¥${market.max_price}` : '暂无范围',
    },
  ]
})

const latestSnapshotText = computed(() => {
  if (!props.insights?.latest_snapshot_at) return '尚未形成市场快照'
  return `最近更新于 ${new Date(props.insights.latest_snapshot_at).toLocaleString('zh-CN')}`
})
</script>

<template>
  <section class="mb-6 overflow-hidden rounded-[32px] border border-[#dac9b2] bg-[linear-gradient(135deg,#faf5eb_0%,#f2ebe0_55%,#f8f4ef_100%)] shadow-[0_24px_70px_rgba(92,68,36,0.08)]">
    <div class="grid gap-8 px-6 py-6 lg:grid-cols-[1.15fr_0.85fr] lg:px-8">
      <div class="space-y-5">
        <div class="space-y-2">
          <p class="text-xs uppercase tracking-[0.34em] text-[#9b7a5b]">Market Intelligence</p>
          <h2 class="font-serif text-3xl text-[#2d261f]">
            {{ selectedTaskLabel || '价格走势洞察' }}
          </h2>
          <p class="max-w-2xl text-sm leading-6 text-[#6d5b49]">
            用历史快照回看同关键词市场，当前均价、近期波动和价格带都集中在这里。
          </p>
        </div>

        <div class="grid gap-4 md:grid-cols-3">
          <article
            v-for="card in summaryCards"
            :key="card.label"
            class="rounded-[24px] border border-white/70 bg-white/70 p-4 shadow-[0_12px_30px_rgba(92,68,36,0.06)] backdrop-blur"
          >
            <p class="text-xs uppercase tracking-[0.22em] text-[#9b7a5b]">{{ card.label }}</p>
            <p class="mt-3 text-2xl font-semibold text-[#231d18]">{{ card.value }}</p>
            <p class="mt-2 text-xs text-[#7a6855]">{{ card.hint }}</p>
          </article>
        </div>

        <PriceTrendChart :points="insights?.daily_trend || []" />
      </div>

      <div class="space-y-4">
        <div class="rounded-[28px] border border-[#d8c7b5] bg-[#2a4c53] p-6 text-[#f7f1e7] shadow-[0_16px_40px_rgba(24,48,52,0.24)]">
          <p class="text-xs uppercase tracking-[0.3em] text-[#c7ddd7]">Trend Reading</p>
          <p class="mt-4 text-3xl font-semibold">
            {{ insights?.market_summary.sample_count || 0 }} 条
          </p>
          <p class="mt-2 text-sm leading-6 text-[#d5e8e2]">
            当前市场样本已进入历史分析层，可以直接给 AI 价格参照，不再只是新商品列表。
          </p>
        </div>

        <div class="rounded-[28px] border border-[#d8c7b5] bg-white/80 p-5 shadow-[0_12px_30px_rgba(92,68,36,0.06)]">
          <p class="text-xs uppercase tracking-[0.24em] text-[#9b7a5b]">Snapshot Note</p>
          <p class="mt-4 text-sm leading-6 text-[#5e5043]">
            {{ latestSnapshotText }}
          </p>
          <div class="mt-4 grid gap-3 text-sm text-[#6d5b49]">
            <div class="rounded-2xl bg-[#f8f1e5] px-4 py-3">
              当前中位数：
              <span class="font-semibold text-[#2d261f]">
                {{ insights?.market_summary.median_price ? `¥${insights.market_summary.median_price}` : '—' }}
              </span>
            </div>
            <div class="rounded-2xl bg-[#f4ece2] px-4 py-3">
              历史最低价：
              <span class="font-semibold text-[#2d261f]">
                {{ insights?.history_summary.min_price ? `¥${insights.history_summary.min_price}` : '—' }}
              </span>
            </div>
            <div class="rounded-2xl bg-[#eee4d7] px-4 py-3">
              历史最高价：
              <span class="font-semibold text-[#2d261f]">
                {{ insights?.history_summary.max_price ? `¥${insights.history_summary.max_price}` : '—' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
