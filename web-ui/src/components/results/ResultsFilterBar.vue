<script setup lang="ts">
import { computed } from 'vue'
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
}

interface Props {
  files: string[]
  fileOptions?: FileOption[]
  selectedFile: string | null
  recommendedOnly: boolean
  sortBy: 'crawl_time' | 'publish_time' | 'price'
  sortOrder: 'asc' | 'desc'
  isLoading: boolean
  isReady: boolean
}

const props = defineProps<Props>()

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
  if (!props.isReady) return '加载任务名称...'
  if (options.value.length === 0) return '暂无结果，请先运行任务'
  if (!props.selectedFile) return '请选择任务结果'
  const match = options.value.find((option) => option.value === props.selectedFile)
  return match ? match.label : '任务名称：未命名'
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
  (e: 'update:recommendedOnly', value: boolean): void
  (e: 'update:sortBy', value: 'crawl_time' | 'publish_time' | 'price'): void
  (e: 'update:sortOrder', value: 'asc' | 'desc'): void
  (e: 'refresh'): void
  (e: 'delete'): void
}>()
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
        <SelectItem value="crawl_time">按爬取时间</SelectItem>
        <SelectItem value="publish_time">按发布时间</SelectItem>
        <SelectItem value="price">按价格</SelectItem>
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
        <SelectItem value="desc">降序</SelectItem>
        <SelectItem value="asc">升序</SelectItem>
      </SelectContent>
    </Select>

    <div class="flex items-center space-x-2">
      <Checkbox
        id="recommended-only"
        :model-value="props.recommendedOnly"
        @update:modelValue="(value) => emit('update:recommendedOnly', value === true)"
      />
      <Label for="recommended-only" class="cursor-pointer">仅看AI推荐</Label>
    </div>

    <Button @click="emit('refresh')" :disabled="props.isLoading">
      刷新
    </Button>

    <Button
      variant="destructive"
      @click="emit('delete')"
      :disabled="props.isLoading || !props.selectedFile"
    >
      删除结果
    </Button>
  </div>
</template>
