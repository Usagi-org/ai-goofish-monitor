<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/components/ui/toast/use-toast'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Trash2, Shield, ShieldAlert, UserPlus, UserSearch } from 'lucide-vue-next'
import { getBlacklist, getWhitelist, removeFromList, addToBlacklist, addToWhitelist } from '@/api/sellers'
import type { SellerListResponse } from '@/types/seller.d.ts'
import SellerSearch from '@/components/sellers/SellerSearch.vue'

const { toast } = useToast()

const blacklist = ref<SellerListResponse[]>([])
const whitelist = ref<SellerListResponse[]>([])
const dialogOpen = ref(false)
const selectedSellerId = ref('')
const reason = ref('')
const listType = ref<'blacklist' | 'whitelist'>('blacklist')

async function loadLists() {
  try {
    blacklist.value = await getBlacklist()
    whitelist.value = await getWhitelist()
  } catch (error: any) {
    toast({
      title: '加载失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

async function handleRemove(sellerId: string) {
  try {
    await removeFromList(sellerId)
    toast({
      title: '已移除',
      description: `卖家 ${sellerId} 已从列表中移除`,
    })
    await loadLists()
  } catch (error: any) {
    toast({
      title: '操作失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

function openAddDialog(type: 'blacklist' | 'whitelist') {
  listType.value = type
  selectedSellerId.value = ''
  reason.value = ''
  dialogOpen.value = true
}

async function handleAdd() {
  if (!selectedSellerId.value) {
    toast({
      title: '请输入卖家 ID',
      description: '卖家 ID 不能为空',
      variant: 'destructive',
    })
    return
  }

  try {
    if (listType.value === 'blacklist') {
      await addToBlacklist(selectedSellerId.value, reason.value)
    } else {
      await addToWhitelist(selectedSellerId.value, reason.value)
    }
    toast({
      title: '操作成功',
      description: `卖家 ${selectedSellerId.value} 已添加到${listType.value === 'blacklist' ? '黑名单' : '白名单'}`,
    })
    dialogOpen.value = false
    await loadLists()
  } catch (error: any) {
    toast({
      title: '操作失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '永久'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadLists()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold">卖家管理</h2>
        <p class="text-sm text-slate-500">
          管理卖家黑名单和白名单
        </p>
      </div>
      <div class="flex gap-2">
        <Button @click="openAddDialog('blacklist')" variant="destructive">
          <ShieldAlert class="w-4 h-4 mr-2" />
          添加黑名单
        </Button>
        <Button @click="openAddDialog('whitelist')" variant="default" class="bg-emerald-600 hover:bg-emerald-700">
          <Shield class="w-4 h-4 mr-2" />
          添加白名单
        </Button>
      </div>
    </div>

    <Tabs default-value="blacklist">
      <TabsList>
        <TabsTrigger value="blacklist">
          <ShieldAlert class="w-4 h-4 mr-2" />
          黑名单
          <Badge variant="secondary" class="ml-2">{{ blacklist.length }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="whitelist">
          <Shield class="w-4 h-4 mr-2" />
          白名单
          <Badge variant="secondary" class="ml-2">{{ whitelist.length }}</Badge>
        </TabsTrigger>
        <TabsTrigger value="search">
          <UserSearch class="w-4 h-4 mr-2" />
          卖家搜索
        </TabsTrigger>
      </TabsList>

      <TabsContent value="blacklist">
        <Card>
          <CardHeader>
            <CardTitle>黑名单卖家</CardTitle>
            <CardDescription>
              被加入黑名单的卖家将不会出现在监控结果中
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table v-if="blacklist.length > 0">
              <TableHeader>
                <TableRow>
                  <TableHead>卖家 ID</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead>创建于</TableHead>
                  <TableHead>过期时间</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="item in blacklist" :key="item.seller_id">
                  <TableCell class="font-medium">{{ item.seller_id }}</TableCell>
                  <TableCell>{{ item.reason || '-' }}</TableCell>
                  <TableCell>{{ formatDate(item.created_at) }}</TableCell>
                  <TableCell>{{ formatDate(item.expires_at) }}</TableCell>
                  <TableCell class="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      @click="handleRemove(item.seller_id)"
                    >
                      <Trash2 class="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div v-else class="text-center py-8 text-slate-500">
              <UserPlus class="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>暂无黑名单卖家</p>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="whitelist">
        <Card>
          <CardHeader>
            <CardTitle>白名单卖家</CardTitle>
            <CardDescription>
              白名单卖家的商品将被优先监控
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table v-if="whitelist.length > 0">
              <TableHeader>
                <TableRow>
                  <TableHead>卖家 ID</TableHead>
                  <TableHead>原因</TableHead>
                  <TableHead>创建于</TableHead>
                  <TableHead>过期时间</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="item in whitelist" :key="item.seller_id">
                  <TableCell class="font-medium">{{ item.seller_id }}</TableCell>
                  <TableCell>{{ item.reason || '-' }}</TableCell>
                  <TableCell>{{ formatDate(item.created_at) }}</TableCell>
                  <TableCell>{{ formatDate(item.expires_at) }}</TableCell>
                  <TableCell class="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      @click="handleRemove(item.seller_id)"
                    >
                      <Trash2 class="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div v-else class="text-center py-8 text-slate-500">
              <UserPlus class="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>暂无白名单卖家</p>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="search">
        <SellerSearch />
      </TabsContent>
    </Tabs>

    <!-- 添加卖家对话框 -->
    <Dialog v-model:open="dialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            添加到{{ listType === 'blacklist' ? '黑名单' : '白名单' }}
          </DialogTitle>
          <DialogDescription>
            输入卖家 ID 和原因（可选）
          </DialogDescription>
        </DialogHeader>
        <div class="grid gap-4 py-4">
          <div class="grid gap-2">
            <Label for="seller-id-add">卖家 ID</Label>
            <Input
              id="seller-id-add"
              v-model="selectedSellerId"
              placeholder="请输入卖家 ID"
            />
          </div>
          <div class="grid gap-2">
            <Label for="reason-add">原因 (可选)</Label>
            <Textarea
              id="reason-add"
              v-model="reason"
              placeholder="添加到此列表的原因"
              rows="3"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="dialogOpen = false">取消</Button>
          <Button
            @click="handleAdd"
            :variant="listType === 'blacklist' ? 'destructive' : 'default'"
            :class="listType === 'whitelist' && 'bg-emerald-600 hover:bg-emerald-700'"
          >
            确认添加
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
