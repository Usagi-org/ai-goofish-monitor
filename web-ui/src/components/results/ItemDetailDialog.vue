<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResultItem } from '@/types/result.d.ts'
import ItemImageCarousel from './ItemImageCarousel.vue'
import Badge from '@/components/ui/badge/Badge.vue'
import { formatDateTime, formatNumber } from '@/i18n'
import {
  buildGoofishLinks,
  copyTextToClipboard,
  isMobileDevice,
  openGoofishListing,
} from '@/lib/goofishLink'
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  FileText,
  History,
  Loader2,
  MapPin,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  Sparkles,
  Tag,
  TrendingDown,
  User,
  X,
  XCircle,
} from 'lucide-vue-next'

interface Props {
  open: boolean
  item: ResultItem | null
  isCheckingStatus?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'check-status', item: ResultItem): void
  (e: 'toggle-sold', item: ResultItem): void
  (e: 'toggle-block', item: ResultItem): void
}>()

const { t } = useI18n()
const titleId = useId()

const dialogRef = ref<HTMLDialogElement | null>(null)
const bodyRef = ref<HTMLElement | null>(null)
const carouselRef = ref<InstanceType<typeof ItemImageCarousel> | null>(null)

const copyState = ref<'idle' | 'copied' | 'failed'>('idle')
const copyAnnouncement = ref('')
let lastCopyMessage = ''
let copyResetTimer: ReturnType<typeof setTimeout> | null = null
let pointerDownOutside = false

const supportsClosedBy =
  typeof HTMLDialogElement !== 'undefined' && 'closedBy' in HTMLDialogElement.prototype

const isMobile = computed(() => isMobileDevice())

const info = computed(() => props.item?.商品信息 ?? null)
const seller = computed(() => props.item?.卖家信息 ?? null)
const ai = computed(() => props.item?.ai_analysis ?? null)
const priceInsight = computed(() => props.item?.price_insight ?? null)

const links = computed(() =>
  buildGoofishLinks({
    itemId: info.value?.商品ID,
    url: info.value?.商品链接,
  })
)

const galleryImages = computed(() => {
  const list = info.value?.商品图片列表 ?? []
  const main = info.value?.商品主图链接
  return main ? [...list, main] : [...list]
})

const isSold = computed(() => props.item?._status === 'sold' || props.item?._is_sold === true)
const isExpired = computed(() => props.item?._status === 'expired')
const isHidden = computed(() => props.item?._effective_hidden === true || props.item?._status === 'hidden')
const isRuleHidden = computed(() => props.item?._hidden_reason === 'rule')
const canToggleBlock = computed(
  () => props.item?._hidden_reason !== 'rule' && props.item?._hidden_reason !== 'expired'
)

const currentPrice = computed(() => {
  if (priceInsight.value?.current_price != null) {
    return `¥${formatNumber(priceInsight.value.current_price, { maximumFractionDigits: 2 })}`
  }
  return info.value?.当前售价 ?? ''
})

const originalPrice = computed(() => {
  const value = info.value?.商品原价?.trim()
  return value && /\d/.test(value) ? value : null
})

const descriptionText = computed(() => info.value?.商品描述?.trim() ?? '')

const matchScore = computed(() => ai.value?.value_score ?? 0)
const recommendationMeta = computed(() => {
  if (ai.value?.is_recommended === true) {
    return {
      label: t('results.card.strongRecommend'),
      icon: CheckCircle2,
      bar: 'bg-emerald-500',
      text: 'text-emerald-700',
      bg: 'bg-emerald-50/90 border-emerald-200/80',
    }
  }
  if (ai.value?.is_recommended === false) {
    return {
      label: t('results.card.notRecommended'),
      icon: XCircle,
      bar: 'bg-rose-500',
      text: 'text-rose-700',
      bg: 'bg-rose-50/90 border-rose-200/80',
    }
  }
  return {
    label: t('results.card.pending'),
    icon: AlertCircle,
    bar: 'bg-amber-500',
    text: 'text-amber-700',
    bg: 'bg-amber-50/90 border-amber-200/80',
  }
})

const riskTags = computed(() =>
  (ai.value?.risk_tags ?? []).map((tag) => String(tag).trim()).filter(Boolean)
)

