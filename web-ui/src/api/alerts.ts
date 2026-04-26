import type { AlertLevel } from '@/types/task.d.ts'
import { http } from '@/lib/http'

export interface Alert {
  id: number
  task_name: string
  keyword: string
  alert_type: string
  alert_level: AlertLevel
  message: string
  previous_avg_price: number | null
  current_avg_price: number | null
  drop_percentage: number | null
  consecutive_scans: number
  snapshot_time: string
  is_read: boolean
  is_dismissed: boolean
  created_at: string
  updated_at: string
  details?: Record<string, unknown>
}

export interface AlertSummary {
  task_name: string
  has_active_alert: boolean
  active_alert_count: number
  latest_alert_level: AlertLevel | null
  latest_alert_message: string | null
  latest_alert_time: string | null
}

export async function getAllAlerts(
  includeDismissed: boolean = false,
  limit: number = 100
): Promise<Alert[]> {
  const params = new URLSearchParams({
    include_dismissed: String(includeDismissed),
    limit: String(limit),
  })
  return await http(`/api/alerts?${params}`)
}

export async function getTaskAlerts(
  taskName: string,
  includeDismissed: boolean = false,
  includeRead: boolean = true,
  limit: number = 50
): Promise<Alert[]> {
  const params = new URLSearchParams({
    include_dismissed: String(includeDismissed),
    include_read: String(includeRead),
    limit: String(limit),
  })
  return await http(`/api/alerts/task/${encodeURIComponent(taskName)}?${params}`)
}

export async function getTaskAlertSummary(taskName: string): Promise<AlertSummary> {
  return await http(`/api/alerts/summary/${encodeURIComponent(taskName)}`)
}

export async function getBatchAlertSummaries(taskNames: string[]): Promise<Record<string, AlertSummary>> {
  return await http('/api/alerts/summary/batch', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(taskNames),
  })
}

export async function getAlert(alertId: number): Promise<Alert> {
  return await http(`/api/alerts/${alertId}`)
}

export async function markAlertAsRead(alertId: number): Promise<{ message: string; alert: Alert }> {
  return await http(`/api/alerts/${alertId}/read`, {
    method: 'POST',
  })
}

export async function dismissAlert(alertId: number): Promise<{ message: string; alert: Alert }> {
  return await http(`/api/alerts/${alertId}/dismiss`, {
    method: 'POST',
  })
}

export async function dismissAllAlertsForTask(taskName: string): Promise<{
  message: string
  dismissed_count: number
  task_name: string
}> {
  return await http(`/api/alerts/task/${encodeURIComponent(taskName)}/dismiss-all`, {
    method: 'POST',
  })
}

export interface CheckPriceTrendOptions {
  taskName: string
  keyword: string
  consecutiveScans?: number
  dropThreshold?: number
  forceCreate?: boolean
  sendNotification?: boolean
}

export async function checkPriceTrend(options: CheckPriceTrendOptions): Promise<{
  message: string
  task_name: string
  keyword: string
  alert_created: boolean
  alert?: Alert
  notification_results?: Record<string, { channel: string; label: string; success: boolean; message: string }>
}> {
  const params = new URLSearchParams({
    task_name: options.taskName,
    keyword: options.keyword,
  })
  if (options.consecutiveScans !== undefined) {
    params.set('consecutive_scans', String(options.consecutiveScans))
  }
  if (options.dropThreshold !== undefined) {
    params.set('drop_threshold', String(options.dropThreshold))
  }
  if (options.forceCreate !== undefined) {
    params.set('force_create', String(options.forceCreate))
  }
  if (options.sendNotification !== undefined) {
    params.set('send_notification', String(options.sendNotification))
  }
  return await http(`/api/alerts/check?${params}`, {
    method: 'POST',
  })
}
