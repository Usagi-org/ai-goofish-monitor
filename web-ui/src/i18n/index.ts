import { computed, watch } from 'vue'
import { createI18n, useI18n } from 'vue-i18n'
import zhCN from '@/i18n/messages/zh-CN'
import enUS from '@/i18n/messages/en-US'

export type AppLocale = 'zh-CN' | 'en-US'

const LOCALE_STORAGE_KEY = 'app_locale'
const DEFAULT_LOCALE: AppLocale = 'zh-CN'
const SUPPORTED_LOCALES: AppLocale[] = ['zh-CN', 'en-US']

function resolveInitialLocale(): AppLocale {
  const saved = localStorage.getItem(LOCALE_STORAGE_KEY)
  if (saved && SUPPORTED_LOCALES.includes(saved as AppLocale)) {
    return saved as AppLocale
  }
  const browserLocale = navigator.language.toLowerCase()
  return browserLocale.startsWith('zh') ? 'zh-CN' : 'en-US'
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export function setLocale(locale: AppLocale) {
  i18n.global.locale.value = locale
}

export function useLocale() {
  const { locale } = useI18n()
  const currentLocale = computed(() => locale.value as AppLocale)

  function toggleLocale(nextLocale: AppLocale) {
    locale.value = nextLocale
  }

  return {
    locale: currentLocale,
    toggleLocale,
    supportedLocales: SUPPORTED_LOCALES,
  }
}

export function t(key: string, params?: Record<string, unknown>) {
  return params ? i18n.global.t(key, params) : i18n.global.t(key)
}

export function formatNumber(value: number, options?: Intl.NumberFormatOptions) {
  return new Intl.NumberFormat(i18n.global.locale.value, options).format(value)
}

export function formatDateTime(
  value: string | Date,
  options: Intl.DateTimeFormatOptions = {},
) {
  const date = value instanceof Date ? value : new Date(value)
  return new Intl.DateTimeFormat(i18n.global.locale.value, options).format(date)
}

export function formatRelativeTimeFromNow(value: string | null | undefined) {
  if (!value) return t('time.justNow')
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return t('time.justNow')
  const diffMinutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000))
  if (diffMinutes < 60) return t('time.minutesAgo', { count: diffMinutes })
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return t('time.hoursAgo', { count: diffHours })
  const diffDays = Math.round(diffHours / 24)
  return t('time.daysAgo', { count: diffDays })
}

watch(
  () => i18n.global.locale.value,
  (locale) => {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    document.documentElement.lang = locale
  },
  { immediate: true },
)
