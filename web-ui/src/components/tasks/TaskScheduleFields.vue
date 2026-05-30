<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  EMPTY_CRON_VALUE,
  fromPresetCronModelValue,
  isPresetCronValue,
  toPresetCronModelValue,
  type CronMode,
} from '@/components/tasks/taskFormPayload'

const props = defineProps<{
  form: Record<string, any>
  cronMode: CronMode
}>()

const emit = defineEmits<{
  (e: 'update:cronMode', value: CronMode): void
}>()

const { t } = useI18n()
const cronModeModel = computed({
  get: () => props.cronMode,
  set: (value: CronMode) => emit('update:cronMode', value),
})

const cronPresets = computed(() => [
  { value: EMPTY_CRON_VALUE, label: t('tasks.form.cron.manual') },
  { value: '*/5 * * * *', label: t('tasks.form.cron.every5Minutes') },
  { value: '*/15 * * * *', label: t('tasks.form.cron.every15Minutes') },
  { value: '*/30 * * * *', label: t('tasks.form.cron.every30Minutes') },
  { value: '0 * * * *', label: t('tasks.form.cron.hourly') },
  { value: '0 */2 * * *', label: t('tasks.form.cron.every2Hours') },
  { value: '0 */6 * * *', label: t('tasks.form.cron.every6Hours') },
  { value: '0 8 * * *', label: t('tasks.form.cron.daily8') },
  { value: '0 12 * * *', label: t('tasks.form.cron.daily12') },
  { value: '0 18 * * *', label: t('tasks.form.cron.daily18') },
  { value: '0 20 * * *', label: t('tasks.form.cron.daily20') },
  { value: '0 8,12,18 * * *', label: t('tasks.form.cron.daily81218') },
  { value: '0 9 * * 1-5', label: t('tasks.form.cron.weekday9') },
  { value: '0 10 * * 6,0', label: t('tasks.form.cron.weekend10') },
])

const isPresetCron = computed(() => isPresetCronValue(props.form.cron))
const presetCronValue = computed({
  get: () => toPresetCronModelValue(isPresetCron.value ? props.form.cron : undefined),
  set: (val: string) => { props.form.cron = fromPresetCronModelValue(val) },
})
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:items-center sm:gap-4">
    <Label for="cron" class="sm:text-right">{{ t('tasks.form.schedule') }}</Label>
    <div class="space-y-2 sm:col-span-3">
      <Tabs v-model="cronModeModel" class="w-full">
        <TabsList class="grid w-full grid-cols-2">
          <TabsTrigger value="preset">{{ t('tasks.form.cronPresetTab') }}</TabsTrigger>
          <TabsTrigger value="custom">{{ t('tasks.form.cronCustomTab') }}</TabsTrigger>
        </TabsList>
        <TabsContent value="preset">
          <Select v-model="presetCronValue">
            <SelectTrigger>
              <SelectValue :placeholder="t('tasks.form.cronPlaceholder')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="preset in cronPresets" :key="preset.value" :value="preset.value">
                {{ preset.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </TabsContent>
        <TabsContent value="custom">
          <Input
            id="cron"
            v-model="form.cron"
            :placeholder="t('tasks.form.cronCustomPlaceholder')"
          />
          <p class="text-xs text-gray-500 mt-1">
            {{ t('tasks.form.cronCustomHintLine1') }}
          </p>
          <p class="text-xs text-gray-500">
            {{ t('tasks.form.cronCustomHintLine2') }}
          </p>
        </TabsContent>
      </Tabs>
    </div>
  </div>
</template>
