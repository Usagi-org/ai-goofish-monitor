<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/components/ui/toast/use-toast'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
 import { Badge } from '@/components/ui/badge'
import { Search, User, Star, CreditCard, Package } from 'lucide-vue-next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { getSellerInfo, searchByItemId, getSearchHistory } from '@/api/sellers'
import type { ItemSearchResult, SearchHistoryItem } from '@/types/seller.d.ts'

const { toast } = useToast()

const activeTab = ref<'seller' | 'item'>('seller')
const sellerId = ref('')
const itemId = ref('')
const sellerInfo = ref<any>(null)
const itemInfo = ref<ItemSearchResult | null>(null)
const searchHistory = ref<SearchHistoryItem[]>([])
const loading = ref(false)

async function handleSellerSearch() {
  if (!sellerId.value) return
  loading.value = true
  try {
    const info = await getSellerInfo(sellerId.value)
    sellerInfo.value = info
    toast({
      title: '搜索成功',
      description: '已找到卖家信息',
    })
  } catch (error: any) {
    toast({
      title: '搜索失败',
      description: error.message,
      variant: 'destructive',
    })
    sellerInfo.value = null
  } finally {
    loading.value = false
  }
}

async function handleItemSearch() {
  if (!itemId.value) return
  loading.value = true
  try {
    const result = await searchByItemId(itemId.value)
    itemInfo.value = result
    toast({
      title: '搜索成功',
      description: '已找到商品信息',
    })
    // 刷新搜索历史
    await loadSearchHistory()
  } catch (error: any) {
    toast({
      title: '搜索失败',
      description: error.message,
      variant: 'destructive',
    })
    itemInfo.value = null
  } finally {
    loading.value = false
  }
}

async function loadSearchHistory() {
  try {
    searchHistory.value = await getSearchHistory(10)
  } catch (e) {
    // 静默失败
  }
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatRelativeTime(dateStr: string) {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  return `${days}天前`
}

onMounted(() => {
  loadSearchHistory()
})
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle>卖家/商品搜索</CardTitle>
      <CardDescription>
        通过卖家 ID 或商品 ID 查询信息
      </CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <Tabs v-model="activeTab">
        <TabsList class="grid w-full grid-cols-2">
          <TabsTrigger value="seller">
            <User class="w-4 h-4 mr-2" />
            卖家 ID
          </TabsTrigger>
          <TabsTrigger value="item">
            <Package class="w-4 h-4 mr-2" />
            商品 ID
          </TabsTrigger>
        </TabsList>

        <!-- 卖家 ID 搜索 -->
        <TabsContent value="seller" class="space-y-4">
          <div class="flex gap-2">
            <div class="flex-1">
              <Input
                v-model="sellerId"
                placeholder="请输入卖家 ID"
                @keyup.enter="handleSellerSearch"
              />
            </div>
            <Button @click="handleSellerSearch" :disabled="loading || !sellerId">
              <Search class="w-4 h-4 mr-2" />
              搜索
            </Button>
          </div>

          <div v-if="sellerInfo" class="rounded-lg border bg-slate-50 p-4 space-y-3">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                <User class="w-6 h-6 text-primary" />
              </div>
              <div class="flex-1">
                <h4 class="font-semibold text-lg">{{ sellerInfo['卖家昵称'] || '-' }}</h4>
                <p class="text-sm text-slate-500">ID: {{ sellerInfo['卖家 ID'] }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-lg bg-white p-3 border">
                <div class="flex items-center gap-2 text-sm text-slate-500">
                  <Star class="w-4 h-4" />
                  芝麻信用
                </div>
                <p class="text-lg font-bold text-amber-600 mt-1">
                  {{ sellerInfo['芝麻信用'] || '未认证' }}
                </p>
              </div>
              <div class="rounded-lg bg-white p-3 border">
                <div class="flex items-center gap-2 text-sm text-slate-500">
                  <CreditCard class="w-4 h-4" />
                  卖家类型
                </div>
                <p class="text-lg font-bold mt-1">
                  {{ sellerInfo['卖家类型'] || '个人' }}
                </p>
              </div>
            </div>

            <div class="text-xs text-slate-500">
              <p>最后更新时间：{{ formatDate(sellerInfo.last_updated) }}</p>
            </div>
          </div>
        </TabsContent>

        <!-- 商品 ID 搜索 -->
        <TabsContent value="item" class="space-y-4">
          <div class="flex gap-2">
            <div class="flex-1">
              <Input
                v-model="itemId"
                placeholder="请输入商品 ID"
                @keyup.enter="handleItemSearch"
              />
            </div>
            <Button @click="handleItemSearch" :disabled="loading || !itemId">
              <Search class="w-4 h-4 mr-2" />
              搜索
            </Button>
          </div>

          <div v-if="itemInfo" class="rounded-lg border bg-slate-50 p-4 space-y-3">
            <div class="flex items-start gap-3">
              <div class="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <Package class="w-6 h-6 text-primary" />
              </div>
              <div class="flex-1 min-w-0">
                <h4 class="font-semibold text-lg truncate">{{ itemInfo['商品标题'] }}</h4>
                <p class="text-sm text-slate-500">ID: {{ itemInfo['商品 ID'] }}</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-lg bg-white p-3 border">
                <div class="text-sm text-slate-500">当前售价</div>
                <p class="text-lg font-bold text-red-600 mt-1">{{ itemInfo['当前售价'] }}</p>
              </div>
              <div class="rounded-lg bg-white p-3 border">
                <div class="text-sm text-slate-500">原价</div>
                <p class="text-lg font-bold text-slate-700 mt-1">{{ itemInfo['商品原价'] || '暂无' }}</p>
              </div>
              <div class="rounded-lg bg-white p-3 border">
                <div class="text-sm text-slate-500">想要人数</div>
                <p class="text-lg font-bold mt-1">{{ itemInfo['想要人数'] || '0' }}</p>
              </div>
              <div class="rounded-lg bg-white p-3 border">
                <div class="text-sm text-slate-500">发货地区</div>
                <p class="text-lg font-bold mt-1">{{ itemInfo['发货地区'] }}</p>
              </div>
            </div>

            <div v-if="itemInfo['商品标签'] && itemInfo['商品标签'].length > 0" class="flex flex-wrap gap-2">
              <Badge v-for="(tag, index) in itemInfo['商品标签']" :key="index" variant="secondary">
                {{ tag }}
              </Badge>
            </div>

            <div class="text-xs text-slate-500 space-y-1">
              <p>卖家：{{ itemInfo['卖家昵称'] }}</p>
              <p>发布时间：{{ itemInfo['发布时间'] }}</p>
              <a :href="itemInfo['商品链接']" target="_blank" class="text-primary hover:underline">
                查看商品链接 →
              </a>
            </div>
          </div>

          <!-- 搜索历史 -->
          <div v-if="searchHistory.length > 0" class="pt-4 border-t">
            <h5 class="text-sm font-medium mb-2">搜索历史</h5>
            <div class="space-y-2 max-h-48 overflow-y-auto">
              <div
                v-for="(item, index) in searchHistory"
                :key="index"
                class="flex items-center justify-between p-2 rounded-lg bg-slate-100 hover:bg-slate-200 cursor-pointer"
                @click="() => { itemId = item.search_value; handleItemSearch() }"
              >
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium truncate">{{ item.search_value }}</p>
                  <p class="text-xs text-slate-500">{{ formatRelativeTime(item.searched_at) }}</p>
                </div>
                <Search class="w-4 h-4 text-slate-400" />
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </CardContent>
  </Card>
</template>
