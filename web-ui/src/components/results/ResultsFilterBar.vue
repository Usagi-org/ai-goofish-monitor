<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface FileOption {
  value: string
  label: string
  taskName?: string
}

interface Props {
  files: string[]
  fileOptions?: FileOption[]
  selectedFile: string | null
  aiRecommendedOnly: boolean
  keywordRecommendedOnly: boolean
  sortBy: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count'
  sortOrder: 'asc' | 'desc'
  isLoading: boolean
  isReady: boolean
}

const props = defineProps<Props>()
const { t } = useI18n()

const options = computed(() => {
  if (!props.isReady) {
    return []
  }
  if (props.fileOptions && props.fileOptions.length > 0) {
    return props.fileOptions
  }
  return props.files.map((file) => ({ value: file, label: file }))
})

const selectedLabel = computed(() => {
  if (!props.isReady) return t('results.filters.loadingTaskNames')
  if (options.value.length === 0) return t('results.filters.noResults')
  if (!props.selectedFile) return t('results.filters.chooseResult')
  const match = options.value.find((option) => option.value === props.selectedFile)
  return match ? match.label : t('results.filters.taskNameLabel', { task: t('common.unnamed') })
})

const labelClass = computed(() => {
  const classes = ['transition-opacity', 'duration-200']
  if (!props.isReady || !props.selectedFile || options.value.length === 0) {
    classes.push('text-muted-foreground')
  }
  classes.push(props.isReady ? 'opacity-100' : 'opacity-70')
  return classes.join(' ')
})

const isSelectDisabled = computed(() => !props.isReady || options.value.length === 0)

const emit = defineEmits<{
  (e: 'update:selectedFile', value: string): void
  (e: 'update:aiRecommendedOnly', value: boolean): void
  (e: 'update:keywordRecommendedOnly', value: boolean): void
  (e: 'update:sortBy', value: 'crawl_time' | 'publish_time' | 'price' | 'keyword_hit_count'): void
  (e: 'update:sortOrder', value: 'asc' | 'desc'): void
  (e: 'refresh'): void
  (e: 'export'): void
  (e: 'delete'): void
}>()

function handleToggleAiRecommended(value: boolean) {
  emit('update:aiRecommendedOnly', value)
  if (value) {
    emit('update:keywordRecommendedOnly', false)
  }
}

function handleToggleKeywordRecommended(value: boolean) {
  emit('update:keywordRecommendedOnly', value)
  if (value) {
    emit('update:aiRecommendedOnly', false)
  }
}
</script>

<template>
  <div class="flex flex-wrap gap-4 items-center mb-6 p-4 bg-gray-50 rounded-lg border">
    <Select
      :model-value="props.selectedFile || undefined"
      @update:model-value="(value) => emit('update:selectedFile', value as string)"
    >
      <SelectTrigger class="w-[280px]" :disabled="isSelectDisabled">
        <span :class="labelClass">
          {{ selectedLabel }}
        </span>
      </SelectTrigger>
      <SelectContent>
        <SelectItem v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </SelectItem>
      </SelectContent>
    </Select>

    <Select
      :model-value="props.sortBy"
      @update:model-value="(value) => emit('update:sortBy', value as any)"
    >
      <SelectTrigger class="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="crawl_time">{{ t('results.filters.sortByCrawlTime') }}</SelectItem>
        <SelectItem value="publish_time">{{ t('results.filters.sortByPublishTime') }}</SelectItem>
        <SelectItem value="price">{{ t('results.filters.sortByPrice') }}</SelectItem>
        <SelectItem value="keyword_hit_count">{{ t('results.filters.sortByKeywordHits') }}</SelectItem>
      </SelectContent>
    </Select>

    <Select
      :model-value="props.sortOrder"
      @update:model-value="(value) => emit('update:sortOrder', value as any)"
    >
      <SelectTrigger class="w-[120px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="desc">{{ t('results.filters.desc') }}</SelectItem>
        <SelectItem value="asc">{{ t('results.filters.asc') }}</SelectItem>
      </SelectContent>
    </Select>

    <div class="flex items-center space-x-2">
      <Checkbox
        id="ai-recommended-only"
        :model-value="props.aiRecommendedOnly"
        @update:modelValue="(value) => handleToggleAiRecommended(value === true)"
      />
      <Label for="ai-recommended-only" class="cursor-pointer">{{ t('results.filters.aiOnly') }}</Label>
    </div>

    <div class="flex items-center space-x-2">
      <Checkbox
        id="keyword-recommended-only"
        :model-value="props.keywordRecommendedOnly"
        @update:modelValue="(value) => handleToggleKeywordRecommended(value === true)"
      />
      <Label for="keyword-recommended-only" class="cursor-pointer">{{ t('results.filters.keywordOnly') }}</Label>
    </div>

    <Button @click="emit('refresh')" :disabled="props.isLoading">
      {{ t('common.refresh') }}
    </Button>

    <Button
      variant="outline"
      @click="emit('export')"
      :disabled="props.isLoading || !props.selectedFile"
    >
      {{ t('results.filters.exportCsv') }}
    </Button>

    <Button
      variant="destructive"
      @click="emit('delete')"
      :disabled="props.isLoading || !props.selectedFile"
    >
      {{ t('results.filters.deleteResult') }}
    </Button>
  </div>
</template>
