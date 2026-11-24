<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResultItem } from '@/types/result.d.ts'
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import Badge from '@/components/ui/badge/Badge.vue'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  Eye,
  EyeOff,
  Images,
  Info,
  RotateCcw,
  ShoppingBag,
  TrendingDown,
  TrendingUp,
  User,
  XCircle,
} from 'lucide-vue-next'
import { formatDateTime, formatNumber } from '@/i18n'
import { buildGoofishLinks, isMobileDevice, openGoofishListing } from '@/lib/goofishLink'

interface Props {
  item: ResultItem
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'open-detail', item: ResultItem): void
  (e: 'toggle-block', item: ResultItem): void
  (e: 'toggle-sold', item: ResultItem): void
}>()
const { t } = useI18n()

const info = computed(() => props.item.商品信息)
const seller = computed(() => props.item.卖家信息)
const ai = computed(() => props.item.ai_analysis)
const priceInsight = computed(() => props.item.price_insight)

const links = computed(() =>
  buildGoofishLinks({
    itemId: info.value.商品ID,
    url: info.value.商品链接,
  })
)

const currentPrice = computed(() =>
  priceInsight.value?.current_price != null
    ? `¥${formatNumber(priceInsight.value.current_price, { maximumFractionDigits: 2 })}`
    : info.value.当前售价
)

const originalPrice = computed(() => {
  const value = info.value.商品原价?.trim()
  return value && /\d/.test(value) ? value : null
})

const isRecommended = computed(() => ai.value?.is_recommended === true)
const recommendationStatus = computed(() => {
  if (ai.value?.is_recommended === true) {
    return {
      label: t('results.card.strongRecommend'),
      color: 'bg-emerald-500',
      icon: CheckCircle2,
      text: 'text-emerald-600',
      bg: 'bg-emerald-50',
    }
  }
  if (ai.value?.is_recommended === false) {
    return {
      label: t('results.card.notRecommended'),
      color: 'bg-rose-500',
      icon: XCircle,
      text: 'text-rose-600',
      bg: 'bg-rose-50',
    }
  }
  return {
    label: t('results.card.pending'),
    color: 'bg-amber-500',
    icon: AlertCircle,
    text: 'text-amber-600',
    bg: 'bg-amber-50',
  }
})

const imageList = computed(() => {
  const rawList = info.value.商品图片列表 ?? []
  const main = info.value.商品主图链接
  const seen = new Set<string>()
  const unique: string[] = []
  for (const candidate of main ? [...rawList, main] : rawList) {
    const trimmed = typeof candidate === 'string' ? candidate.trim() : ''
    if (trimmed && !seen.has(trimmed)) {
      seen.add(trimmed)
      unique.push(trimmed)
    }
  }
  return unique
})

const imageUrl = computed(() => imageList.value[0] || '')
const imageCount = computed(() => imageList.value.length)

