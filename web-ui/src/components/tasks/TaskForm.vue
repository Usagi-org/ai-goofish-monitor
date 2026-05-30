<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NotificationTarget, Task, TaskGenerateRequest } from '@/types/task.d.ts'
import { toast } from '@/components/ui/toast'
import TaskAccountStrategy from '@/components/tasks/TaskAccountStrategy.vue'
import TaskBasicFields from '@/components/tasks/TaskBasicFields.vue'
import TaskDecisionMode from '@/components/tasks/TaskDecisionMode.vue'
import TaskFilterFields from '@/components/tasks/TaskFilterFields.vue'
import TaskKeywordRules from '@/components/tasks/TaskKeywordRules.vue'
import TaskNotificationTargets from '@/components/tasks/TaskNotificationTargets.vue'
import TaskScheduleFields from '@/components/tasks/TaskScheduleFields.vue'
import TaskSellerPublicationFields from '@/components/tasks/TaskSellerPublicationFields.vue'
import {
  AUTO_ACCOUNT_VALUE,
  buildInitialTaskFormState,
  buildTaskSubmitPayload,
  parseKeywordText,
  type AccountStrategy,
  type CronMode,
  type EmittedTaskFormData,
  type FormMode,
} from '@/components/tasks/taskFormPayload'

const props = defineProps<{
  mode: FormMode
  formId?: string
  initialData?: Task | null
  accountOptions?: { name: string; path: string }[]
  defaultAccount?: string
  defaultValues?: Partial<TaskGenerateRequest & Partial<Task>>
}>()

const emit = defineEmits<{
  (e: 'submit', data: EmittedTaskFormData): void
}>()
const { t } = useI18n()

const form = ref<any>({})
const accountStrategy = ref<AccountStrategy>('auto')
const selectedAccountStateFile = ref(AUTO_ACCOUNT_VALUE)
const keywordRulesInput = ref('')
const cronMode = ref<CronMode>('preset')

watch(() => [props.mode, props.initialData, props.defaultValues, props.defaultAccount], () => {
  const state = buildInitialTaskFormState({
    mode: props.mode,
    initialData: props.initialData,
    defaultValues: props.defaultValues,
    defaultAccount: props.defaultAccount,
  })
  form.value = state.form
  keywordRulesInput.value = state.keywordRulesInput
  cronMode.value = state.cronMode
  accountStrategy.value = state.accountStrategy
  selectedAccountStateFile.value = state.selectedAccountStateFile
}, { immediate: true, deep: true })

watch(accountStrategy, (value) => {
  form.value.account_strategy = value
  if (value === 'fixed') {
    form.value.account_state_file = selectedAccountStateFile.value || props.defaultAccount || AUTO_ACCOUNT_VALUE
    return
  }
  form.value.account_state_file = null
})

watch(selectedAccountStateFile, (value) => {
  if (accountStrategy.value !== 'fixed') return
  form.value.account_state_file = value || props.defaultAccount || AUTO_ACCOUNT_VALUE
})

function updateNotificationTargets(value: NotificationTarget[]) {
  form.value.notification_targets = value
}

function handleSubmit() {
  if (!form.value.task_name || !form.value.keyword) {
    toast({
      title: t('tasks.form.validation.incomplete'),
      description: t('tasks.form.validation.nameAndKeywordRequired'),
      variant: 'destructive',
    })
    return
  }

  const decisionMode = form.value.decision_mode || 'ai'
  if (decisionMode === 'ai' && !String(form.value.description || '').trim()) {
    toast({
      title: t('tasks.form.validation.incomplete'),
      description: t('tasks.form.validation.aiDescriptionRequired'),
      variant: 'destructive',
    })
    return
  }

  const keywordRules = parseKeywordText(keywordRulesInput.value)
  if (decisionMode === 'keyword' && keywordRules.length === 0) {
    toast({
      title: t('tasks.form.validation.keywordRuleIncomplete'),
      description: t('tasks.form.validation.keywordRuleRequired'),
      variant: 'destructive',
    })
    return
  }

  const result = buildTaskSubmitPayload({
    form: form.value,
    keywordRulesInput: keywordRulesInput.value,
    accountStrategy: accountStrategy.value,
    selectedAccountStateFile: selectedAccountStateFile.value,
  })

  if (result.error === 'fixed-account-required') {
    toast({
      title: t('tasks.form.validation.accountStrategyIncomplete'),
      description: t('tasks.form.validation.fixedAccountRequired'),
      variant: 'destructive',
    })
    return
  }

  emit('submit', result.payload!)
}

</script>

<template>
  <form :id="formId || 'task-form'" @submit.prevent="handleSubmit">
    <div class="grid gap-6 py-4">
      <TaskBasicFields :form="form" />
      <TaskDecisionMode :form="form" />
      <TaskKeywordRules v-if="form.decision_mode === 'keyword'" v-model="keywordRulesInput" />
      <TaskFilterFields :form="form" />
      <TaskScheduleFields :form="form" v-model:cron-mode="cronMode" />
      <TaskAccountStrategy
        v-model:account-strategy="accountStrategy"
        v-model:selected-account-state-file="selectedAccountStateFile"
        :account-options="accountOptions"
      />
      <TaskSellerPublicationFields :form="form" />
      <TaskNotificationTargets
        :model-value="form.notification_targets || []"
        @update:model-value="updateNotificationTargets"
      />
    </div>
  </form>
</template>
