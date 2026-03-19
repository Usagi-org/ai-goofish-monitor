<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import TheHeader from '@/components/layout/TheHeader.vue'
import TheSidebar from '@/components/layout/TheSidebar.vue'
import Toaster from '@/components/ui/toast/Toaster.vue'
import { useMobileNav } from '@/composables/useMobileNav'

const { isMobileNavOpen, closeMobileNav } = useMobileNav()
const { t } = useI18n()
</script>

<template>
  <div class="relative min-h-screen w-full flex flex-col bg-slate-50 selection:bg-primary/20">
    <!-- 背景装饰渐变 -->
    <div class="fixed inset-0 pointer-events-none overflow-hidden">
      <div class="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full bg-primary/5 blur-[120px] animate-pulse"></div>
      <div class="absolute top-[20%] -right-[5%] w-[30%] h-[35%] rounded-full bg-blue-400/5 blur-[100px]"></div>
      <div class="absolute -bottom-[10%] left-[20%] w-[35%] h-[35%] rounded-full bg-emerald-400/5 blur-[100px]"></div>
    </div>

    <!-- Header -->
    <TheHeader class="sticky top-0 z-50 glass" />

    <transition name="mobile-nav">
      <div v-if="isMobileNavOpen" class="fixed inset-0 z-[90] md:hidden">
        <button
          class="absolute inset-0 bg-slate-950/25 backdrop-blur-[2px]"
          :aria-label="t('common.close')"
          @click="closeMobileNav"
        />
        <aside class="relative h-full w-72 border-r border-slate-200/60 bg-white/90 p-4 shadow-2xl backdrop-blur-xl">
          <TheSidebar class="pt-16" @navigate="closeMobileNav" />
        </aside>
      </div>
    </transition>

    <div class="flex flex-grow relative z-10">
      <!-- Sidebar -->
      <aside class="hidden md:block w-64 flex-shrink-0 border-r border-slate-200/60 bg-white/40 backdrop-blur-sm">
        <TheSidebar class="sticky top-16 h-[calc(100vh-4rem)] p-4" />
      </aside>

      <!-- Main Content Area -->
      <main class="flex-grow p-4 md:p-8 overflow-x-hidden">
        <div class="max-w-7xl mx-auto animate-fade-in">
          <RouterView v-slot="{ Component }">
            <transition name="page" mode="out-in">
              <component :is="Component" />
            </transition>
          </RouterView>
        </div>
      </main>
    </div>

    <Toaster />
  </div>
</template>

<style scoped>
.page-enter-active,
.page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.mobile-nav-enter-active,
.mobile-nav-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.mobile-nav-enter-from,
.mobile-nav-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}
</style>
