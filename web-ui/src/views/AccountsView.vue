<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listAccounts, getAccount, createAccount, updateAccount, deleteAccount, type AccountItem } from '@/api/accounts'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { toast } from '@/components/ui/toast'

const accounts = ref<AccountItem[]>([])
const isLoading = ref(false)
const isSaving = ref(false)
const router = useRouter()

const isCreateDialogOpen = ref(false)
const isEditDialogOpen = ref(false)
const isDeleteDialogOpen = ref(false)

const newName = ref('')
const newContent = ref('')
const editName = ref('')
const editContent = ref('')
const deleteName = ref('')

async function fetchAccounts() {
  isLoading.value = true
  try {
    accounts.value = await listAccounts()
  } catch (e) {
    toast({ title: '加载账号失败', description: (e as Error).message, variant: 'destructive' })
  } finally {
    isLoading.value = false
  }
}

function openCreateDialog() {
  newName.value = ''
  newContent.value = ''
  isCreateDialogOpen.value = true
}

async function openEditDialog(name: string) {
  isSaving.value = true
  try {
    const detail = await getAccount(name)
    editName.value = detail.name
    editContent.value = detail.content
    isEditDialogOpen.value = true
  } catch (e) {
    toast({ title: '加载账号内容失败', description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

function openDeleteDialog(name: string) {
  deleteName.value = name
  isDeleteDialogOpen.value = true
}

function goCreateTask(name: string) {
  router.push({ path: '/tasks', query: { account: name, create: '1' } })
}

async function handleCreateAccount() {
  if (!newName.value.trim() || !newContent.value.trim()) {
    toast({ title: '信息不完整', description: '请填写账号名称并粘贴 JSON 内容。', variant: 'destructive' })
    return
  }
  isSaving.value = true
  try {
    await createAccount({ name: newName.value.trim(), content: newContent.value.trim() })
    toast({ title: '账号已添加' })
    isCreateDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: '添加账号失败', description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

async function handleUpdateAccount() {
  if (!editContent.value.trim()) {
    toast({ title: '内容不能为空', description: '请粘贴 JSON 内容。', variant: 'destructive' })
    return
  }
  isSaving.value = true
  try {
    await updateAccount(editName.value, editContent.value.trim())
    toast({ title: '账号已更新' })
    isEditDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: '更新账号失败', description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

async function handleDeleteAccount() {
  isSaving.value = true
  try {
    await deleteAccount(deleteName.value)
    toast({ title: '账号已删除' })
    isDeleteDialogOpen.value = false
    await fetchAccounts()
  } catch (e) {
    toast({ title: '删除账号失败', description: (e as Error).message, variant: 'destructive' })
  } finally {
    isSaving.value = false
  }
}

onMounted(fetchAccounts)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">闲鱼账号管理</h1>
        <p class="text-sm text-gray-500 mt-1">使用 Chrome 扩展提取登录状态 JSON，并在此添加账号。</p>
      </div>
      <Button @click="openCreateDialog">+ 添加账号</Button>
    </div>

    <Card class="mb-6">
      <CardHeader>
        <CardTitle>获取闲鱼Cookie</CardTitle>
      </CardHeader>
      <CardContent class="text-sm text-gray-600">
        <ol class="list-decimal list-inside space-y-1">
          <li>
            安装
            <a
              class="text-blue-600 hover:underline"
              href="https://chromewebstore.google.com/detail/xianyu-login-state-extrac/eidlpfjiodpigmfcahkmlenhppfklcoa"
              target="_blank"
              rel="noopener noreferrer"
            >闲鱼登录状态提取扩展</a>
          </li>
          <li>
            打开并登录
            <a
              class="text-blue-600 hover:underline"
              href="https://www.goofish.com"
              target="_blank"
              rel="noopener noreferrer"
            >闲鱼官网</a>
          </li>
          <li>点击扩展图标，选择“提取登录状态”，再点击“复制到剪贴板”</li>
          <li>回到本页，点击“添加账号”，粘贴 JSON 内容并保存</li>
          <li>如果配置多账号，不要在当前窗口退出闲鱼账号，可以新开无痕窗口登录提取其他账号Cookie</li>
        </ol>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>账号列表</CardTitle>
        <CardDescription>账号文件保存在 state/ 目录下，可绑定到任务。</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>账号名称</TableHead>
              <TableHead>状态文件</TableHead>
              <TableHead class="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="isLoading">
              <TableCell colspan="3" class="h-20 text-center text-muted-foreground">加载中...</TableCell>
            </TableRow>
            <TableRow v-else-if="accounts.length === 0">
              <TableCell colspan="3" class="h-20 text-center text-muted-foreground">暂无账号</TableCell>
            </TableRow>
            <TableRow v-else v-for="account in accounts" :key="account.name">
              <TableCell class="font-medium">{{ account.name }}</TableCell>
              <TableCell class="text-sm text-gray-500">{{ account.path }}</TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-2">
                  <Button size="sm" variant="outline" @click="goCreateTask(account.name)">创建任务</Button>
                  <Button size="sm" variant="outline" @click="openEditDialog(account.name)">更新</Button>
                  <Button size="sm" variant="destructive" @click="openDeleteDialog(account.name)">删除</Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <Dialog v-model:open="isCreateDialogOpen">
      <DialogContent class="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>添加闲鱼账号</DialogTitle>
          <DialogDescription>粘贴通过 Chrome 插件提取的 JSON 内容。</DialogDescription>
        </DialogHeader>
        <div class="space-y-4">
          <div class="grid gap-2">
            <Label>账号名称</Label>
            <Input v-model="newName" placeholder="例如：acc_1" />
          </div>
          <div class="grid gap-2">
            <Label>JSON 内容</Label>
            <Textarea v-model="newContent" class="min-h-[200px]" placeholder="请粘贴登录状态 JSON..." />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isCreateDialogOpen = false">取消</Button>
          <Button :disabled="isSaving" @click="handleCreateAccount">
            {{ isSaving ? '保存中...' : '保存' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isEditDialogOpen">
      <DialogContent class="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>更新账号：{{ editName }}</DialogTitle>
          <DialogDescription>替换账号的登录状态 JSON。</DialogDescription>
        </DialogHeader>
        <div class="space-y-4">
          <div class="grid gap-2">
            <Label>JSON 内容</Label>
            <Textarea v-model="editContent" class="min-h-[200px]" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="isEditDialogOpen = false">取消</Button>
          <Button :disabled="isSaving" @click="handleUpdateAccount">
            {{ isSaving ? '保存中...' : '保存' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="isDeleteDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除账号</DialogTitle>
          <DialogDescription>确认删除账号 {{ deleteName }} 吗？该操作不可恢复。</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="isDeleteDialogOpen = false">取消</Button>
          <Button variant="destructive" :disabled="isSaving" @click="handleDeleteAccount">
            {{ isSaving ? '删除中...' : '删除' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
