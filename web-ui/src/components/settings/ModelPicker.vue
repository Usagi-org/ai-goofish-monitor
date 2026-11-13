<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Check, ListChecks, Loader2, RefreshCw, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{
  modelValue?: string
  models: string[]
  loading: boolean
  loaded: boolean
  error: string | null
  disabled?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  refresh: []
}>()
const { t } = useI18n()
const open = ref(false)
const query = ref('')
const selected = ref('')
const filtered = computed(() => {
  const term = query.value.trim().toLowerCase()
  return props.models.filter(model => model.toLowerCase().includes(term))
})
const canApply = computed(() => !props.loading && !props.error && props.models.includes(selected.value))

watch(open, value => {
  if (!value) return
  query.value = ''
  selected.value = props.modelValue || ''
  if (!props.loaded && !props.loading) emit('refresh')
})

function apply() {
  if (!canApply.value) return
  emit('update:modelValue', selected.value)
  open.value = false
}
</script>

<template>
  <Button type="button" variant="outline" class="shrink-0 gap-2" :disabled="disabled" @click="open = true">
    <ListChecks class="h-4 w-4" aria-hidden="true" />
    {{ t(loaded ? 'settings.ai.chooseModel' : 'settings.ai.loadModels') }}
  </Button>
  <Dialog v-model:open="open">
    <DialogContent overlay-class="z-[110] bg-slate-950/40" class="z-[111] flex max-h-[90dvh] w-[calc(100%-2rem)] max-w-[560px] flex-col gap-4 rounded-xl p-5 sm:p-6">
      <DialogHeader class="pr-5 text-left">
        <DialogTitle>{{ t('settings.ai.chooseModel') }}</DialogTitle>
        <DialogDescription>{{ t('settings.ai.modelPickerDescription') }}</DialogDescription>
      </DialogHeader>

      <div class="flex shrink-0 items-center gap-2">
        <div class="relative min-w-0 flex-1">
          <Search class="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" aria-hidden="true" />
          <Input v-model="query" class="pl-9" :aria-label="t('settings.ai.searchModels')" :placeholder="t('settings.ai.searchModels')" autocomplete="off" @keydown.enter.prevent />
        </div>
        <Button type="button" variant="outline" class="shrink-0 px-3" :disabled="loading" :aria-label="t('settings.ai.refreshModels')" :title="t('settings.ai.refreshModels')" @click="emit('refresh')">
          <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': loading }" aria-hidden="true" />
        </Button>
      </div>

      <p class="text-xs text-slate-500" role="status">
        {{ t('settings.ai.modelsCount', { visible: filtered.length, total: models.length }) }}
      </p>
      <div class="min-h-0 flex-1 overflow-y-auto rounded-lg border border-slate-200 sm:flex-none" style="height: min(320px, 40dvh)">
        <div v-if="loading" class="flex h-full min-h-24 items-center justify-center gap-2 text-sm text-slate-500" role="status">
          <Loader2 class="h-4 w-4 animate-spin" aria-hidden="true" />
          {{ t('settings.ai.loadingModels') }}
        </div>
        <p v-else-if="error" class="px-4 py-8 text-sm text-red-600" role="alert">{{ error }}</p>
        <p v-else-if="!filtered.length" class="px-4 py-8 text-center text-sm text-slate-500">
          {{ t(models.length ? 'settings.ai.noMatchingModels' : 'settings.ai.modelsEmpty') }}
        </p>
        <div v-else role="radiogroup" :aria-label="t('settings.ai.chooseModel')" class="divide-y divide-slate-100">
          <label v-for="model in filtered" :key="model" class="flex cursor-pointer items-center gap-3 px-3 py-3 text-sm transition-colors focus-within:ring-2 focus-within:ring-inset focus-within:ring-blue-500" :class="selected === model ? 'bg-blue-50' : 'hover:bg-slate-50'">
            <span class="relative flex h-4 w-4 shrink-0 items-center justify-center">
              <input v-model="selected" type="radio" name="ai-model-choice" :value="model" :aria-label="model" class="h-4 w-4 cursor-pointer appearance-none rounded border border-slate-300 bg-white checked:border-blue-600 checked:bg-blue-600" />
              <Check v-if="selected === model" class="pointer-events-none absolute h-3 w-3 text-white" aria-hidden="true" />
            </span>
            <span class="min-w-0 flex-1 break-all font-mono text-xs">{{ model }}</span>
            <span v-if="model === modelValue" class="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{{ t('settings.ai.currentModel') }}</span>
          </label>
        </div>
      </div>
      <p class="min-w-0 break-all text-xs text-slate-500">
        {{ t('settings.ai.selectedModel') }} <span class="font-medium text-slate-700">{{ selected || t('settings.ai.noModelSelected') }}</span>
      </p>
      <DialogFooter class="flex-row justify-end gap-2 border-t border-slate-100 pt-4">
        <Button type="button" variant="outline" @click="open = false">{{ t('common.cancel') }}</Button>
        <Button type="button" :disabled="!canApply" @click="apply">{{ t('settings.ai.applyModel') }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
