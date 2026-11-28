<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ResultItem } from '@/types/result.d.ts'
import { useResults } from '@/composables/useResults'
import ResultsFilterBar from '@/components/results/ResultsFilterBar.vue'
import ResultsGrid from '@/components/results/ResultsGrid.vue'
import ResultsInsightsPanel from '@/components/results/ResultsInsightsPanel.vue'
import ItemDetailDialog from '@/components/results/ItemDetailDialog.vue'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { toast } from '@/components/ui/toast'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const { t } = useI18n()

const {
  files,
  selectedFile,
  results,
  insights,
  filters,
  isLoading,
  error,
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
} = useResults()

const isDeleteDialogOpen = ref(false)
const isBlacklistDialogOpen = ref(false)
const blacklistDraft = ref('')

const isDetailDialogOpen = ref(false)
const selectedItemId = ref<string | null>(null)
const fallbackSelectedItem = ref<ResultItem | null>(null)

const selectedItem = computed<ResultItem | null>(() => {
  if (!selectedItemId.value) return null
  const live = results.value.find((entry) => entry.商品信息?.商品ID === selectedItemId.value)
  return live ?? fallbackSelectedItem.value
})

const isSelectedItemChecking = computed(() => {
  if (isCheckingStatus.value) return true
  if (!selectedItemId.value) return false
  return checkingItemIds.value.includes(selectedItemId.value)
})

watch(
  results,
  (items) => {
    if (!selectedItemId.value) return
    const latest = items.find((entry) => entry.商品信息?.商品ID === selectedItemId.value)
    if (latest) {
      fallbackSelectedItem.value = latest
    }
  }
)

watch(isDetailDialogOpen, (open) => {
  if (!open) {
    selectedItemId.value = null
    fallbackSelectedItem.value = null
  }
})

watch(selectedFile, () => {
  isDetailDialogOpen.value = false
})

const selectedTaskLabel = computed(() => {
  if (!selectedFile.value || fileOptions.value.length === 0) return null
  const match = fileOptions.value.find((option) => option.value === selectedFile.value)
  if (!match) return null
  return match.taskName || null
})

const deleteConfirmText = computed(() => {
  return selectedTaskLabel.value
    ? t('results.filters.deleteDialogWithTask', { task: selectedTaskLabel.value })
    : t('results.filters.deleteDialogFallback')
})

function openItemDetail(item: ResultItem) {
  selectedItemId.value = item.商品信息.商品ID
  fallbackSelectedItem.value = item
  isDetailDialogOpen.value = true
}

function openDeleteDialog() {
  if (!selectedFile.value) {
    toast({
      title: t('results.filters.noResultToDelete'),
      variant: 'destructive',
    })
    return
  }
  isDeleteDialogOpen.value = true
}

function openBlacklistDialog() {
  if (!selectedFile.value) {
    toast({
      title: t('results.filters.noResultSelected'),
      variant: 'destructive',
    })
    return
  }
  blacklistDraft.value = blacklistKeywords.value.join('\n')
  isBlacklistDialogOpen.value = true
}

function handleExportResults() {
  if (!selectedFile.value) {
    toast({
      title: t('results.filters.noResultToExport'),
      variant: 'destructive',
    })
    return
  }
  exportSelectedResults()
}

