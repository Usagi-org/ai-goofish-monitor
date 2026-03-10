<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import type { RotationSettings } from '@/api/settings'

defineProps<{
  settings: RotationSettings
  isReady: boolean
  isSaving: boolean
}>()

const emit = defineEmits<{
  (e: 'save'): void
}>()
</script>

<template>
  <Card class="overflow-hidden border-slate-200">
    <CardHeader>
      <CardTitle>账号与代理轮换</CardTitle>
      <CardDescription>显式配置多账号切换策略，并保留代理池控制。</CardDescription>
    </CardHeader>
    <CardContent v-if="isReady" class="grid gap-6 lg:grid-cols-2">
      <section class="rounded-[28px] border border-[#d7d0c6] bg-[linear-gradient(145deg,#f6f2e9_0%,#efe8db_100%)] p-5 shadow-[0_14px_30px_rgba(69,52,29,0.08)]">
        <div class="mb-5 flex items-center justify-between">
          <div>
            <h3 class="font-semibold text-[#2d261f]">账号轮换</h3>
            <p class="text-sm text-[#786858]">为任务提供自动账号池切换。</p>
          </div>
          <Switch v-model:checked="settings.ACCOUNT_ROTATION_ENABLED" />
        </div>

        <div class="grid gap-4">
          <div class="grid gap-2">
            <Label>账号目录</Label>
            <Input v-model="settings.ACCOUNT_STATE_DIR" placeholder="state" />
          </div>
          <div class="grid gap-2">
            <Label>轮换模式</Label>
            <Select v-model="settings.ACCOUNT_ROTATION_MODE">
              <SelectTrigger>
                <SelectValue placeholder="请选择轮换模式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="per_task">按任务固定</SelectItem>
                <SelectItem value="on_failure">失败后轮换</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="grid gap-2">
              <Label>重试上限</Label>
              <Input v-model.number="settings.ACCOUNT_ROTATION_RETRY_LIMIT" type="number" min="1" />
            </div>
            <div class="grid gap-2">
              <Label>黑名单 TTL (秒)</Label>
              <Input v-model.number="settings.ACCOUNT_BLACKLIST_TTL" type="number" min="0" />
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
        <div class="mb-5 flex items-center justify-between">
          <div>
            <h3 class="font-semibold text-slate-900">代理轮换</h3>
            <p class="text-sm text-slate-500">代理池保持独立控制，和账号轮换可以叠加。</p>
          </div>
          <Switch v-model:checked="settings.PROXY_ROTATION_ENABLED" />
        </div>

        <div class="grid gap-4">
          <div class="grid gap-2">
            <Label>轮换模式</Label>
            <Select v-model="settings.PROXY_ROTATION_MODE">
              <SelectTrigger>
                <SelectValue placeholder="请选择轮换模式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="per_task">按任务固定</SelectItem>
                <SelectItem value="on_failure">失败后轮换</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid gap-2">
            <Label>代理池 (逗号分隔)</Label>
            <Textarea
              v-model="settings.PROXY_POOL"
              class="min-h-[120px]"
              placeholder="http://127.0.0.1:7890,socks5://127.0.0.1:1080"
            />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="grid gap-2">
              <Label>重试上限</Label>
              <Input v-model.number="settings.PROXY_ROTATION_RETRY_LIMIT" type="number" min="1" />
            </div>
            <div class="grid gap-2">
              <Label>黑名单 TTL (秒)</Label>
              <Input v-model.number="settings.PROXY_BLACKLIST_TTL" type="number" min="0" />
            </div>
          </div>
        </div>
      </section>
    </CardContent>
    <CardContent v-else class="py-8 text-sm text-gray-500">
      正在加载轮换配置...
    </CardContent>
    <CardFooter v-if="isReady" class="flex gap-2">
      <Button @click="emit('save')" :disabled="isSaving">保存轮换设置</Button>
    </CardFooter>
  </Card>
</template>
