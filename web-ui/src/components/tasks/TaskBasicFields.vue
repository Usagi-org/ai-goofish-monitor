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
    <Label for="task-name" class="sm:text-right">{{ t('tasks.form.taskName') }}</Label>
    <Input id="task-name" v-model="form.task_name" class="sm:col-span-3" :placeholder="t('tasks.form.taskNamePlaceholder')" required />
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="keyword" class="sm:text-right">{{ t('tasks.form.keyword') }}</Label>
    <Input id="keyword" v-model="form.keyword" class="sm:col-span-3" :placeholder="t('tasks.form.keywordPlaceholder')" required />
  </div>
</template>
