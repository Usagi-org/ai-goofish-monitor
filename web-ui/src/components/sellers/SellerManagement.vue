<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from '@/components/ui/toast/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { addToBlacklist, addToWhitelist, getSellerInfo } from '@/api/sellers'
import type { SellerInfo } from '@/types/seller.d.ts'
import { User, Shield, ShieldAlert } from 'lucide-vue-next'

const { toast } = useToast()

const sellerId = ref('')
const reason = ref('')
const sellerInfo = ref<SellerInfo | null>(null)
const loading = ref(false)

async function fetchSellerInfo() {
  if (!sellerId.value) return
  loading.value = true
  try {
    const info = await getSellerInfo(sellerId.value)
    sellerInfo.value = info
  } catch (error: any) {
    toast({
      title: '获取卖家信息失败',
      description: error.message,
      variant: 'destructive',
    })
  } finally {
    loading.value = false
  }
}

async function handleAddToBlacklist() {
  if (!sellerId.value) return
  try {
    await addToBlacklist(sellerId.value, reason.value)
    toast({
      title: '已成功添加到黑名单',
      description: `卖家 ${sellerId.value} 已被加入黑名单`,
    })
    reason.value = ''
  } catch (error: any) {
    toast({
      title: '操作失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

async function handleAddToWhitelist() {
  if (!sellerId.value) return
  try {
    await addToWhitelist(sellerId.value, reason.value)
    toast({
      title: '已成功添加到白名单',
      description: `卖家 ${sellerId.value} 已被加入白名单`,
    })
    reason.value = ''
  } catch (error: any) {
    toast({
      title: '操作失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>卖家管理</CardTitle>
      <CardDescription>
        通过卖家 ID 管理黑名单/白名单
      </CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="grid gap-2">
        <Label for="seller-id">卖家 ID</Label>
        <div class="flex gap-2">
          <Input
            id="seller-id"
            v-model="sellerId"
            placeholder="请输入卖家 ID"
            @keyup.enter="fetchSellerInfo"
          />
          <Button @click="fetchSellerInfo" :disabled="loading || !sellerId">
            查询
          </Button>
        </div>
      </div>

      <div v-if="sellerInfo" class="rounded-lg border bg-slate-50 p-4">
        <div class="flex items-center gap-3 mb-4">
          <div class="h-12 w-12 rounded-full bg-slate-200 flex items-center justify-center">
            <User class="h-6 w-6 text-slate-500" />
          </div>
          <div>
            <h4 class="font-semibold">{{ sellerInfo.seller_nickname }}</h4>
            <p class="text-sm text-slate-500">ID: {{ sellerInfo.seller_id }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span class="text-slate-500">芝麻信用:</span>
            <span class="ml-2 font-medium">{{ sellerInfo.zhima_credit || '未认证' }}</span>
          </div>
          <div>
            <span class="text-slate-500">注册天数:</span>
            <span class="ml-2 font-medium">{{ sellerInfo.registration_days || '-' }} 天</span>
          </div>
          <div>
            <span class="text-slate-500">好评率:</span>
            <span class="ml-2 font-medium">{{ sellerInfo.good_rate || '-' }}</span>
          </div>
          <div>
            <span class="text-slate-500">在售商品:</span>
            <span class="ml-2 font-medium">{{ sellerInfo.total_items || '-' }}</span>
          </div>
        </div>
      </div>

      <div class="grid gap-2">
        <Label for="reason">原因 (可选)</Label>
        <Input
          id="reason"
          v-model="reason"
          placeholder="添加到此列表的原因"
        />
      </div>

      <div class="flex gap-2">
        <Button
          variant="destructive"
          @click="handleAddToBlacklist"
          :disabled="!sellerId"
          class="flex-1"
        >
          <ShieldAlert class="w-4 h-4 mr-2" />
          加入黑名单
        </Button>
        <Button
          variant="default"
          @click="handleAddToWhitelist"
          :disabled="!sellerId"
          class="flex-1 bg-emerald-600 hover:bg-emerald-700"
        >
          <Shield class="w-4 h-4 mr-2" />
          加入白名单
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
