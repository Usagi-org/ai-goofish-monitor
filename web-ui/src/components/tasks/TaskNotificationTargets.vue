<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NotificationChannel, NotificationTarget } from '@/types/task.d.ts'
import { fetchWeComAppDepartments, fetchWeComAppUsers, type WeComAppDepartment, type WeComAppUser } from '@/api/settings'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface WeComRecipientPickerState {
  departments: WeComAppDepartment[]
  users: WeComAppUser[]
  selectedDepartmentId: string
  loadingDepartments: boolean
  loadingUsers: boolean
  loadedDepartments: boolean
  error: string
}

const props = defineProps<{
  modelValue?: NotificationTarget[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: NotificationTarget[]): void
}>()

const { t } = useI18n()
const wecomRecipientPickers = ref<Record<string, WeComRecipientPickerState>>({})
const targets = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])
const notificationChannelOptions = computed(() => [
  { value: 'telegram', label: t('tasks.form.notifications.channels.telegram') },
  { value: 'wecom_app', label: t('tasks.form.notifications.channels.wecomApp') },
  { value: 'default', label: t('tasks.form.notifications.channels.default') },
])

function emitTargets(value: NotificationTarget[]) {
  emit('update:modelValue', value)
}

function addNotificationTarget() {
  emitTargets([...targets.value, { channel: 'telegram', recipient: '', label: '' }])
}

function removeNotificationTarget(index: string | number) {
  const numericIndex = Number(index)
  if (!Number.isFinite(numericIndex)) return
  const nextTargets = [...targets.value]
  nextTargets.splice(numericIndex, 1)
  emitTargets(nextTargets)
  delete wecomRecipientPickers.value[String(numericIndex)]
}

function updateNotificationTargetChannel(index: string | number, value: unknown) {
  const numericIndex = Number(index)
  if (!Number.isFinite(numericIndex)) return
  const channel = String(value || '').trim() as NotificationChannel
  if (!['telegram', 'wecom_app', 'default'].includes(channel)) return

  const nextTargets = [...targets.value]
  const current = nextTargets[numericIndex]
  if (!current) return

  nextTargets[numericIndex] = {
    ...current,
    channel,
    recipient: channel === 'default' ? '' : (current.recipient || ''),
  }
  emitTargets(nextTargets)
}

function notificationRecipientPlaceholder(channel: NotificationChannel) {
  if (channel === 'telegram') return t('tasks.form.notifications.placeholders.telegram')
  if (channel === 'wecom_app') return t('tasks.form.notifications.placeholders.wecom_app', { at: '@' })
  return t('tasks.form.notifications.placeholders.default')
}

function getWeComPickerState(index: string | number): WeComRecipientPickerState {
  const key = String(index)
  if (!wecomRecipientPickers.value[key]) {
    wecomRecipientPickers.value[key] = {
      departments: [],
      users: [],
      selectedDepartmentId: '1',
      loadingDepartments: false,
      loadingUsers: false,
      loadedDepartments: false,
      error: '',
    }
  }
  return wecomRecipientPickers.value[key]
}

function getNotificationTarget(index: string | number): NotificationTarget | null {
  const numericIndex = Number(index)
  if (!Number.isFinite(numericIndex)) return null
  return targets.value[numericIndex] || null
}

function parseWeComRecipientIds(recipient: string): string[] {
  return String(recipient || '')
    .split('|')
    .map((item) => item.trim())
    .filter((item) => item.length > 0 && item !== '@all')
}

function updateWeComRecipientFromIds(index: string | number, userIds: string[]) {
  const target = getNotificationTarget(index)
  if (!target) return
  target.recipient = Array.from(new Set(userIds)).join('|')
}

async function loadWeComDepartments(index: string | number) {
  const state = getWeComPickerState(index)
  state.loadingDepartments = true
  state.error = ''
  try {
    const payload = await fetchWeComAppDepartments()
    state.departments = payload.departments
    state.loadedDepartments = true
    state.selectedDepartmentId = String(payload.departments[0]?.id ?? (state.selectedDepartmentId || '1'))
    await loadWeComUsers(index, state.selectedDepartmentId)
  } catch (error) {
    state.error = error instanceof Error ? error.message : t('tasks.form.notifications.wecomAppPicker.loadFailed')
  } finally {
    state.loadingDepartments = false
  }
}

async function loadWeComUsers(index: string | number, departmentId?: string | number) {
  const state = getWeComPickerState(index)
  const selectedDepartmentId = String(departmentId || state.selectedDepartmentId || '1')
  state.selectedDepartmentId = selectedDepartmentId
  state.loadingUsers = true
  state.error = ''
  try {
    const payload = await fetchWeComAppUsers(selectedDepartmentId, true)
    state.users = payload.users
  } catch (error) {
    state.error = error instanceof Error ? error.message : t('tasks.form.notifications.wecomAppPicker.loadFailed')
  } finally {
    state.loadingUsers = false
  }
}

function handleWeComDepartmentChange(index: string | number, event: Event) {
  const departmentId = (event.target as HTMLSelectElement).value
  void loadWeComUsers(index, departmentId)
}

function isWeComUserSelected(index: string | number, userid: string): boolean {
  const target = getNotificationTarget(index)
  if (!target) return false
  return parseWeComRecipientIds(target.recipient).includes(userid)
}

