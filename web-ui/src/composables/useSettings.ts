import { ref, onMounted, watch } from 'vue'
import * as settingsApi from '@/api/settings'
import type {
  NotificationSettings,
  NotificationSettingsUpdate,
  NotificationTestResponse,
  AiSettings,
  RotationSettings,
  SystemStatus
} from '@/api/settings'

export function useSettings() {
  const notificationSettings = ref<NotificationSettings>({})
  const aiSettings = ref<AiSettings>({})
  const rotationSettings = ref<RotationSettings>({})
  const systemStatus = ref<SystemStatus | null>(null)
  const isReady = ref(false)
  
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<Error | null>(null)

  const aiModels = ref<string[]>([])
  const isLoadingModels = ref(false)
  const hasLoadedModels = ref(false)
  const modelListError = ref<string | null>(null)
  let modelRequestVersion = 0

  watch(
    () => [aiSettings.value.OPENAI_BASE_URL, aiSettings.value.OPENAI_API_KEY, aiSettings.value.PROXY_URL],
    () => {
      modelRequestVersion++
      aiModels.value = []
      hasLoadedModels.value = false
      modelListError.value = null
      isLoadingModels.value = false
    },
    { flush: 'sync' },
  )

  async function loadAiModels() {
    const version = ++modelRequestVersion
    isLoadingModels.value = true
    hasLoadedModels.value = false
    modelListError.value = null
    aiModels.value = []
    try {
      const result = await settingsApi.getAiModels({
        OPENAI_BASE_URL: aiSettings.value.OPENAI_BASE_URL,
        OPENAI_API_KEY: aiSettings.value.OPENAI_API_KEY?.trim() || undefined,
        PROXY_URL: aiSettings.value.PROXY_URL,
      })
      if (version !== modelRequestVersion) return
      if (!result.success) throw new Error(result.message)
      aiModels.value = result.models
      hasLoadedModels.value = true
    } catch (e) {
      if (version === modelRequestVersion) modelListError.value = (e as Error).message
    } finally {
      if (version === modelRequestVersion) isLoadingModels.value = false
    }
  }

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

  async function saveNotificationSettings(payload: NotificationSettingsUpdate) {
    isSaving.value = true
    try {
      await settingsApi.updateNotificationSettings(payload)
      const [notif, status] = await Promise.all([
        settingsApi.getNotificationSettings(),
        settingsApi.getSystemStatus()
      ])
      notificationSettings.value = notif
      systemStatus.value = status
    } catch (e) {
      if (e instanceof Error) error.value = e
      throw e
    } finally {
      isSaving.value = false
    }
  }

  async function testNotification(payload: {
    channel?: string
    settings: NotificationSettingsUpdate
  }): Promise<NotificationTestResponse> {
    isSaving.value = true
    try {
      return await settingsApi.testNotificationSettings(payload)
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
      const payload = { ...aiSettings.value }
      const apiKey = (payload.OPENAI_API_KEY || '').trim()
      if (apiKey) {
        payload.OPENAI_API_KEY = apiKey
      } else {
        delete payload.OPENAI_API_KEY
      }
      await settingsApi.updateAiSettings(payload)
      if (aiSettings.value.OPENAI_API_KEY) {
        aiSettings.value.OPENAI_API_KEY = ''
      }
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
      const payload = { ...aiSettings.value }
      const apiKey = (payload.OPENAI_API_KEY || '').trim()
      if (apiKey) {
        payload.OPENAI_API_KEY = apiKey
      } else {
        delete payload.OPENAI_API_KEY
      }
      const res = await settingsApi.testAiSettings(payload)
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
    aiModels,
    isLoadingModels,
    hasLoadedModels,
    modelListError,
    loadAiModels,
    rotationSettings,
    systemStatus,
    isLoading,
    isSaving,
    isReady,
    error,
    fetchAll,
    saveNotificationSettings,
    testNotification,
    saveAiSettings,
    saveRotationSettings,
    testAiConnection,
    refreshStatus,
  }
}