async function handleDeleteResults() {
  if (!selectedFile.value) return
  try {
    await deleteSelectedFile(selectedFile.value)
    toast({ title: t('results.filters.resultDeleted') })
  } catch (e) {
    toast({
      title: t('results.filters.deleteFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  } finally {
    isDeleteDialogOpen.value = false
  }
}

async function handleToggleBlock(item: ResultItem) {
  try {
    const nextStatus = await toggleItemBlock(item)
    if (nextStatus && fallbackSelectedItem.value?.商品信息?.商品ID === item.商品信息.商品ID) {
      const isRuleHidden = fallbackSelectedItem.value._hidden_reason === 'rule'
      fallbackSelectedItem.value = {
        ...fallbackSelectedItem.value,
        _status: nextStatus,
        _is_sold: false,
        _effective_hidden: nextStatus === 'hidden' || isRuleHidden,
        _hidden_reason: nextStatus === 'hidden' ? 'manual' : isRuleHidden ? 'rule' : null,
      }
    }
  } catch (e) {
    toast({
      title: t('results.card.statusUpdateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleToggleSold(item: ResultItem) {
  try {
    const nextStatus = await toggleItemSold(item)
    if (!nextStatus) return
    if (fallbackSelectedItem.value?.商品信息?.商品ID === item.商品信息.商品ID) {
      const isRuleHidden = fallbackSelectedItem.value._hidden_reason === 'rule'
      fallbackSelectedItem.value = {
        ...fallbackSelectedItem.value,
        _status: nextStatus,
        _is_sold: nextStatus === 'sold',
        _effective_hidden: isRuleHidden,
        _hidden_reason: isRuleHidden ? 'rule' : null,
      }
    }
    toast({
      title: nextStatus === 'sold' ? t('results.card.markedSold') : t('results.card.markedActive'),
    })
  } catch (e) {
    toast({
      title: t('results.card.statusUpdateFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleCheckAllStatus() {
  if (!selectedFile.value) {
    toast({
      title: t('results.filters.noResultSelected'),
      variant: 'destructive',
    })
    return
  }
  try {
    const res = await checkAllActiveStatus()
    if (!res) return
    if (res.checked === 0) {
      toast({ title: t('results.filters.checkStatusEmpty') })
      return
    }
    const baseSummary = t('results.filters.checkStatusSummary', {
      checked: res.checked,
      active: res.active_count,
      sold: res.sold_count,
      expired: res.expired_count,
      failed: res.failed_count,
    })
    const stoppedSuffix = res.stopped_reason
      ? t('results.filters.checkStatusStopped', { reason: res.stopped_reason })
      : ''
    toast({
      title: t('results.filters.checkStatusDone'),
      description: `${baseSummary}${stoppedSuffix}`,
    })
  } catch (e) {
    toast({
      title: t('results.filters.checkStatusFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

async function handleCheckSingleStatus(item: ResultItem) {
  try {
    const res = await checkSingleItemStatus(item)
    if (!res) return
    const entry = res.results?.[0]
    if (entry?.error) {
      toast({
        title: t('results.detail.singleCheckFailed'),
        description: entry.error,
        variant: 'destructive',
      })
      return
    }
    const isUnknownLiveStatus =
      entry?.mapped_status === 'unknown' ||
      (entry?.mapped_status === undefined && res.unknown_count > 0)
    const statusLabel =
      entry?.status_label ||
      (entry?.status === 'sold'
        ? t('results.card.soldStamp')
        : entry?.status === 'expired'
          ? t('results.card.expired')
          : isUnknownLiveStatus
            ? null
            : t('results.card.activeStatus'))
    if (
      entry &&
      fallbackSelectedItem.value?.商品信息?.商品ID === item.商品信息.商品ID &&
      !results.value.some((record) => record.商品信息?.商品ID === item.商品信息.商品ID)
    ) {
      const nextStatus = entry.status as ResultItem['_status']
      const isRuleHidden = fallbackSelectedItem.value._hidden_reason === 'rule'
      const nextHiddenReason =
        nextStatus === 'expired'
          ? 'expired'
          : nextStatus === 'hidden'
            ? 'manual'
            : isRuleHidden
              ? 'rule'
              : null
      const nextInfo = {
        ...fallbackSelectedItem.value.商品信息,
        ...(entry.title ? { 商品标题: entry.title } : {}),
        ...(entry.description ? { 商品描述: entry.description } : {}),
        ...(entry.image_urls && entry.image_urls.length > 0
          ? { 商品图片列表: entry.image_urls, 商品主图链接: entry.image_urls[0] }
          : {}),
        ...(statusLabel ? { 商品状态: statusLabel } : {}),
        状态检查时间: entry.checked_at || new Date().toISOString(),
      }
      fallbackSelectedItem.value = {
        ...fallbackSelectedItem.value,
        _status: nextStatus,
        _is_sold: nextStatus === 'sold',
        _effective_hidden: nextHiddenReason !== null,
        _hidden_reason: nextHiddenReason,
        商品信息: nextInfo,
      }
    }
    toast({
      title: entry?.description_updated
        ? t('results.detail.singleCheckSyncedDesc')
        : isUnknownLiveStatus
          ? t('results.detail.singleCheckUnknown')
          : t('results.detail.singleCheckUpdated', { status: statusLabel || t('common.unknown') }),
      description: entry?.status_label ? `${t('results.detail.liveStatusLabel')}：${entry.status_label}` : undefined,
    })
  } catch (e) {
    toast({
      title: t('results.detail.singleCheckFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}

function parseBlacklistKeywords(input: string) {
  return input
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

async function handleSaveBlacklistRules() {
  try {
    await saveBlacklistRules(parseBlacklistKeywords(blacklistDraft.value))
    toast({ title: t('results.filters.blacklistSaved') })
    isBlacklistDialogOpen.value = false
  } catch (e) {
    toast({
      title: t('results.filters.blacklistSaveFailed'),
      description: (e as Error).message,
      variant: 'destructive',
    })
  }
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-gray-800 mb-6">
      {{ t('results.title') }}
    </h1>

    <div v-if="error" class="app-alert-error mb-4" role="alert">
      <strong class="font-bold">{{ t('common.error') }}</strong>
      <span class="block sm:inline">{{ error.message }}</span>
    </div>

    <ResultsFilterBar
      :files="files"
      :file-options="fileOptions"
      :is-ready="isFileOptionsReady"
      v-model:selectedFile="selectedFile"
      v-model:aiRecommendedOnly="filters.ai_recommended_only"
      v-model:keywordRecommendedOnly="filters.keyword_recommended_only"
      v-model:includeHidden="filters.include_hidden"
      v-model:hideSold="filters.hide_sold"
      v-model:sortBy="filters.sort_by"
      v-model:sortOrder="filters.sort_order"
      :is-loading="isLoading"
      :is-checking-status="isCheckingStatus"
      @refresh="refreshResults"
      @check-status="handleCheckAllStatus"
      @manage-blacklist="openBlacklistDialog"
      @export="handleExportResults"
      @delete="openDeleteDialog"
    />

    <ResultsInsightsPanel :insights="insights" :selected-task-label="selectedTaskLabel" />

    <ResultsGrid
      :results="results"
      :is-loading="isLoading"
      @open-detail="openItemDetail"
      @toggle-block="handleToggleBlock"
      @toggle-sold="handleToggleSold"
    />

    <ItemDetailDialog
      v-model:open="isDetailDialogOpen"
      :item="selectedItem"
      :is-checking-status="isSelectedItemChecking"
      @check-status="handleCheckSingleStatus"
      @toggle-sold="handleToggleSold"
      @toggle-block="handleToggleBlock"
    />

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent class="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{{ t('results.filters.deleteDialogTitle') }}</DialogTitle>
          <DialogDescription>
            {{ deleteConfirmText }}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button variant="destructive" :disabled="isLoading" @click="handleDeleteResults">
            {{ t('results.filters.confirmDelete') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isBlacklistDialogOpen">
      <DialogContent class="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ t('results.filters.blacklistDialogTitle') }}</DialogTitle>
          <DialogDescription>
            {{ t('results.filters.blacklistDialogDescription') }}
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">
            {{ t('results.filters.blacklistRulesLabel') }}
          </label>
          <Textarea
            v-model="blacklistDraft"
            class="min-h-[180px]"
            :placeholder="t('results.filters.blacklistRulesPlaceholder')"
          />
          <p class="text-xs leading-5 text-slate-500">
            {{ t('results.filters.blacklistRulesHint') }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isBlacklistDialogOpen = false">{{ t('common.cancel') }}</Button>
          <Button :disabled="isSavingBlacklist" @click="handleSaveBlacklistRules">
            {{ t('results.filters.confirmBlacklistSave') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
