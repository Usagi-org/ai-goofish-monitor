<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronLeft, ChevronRight, ImageOff, Maximize2, X, ZoomIn, ZoomOut } from 'lucide-vue-next'

interface Props {
  images: string[]
  title: string
  isSold?: boolean
  resetKey?: string | number
}

const props = defineProps<Props>()
const { t } = useI18n()

const trackRef = ref<HTMLElement | null>(null)
const prevBtnRef = ref<HTMLButtonElement | null>(null)
const nextBtnRef = ref<HTMLButtonElement | null>(null)
const lightboxCloseBtnRef = ref<HTMLButtonElement | null>(null)
const lightboxPrevBtnRef = ref<HTMLButtonElement | null>(null)
const lightboxNextBtnRef = ref<HTMLButtonElement | null>(null)

const activeIndex = ref(0)
const lastAnnouncedIndex = ref(0)
const liveAnnouncement = ref('')
const userInitiatedScroll = ref(false)
const isLightboxOpen = ref(false)
const isLightboxZoomed = ref(false)

let scrollRafId: number | null = null
let scrollEndTimer: ReturnType<typeof setTimeout> | null = null
let pendingTargetIndex: number | null = null
let pendingStartLeft: number | null = null
let lastLightboxTrigger: HTMLElement | null = null
let cleanupTrackListeners: (() => void) | null = null

const validImages = computed(() => {
  const seen = new Set<string>()
  const list: string[] = []
  for (const raw of props.images) {
    const url = typeof raw === 'string' ? raw.trim() : ''
    if (url && !seen.has(url)) {
      seen.add(url)
      list.push(url)
    }
  }
  return list
})

const currentImageUrl = computed(() => validImages.value[activeIndex.value] ?? validImages.value[0] ?? '')

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function readTrackIndex(): number {
  const track = trackRef.value
  const total = validImages.value.length
  if (!track || total <= 1 || track.clientWidth <= 0) return 0
  const raw = Math.round(track.scrollLeft / track.clientWidth)
  return Math.max(0, Math.min(total - 1, raw))
}

function announceSettledSlide(index: number) {
  if (!userInitiatedScroll.value) return
  userInitiatedScroll.value = false
  if (index === lastAnnouncedIndex.value || validImages.value.length <= 1) return
  lastAnnouncedIndex.value = index
  liveAnnouncement.value = t('results.detail.slideLabel', {
    current: index + 1,
    total: validImages.value.length,
  })
}

function handleScrollSettle() {
  const track = trackRef.value
  const settledIndex = readTrackIndex()
  if (
    track &&
    pendingTargetIndex !== null &&
    pendingStartLeft !== null &&
    Math.abs(track.scrollLeft - pendingStartLeft) < 2 &&
    settledIndex !== pendingTargetIndex
  ) {
    return
  }
  pendingTargetIndex = null
  pendingStartLeft = null
  activeIndex.value = settledIndex
  announceSettledSlide(settledIndex)
}

function handleUserScrollStart() {
  pendingTargetIndex = null
  pendingStartLeft = null
  userInitiatedScroll.value = true
}

function bindTrackListeners(track: HTMLElement | null) {
  if (cleanupTrackListeners) {
    cleanupTrackListeners()
    cleanupTrackListeners = null
  }
  if (!track || typeof window === 'undefined') return

  const supportsScrollEnd = 'onscrollend' in window

  const onScroll = () => {
    if (pendingTargetIndex === null && scrollRafId === null) {
      scrollRafId = window.requestAnimationFrame(() => {
        scrollRafId = null
        if (pendingTargetIndex !== null) return
        const nextIndex = readTrackIndex()
        if (nextIndex !== activeIndex.value) {
          activeIndex.value = nextIndex
        }
      })
    }
    if (!supportsScrollEnd) {
      if (scrollEndTimer !== null) clearTimeout(scrollEndTimer)
      scrollEndTimer = setTimeout(() => {
        scrollEndTimer = null
        handleScrollSettle()
      }, 140)
    }
  }

  const onScrollEnd = () => {
    handleScrollSettle()
  }

  track.addEventListener('scroll', onScroll, { passive: true })
  if (supportsScrollEnd) {
    track.addEventListener('scrollend', onScrollEnd, { passive: true })
  }

  cleanupTrackListeners = () => {
    track.removeEventListener('scroll', onScroll)
    if (supportsScrollEnd) {
      track.removeEventListener('scrollend', onScrollEnd)
    }
    if (scrollRafId !== null) {
      window.cancelAnimationFrame(scrollRafId)
      scrollRafId = null
    }
    if (scrollEndTimer !== null) {
      clearTimeout(scrollEndTimer)
      scrollEndTimer = null
    }
  }
}

