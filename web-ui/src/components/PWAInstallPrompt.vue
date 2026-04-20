<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { X } from 'lucide-vue-next'

const showInstallPrompt = ref(false)
const deferredPrompt = ref<any>(null)

onMounted(() => {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt.value = e
    showInstallPrompt.value = true
  })

  window.addEventListener('appinstalled', () => {
    showInstallPrompt.value = false
    deferredPrompt.value = null
  })
})

async function handleInstall() {
  if (!deferredPrompt.value) return

  deferredPrompt.value.prompt()
  const { outcome } = await deferredPrompt.value.userChoice

  if (outcome === 'accepted') {
    showInstallPrompt.value = false
    deferredPrompt.value = null
  }
}

function dismiss() {
  showInstallPrompt.value = false
}
</script>

<template>
  <div
    v-if="showInstallPrompt"
    class="fixed bottom-4 right-4 z-50 max-w-sm rounded-2xl bg-slate-900/95 backdrop-blur-sm p-4 shadow-xl border border-slate-700 animate-in slide-in-from-bottom-4"
  >
    <div class="flex items-start gap-3">
      <div class="flex-1">
        <h4 class="text-sm font-semibold text-white mb-1">
          安装到桌面
        </h4>
        <p class="text-xs text-slate-300">
          将闲鱼监控添加到桌面，快速访问
        </p>
      </div>
      <button
        @click="dismiss"
        class="text-slate-400 hover:text-white transition-colors"
      >
        <X class="w-4 h-4" />
      </button>
    </div>
    <button
      @click="handleInstall"
      class="mt-3 w-full rounded-lg bg-blue-500 py-2 text-sm font-medium text-white hover:bg-blue-600 transition-colors"
    >
      立即安装
    </button>
  </div>
</template>