const matchedKeywords = computed(() =>
  (ai.value?.matched_keywords ?? []).map((kw) => String(kw).trim()).filter(Boolean)
)

const productTags = computed(() =>
  (info.value?.商品标签 ?? []).map((tag) => String(tag).trim()).filter(Boolean)
)

const criteriaEntries = computed(() => {
  const criteria = ai.value?.criteria_analysis
  if (!criteria || typeof criteria !== 'object') return []
  return Object.entries(criteria)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value) : String(value),
    }))
})

const sellerStats = computed(() => {
  const s = seller.value
  const entries: Array<{ label: string; value: string }> = []
  if (!s) return entries

  const pushIfPresent = (label: string, raw?: string | number | null) => {
    if (raw === null || raw === undefined) return
    const text = String(raw).trim()
    if (text) entries.push({ label, value: text })
  }

  pushIfPresent(t('results.detail.sellerCredit'), s.卖家信用等级 || s.卖家芝麻信用)
  pushIfPresent(t('results.detail.sellerZhima'), s.卖家信用等级 && s.卖家芝麻信用 && s.卖家芝麻信用 !== s.卖家信用等级 ? s.卖家芝麻信用 : undefined)
  pushIfPresent(t('results.detail.sellerRegDuration'), s.卖家注册时长)
  pushIfPresent(t('results.detail.sellerPositiveRate'), s.作为卖家的好评率)
  pushIfPresent(t('results.detail.sellerPositiveCount'), s.作为卖家的好评数)
  pushIfPresent(t('results.detail.sellerTotalReviews'), s.卖家收到的评价总数)
  pushIfPresent(t('results.detail.sellerListingCount'), s['卖家在售/已售商品数'])
  pushIfPresent(t('results.detail.shippingArea'), info.value?.发货地区)
  pushIfPresent(t('results.detail.buyerCredit'), s.买家信用等级)

  return entries
})

