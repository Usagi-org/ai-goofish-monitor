<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'

const router = useRouter()

function goAccounts() {
  router.push('/accounts')
}
</script>

<template>
  <header class="bg-white h-16 px-6 border-b border-gray-200 flex justify-between items-center flex-shrink-0 shadow-sm z-10">
    <h1 class="text-xl font-semibold text-gray-800">
      闲鱼智能监控机器人
    </h1>
    <div class="ml-auto">
      <Button variant="outline" size="sm" @click="goAccounts">闲鱼账号管理</Button>
    </div>
  </header>
</template>
