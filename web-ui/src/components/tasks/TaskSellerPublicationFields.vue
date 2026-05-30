<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import TaskRegionSelector from '@/components/tasks/TaskRegionSelector.vue'

defineProps<{
  form: Record<string, any>
}>()

const { t } = useI18n()
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="personal-only" class="sm:text-right">{{ t('tasks.form.personalOnly') }}</Label>
    <div class="sm:col-span-3">
      <Switch id="personal-only" v-model="form.personal_only" />
    </div>
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="free-shipping" class="sm:text-right">{{ t('tasks.form.freeShipping') }}</Label>
    <div class="sm:col-span-3">
      <Switch id="free-shipping" v-model="form.free_shipping" />
    </div>
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.newPublish') }}</Label>
    <div class="sm:col-span-3">
      <Select v-model="form.new_publish_option as any">
        <SelectTrigger>
          <SelectValue :placeholder="t('tasks.form.publishOptions.none')" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none__">{{ t('tasks.form.publishOptions.none') }}</SelectItem>
          <SelectItem value="最新">{{ t('tasks.form.publishOptions.latest') }}</SelectItem>
          <SelectItem value="1天内">{{ t('tasks.form.publishOptions.oneDay') }}</SelectItem>
          <SelectItem value="3天内">{{ t('tasks.form.publishOptions.threeDays') }}</SelectItem>
          <SelectItem value="7天内">{{ t('tasks.form.publishOptions.sevenDays') }}</SelectItem>
          <SelectItem value="14天内">{{ t('tasks.form.publishOptions.fourteenDays') }}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.region') }}</Label>
    <div class="space-y-1 sm:col-span-3">
      <TaskRegionSelector v-model="form.region as any" />
      <p class="text-xs text-gray-500">{{ t('tasks.form.regionHint') }}</p>
    </div>
  </div>
</template>
