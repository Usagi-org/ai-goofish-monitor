<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import regionTree from '@/data/goofishRegions.json'

type RegionTree = Record<string, Record<string, string[]>>

const props = defineProps<{
  modelValue?: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const tree = regionTree as RegionTree
const provinceKeys = Object.keys(tree)
const selectedProvince = ref('')
const selectedCity = ref('')
const selectedDistrict = ref('')
const lastSyncedPath = ref('')

const provinceOptions = computed(() => provinceKeys)
const cityOptions = computed(() => {
  return selectedProvince.value ? Object.keys(tree[selectedProvince.value] || {}) : []
})
const districtOptions = computed(() => {
  if (!selectedProvince.value || !selectedCity.value) return []
  return tree[selectedProvince.value]?.[selectedCity.value] || []
})
const currentPath = computed(() => {
  return [selectedProvince.value, selectedCity.value, selectedDistrict.value]
    .filter((item) => item.length > 0)
    .join('/')
})

function normalizePath(value: string | null | undefined): string {
  return String(value || '')
    .split('/')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .join('/')
}

function isFullOption(value: string): boolean {
  return value.startsWith('全') || value === '全国'
}

function syncFromModel() {
  const normalized = normalizePath(props.modelValue)
  if (normalized === lastSyncedPath.value) return
  lastSyncedPath.value = normalized

  const parts = normalized.split('/').filter(Boolean)
  selectedProvince.value = parts[0] || ''
  selectedCity.value = parts[1] || ''
  selectedDistrict.value = parts[2] || ''
}

function emitCurrentPath() {
  emit('update:modelValue', currentPath.value)
}

function clearSelection() {
  selectedProvince.value = ''
  selectedCity.value = ''
  selectedDistrict.value = ''
  emit('update:modelValue', '')
}

function handleProvinceChange(value: string) {
  selectedProvince.value = value
  selectedCity.value = ''
  selectedDistrict.value = ''

  const firstCity = cityOptions.value[0] || ''
  if (value && value !== '全国' && isFullOption(firstCity)) {
    selectedCity.value = firstCity
  }
  emitCurrentPath()
}

function handleCityChange(value: string) {
  selectedCity.value = value
  selectedDistrict.value = ''

  const firstDistrict = districtOptions.value[0] || ''
  if (isFullOption(firstDistrict)) {
    selectedDistrict.value = firstDistrict
  }
  emitCurrentPath()
}

function handleDistrictChange(value: string) {
  selectedDistrict.value = value
  emitCurrentPath()
}

watch(() => props.modelValue, syncFromModel, { immediate: true })
</script>

<template>
  <div class="space-y-3">
    <div class="grid gap-2 md:grid-cols-3">
      <Select
        :model-value="selectedProvince"
        @update:model-value="(value) => handleProvinceChange(String(value || ''))"
      >
        <SelectTrigger>
          <SelectValue placeholder="选择省份 / 全国" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="option in provinceOptions" :key="option" :value="option">
            {{ option }}
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        :disabled="!selectedProvince || cityOptions.length === 0"
        :model-value="selectedCity"
        @update:model-value="(value) => handleCityChange(String(value || ''))"
      >
        <SelectTrigger>
          <SelectValue placeholder="选择城市 / 区域组" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="option in cityOptions" :key="option" :value="option">
            {{ option }}
          </SelectItem>
        </SelectContent>
      </Select>

      <Select
        :disabled="!selectedCity || districtOptions.length === 0"
        :model-value="selectedDistrict"
        @update:model-value="(value) => handleDistrictChange(String(value || ''))"
      >
        <SelectTrigger>
          <SelectValue placeholder="选择区 / 县" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="option in districtOptions" :key="option" :value="option">
            {{ option }}
          </SelectItem>
        </SelectContent>
      </Select>
    </div>

    <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <span>区域选项基于闲鱼页面抓取快照内置，不再依赖实时外站请求</span>
    </div>

    <div class="flex flex-wrap gap-2">
      <Button type="button" variant="ghost" size="sm" @click="clearSelection">
        清空区域
      </Button>
      <span v-if="currentPath" class="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
        当前：{{ currentPath }}
      </span>
    </div>
  </div>
</template>
