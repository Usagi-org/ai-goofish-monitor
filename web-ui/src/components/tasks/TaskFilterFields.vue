<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

defineProps<{
  form: Record<string, any>
}>()

const { t } = useI18n()
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.priceRange') }}</Label>
    <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:col-span-3">
      <Input type="number" v-model="form.min_price as any" :aria-label="t('tasks.form.minPrice')" :placeholder="t('tasks.form.minPrice')" />
      <span>-</span>
      <Input type="number" v-model="form.max_price as any" :aria-label="t('tasks.form.maxPrice')" :placeholder="t('tasks.form.maxPrice')" />
    </div>
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="max-pages" class="sm:text-right">{{ t('tasks.form.maxPages') }}</Label>
    <Input id="max-pages" v-model.number="form.max_pages" type="number" class="sm:col-span-3" />
  </div>
</template>