const crawlTime = computed(() =>
  props.item.爬取时间
    ? formatDateTime(props.item.爬取时间, {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : t('common.unknown')
)

const matchScore = computed(() => ai.value?.value_score ?? 0)
const isSold = computed(() => props.item._status === 'sold' || props.item._is_sold === true)
const isExpired = computed(() => props.item._status === 'expired')
const isHidden = computed(() => props.item._effective_hidden === true || props.item._status === 'hidden')
const isRuleHidden = computed(() => props.item._hidden_reason === 'rule')
const canToggleBlock = computed(
  () => props.item._hidden_reason !== 'rule' && props.item._hidden_reason !== 'expired'
)
const hiddenLabel = computed(() => {
  if (props.item._hidden_reason === 'rule') return t('results.card.blacklisted')
  if (props.item._hidden_reason === 'expired') return t('results.card.expired')
  return t('results.card.hidden')
})

const shouldShowTitlePreview = computed(() => (info.value.商品标题?.trim().length ?? 0) > 24)
const expanded = ref(false)

function handleOpenDetail() {
  emit('open-detail', props.item)
}

function handleOpenExternal(event: MouseEvent) {
  if (isMobileDevice() && links.value.appSchemeUrl) {
    event.preventDefault()
    openGoofishListing(links.value, { preferApp: true })
  }
}
</script>

<template>
  <Card
    class="result-card-root group flex flex-col h-full border-none shadow-glass hover:shadow-card-hover transition-all duration-300 rounded-2xl overflow-hidden bg-white/80 backdrop-blur-sm"
    :class="{
      'opacity-50': isHidden,
      'bg-slate-50/75 opacity-80 hover:opacity-95': !isHidden && isSold,
    }"
  >
    <div class="relative aspect-[4/3] overflow-hidden bg-slate-100">
      <button
        type="button"
        class="relative block h-full w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        :aria-label="t('results.card.openDetailAria', { title: info.商品标题 })"
        @click="handleOpenDetail"
      >
        <div class="absolute inset-0 bg-slate-200 animate-pulse" v-if="!imageUrl"></div>
        <img
          v-else
          :src="imageUrl"
          :alt="info.商品标题"
          class="w-full h-full object-cover transition-transform duration-500"
          :class="isSold ? 'grayscale contrast-90 brightness-90 group-hover:scale-105' : 'group-hover:scale-110'"
          loading="lazy"
        />

        <div
          v-if="isSold && !isHidden"
          class="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-950/45"
        >
          <div class="-rotate-12 flex h-20 w-20 items-center justify-center rounded-full border-2 border-white/85 bg-slate-900/75 p-1 shadow-lg backdrop-blur-[2px]">
            <div class="flex h-full w-full items-center justify-center rounded-full border border-dashed border-white/65">
              <span class="text-xs font-extrabold tracking-[0.18em] text-white">
                {{ t('results.card.soldStamp') }}
              </span>
            </div>
          </div>
        </div>

        <div v-else-if="isHidden" class="pointer-events-none absolute inset-0 bg-black/35 flex items-center justify-center">
          <span class="rounded-full bg-slate-900/70 px-3 py-1 text-white/90 text-xs font-semibold uppercase tracking-wider">
            {{ hiddenLabel }}
          </span>
        </div>

        <div v-else-if="isExpired" class="pointer-events-none absolute inset-0 bg-slate-950/35 flex items-center justify-center">
          <span class="rounded-full border border-white/40 bg-slate-900/75 px-3 py-1 text-xs font-bold tracking-wider text-white">
            {{ t('results.card.expired') }}
          </span>
        </div>

        <div class="pointer-events-none absolute top-3 left-3 flex gap-2">
          <Badge
            v-if="isRecommended && !isHidden && !isSold"
            variant="default"
            class="bg-emerald-500/90 backdrop-blur-md border-none shadow-sm"
          >
            {{ t('results.card.curated') }}
          </Badge>
          <Badge
            v-if="isRuleHidden"
            variant="secondary"
            class="bg-slate-900/75 text-white border-none backdrop-blur-md shadow-sm"
          >
            {{ t('results.card.blacklisted') }}
          </Badge>
        </div>

        <div
          v-if="imageCount > 1"
          class="pointer-events-none absolute right-2.5 bottom-2.5 inline-flex items-center gap-1 rounded-full bg-slate-900/75 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-white shadow-sm backdrop-blur-sm"
        >
          <Images class="h-3 w-3" aria-hidden="true" />
          <span>1/{{ imageCount }}</span>
        </div>
      </button>

      <div class="card-quick-actions absolute top-3 right-3 z-10 flex gap-1.5">
        <button
          type="button"
          @click.stop="emit('toggle-sold', props.item)"
          :aria-label="isSold ? t('results.card.markActive') : t('results.card.markSold')"
          :title="isSold ? t('results.card.markActive') : t('results.card.markSold')"
          class="card-quick-btn"
        >
          <RotateCcw v-if="isSold" class="w-4 h-4" aria-hidden="true" />
          <ShoppingBag v-else class="w-4 h-4" aria-hidden="true" />
        </button>

        <button
          v-if="canToggleBlock"
          type="button"
          @click.stop="emit('toggle-block', props.item)"
          :aria-label="isHidden ? t('results.card.unblock') : t('results.card.block')"
          :title="isHidden ? t('results.card.unblock') : t('results.card.block')"
          class="card-quick-btn"
        >
          <EyeOff v-if="!isHidden" class="w-4 h-4" aria-hidden="true" />
          <Eye v-else class="w-4 h-4" aria-hidden="true" />
        </button>

        <a
          v-if="links.webUrl"
          :href="links.webUrl"
          target="_blank"
          rel="noopener noreferrer"
          :aria-label="t('results.card.detail')"
          :title="t('results.card.detail')"
          class="card-quick-btn"
          @click.stop="handleOpenExternal"
        >
          <ExternalLink class="w-4 h-4" aria-hidden="true" />
        </a>
      </div>
    </div>

    <CardHeader class="p-4 pb-2">
      <div class="relative group/title flex justify-between items-start gap-3">
        <CardTitle class="text-base font-semibold text-slate-800 leading-snug flex-grow h-10 overflow-hidden">
          <button
            type="button"
            :title="info.商品标题"
            class="block w-full text-left line-clamp-2 transition-colors hover:text-primary active:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:rounded"
            @click="handleOpenDetail"
          >
            {{ info.商品标题 }}
          </button>
        </CardTitle>

        <div
          v-if="shouldShowTitlePreview"
          aria-hidden="true"
          class="title-preview-popover pointer-events-none absolute top-full left-0 right-0 z-30 mt-1.5 rounded-xl border border-slate-700/80 bg-slate-900/95 px-3 py-2 text-xs font-medium leading-relaxed text-white shadow-xl backdrop-blur-md"
        >
          {{ info.商品标题 }}
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 mt-2">
        <span
          class="text-2xl font-bold tracking-tight"
          :class="isSold ? 'text-slate-500 line-through decoration-slate-400/80' : 'text-rose-600'"
        >
          {{ currentPrice }}
        </span>
        <span v-if="originalPrice" class="text-xs text-slate-400 line-through">{{ originalPrice }}</span>
      </div>
    </CardHeader>

    <CardContent class="p-4 pt-2 flex-grow">
      <div class="rounded-xl p-3 border border-slate-100" :class="recommendationStatus.bg">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <component :is="recommendationStatus.icon" class="w-4 h-4" :class="recommendationStatus.text" aria-hidden="true" />
            <span class="text-sm font-bold" :class="recommendationStatus.text">{{ recommendationStatus.label }}</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="text-[10px] font-medium uppercase tracking-wider text-slate-400">AI Match</span>
            <span class="text-sm font-black" :class="recommendationStatus.text">{{ matchScore }}%</span>
          </div>
        </div>

        <div class="w-full h-1.5 bg-white/50 rounded-full overflow-hidden mb-3">
          <div
            class="h-full transition-all duration-1000 ease-out rounded-full"
            :class="recommendationStatus.color"
            :style="{ width: `${matchScore}%` }"
          ></div>
        </div>

        <p class="text-xs leading-relaxed text-slate-600" :class="{ 'line-clamp-2': !expanded }">
          {{ ai?.reason || t('results.card.analyzing') }}
        </p>

        <button
          type="button"
          v-if="ai?.reason && ai.reason.length > 50"
          @click.stop="expanded = !expanded"
          class="mt-1 text-[10px] font-bold uppercase text-primary/70 hover:text-primary active:scale-95 transition-all flex items-center gap-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
        >
          {{ expanded ? t('results.card.collapse') : t('results.card.expand') }}
          <Info class="w-3 h-3" aria-hidden="true" />
        </button>
      </div>

      <div v-if="priceInsight?.observation_count" class="mt-4 grid grid-cols-2 gap-3">
        <div class="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100/50 group/stat">
          <div class="flex items-center gap-1.5 text-[10px] font-medium text-slate-400 mb-1">
            <TrendingUp class="w-3 h-3" aria-hidden="true" /> {{ t('results.card.marketAvg') }}
          </div>
          <div class="text-sm font-bold text-slate-700">
            {{ priceInsight.market_avg_price ? `¥${priceInsight.market_avg_price}` : '—' }}
          </div>
        </div>
        <div class="bg-slate-50/50 p-2.5 rounded-xl border border-slate-100/50">
          <div class="flex items-center gap-1.5 text-[10px] font-medium text-slate-400 mb-1">
            <TrendingDown class="w-3 h-3" aria-hidden="true" /> {{ t('results.card.historicalLow') }}
          </div>
          <div class="text-sm font-bold text-slate-700">
            {{ priceInsight.min_price ? `¥${priceInsight.min_price}` : '—' }}
          </div>
        </div>
      </div>
    </CardContent>

    <CardFooter class="px-4 py-3 bg-slate-50/30 border-t border-slate-100/60 flex items-center justify-between gap-2 text-[11px]">
      <div class="flex items-center gap-2.5 text-slate-400 min-w-0">
        <div class="flex items-center gap-1 min-w-0">
          <User class="w-3 h-3 shrink-0" aria-hidden="true" />
          <span class="truncate max-w-[64px]">{{ seller.卖家昵称 || info.卖家昵称 || t('results.card.anonymous') }}</span>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <Clock class="w-3 h-3" aria-hidden="true" />
          <span>{{ crawlTime }}</span>
        </div>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <button
          type="button"
          class="rounded-md px-1.5 py-0.5 font-semibold text-slate-600 transition-all hover:bg-slate-200/70 hover:text-slate-900 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
          @click.stop="handleOpenDetail"
        >
          {{ t('results.card.inAppDetail') }}
        </button>

        <a
          v-if="links.webUrl"
          :href="links.webUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-primary font-bold transition-all hover:bg-primary/10 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
          @click.stop="handleOpenExternal"
        >
          {{ t('results.card.detail') }}
          <ExternalLink class="w-3 h-3" aria-hidden="true" />
        </a>
      </div>
    </CardFooter>
  </Card>
</template>

<style scoped>
.card-quick-actions {
  opacity: 1;
  transition: opacity 150ms ease;
}

@media (hover: hover) {
  .card-quick-actions {
    opacity: 0;
  }

  .result-card-root:hover .card-quick-actions,
  .result-card-root:focus-within .card-quick-actions {
    opacity: 1;
  }
}

@media (hover: none) {
  .card-quick-actions {
    opacity: 1;
  }
}

.card-quick-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 2rem;
  width: 2rem;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(15, 23, 42, 0.68);
  color: #ffffff;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.25);
  touch-action: manipulation;
  transition: background-color 150ms ease, transform 120ms ease;
}

.card-quick-btn:hover {
  background: rgba(15, 23, 42, 0.9);
}

.card-quick-btn:active {
  transform: scale(0.92);
}

.card-quick-btn:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}

.title-preview-popover {
  display: none;
}

@media (hover: hover) {
  .title-preview-popover {
    display: block;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 160ms ease, transform 160ms ease;
  }

  .group\/title:hover .title-preview-popover,
  .group\/title:focus-within .title-preview-popover {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
