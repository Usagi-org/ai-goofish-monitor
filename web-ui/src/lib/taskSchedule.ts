import { t } from '@/i18n'

const SECOND_MS = 1000
const MINUTE_MS = 60 * SECOND_MS
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function padNumber(value: number): string {
  return String(value).padStart(2, '0')
}

export function formatNextRunAbsolute(value: string | null | undefined): string {
  const date = parseDate(value)
  if (!date) return t('time.scheduled')
  return `${padNumber(date.getMonth() + 1)}-${padNumber(date.getDate())} ${padNumber(date.getHours())}:${padNumber(date.getMinutes())}:${padNumber(date.getSeconds())}`
}

export function formatCountdown(
  value: string | null | undefined,
  nowMs: number,
): string | null {
  const date = parseDate(value)
  if (!date) return null

  const diff = date.getTime() - nowMs
  if (diff <= 0) return t('time.upcoming')

  const days = Math.floor(diff / DAY_MS)
  const hours = Math.floor((diff % DAY_MS) / HOUR_MS)
  const minutes = Math.floor((diff % HOUR_MS) / MINUTE_MS)
  const seconds = Math.floor((diff % MINUTE_MS) / SECOND_MS)

  if (days > 0) return t('time.countdownDays', { days, hours, minutes })
  if (hours > 0) return t('time.countdownHours', { hours, minutes, seconds })
  if (minutes > 0) return t('time.countdownMinutes', { minutes, seconds })
  return t('time.countdownSeconds', { seconds })
}