watch(trackRef, (track) => {
  bindTrackListeners(track)
})

function goToSlide(index: number, options: { announce?: boolean; instant?: boolean } = {}) {
  const total = validImages.value.length
  if (total === 0) return
  const clamped = Math.max(0, Math.min(total - 1, index))
  const shouldAnnounce = options.announce !== false
  const focusNextAfterDisable =
    typeof document !== 'undefined' &&
    total > 1 &&
    clamped <= 0 &&
    document.activeElement === prevBtnRef.value
  const focusPrevAfterDisable =
    typeof document !== 'undefined' &&
    total > 1 &&
    clamped >= total - 1 &&
    document.activeElement === nextBtnRef.value

  userInitiatedScroll.value = shouldAnnounce
  activeIndex.value = clamped

  if (focusNextAfterDisable) {
    nextTick(() => nextBtnRef.value?.focus({ preventScroll: true }))
  } else if (focusPrevAfterDisable) {
    nextTick(() => prevBtnRef.value?.focus({ preventScroll: true }))
  }

  const track = trackRef.value
  if (track && track.clientWidth > 0) {
    const targetLeft = clamped * track.clientWidth
    const alreadyAtTarget = Math.abs(track.scrollLeft - targetLeft) < 2
    const instant = Boolean(options.instant) || prefersReducedMotion()
    if (alreadyAtTarget || instant) {
      pendingTargetIndex = null
      pendingStartLeft = null
      track.scrollTo({
        left: targetLeft,
        behavior: 'instant',
      })
      announceSettledSlide(clamped)
    } else {
      pendingTargetIndex = clamped
      pendingStartLeft = track.scrollLeft
      track.scrollTo({
        left: targetLeft,
        behavior: 'smooth',
      })
    }
  } else if (shouldAnnounce) {
    pendingTargetIndex = null
    pendingStartLeft = null
    announceSettledSlide(clamped)
  }
}

function handleTrackKeydown(event: KeyboardEvent) {
  if (event.target !== event.currentTarget) return
  if (validImages.value.length <= 1) return

  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    goToSlide(activeIndex.value - 1)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    goToSlide(activeIndex.value + 1)
  } else if (event.key === 'Home') {
    event.preventDefault()
    goToSlide(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    goToSlide(validImages.value.length - 1)
  }
}

function openLightbox(event: MouseEvent) {
  if (!currentImageUrl.value) return
  lastLightboxTrigger = event.currentTarget instanceof HTMLElement ? event.currentTarget : null
  isLightboxZoomed.value = false
  isLightboxOpen.value = true
  if (typeof window !== 'undefined') {
    window.addEventListener('keydown', handleLightboxKeydown, true)
  }
  nextTick(() => {
    lightboxCloseBtnRef.value?.focus({ preventScroll: true })
  })
}

function closeLightbox() {
  if (!isLightboxOpen.value) return
  isLightboxOpen.value = false
  isLightboxZoomed.value = false
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleLightboxKeydown, true)
  }
  nextTick(() => {
    if (lastLightboxTrigger && lastLightboxTrigger.isConnected) {
      lastLightboxTrigger.focus({ preventScroll: true })
    }
    lastLightboxTrigger = null
  })
}

