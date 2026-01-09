import { ref, onMounted } from 'vue'
import * as settingsApi from '@/api/settings'
import type { NotificationSettings, AiSettings, RotationSettings, SystemStatus } from '@/api/settings'

export function useSettings() {
  const notificationSettings = ref<NotificationSettings>({})
  const aiSettings = ref<AiSettings>({})
  const rotationSettings = ref<RotationSettings>({})
  const systemStatus = ref<SystemStatus | null>(null)
  const isReady = ref(false)
  
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<Error | null>(null)

  async function fetchAll() {
    isLoading.value = true
    error.value = null
    try {
      const [notif, ai, rotation, status] = await Promise.all([
        settingsApi.getNotificationSettings(),
        settingsApi.getAiSettings(),
        settingsApi.getRotationSettings(),
        settingsApi.getSystemStatus()
      ])
      notificationSettings.value = notif
      aiSettings.value = ai
      rotationSettings.value = rotation
      systemStatus.value = status
    } catch (e) {
      if (e instanceof Error) error.value = e
    } finally {
      isLoading.value = false
      isReady.value = true
    }
  }

  async function refreshStatus() {
    isLoading.value = true
    error.value = null
    try {
      systemStatus.value = await settingsApi.getSystemStatus()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function saveNotificationSettings() {
    isSaving.value = true
    try {
      await settingsApi.updateNotificationSettings(notificationSettings.value)
      // Refresh status as env file changed
      systemStatus.value = await settingsApi.getSystemStatus()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveAiSettings() {
    isSaving.value = true
    try {
      await settingsApi.updateAiSettings(aiSettings.value)
      // Refresh status
      systemStatus.value = await settingsApi.getSystemStatus()
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function saveRotationSettings() {
    isSaving.value = true
    try {
      await settingsApi.updateRotationSettings(rotationSettings.value)
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function testAiConnection() {
    isSaving.value = true
    try {
      const res = await settingsApi.testAiSettings(aiSettings.value)
      return res
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  onMounted(fetchAll)

  return {
    notificationSettings,
    aiSettings,
    rotationSettings,
    systemStatus,
    isLoading,
    isSaving,
    isReady,
    error,
    fetchAll,
    saveNotificationSettings,
    saveAiSettings,
    saveRotationSettings,
    testAiConnection,
    refreshStatus,
  }
}