function toggleWeComUser(index: string | number, userid: string, checked: boolean) {
  const target = getNotificationTarget(index)
  if (!target) return
  const ids = parseWeComRecipientIds(target.recipient)
  if (checked) {
    ids.push(userid)
  } else {
    const removeIndex = ids.indexOf(userid)
    if (removeIndex >= 0) ids.splice(removeIndex, 1)
  }
  updateWeComRecipientFromIds(index, ids)
}

function setWeComRecipientAll(index: string | number) {
  const target = getNotificationTarget(index)
  if (!target) return
  target.recipient = '@all'
}

function handleAddNotificationTarget(event?: Event) {
  event?.preventDefault()
  event?.stopPropagation()
  addNotificationTarget()
}

function handleRemoveNotificationTarget(event: Event, index: string | number) {
  event.preventDefault()
  event.stopPropagation()
  removeNotificationTarget(index)
}
</script>

<template>
  <div class="grid gap-2 sm:grid-cols-4 sm:gap-4">
    <Label class="pt-1 sm:pt-2 sm:text-right">{{ t('tasks.form.notifications.title') }}</Label>
    <div class="space-y-3 sm:col-span-3">
      <p class="text-xs text-gray-500">{{ t('tasks.form.notifications.hint') }}</p>
      <div
        v-for="(target, index) in targets"
        :key="index"
        class="grid gap-2 rounded-md border p-3 md:grid-cols-[150px_minmax(260px,1fr)_150px_auto]"
      >
        <select
          :value="target.channel"
          class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          @change="(event) => updateNotificationTargetChannel(index, (event.target as HTMLSelectElement).value)"
        >
          <option v-for="option in notificationChannelOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <Input
          v-if="target.channel !== 'wecom_app'"
          v-model="target.recipient"
          :disabled="target.channel === 'default'"
          :placeholder="notificationRecipientPlaceholder(target.channel)"
        />
        <div v-else class="space-y-2">
          <Input
            v-model="target.recipient"
            :placeholder="notificationRecipientPlaceholder(target.channel)"
          />
          <div class="space-y-2 rounded-md border bg-muted/20 p-2">
            <div class="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                :disabled="getWeComPickerState(index).loadingDepartments"
                @click="loadWeComDepartments(index)"
              >
                {{
                  getWeComPickerState(index).loadedDepartments
                    ? t('tasks.form.notifications.wecomAppPicker.reloadContacts')
                    : t('tasks.form.notifications.wecomAppPicker.loadContacts')
                }}
              </Button>
              <Button type="button" variant="outline" size="sm" @click="setWeComRecipientAll(index)">
                {{ t('tasks.form.notifications.wecomAppPicker.allMembers', { at: '@' }) }}
              </Button>
              <select
                v-if="getWeComPickerState(index).departments.length > 0"
                :value="getWeComPickerState(index).selectedDepartmentId"
                class="h-9 min-w-[180px] rounded-md border border-input bg-background px-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                @change="(event) => handleWeComDepartmentChange(index, event)"
              >
                <option
                  v-for="department in getWeComPickerState(index).departments"
                  :key="department.id"
                  :value="String(department.id)"
                >
                  {{ department.name }}
                </option>
              </select>
            </div>
            <p v-if="getWeComPickerState(index).error" class="text-xs text-destructive">
              {{ getWeComPickerState(index).error }}
            </p>
            <p
              v-else-if="getWeComPickerState(index).loadingDepartments || getWeComPickerState(index).loadingUsers"
              class="text-xs text-gray-500"
            >
              {{ t('tasks.form.notifications.wecomAppPicker.loading') }}
            </p>
            <div v-if="getWeComPickerState(index).users.length > 0" class="grid max-h-40 gap-1 overflow-auto pr-1 sm:grid-cols-2">
              <label
                v-for="user in getWeComPickerState(index).users"
                :key="user.userid"
                class="flex min-w-0 items-center gap-2 rounded border px-2 py-1 text-sm"
              >
                <input
                  type="checkbox"
                  class="h-4 w-4"
                  :checked="isWeComUserSelected(index, user.userid)"
                  @change="(event) => toggleWeComUser(index, user.userid, (event.target as HTMLInputElement).checked)"
                >
                <span class="min-w-0 truncate">{{ user.name || user.userid }}</span>
                <span class="min-w-0 truncate text-xs text-gray-500">{{ user.userid }}</span>
              </label>
            </div>
            <p
              v-else-if="getWeComPickerState(index).loadedDepartments && !getWeComPickerState(index).loadingUsers && !getWeComPickerState(index).error"
              class="text-xs text-gray-500"
            >
              {{ t('tasks.form.notifications.wecomAppPicker.noUsers') }}
            </p>
            <p class="text-xs text-gray-500">
              {{ t('tasks.form.notifications.wecomAppPicker.manualFallback') }}
            </p>
          </div>
        </div>
        <Input v-model="target.label" :placeholder="t('tasks.form.notifications.labelPlaceholder')" />
        <Button type="button" variant="outline" size="sm" @click="handleRemoveNotificationTarget($event, index)">
          {{ t('common.delete') }}
        </Button>
      </div>
      <Button type="button" variant="outline" size="sm" @click="handleAddNotificationTarget">
        {{ t('tasks.form.notifications.add') }}
      </Button>
    </div>
  </div>
</template>
