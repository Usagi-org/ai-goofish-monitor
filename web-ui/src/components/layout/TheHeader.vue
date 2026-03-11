<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import DashboardTaskSearch from '@/components/layout/DashboardTaskSearch.vue'
import { 
  Zap, 
  Bell, 
  Search, 
  UserCircle,
  HelpCircle,
  Menu
} from 'lucide-vue-next'
import Badge from '@/components/ui/badge/Badge.vue'
import { useMobileNav } from '@/composables/useMobileNav'

const router = useRouter()
const route = useRoute()
const { toggleMobileNav } = useMobileNav()
const inactiveSearchValue = ref('')

const isDashboard = computed(() => route.name === 'Dashboard')

function goAccounts() {
  router.push('/accounts')
}

function goNotifications() {
  router.push({ name: 'Settings', query: { tab: 'notifications' } })
}

function goPrompts() {
  router.push({ name: 'Settings', query: { tab: 'prompts' } })
}
</script>

<template>
  <header class="flex items-center justify-between px-6 h-16 bg-white/60 backdrop-blur-md border-b border-slate-200/60 sticky top-0 z-[100]">
    <!-- Brand Logo -->
    <div class="flex items-center gap-2 group cursor-pointer" @click="router.push('/')">
      <div class="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/20 transition-transform group-hover:rotate-12">
        <Zap class="w-5 h-5 text-white fill-white" />
      </div>
      <h1 class="text-lg font-black text-slate-800 tracking-tighter">
        AI <span class="text-primary">Xianyu</span> Hunter
      </h1>
      <Badge variant="outline" class="ml-2 text-[10px] font-bold border-primary/20 text-primary bg-primary/5 uppercase tracking-widest hidden sm:flex">
        PRO
      </Badge>
    </div>

    <!-- Search & Navigation -->
    <div class="hidden md:flex flex-grow max-w-md mx-8">
      <DashboardTaskSearch v-if="isDashboard" />
      <div v-else class="relative w-full group">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 transition-colors" />
        <input 
          type="text" 
          v-model="inactiveSearchValue"
          placeholder="任务搜索仅在监控概览页可用..."
          class="w-full h-10 pl-10 pr-4 bg-slate-100/50 border border-slate-200/50 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-white focus:border-primary/50"
        />
        <kbd class="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded border border-slate-300 bg-white text-[10px] text-slate-400 font-sans shadow-sm pointer-events-none">
          /
        </kbd>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1 sm:gap-2 mr-2">
         <Button variant="ghost" size="icon" class="rounded-full text-slate-500 hover:text-primary hover:bg-primary/10" @click="goNotifications">
            <Bell class="w-5 h-5" />
         </Button>
         <Button variant="ghost" size="icon" class="rounded-full text-slate-500 hover:text-primary hover:bg-primary/10" @click="goPrompts">
            <HelpCircle class="w-5 h-5" />
         </Button>
      </div>
      
      <div class="h-6 w-px bg-slate-200 mx-1 hidden sm:block"></div>

      <Button 
        variant="ghost" 
        class="hidden sm:flex items-center gap-2 pl-2 pr-4 rounded-full hover:bg-slate-100 transition-all active:scale-95"
        @click="goAccounts"
      >
        <div class="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center overflow-hidden border border-slate-300 shadow-sm">
           <UserCircle class="w-6 h-6 text-slate-500" />
        </div>
        <div class="text-left hidden lg:block">
           <p class="text-xs font-black text-slate-700 leading-none mb-0.5">Xianyu Admin</p>
           <p class="text-[10px] text-slate-400 font-medium">账号管理</p>
        </div>
      </Button>

      <Button variant="ghost" size="icon" class="md:hidden" @click="toggleMobileNav">
         <Menu class="w-6 h-6 text-slate-700" />
      </Button>
    </div>
  </header>
</template>