function handleLightboxKeydown(event: KeyboardEvent) {
  if (!isLightboxOpen.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    closeLightbox()
  } else if (event.key === 'ArrowLeft' && validImages.value.length > 1) {
    event.preventDefault()
    stepLightbox(-1)
  } else if (event.key === 'ArrowRight' && validImages.value.length > 1) {
    event.preventDefault()
    stepLightbox(1)
  }
}

function stepLightbox(delta: number) {
  const total = validImages.value.length
  const nextIndex = Math.max(0, Math.min(total - 1, activeIndex.value + delta))
  const focusNextAfterDisable =
    typeof document !== 'undefined' &&
    total > 1 &&
    nextIndex <= 0 &&
    document.activeElement === lightboxPrevBtnRef.value
  const focusPrevAfterDisable =
    typeof document !== 'undefined' &&
    total > 1 &&
    nextIndex >= total - 1 &&
    document.activeElement === lightboxNextBtnRef.value

  isLightboxZoomed.value = false
  goToSlide(nextIndex, { instant: true })

  if (focusNextAfterDisable) {
    nextTick(() => lightboxNextBtnRef.value?.focus({ preventScroll: true }))
  } else if (focusPrevAfterDisable) {
    nextTick(() => lightboxPrevBtnRef.value?.focus({ preventScroll: true }))
  }
}

watch(
  [() => props.resetKey, () => props.images.join('|')],
  () => {
    if (isLightboxOpen.value && typeof window !== 'undefined') {
      window.removeEventListener('keydown', handleLightboxKeydown, true)
    }
    pendingTargetIndex = null
    pendingStartLeft = null
    isLightboxOpen.value = false
    isLightboxZoomed.value = false
    activeIndex.value = 0
    lastAnnouncedIndex.value = 0
    liveAnnouncement.value = ''
    userInitiatedScroll.value = false
    nextTick(() => {
      if (trackRef.value) {
        trackRef.value.scrollTo({ left: 0, behavior: 'instant' })
      }
    })
  }
)

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleLightboxKeydown, true)
  }
  if (cleanupTrackListeners) {
    cleanupTrackListeners()
    cleanupTrackListeners = null
  }
})

defineExpose({
  isLightboxOpen,
  closeLightbox,
})
</script>