function formatDisplayTime(value?: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return formatDateTime(date, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

const shortDate = (value: string) => formatDateTime(value, { month: '2-digit', day: '2-digit' })
const money = (price: number) => `¥${formatNumber(price, { maximumFractionDigits: 2 })}`

const historyPoints = computed(() => priceInsight.value?.price_history ?? [])
const latestDrop = computed(() => priceInsight.value?.latest_price_drop ?? null)

const chartPlot = computed(() => {
  const history = historyPoints.value
  if (!history.length) return []
  const prices = history.map((point) => point.price)
  const times = history.map((point) => new Date(point.observed_at).getTime())
  const firstTime = times[0]!
  const duration = times[times.length - 1]! - firstTime
  const minimum = Math.min(...prices)
  const maximum = Math.max(...prices)
  return history.map((point, index) => ({
    ...point,
    x: duration ? 14 + ((times[index]! - firstTime) / duration) * 280 : 154,
    y: maximum === minimum ? 62 : 108 - ((point.price - minimum) / (maximum - minimum)) * 92,
  }))
})

const chartPath = computed(() =>
  chartPlot.value
    .map((point, index) => (index === 0 ? `M ${point.x} ${point.y}` : `H ${point.x} V ${point.y}`))
    .join(' ')
)

const historyRows = computed(() =>
  historyPoints.value
    .map((point, index) => ({
      ...point,
      change:
        index > 0
          ? Math.round((point.price - historyPoints.value[index - 1]!.price) * 100) / 100
          : null,
    }))
    .reverse()
)

function closeDialog() {
  if (dialogRef.value?.open) {
    dialogRef.value.close()
  } else if (props.open) {
    emit('update:open', false)
  }
}

function handleNativeCancel(event: Event) {
  if (carouselRef.value?.isLightboxOpen) {
    event.preventDefault()
    carouselRef.value.closeLightbox()
  }
}

function handleNativeClose() {
  if (dialogRef.value) {
    dialogRef.value.returnValue = ''
  }
  carouselRef.value?.closeLightbox()
  pointerDownOutside = false
  if (props.open) {
    emit('update:open', false)
  }
}

function isPointOutsideDialog(event: PointerEvent): boolean {
  const dialog = dialogRef.value
  if (!dialog) return false
  const rect = dialog.getBoundingClientRect()
  return (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  )
}

function handleDialogPointerDown(event: PointerEvent) {
  if (supportsClosedBy || carouselRef.value?.isLightboxOpen) {
    pointerDownOutside = false
    return
  }
  pointerDownOutside = isPointOutsideDialog(event)
}

function handleDialogPointerUp(event: PointerEvent) {
  if (supportsClosedBy || carouselRef.value?.isLightboxOpen) {
    pointerDownOutside = false
    return
  }
  const shouldClose = pointerDownOutside && isPointOutsideDialog(event)
  pointerDownOutside = false
  if (shouldClose) {
    closeDialog()
  }
}

function handleLaunchGoofishApp() {
  openGoofishListing(links.value, { preferApp: true })
}

async function handleCopyLink() {
  const targetUrl = links.value.webUrl
  if (!targetUrl) return

  if (copyResetTimer !== null) {
    clearTimeout(copyResetTimer)
    copyResetTimer = null
  }

  const ok = await copyTextToClipboard(targetUrl, dialogRef.value)
  copyState.value = ok ? 'copied' : 'failed'

  const baseMessage = ok ? t('results.detail.linkCopied') : t('results.detail.copyFailed')
  const nextMessage = baseMessage === lastCopyMessage ? `${baseMessage}\u00A0` : baseMessage
  lastCopyMessage = nextMessage
  copyAnnouncement.value = nextMessage

  copyResetTimer = setTimeout(() => {
    copyState.value = 'idle'
    copyAnnouncement.value = ''
    copyResetTimer = null
  }, 2200)
}

watch(
  [() => props.open, () => props.item?.商品信息?.商品ID],
  async ([isOpen, itemId], [, prevItemId]) => {
    const dialog = dialogRef.value
    if (!dialog) return

    if (isOpen && props.item) {
      await nextTick()
      if (!dialog.open) {
        dialog.showModal()
      }
      if (itemId !== prevItemId) {
        copyState.value = 'idle'
        copyAnnouncement.value = ''
        bodyRef.value?.scrollTo({ top: 0 })
      }
    } else if (dialog.open) {
      dialog.close()
    }
  }
)

onBeforeUnmount(() => {
  if (copyResetTimer !== null) {
    clearTimeout(copyResetTimer)
    copyResetTimer = null
  }
  if (dialogRef.value?.open) {
    dialogRef.value.close()
  }
})
</script>

<template>
  <dialog
    ref="dialogRef"
    class="item-detail-dialog"
    v-bind="({ closedby: 'any' } as any)"
    :aria-labelledby="titleId"
    @cancel="handleNativeCancel"
    @close="handleNativeClose"
    @pointerdown="handleDialogPointerDown"
    @pointerup="handleDialogPointerUp"
  >
    <div
      v-if="props.item && info"
      class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white text-slate-900 shadow-2xl"
    >
      <header class="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200/80 bg-slate-50/90 px-4 py-3 sm:px-6">
        <div class="flex flex-wrap items-center gap-2 min-w-0">
          <Badge
            v-if="isSold"
            variant="secondary"
            class="border-none bg-slate-800 text-white"
          >
            {{ t('results.card.soldStamp') }}
          </Badge>
          <Badge
            v-else-if="isExpired"
            variant="secondary"
            class="border-none bg-amber-600 text-white"
          >
            {{ t('results.card.expired') }}
          </Badge>
          <Badge
            v-else-if="ai?.is_recommended === true && !isHidden"
            variant="default"
            class="border-none bg-emerald-600 text-white"
          >
            {{ t('results.card.curated') }}
          </Badge>
          <Badge
            v-if="isRuleHidden"
            variant="secondary"
            class="border-none bg-slate-900 text-white"
          >
            {{ t('results.card.blacklisted') }}
          </Badge>
          <Badge
            v-else-if="isHidden"
            variant="secondary"
            class="border-none bg-slate-700 text-white"
          >
            {{ t('results.card.hidden') }}
          </Badge>
          <span class="truncate text-xs font-mono text-slate-500">
            ID: {{ info.商品ID }}
          </span>
        </div>

        <button
          type="button"
          class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition-all hover:bg-slate-100 hover:text-slate-900 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          :aria-label="t('common.close')"
          @click="closeDialog"
        >
          <X class="h-4 w-4" aria-hidden="true" />
        </button>
      </header>

      <div
        ref="bodyRef"
        class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-6 sm:py-5"
      >
        <div class="grid gap-6 lg:grid-cols-[minmax(0,1.02fr)_minmax(0,1fr)]">
          <div class="space-y-5 min-w-0">
            <ItemImageCarousel
              ref="carouselRef"
              :images="galleryImages"
              :title="info.商品标题"
              :is-sold="isSold"
              :reset-key="info.商品ID"
            />

            <section
              v-if="priceInsight && (historyPoints.length > 0 || priceInsight.observation_count > 0)"
              class="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4"
            >
              <div class="mb-3 flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <History class="h-4 w-4 text-slate-600" aria-hidden="true" />
                  <h2 class="text-sm font-semibold text-slate-900">{{ t('results.card.priceHistory') }}</h2>
                </div>
                <span class="text-xs text-slate-500">
                  {{ t('results.card.priceObservations', { count: historyPoints.length || priceInsight.observation_count }) }}
                </span>
              </div>

              <div class="mb-3 grid grid-cols-3 gap-2">
                <div class="rounded-xl border border-slate-200/70 bg-white px-3 py-2">
                  <div class="text-[11px] text-slate-500">{{ t('results.card.marketAvg') }}</div>
                  <div class="mt-0.5 text-sm font-bold tabular-nums text-slate-800">
                    {{ priceInsight.market_avg_price != null ? money(priceInsight.market_avg_price) : '—' }}
                  </div>
                </div>
                <div class="rounded-xl border border-slate-200/70 bg-white px-3 py-2">
                  <div class="text-[11px] text-slate-500">{{ t('results.card.historicalLow') }}</div>
                  <div class="mt-0.5 text-sm font-bold tabular-nums text-emerald-700">
                    {{ priceInsight.min_price != null ? money(priceInsight.min_price) : '—' }}
                  </div>
                </div>
                <div class="rounded-xl border border-slate-200/70 bg-white px-3 py-2">
                  <div class="text-[11px] text-slate-500">{{ t('results.card.historicalHigh') }}</div>
                  <div class="mt-0.5 text-sm font-bold tabular-nums text-slate-800">
                    {{ priceInsight.max_price != null ? money(priceInsight.max_price) : '—' }}
                  </div>
                </div>
              </div>

              <div
                v-if="latestDrop"
                class="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200/80 bg-emerald-50 px-3 py-2 text-xs text-emerald-800"
              >
                <span class="inline-flex items-center gap-1.5 font-semibold">
                  <TrendingDown class="h-3.5 w-3.5" aria-hidden="true" />
                  {{ t('results.card.latestPriceDrop', { amount: money(latestDrop.from_price - latestDrop.to_price) }) }}
                </span>
                <span class="tabular-nums">
                  {{ money(latestDrop.from_price) }} → {{ money(latestDrop.to_price) }}
                </span>
              </div>

              <template v-if="historyPoints.length > 0">
                <svg
                  viewBox="0 0 308 124"
                  class="my-1 w-full text-emerald-600"
                  role="img"
                  :aria-label="t('results.card.priceHistory')"
                >
                  <path
                    d="M 14 16 H 294 M 14 62 H 294 M 14 108 H 294"
                    stroke="#e2e8f0"
                    stroke-dasharray="3 4"
                    fill="none"
                  />
                  <path
                    :d="chartPath"
                    stroke="currentColor"
                    stroke-width="2"
                    fill="none"
                    stroke-linejoin="round"
                  />
                  <circle
                    v-for="(point, index) in chartPlot"
                    :key="index"
                    :cx="point.x"
                    :cy="point.y"
                    r="3.2"
                    fill="currentColor"
                    stroke="white"
                    stroke-width="1.2"
                  >
                    <title>{{ formatDisplayTime(point.observed_at) }} · {{ money(point.price) }}</title>
                  </circle>
                </svg>

                <div class="mb-2.5 flex justify-between text-[11px] text-slate-400">
                  <span>{{ shortDate(historyPoints[0]!.observed_at) }}</span>
                  <span>{{ shortDate(historyPoints[historyPoints.length - 1]!.observed_at) }}</span>
                </div>

                <p v-if="historyPoints.length === 1" class="mb-2.5 text-xs text-slate-500">
                  {{ t('results.card.singlePriceObservation') }}
                </p>

                <div class="max-h-36 overflow-y-auto rounded-xl border border-slate-200/80 bg-white">
                  <table class="w-full text-xs tabular-nums">
                    <thead class="sticky top-0 bg-slate-50 text-slate-500">
                      <tr>
                        <th class="px-2.5 py-2 text-left font-medium">{{ t('results.card.observedAt') }}</th>
                        <th class="px-2.5 py-2 text-right font-medium">{{ t('results.card.observedPrice') }}</th>
                        <th class="px-2.5 py-2 text-right font-medium">{{ t('results.card.priceChange') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(point, index) in historyRows"
                        :key="index"
                        class="border-t border-slate-100"
                      >
                        <td class="whitespace-nowrap px-2.5 py-1.5 text-slate-600">
                          {{ formatDisplayTime(point.observed_at) }}
                        </td>
                        <td class="px-2.5 py-1.5 text-right font-semibold text-slate-800">
                          {{ money(point.price) }}
                        </td>
                        <td
                          class="whitespace-nowrap px-2.5 py-1.5 text-right font-medium"
                          :class="
                            point.change !== null && point.change < 0
                              ? 'text-emerald-600'
                              : point.change !== null && point.change > 0
                                ? 'text-rose-600'
                                : 'text-slate-400'
                          "
                        >
                          {{
                            point.change
                              ? `${point.change > 0 ? '+' : '−'}${money(Math.abs(point.change))}`
                              : '—'
                          }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>

              <p class="mt-2.5 text-[11px] leading-relaxed text-slate-400">
                {{ t('results.card.priceHistoryNote') }}
              </p>
            </section>
          </div>

          <div class="space-y-5 min-w-0">
            <div class="space-y-3">
              <h1
                :id="titleId"
                class="text-lg sm:text-xl font-bold leading-snug text-slate-900 break-words"
              >
                {{ info.商品标题 }}
              </h1>

              <div class="flex flex-wrap items-baseline gap-2.5">
                <span class="text-3xl font-extrabold tracking-tight text-rose-600 tabular-nums">
                  {{ currentPrice }}
                </span>
                <span v-if="originalPrice" class="text-sm text-slate-400 line-through tabular-nums">
                  {{ originalPrice }}
                </span>
                <span
                  v-if="priceInsight?.deal_label"
                  class="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800"
                >
                  {{ priceInsight.deal_label }}
                </span>
              </div>

              <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-500">
                <span v-if="info['“想要”人数']" class="inline-flex items-center gap-1">
                  <Sparkles class="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
                  {{ t('results.detail.wantedCount', { count: info['“想要”人数'] }) }}
                </span>
                <span v-if="info.浏览量" class="inline-flex items-center gap-1">
                  <Eye class="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                  {{ t('results.detail.viewCount', { count: info.浏览量 }) }}
                </span>
                <span v-if="info.发货地区" class="inline-flex items-center gap-1">
                  <MapPin class="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                  {{ info.发货地区 }}
                </span>
                <span v-if="info.发布时间" class="inline-flex items-center gap-1">
                  <Clock class="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                  {{ t('results.card.publishedAt') }}：{{ formatDisplayTime(info.发布时间) }}
                </span>
                <span v-if="props.item.爬取时间" class="inline-flex items-center gap-1">
                  <Clock class="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                  {{ t('results.detail.crawledAt') }}：{{ formatDisplayTime(props.item.爬取时间) }}
                </span>
              </div>

              <div
                v-if="info.商品状态 || info.状态检查时间"
                class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200/80 bg-slate-50 px-3 py-2 text-xs text-slate-600"
              >
                <ShieldCheck class="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
                <span v-if="info.商品状态" class="font-semibold text-slate-800">
                  {{ t('results.detail.liveStatusLabel') }}：{{ info.商品状态 }}
                </span>
                <span v-if="info.状态检查时间" class="text-slate-500">
                  ({{ t('results.detail.checkedAt') }} {{ formatDisplayTime(info.状态检查时间) }})
                </span>
              </div>

              <div v-if="productTags.length > 0" class="flex flex-wrap gap-1.5">
                <span
                  v-for="tag in productTags"
                  :key="tag"
                  class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100/80 px-2.5 py-0.5 text-xs text-slate-700"
                >
                  <Tag class="h-3 w-3 text-slate-400" aria-hidden="true" />
                  {{ tag }}
                </span>
              </div>
            </div>

            <section class="rounded-2xl border border-slate-200/80 bg-white p-4">
              <div class="mb-2.5 flex items-center justify-between gap-2">
                <h2 class="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
                  <FileText class="h-4 w-4 text-slate-500" aria-hidden="true" />
                  {{ t('results.detail.descriptionTitle') }}
                </h2>
              </div>

              <p
                v-if="descriptionText"
                class="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-700"
              >
                {{ descriptionText }}
              </p>

              <div
                v-else
                class="rounded-xl border border-dashed border-slate-200 bg-slate-50/80 p-3.5 text-xs text-slate-500"
              >
                <p class="leading-relaxed">
                  {{ t('results.detail.descriptionEmptyHint') }}
                </p>
                <button
                  type="button"
                  :disabled="props.isCheckingStatus"
                  class="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-all hover:bg-primary/15 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                  @click="emit('check-status', props.item)"
                >
                  <Loader2 v-if="props.isCheckingStatus" class="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  <RefreshCw v-else class="h-3.5 w-3.5" aria-hidden="true" />
                  <span>
                    {{ props.isCheckingStatus ? t('results.detail.syncingStatus') : t('results.detail.syncDescriptionAction') }}
                  </span>
                </button>
              </div>
            </section>

            <section
              class="rounded-2xl border p-4"
              :class="recommendationMeta.bg"
            >
              <div class="mb-2.5 flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <component :is="recommendationMeta.icon" class="h-4 w-4" :class="recommendationMeta.text" aria-hidden="true" />
                  <h2 class="text-sm font-bold" :class="recommendationMeta.text">
                    {{ recommendationMeta.label }}
                  </h2>
                  <span
                    v-if="ai?.analysis_source"
                    class="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600"
                  >
                    {{ ai.analysis_source === 'keyword' ? t('common.keyword') : t('common.ai') }}
                  </span>
                </div>
                <div class="flex items-center gap-1.5">
                  <span class="text-[11px] font-medium uppercase tracking-wider text-slate-500">AI Match</span>
                  <span class="text-base font-black tabular-nums" :class="recommendationMeta.text">
                    {{ matchScore }}%
                  </span>
                </div>
              </div>

              <div class="mb-3 h-2 w-full overflow-hidden rounded-full bg-white/70">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="recommendationMeta.bar"
                  :style="{ width: `${Math.max(0, Math.min(100, matchScore))}%` }"
                />
              </div>

              <p
                v-if="ai?.value_summary && ai.value_summary !== ai.reason"
                class="mb-2 rounded-xl bg-white/70 px-3 py-2 text-xs font-medium text-slate-800"
              >
                {{ ai.value_summary }}
              </p>

              <p class="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-700">
                {{ ai?.reason || t('results.card.analyzing') }}
              </p>

              <div v-if="riskTags.length > 0" class="mt-3 pt-3 border-t border-black/5">
                <div class="mb-1.5 inline-flex items-center gap-1 text-xs font-semibold text-rose-700">
                  <AlertTriangle class="h-3.5 w-3.5" aria-hidden="true" />
                  {{ t('results.detail.riskTags') }}
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="risk in riskTags"
                    :key="risk"
                    class="rounded-full border border-rose-200 bg-rose-100/90 px-2.5 py-0.5 text-xs font-medium text-rose-800"
                  >
                    {{ risk }}
                  </span>
                </div>
              </div>

              <div v-if="matchedKeywords.length > 0" class="mt-3 pt-3 border-t border-black/5">
                <div class="mb-1.5 text-xs font-semibold text-slate-600">
                  {{ t('results.detail.matchedKeywords') }}
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="keyword in matchedKeywords"
                    :key="keyword"
                    class="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-xs font-medium text-sky-800"
                  >
                    {{ keyword }}
                  </span>
                </div>
              </div>

              <div v-if="criteriaEntries.length > 0" class="mt-3 pt-3 border-t border-black/5">
                <div class="mb-1.5 text-xs font-semibold text-slate-600">
                  {{ t('results.detail.criteriaAnalysis') }}
                </div>
                <dl class="space-y-1.5 text-xs">
                  <div
                    v-for="entry in criteriaEntries"
                    :key="entry.key"
                    class="rounded-lg bg-white/70 px-2.5 py-1.5"
                  >
                    <dt class="font-semibold text-slate-700">{{ entry.key }}</dt>
                    <dd class="mt-0.5 break-words text-slate-600">{{ entry.value }}</dd>
                  </div>
                </dl>
              </div>
            </section>

            <section class="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4">
              <div class="flex items-center gap-3">
                <img
                  v-if="seller?.卖家头像链接"
                  :src="seller.卖家头像链接"
                  :alt="seller.卖家昵称 || info.卖家昵称 || t('results.card.anonymous')"
                  class="h-11 w-11 shrink-0 rounded-full border border-slate-200 object-cover"
                  loading="lazy"
                />
                <div
                  v-else
                  class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500"
                >
                  <User class="h-5 w-5" aria-hidden="true" />
                </div>
                <div class="min-w-0 flex-1">
                  <h2 class="truncate text-sm font-bold text-slate-900">
                    {{ seller?.卖家昵称 || info.卖家昵称 || t('results.card.anonymous') }}
                  </h2>
                  <p v-if="seller?.卖家个性签名" class="mt-0.5 line-clamp-2 text-xs text-slate-500">
                    {{ seller.卖家个性签名 }}
                  </p>
                  <p v-else class="mt-0.5 text-xs text-slate-400">
                    {{ t('results.detail.sellerProfile') }}
                  </p>
                </div>
              </div>

              <dl
                v-if="sellerStats.length > 0"
                class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3"
              >
                <div
                  v-for="stat in sellerStats"
                  :key="stat.label"
                  class="rounded-xl border border-slate-200/70 bg-white px-2.5 py-2"
                >
                  <dt class="text-[11px] text-slate-500">{{ stat.label }}</dt>
                  <dd class="mt-0.5 truncate text-xs font-semibold text-slate-800" :title="stat.value">
                    {{ stat.value }}
                  </dd>
                </div>
              </dl>
            </section>
          </div>
        </div>
      </div>

      <footer class="shrink-0 border-t border-slate-200/90 bg-white/95 px-4 py-3 backdrop-blur-sm sm:px-6">
        <div class="flex flex-wrap items-center justify-between gap-2.5">
          <div class="flex flex-wrap items-center gap-2">
            <template v-if="isMobile && links.appSchemeUrl">
              <button
                type="button"
                class="action-btn-primary"
                @click="handleLaunchGoofishApp"
              >
                <Smartphone class="h-4 w-4" aria-hidden="true" />
                <span>{{ t('results.detail.openInApp') }}</span>
              </button>
              <a
                v-if="links.webUrl"
                :href="links.webUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="action-btn-secondary"
              >
                <ExternalLink class="h-4 w-4" aria-hidden="true" />
                <span>{{ t('results.detail.openWebFallback') }}</span>
              </a>
            </template>

            <a
              v-else-if="links.webUrl"
              :href="links.webUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="action-btn-primary"
            >
              <ExternalLink class="h-4 w-4" aria-hidden="true" />
              <span>{{ t('results.detail.openOnGoofish') }}</span>
            </a>

            <div v-if="links.webUrl" class="relative inline-flex items-center">
              <button
                type="button"
                class="action-btn-secondary"
                @click="handleCopyLink"
              >
                <Check v-if="copyState === 'copied'" class="h-4 w-4 text-emerald-600" aria-hidden="true" />
                <Copy v-else class="h-4 w-4" aria-hidden="true" />
                <span>
                  {{ copyState === 'copied' ? t('results.detail.copiedShort') : t('results.detail.copyLink') }}
                </span>
              </button>
              <span
                role="status"
                aria-live="polite"
                class="pointer-events-none absolute -top-10 left-0 sm:left-1/2 sm:-translate-x-1/2 whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-medium shadow-md transition-opacity duration-200"
                :class="[
                  copyState === 'idle' ? 'opacity-0' : 'opacity-100',
                  copyState === 'failed' ? 'bg-rose-600 text-white' : 'bg-slate-900 text-white',
                ]"
              >
                {{ copyAnnouncement }}
              </span>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button
              type="button"
              :disabled="props.isCheckingStatus"
              class="action-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
              @click="emit('check-status', props.item)"
            >
              <Loader2 v-if="props.isCheckingStatus" class="h-4 w-4 animate-spin" aria-hidden="true" />
              <RefreshCw v-else class="h-4 w-4" aria-hidden="true" />
              <span>
                {{ props.isCheckingStatus ? t('results.detail.checkingStatus') : t('results.detail.checkLiveStatus') }}
              </span>
            </button>

            <button
              type="button"
              class="action-btn-secondary"
              :class="isSold ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : ''"
              @click="emit('toggle-sold', props.item)"
            >
              <RotateCcw v-if="isSold" class="h-4 w-4" aria-hidden="true" />
              <ShoppingBag v-else class="h-4 w-4" aria-hidden="true" />
              <span>{{ isSold ? t('results.detail.markActive') : t('results.detail.markSold') }}</span>
            </button>

            <button
              v-if="canToggleBlock"
              type="button"
              class="action-btn-secondary"
              :class="isHidden ? '' : 'hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700'"
              @click="emit('toggle-block', props.item)"
            >
              <Eye v-if="isHidden" class="h-4 w-4" aria-hidden="true" />
              <EyeOff v-else class="h-4 w-4" aria-hidden="true" />
              <span>{{ isHidden ? t('results.card.unblock') : t('results.card.block') }}</span>
            </button>
          </div>
        </div>
      </footer>
    </div>
  </dialog>
</template>

<style scoped>
/* Never set display unconditionally on <dialog>; scope flex layout strictly to [open]. */
.item-detail-dialog {
  width: min(960px, calc(100vw - 1rem));
  max-width: min(960px, calc(100vw - 1rem));
  max-height: calc(100dvh - 1rem);
  margin: auto;
  padding: 0;
  border: 0;
  background: transparent;
  overflow: visible;
}

@media (min-width: 640px) {
  .item-detail-dialog {
    width: min(960px, calc(100vw - 2.5rem));
    max-width: min(960px, calc(100vw - 2.5rem));
    max-height: calc(100dvh - 3rem);
  }
}

.item-detail-dialog[open] {
  display: flex;
  flex-direction: column;
}

.item-detail-dialog:modal {
  overscroll-behavior: contain;
}

.item-detail-dialog::backdrop {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(4px);
  overflow: hidden;
  overscroll-behavior: contain;
}

.action-btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 2.375rem;
  padding: 0.5rem 0.95rem;
  border-radius: 0.75rem;
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  font-size: 0.8125rem;
  font-weight: 600;
  touch-action: manipulation;
  transition: background-color 150ms ease, transform 120ms ease, box-shadow 150ms ease;
}

.action-btn-primary:hover {
  filter: brightness(0.95);
}

.action-btn-primary:active {
  transform: scale(0.97);
}

.action-btn-primary:focus-visible {
  outline: 2px solid hsl(var(--primary));
  outline-offset: 2px;
}

.action-btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 2.375rem;
  padding: 0.5rem 0.85rem;
  border-radius: 0.75rem;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #1e293b;
  font-size: 0.8125rem;
  font-weight: 600;
  touch-action: manipulation;
  transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease, transform 120ms ease;
}

.action-btn-secondary:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #94a3b8;
}

.action-btn-secondary:active:not(:disabled) {
  transform: scale(0.97);
}

.action-btn-secondary:focus-visible {
  outline: 2px solid hsl(var(--primary));
  outline-offset: 2px;
}
</style>
