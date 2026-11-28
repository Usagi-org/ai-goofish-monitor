export interface GoofishLinks {
  itemId: string | null
  webUrl: string
  shareUrl: string
  appSchemeUrl: string | null
  appFallbackSchemeUrl: string | null
}

export interface GoofishLaunchPlan {
  mode: 'app' | 'web'
  primaryUrl: string
  fallbackUrl: string | null
}

const NUMERIC_ID_RE = /^\d+$/

function normalizeCandidateId(value: unknown): string | null {
  if (typeof value === 'number' && Number.isSafeInteger(value) && value > 0) {
    return String(value)
  }
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return NUMERIC_ID_RE.test(trimmed) ? trimmed : null
}

function extractIdFromSearchParams(params: URLSearchParams): string | null {
  for (const key of ['id', 'itemId', 'item_id']) {
    const candidate = normalizeCandidateId(params.get(key))
    if (candidate) return candidate
  }

  const bfp = params.get('bfp')
  if (bfp) {
    const rawMatch = bfp.match(/["'](?:id|itemId|item_id)["']\s*:\s*"?(\d+)"?/)
    if (rawMatch?.[1]) {
      const candidate = normalizeCandidateId(rawMatch[1])
      if (candidate) return candidate
    }
    try {
      const parsed = JSON.parse(bfp) as Record<string, unknown> | null
      if (parsed && typeof parsed === 'object') {
        const candidate = normalizeCandidateId(parsed.id ?? parsed.itemId ?? parsed.item_id)
        if (candidate) return candidate
      }
    } catch {
      return null
    }
  }

  return null
}

function normalizeHttpUrl(raw?: string): string | null {
  if (!raw) return null
  const trimmed = raw.trim()
  if (!trimmed) return null
  if (trimmed.startsWith('//')) {
    return `https:${trimmed}`
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed
  }
  return null
}

export function extractGoofishItemId(url?: string, fallbackId?: string): string | null {
  if (url && typeof url === 'string') {
    const trimmed = url.trim()
    if (trimmed) {
      const normalized = trimmed.startsWith('//') ? `https:${trimmed}` : trimmed
      try {
        const parsed = new URL(normalized)
        const fromSearch = extractIdFromSearchParams(parsed.searchParams)
        if (fromSearch) return fromSearch

        if (parsed.hash) {
          const hashQueryIndex = parsed.hash.indexOf('?')
          if (hashQueryIndex !== -1) {
            const fromHash = extractIdFromSearchParams(new URLSearchParams(parsed.hash.slice(hashQueryIndex + 1)))
            if (fromHash) return fromHash
          }
        }

        const pathMatch = parsed.pathname.match(/\/item\/(\d+)/i)
        if (pathMatch?.[1]) return pathMatch[1]
      } catch {
      }

      const regexMatch = trimmed.match(/(?:[?&#](?:id|itemId|item_id)=|\/item\/)(\d+)(?=$|[&#/?])/)
      if (regexMatch?.[1]) return regexMatch[1]
    }
  }

  return normalizeCandidateId(fallbackId)
}

export function buildGoofishLinks(input: { itemId?: string; url?: string }): GoofishLinks {
  const itemId = extractGoofishItemId(input.url, input.itemId)
  const normalizedHttp = normalizeHttpUrl(input.url)

  const webUrl = normalizedHttp || (itemId ? `https://www.goofish.com/item?id=${encodeURIComponent(itemId)}` : '')
  const shareUrl = itemId
    ? `https://pages.goofish.com/sharexy?loadingVisible=false&bft=item&bfs=idlepc.item&spm=a21ybx.item.0.0&bfp=${encodeURIComponent(`{"id":${itemId}}`)}`
    : webUrl
  const appSchemeUrl = itemId
    ? `fleamarket://awesome_detail?itemId=${encodeURIComponent(itemId)}&flutter=true`
    : null
  const appFallbackSchemeUrl = itemId
    ? `fleamarket://itemDetail?itemId=${encodeURIComponent(itemId)}`
    : null

  return {
    itemId,
    webUrl,
    shareUrl,
    appSchemeUrl,
    appFallbackSchemeUrl,
  }
}

export function isIosDevice(ua?: string): boolean {
  const userAgent = ua ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  if (/iPhone|iPad|iPod/i.test(userAgent)) {
    return true
  }
  if (
    ua === undefined &&
    typeof navigator !== 'undefined' &&
    navigator.platform === 'MacIntel' &&
    navigator.maxTouchPoints > 1
  ) {
    return true
  }
  return false
}

export function isMobileDevice(ua?: string): boolean {
  if (isIosDevice(ua)) return true
  const userAgent = ua ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  return /Android|Mobile|HarmonyOS|Windows Phone|webOS|BlackBerry/i.test(userAgent)
}

export function resolveGoofishLaunchPlan(
  links: GoofishLinks,
  options: { preferApp?: boolean; userAgent?: string } = {}
): GoofishLaunchPlan {
  const shouldUseApp =
    options.preferApp !== false &&
    Boolean(links.appSchemeUrl) &&
    isMobileDevice(options.userAgent)

  if (shouldUseApp && links.appSchemeUrl) {
    return {
      mode: 'app',
      primaryUrl: links.appSchemeUrl,
      fallbackUrl: links.shareUrl || links.webUrl || null,
    }
  }

  return {
    mode: 'web',
    primaryUrl: links.webUrl || links.shareUrl || '',
    fallbackUrl: null,
  }
}

export function openGoofishListing(
  links: GoofishLinks,
  options: { preferApp?: boolean; fallbackDelayMs?: number } = {}
): 'app' | 'web' | 'none' {
  if (typeof window === 'undefined') return 'none'

  const plan = resolveGoofishLaunchPlan(links, { preferApp: options.preferApp })
  if (!plan.primaryUrl) return 'none'

  if (plan.mode === 'web') {
    window.open(plan.primaryUrl, '_blank', 'noopener,noreferrer')
    return 'web'
  }

  const delayMs = options.fallbackDelayMs ?? 1400
  let settled = false
  let fallbackTimer: ReturnType<typeof setTimeout> | undefined

  const cleanup = () => {
    if (settled) return
    settled = true
    if (fallbackTimer !== undefined) {
      clearTimeout(fallbackTimer)
      fallbackTimer = undefined
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    window.removeEventListener('pagehide', cleanup)
  }

  const handleVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      cleanup()
    }
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('pagehide', cleanup, { once: true })

  fallbackTimer = setTimeout(() => {
    const stillVisible = document.visibilityState === 'visible'
    cleanup()
    if (stillVisible && plan.fallbackUrl) {
      window.location.href = plan.fallbackUrl
    }
  }, delayMs)

  window.location.href = plan.primaryUrl
  return 'app'
}

function legacyCopy(text: string, container?: HTMLElement | null): boolean {
  if (typeof document === 'undefined') return false

  const previousFocus = document.activeElement
  const host =
    container ??
    (previousFocus instanceof HTMLElement ? previousFocus.closest('dialog') : null) ??
    document.querySelector<HTMLDialogElement>('dialog[open]') ??
    document.body

  if (!host) return false

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.readOnly = true
  textarea.tabIndex = -1
  textarea.setAttribute('aria-hidden', 'true')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.padding = '0'
  textarea.style.border = '0'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  textarea.style.fontSize = '16px'

  host.appendChild(textarea)

  let copied = false
  try {
    textarea.focus({ preventScroll: true })
    textarea.select()
    textarea.setSelectionRange(0, text.length)
    copied = document.execCommand('copy')
  } catch {
    copied = false
  } finally {
    textarea.remove()
    if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
      previousFocus.focus({ preventScroll: true })
    }
  }

  return copied
}

export async function copyTextToClipboard(
  text: string,
  container?: HTMLElement | null
): Promise<boolean> {
  if (!text) return false

  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall back to execCommand for non-HTTPS LAN / NAS deployments.
    }
  }

  return legacyCopy(text, container)
}
