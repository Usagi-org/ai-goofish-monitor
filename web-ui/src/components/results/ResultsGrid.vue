<script setup lang="ts">
import type { ResultItem } from '@/types/result.d.ts'
import { useI18n } from 'vue-i18n'
import ResultCard from './ResultCard.vue'

interface Props {
  results: ResultItem[]
  isLoading: boolean
}

defineProps<Props>()
const { t } = useI18n()
</script>

<template>
  <div>
    <div v-if="isLoading" class="text-center py-12 text-gray-500">
      {{ t('results.grid.loading') }}
    </div>
    <div v-else-if="results.length === 0" class="text-center py-12 text-gray-500">
      {{ t('results.grid.empty') }}
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      <ResultCard v-for="item in results" :key="item.商品信息.商品ID" :item="item" />
    </div>
  </div>
</template>
