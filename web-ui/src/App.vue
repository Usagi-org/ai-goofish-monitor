<script setup lang="ts">
import { RouterView } from 'vue-router'
import Toaster from '@/components/ui/toast/Toaster.vue'
import PWAInstallPrompt from '@/components/PWAInstallPrompt.vue'
</script>

<template>
  <RouterView />
  <Toaster />
  <PWAInstallPrompt />
</template>