<template>
  <section
    class="relative select-none"
    aria-roledescription="carousel"
    :aria-label="t('results.detail.galleryLabel', { title: props.title })"
  >
    <div
      v-if="validImages.length === 0"
      class="flex h-[260px] sm:h-[320px] flex-col items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-100 text-slate-400"
    >
      <ImageOff class="h-8 w-8" aria-hidden="true" />
      <span class="text-xs font-medium">{{ t('results.detail.noImages') }}</span>
    </div>

    <template v-else>
      <div class="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-950">
        <!-- Prev / Next buttons MUST precede the track in DOM order -->
        <button
          v-if="validImages.length > 1"
          ref="prevBtnRef"
          type="button"
          class="carousel-nav-btn left-2.5"
          :disabled="activeIndex <= 0"
          :aria-label="t('results.detail.prevImage')"
          @click="goToSlide(activeIndex - 1)"
        >
          <ChevronLeft class="h-5 w-5" aria-hidden="true" />
        </button>

        <button
          v-if="validImages.length > 1"
          ref="nextBtnRef"
          type="button"
          class="carousel-nav-btn right-2.5"
          :disabled="activeIndex >= validImages.length - 1"
          :aria-label="t('results.detail.nextImage')"
          @click="goToSlide(activeIndex + 1)"
        >
          <ChevronRight class="h-5 w-5" aria-hidden="true" />
        </button>

        <div
          ref="trackRef"
          class="carousel-track focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
          tabindex="0"
          @pointerdown="handleUserScrollStart"
          @touchstart.passive="handleUserScrollStart"
          @wheel.passive="handleUserScrollStart"
          @keydown="handleTrackKeydown"
        >
          <div
            v-for="(src, index) in validImages"
            :key="`${src}-${index}`"
            role="group"
            aria-roledescription="slide"
            :aria-label="t('results.detail.slideLabel', { current: index + 1, total: validImages.length })"
            class="carousel-slide flex h-[280px] sm:h-[360px] items-center justify-center bg-slate-950"
          >
            <button
              type="button"
              class="group/zoom relative flex h-full w-full cursor-zoom-in items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white"
              :aria-label="t('results.detail.zoomImage')"
              @click="openLightbox($event)"
            >
              <img
                :src="src"
                :alt="`${props.title} (${index + 1}/${validImages.length})`"
                class="max-h-full max-w-full object-contain transition-transform duration-300 group-hover/zoom:scale-[1.02]"
                :class="{ 'grayscale-[35%]': props.isSold }"
                :loading="index === 0 ? 'eager' : 'lazy'"
              />
            </button>
          </div>
        </div>

        <div
          v-if="props.isSold"
          class="pointer-events-none absolute top-3 left-3 rounded-full border border-white/50 bg-slate-900/80 px-3 py-1 text-xs font-bold tracking-wider text-white backdrop-blur-sm"
        >
          {{ t('results.card.soldStamp') }}
        </div>

        <div class="pointer-events-none absolute right-3 bottom-3 flex items-center gap-1.5">
          <span class="inline-flex items-center gap-1 rounded-full bg-slate-900/75 px-2.5 py-1 text-[11px] font-medium text-white/90 backdrop-blur-sm">
            <Maximize2 class="h-3 w-3" aria-hidden="true" />
            {{ t('results.detail.tapToZoom') }}
          </span>
          <span
            v-if="validImages.length > 1"
            class="rounded-full bg-slate-900/80 px-2.5 py-1 text-[11px] font-semibold tabular-nums text-white backdrop-blur-sm"
          >
            {{ activeIndex + 1 }} / {{ validImages.length }}
          </span>
        </div>
      </div>

      <p class="sr-only" role="status" aria-live="polite">{{ liveAnnouncement }}</p>

      <div
        v-if="validImages.length > 1"
        class="mt-2.5 flex items-center gap-2 overflow-x-auto px-0.5 py-1"
      >
        <button
          v-for="(src, index) in validImages"
          :key="`thumb-${src}-${index}`"
          type="button"
          class="relative h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-slate-100 transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          :class="
            index === activeIndex
              ? 'scale-[1.03] border-2 border-primary ring-2 ring-primary/35 opacity-100 shadow-sm'
              : 'border border-slate-200 opacity-70 hover:opacity-100'
          "
          :aria-current="index === activeIndex ? 'true' : undefined"
          :aria-label="t('results.detail.goToImage', { index: index + 1 })"
          @click="goToSlide(index)"
        >
          <img
            :src="src"
            alt=""
            class="h-full w-full object-cover"
            loading="lazy"
          />
          <span
            v-if="index === activeIndex"
            aria-hidden="true"
            class="absolute inset-x-1 bottom-0.5 h-1 rounded-full bg-primary"
          />
        </button>
      </div>

      <!-- Full-resolution lightbox rendered inside the dialog top layer -->
      <div
        v-if="isLightboxOpen"
        class="fixed inset-0 z-50 flex flex-col bg-slate-950/95 text-white"
        role="region"
        :aria-label="t('results.detail.lightboxLabel')"
        @click.self="closeLightbox"
      >
        <div class="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <span class="text-sm font-semibold tabular-nums text-white/90">
            {{ activeIndex + 1 }} / {{ validImages.length }}
          </span>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex h-10 items-center gap-1.5 rounded-full border border-white/25 bg-white/10 px-3 text-xs font-medium text-white transition-all hover:bg-white/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              @click="isLightboxZoomed = !isLightboxZoomed"
            >
              <ZoomOut v-if="isLightboxZoomed" class="h-4 w-4" aria-hidden="true" />
              <ZoomIn v-else class="h-4 w-4" aria-hidden="true" />
              <span>{{ isLightboxZoomed ? t('results.detail.zoomFit') : t('results.detail.zoomActual') }}</span>
            </button>
            <button
              ref="lightboxCloseBtnRef"
              type="button"
              class="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/25 bg-white/10 text-white transition-all hover:bg-white/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
              :aria-label="t('results.detail.closeLightbox')"
              @click="closeLightbox"
            >
              <X class="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div
          class="relative flex min-h-0 flex-1 overflow-auto p-4"
          @click.self="closeLightbox"
        >
          <button
            v-if="validImages.length > 1"
            ref="lightboxPrevBtnRef"
            type="button"
            class="lightbox-nav-btn left-3"
            :disabled="activeIndex <= 0"
            :aria-label="t('results.detail.prevImage')"
            @click.stop="stepLightbox(-1)"
          >
            <ChevronLeft class="h-6 w-6" aria-hidden="true" />
          </button>

          <img
            :src="currentImageUrl"
            :alt="`${props.title} (${activeIndex + 1}/${validImages.length})`"
            class="m-auto shrink-0 rounded-lg transition-transform duration-200 select-none"
            :class="
              isLightboxZoomed
                ? 'max-h-none max-w-none cursor-zoom-out'
                : 'max-h-full max-w-full object-contain cursor-zoom-in'
            "
            @click.stop="isLightboxZoomed = !isLightboxZoomed"
          />

          <button
            v-if="validImages.length > 1"
            ref="lightboxNextBtnRef"
            type="button"
            class="lightbox-nav-btn right-3"
            :disabled="activeIndex >= validImages.length - 1"
            :aria-label="t('results.detail.nextImage')"
            @click.stop="stepLightbox(1)"
          >
            <ChevronRight class="h-6 w-6" aria-hidden="true" />
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.carousel-track {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  overscroll-behavior-x: contain;
  touch-action: manipulation;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.carousel-track::-webkit-scrollbar {
  display: none;
}

@media (prefers-reduced-motion: no-preference) {
  .carousel-track {
    scroll-behavior: smooth;
  }
}

.carousel-slide {
  flex: 0 0 100%;
  scroll-snap-align: center;
  scroll-snap-stop: always;
}

.carousel-nav-btn {
  position: absolute;
  top: 50%;
  z-index: 10;
  display: inline-flex;
  height: 2.5rem;
  width: 2.5rem;
  transform: translateY(-50%);
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(15, 23, 42, 0.72);
  color: #ffffff;
  touch-action: manipulation;
  transition: background-color 150ms ease, opacity 150ms ease, transform 120ms ease;
}

.carousel-nav-btn:hover:not(:disabled) {
  background: rgba(15, 23, 42, 0.92);
}

.carousel-nav-btn:active:not(:disabled) {
  transform: translateY(-50%) scale(0.94);
}

.carousel-nav-btn:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}

.carousel-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.lightbox-nav-btn {
  position: fixed;
  top: 50%;
  z-index: 60;
  display: inline-flex;
  height: 2.75rem;
  width: 2.75rem;
  transform: translateY(-50%);
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.32);
  background: rgba(15, 23, 42, 0.8);
  color: #ffffff;
  touch-action: manipulation;
  transition: background-color 150ms ease, opacity 150ms ease, transform 120ms ease;
}

.lightbox-nav-btn:hover:not(:disabled) {
  background: rgba(30, 41, 59, 0.95);
}

.lightbox-nav-btn:active:not(:disabled) {
  transform: translateY(-50%) scale(0.94);
}

.lightbox-nav-btn:focus-visible {
  outline: 2px solid #ffffff;
  outline-offset: 2px;
}

.lightbox-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
