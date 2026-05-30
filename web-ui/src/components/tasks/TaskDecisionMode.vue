<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

defineProps<{
  form: Record<string, any>
}>()

const { t } = useI18n()
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.decisionMode') }}</Label>
    <div class="sm:col-span-3">
      <Select v-model="form.decision_mode">
        <SelectTrigger>
          <SelectValue :placeholder="t('tasks.form.decisionModePlaceholder')" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="ai">{{ t('tasks.form.aiMode') }}</SelectItem>
          <SelectItem value="keyword">{{ t('tasks.form.keywordMode') }}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  </div>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="description" class="sm:text-right">{{ t('tasks.form.description') }}</Label>
    <div class="space-y-1 sm:col-span-3">
      <Textarea
        id="description"
        v-model="form.description"
        :placeholder="t('tasks.form.descriptionPlaceholder')"
      />
      <p v-if="form.decision_mode === 'keyword'" class="text-xs text-gray-500">
        {{ t('tasks.form.keywordDescriptionHint') }}
      </p>
    </div>
  </div>
  <div v-if="form.decision_mode === 'ai'" class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="analyze-images" class="sm:text-right">{{ t('tasks.form.analyzeImages') }}</Label>
    <div class="space-y-1 sm:col-span-3">
      <Switch id="analyze-images" v-model="form.analyze_images" />
      <p class="text-xs text-gray-500">
        {{ t('tasks.form.analyzeImagesHint') }}
      </p>
    </div>
  </div>
</template>
