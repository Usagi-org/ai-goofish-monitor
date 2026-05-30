<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Label } from '@/components/ui/label'
import { AUTO_ACCOUNT_VALUE, type AccountStrategy } from '@/components/tasks/taskFormPayload'

defineProps<{
  accountStrategy: AccountStrategy
  selectedAccountStateFile: string
  accountOptions?: { name: string; path: string }[]
}>()

const emit = defineEmits<{
  (e: 'update:accountStrategy', value: AccountStrategy): void
  (e: 'update:selectedAccountStateFile', value: string): void
}>()

const { t } = useI18n()
const accountStrategyOptions = computed(() => [
  { value: 'auto', label: t('tasks.form.accountStrategy.auto'), description: t('tasks.form.accountStrategy.autoDescription') },
  { value: 'fixed', label: t('tasks.form.accountStrategy.fixed'), description: t('tasks.form.accountStrategy.fixedDescription') },
  { value: 'rotate', label: t('tasks.form.accountStrategy.rotate'), description: t('tasks.form.accountStrategy.rotateDescription') },
])

function handleAccountStrategyChange(event: Event) {
  emit('update:accountStrategy', (event.target as HTMLSelectElement).value as AccountStrategy)
}

function handleAccountStateFileChange(event: Event) {
  emit('update:selectedAccountStateFile', (event.target as HTMLSelectElement).value || AUTO_ACCOUNT_VALUE)
}
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.accountStrategyLabel') }}</Label>
    <div class="space-y-2 sm:col-span-3">
      <select
        :value="accountStrategy"
        class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        @change="handleAccountStrategyChange"
      >
        <option v-for="option in accountStrategyOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <p class="text-xs text-gray-500">
        {{ accountStrategyOptions.find((option) => option.value === accountStrategy)?.description }}
      </p>
    </div>
  </div>
  <div v-if="accountStrategy === 'fixed'" class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label class="sm:text-right">{{ t('tasks.form.fixedAccount') }}</Label>
    <div class="sm:col-span-3">
      <select
        :value="selectedAccountStateFile"
        class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        @change="handleAccountStateFileChange"
      >
        <option :value="AUTO_ACCOUNT_VALUE">{{ t('tasks.form.selectAccount') }}</option>
        <option v-for="account in accountOptions || []" :key="account.path" :value="account.path">
          {{ account.name }}
        </option>
      </select>
    </div>
  </div>
</template>
