<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const { t } = useI18n()
const keywordRulesInput = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value),
})
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:gap-4">
    <Label class="pt-1 sm:pt-2 sm:text-right">{{ t('tasks.form.keywordRules') }}</Label>
    <div class="space-y-2 sm:col-span-3">
      <p class="text-xs text-gray-500">
        {{ t('tasks.form.keywordRulesHint') }}
      </p>
      <Textarea
        v-model="keywordRulesInput"
        class="min-h-[120px]"
        :placeholder="t('tasks.form.keywordRulesPlaceholder')"
      />
    </div>
  </div>
</template>
