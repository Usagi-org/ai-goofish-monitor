import { http } from '@/lib/http'

export interface NotificationSettings {
  NTFY_TOPIC_URL?: string
  GOTIFY_URL?: string
  GOTIFY_TOKEN?: string
  BARK_URL?: string
  WX_BOT_URL?: string
  TELEGRAM_BOT_TOKEN?: string
  TELEGRAM_CHAT_ID?: string
  WEBHOOK_URL?: string
  WEBHOOK_METHOD?: string
  WEBHOOK_HEADERS?: string
  WEBHOOK_CONTENT_TYPE?: string
  WEBHOOK_QUERY_PARAMETERS?: string
  WEBHOOK_BODY?: string
  PCURL_TO_MOBILE?: boolean
}

export interface AiSettings {
  OPENAI_API_KEY?: string
  OPENAI_BASE_URL?: string
  OPENAI_MODEL_NAME?: string
  PROXY_URL?: string
}

export interface RotationSettings {
  PROXY_ROTATION_ENABLED?: boolean
  PROXY_ROTATION_MODE?: string
  PROXY_POOL?: string
  PROXY_ROTATION_RETRY_LIMIT?: number
  PROXY_BLACKLIST_TTL?: number
}

export interface SystemStatus {
  scraper_running: boolean
  login_state_file: {
    exists: boolean
    path: string
  }
  env_file: {
    exists: boolean
    openai_api_key_set: boolean
    openai_base_url_set: boolean
    openai_model_name_set: boolean
    ntfy_topic_url_set: boolean
    gotify_url_set: boolean
    gotify_token_set: boolean
    bark_url_set: boolean
  }
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  return await http('/api/settings/notifications')
}

export async function updateNotificationSettings(settings: NotificationSettings): Promise<void> {
  await http('/api/settings/notifications', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  })
}

export async function getAiSettings(): Promise<AiSettings> {
  return await http('/api/settings/ai')
}

export async function updateAiSettings(settings: AiSettings): Promise<void> {
  await http('/api/settings/ai', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  })
}

export async function getRotationSettings(): Promise<RotationSettings> {
  return await http('/api/settings/rotation')
}

export async function updateRotationSettings(settings: RotationSettings): Promise<void> {
  await http('/api/settings/rotation', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  })
}

export async function testAiSettings(settings: AiSettings): Promise<{ success: boolean; message: string; response?: string }> {
  return await http('/api/settings/ai/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  })
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return await http('/api/settings/status')
}

export async function updateLoginState(content: string): Promise<{ message: string }> {
  return await http('/api/login-state', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  })
}

export async function deleteLoginState(): Promise<{ message: string }> {
  return await http('/api/login-state', { method: 'DELETE' })
}
